/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <ctype.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "commands.h"
#include "ScriptVariant.h"
#undef printf
uint32_t obor_profile_build;
static unsigned messages;
void writeToLogFile(const char *format,...){assert(format);messages++;}
void borShutdown(int status,char *format,...){(void)status;(void)format;abort();}
void borExit(int status){(void)status;abort();}
void exitIfFalse(int value,const char *c,const char *n,const char *f,int l){(void)c;(void)n;(void)f;(void)l;assert(value);}
void abortIfFalse(int v,const char *c,const char *n,const char *f,int l){exitIfFalse(v,c,n,f,l);}
void obor_port_assert(int v,const char *c,const char *n,const char *f,int l){exitIfFalse(v,c,n,f,l);}
@LOWER@
@RECORD@
@EMPTY@
@DESCRIPTOR@
@ENUM@
@NAMESPACES@
enum {_gep_attack=1};
@SEARCH@
@MACRO@
static void map_attack(ScriptVariant **varlist,int paramCount){
 char *propname;int prop,obor_property=_gep_attack;if(paramCount<3)return;@MAPPING@
}
typedef struct {int numframes;s_attack **attacks;} animation;
typedef struct entity {
 struct {int health;struct {int maximum,current;} guardpoints;
         float offense_factors[4],defense_factors[4];animation **animation;} modeldata;
 int health,damage_on_landing,projectile,invincible,lifespancountdown;float a;
} entity;
static int validanim(entity *ent,int index){return index==0 && ent->modeldata.animation[0]!=NULL;}
static HRESULT query(entity *ent,ScriptVariant **varlist,ScriptVariant **pretvar,int paramCount){
 ScriptVariant *arg;LONG ltemp;int i,tempint;s_attack *attack;
 ScriptVariant_Clear(*pretvar);map_attack(varlist,paramCount);
 switch(_gep_attack){case _gep_attack:@QUERY@}
 return S_OK;
}
static s_attack attack,bomb,*pattack;
static struct {s_attack *smartbomb;} model,*newchar=&model;
static void *newanim;
static int requested;
#define GET_INT_ARG(n) ((void)(n),requested)
static void load_nokill(modelCommands command){switch(command){case CMD_MODEL_NOKILL:@SETTER@default:abort();}}
#undef GET_INT_ARG
static entity *self;
static int max_attack_types=4,damage_calls,death_calls,expected_effective,expected_before,expected_after;
@PIT@
static void check_callback(entity *who,entity *other,int force,int drop,int type,int block,int guard,int juggle,int pause){
 assert(who==self && other && force==expected_effective);
 assert(drop==attack.attack_drop && type==attack.attack_type && block==attack.no_block);
 assert(guard==attack.guardcost && juggle==attack.jugglecost && pause==attack.pause_add);
}
static void execute_takedamage_script(entity *who,entity *other,int force,int drop,int type,int block,int guard,int juggle,int pause){
 check_callback(who,other,force,drop,type,block,guard,juggle,pause);assert(who->health==expected_before);damage_calls++;
}
static void execute_ondeath_script(entity *who,entity *other,int force,int drop,int type,int block,int guard,int juggle,int pause){
 check_callback(who,other,force,drop,type,block,guard,juggle,pause);assert(who->health==expected_after);death_calls++;
}
@DAMAGE@
typedef struct {const char *name;int kind;LONG integer;double decimal;} property_case;
@ARRAYS@
typedef struct {int health,maximum,force,flag,invincible,pit,expired,broken_guard;
                float offense,defense;int projectile,landing_self,effective_force,old[3],modern[3];} damage_case;
