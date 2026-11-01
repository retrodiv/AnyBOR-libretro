/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Independent finite grid oracle for palette, key and blend ordering.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "globals.h"
#include "source/gamelib/types.h"
#define CHECK(v) do{if(!(v)){fprintf(stderr,"water entry revision=%u line=%d: %s\n",obor_profile_build,__LINE__,#v);abort();}}while(0)
uint32_t obor_profile_build;
int pixelbytes[5]={1,1,2,3,4};
unsigned char *blendtables[MAX_BLENDINGS];
blend16fp blendfunctions16[MAX_BLENDINGS];
blend32fp blendfunctions32[MAX_BLENDINGS];
@NATIVE@
static unsigned char remap[256],blend[65536];
static s_screen *screen(int w,int h){
 s_screen *s=calloc(1,sizeof(*s)+(size_t)w*h);CHECK(s);
 s->width=w;s->height=h;s->pixelformat=PIXEL_8;return s;
}
static void oracle(unsigned char *out,s_screen *source,int x,int y,
                   int advanced,int key,int map,int alpha,int unified){
 if(!advanced){key=map=alpha=0;}
 else if(!unified){map=0;if(alpha)key=1;}
 for(int sy=0;sy<source->height;sy++)for(int sx=0;sx<source->width;sx++){
  int dx=x+sx,dy=y+sy;if(dx<0||dx>=8||dy<0||dy>=5)continue;
  unsigned char colour=source->data[sx+sy*source->width];
  if(key&&!colour)continue;
  if(map)colour=remap[colour];
  out[dx+8*dy]=alpha?blend[(colour<<8)|out[dx+8*dy]]:colour;
 }
}
static void check(unsigned revision,int unified){
 obor_profile_build=revision;
 for(int i=0;i<256;i++)remap[i]=(unsigned char)(5*i+3);
 for(int i=0;i<65536;i++)blend[i]=(unsigned char)(3*(i>>8)+7*(i&255)+11);
 blendtables[0]=blend;
 s_screen *source=screen(4,3),*actual=screen(8,5);unsigned char expected[40];
 for(int i=0;i<12;i++)source->data[i]=(unsigned char)(i%5);
 for(int flag=-1;flag<2;flag++)for(int key=0;key<2;key++)
 for(int map=0;map<2;map++)for(int alpha=0;alpha<2;alpha++)
 for(int x=-1;x<=1;x+=2)for(int y=-1;y<=4;y+=(y<0?2:3)){
  s_drawmethod method={0},saved;method.flag=flag>0;method.table=map?remap:NULL;
  method.alpha=alpha;method.transbg=key;memcpy(&saved,&method,sizeof(method));
  for(int i=0;i<40;i++)actual->data[i]=expected[i]=(unsigned char)(i*3+9);
  oracle(expected,source,x,y,flag>0,key,map,alpha,unified);
  putscreen_water(actual,source,x,y,0,7,0,0,flag<0?NULL:&method);
  CHECK(!memcmp(actual->data,expected,40));CHECK(!memcmp(&method,&saved,sizeof(method)));
  if(unified){
   for(int i=0;i<40;i++)actual->data[i]=expected[i]=(unsigned char)(i*3+9);
   oracle(expected,source,x,y,1,key,map,alpha,1);
   putscreen8_water(actual,source,x,y,key,map?remap:NULL,alpha?blend:NULL,0,7,0,0);
   CHECK(!memcmp(actual->data,expected,40));
  }
 }
 free(source);free(actual);
}
int main(void){@CHECKS@ puts("water_entry=1");return 0;}
