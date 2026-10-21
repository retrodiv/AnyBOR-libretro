"""Check clipped optional masks against an independent pixel placement model.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from native_sanitizers import sanitizer_environment
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))

PROGRAM = r'''
#include <assert.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include "types.h"
#include "sprite.h"
static unsigned short mix16(unsigned short s,unsigned short d) {return s^d;}
static unsigned mix32(unsigned s,unsigned d) {return s^d;}
static s_sprite *image(int mask) {
    s_sprite *s=calloc(1,sizeof(*s)+128); assert(s);
    s->width=4;s->height=3;
    unsigned char *p=(unsigned char*)(s->data+3);
    for(int y=0;y<3;++y) {
        s->data[y]=(int)(p-(unsigned char*)(s->data+y));
        *p++=0;*p++=4;
        for(int x=0;x<4;++x)*p++=mask?50+y*10+x:1+y*4+x;
        *p++=255;
    }
    return s;
}
int main(void) {
    s_sprite *s=image(0),*mask=image(1);
    s_screen *screen=calloc(1,sizeof(*screen)+8*6*4);assert(screen);
    screen->width=8;screen->height=6;
    unsigned short p16[256],r16[256];unsigned p32[256],r32[256];
    for(int i=0;i<256;++i) {
        p16[i]=i*103;r16[i]=i*71;p32[i]=i*1234567u;r32[i]=i*76543u;
    }
    for(int bits=16;bits<=32;bits+=16)
    for(int masked=0;masked<2;++masked)for(int flip=0;flip<2;++flip)
    for(int blend=0;blend<2;++blend)for(int remap=0;remap<2;++remap)
    for(int clip=0;clip<2;++clip)for(int y=-3;y<=7;++y)
    for(int x=-2;x<=10;x+=2) {
        useclip=clip;clipx1=1;clipx2=7;clipy1=1;clipy2=5;
        s->mask=masked?mask:NULL;
        s->palette=(unsigned char*)(bits==16?(void*)p16:(void*)p32);
        memset(screen->data,0x6d,8*6*4);
        if(bits==16)putsprite_x8p16(x,y,flip,s,screen,remap?r16:NULL,blend?mix16:NULL);
        else putsprite_x8p32(x,y,flip,s,screen,remap?r32:NULL,blend?mix32:NULL);
        for(int dy=0;dy<6;++dy)for(int dx=0;dx<8;++dx) {
            unsigned expected=bits==16?0x6d6du:0x6d6d6d6du;
            int sx=flip?x-1-dx:dx-x,sy=dy-y;
            if(sx>=0&&sx<4&&sy>=0&&sy<3&&(!clip||(dx>=1&&dx<7&&dy>=1&&dy<5))) {
                int index=1+sy*4+sx;
                unsigned value=bits==16?(remap?r16[index]:p16[index]):(remap?r32[index]:p32[index]);
                if(masked)expected=bits==16?blend_channel16(value,expected,50+sy*10+sx):blend_channel32(value,expected,50+sy*10+sx);
                else expected=blend?(value^expected):value;
            }
            unsigned actual=bits==16?((unsigned short*)screen->data)[dy*8+dx]:((unsigned*)screen->data)[dy*8+dx];
            assert(actual==expected);
        }
    }
    free(screen);free(mask);free(s);return 0;
}
'''


class SpriteMaskTests(unittest.TestCase):
    def test_transform_traversal_with_and_without_masks(self):
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        for engine in ('7142', '7533', '8023'):
            with self.subTest(engine=engine), tempfile.TemporaryDirectory(prefix='transform-mask-') as temp:
                work = Path(temp)
                source = ROOT/'src/engines'/engine/'source'
                actual = (source/'gamelib/transform.c').read_text()
                methods = '\n'.join(function(actual, name) for name in ('_sprite_seek', 'src_inc', 'src_dec'))
                code = r'''
#include <assert.h>
#include <stddef.h>
#include "types.h"
static gfx_entry *handle_src;
static unsigned char *ptr_src,*ptr_src_mask,*cur_src,*cur_src_mask,*cur_spr;
static unsigned char dummyptrs[8];
static int x_src,y_src,spb,span_src;
METHODS
int main(void) {
    int row[8]={0};
    unsigned char *pixels=(unsigned char*)(row+1);
    row[0]=sizeof(int);pixels[0]=0;pixels[1]=4;
    for(int i=0;i<4;++i)pixels[2+i]=20+i;
    pixels[6]=255;
    s_screen screen={0};screen.magic=sprite_magic;
    gfx_entry entry;entry.screen=&screen;handle_src=&entry;
    ptr_src=(unsigned char*)row;
    for(int masked=0;masked<2;++masked) {
        ptr_src_mask=masked?(unsigned char*)row:NULL;
        x_src=1;y_src=0;_sprite_seek(x_src,y_src);
        assert(cur_src==pixels+3);
        /* The mask cursor's historical positioning is retained. This test
           checks optional-pointer safety without redefining masked pixels. */
        unsigned char *expected=masked?pixels+1:NULL;
        assert(cur_src_mask==expected);
        src_inc();assert(cur_src==pixels+4);
        if(masked)++expected;
        assert(cur_src_mask==expected);
        src_dec();assert(cur_src==pixels+3);
        if(masked)--expected;
        assert(cur_src_mask==expected);
        _sprite_seek(4,0);assert(cur_src==dummyptrs&&cur_src_mask==dummyptrs);
    }
    return 0;
}
'''.replace('METHODS', methods)
                (work/'probe.c').write_text(code)
                built = subprocess.run([*compiler, '-std=gnu99', '-O1', '-g',
                    '-fsanitize=address,undefined,pointer-overflow', '-I', str(source),
                    '-I', str(source/'gamelib'), str(work/'probe.c'), '-o', str(work/'probe')],
                    text=True, capture_output=True, timeout=45)
                self.assertEqual(built.returncode, 0, built.stderr[-12000:])
                result = subprocess.run([str(work/'probe')], env=sanitizer_environment(),
                    capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr[-12000:])

    def test_top_clipping_with_and_without_masks(self):
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        for engine in ('3842', '4086', '4432', '6391', '7142', '7533', '8023'):
            with self.subTest(engine=engine), tempfile.TemporaryDirectory(prefix='sprite-mask-') as temp:
                work = Path(temp)
                (work/'probe.c').write_text(PROGRAM)
                source = ROOT/'src/engines'/engine/'source'
                flags = ['-std=gnu99', '-O1', '-g', '-fcommon', '-fno-strict-aliasing',
                         '-fsanitize=address,undefined,pointer-overflow',
                         '-ffunction-sections', '-fdata-sections',
                         '-I', str(source), '-I', str(source/'gamelib'),
                         '-I', str(ROOT/'src/port/libretro')]
                link = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-Wl,--gc-sections']
                command = [*compiler, *flags, str(work/'probe.c'),
                           *[str(source/'gamelib'/name) for name in
                             ('spritex8p16.c', 'spritex8p32.c', 'pixelformat.c')],
                           *link, '-lm', '-o', str(work/'probe')]
                built = subprocess.run(command, text=True, capture_output=True, timeout=45)
                self.assertEqual(built.returncode, 0, built.stderr[-12000:])
                result = subprocess.run([str(work/'probe')], env=sanitizer_environment(),
                                        text=True, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr[-12000:])


if __name__ == '__main__':
    unittest.main()
