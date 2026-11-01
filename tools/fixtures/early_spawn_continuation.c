/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Native caller windows and complete falling/bomb caller contracts.
 */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef assert
#undef time
#undef inair
#define time probe_time
#define assert(c) do {if(!(c)){fprintf(stderr,"spawn contract line=%d revision=%u\n",__LINE__,obor_profile_build);abort();}}while(0)
uint32_t obor_profile_build;
static entity actor,child,held,*self=&actor;
static s_anim animation;
static s_model child_model;
static unsigned time=1000;
static int nocost,autoland,level_completed,tospeedup,operation,missing,expected_index,air,weapon_requested;
static float expected_a;
static char trace[32];static unsigned trace_at;
static void note(char c){assert(trace_at+1<sizeof(trace));trace[trace_at++]=c;trace[trace_at]=0;}
entity *spawn(float x,float z,float a,int direction,char *name,int index,s_model *model){
 assert(x==17 && index==expected_index);
 if(operation==1)assert(z==100000 && a==0 && direction==0 && name && !strcmp(name,"weapon") && model==&child_model);
 else assert(z==23 && a==actor.a && direction==actor.direction && model==NULL);
 if(operation==0)assert(name==NULL);
 note('S');return missing?NULL:&child;
}
void execute_onspawn_script(entity *e){
 if(operation==0)assert(e==&child && e->base==actor.a && e->autokill==1);
 else assert(operation==1 && e==&actor && e->weapent==(weapon_requested&&!missing?&child:NULL));
 note('E');
}
void execute_spawn_script(s_spawn_entry *p,entity *e){assert(p && e==&actor);note('P');}
void set_weapon(entity *e,int slot,int reset){assert(operation==1 && e==&actor && !e->weapent && slot==4 && reset==0);note('W');}
void common_think(void){abort();}
int common_takedamage(entity *e,s_attack *attack){(void)e;(void)attack;abort();}
void common_lie(void){abort();}
void toss(entity *e,float lift){assert(operation==2 && e==&child && e->a==expected_a && lift==3.5f);note('T');}
void ent_set_colourmap(entity *e,unsigned int map){assert(operation==2 && e==&child && map==2 && e->owner==self && e->attacking && e->nograb);note('M');}
void dropweapon(int flag){assert(flag==1);note('W');}
void doland(void){note('D');}
static int probe_air(entity *e){assert(e==self);note('A');return air;}
#define inair probe_air
@FUNCTIONS@
@EFFECTS@
@WEAPON@
static void (*const effects[])(void)={@EFFECT_POINTERS@};
static const int effect_indices[]={41,43,42,44,44,45,45};
struct fall_result {const char *trace;int normal,landed,speedup;};
struct fall_case {int falling,air,toss,projectile,autoland,damage,weaploss,boss,complete;struct fall_result expected[2];};
static const struct fall_case falls[]={@FALL_CASES@};
struct bomb_case {int route,model_speed,nomove,cost,nocost,speed,cantfire;};
static const struct bomb_case bombs[]={@BOMB_CASES@};
static const float heights[][3]={@HEIGHTS@};
static void reset(void){
 memset(&actor,0,sizeof(actor));memset(&child,0,sizeof(child));memset(&held,0,sizeof(held));
 memset(&animation,0,sizeof(animation));memset(&child_model,0,sizeof(child_model));
 actor.exists=child.exists=held.exists=1;
 actor.x=17;actor.z=23;actor.animation=&animation;actor.modeldata.hostile=TYPE_ENEMY;actor.modeldata.candamage=TYPE_PLAYER;
 animation.jumpframe.ent=41;animation.landframe.ent=42;actor.modeldata.dust[0]=43;actor.modeldata.dust[1]=44;actor.modeldata.dust[2]=45;
 child.model=&child_model;child.modeldata.weapnum=4;child.modeldata.jumpheight=3.5f;
 trace_at=0;trace[0]=0;tospeedup=0;
}
static void check(int revision,int fall_era,int bomb_era){
 obor_profile_build=(uint32_t)revision;
 for(unsigned site=0;site<sizeof(effects)/sizeof(*effects);++site)
 for(int fail=0;fail<2;++fail)for(int direction=0;direction<2;++direction)for(int height=0;height<2;++height){
  reset();operation=0;missing=fail;expected_index=effect_indices[site];actor.direction=direction;actor.a=heights[height][0];
  entity before=actor;effects[site]();
  assert(!strcmp(trace,fail?"S":"SE") && !memcmp(&actor,&before,sizeof(actor)));
 }
 for(int weapon=0;weapon<2;++weapon)for(int fail=0;fail<2;++fail){
  reset();operation=1;missing=fail;weapon_requested=weapon;expected_index=7;s_spawn_entry props={0};
  props.weapon=weapon?(char*)"weapon":NULL;props.weaponindex=7;props.weaponmodel=&child_model;
  assert(weapon_tail(&props)==&actor);
  assert(!strcmp(trace,!weapon?"EP":fail?"SEP":"SWEP"));
  assert(actor.weapent==(weapon&&!fail?&child:NULL));
 }
 for(unsigned i=0;i<sizeof(falls)/sizeof(*falls);++i){
  const struct fall_case *c=falls+i;const struct fall_result *want=&c->expected[fall_era];
  reset();air=c->air;autoland=c->autoland;level_completed=c->complete;actor.falling=c->falling;actor.tossv=c->toss;
  actor.projectile=c->projectile;actor.damage_on_landing=c->damage;actor.modeldata.weaploss[0]=c->weaploss;actor.boss=c->boss;
  actor.staydown.rise=4;actor.staydown.riseattack=5;actor.modeldata.risetime[0]=7;actor.modeldata.risetime[1]=11;
  actor.stalltime=99;actor.staydown.riseattack_stall=98;common_fall();
  assert(!strcmp(trace,want->trace) && tospeedup==want->speedup);
  if(want->normal){
   assert(actor.takeaction==common_lie && actor.stalltime==4+time+GAME_SPEED-7);
   assert(actor.staydown.riseattack_stall==994 && actor.staydown.rise==0 && actor.staydown.riseattack==0);
  }else assert(!actor.takeaction && actor.stalltime==99 && actor.staydown.riseattack_stall==98 && actor.staydown.rise==4 && actor.staydown.riseattack==5);
  assert((strchr(trace,'D')!=NULL)==want->landed);
 }
 for(unsigned i=0;i<sizeof(bombs)/sizeof(*bombs);++i)
 for(int fail=0;fail<2;++fail)for(int height=0;height<2;++height){
  const struct bomb_case *c=bombs+i;
  reset();operation=2;missing=fail;actor.a=heights[height][0];expected_a=heights[height][1+bomb_era];actor.direction=1;
  actor.weapent=c->route==0?&held:NULL;held.modeldata.subtype=SUBTYPE_PROJECTILE;held.modeldata.project=51;
  animation.custbomb=c->route<=1?52:-1;actor.modeldata.bomb=c->route<=2?53:-1;
  expected_index=c->route==0?51:c->route==1?52:c->route==2?53:54;
  child_model.speed=c->model_speed;child.modeldata.speed=7;child.modeldata.nomove=c->nomove;
  child.modeldata.hostile=child.modeldata.candamage=-1;nocost=c->nocost;animation.energycost.cost=c->cost;
  entity *result=bomb_spawn((char*)"authored",54,17,23,actor.a,1,2);
  assert(result==(fail?NULL:&child) && !strcmp(trace,fail?"S":"SMT"));
  assert(actor.cantfire==(!fail&&c->cantfire));
  if(!fail){
   assert(child.a==expected_a && child.modeldata.speed==c->speed && child.attacking && child.nograb && child.toexplode);
   assert(child.owner==&actor && child.think==common_think && child.nextthink==time+1 && !child.trymove && !child.takeaction);
   assert(child.modeldata.aimove==AIMOVE1_BOMB && child.modeldata.aiattack==AIATTACK1_NOATTACK && child.takedamage==common_takedamage);
   assert(child.remove_on_attack==0 && child.autokill==c->nomove && child.modeldata.hostile==TYPE_ENEMY && child.modeldata.candamage==TYPE_PLAYER);
   assert(child.modeldata.no_adjust_base==0 && child.modeldata.subject_to_wall && child.modeldata.subject_to_platform && child.modeldata.subject_to_hole && child.modeldata.subject_to_gravity);
  }
 }
 printf("revision=%d effects=7 weapon=1 fall=%zu bomb=%zu\n",revision,sizeof(falls)/sizeof(*falls),sizeof(bombs)/sizeof(*bombs));
}
int main(void){@CHECKS@puts("early_spawn_continuation=1");return 0;}
