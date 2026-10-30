"""Compare native water rows with source-owned clipping and palette contracts.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from historical_water_phase import water_source


def render_water_rows(engine, fixture):
    rows = fixture['sources']
    if (not 1 <= len(rows) <= 128 or
            any(type(r['revision']) is not int or not 0 < r['revision'] <= 0xffffffff or
                type(r['period']) is not int or r['period'] not in (255, 256) or
                type(r['legacy_rows']) is not bool or
                type(r['copy_limit']) is not int or not 1 <= r['copy_limit'] <= 4096 for r in rows) or
            len({r['revision'] for r in rows}) != len(rows)):
        raise ValueError('Bounded unique contexts and explicit water row contracts required')
    checks = '\n'.join('check(%d,%d,%d,%d);' % (
        r['revision'], r['period'], r['legacy_rows'], r['copy_limit']) for r in rows)
    code = r'''
#include <assert.h>
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "source/gamelib/types.h"
#undef assert
#define assert(c) do{if(!(c)){fprintf(stderr,"water rows revision=%u line=%d: %s\n",obor_profile_build,__LINE__,#c);abort();}}while(0)
uint32_t obor_profile_build;
int pixelbytes[5]={1,1,2,3,4};
@NATIVE@
static unsigned short map16[256];static unsigned map32[256];static unsigned char lut[65536];
static uint64_t trace;static unsigned calls;
static unsigned short blend16(unsigned short s,unsigned short d){
 trace=trace*65599+((uint64_t)s<<32)+d;++calls;return (unsigned short)((s*3u)^d);
}
static unsigned blend32(unsigned s,unsigned d){trace=trace*65599+((uint64_t)s<<32)+d;++calls;return (s*3u)^d;}
static unsigned char *bytes(s_screen *s){return (unsigned char*)s+offsetof(s_screen,data);}
typedef struct scenario {int sw,sh,dw,dh,x,y,a,time;float wave;int mode,alias;} scenario;
static const scenario scenarios[]={
 {2,2,6,5,2,1,0,0,7,0,0},
 {8,3,8,5,0,1,0,0,7,0,0},
 {8,3,8,5,-2,1,0,0,7,0,0},
 {8,3,5,5,1,1,0,0,7,0,0},
 {10,2,6,5,-2,1,0,0,7,0,0},
 {5,2,10,5,5,1,0,0,7,0,0},
 {8,3,8,5,0,-1,2,255,4.5f,0,0},
 {8,3,8,5,1,4,2,128,5.0f,1,0},
 {8,3,8,5,0,1,-2,254,-3.0f,0,0},
 {8,3,8,5,0,1,2,128,INFINITY,0,0},
 {8,5,8,5,1,0,0,0,7,0,1},
 {8,5,8,5,-1,1,0,0,7,0,1},
 {960,1,960,3,0,1,0,0,7,0,0},
 {961,1,961,3,0,1,0,0,7,0,0},
 {10,1,6,1,-2,0,0,0,7,0,0}
};
static s_screen *screen(int width,int height,int format){
 s_screen *s=calloc(1,sizeof(*s)+(size_t)width*height*pixelbytes[format]+32);assert(s);
 s->width=width;s->height=height;s->pixelformat=format;return s;
}
static int wave_at(float phase,int a){return (int)(_sinfactors[(int)phase]*a+0.5);}
static void expected(unsigned char *out,s_screen *src,const scenario *c,int format,int kind,
                     int period,int legacy,int copy_limit,int key,int palette,int mismatch){
 if((kind==0 || (legacy && kind<3)) && mismatch)return;
 /* A missing explicit remap has defined fallback only in the old source.
    Later null-remap calls are candidate stability controls, not old oracles. */
 if(kind>=3 && palette && (!legacy || palette==2))return;
 if(c->x+c->a*2+c->sw<=0 || c->x-c->a*2>=c->dw)return;
 int sy=c->y<0?-c->y:0,dy=c->y<0?0:c->y,rows=c->sh-sy;
 if(c->y+c->sh>c->dh)rows-=c->y+c->sh-c->dh;
 float phase=(float)(c->time%period);int origin=c->mode==1?wave_at(phase,c->a):c->a;
 float step=period/c->wave;phase+=sy*step;
 for(int r=0;r<rows;++r){
  phase=phase-(int)phase+(int)phase%period;int shift=wave_at(phase,c->a)-origin;phase+=step;
  int first=c->x+shift,last=first+c->sw,source=0,count;
  if(legacy){
   if(last<0||first>c->dw)continue;
   if(first<0){source=-first;count=last;first=0;}
   else count=last>c->dw?c->dw-first:c->sw;
  }else{
   if(first>=c->sw||last<=0)continue;
   if(first<0){source=-first;first=0;}if(last>c->dw)last=c->dw;count=last-first;
  }
  if(count<=0)continue;
  int si=(sy+r)*c->sw+source,di=(dy+r)*c->dw+first;
  assert(si>=0&&si+count<=c->sw*c->sh&&di>=0);
  assert(di+count<=c->dw*c->dh || (c->sh==1&&c->dh==1&&c->sw>c->dw));
  unsigned char *input=c->alias?out:bytes(src);
  if(kind==0){memcpy(out+di*pixelbytes[format],input+si*pixelbytes[format],count*pixelbytes[format]);continue;}
  if(kind>=3&&legacy&&!key&&kind==3&&count>copy_limit)continue;
  for(int j=0;j<count;++j){int i=legacy?count-1-j:j;
   if(kind==1){if(input[si+i])out[di+i]=input[si+i];}
   else if(kind==2){if(input[si+i])out[di+i]=lut[(input[si+i]<<8)|out[di+i]];}
   else if(!key||input[si+i]){
    unsigned index=input[legacy?si+i:i];int dest_index=legacy?di+i:i;
    if(format==PIXEL_16){unsigned short v=map16[index],d;
     memcpy(&d,out+dest_index*2,2);if(kind==4)v=blend16(v,d);memcpy(out+(di+i)*2,&v,2);}
    else{unsigned v=map32[index],d;
     memcpy(&d,out+dest_index*4,4);if(kind==4)v=blend32(v,d);memcpy(out+(di+i)*4,&v,4);}
   }
  }
 }
}
static void invoke(s_screen *dest,s_screen *src,const scenario *c,int format,int kind,int key,int palette){
 if(kind==0)copyscreen_water(dest,src,c->x,c->y,c->a,c->wave,c->time,c->mode);
 else if(kind==1)copyscreen_trans_water(dest,src,c->x,c->y,c->a,c->wave,c->time,c->mode);
 else if(kind==2)blendscreen_water(dest,src,c->x,c->y,c->a,c->wave,c->time,c->mode,lut);
 else if(format==PIXEL_16)putscreenx8p16_water(dest,src,c->x,c->y,key,palette?NULL:map16,kind==4?blend16:NULL,c->a,c->wave,c->time,c->mode);
 else putscreenx8p32_water(dest,src,c->x,c->y,key,palette?NULL:map32,kind==4?blend32:NULL,c->a,c->wave,c->time,c->mode);
}
static void check(unsigned revision,int period,int legacy,int copy_limit){
 obor_profile_build=revision;
 for(int i=0;i<256;++i){map16[i]=(unsigned short)(0x1111+i*17);map32[i]=0x21212121u+i*11111u;}
 for(int i=0;i<65536;++i)lut[i]=(unsigned char)(((i>>8)*3+i)&255);
 for(unsigned ci=0;ci<sizeof(scenarios)/sizeof(*scenarios);++ci){const scenario *c=&scenarios[ci];
  for(int kind=0;kind<5;++kind)for(int format=0;format<5;++format){
   if(kind==0){}else if(kind<3){if(format!=PIXEL_8)continue;}else if(format!=PIXEL_16&&format!=PIXEL_32)continue;
   if(c->alias&&kind!=1&&kind!=2)continue;
   if(c->sh==1&&c->dh==1&&kind==0)continue;
   for(int mismatch=0;mismatch<2;++mismatch)for(int key=0;key<2;++key)for(int palette=0;palette<(kind>=3?3:1);++palette){
    if(mismatch&&(kind>=3||c->alias))continue;
    if(c->sh==1&&c->dh==1&&kind>=3&&!key)continue;
    int src_format=kind>=3?PIXEL_x8:mismatch?(format+1)%5:format;
    s_screen *dest=screen(c->dw,c->dh,format),*src=c->alias?dest:screen(c->sw,c->sh,src_format);
    size_t size=(size_t)c->dw*c->dh*pixelbytes[format],ssize=(size_t)c->sw*c->sh*pixelbytes[src_format];
    for(size_t i=0;i<size;++i)bytes(dest)[i]=(unsigned char)((i*7+11)%251);
    if(!c->alias)for(size_t i=0;i<ssize;++i)bytes(src)[i]=(unsigned char)((i*13+(i/c->sw)*29)%19);
    if(c->sh==1&&c->dh==1){bytes(src)[8]=bytes(src)[9]=0;}
    if(kind>=3)src->palette=palette==2?NULL:(unsigned char*)(format==PIXEL_16?(void*)map16:(void*)map32);
    unsigned char *oracle=malloc(size);assert(oracle);memcpy(oracle,bytes(dest),size);
    trace=0;calls=0;expected(oracle,src,c,format,kind,period,legacy,copy_limit,key,palette,mismatch);
    uint64_t expected_trace=trace;unsigned expected_calls=calls;trace=0;calls=0;
    invoke(dest,src,c,format,kind,key,palette);
    if(memcmp(bytes(dest),oracle,size)||trace!=expected_trace||calls!=expected_calls){
     fprintf(stderr,"water rows revision=%u case=%u kind=%d format=%d key=%d palette=%d mismatch=%d\n",revision,ci,kind,format,key,palette,mismatch);abort();}
    free(oracle);if(!c->alias)free(src);free(dest);
   }
  }
 }
 /* Candidate-only bounded outcomes, with no claim about undefined originals. */
 scenario c={8,2,8,3,0,0,2,0,7,0,0};s_screen *src=screen(8,2,PIXEL_8),*dest=screen(8,3,PIXEL_8);
 for(int which=0;which<7;++which){scenario bad=c;src->height=2;memset(bytes(dest),9,24);
  if(which==0)src->height=0;else if(which==1)bad.y=INT_MIN;else if(which==2)bad.y=INT_MAX;
  else if(which==3)bad.wave=0;else if(which==4)bad.wave=NAN;else if(which==5){bad.time=-1;bad.mode=1;}else bad.wave=1.0e-38f;
  copyscreen_water(dest,src,bad.x,bad.y,bad.a,bad.wave,bad.time,bad.mode);
  for(int i=0;i<24;++i)assert(bytes(dest)[i]==9);
 }
 copyscreen_water(dest,NULL,0,0,0,7,0,0);copyscreen_water(NULL,src,0,0,0,7,0,0);
 free(src);free(dest);
}
int main(void){@CHECKS@ puts("water_rows=1");return 0;}
'''
    return code.replace('@NATIVE@', water_source(engine)).replace('@CHECKS@', checks)
