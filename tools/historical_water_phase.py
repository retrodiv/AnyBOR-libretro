"""Check native water phase arithmetic independently of row-sampling changes.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from test_historical_player import function


def water_source(engine):
    """Read complete shared traversal, water bodies, sine table and native copies."""
    pieces = []
    for filename, names in (
            ('screen.c', ('copyscreen_water', 'copyscreen_trans_water', 'blendscreen_water')),
            ('screen16.c', ('putscreenx8p16_water',)),
            ('screen32.c', ('putscreenx8p32_water',))):
        source = (engine / 'source/gamelib' / filename).read_text()
        pieces.extend(function(source, name) for name in names)
    texture = (engine / 'source/gamelib/texture.c').read_text()
    table = re.search(r'(?m)^float _sinfactors\[256\]\s*=\s*\{[^}]+};', texture)
    if table is None:
        raise ValueError('Actual native water sine table required')
    pixel = (engine / 'source/gamelib/pixelformat.c').read_text()
    copy_macro = next(line for line in pixel.splitlines() if line.startswith('#define _pcpy '))
    copies = copy_macro + '\n' + function(pixel, 'u16pcpy') + '\n' + function(pixel, 'u32pcpy')
    return table.group() + '\n' + (engine / 'source/gamelib/obor_water.h').read_text() + '\n' + copies + '\n' + '\n'.join(pieces)


def render_water_phase(engine, fixture):
    rows = fixture['sources']
    if (not 1 <= len(rows) <= 128 or
            any(type(r['revision']) is not int or not 0 < r['revision'] <= 0xffffffff or
                type(r['period']) is not int or r['period'] not in (255, 256) for r in rows) or
            len({r['revision'] for r in rows}) != len(rows)):
        raise ValueError('Bounded unique contexts and explicit phase periods required')
    checks = '\n'.join('check(%d,%d);' % (r['revision'], r['period']) for r in rows)
    code = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "source/gamelib/types.h"
#undef assert
#define assert(c) do{if(!(c)){fprintf(stderr,"water phase revision=%u line=%d: %s\n",obor_profile_build,__LINE__,#c);abort();}}while(0)
uint32_t obor_profile_build;
int pixelbytes[5]={1,1,2,3,4};
@NATIVE@
#define distortion(x,a) ((int)(_sinfactors[x]*(a)+0.5))
enum {W=64,H=7};
static unsigned short remap16[256];static unsigned remap32[256];static unsigned char lut[65536];
static unsigned short blend16(unsigned short s,unsigned short d){(void)d;return s+7;}
static unsigned blend32(unsigned s,unsigned d){(void)d;return s+7;}
static unsigned char *pixels(s_screen *s){return (unsigned char*)s+offsetof(s_screen,data);}
static s_screen *screen(int format){
 s_screen *s=calloc(1,sizeof(*s)+W*H*4+32);assert(s);
 s->width=W;s->height=H;s->pixelformat=format;
 memset(pixels(s),3,W*H*pixelbytes[format]);return s;
}
static void expected(unsigned char *out,int format,int kind,int period,int time,int amplitude,float wavelength,int mode,int y,int source_height){
 int soy=y<0?-y:0,dy=y<0?0:y,ch=source_height-soy;
 if(y+source_height>H)ch-=y+source_height-H;
 float phase=(float)(time%period);int u=mode==1?distortion((int)phase,amplitude):amplitude;
 float step=period/wavelength;phase+=soy*step;
 for(int row=0;row<ch;++row){
  phase=phase-(int)phase+(int)phase%period;
  int shift=distortion((int)phase,amplitude)-u;
  for(int sx=0;sx<W;++sx){int dx=sx+shift;if(dx<0||dx>=W)continue;
   int at=(dy+row)*W+dx;
   if(kind<3){unsigned char value=kind==2?lut[(3<<8)|9]:3;
    memset(out+at*pixelbytes[format],value,pixelbytes[format]);}
   else if(format==PIXEL_16){unsigned short v=remap16[3];if(kind==4)v=blend16(v,0x0909);memcpy(out+at*2,&v,2);}
   else{unsigned v=remap32[3];if(kind==4)v=blend32(v,0x09090909);memcpy(out+at*4,&v,4);}
  }
  phase+=step;
 }
}
static void check(unsigned revision,int period){
 obor_profile_build=revision;
 for(int i=0;i<256;++i){remap16[i]=(unsigned short)(0x1111+i);remap32[i]=0x21212121u+i;}
 for(int i=0;i<65536;++i)lut[i]=(unsigned char)(((i>>8)+i)&255);
 const int times[]={0,127,254,255,256,509,65535};
 const float waves[]={2.5f,17.0f,255.0f,256.0f};
 for(int kind=0;kind<5;++kind)for(int f=0;f<3;++f){
  int format=f==0?PIXEL_8:f==1?PIXEL_16:PIXEL_32;
  if((kind==1||kind==2)&&format!=PIXEL_8)continue;
  if(kind>=3&&format==PIXEL_8)continue;
  s_screen *src=screen(kind>=3?PIXEL_x8:format),*dest=screen(format);
  size_t bytes=W*H*pixelbytes[format];unsigned char oracle[W*H*4];
  for(unsigned ti=0;ti<sizeof(times)/sizeof(*times);++ti)
  for(unsigned wi=0;wi<sizeof(waves)/sizeof(*waves);++wi)
  for(int mode=0;mode<2;++mode)for(int y=-1;y<=1;++y)for(int key=0;key<2;++key){
   /* One visible indexed row isolates phase from historical base-row sampling. */
   src->height=kind>=3?(y<0?2:1):H;
   memset(pixels(dest),9,bytes);memset(oracle,9,bytes);
   expected(oracle,format,kind,period,times[ti],5,waves[wi],mode,y,src->height);
   if(kind==0)copyscreen_water(dest,src,0,y,5,waves[wi],times[ti],mode);
   else if(kind==1)copyscreen_trans_water(dest,src,0,y,5,waves[wi],times[ti],mode);
   else if(kind==2)blendscreen_water(dest,src,0,y,5,waves[wi],times[ti],mode,lut);
   else if(format==PIXEL_16)putscreenx8p16_water(dest,src,0,y,key,remap16,kind==4?blend16:NULL,5,waves[wi],times[ti],mode);
   else putscreenx8p32_water(dest,src,0,y,key,remap32,kind==4?blend32:NULL,5,waves[wi],times[ti],mode);
   if(memcmp(pixels(dest),oracle,bytes)){fprintf(stderr,"kind=%d format=%d time=%d wave=%g mode=%d y=%d key=%d\n",kind,format,times[ti],(double)waves[wi],mode,y,key);abort();}
  }
  free(src);free(dest);
 }
}
int main(void){@CHECKS@ puts("water_phase=1");return 0;}
'''
    return code.replace('@NATIVE@', water_source(engine)).replace('@CHECKS@', checks)
