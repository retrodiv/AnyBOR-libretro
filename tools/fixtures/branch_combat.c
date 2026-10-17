/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */

#include <stdint.h>
#include <limits.h>
#include "source/openborscript/scriptcommon.h"
#undef assert
#define assert(x) ((x)?(void)0:__builtin_trap())
#undef cangrab
#define cangrab(a,b) (grab_allowed)
static int grab_allowed;
uint32_t obor_profile_build;
entity *self;
int max_follows=4;
int max_attack_types=MAX_ATKS;
static int follow_ids[4]={1,2,3,4};
int *animfollows=follow_ids;
static int animation_calls,last_reset,flash_calls;
void ent_set_anim(entity *ent,int id,int reset) { ++animation_calls;last_reset=reset;ent->animation=ent->modeldata.animation[id]; }
entity *spawn_attack_flash(entity *ent,s_collision_attack *attack,int flash,int model) {
 (void)ent;(void)attack;(void)flash;(void)model;++flash_calls;return NULL;
}
__OBOR_DAMAGE_FUNCTION__
METHODS
static int reference_follow(entity *e,int didblock) { return (e->animation->followup.animation && !e->animation->obor_counter_present &&
  ((int)e->animation->followup.condition == 0 || (int)e->animation->followup.condition == 1 ||
   (((self->modeldata.type & e->modeldata.hostile) != 0) &&
    ((int)e->animation->followup.condition == 2 ||
     ((int)e->animation->followup.condition == 3 && self->energy_state.health_current > 0 && !didblock) ||
     ((int)e->animation->followup.condition == 4 && self->energy_state.health_current > 0 && !didblock && grab_allowed))))); }
static int reference_counter(entity *e,s_collision_attack *attack,int force,int them) {
 if(!self->animation->obor_counter_present || self->frozen ||
    self->animpos < self->animation->counter_action.frame.min ||
    self->animpos > self->animation->counter_action.frame.max) return 0;
 switch((int)self->animation->counter_action.condition) {
  case 4:return 1;
  case 1:return self->energy_state.health_current > force;
  case 2:return self->energy_state.health_current > force && (e->modeldata.type & them)!=0;
  case 3:return self->energy_state.health_current > force && !attack->no_block && self->direction!=e->direction && !attack->freeze;
  default:return 0;
 }
}
int main(void) {
 entity attacker={0},target={0};s_anim a={0},t={0},next={0};s_collision_attack attack={0};
 s_anim *animations[5]={&a,&next,&next,&next,&next};
 attacker.animation=&a;attacker.modeldata.animation=animations;attacker.modeldata.animation_capacity=5;
 target.animation=&t;target.modeldata.animation=animations;target.modeldata.animation_capacity=5;
 a.numframes=t.numframes=next.numframes=1;self=&target;
 float offense[MAX_ATKS];s_defense defense[MAX_ATKS];memset(defense,0,sizeof(defense));
 for(int i=0;i<MAX_ATKS;++i){offense[i]=2.0f;defense[i].factor=1.0f;}
 attacker.offense_factors=offense;target.defense=defense;

 const unsigned profiles[]={7086,7123};
 for(unsigned p=0;p<2;++p) {
  obor_profile_build=profiles[p];
  for(int condition=-1;condition<=8;++condition)for(int counter=0;counter<2;++counter)
  for(int blocked=0;blocked<2;++blocked)for(int alive=0;alive<2;++alive)
  for(int hostile=0;hostile<2;++hostile)for(int grab=0;grab<2;++grab) {
   attacker.animation=&a;target.animation=&t;a.followup.animation=1;
   a.obor_counter_present=counter;a.followup.condition=condition;
   target.energy_state.health_current=alive;target.modeldata.type=TYPE_ENEMY;
   attacker.modeldata.hostile=hostile?TYPE_ENEMY:0;grab_allowed=grab;
   int expected=reference_follow(&attacker,blocked);
   assert(!!check_follow_up_condition(&attacker,&target,&a,blocked)==expected);
   animation_calls=0;a.attack_one=1;next.attack_one=0;
   assert(try_follow_up(&attacker,&target,&a,blocked)==expected);
   assert(animation_calls==expected && next.attack_one==expected);
   if(expected)assert(last_reset==1);
  }
  attacker.animation=&a;target.animation=&t;target.animpos=2;
  t.followup.animation=1;t.counter_action.frame.min=1;t.counter_action.frame.max=3;
  attack=(s_collision_attack){0};
  for(int condition=-1;condition<=6;++condition)for(int present=0;present<2;++present)
  for(int frozen=0;frozen<2;++frozen)for(int lethal=0;lethal<2;++lethal)
  for(int type=0;type<2;++type)for(int mask=0;mask<2;++mask)
  for(int direction=0;direction<2;++direction)for(int unblockable=0;unblockable<2;++unblockable)
  for(int freeze=0;freeze<2;++freeze) {
   t.counter_action.condition=condition;t.obor_counter_present=present;
   target.frozen=frozen;target.energy_state.health_current=lethal?10:30;
   attacker.modeldata.type=type?TYPE_ENEMY:TYPE_PLAYER;
   attacker.modeldata.candamage=mask?TYPE_ENEMY:TYPE_PLAYER;
   attacker.projectile=0;target.direction=0;attacker.direction=direction;
   attack.attack_force=20;attack.no_block=unblockable;attack.freeze=freeze;
   int expected=reference_counter(&attacker,&attack,20,attacker.modeldata.candamage);
   assert(!!check_counter_condition(&target,&attacker,&attack)==expected);
  }
  target.frozen=0;target.direction=0;attacker.direction=1;target.animpos=2;
  t.counter_action.condition=COUNTERACTION_CONDITION_ALWAYS_RAGE;t.obor_counter_present=1;
  t.counter_action.damaged=COUNTERACTION_DAMAGE_NORMAL;target.energy_state.health_current=30;
  t.followup.animation=1;target.animation=&t;attack.attack_force=20;animation_calls=flash_calls=0;
  assert(try_counter_action(&target,&attacker,&attack)==2);
  assert(target.energy_state.health_current==10 && animation_calls==1 && flash_calls==1 && last_reset==0);
  target.animation=&t;target.energy_state.health_current=10;
  assert(try_counter_action(&target,&attacker,&attack)==2 && target.energy_state.health_current==1);
  target.animation=&t;next.numframes=0;target.energy_state.health_current=30;
  assert(try_counter_action(&target,&attacker,&attack)==1 && target.energy_state.health_current==10);
  next.numframes=1;t.followup.animation=0;target.animation=&t;
  assert(!try_counter_action(&target,&attacker,&attack));
  t.followup.animation=5;assert(!try_counter_action(&target,&attacker,&attack));
  a.followup.animation=5;assert(!try_follow_up(&attacker,&target,&a,0));
 }
 obor_profile_build=7142;target.animation=&t;target.energy_state.health_current=30;
 t.counter_action.condition=COUNTER_ACTION_CONDITION_ANY;t.followup.animation=1;
 assert(try_counter_action(&target,&attacker,&attack)==1 && target.energy_state.health_current==1);
}
