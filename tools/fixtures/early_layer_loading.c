/* Source-owned layer loader dispatch and repeat-origin controls.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */
#include <assert.h>
#include <limits.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Layer load mismatch: revision=%u line=%d\n",obor_profile_build,__LINE__);abort();}}while(0)
uint32_t obor_profile_build;
static s_level storage,*level=&storage;
char packfile[OBOR_CONTENT_PATH_MAX]="fixture.pak";
int pixelformat=PIXEL_8;
static int screens,sprites,fail_load,stops,null_names;
static jmp_buf stop;
static s_screen image;
static s_sprite picture;
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
void shutdown(int status,char *message,...) {
 assert(status==1 && message);++stops;longjmp(stop,1);
}
s_sprite *loadsprite2(char *name,int *width,int *height) {
 ++sprites;null_names+=name==NULL;
 if(fail_load)return NULL;
 *width=7;*height=11;return &picture;
}
int loadscreen(char *name,char *pack,unsigned char *palette,int format,s_screen **out) {
 assert(pack==packfile && palette==NULL && format==PIXEL_8);++screens;null_names+=name==NULL;
 if(fail_load)return 0;
 *out=&image;return 1;
}
@FUNCTIONS@
static void reset(void) {
 memset(&storage,0,sizeof(storage));level=&storage;
 memset(&image,0,sizeof(image));image.width=7;image.height=11;
 screens=sprites=fail_load=stops=null_names=0;
}
static void check(int water_screen,int reuse,int repeat,int nested) {
 void (*calls[])(char*,int)={load_bglayer,load_fglayer};
 const int alphas[]={-1,0,1,7};
 for(int fg=0;fg<2;++fg)for(unsigned a=0;a<sizeof(alphas)/sizeof(*alphas);++a)
 for(int transparent=0;transparent<2;++transparent)for(int water=0;water<2;++water)
 for(int no_name=0;no_name<2;++no_name)for(int failed=0;failed<2;++failed)
 for(int xrepeat=0;xrepeat<2;++xrepeat)for(int zrepeat=0;zrepeat<2;++zrepeat) {
  reset();fail_load=failed;
  s_bglayer *bg=level->bglayers;s_fglayer *front=level->fglayers;
  /* Opposite-era fields deliberately disagree so the profile route matters. */
  bg->alpha=front->alpha=nested?0:alphas[a];
  bg->transparency=front->transparency=nested?0:transparent;
  bg->watermode=front->watermode=nested?!water:water;
  bg->drawmethod.alpha=front->drawmethod.alpha=nested?alphas[a]:0;
  bg->drawmethod.transbg=front->drawmethod.transbg=nested?transparent:0;
  bg->drawmethod.water.watermode=front->drawmethod.water.watermode=nested?water:!water;
  bg->width=front->width=3;bg->height=front->height=5;
  bg->xoffset=front->xoffset=13;bg->zoffset=front->zoffset=17;
  bg->xrepeat=front->xrepeat=xrepeat?-1:2;bg->zrepeat=front->zrepeat=zrepeat?-1:4;
  int skips= !fg && no_name && reuse;
  if(skips){bg->screen=&image;bg->type=bg_screen;}
  int want_sprite=(alphas[a]>0 || transparent) && (!water || (fg && !water_screen));
  int expected_failure=failed && !skips;
  if(!setjmp(stop)){calls[fg](no_name?NULL:"fixture.png",0);assert(!expected_failure);}
  else assert(expected_failure);
  assert(stops==expected_failure);
  assert(screens==(!skips && !want_sprite));assert(sprites==(!skips && want_sprite));
  assert(null_names==(no_name && !skips));
  if(!expected_failure) {
   int width=skips?3:7,height=skips?5:11;
   int got_width=fg?front->width:bg->width,got_height=fg?front->height:bg->height;
   assert(got_width==width && got_height==height);
   assert((fg?(void*)front->handle:bg->handle)==(skips || !want_sprite?(void*)&image:(void*)&picture));
   assert((fg?front->type:bg->type)==(want_sprite && !skips?bg_sprite:bg_screen));
   assert((fg?front->xrepeat:bg->xrepeat)==(repeat && xrepeat?40000:xrepeat?-1:2));
   assert((fg?front->zrepeat:bg->zrepeat)==(repeat && zrepeat?40000:zrepeat?-1:4));
   assert((fg?front->xoffset:bg->xoffset)==(repeat && xrepeat?-width*20000:13));
   assert((fg?front->zoffset:bg->zoffset)==(repeat && zrepeat?-height*20000:17));
  }
 }
 reset();level=NULL;load_bglayer("fixture.png",0);load_fglayer("fixture.png",0);assert(!screens && !sprites && !stops);
 reset();load_bglayer("fixture.png",-1);load_bglayer("fixture.png",LEVEL_MAX_BGLAYERS);
 load_fglayer("fixture.png",-1);load_fglayer("fixture.png",LEVEL_MAX_FGLAYERS);assert(!screens && !sprites && !stops);
 if(reuse) {
  reset();level->bglayers[0].screen=&image;level->bglayers[0].width=INT_MAX;level->bglayers[0].xrepeat=-1;
  if(!setjmp(stop)){load_bglayer(NULL,0);assert(0);}else assert(stops==1);
 }
}
int main(void) {@CHECKS@ return 0;}
