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
from test_historical_player import function

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


def program(engine, *, blank_zero=False, dimensions=None, palette_validation=False):
    engine = Path(engine)
    source = (engine/'source/gamelib/font.c').read_text()
    main = (engine/'openbor.c').read_text()
    start = main.index('const s_drawmethod plainmethod =')
    plain = main[start:main.index('\n};', start)+3]
    methods = '\n'.join(function(source, name) for name in FONT_FUNCTIONS)
    if 'static int obor_font_palette_valid(' in source:
        methods = function(source, 'obor_font_palette_valid') + '\n' + methods
    screen = (engine/'source/gamelib/screen.c').read_text()
    allocation = '\n'.join(function(screen, name) for name in ('allocscreen', 'freescreen'))
    body = PALETTE_MAIN if palette_validation else MAIN
    if dimensions is not None:
        if not isinstance(dimensions, (list, tuple)) or not 1 <= len(dimensions) <= 3:
            raise ValueError('Use one to three authored tile dimensions')
        if any(not isinstance(pair, (list, tuple)) or len(pair) != 2 or
               any(type(value) is not int or not 1 <= value <= 32 for value in pair)
               for pair in dimensions):
            raise ValueError('Authored tile dimensions must be integer pairs within 1..32')
        pairs = '{' + ','.join('{' + str(w) + ',' + str(h) + '}' for w, h in dimensions) + '}'
        body = body.replace('{{1,1},{8,8},{17,11}}', pairs).replace('dim<3;', 'dim<' + str(len(dimensions)) + ';')
    return ('#define PROBE_BLANK_ZERO ' + str(int(blank_zero)) + '\n' +
            PREFIX.replace('PLAIN_METHOD', plain).replace('SCREEN_ALLOCATION', allocation).replace('FONT_METHODS', methods) + body)


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
int loadscreen(char *filename,char *pack,unsigned char *pal,int format,s_screen **out) {
    (void)pack;(void)pal;
    int page=0;
    char *slash=strrchr(filename,'/');
    if(slash) {page=(int)strtol(slash+1,NULL,16);if(page!=0 && page!=128 && page!=255)return 0;}
    int width=tile_width*16,height=tile_height*16;
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


def run(engine, port_include, *, cc=None, sanitizers=True, null_offset_control=False, blank_zero=False, dimensions=None, palette_validation=False):
    """Return byte-derived digests; discard temporary executables and raw pixels."""
    engine = Path(engine).resolve()
    for flag in (sanitizers, null_offset_control, blank_zero, palette_validation):
        if type(flag) is not bool:
            raise ValueError('Probe switches must be JSON booleans')
    code = program(engine, blank_zero=blank_zero, dimensions=dimensions, palette_validation=palette_validation)
    inputs = [engine/'source/gamelib'/name for name in UNITS]
    with tempfile.TemporaryDirectory(prefix='font-raster-') as temp:
        work = Path(temp)
        (work/'probe.c').write_text(code)
        compiler = cc or shlex.split(os.environ.get('HOST_CC', 'cc'))
        flags = ['-std=gnu99', '-O1', '-g', '-fcommon', '-fno-strict-aliasing',
                 '-ffunction-sections', '-fdata-sections', '-Wno-deprecated-declarations',
                 '-I', str(engine/'source'), '-I', str(engine/'source/gamelib'),
                 '-I', str(Path(port_include).resolve())]
        if sanitizers:
            flags += ['-fsanitize=address,undefined']
            if null_offset_control:
                # Unmodified upstream encoders form a member address from a
                # null destination in their sizing pass. Keep this explicitly
                # scoped oracle exception visible; it is not clean UBSan proof.
                flags += ['-fno-sanitize=null']
        link = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-Wl,--gc-sections']
        compile_result = subprocess.run([*compiler, *flags, str(work/'probe.c'),
                                        *map(str, inputs), *link, '-lm', '-o', str(work/'probe')],
                                       text=True, capture_output=True, timeout=60)
        if compile_result.returncode:
            raise RuntimeError('Font raster probe compilation failed:\n' + compile_result.stderr[-14000:])
        rows = {}
        with (work/'errors').open('w') as errors:
            process = subprocess.Popen([str(work/'probe')], stdout=subprocess.PIPE, stderr=errors,
                                       text=True, env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
                                                          UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1'))
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
            if returncode:
                raise RuntimeError('Font raster probe failed:\n' + (work/'errors').read_text()[-12000:])
            if not rows:
                raise RuntimeError('Font raster probe produced no observations')
        return {'program_sha256': hashlib.sha256(code.encode()).hexdigest(),
                'source_sha256': {str(p.relative_to(engine)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in [*inputs, engine/'source/gamelib/screen.c', engine/'source/gamelib/font.c',
                                            engine/'source/gamelib/font.h', engine/'openbor.c']},
                'rows': rows, 'temporary_artifacts': 'Retired on return',
                'null_offset_oracle_exception': bool(null_offset_control),
                'sanitizers_enabled': sanitizers,
                'blank_zero_glyph': bool(blank_zero),
                'palette_validation': palette_validation,
                'tile_dimensions': dimensions or [[1, 1], [8, 8], [17, 11]],
                'scope': 'Authored images; actual font/bitmap/encoder/raster/queue C paths. Neutral transforms only; resource notifications are observed as no-ops, not state acceptance.'}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec', type=Path, help='JSON with engine, port_include, output, optional cc/sanitizers')
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    result = run(spec['engine'], spec['port_include'], cc=spec.get('cc'),
                 sanitizers=spec.get('sanitizers', True),
                 null_offset_control=spec.get('null_offset_control', False),
                 blank_zero=spec.get('blank_zero', False), dimensions=spec.get('dimensions'),
                 palette_validation=spec.get('palette_validation', False))
    Path(spec['output']).write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print('Font raster observations:', len(result['rows']))


if __name__ == '__main__':
    main()
