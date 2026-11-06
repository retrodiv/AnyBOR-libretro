"""Run authored font images through an engine's own font and raster C code.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time
from test_historical_player import function
from native_sanitizers import sanitizer_environment

UNITS = ('bitmap.c', 'sprite.c', 'spritex8p16.c',
         'spritex8p32.c', 'pixelformat.c', 'spriteq.c')
FONT_FUNCTIONS = ('_font_unload', 'font_unload', '_font_load', 'font_load',
                  'fontmonowidth', 'fontheight', 'font_string_width',
                  'font_printf', 'screen_printf')


def matrix_digest(rows):
    """Bind case names and byte/width observations without retaining raw pixels."""
    digest = hashlib.sha256()
    for key in sorted(rows):
        digest.update(key.encode() + b'\0')
        digest.update(json.dumps(rows[key], sort_keys=True, separators=(',', ':')).encode() + b'\n')
    return digest.hexdigest()


def profile_revisions(profiles):
    if (not isinstance(profiles, (list, tuple)) or not 1 <= len(profiles) <= 128 or
            any(type(value) is not int or not 1 <= value <= 0xffffffff for value in profiles) or
            len(set(profiles)) != len(profiles)):
        raise ValueError('One to 128 unique positive 32-bit profile revisions required')
    return tuple(profiles)


def program(engine, *, blank_zero=False, dimensions=None, palette_validation=False, profile=None,
            profile_argument=False, binary_pixels=False, inset=0, ownership_validation=False,
            mask_validation=False):
    if type(inset) is not int or not 0 <= inset <= 31 or inset and dimensions is None:
        raise ValueError('A bounded glyph inset requires explicit tile dimensions')
    engine = Path(engine)
    source = (engine/'source/gamelib/font.c').read_text()
    main = (engine/'openbor.c').read_text()
    start = main.index('const s_drawmethod plainmethod =')
    plain = main[start:main.index('\n};', start)+3]
    methods = '\n'.join(function(source, name) for name in FONT_FUNCTIONS)
    if mask_validation:
        methods += '\n' + '\n'.join(function(source,name) for name in ('_font_loadmask','font_loadmask'))
    for name in ('obor_font_loading_slot', 'obor_font_cached_dimension', 'obor_font_load_glyphs'):
        if 'static int ' + name + '(' in source:
            methods = function(source, name) + '\n' + methods
    if 'static int obor_font_palette_valid(' in source:
        methods = function(source, 'obor_font_palette_valid') + '\n' + methods
    screen = (engine/'source/gamelib/screen.c').read_text()
    allocation = '\n'.join(function(screen, name) for name in ('allocscreen', 'freescreen'))
    if (any(type(value) is not bool for value in (ownership_validation,mask_validation)) or
            sum((ownership_validation,mask_validation,palette_validation)) > 1):
        raise ValueError('Choose one authored validation mode')
    body = (MASK_MAIN if mask_validation else OWNERSHIP_MAIN if ownership_validation else
            PALETTE_MAIN if palette_validation else MAIN)
    if dimensions is not None:
        if not isinstance(dimensions, (list, tuple)) or not 1 <= len(dimensions) <= 3:
            raise ValueError('Use one to three authored tile dimensions')
        if any(not isinstance(pair, (list, tuple)) or len(pair) != 2 or
               any(type(value) is not int or not 1 <= value <= 32 for value in pair)
               for pair in dimensions):
            raise ValueError('Authored tile dimensions must be integer pairs within 1..32')
        pairs = '{' + ','.join('{' + str(w) + ',' + str(h) + '}' for w, h in dimensions) + '}'
        body = body.replace('{{1,1},{8,8},{17,11}}', pairs).replace('dim<3;', 'dim<' + str(len(dimensions)) + ';')
    if profile is not None and (type(profile) is not int or not 1 <= profile <= 0xffffffff):
        raise ValueError('A profile must be a positive integer')
    if type(profile_argument) is not bool or type(binary_pixels) is not bool:
        raise ValueError('Profile and transport switches must be booleans')
    if profile is not None and profile_argument:
        raise ValueError('Fixed and argument-selected profiles are mutually exclusive')
    if 'obor_profile_build' in methods and profile is None and not profile_argument:
        raise ValueError('Profile-aware font code requires an explicit profile')
    prefix = PREFIX
    if ownership_validation or mask_validation:
        prefix = prefix.replace('FONT_METHODS', OWNERSHIP_ALLOCATOR + '\n' +
            '#define malloc font_malloc\n#define calloc font_calloc\n#define free font_free\n' +
            'FONT_METHODS\n#undef malloc\n#undef calloc\n#undef free\n')
    if inset:
        if any(inset >= min(pair) for pair in dimensions):
            raise ValueError('Glyph inset must leave pixels inside every tile')
        prefix = prefix.replace('if(on)s->data',
            'if(on && x>=' + str(inset) + ' && y>=' + str(inset) + ')s->data')
        prefix = prefix.replace('if(!PROBE_BLANK_ZERO)s->data[0]=1;', '')
    if profile is not None or profile_argument:
        prefix = prefix.replace('#undef printf', '#undef printf\nuint32_t obor_profile_build = ' + str(profile or 0) + 'u;')
    if binary_pixels and not palette_validation and not ownership_validation and not mask_validation:
        old = 'for(size_t i=0;i<bytes;++i)printf("%02x",screen->data[i]);'
        if body.count(old) != 1:
            raise ValueError('One authored raster transport boundary required')
        body = body.replace(old, 'printf("%zu\\n",bytes);\n'
                                 '    assert(fwrite(screen->data,1,bytes,stdout)==bytes);')
    if profile_argument:
        if body.count('int main(void) {') != 1:
            raise ValueError('One authored probe entry required')
        body = body.replace('int main(void) {', 'static int font_probe_main(void) {')
        body += r'''
#include <errno.h>
int main(int argc,char **argv) {
    if(argc!=2 || argv[1][0]<'1' || argv[1][0]>'9')return 2;
    errno=0;char *end=NULL;unsigned long long value=strtoull(argv[1],&end,10);
    if(errno || !end || *end || value>UINT32_MAX)return 2;
    obor_profile_build=(uint32_t)value;
    printf("PROFILE %lu\n",(unsigned long)obor_profile_build);
    return font_probe_main();
}
'''
    return ('#define PROBE_BLANK_ZERO ' + str(int(blank_zero)) + '\n' +
            prefix.replace('PLAIN_METHOD', plain).replace('SCREEN_ALLOCATION', allocation).replace('FONT_METHODS', methods) + body)


def read_rows(output, *, binary_pixels=False, profile=None):
    """Read the bounded raster protocol without retaining raw pixel buffers."""
    if profile is not None and output.readline(128) != ('PROFILE %d\n' % profile).encode():
        raise RuntimeError('Missing or different native profile marker')
    rows = {}
    while True:
        line = output.readline(65537)
        if not line:
            break
        if len(line) > 65536 or not line.endswith(b'\n'):
            raise RuntimeError('Oversized or unfinished raster record')
        try:
            text = line[:-1].decode('ascii')
            kind, separator, value = text.rpartition(' ')
            if not separator:
                raise ValueError('Missing record payload')
            if text.startswith('RASTER '):
                if binary_pixels:
                    count = int(value)
                    if not 0 < count <= 24 * 20 * 4:
                        raise ValueError('Raster byte count outside the authored screen')
                    raw = output.read(count)
                    if len(raw) != count or output.read(1) != b'\n':
                        raise ValueError('Truncated or unframed raster bytes')
                else:
                    if not 0 < len(value) <= 24 * 20 * 4 * 2:
                        raise ValueError('Raster hex length outside the authored screen')
                    raw = bytes.fromhex(value)
                result = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            elif text.startswith('WIDTHS '):
                if not value.endswith(','):
                    raise ValueError('Unfinished width payload')
                words = value[:-1].split(',')
                if not 1 <= len(words) <= 256:
                    raise ValueError('Width count outside the authored table')
                result = {'widths': [int(word) for word in words]}
            else:
                raise ValueError('Unexpected record kind')
        except (ValueError, UnicodeError) as error:
            raise RuntimeError('Invalid raster record: ' + repr(line[:160])) from error
        if kind in rows:
            raise RuntimeError('Duplicate raster case: ' + kind)
        if len(rows) >= 221112:
            raise RuntimeError('Too many authored raster cases')
        rows[kind] = result
    if not rows:
        raise RuntimeError('Font raster probe produced no observations')
    return rows


PREFIX = r'''
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "types.h"
#include "font.h"
#include "screen.h"
#include "bitmap.h"
#include "sprite.h"
#include "spriteq.h"
#include "draw.h"
#include "transform.h"
#undef printf
PLAIN_METHOD
static s_font **fonts[MAX_FONTS];
static char b[1024];
static int image_mode;
static int tile_width=8,tile_height=8;
void writeToLogFile(const char *format,...) { (void)format; }
void exitIfFalse(int value,const char *expression,const char *func,const char *file,int line) {
    if(!value) {fprintf(stderr,"native assertion %s in %s at %s:%d\n",expression,func,file,line);abort();}
}
void obor_resources_forget_owner(const void *owner) { (void)owner; }
void obor_resources_bitmap_cropped(const void *bitmap,unsigned left,unsigned top,unsigned width,unsigned height) {
    (void)bitmap;(void)left;(void)top;(void)width;(void)height;
}
void obor_resources_sprite_encoded(const void *bitmap,void *owner,void *body,size_t length,unsigned x,unsigned y,unsigned width,unsigned height) {
    (void)bitmap;(void)owner;(void)body;(void)length;(void)x;(void)y;(void)width;(void)height;
}
/* Fonts use neutral transforms and only queue sprites. Unexpected alternate
   primitives fail instead of silently replacing a path under investigation. */
void gfx_draw_rotate(s_screen *d,gfx_entry *s,int x,int y,int cx,int cy,s_drawmethod *m) {abort();}
void gfx_draw_scale(s_screen *d,gfx_entry *s,int x,int y,int cx,int cy,s_drawmethod *m) {abort();}
void gfx_draw_water(s_screen *d,gfx_entry *s,int x,int y,int cx,int cy,s_drawmethod *m) {abort();}
void gfx_draw_plane(s_screen *d,gfx_entry *s,int x,int y,int cx,int cy,s_drawmethod *m) {abort();}
void putscreen(s_screen *d,s_screen *s,int x,int y,s_drawmethod *m) {abort();}
void putpixel(unsigned x,unsigned y,int colour,s_screen *s,s_drawmethod *m) {abort();}
void putline(int x,int y,int ex,int ey,int colour,s_screen *s,s_drawmethod *m) {abort();}
void putbox(int x,int y,int w,int h,int colour,s_screen *s,s_drawmethod *m) {abort();}
/* Track actual authored screen allocations, including their exact capacities.
   Production uses the engine arena's existing allocation-size query. */
static struct { void *owner; size_t bytes; } screen_allocations[32];
static void *screen_malloc(size_t bytes) {
    void *p=malloc(bytes); if(!p)return NULL;
    for(unsigned i=0;i<32;++i)if(!screen_allocations[i].owner) {
        screen_allocations[i].owner=p;screen_allocations[i].bytes=bytes;return p;
    }
    abort();
}
static void screen_free(void *p) {
    for(unsigned i=0;i<32;++i)if(screen_allocations[i].owner==p) {
        screen_allocations[i].owner=NULL;screen_allocations[i].bytes=0;free(p);return;
    }
    assert(!p);
}
size_t obor_allocation_size(const void *owner) {
    for(unsigned i=0;i<32;++i)if(screen_allocations[i].owner==owner)return screen_allocations[i].bytes;
    return 0;
}
#define malloc screen_malloc
#define free screen_free
SCREEN_ALLOCATION
#undef malloc
#undef free
static int palette_case;
static int mask_case;
int loadscreen(char *filename,char *pack,unsigned char *pal,int format,s_screen **out) {
    (void)pack;(void)pal;
    int page=0;
    char *slash=strrchr(filename,'/');
    if(slash) {page=(int)strtol(slash+1,NULL,16);if(page!=0 && page!=128 && page!=255)return 0;}
    int width=tile_width*16,height=tile_height*16;
    int is_mask=strstr(filename,"mask")!=NULL;
    if(is_mask && (mask_case==1 || (mask_case==5 && page==128)))return 0;
    if(is_mask && mask_case==2)width+=16;
    *out=allocscreen(width,height,format);assert(*out);
    s_screen *s=*out;
    memset(s->data,0,(size_t)width*height);
    if(palette_case && format==PIXEL_x8) {
        size_t bytes=obor_allocation_size(s);
        if(palette_case==1)s->palette=NULL;
        else if(palette_case==2)s->palette=(unsigned char*)s+bytes-PAL_BYTES+1;
        else if(palette_case==3)s->palette=(unsigned char*)s+bytes;
        else if(palette_case==4)s->palette=(unsigned char*)s;
        else if(palette_case==5)s->palette=(unsigned char*)s+bytes-PAL_BYTES;
        if(palette_case<5)return 1;
    }
    if(s->palette) {
        for(unsigned i=0;i<256;++i) {
            unsigned r=(i*3+page)&255,g=(i*7+page)&255,blue=(i*11+page)&255;
            if(screenformat==PIXEL_16) { uint16_t value=colour16(r,g,blue); memcpy(s->palette+2*i,&value,2); }
            else if(screenformat==PIXEL_32) { uint32_t value=colour32(r,g,blue); memcpy(s->palette+4*i,&value,4); }
            else {s->palette[3*i]=r;s->palette[3*i+1]=g;s->palette[3*i+2]=blue;}
        }
    }
    for(int glyph=0;glyph<256;++glyph) {
        int gx=(glyph&15)*tile_width,gy=(glyph>>4)*tile_height;
        if((glyph || PROBE_BLANK_ZERO) && glyph%13==0)continue;
        for(int y=0;y<tile_height;++y)for(int x=0;x<tile_width;++x) {
            int on=image_mode==0?(x>=(glyph%3) && y>=(glyph%2) && x<tile_width-1 && y<tile_height-1):
                ((x+y+glyph)%3==0 || (x==tile_width-1 && (glyph&1)) || (y==tile_height-1 && (glyph&2)));
            if(is_mask && mask_case==3 && glyph==1 && x==tile_width-1)on=0;
            if(on)s->data[(gy+y)*width+gx+x]=(unsigned char)(1+(glyph+x*5+y*9+page)%255);
        }
    }
    if(!PROBE_BLANK_ZERO)s->data[0]=1;
    return 1;
}
FONT_METHODS
'''

MAIN = r'''
static void record(const char *kind,int format,int flags,int image,int item,int position,int queue,
                   s_screen *screen) {
    printf("RASTER %s %d %d %d %d %d %d %d %d ",kind,format,flags,image,tile_width,tile_height,item,position,queue);
    size_t bytes=(size_t)screen->width*screen->height*pixelbytes[screen->pixelformat];
    for(size_t i=0;i<bytes;++i)printf("%02x",screen->data[i]);
    putchar('\n');
}
int main(void) {
    const int formats[]={PIXEL_8,PIXEL_16,PIXEL_32};
    const int dimensions[][2]={{1,1},{8,8},{17,11}};
    const int positions[][2]={{3,4},{-3,4},{3,-3},{21,4},{3,17},{-7,-7}};
    for(unsigned dim=0;dim<3;++dim)
    for(unsigned f=0;f<3;++f)for(int mono=0;mono<2;++mono)for(int image=0;image<2;++image)for(int mbs=0;mbs<2;++mbs) {
        tile_width=dimensions[dim][0];tile_height=dimensions[dim][1];
        screenformat=formats[f];pixelformat=screenformat==PIXEL_8?PIXEL_8:PIXEL_x8;
        image_mode=image;
        int flags=(mono?FONT_MONO:0)|(mbs?FONT_MBS:0);
        assert(font_load(0,"fixture","authored",flags));
        assert(fontheight(0)==tile_height && fontmonowidth(0)==tile_width);
        printf("WIDTHS %d %d %d %d %d ",screenformat,flags,image,tile_width,tile_height);
        for(int i=0;i<256;++i)printf("%d,",fonts[0][0]->token_width[i]);
        putchar('\n');
        s_screen *screen=allocscreen(24,20,screenformat);assert(screen);
        for(int glyph=1;glyph<256;++glyph) {
            char text[2]={(char)glyph,0};
            for(unsigned pos=0;pos<sizeof(positions)/sizeof(*positions);++pos)for(int queue=0;queue<2;++queue) {
                memset(screen->data,0x6d,(size_t)24*20*pixelbytes[screenformat]);
                spriteq_clear();
                int x=positions[pos][0],y=positions[pos][1];
                if(queue) {font_printf(x,y,0,0,"%s",text);spriteq_draw(screen,0,INT_MIN,INT_MAX,0,0);}
                else screen_printf(screen,x,y,0,"%s",text);
                record("glyph",screenformat,flags,image,glyph,(int)pos,queue,screen);
            }
        }
        const char *strings[]={"A B\nCZ","\x81" "QZ","QQQ", "\xff" "Z", "\x80" "QZ"};
        for(unsigned str=0;str<sizeof(strings)/sizeof(*strings);++str)for(int queue=0;queue<2;++queue) {
            memset(screen->data,0x6d,(size_t)24*20*pixelbytes[screenformat]);spriteq_clear();
            if(queue) {font_printf(-2,2,0,0,"%s",strings[str]);spriteq_draw(screen,0,INT_MIN,INT_MAX,0,0);}
            else screen_printf(screen,-2,2,0,"%s",strings[str]);
            record("string",screenformat,flags,image,(int)str,0,queue,screen);
        }
        freescreen(&screen);font_unload(0);
    }
    return 0;
}
'''


PALETTE_MAIN = r'''
int main(void) {
    const int formats[]={PIXEL_8,PIXEL_16,PIXEL_32};
    for(unsigned f=0;f<3;++f)for(int bad=0;bad<=5;++bad) {
        screenformat=formats[f];pixelformat=screenformat==PIXEL_8?PIXEL_8:PIXEL_x8;
        palette_case=bad;image_mode=1;
        int expected=screenformat==PIXEL_8 || bad==0 || bad==5;
        assert(font_load(0,"fixture","authored",0)==expected);
        if(expected) {assert(fonts[0] && fonts[0][0]);font_unload(0);}
        else assert(!fonts[0]);
        for(unsigned i=0;i<32;++i)assert(!screen_allocations[i].owner);
        printf("WIDTHS palette %d %d %d %d,\n",screenformat,bad,expected,expected);
    }
    return 0;
}
'''


OWNERSHIP_ALLOCATOR = r'''
/* Track only allocations in the font unit: borrowed palettes are interior
   pointers and must never be released as separate owners. */
static void *font_allocations[2048];
static unsigned font_attempt, font_refuse;
static void *font_malloc(size_t bytes) {
    if(++font_attempt==font_refuse)return NULL;
    void *owner=malloc(bytes);
    if(owner) {
        for(unsigned i=0;i<2048;++i)if(!font_allocations[i]) {
            font_allocations[i]=owner;return owner;
        }
        abort();
    }
    return owner;
}
static void *font_calloc(size_t count,size_t bytes) {
    assert(!count || bytes<=SIZE_MAX/count);
    void *owner=font_malloc(count*bytes);
    if(owner)memset(owner,0,count*bytes);
    return owner;
}
static void font_free(void *owner) {
    if(!owner)return;
    for(unsigned i=0;i<2048;++i)if(font_allocations[i]==owner) {
        font_allocations[i]=NULL;free(owner);return;
    }
    /* A non-owner, repeated release or borrowed palette is a failed control. */
    abort();
}
'''


OWNERSHIP_MAIN = r'''
int main(void) {
    const int formats[]={PIXEL_8,PIXEL_16,PIXEL_32};
    const unsigned failures[]={0,1,2,130,257};
    for(unsigned f=0;f<3;++f)for(unsigned n=0;n<5;++n) {
        screenformat=formats[f];pixelformat=screenformat==PIXEL_8?PIXEL_8:PIXEL_x8;
        image_mode=1;font_refuse=0;
        s_font *font=font_calloc(1,sizeof(*font));assert(font);
        font_attempt=0;font_refuse=failures[n];
        int loaded=_font_load(font,"fixture","authored");
        int refused=font_refuse && font_attempt>=font_refuse;
        assert(loaded==!refused);
        if(loaded && font->glyphs) {
            for(unsigned i=1;i<256;++i)assert(font->glyphs[i]->palette==font->glyphs[0]->palette);
        }
        _font_unload(font);
        for(unsigned i=0;i<2048;++i)assert(!font_allocations[i]);
        for(unsigned i=0;i<32;++i)assert(!screen_allocations[i].owner);
        printf("WIDTHS ownership %d %u %d,\n",screenformat,failures[n],loaded);
    }
    return 0;
}
'''


MASK_MAIN = r'''
static unsigned masks_in(const s_font *font) {
    unsigned count=0;
    if(font && font->glyphs)for(unsigned i=0;i<256;++i)count+=font->glyphs[i]->mask!=NULL;
    return count;
}
int main(void) {
    const int formats[]={PIXEL_8,PIXEL_16,PIXEL_32};
    for(unsigned f=0;f<3;++f)for(int flags=0;flags<4;++flags)for(int mode=0;mode<9;++mode) {
        screenformat=formats[f];pixelformat=screenformat==PIXEL_8?PIXEL_8:PIXEL_x8;
        image_mode=1;palette_case=mask_case=0;
        assert(font_load(0,"fixture","authored",flags));
        mask_case=mode;
        if(mode==6)palette_case=1;
        if(mode==8)font_unload(0);
        int request=mode==7 ? FONT_MBS : flags;
        int result=font_loadmask(0,"fixture-mask","authored",request);
        if(mode==4)result=font_loadmask(0,"fixture-mask","authored",request);
        unsigned counts[3]={0,0,0};
        const unsigned pages[3]={0,128,255};
        if(fonts[0])for(unsigned j=0;j<3;++j) {
            if(pages[j] && !(flags&FONT_MBS))continue;
            counts[j]=masks_in(fonts[0][pages[j]]);
        }
        printf("WIDTHS mask %d %d %d %d,%u,%u,%u,\n",screenformat,flags,mode,
               result,counts[0],counts[1],counts[2]);
        font_unload(0);
        assert(!font_loadmask(-1,"fixture-mask","authored",flags));
        for(unsigned i=0;i<2048;++i)assert(!font_allocations[i]);
        for(unsigned i=0;i<32;++i)assert(!screen_allocations[i].owner);
    }
    return 0;
}
'''


def compile_probe(engine, port_include, work, code, cc, sanitizers, null_offset_control):
    (work / 'probe.c').write_text(code)
    inputs = [engine / 'source/gamelib' / name for name in UNITS]
    compiler = cc or shlex.split(os.environ.get('HOST_CC', 'cc'))
    flags = ['-std=gnu99', '-O1', '-g', '-fcommon', '-fno-strict-aliasing',
             '-ffunction-sections', '-fdata-sections', '-Wno-deprecated-declarations',
             '-I', str(engine/'source'), '-I', str(engine/'source/gamelib'),
             '-I', str(Path(port_include).resolve())]
    if sanitizers:
        flags += ['-fsanitize=address,undefined,pointer-overflow']
        if null_offset_control:
            flags += ['-fno-sanitize=null']
    link = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-Wl,--gc-sections']
    command = [*compiler, *flags, str(work/'probe.c'), *map(str, inputs),
               *link, '-lm', '-o', str(work/'probe')]
    result = subprocess.run(command, text=True, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Font raster probe compilation failed:\n' + result.stderr[-14000:])
    return inputs


def source_hashes(engine, inputs):
    return {str(p.relative_to(engine)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [*inputs, engine/'source/gamelib/screen.c', engine/'source/gamelib/font.c',
                      engine/'source/gamelib/font.h', engine/'openbor.c']}


def run_profiles(engine, port_include, profiles, *, cc=None, sanitizers=True,
                 null_offset_control=False, blank_zero=False, dimensions=None,
                 palette_validation=False, retain_rows=False, inset=0, ownership_validation=False,
                 mask_validation=False):
    """Compile once, then observe each requested profile in a fresh process."""
    revisions = profile_revisions(profiles)
    for value in (sanitizers, null_offset_control, blank_zero, palette_validation, retain_rows, ownership_validation, mask_validation):
        if type(value) is not bool:
            raise ValueError('Probe switches must be JSON booleans')
    if retain_rows and len(revisions) > 2 and not (palette_validation or ownership_validation or mask_validation):
        raise ValueError('Retained row matrices are limited to two profiles; use summaries for larger batches')
    engine = Path(engine).resolve()
    code = program(engine, blank_zero=blank_zero, dimensions=dimensions,
                   palette_validation=palette_validation, profile_argument=True, binary_pixels=True,
                   inset=inset, ownership_validation=ownership_validation,mask_validation=mask_validation)
    started = time.monotonic()
    contexts = {}
    with tempfile.TemporaryDirectory(prefix='font-profile-raster-') as temporary:
        work = Path(temporary)
        inputs = compile_probe(engine, port_include, work, code, cc, sanitizers, null_offset_control)
        hashes = source_hashes(engine, inputs)
        compile_seconds = time.monotonic() - started
        for revision in revisions:
            began = time.monotonic()
            error_path = work / ('errors-' + str(revision))
            with error_path.open('w') as errors:
                process = subprocess.Popen([str(work/'probe'), str(revision)], stdout=subprocess.PIPE,
                    stderr=errors, env=sanitizer_environment())
                try:
                    rows = read_rows(process.stdout, binary_pixels=True, profile=revision)
                    returncode = process.wait(timeout=20)
                    if returncode:
                        raise RuntimeError('Native profile exited ' + str(returncode))
                except (RuntimeError, ValueError) as error:
                    raise RuntimeError('Font profile ' + str(revision) + ' failed: ' + str(error) +
                                       '\n' + error_path.read_text()[-12000:]) from error
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                    process.stdout.close()
            changed = {}
            for key, row in rows.items():
                if key.startswith('RASTER '):
                    fields = key.split()
                    if row['sha256'] != hashlib.sha256(b'\x6d' * row['bytes']).hexdigest():
                        changed.setdefault(fields[4], set()).add(int(fields[2]))
            contexts[str(revision)] = dict(profile=revision, observations=len(rows),
                matrix_sha256=matrix_digest(rows),
                nonbackground_formats_by_image={key: sorted(values) for key, values in changed.items()},
                elapsed_seconds=time.monotonic()-began)
            if retain_rows:
                contexts[str(revision)]['rows'] = rows
            del rows
        if source_hashes(engine, inputs) != hashes:
            raise RuntimeError('Font sources changed during profile observations')
    return dict(program_sha256=hashlib.sha256(code.encode()).hexdigest(), source_sha256=hashes,
        profiles=contexts, compile_seconds=compile_seconds, elapsed_seconds=time.monotonic()-started,
        temporary_artifacts='Retired on return', sanitizers_enabled=sanitizers,
        null_offset_oracle_exception=null_offset_control, blank_zero_glyph=blank_zero,
        palette_validation=palette_validation, tile_dimensions=dimensions or [[1,1],[8,8],[17,11]],
        ownership_validation=ownership_validation,
        mask_validation=mask_validation,
        glyph_inset=inset,
        scope='Every declared profile executes in a fresh process with an observed native revision marker. '
              'Authored raster cases and byte digests only; no gameplay or state acceptance.')


def run(engine, port_include, *, cc=None, sanitizers=True, null_offset_control=False, blank_zero=False, dimensions=None, palette_validation=False, profile=None, inset=0):
    """Return byte-derived digests; discard temporary executables and raw pixels."""
    engine = Path(engine).resolve()
    for flag in (sanitizers, null_offset_control, blank_zero, palette_validation):
        if type(flag) is not bool:
            raise ValueError('Probe switches must be JSON booleans')
    code = program(engine, blank_zero=blank_zero, dimensions=dimensions, palette_validation=palette_validation, profile=profile, inset=inset)
    inputs = [engine/'source/gamelib'/name for name in UNITS]
    with tempfile.TemporaryDirectory(prefix='font-raster-') as temp:
        work = Path(temp)
        compile_probe(engine, port_include, work, code, cc, sanitizers, null_offset_control)
        rows = {}
        with (work/'errors').open('w') as errors:
            process = subprocess.Popen([str(work/'probe')], stdout=subprocess.PIPE, stderr=errors,
                                       text=True, env=sanitizer_environment())
            try:
                for line in process.stdout:
                    kind, _, value = line.rstrip().rpartition(' ')
                    if line.startswith('RASTER '):
                        raw = bytes.fromhex(value)
                        result = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                    elif line.startswith('WIDTHS '):
                        result = {'widths': [int(x) for x in value.rstrip(',').split(',')]}
                    else:
                        raise RuntimeError('Unexpected probe output: ' + line[:300])
                    if kind in rows:
                        raise RuntimeError('Duplicate raster case: ' + kind)
                    rows[kind] = result
                returncode = process.wait(timeout=20)
            except (ValueError, RuntimeError) as error:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                raise RuntimeError('Invalid raster output near ' + repr(line[:250]) +
                                   '\n' + (work/'errors').read_text()[-12000:]) from error
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                process.stdout.close()
            if returncode:
                raise RuntimeError('Font raster probe failed:\n' + (work/'errors').read_text()[-12000:])
            if not rows:
                raise RuntimeError('Font raster probe produced no observations')
        return {'program_sha256': hashlib.sha256(code.encode()).hexdigest(),
                'source_sha256': source_hashes(engine, inputs),
                'rows': rows, 'temporary_artifacts': 'Retired on return',
                'null_offset_oracle_exception': bool(null_offset_control),
                'sanitizers_enabled': sanitizers,
                'blank_zero_glyph': bool(blank_zero),
                'palette_validation': palette_validation,
                'profile': profile,
                'tile_dimensions': dimensions or [[1, 1], [8, 8], [17, 11]],
                'glyph_inset': inset,
                'scope': 'Authored images; actual font/bitmap/encoder/raster/queue C paths. Neutral transforms only; resource notifications are observed as no-ops, not state acceptance.'}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec', type=Path, help='JSON with engine, port_include, output, optional cc/sanitizers')
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    options = dict(cc=spec.get('cc'), sanitizers=spec.get('sanitizers', True),
                   null_offset_control=spec.get('null_offset_control', False),
                   blank_zero=spec.get('blank_zero', False), dimensions=spec.get('dimensions'),
                   palette_validation=spec.get('palette_validation', False), inset=spec.get('inset',0))
    if spec.get('ownership_validation', False):
        if 'profiles' not in spec:
            raise ValueError('Ownership validation requires an explicit profile batch')
        options['ownership_validation'] = spec['ownership_validation']
    if spec.get('mask_validation', False):
        if 'profiles' not in spec:
            raise ValueError('Mask validation requires an explicit profile batch')
        options['mask_validation'] = spec['mask_validation']
    if 'profiles' in spec:
        if 'profile' in spec:
            raise ValueError('Choose one fixed profile or a profile batch')
        result = run_profiles(spec['engine'], spec['port_include'], spec['profiles'],
                              retain_rows=spec.get('retain_rows', False), **options)
        count = sum(row['observations'] for row in result['profiles'].values())
    else:
        result = run(spec['engine'], spec['port_include'], profile=spec.get('profile'), **options)
        count = len(result['rows'])
    Path(spec['output']).write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print('Font raster observations:', count)


if __name__ == '__main__':
    main()
