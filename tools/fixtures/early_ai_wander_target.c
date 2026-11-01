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
static unsigned rng_calls,walk_calls,idle_calls;
static uint32_t random_values[3];
static float walked_x,walked_z;
static uint32_t random_value(void){assert(rng_calls<3);return random_values[rng_calls++];}
static void record_walk(entity *e){assert(e==&target);walk_calls++;walked_x=self->xdir;walked_z=self->zdir;}
static int record_idle(entity *e){assert(e==self && !self->xdir && !self->zdir);idle_calls++;return 1;}
#define rand32 random_value
#define adjust_walk_animation record_walk
#define set_idle record_idle
@FUNCTIONS@
typedef struct {int result;float x,z;int delay;unsigned rng,walk,idle;} expected;
typedef struct {
 const char *name;float x,z,tx,tz,grab;
 int aggression,target_direction,target_attacking,nomove,present,r0,r1,r2,vertical,dox,doz,width,height;
 expected results[6];
} input;
static const input cases[]={@CASES@};
static void check(unsigned revision,unsigned era){
 assert(era<6);obor_profile_build=revision;
 for(unsigned k=0;k<sizeof(cases)/sizeof(*cases);k++){
  const input *row=&cases[k];const expected *want=&row->results[era];
  if(era<3 && (!row->dox || !row->doz))continue;
  memset(&actor,0,sizeof(actor));memset(&target,0,sizeof(target));memset(&scene,0,sizeof(scene));
  actor.x=row->x;actor.z=row->z;target.x=row->tx;target.z=row->tz;
  actor.xdir=7;actor.zdir=9;actor.stalltime=1000;actor.running=1;actor.direction=1;
  actor.modeldata.speed=4;actor.modeldata.grabdistance=row->grab;actor.modeldata.aggression=row->aggression;
  actor.modeldata.nomove=row->nomove;target.direction=row->target_direction;target.attacking=row->target_attacking;
  scene.scrolldir=row->vertical==2?SCROLL_DOWN:row->vertical?SCROLL_UP:SCROLL_RIGHT;
  videomodes.hRes=row->width;videomodes.vRes=row->height;
  random_values[0]=row->r0;random_values[1]=row->r1;random_values[2]=row->r2;
  rng_calls=walk_calls=idle_calls=0;walked_x=walked_z=0;
  int result=common_try_wander(row->present?&target:NULL,row->dox,row->doz);
  if(result!=want->result || actor.xdir!=want->x || actor.zdir!=want->z || actor.stalltime!=1000u+want->delay ||
     rng_calls!=want->rng || walk_calls!=want->walk || idle_calls!=want->idle){
   fprintf(stderr,"%s revision=%u result=%d x=%g z=%g delay=%d rng=%u walk=%u idle=%u\n",
           row->name,revision,result,(double)actor.xdir,(double)actor.zdir,
           (int)(actor.stalltime-1000u),rng_calls,walk_calls,idle_calls);
   abort();
  }
  assert(actor.running==1 && actor.direction==1);
  if(walk_calls)assert(walked_x==actor.xdir && walked_z==actor.zdir);
 }
}
int main(void){@CHECKS@ puts("early_ai_wander_target=1");return 0;}
