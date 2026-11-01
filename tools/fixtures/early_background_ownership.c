/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Actual background resource callers with bounded allocation providers.
 * Profile oracles come from the allocation/reset/release statements in each
 * original. Counts and ownership are checked independently of the callers.
 */
#include <assert.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#include "models.h"
#undef printf
#undef assert
#define assert(c) do{if(!(c)){fprintf(stderr,"Background ownership revision=%u line=%d\n",obor_profile_build,__LINE__);abort();}}while(0)
#undef time
#define time resource_time
uint32_t obor_profile_build;
static s_level room,*level=&room;
static s_screen *bgbuffer;
static s_bitmap *texture;
static char bgbuffer_updated;
char packfile[OBOR_CONTENT_PATH_MAX]="fixture.pak";
int pixelformat,screenformat;
static s_videomodes videomodes;
static float advancex,advancey,scrollminz,scrollmaxz,blockade;
static int nojoin,current_spawn,groupmin,groupmax,level_completed,tospeedup;
static int reached[4],showtimeover,pause,endgame,cameratype,light[2],gfx_y_offset;
static u32 go_time,neon_time,time;
unsigned int models_loaded;
static void *owned[4];
static int active,alloc_ok,image_ok,allocs,loads,frees,screen_releases,background_releases,panel_releases;
static int events[16],used;
static jmp_buf stop;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
static void event(int kind){assert(used<16);events[used++]=kind;}
static void *allocate(size_t bytes){
 void *p=calloc(1,bytes);assert(p);int i;for(i=0;i<4 && owned[i];++i){}assert(i<4);owned[i]=p;++active;return p;
}
static void owned_free(void *p){
 if(!p)return;
 int found=0;for(int i=0;i<4;i++)if(owned[i]==p){owned[i]=NULL;found=1;break;}
 assert(found && active>0);--active;++frees;free(p);
}
s_screen *allocscreen(int width,int height,int format){
 assert(width==8 && height==6 && format==screenformat);++allocs;
 return alloc_ok?allocate(sizeof(s_screen)+8*6*4):NULL;
}
s_bitmap *loadbitmap(char *name,char *pack,int format){
 assert(!strcmp(name,"fixture.img") && pack==packfile && format==pixelformat);++loads;
 return image_ok?allocate(sizeof(s_bitmap)+32):NULL;
}
void freebitmap(s_bitmap *p){assert(p==texture);event(2);owned_free(p);}
void shutdown(int status,char *message,...){
 char diagnostic[128];va_list args;va_start(args,message);vsnprintf(diagnostic,sizeof(diagnostic),message,args);va_end(args);
 assert(status==1 && !strcmp(diagnostic,"Error loading file 'fixture.img'"));assert(!texture);longjmp(stop,1);
}
void unload_background(void){++background_releases;event(1);}
void freepanels(void){++panel_releases;event(3);}
void free_level(s_level *p){assert(p==level && !p->name);event(5);}
void free_model(s_model *p){(void)p;abort();}
s_model *getFirstModel(void){return NULL;}
s_model *getCurrentModel(void){return NULL;}
s_model *getNextModel(void){return NULL;}
s_model *getModelAt(int index){(void)index;abort();}
void getRamStatus(int bytes){(void)bytes;}
#define free owned_free
#define freescreen actual_freescreen
@FREE_SCREEN@
#undef freescreen
#undef free
void freescreen(s_screen **slot){assert(slot==&bgbuffer);++screen_releases;event(4);actual_freescreen(slot);}
@TEXTURE_FUNCTIONS@
#define free owned_free
@FUNCTIONS@
#undef free
static void reset(void){
 assert(!active);memset(&room,0,sizeof(room));level=&room;bgbuffer=NULL;texture=NULL;
 bgbuffer_updated=7;videomodes.hRes=8;videomodes.vRes=6;
 allocs=loads=frees=screen_releases=background_releases=panel_releases=used=0;
 alloc_ok=image_ok=1;
}
static void check(int revision,int allocate_buffer,int reset_cache,int release_buffer,int has_texture){
 obor_profile_build=revision;
 int formats[]={PIXEL_8,PIXEL_x8,PIXEL_16,PIXEL_32};
 for(unsigned f=0;f<4;f++)for(int layers=0;layers<2;layers++)for(int failed=0;failed<2;failed++){
  reset();pixelformat=formats[f];screenformat=f%2?PIXEL_32:PIXEL_16;level->numbglayers=layers;alloc_ok=!failed;
  obor_prepare_background_buffer();
  int requested=allocate_buffer && formats[f]==PIXEL_x8 && layers;
  assert(allocs==requested && active==(requested && !failed));
  assert(!!bgbuffer==(requested && !failed));assert(bgbuffer_updated==(reset_cache?0:7));
  room.name=allocate(16);strcpy(room.name,"fixture");
  for(int repeat=0;repeat<2;repeat++){
   used=0;int before=frees;
   unload_level();
   assert(!bgbuffer && !texture && !level && !active);
   assert(frees-before==(repeat?0:(requested && !failed)+1));
   assert(background_releases==repeat+1 && panel_releases==repeat+1);
   assert(screen_releases==(repeat+1)*release_buffer);
   int expected[]={1,3,4};assert(used==(release_buffer?4:3)-(repeat?1:0));
   /* First call also clears the live level name and level; second is empty. */
   assert(events[0]==expected[0] && events[1]==expected[1]);
   if(release_buffer)assert(events[2]==expected[2]);
   if(!repeat)assert(events[used-1]==5);
  }
 }
 if(has_texture)for(int existing=0;existing<2;existing++)for(int fail=0;fail<2;fail++){
  reset();pixelformat=PIXEL_x8;screenformat=PIXEL_32;
  if(existing)texture=allocate(sizeof(s_bitmap)+32);
  image_ok=!fail;
  if(!setjmp(stop)){load_texture("fixture.img");assert(!fail);}else assert(fail);
  assert(loads==1 && frees==existing && active==!fail && !!texture==!fail);
  /* All successful ownership reaches the real level teardown. */
  room.name=allocate(16);strcpy(room.name,"fixture");
  used=0;unload_level();assert(!texture && !active && !level);
  int i=0;assert(events[i++]==1);if(!fail)assert(events[i++]==2);assert(events[i++]==3);
  if(release_buffer){assert(events[i++]==4);}
  assert(events[i++]==5);assert(used==i);
  assert(frees==existing+!fail+1);
 }
 assert(!active);
}
int main(void){@CHECKS@return 0;}
