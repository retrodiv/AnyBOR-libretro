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
#undef validanim
uint32_t obor_profile_build;
static entity actor,*self=&actor;
static s_level scene,*level=&scene;
static s_videomodes videomodes;
static float advancex=100,advancey=50;
static unsigned rng_calls,turn_calls,walk_calls;
static uint32_t random_values[2];
static int has_turn,walked_direction;
static float walked_x,walked_z;
static uint32_t random_value(void){assert(rng_calls<2);return random_values[rng_calls++];}
static int valid(entity *e,int anim){assert(e==self && anim==ANI_TURN);turn_calls++;return has_turn;}
static void record_walk(entity *e){assert(!e);walk_calls++;walked_x=self->xdir;walked_z=self->zdir;walked_direction=self->direction;}
#define rand32 random_value
#define validanim valid
#define adjust_walk_animation record_walk
@FUNCTION@
typedef struct {int result;float x,z;int direction,delay;unsigned rng,turn,walk;} expected;
typedef struct {
 const char *name;float x,z;
 int direction,noflip,nomove,has_turn,r0,r1,vertical,dox,doz,width,height;
 expected results[6];
} input;
static const input cases[]={@CASES@};
static void check(unsigned revision,unsigned era){
 assert(era<6);obor_profile_build=revision;
 for(unsigned k=0;k<sizeof(cases)/sizeof(*cases);k++){
  const input *row=&cases[k];const expected *want=&row->results[era];
  if(era<3 && (!row->dox || !row->doz))continue;
  memset(&actor,0,sizeof(actor));memset(&scene,0,sizeof(scene));
  actor.x=row->x;actor.z=row->z;actor.direction=row->direction;actor.running=1;
  actor.modeldata.speed=4;actor.modeldata.noflip=row->noflip;actor.modeldata.nomove=row->nomove;
  actor.xdir=7;actor.zdir=9;actor.stalltime=1000;
  scene.scrolldir=row->vertical==2?SCROLL_DOWN:row->vertical?SCROLL_UP:SCROLL_RIGHT;
  videomodes.hRes=row->width;videomodes.vRes=row->height;
  has_turn=row->has_turn;random_values[0]=row->r0;random_values[1]=row->r1;
  rng_calls=turn_calls=walk_calls=0;walked_direction=-1;walked_x=walked_z=0;
  int result=common_try_wandercompletely(row->dox,row->doz);
  if(result!=want->result || actor.xdir!=want->x || actor.zdir!=want->z || actor.direction!=want->direction ||
     actor.stalltime!=1000u+want->delay || rng_calls!=want->rng || turn_calls!=want->turn || walk_calls!=want->walk){
   fprintf(stderr,"%s revision=%u result=%d x=%g z=%g dir=%d delay=%d rng=%u turn=%u walk=%u\n",
           row->name,revision,result,(double)actor.xdir,(double)actor.zdir,actor.direction,
           (int)(actor.stalltime-1000u),rng_calls,turn_calls,walk_calls);
   abort();
  }
  assert(actor.running==1);
  if(walk_calls)assert(walked_x==actor.xdir && walked_z==actor.zdir && walked_direction==actor.direction);
 }
}
int main(void){@CHECKS@ puts("early_ai_wander_free=1");return 0;}
