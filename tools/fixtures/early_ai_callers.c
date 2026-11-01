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
static entity actor,parent,*self=&actor;
static unsigned time=1000;
static char trace[32];
static unsigned trace_length;
static int follows;
static void mark(char value){assert(trace_length+1<sizeof(trace));trace[trace_length++]=value;trace[trace_length]=0;}
static entity *probe_target(int type,int hostile){assert(type==-1 && !hostile);mark('N');return NULL;}
static entity *probe_item(void){mark('L');return NULL;}
static int probe_jump(void){mark('J');return 0;}
static int probe_blocked(void){mark('B');return 0;}
static int probe_follow(entity *owner,int dox,int doz){
 assert(owner==actor.parent && dox && doz);mark('F');
 if(follows){assert(owner==&parent);actor.xdir=2;actor.zdir=1;}
 return follows;
}
static int probe_free(int dox,int doz){assert(dox && doz);mark('W');actor.xdir=4;actor.zdir=2;return 1;}
static int probe_idle(entity *ent){assert(ent==self && !ent->xdir && !ent->zdir);mark('I');return 1;}
static int probe_unexpected(void){abort();return 0;}
#define normal_find_target probe_target
#define normal_find_item probe_item
#define common_try_jump probe_jump
#define checkpathblocked probe_blocked
#define common_try_follow probe_follow
#define common_try_wandercompletely probe_free
#define set_idle probe_idle
#define validanim(...) probe_unexpected()
#define ent_set_anim(...) abort()
#define common_try_pick(...) abort()
#define common_try_chase(...) probe_unexpected()
#define common_try_avoid(...) probe_unexpected()
#define common_try_wander(...) abort()
#define find_ent_here(...) (abort(),(entity*)NULL)
#define common_pickupitem(...) abort()
void common_turn(void){abort();}
@FUNCTIONS@
typedef struct {const char *trace;float x,z;unsigned stall;} expected;
typedef struct {
 const char *name;int family,follow,idle_flag,aggression,initial_stall;
 expected results[4];
} input;
static const input cases[]={@CASES@};
static void check(unsigned revision,unsigned era){
 assert(era<4 && GAME_SPEED==@GAME_SPEED@);obor_profile_build=revision;
 for(unsigned k=0;k<sizeof(cases)/sizeof(*cases);k++){
  const input *row=&cases[k];const expected *want=&row->results[era];
  memset(&actor,0,sizeof(actor));memset(&parent,0,sizeof(parent));
  actor.x=100;parent.x=200;actor.direction=1;actor.running=1;
  actor.xdir=7;actor.zdir=9;actor.stalltime=row->initial_stall;
  actor.modeldata.type=TYPE_ENEMY;actor.modeldata.aggression=row->aggression;
  actor.modeldata.aimove=row->idle_flag?AIMOVE2_NOTARGETIDLE:0;
  follows=row->follow;actor.parent=follows?&parent:NULL;trace_length=0;trace[0]=0;
  int result=row->family==0?normal_move():row->family==1?avoid_move():chase_move();
  if(result!=1 || strcmp(trace,want->trace) || actor.xdir!=want->x || actor.zdir!=want->z || actor.stalltime!=want->stall){
   fprintf(stderr,"%s revision=%u trace=%s x=%g z=%g stall=%u\n",row->name,revision,
           trace,(double)actor.xdir,(double)actor.zdir,actor.stalltime);abort();
  }
  assert(actor.direction==1 && actor.running==1 && !actor.takeaction);
 }
}
int main(void){@CHECKS@ puts("early_ai_callers=1");return 0;}
