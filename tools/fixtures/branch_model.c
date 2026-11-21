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
s_collision_attack emptyattack;
void *checkAlloc(void *pointer,size_t size,const char *function,const char *file,int line) {
 (void)size;(void)function;(void)file;(void)line;
 assert(pointer);return pointer;
}
void borShutdown(int status,char *message,...) {(void)status;(void)message;abort();}
int getValidInt(char *text,char *file,char *cmd) { (void)file;(void)cmd;return atoi(text); }
float getValidFloat(char *text,char *file,char *cmd) { (void)file;(void)cmd;return strtof(text,NULL); }
int get_cached_model_index(char *name) { assert(!strcmp(name,"model"));return 35; }
void writeToLogFile(const char *format,...) {(void)format;}
TYPE_METHODS
static void initialize(s_anim *newanim, const s_model *newchar) {
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
 const unsigned profiles[]={6997,7039,7086,7091,7123,7142};
 for(unsigned p=0;p<sizeof(profiles)/sizeof(profiles[0]);++p) {
  obor_profile_build=profiles[p];int legacy=obor_profile_build!=7142;s_anim a;s_model m={0};
  s_defense defenses[128]={0};float offense[128]={0};m.defense=defenses;m.offense_factors=offense;
  m.type=TYPE_PLAYER;m.jumpheight=12;
  initialize(&a,&m);
  assert(!a.obor_energy_present && !a.obor_counter_present && !a.obor_drop_present && !a.obor_jump_present && !a.obor_land_present);
  int minimum=(obor_profile_build==6997||obor_profile_build==7039)?T_MIN_BASEMAP:0;
  assert(a.range.y.min==minimum && a.range.base.min==minimum);
  assert(a.range.y.max==240 && a.range.base.max==240);
  assert(a.subject_to_gravity && a.charge_time==2 && a.projectile.position.x==0 && a.projectile.position.z==0);
  assert(a.projectile.position.y==(legacy?0:70));
  assert(a.energy_cost.cost==0 && a.energy_cost.disable==0 && a.energy_cost.mponly==COST_TYPE_MP_THEN_HP);
  assert(special_defaults(&a,"special")==ANI_SPECIAL);
  assert(a.obor_energy_present && a.energy_cost.cost==6);
  a.energy_cost.cost=29;
  special_defaults(&a,"special");assert(a.energy_cost.cost==(legacy?29:6));
  initialize(&a,&m);assert(special_defaults(&a,"special2")==ANI_SPECIAL2 && a.obor_energy_present && a.energy_cost.cost==0);
  initialize(&a,&m);assert(special_defaults(&a,"jumpspecial")==ANI_JUMPSPECIAL && a.obor_energy_present && a.energy_cost.cost==0);
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
  initialize(&a,&m);one(&a,&m,CMD_MODEL_MPONLY,"2",NULL,NULL,NULL,NULL);
  assert(a.obor_energy_present && a.energy_cost.cost==0 && a.energy_cost.disable==0 && a.energy_cost.mponly==2);
  initialize(&a,&m);a.numframes=10;
  one(&a,&m,CMD_MODEL_JUMPFRAME,"this","5","2","3","model");
  assert(a.obor_jump_present && a.jumpframe.frame==10 && a.jumpframe.ent==35);
  assert(a.jumpframe.velocity.x==2 && a.jumpframe.velocity.y==5 && a.jumpframe.velocity.z==3);
  one(&a,&m,CMD_MODEL_DIVE1,"4",NULL,NULL,NULL,NULL);
  assert(a.obor_jump_present && !a.subject_to_gravity && a.jumpframe.frame==0 && a.jumpframe.ent==-1);
  assert(a.jumpframe.velocity.x==4 && a.jumpframe.velocity.y==0 && a.jumpframe.velocity.z==0);
  one(&a,&m,CMD_MODEL_DIVE,"3","7",NULL,NULL,NULL);
  assert(a.obor_jump_present && !a.subject_to_gravity && a.jumpframe.frame==0 && a.jumpframe.ent==-1);
  assert(a.jumpframe.velocity.x==3 && a.jumpframe.velocity.y==-7 && a.jumpframe.velocity.z==0);
  one(&a,&m,CMD_MODEL_DIVE2,"5",NULL,NULL,NULL,NULL);
  assert(a.obor_jump_present && !a.subject_to_gravity && a.jumpframe.frame==0 && a.jumpframe.ent==-1);
  assert(a.jumpframe.velocity.x==0 && a.jumpframe.velocity.y==-5 && a.jumpframe.velocity.z==0);
  const int jump_types[]={TYPE_PLAYER,TYPE_ENEMY,TYPE_NPC,TYPE_ITEM};
  for(size_t type=0;type<sizeof(jump_types)/sizeof(jump_types[0]);++type) {
   m.type=jump_types[type];
   initialize(&a,&m);
   one(&a,&m,CMD_MODEL_JUMPFRAME,"2","0",NULL,NULL,NULL);
   assert(a.obor_jump_present && a.jumpframe.frame==2 && a.jumpframe.ent==-1);
   assert(a.jumpframe.velocity.y==(m.type==TYPE_PLAYER?6:12));
   assert(a.jumpframe.velocity.x==(m.type==TYPE_PLAYER?2:0) && a.jumpframe.velocity.z==0);
   one(&a,&m,CMD_MODEL_JUMPFRAME,"3","4",NULL,NULL,NULL);
   assert(a.jumpframe.frame==3 && a.jumpframe.ent==-1 && a.jumpframe.velocity.y==4);
   const float expected=m.type==TYPE_ENEMY||m.type==TYPE_NPC?(float)1.3:0;
   assert(a.jumpframe.velocity.x==expected && a.jumpframe.velocity.z==0);
  }
  m.type=TYPE_PLAYER;
  initialize(&a,&m);one(&a,&m,CMD_MODEL_LANDFRAME,"3","model",NULL,NULL,NULL);
  assert(a.obor_land_present && a.landframe.frame==3 && a.landframe.model_index==35);
  one(&a,&m,CMD_MODEL_LANDFRAME,"4",NULL,NULL,NULL,NULL);
  assert(a.landframe.frame==4 && a.landframe.model_index==(legacy?-1:35));
  initialize(&a,&m);one(&a,&m,CMD_MODEL_DROPFRAME,"2","model",NULL,NULL,NULL);
  assert(a.obor_drop_present && a.dropframe.frame==2 && a.dropframe.model_index==(legacy?0:35));
  for(int condition=0;condition<=6;++condition) {
   char value[16];snprintf(value,sizeof(value),"%d",condition);
   initialize(&a,&m);one(&a,&m,CMD_MODEL_FOLLOWCOND,value,NULL,NULL,NULL,NULL);
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
  initialize(&a,&m);one(&a,&m,CMD_MODEL_PROJECTILE_POSITION_X,"7",NULL,NULL,NULL,NULL);
  assert(a.obor_projectile_position_explicit && a.projectile.position.x==7);
  char timeover[16];
  snprintf(timeover,sizeof(timeover),"%d",legacy?21:23);
  ArgList smartbomb={0};smartbomb.count=3;
  smartbomb.args[0]="smartbomb";smartbomb.args[1]="25";smartbomb.args[2]=timeover;
  lcmHandleCommandSmartbomb(&smartbomb,&m,"synthetic");
  assert(m.smartbomb && m.smartbomb->attack_force==25 && m.smartbomb->attack_type==ATK_TIMEOVER);
  assert(m.smartbomb->attack_drop==1 && m.smartbomb->dropv.y==default_model_dropv.y);
  free(m.smartbomb);m.smartbomb=NULL;
  one(&a,&m,CMD_MODEL_DEFENSE,"normal11","2",NULL,NULL,NULL);
  assert(defenses[24].factor==2); /* Canonical slot for original normal11. */
  const int early=profiles[p]==6997||profiles[p]==7039||profiles[p]==7091;
  const char *subentity_names[]={"SUB_ENTITY_PARENT_KILL","SUB_ENTITY_UNSUMMON"};
  const int subentity_slots[]={ATK_SUB_ENTITY_PARENT_KILL,ATK_SUB_ENTITY_UNSUMMON};
  for(size_t i=0;i<sizeof(subentity_slots)/sizeof(subentity_slots[0]);++i) {
   one(&a,&m,CMD_MODEL_DEFENSE,(char *)subentity_names[i],"3",NULL,NULL,NULL);
   one(&a,&m,CMD_MODEL_OFFENSE,(char *)subentity_names[i],"4",NULL,NULL,NULL);
   assert(defenses[subentity_slots[i]].factor==(early?0:3));
   assert(offense[subentity_slots[i]]==(early?0:4));
  }
  one(&a,&m,CMD_MODEL_DEFENSE,"ALL","5",NULL,NULL,NULL);
  one(&a,&m,CMD_MODEL_OFFENSE,"ALL","6",NULL,NULL,NULL);
  assert(defenses[ATK_NORMAL].factor==5 && offense[ATK_NORMAL]==6);
  for(size_t i=0;i<sizeof(subentity_slots)/sizeof(subentity_slots[0]);++i) {
   assert(defenses[subentity_slots[i]].factor==(early?0:3));
   assert(offense[subentity_slots[i]]==(early?0:4));
  }
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
