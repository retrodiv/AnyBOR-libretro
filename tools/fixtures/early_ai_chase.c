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
#undef randf
#undef validanim
uint32_t obor_profile_build;
static entity actor,target,*self=&actor;
static s_videomodes videomodes;
static float advancex=100,advancey=50;
static unsigned time=1000;
static int rng_calls,float_calls,walk_calls,random_roll,zero_mask,has_run;
static float walked_x,walked_z;
static uint32_t random_value(void){int call=rng_calls++;assert(call<2);return call?(uint32_t)random_roll:zero_mask?0:UINT32_MAX;}
/* Both side draws use the same finite value: their preserved native
 * expression does not require an expectation about operand evaluation order. */
static float random_float(float limit){assert(limit==1);float_calls++;return 0.5f;}
static int valid(entity *e,int anim){assert(e==self && anim==ANI_RUN);return has_run;}
static void walk(entity *other){assert(other==&target);walk_calls++;walked_x=self->xdir;walked_z=self->zdir;}
#define rand32 random_value
#define randf random_float
#define validanim valid
#define adjust_walk_animation walk
@FUNCTIONS@
typedef struct {int result;float x,z;int running,delay,rng,floats,walk;} expected;
typedef struct {
 const char *name;float x,z,tx,tz,xdir,zdir;
 int direction,aimove,subtype_chase,dox,doz,nomove,present,has_run,runupdown,roll,zero_mask,width,height,grab;
 expected results[5];
} input;
static const input cases[]={@CASES@};
static void check(unsigned revision,unsigned era){
 assert(era<5);obor_profile_build=revision;
 for(unsigned k=0;k<sizeof(cases)/sizeof(*cases);k++){
  const input *row=&cases[k];const expected *want=&row->results[era];
  if(era<2 && (!row->dox || !row->doz))continue;
  memset(&actor,0,sizeof(actor));memset(&target,0,sizeof(target));
  actor.modeldata.speed=4;actor.modeldata.runspeed=8;actor.modeldata.aimove=row->aimove;
  actor.modeldata.subtype=row->subtype_chase?SUBTYPE_CHASE:0;
  actor.modeldata.nomove=row->nomove;actor.modeldata.runupdown=row->runupdown;actor.modeldata.grabdistance=row->grab;
  actor.x=row->x;actor.z=row->z;target.x=row->tx;target.z=row->tz;
  actor.xdir=row->xdir;actor.zdir=row->zdir;actor.direction=row->direction;actor.running=1;actor.stalltime=time;
  videomodes.hRes=row->width;videomodes.vRes=row->height;
  random_roll=row->roll;zero_mask=row->zero_mask;has_run=row->has_run;
  rng_calls=float_calls=walk_calls=0;walked_x=walked_z=0;
  int result=common_try_chase(row->present?&target:NULL,row->dox,row->doz);
  if(result!=want->result || actor.xdir!=want->x || actor.zdir!=want->z ||
     actor.running!=want->running || actor.stalltime!=time+want->delay ||
     rng_calls!=want->rng || float_calls!=want->floats || walk_calls!=want->walk){
   fprintf(stderr,"%s revision=%u result=%d x=%g z=%g running=%d delay=%d rng=%d float=%d walk=%d\n",
           row->name,revision,result,(double)actor.xdir,(double)actor.zdir,actor.running,
           (int)(actor.stalltime-time),rng_calls,float_calls,walk_calls);
   abort();
  }
  assert(actor.direction==row->direction);
  if(walk_calls)assert(walked_x==actor.xdir && walked_z==actor.zdir);
 }
}
int main(void){@CHECKS@ puts("early_ai_chase=1");return 0;}
