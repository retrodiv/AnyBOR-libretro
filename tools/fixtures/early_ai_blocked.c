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
uint32_t obor_profile_build;
static entity actor,*self=&actor;
static unsigned time=1000;
static int PLAYER_MIN_Z=160,PLAYER_MAX_Z=232;
static int roll,rng_calls,walk_calls,walk_counter;
static unsigned walk_stall;
static float random_value(float limit){
 int call=rng_calls++;
 if(!call){assert(limit==1);return roll==0?0.75f:roll==1?0.5f:0.125f;}
 assert(roll==2 && limit==2 && call<=2);return call==1?1.5f:0.5f;
}
static int idle(entity *e){assert(e==self);abort();}
static void walk(entity *e){assert(!e && !self->running);walk_calls++;walk_counter=self->pathblocked;walk_stall=self->stalltime;}
#define randf random_value
#define set_idle idle
#define adjust_walk_animation walk
@FUNCTION@
typedef struct {unsigned revision;int delay,z_reversal,limit,returns_active,nomove_guard,callback_before_reset;} contract;
static const contract contracts[]={@ROWS@};
static void reset(void){
 memset(&actor,0,sizeof(actor));actor.modeldata.speed=4;actor.running=1;
 actor.stalltime=time;actor.z=200;rng_calls=walk_calls=0;walk_counter=-1;walk_stall=0;
}
static void verify(const contract *c,int raw,int chase,int active,int nomove,float x,float z,float position,int bounds){
 reset();obor_profile_build=c->revision;actor.pathblocked=raw;actor.stalltime=time+active;
 actor.xdir=x;actor.zdir=z;actor.z=position;actor.modeldata.nomove=nomove;
 actor.modeldata.subject_to_minz=!!(bounds&1);actor.modeldata.subject_to_maxz=!!(bounds&2);
 static const int chase_types[]={0,AIMOVE1_CHASEX,AIMOVE1_CHASEZ,AIMOVE1_CHASE};
 if(chase==4)actor.modeldata.subtype=SUBTYPE_CHASE;else actor.modeldata.aimove=chase_types[chase];
 int eligible=active>=0 && !(nomove && c->nomove_guard);
 int reverse=eligible && c->z_reversal && !x &&
   ((bounds&1 && z<0 && position+z<=160) || (bounds&2 && z>0 && position+z>=232));
 int steer=eligible && !reverse && (raw>c->limit || (raw>20 && chase));
 int result=checkpathblocked();
 assert(result==(eligible && c->returns_active));
 if(reverse){
  assert(actor.xdir==x && actor.zdir==-z && actor.running==1 && actor.stalltime==time+active);
  assert(actor.pathblocked==(c->callback_before_reset?0:raw) && !rng_calls && !walk_calls);
 }else if(steer){
  float nx=x>0?4:x<0?-4:0,nz=z>0?2:z<0?-2:0;
  float expected_x=roll==0?-nz:roll==1?nz:2,expected_z=roll==0?nx:roll==1?-nx:-1;
  assert(actor.xdir==expected_x && actor.zdir==expected_z && !actor.running && !actor.pathblocked);
  assert(actor.stalltime==time+c->delay && walk_stall==actor.stalltime && walk_calls==1);
  assert(walk_counter==(c->callback_before_reset?raw:0) && rng_calls==(roll==2?3:1));
 }else{
  assert(actor.xdir==x && actor.zdir==z && actor.running==1 && actor.pathblocked==raw);
  assert(actor.stalltime==time+active && !rng_calls && !walk_calls);
 }
}
static void check(const contract *c){
 static const int counts[]={0,20,21,40,41,200,201,255};
 static const int positions[]={159,160,161,231,232,233};
 for(unsigned i=0;i<sizeof(counts)/sizeof(*counts);i++)for(int chase=0;chase<=4;chase++)
 for(int active=-1;active<=1;active++)for(int nomove=0;nomove<=1;nomove++)
 for(int x=-1;x<=1;x++)for(int z=-1;z<=1;z++)for(roll=0;roll<3;roll++)
  verify(c,counts[i],chase,active,nomove,x*2.0f,(float)z,200,0);
 for(unsigned i=0;i<sizeof(positions)/sizeof(*positions);i++)for(int bounds=0;bounds<4;bounds++)
 for(int active=-1;active<=1;active++)for(int nomove=0;nomove<=1;nomove++)
 for(int x=0;x<=1;x++)for(int z=-1;z<=1;z++)for(int blocked=0;blocked<=1;blocked++){
  roll=0;verify(c,blocked?201:7,0,active,nomove,(float)x,(float)z,positions[i],bounds);
 }
}
int main(void){
 for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);i++)check(&contracts[i]);
 puts("early_ai_blocked=1");return 0;
}
