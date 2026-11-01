/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Actual load-width statement and shadow predicate, with controlled queries.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#define CHECK(c) do{if(!(c)){fprintf(stderr,"Viewport/shadow revision=%u line=%d\n",obor_profile_build,__LINE__);abort();}}while(0)
static uint32_t obor_profile_build;
static struct {int width;} storage,*level=&storage;
static struct {int hRes;} videomodes;
static struct {float x,z;} actor,*e=&actor;
static int hole,queries;
static int checkhole(float x,float z){CHECK(x==12.5f && z==21.25f);++queries;return hole;}
static void loaded_width(void){@WIDTH@}
static int shadow_visible(float temp1,float temp2,int wall2,void *other){return @SHADOW@;}
static void check(int revision,int minimum,int platform){
 obor_profile_build=revision;
 const int widths[]={0,1,319,320,321,640,1920};
 const int displays[]={1,320,640,1920};
 for(unsigned v=0;v<sizeof(displays)/sizeof(*displays);v++)
 for(unsigned w=0;w<sizeof(widths)/sizeof(*widths);w++){
  storage.width=widths[w];videomodes.hRes=displays[v];loaded_width();
  CHECK(storage.width==(minimum && widths[w]<displays[v]?displays[v]:widths[w]));
 }
 actor.x=10.0f;actor.z=20.0f;
 for(int h=0;h<=2;h++)for(int wall=-1;wall<=1;wall++)for(int has_platform=0;has_platform<2;has_platform++){
  hole=h;queries=0;int visible=shadow_visible(2.5f,1.25f,wall,has_platform?&actor:NULL);
  CHECK(visible==!(h && wall<0 && (!platform || !has_platform)) && queries==1);
 }
}
int main(void){@CHECKS@ return 0;}
