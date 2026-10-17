/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <limits.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "source/openborscript/scriptcommon.h"
#include "commands.h"
#undef assert
#define assert(x) ((x)?(void)0:(fprintf(stderr,"assertion line %d: %s\n",__LINE__,#x),__builtin_trap()))
uint32_t obor_profile_build;
int max_attack_types=MAX_ATKS+4;
s_defense default_defense;
s_axis_principal_float default_model_dropv={1.2f,3.0f,0.0f};
int getValidInt(char *text,char *file,char *cmd) { (void)file;(void)cmd;return atoi(text); }
float getValidFloat(char *text,char *file,char *cmd) { (void)file;(void)cmd;return strtof(text,NULL); }
int get_cached_model_index(char *name) { assert(!strcmp(name,"model"));return 35; }
void writeToLogFile(const char *format,...) {(void)format;}
TYPE_METHODS
static void initialize(s_anim *newanim) {
 memset(newanim,0,sizeof(*newanim));
 INITIALIZER
}
static int special_defaults(s_anim *newanim,char *value) {
 int ani_id=-1;
 if(0) {}
 SPECIAL_DEFAULTS
 return ani_id;
}
static void apply(s_anim *newanim,s_model *newchar,int cmd,int count,char **args) {
 ArgList arglist={0};arglist.count=count;
 for(int i=0;i<count;++i)arglist.args[i]=args[i];
 char *filename="synthetic",*command="synthetic",*value;
 int tempInt,i;float tempFloat;s_defense defense;
 switch(cmd) {
 CASES
 default:assert(0);
 }
}
static void one(s_anim *a,s_model *m,int command,char *v1,char *v2,char *v3,char *v4,char *v5) {
 char *args[]={"command",v1,v2,v3,v4,v5};int count=1;
 while(count<6 && args[count])++count;
 apply(a,m,command,count,args);
}
int main(void) {
 const unsigned profiles[]={7086,7123,7142};
 for(unsigned p=0;p<3;++p) {
  int legacy=p!=2;obor_profile_build=profiles[p];s_anim a;s_model m={0};
  s_defense defenses[128]={0};float offense[128]={0};m.defense=defenses;m.offense_factors=offense;
  m.type=TYPE_PLAYER;m.jumpheight=12;
  initialize(&a);
  assert(!a.obor_energy_present && !a.obor_counter_present && !a.obor_drop_present && !a.obor_jump_present && !a.obor_land_present);
  assert(a.subject_to_gravity && a.charge_time==2 && a.projectile.position.x==0 && a.projectile.position.z==0);
  assert(a.projectile.position.y==(legacy?0:70));
  assert(a.energy_cost.cost==0 && a.energy_cost.disable==0 && a.energy_cost.mponly==COST_TYPE_MP_THEN_HP);
  assert(special_defaults(&a,"special")==ANI_SPECIAL);
  assert(a.obor_energy_present && a.energy_cost.cost==6);
  a.energy_cost.cost=29;
  special_defaults(&a,"special");assert(a.energy_cost.cost==(legacy?29:6));
  initialize(&a);assert(special_defaults(&a,"special2")==ANI_SPECIAL2 && a.obor_energy_present && a.energy_cost.cost==0);
  initialize(&a);assert(special_defaults(&a,"jumpspecial")==ANI_JUMPSPECIAL && a.obor_energy_present && a.energy_cost.cost==0);
  for(int disable=-4;disable<=5;++disable) {
   char value[16];snprintf(value,sizeof(value),"%d",disable);
   one(&a,&m,CMD_MODEL_MPCOST,"6","1",value,NULL,NULL);
   int expected=disable;
   if(!legacy)switch(disable) {
    case 1:expected|=TYPE_ENEMY|TYPE_NPC|TYPE_PLAYER;break;
    case 2:expected|=TYPE_ENEMY|TYPE_NPC;break;
    case 3:expected|=TYPE_NPC|TYPE_PLAYER;break;
    case 4:expected|=TYPE_ENEMY|TYPE_PLAYER;break;
   }
   assert(a.obor_energy_present && a.energy_cost.cost==6 && a.energy_cost.mponly==1 && a.energy_cost.disable==expected);
  }
  initialize(&a);one(&a,&m,CMD_MODEL_MPONLY,"2",NULL,NULL,NULL,NULL);
  assert(a.obor_energy_present && a.energy_cost.cost==0 && a.energy_cost.disable==0 && a.energy_cost.mponly==2);
  initialize(&a);a.numframes=10;
  one(&a,&m,CMD_MODEL_JUMPFRAME,"this","5","2","3","model");
  assert(a.obor_jump_present && a.jumpframe.frame==10 && a.jumpframe.ent==35);
  assert(a.jumpframe.velocity.x==2 && a.jumpframe.velocity.y==5 && a.jumpframe.velocity.z==3);
  one(&a,&m,CMD_MODEL_DIVE1,"4",NULL,NULL,NULL,NULL);
  assert(a.obor_jump_present && !a.subject_to_gravity && a.jumpframe.frame==0 && a.jumpframe.ent==-1);
  assert(a.jumpframe.velocity.x==4 && a.jumpframe.velocity.y==0 && a.jumpframe.velocity.z==0);
  initialize(&a);one(&a,&m,CMD_MODEL_LANDFRAME,"3","model",NULL,NULL,NULL);
  assert(a.obor_land_present && a.landframe.frame==3 && a.landframe.model_index==35);
  one(&a,&m,CMD_MODEL_LANDFRAME,"4",NULL,NULL,NULL,NULL);
  assert(a.landframe.frame==4 && a.landframe.model_index==(legacy?-1:35));
  initialize(&a);one(&a,&m,CMD_MODEL_DROPFRAME,"2","model",NULL,NULL,NULL);
  assert(a.obor_drop_present && a.dropframe.frame==2 && a.dropframe.model_index==(legacy?0:35));
  for(int condition=0;condition<=6;++condition) {
   char value[16];snprintf(value,sizeof(value),"%d",condition);
   initialize(&a);one(&a,&m,CMD_MODEL_FOLLOWCOND,value,NULL,NULL,NULL,NULL);
   if(legacy)assert((int)a.followup.condition==condition);
   else {
    const int modes[]={FOLLOW_CONDITION_ANY,FOLLOW_CONDITION_ANY,FOLLOW_CONDITION_HOSTILE_TARGET_TRUE,
     FOLLOW_CONDITION_HOSTILE_TARGET_TRUE|FOLLOW_CONDITION_BLOCK_FALSE|FOLLOW_CONDITION_LETHAL_FALSE,
     FOLLOW_CONDITION_HOSTILE_TARGET_TRUE|FOLLOW_CONDITION_BLOCK_FALSE|FOLLOW_CONDITION_GRAB_TRUE|FOLLOW_CONDITION_LETHAL_FALSE,
     FOLLOW_CONDITION_HOSTILE_TARGET_TRUE|FOLLOW_CONDITION_BLOCK_TRUE|FOLLOW_CONDITION_LETHAL_FALSE,FOLLOW_CONDITION_ANY};
    assert((int)a.followup.condition==modes[condition]);
   }
   one(&a,&m,CMD_MODEL_COUNTERRANGE,"1","5",value,"1",NULL);
   assert(a.obor_counter_present && a.counter_action.frame.min==1 && a.counter_action.frame.max==5 && a.counter_action.damaged==1);
   if(legacy)assert((int)a.counter_action.condition==condition);
   else {
    const int modes[]={COUNTER_ACTION_CONDITION_DAMAGE_LETHAL_FALSE,COUNTER_ACTION_CONDITION_DAMAGE_LETHAL_FALSE,
     COUNTER_ACTION_CONDITION_DAMAGE_LETHAL_FALSE|COUNTER_ACTION_CONDITION_HOSTILE_TARGET_TRUE,
     COUNTER_ACTION_CONDITION_BACK_TRUE|COUNTER_ACTION_CONDITION_BLOCK_TRUE|COUNTER_ACTION_CONDITION_DAMAGE_LETHAL_FALSE|COUNTER_ACTION_CONDITION_FREEZE_FALSE|COUNTER_ACTION_CONDITION_HOSTILE_TARGET_TRUE,
     FOLLOW_CONDITION_ANY,COUNTER_ACTION_CONDITION_DAMAGE_LETHAL_FALSE,COUNTER_ACTION_CONDITION_DAMAGE_LETHAL_FALSE};
    assert((int)a.counter_action.condition==modes[condition]);
   }
  }
  initialize(&a);one(&a,&m,CMD_MODEL_PROJECTILE_POSITION_X,"7",NULL,NULL,NULL,NULL);
  assert(a.obor_projectile_position_explicit && a.projectile.position.x==7);
  one(&a,&m,CMD_MODEL_DEFENSE,"normal11","2",NULL,NULL,NULL);
  assert(defenses[24].factor==2); /* Canonical slot for original normal11. */
  one(&a,&m,CMD_MODEL_DEFENSE,"SUB_ENTITY_PARENT_KILL","3",NULL,NULL,NULL);
  assert(defenses[ATK_SUB_ENTITY_PARENT_KILL].factor==3);
  one(&a,&m,CMD_MODEL_OFFENSE,"SUB_ENTITY_UNSUMMON","4",NULL,NULL,NULL);
  assert(offense[ATK_SUB_ENTITY_UNSUMMON]==4);
  const char *words[]={"enemy","player","obstacle","shot","npc","ground","panel","item","none","4096"};
  const int values[]={TYPE_ENEMY,TYPE_PLAYER,TYPE_OBSTACLE,TYPE_SHOT,TYPE_NPC};
  for(int i=0;i<10;++i) {
   ArgList args={0};args.count=2;args.args[0]="command";args.args[1]=(char *)words[i];
   int expected=i<5?values[i]:legacy?(i==9?4096:0):i==6?TYPE_PLAYER:i==7?TYPE_ITEM:i==8?TYPE_NONE:TYPE_UNKNOWN;
   m.ground=0;lcmHandleCommandHostile(&args,&m);assert(m.hostile==expected);
   lcmHandleCommandProjectilehit(&args,&m);assert(m.projectilehit==expected);
   lcmHandleCommandCandamage(&args,&m);assert(m.candamage==expected && m.ground==(legacy&&i==5));
  }
 }
}
