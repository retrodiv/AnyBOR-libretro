/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef exit
#undef time
#undef pause
#undef shutdown
uint32_t obor_profile_build;
static entity actor,target,*self=&actor;
static s_level scene,*level=&scene;
static s_videomodes videomodes;
static float advancex=100,advancey=50;
static unsigned time=1000;
static int random_zero,rng_calls,walk_calls;
static float walked_x,walked_z;
static uint32_t random_value(void){rng_calls++;return random_zero?0:UINT32_MAX;}
static void walk(entity *other){assert(other==&target);walk_calls++;walked_x=self->xdir;walked_z=self->zdir;}
#define rand32 random_value
#define adjust_walk_animation walk
@FUNCTIONS@
typedef struct {int result;float x,z;int delay,rng,walk;} expected;
typedef struct {
 const char *name;float x,z,tx,tz;
 int width,height,vertical,aimove,dox,doz,nomove,present,random_zero;
 expected results[5];
} input;
static const input cases[]={@CASES@};
static void check(unsigned revision,unsigned era){
 assert(era<5);obor_profile_build=revision;
 for(unsigned k=0;k<sizeof(cases)/sizeof(*cases);k++){
  const input *row=&cases[k];const expected *want=&row->results[era];
  /* Earlier callers have no axis arguments and always request both axes. */
  if(!era && (!row->dox || !row->doz))continue;
  memset(&actor,0,sizeof(actor));memset(&target,0,sizeof(target));memset(&scene,0,sizeof(scene));
  actor.modeldata.speed=4;actor.modeldata.aimove=row->aimove;actor.modeldata.nomove=row->nomove;
  actor.x=row->x;actor.z=row->z;target.x=row->tx;target.z=row->tz;
  actor.xdir=7;actor.zdir=9;actor.stalltime=time;actor.running=1;actor.direction=1;
  scene.scrolldir=row->vertical?SCROLL_UP:SCROLL_RIGHT;
  videomodes.hRes=row->width;videomodes.vRes=row->height;
  random_zero=row->random_zero;rng_calls=walk_calls=0;walked_x=walked_z=0;
  int result=common_try_avoid(row->present?&target:NULL,row->dox,row->doz);
  if(result!=want->result || actor.xdir!=want->x || actor.zdir!=want->z ||
     actor.stalltime!=time+want->delay || rng_calls!=want->rng || walk_calls!=want->walk){
   fprintf(stderr,"%s revision=%u result=%d x=%g z=%g delay=%u rng=%d walk=%d\n",
           row->name,revision,result,(double)actor.xdir,(double)actor.zdir,
           actor.stalltime-time,rng_calls,walk_calls);
   abort();
  }
  assert(actor.running==1 && actor.direction==1);
  if(walk_calls)assert(walked_x==actor.xdir && walked_z==actor.zdir);
 }
}
int main(void){@CHECKS@ puts("early_ai_avoid=1");return 0;}
