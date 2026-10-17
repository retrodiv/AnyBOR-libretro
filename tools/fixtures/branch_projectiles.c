/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <stdint.h>
#include "source/openborscript/scriptcommon.h"
#undef assert
#define assert(x) ((x)?(void)0:__builtin_trap())
uint32_t obor_profile_build;
int max_attack_types;
entity *self;
static float output_x,output_y,output_z;
entity *knife_spawn(char *name,int model,float x,float z,float a,int direction,int type,int map) {
 (void)name;(void)model;(void)direction;(void)type;(void)map;
 output_x=x;output_y=a;output_z=z;return self;
}
entity *bomb_spawn(char *name,int model,float x,float z,float a,int direction,int map) {
 return knife_spawn(name,model,x,z,a,direction,0,map);
}
static void launch(s_anim *anim,int kind) {
 __OBOR_ORIGIN__
 if(kind==0) {__OBOR_KNIFE__;}
 else if(kind==1) {__OBOR_SHOOT__}
 else {__OBOR_BOMB__}
}
int main(void) {
 const unsigned profiles[]={7086,7123,7142};
 for(unsigned p=0;p<3;++p)for(int explicit=0;explicit<2;++explicit)
 for(int direction=0;direction<2;++direction)for(int kind=0;kind<3;++kind) {
  int legacy=p!=2;obor_profile_build=profiles[p];
  entity ent={0};s_anim anim={0};self=&ent;ent.position=(s_axis_principal_float){100,200,300};ent.direction=direction;
  anim.obor_projectile_position_explicit=explicit;
  anim.projectile.position=(s_axis_principal_int){explicit?7:0,explicit?8:legacy?0:70,explicit?9:0};
  launch(&anim,kind);
  assert(output_x==100+(direction?1:-1)*anim.projectile.position.x);
  assert(output_z==300+anim.projectile.position.z);
  assert(output_y==200+((kind==1&&legacy&&!explicit)?0:anim.projectile.position.y));
  for(max_attack_types=MAX_ATKS;max_attack_types<MAX_ATKS+10;++max_attack_types) {
   assert((__OBOR_UNSUMMON__)==(legacy?max_attack_types-1:ATK_SUB_ENTITY_UNSUMMON));
   assert((__OBOR_PARENT__)==(legacy?max_attack_types-1:ATK_SUB_ENTITY_PARENT_KILL));
  }
 }
}
