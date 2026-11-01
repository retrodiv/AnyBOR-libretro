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
static entity actor,parent,target,*self=&actor;
static int idle_present,has_run,idle_calls,run_calls,walk_calls;
static float walked_x,walked_z;
static int valid(entity *e,int anim){
 assert(e==self);
 if(anim==ANI_IDLE){idle_calls++;return idle_present;}
 assert(anim==ANI_RUN);run_calls++;return has_run;
}
static void walk(entity *other){assert(other==&parent);walk_calls++;walked_x=self->xdir;walked_z=self->zdir;}
#define validanim valid
#define adjust_walk_animation walk
@FUNCTIONS@
typedef struct {int result;float x,z;int running,idle,run,walk;} expected;
typedef struct {
 const char *name;float x,z,tx,tz,xdir,zdir;
 int direction,running,nomove,parent_present,target_present,alternate_parent;
 int idle_present,distance,has_run,runupdown,dox,doz;
 expected results[3];
} input;
static const input cases[]={@CASES@};
static void check(unsigned revision,unsigned era){
 assert(era<3);obor_profile_build=revision;
 for(unsigned k=0;k<sizeof(cases)/sizeof(*cases);k++){
  const input *row=&cases[k];const expected *want=&row->results[era];
  if(!era && (!row->dox || !row->doz))continue;
  memset(&actor,0,sizeof(actor));memset(&parent,0,sizeof(parent));memset(&target,0,sizeof(target));
  s_anim idle_animation={0};s_anim *anims[ANI_IDLE+1]={0};anims[ANI_IDLE]=&idle_animation;
  idle_animation.range.xmin=row->distance;actor.modeldata.animation=anims;
  actor.modeldata.speed=4;actor.modeldata.runspeed=8;actor.modeldata.nomove=row->nomove;
  actor.modeldata.runupdown=row->runupdown;actor.parent=row->parent_present?&parent:NULL;
  actor.x=row->x;actor.z=row->z;actor.xdir=row->xdir;actor.zdir=row->zdir;
  actor.running=row->running;actor.direction=row->direction;actor.stalltime=1000;
  target.x=row->tx;target.z=row->tz;
  parent.x=row->alternate_parent?actor.x-240:target.x;parent.z=row->alternate_parent?actor.z:target.z;
  idle_present=row->idle_present;has_run=row->has_run;idle_calls=run_calls=walk_calls=0;
  walked_x=walked_z=0;
  int result=common_try_follow(row->target_present?&target:NULL,row->dox,row->doz);
  if(result!=want->result || actor.xdir!=want->x || actor.zdir!=want->z || actor.running!=want->running ||
     idle_calls!=want->idle || run_calls!=want->run || walk_calls!=want->walk){
   fprintf(stderr,"%s revision=%u result=%d x=%g z=%g running=%d idle=%d run=%d walk=%d\n",
           row->name,revision,result,(double)actor.xdir,(double)actor.zdir,actor.running,idle_calls,run_calls,walk_calls);
   abort();
  }
  assert(actor.direction==row->direction && actor.stalltime==1000);
  if(walk_calls)assert(walked_x==actor.xdir && walked_z==actor.zdir);
 }
}
int main(void){@CHECKS@ puts("early_ai_follow=1");return 0;}
