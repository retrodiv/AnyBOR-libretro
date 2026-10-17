/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */

#include <stdint.h>
#include <limits.h>
#include <stdarg.h>
#include <string.h>
#include "source/openborscript/constants.c"
#undef assert
#define assert(x) ((x)?(void)0:(fprintf(stderr,"assertion line %d: %s\n",__LINE__,#x),__builtin_trap()))
uint32_t obor_profile_build;
GLOBALS
static const char *text;
char *StrCache_Get(int n) { (void)n;return (char *)text; }
void ScriptVariant_Init(ScriptVariant *v) { memset(v,0,sizeof(*v)); }
void ScriptVariant_Clear(ScriptVariant *v) { memset(v,0,sizeof(*v)); }
void ScriptVariant_ChangeType(ScriptVariant *v,VARTYPE t) { ScriptVariant_Clear(v);v->vt=t; }
void ScriptVariant_Copy(ScriptVariant *v,ScriptVariant *other) { *v=*other; }
void ScriptVariant_ToString(ScriptVariant *v,char *out) { (void)v;strcpy(out,"test"); }
void writeToLogFile(const char *s,...) { (void)s; }
static void check(const char *name,int found,int value) {
 text=name;ScriptVariant var={.vt=VT_STR},*args[]={&var};
 assert(mapstrings_transconst(args,1)==found);
 assert(var.vt==(found?VT_INTEGER:VT_STR));
 if(found)assert(var.lVal==value);
}
int main(void) {
 for(unsigned profile=7086;profile<=7142;++profile) {
  obor_profile_build=profile;int legacy=(profile==7086||profile==7123);
  for(int id=-1;id<=100;++id) {
   int physical=legacy&&id>=21?id+2:id;
   assert(obor_attack_from_native(id)==physical && obor_attack_to_native(physical)==id);
   physical=legacy&&id>=SPAWN_TYPE_DUST_DROP?id+1:id;
   assert(obor_spawn_type_from_native(id)==physical && obor_spawn_type_to_native(physical)==id);
  }
  assert(obor_attack_from_native(INT_MAX)==(legacy?-1:INT_MAX));
  assert(obor_attack_from_native(INT_MAX-1)==(legacy?-1:INT_MAX-1));
  assert(obor_spawn_type_from_native(INT_MAX)==(legacy?-1:INT_MAX));
  assert(obor_attack_to_native(ATK_SUB_ENTITY_PARENT_KILL)==(legacy?-2:ATK_SUB_ENTITY_PARENT_KILL));
  assert(obor_attack_to_native(ATK_SUB_ENTITY_UNSUMMON)==(legacy?-3:ATK_SUB_ENTITY_UNSUMMON));
  assert(obor_attack_from_native(legacy?-2:21)==ATK_SUB_ENTITY_PARENT_KILL);
  assert(obor_attack_from_native(legacy?-3:22)==ATK_SUB_ENTITY_UNSUMMON);
  check("ATK_TIMEOVER",1,legacy?21:23);
  check("ATK_SUB_ENTITY_PARENT_KILL",1,legacy?-2:21);
  check("ATK_SUB_ENTITY_UNSUMMON",1,legacy?-3:22);
  check("ATK_NORMAL11",1,legacy?22:24);
  check("ATK_NORMAL12",1,legacy?23:25);
  check("SPAWN_TYPE_DUST_FALL",1,legacy?4:5);
  check("SPAWN_TYPE_WEAPON",1,legacy?16:17);
  check("TYPE_MAX",1,legacy?TYPE_PANEL:TYPE_UNKNOWN);
  check("BIND_OVERRIDE_LANDFRAME",legacy,2);
  check("BIND_OVERRIDE_FRAME_SET_LAND",1,legacy?2:4);
  check("BIND_OVERRIDE_SPECIAL_AI",1,legacy?4:8);
  check("BIND_OVERRIDE_SPECIAL_PLAYER",1,legacy?8:16);
  check("ANI_PROP_ANIMHITS",legacy,0);
  check("ANI_PROP_NUMFRAMES",legacy,25);
  check("ANI_PROP_IGNOREATTACKID",0,0); /* Present enum, absent map upstream. */
  check("ANIMATION_BOUNCE_FACTOR_DEFAULT",1,4);
  check("FOLLOW_CONDITION_ANY",1,FOLLOW_CONDITION_ANY);
 }
}