static const damage_case damage_cases[]={@DAMAGE_CASES@};
static void initialize(void){attack=emptyattack;@INITIALIZE@}
static void check(unsigned revision,int modern,const property_case *properties,size_t count){
 obor_profile_build=revision;assert(emptyattack.no_kill==0 && emptyattack.no_pain==0);
 assert(emptyattack.no_flash==0 && emptyattack.hitsound==-1 && emptyattack.hitflash==-1);
 List *commands=createModelCommandList();assert(commands);
 char command[]="NoKiLl",neighbor[]="noreflect";
 assert(getModelCommand(commands,command)==(modern?CMD_MODEL_NOKILL:0));assert(!strcmp(command,"nokill"));
 assert(getModelCommand(commands,neighbor)==CMD_MODEL_NOREFLECT);
 const int requests[]={-128,-1,0,1,2,127,128,255,256,257,65536};
 for(int animated=0;animated<2;animated++)for(int smart=0;smart<2;smart++)for(unsigned n=0;n<sizeof(requests)/sizeof(*requests);n++){
  initialize();bomb=attack;model.smartbomb=smart?&bomb:NULL;newanim=animated?&model:NULL;requested=requests[n];
  s_attack a=attack,b=bomb;
  if(modern){
   load_nokill(CMD_MODEL_NOKILL);int narrowed=requested&255;if(narrowed>=128)narrowed-=256;
   if(!animated && smart)b.no_kill=narrowed;else a.no_kill=narrowed;
  }
  assert(!memcmp(&a,&attack,sizeof(a)) && !memcmp(&b,&bomb,sizeof(b)));
 }
 freeCommandList(commands);initialize();
 s_attack *frames[]={&attack};animation anim={1,frames};animation *animations[]={&anim};
 entity ent={0};ent.modeldata.animation=animations;
 ScriptVariant args[7]={0},result={0};ScriptVariant *vars[7],*returned=&result;
 for(int i=0;i<7;i++)vars[i]=args+i;
 args[0].vt=VT_PTR;args[0].ptrVal=&ent;args[1].vt=VT_INTEGER;args[1].lVal=_gep_attack;
 for(int i=3;i<7;i++){args[i].vt=VT_INTEGER;args[i].lVal=0;}
 for(size_t i=0;i<count;i++)for(int named=0;named<2;named++){
  ScriptVariant_Clear(&args[2]);
  if(named){ScriptVariant_ChangeType(&args[2],VT_STR);strcpy(StrCache_Get(args[2].strVal),properties[i].name);}
  else {args[2].vt=VT_INTEGER;args[2].lVal=(LONG)i;}
  args[6].lVal=!strcmp(properties[i].name,"coords")?4:!strcmp(properties[i].name,"dropv")?2:0;
  unsigned prior=messages;map_attack(vars,7);map_attack(vars,7);
  assert(args[2].vt==VT_INTEGER && args[2].lVal==(LONG)i && messages==prior);
  HRESULT status=query(&ent,vars,&returned,7);assert(returned==&result);
  if(!properties[i].kind){assert(status==E_FAIL && result.vt==VT_EMPTY);}
  else {
   assert(status==S_OK && (int)result.vt==properties[i].kind);
   if(result.vt==VT_INTEGER)assert(result.lVal==properties[i].integer);
   if(result.vt==VT_DECIMAL)assert(result.dblVal==properties[i].decimal);
   if(result.vt==VT_PTR)assert(result.ptrVal==attack.staydown);
  }
 }
 const LONG outside[]={-1,(LONG)count,INT_MAX};
 for(unsigned i=0;i<sizeof(outside)/sizeof(*outside);i++){
  args[2].vt=VT_INTEGER;args[2].lVal=outside[i];assert(query(&ent,vars,&returned,7)==E_FAIL && result.vt==VT_EMPTY);
 }
 if(sizeof(LONG)>4){uintmax_t wide=(uintmax_t)UINT_MAX+27;
  args[2].lVal=(LONG)wide;assert(query(&ent,vars,&returned,7)==E_FAIL && result.vt==VT_EMPTY);}
 if(!modern){
  ScriptVariant_ChangeType(&args[2],VT_STR);strcpy(StrCache_Get(args[2].strVal),"nokill");
  assert(query(&ent,vars,&returned,7)==E_FAIL && result.vt==VT_EMPTY);
 }
 ScriptVariant_Clear(&args[2]);ScriptVariant_Clear(&result);StrCache_Clear();
 for(unsigned i=0;i<sizeof(damage_cases)/sizeof(*damage_cases);i++){
  const damage_case *c=damage_cases+i;initialize();entity victim={0},attacker={0};self=&victim;
  victim.health=c->health;victim.modeldata.health=c->maximum;victim.invincible=c->invincible;
  victim.a=c->pit?PIT_DEPTH-1:0;victim.lifespancountdown=c->expired?-1:0;
  victim.modeldata.guardpoints.maximum=c->broken_guard?5:0;victim.modeldata.guardpoints.current=0;
  for(int t=0;t<4;t++){victim.modeldata.offense_factors[t]=c->offense;victim.modeldata.defense_factors[t]=c->defense;attacker.modeldata.offense_factors[t]=c->offense;}
  victim.damage_on_landing=c->landing_self;victim.projectile=attacker.projectile=c->projectile;
  attack.attack_force=c->force;attack.no_kill=c->flag;attack.attack_type=1;
  const int *expected=modern?c->modern:c->old;
  expected_effective=c->effective_force;expected_before=expected[0];expected_after=expected[1];damage_calls=death_calls=0;
  checkdamage(c->landing_self?self:&attacker,&attack);
  assert(victim.health==expected_after && damage_calls==1 && death_calls==expected[2]);
 }
}
int main(void){@CHECKS@puts("early_nokill=1");return 0;}
