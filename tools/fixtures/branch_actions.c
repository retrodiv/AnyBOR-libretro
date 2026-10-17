/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <stdint.h>
#include <string.h>
#include "source/openborscript/scriptcommon.h"
#undef assert
#define assert(x) ((x)?(void)0:(fprintf(stderr,"assertion line %d: %s\n",__LINE__,#x),__builtin_trap()))
uint32_t obor_profile_build;
entity *self;
static entity effect;
static int spawned,updated,selected_animation,healthcheat;
void toss(entity *ent,float velocity) {ent->velocity.y=velocity;}
void update_frame(entity *ent,unsigned frame) {++updated;ent->animpos=frame;}
void ent_set_anim(entity *ent,int animation,int reset) {(void)ent;(void)reset;selected_animation=animation;}
entity *spawn(float x,float z,float a,int dir,char *name,int index,s_model *model) {
 (void)x;(void)z;(void)a;(void)dir;(void)name;(void)model;
 assert(index==7);++spawned;return &effect;
}
void execute_onspawn_script(entity *ent) {assert(ent==&effect);}
METHODS
static void drop(void) { __OBOR_DROP_BRANCH__ }
static int jump_cost(void) { int candospecial=0; __OBOR_JUMP_COST__ return candospecial; }
int main(void) {
 const unsigned profiles[]={7086,7123,7142};
 for(unsigned p=0;p<3;++p) {
  int legacy=p!=2;obor_profile_build=profiles[p];
  entity ent={0},parent={0};s_anim animation={0};s_anim *animations[]={&animation};self=&ent;
  ent.animation=&animation;ent.modeldata.animation=animations;ent.modeldata.animation_capacity=1;animation.numframes=10;
  ent.binding.ent=&parent;
  const int flags[]={BIND_OVERRIDE_FALL_LAND,BIND_OVERRIDE_FRAME_SET_LAND,BIND_OVERRIDE_SPECIAL_AI,BIND_OVERRIDE_SPECIAL_PLAYER};
  for(unsigned f=0;f<4;++f)for(int mask=0;mask<32;++mask) {
   ent.binding.overriding=mask;int bit=flags[f];if(legacy&&f)bit>>=1;
   assert(!!check_bind_override(&ent,flags[f])==!!(mask&bit));
  }
  ent.binding.ent=NULL;
  const int types[]={TYPE_PLAYER,TYPE_ENEMY,TYPE_NPC,TYPE_SHOT,TYPE_PLAYER|TYPE_NPC};
  for(unsigned t=0;t<5;++t)for(int disable=-5;disable<=35;++disable)
  for(int cost=0;cost<=8;cost+=4)for(int mode=0;mode<3;++mode)
  for(int hp=0;hp<=8;hp+=4)for(int mp=0;mp<=8;mp+=4)for(int seal=0;seal<=6;seal+=3) {
   int type=types[t];ent.modeldata.type=type;ent.seal=seal;
   ent.energy_state.health_current=hp;ent.energy_state.mp_current=mp;
   animation.energy_cost=(s_energy_cost){.cost=cost,.disable=disable,.mponly=mode};
   int disabled=legacy?(disable==type||disable==-1||
    (disable==-2&&(type&(TYPE_ENEMY|TYPE_NPC)))||
    (disable==-3&&(type&(TYPE_PLAYER|TYPE_NPC)))||
    (disable==-4&&(type&(TYPE_PLAYER|TYPE_ENEMY)))):!!(disable&type);
   assert(!!check_energy(ENERGY_TYPE_HP,0)==(!disabled&&(!seal||seal>=cost)&&mode!=COST_TYPE_MP_ONLY&&hp>cost));
   assert(!!check_energy(ENERGY_TYPE_MP,0)==(!disabled&&(!seal||seal>=cost)&&mode!=COST_TYPE_HP_ONLY&&mp>=cost));
  }
  for(int present=0;present<2;++present)for(int right=0;right<2;++right) {
   animation.obor_jump_present=animation.obor_land_present=animation.obor_drop_present=present;
   animation.jumpframe=(s_onframe_move){.frame=3,.ent=7,.velocity={2,4,6}};
   ent.direction=right;spawned=updated=0;
   int active=!legacy||present;
   assert(check_jumpframe(&ent,3)==active && spawned==active);
   if(active)assert(ent.velocity.x==(right?2:-2)&&ent.velocity.y==4&&ent.velocity.z==6);
   animation.landframe=(s_onframe_set){.frame=3,.model_index=7};
   ent.animpos=0;spawned=updated=0;
   assert(check_landframe(&ent)==active && spawned==active && updated==active);
   animation.dropframe=(s_onframe_set){.frame=3,.model_index=7};
   ent.animpos=0;ent.velocity.y=0;spawned=updated=0;drop();
   assert(updated==active && spawned==(legacy?0:1));
  }
  s_anim *jump_animations[1024]={0};jump_animations[ANI_JUMPSPECIAL]=jump_animations[ANI_JUMPCANT]=&animation;
  ent.modeldata.animation=jump_animations;ent.modeldata.animation_capacity=1024;
  animation.energy_cost=(s_energy_cost){0};ent.seal=0;ent.modeldata.type=TYPE_PLAYER;
  ent.energy_state.health_current=20;ent.energy_state.mp_current=20;
  for(int present=0;present<2;++present) {
   animation.obor_energy_present=present;selected_animation=-1;
   assert(jump_cost()==(!legacy||present));
   assert(selected_animation==((legacy&&!present)?ANI_JUMPCANT:-1));
  }
 }
}
