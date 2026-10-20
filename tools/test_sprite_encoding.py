"""Check sprite sizing and encoded bytes with actual C and an independent decoder.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
ENGINE = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT/'src/engines/3842'))


def encoding_program(source):
    methods = '\n'.join(function(source, name) for name in ('encodesprite', 'fakey_encodesprite'))
    return r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "types.h"
#include "sprite.h"
int screenformat;
int pixelbytes[5]={1,1,2,3,4};
static size_t recorded_body;
void obor_resources_forget_owner(const void *owner) { (void)owner; }
void obor_resources_sprite_encoded(const void *bitmap,void *owner,void *body,size_t length,unsigned x,unsigned y,unsigned width,unsigned height) {
    (void)bitmap;(void)owner;(void)body;(void)x;(void)y;(void)width;(void)height;
    recorded_body=length;
}
METHODS
int main(void) {
    const int widths[]={0,1,2,7,255,256,257,510};
    const int heights[]={0,1,7,16};
    const int formats[]={PIXEL_8,PIXEL_16,PIXEL_32};
    for(unsigned f=0;f<3;++f)for(unsigned w=0;w<8;++w)for(unsigned h=0;h<4;++h)
    for(int pattern=0;pattern<5;++pattern)for(int palette=0;palette<2;++palette) {
        screenformat=formats[f];int width=widths[w],height=heights[h];
        size_t pixels=(size_t)width*height, backing=sizeof(s_bitmap)+pixels+PAL_BYTES+16;
        s_bitmap *bitmap=calloc(1,backing);assert(bitmap);
        bitmap->width=width;bitmap->height=height;
        bitmap->pixelformat=screenformat==PIXEL_8?PIXEL_8:PIXEL_x8;
        if(palette)bitmap->palette=bitmap->data+pixels;
        for(size_t i=0;i<pixels;++i) {
            switch(pattern) {
                case 0:bitmap->data[i]=0;break;
                case 1:bitmap->data[i]=1+(i%255);break;
                case 2:bitmap->data[i]=i%2?77:0;break;
                case 3:bitmap->data[i]=(i%width)<254?0:99;break;
                case 4:bitmap->data[i]=(i%width)<255?19:0;break;
            }
        }
        if(palette)for(int i=0;i<PAL_BYTES;++i)bitmap->palette[i]=(unsigned char)(i*17+3);
        unsigned char *snapshot=malloc(backing);assert(snapshot);memcpy(snapshot,bitmap,backing);
        recorded_body=0;
        unsigned size=fakey_encodesprite(bitmap);
        assert(memcmp(snapshot,bitmap,backing)==0);
        assert(size>=offsetof(s_sprite,data));
        unsigned char *allocation=malloc((size_t)size+32);assert(allocation);
        memset(allocation,0xa5,(size_t)size+32);
        s_sprite *sprite=(s_sprite*)allocation;
        assert(encodesprite(3,-2,bitmap,sprite)==size);
        for(unsigned i=0;i<32;++i)assert(allocation[size+i]==0xa5);
        if(width && height) {
            assert(sprite->width==width && sprite->height==height);
            assert(sprite->centerx==3 && sprite->centery==-2);
            unsigned char *decoded=calloc(1,pixels);assert(decoded);
            const unsigned char *last=(const unsigned char*)sprite->data+height*sizeof(int);
            for(int y=0;y<height;++y) {
                const unsigned char *cursor=(const unsigned char*)(sprite->data+y)+sprite->data[y];
                int x=0;
                for(;;) {
                    assert(cursor>=allocation && cursor<allocation+size);
                    unsigned skip=*cursor++;if(skip==255)break;
                    x+=(int)skip;assert(x<=width && cursor<allocation+size);
                    unsigned run=*cursor++;assert(run<=(unsigned)(width-x));
                    assert(cursor+run<=allocation+size);
                    memcpy(decoded+(size_t)y*width+x,cursor,run);cursor+=run;x+=(int)run;
                }
                if(cursor>last)last=cursor;
            }
            assert(memcmp(decoded,bitmap->data,pixels)==0);free(decoded);
            size_t bytes=(size_t)(last-allocation);
            unsigned padding=palette?(unsigned)((4-bytes%4)%4):0;
            assert(size==bytes+padding+(palette?PAL_BYTES:0)+ANYNUMBER);
            if(palette) {
                assert(sprite->palette==allocation+bytes+padding);
                assert(memcmp(sprite->palette,bitmap->palette,PAL_BYTES)==0);
            } else assert(sprite->palette==NULL);
            printf("ENCODING %d %d %d %d %d %u ",screenformat,width,height,pattern,palette,size);
            for(const unsigned char *p=(const unsigned char*)sprite->data;p<last;++p)printf("%02x",*p);
            putchar('\n');
        } else assert(sprite->width==0 && sprite->height==0 && sprite->palette==NULL);
        assert(memcmp(snapshot,bitmap,backing)==0);
        free(allocation);free(snapshot);free(bitmap);
    }
    return 0;
}
'''.replace('METHODS', methods)


class SpriteEncodingTests(unittest.TestCase):
    def test_actual_size_pass_and_encoded_pixel_roundtrip(self):
        source = encoding_program((ENGINE/'source/gamelib/sprite.c').read_text())
        self.compile_run(source)

    def test_actual_empty_clips_and_endpoint_extremes(self):
        pixel = (ENGINE/'source/gamelib/pixelformat.c').read_text()
        sprite = (ENGINE/'source/gamelib/sprite.c').read_text()
        methods = '\n'.join((function(pixel, 'obor_clip_endpoint'),
                             function(pixel, 'drawmethod_global_init'), function(sprite, 'putsprite')))
        self.compile_run(r'''
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include "types.h"
int screenformat;
unsigned channelr,channelg,channelb,tintmode,tintcolor;
int usechannel,useclip,clipx1,clipx2,clipy1,clipy2;
static int calls;
static void _putsprite(int x,int y,s_sprite *sprite,s_screen *screen,s_drawmethod *method) {
    (void)x;(void)y;(void)sprite;(void)screen;(void)method;++calls;
}
METHODS
static int bounded(int64_t v) {return v<INT_MIN?INT_MIN:v>INT_MAX?INT_MAX:(int)v;}
int main(void) {
    const int origins[]={INT_MIN,-100,-1,0,7,23,24,100,INT_MAX};
    const int extents[]={-1,0,1,2,17,INT_MAX};
    const int formats[]={PIXEL_8,PIXEL_16,PIXEL_32};
    s_screen screen={0};screen.width=24;screen.height=20;s_sprite sprite={0};
    for(unsigned f=0;f<3;++f)for(unsigned xi=0;xi<9;++xi)for(unsigned yi=0;yi<9;++yi)
    for(unsigned wi=0;wi<6;++wi)for(unsigned hi=0;hi<6;++hi) {
        screenformat=formats[f];
        s_drawmethod dm={0};dm.flag=1;dm.xrepeat=2;dm.yrepeat=3;
        dm.channelr=17;dm.channelg=19;dm.channelb=23;
        dm.clipx=origins[xi];dm.clipy=origins[yi];dm.clipw=extents[wi];dm.cliph=extents[hi];
        int enabled=dm.clipw>0 && dm.cliph>0;
        int64_t left=dm.clipx>0?dm.clipx:0,top=dm.clipy>0?dm.clipy:0;
        int64_t right=(int64_t)dm.clipx+dm.clipw,bottom=(int64_t)dm.clipy+dm.cliph;
        if(right>screen.width)right=screen.width;
        if(bottom>screen.height)bottom=screen.height;
        int visible=!enabled || (right>left && bottom>top);
        calls=0;putsprite(3,4,&sprite,&screen,&dm);
        assert(calls==(visible?6:0) && useclip==enabled);
        if(enabled) {
            assert(clipx1==dm.clipx && clipy1==dm.clipy);
            assert(clipx2==bounded((int64_t)dm.clipx+dm.clipw));
            assert(clipy2==bounded((int64_t)dm.clipy+dm.cliph));
        }
        if(screenformat!=PIXEL_8)assert(channelr==17 && channelg==19 && channelb==23 && usechannel);
    }
    return 0;
}
'''.replace('METHODS', methods))

    def compile_run(self, source):
        with tempfile.TemporaryDirectory(prefix='sprite-encoding-') as temp:
            work = Path(temp)
            (work/'probe.c').write_text(source)
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-g', '-fsanitize=address,undefined', '-I', str(ENGINE/'source/gamelib'),
                str(work/'probe.c'), '-o', str(work/'probe')], check=True, timeout=45)
            subprocess.run([str(work/'probe')], check=True, timeout=20,
                           stdout=subprocess.DEVNULL,
                           env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
                                    UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1'))


if __name__ == '__main__':
    unittest.main()
