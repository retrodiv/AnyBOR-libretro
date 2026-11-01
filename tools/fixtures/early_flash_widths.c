/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#undef exit
#undef time
#undef pause
#undef shutdown
#undef printf
#undef GET_INT_ARG
uint32_t obor_profile_build;
s_spawn_entry spawnentry;
CHAR *StrCache_Get(int index) {assert(!index);return "dying";}
void StrCache_Collect(int index) {assert(!index);}
int StrCache_Pop(void) {abort();}
@PIECES@
typedef struct {int direct[2],spawn[2],pipeline[2],script[5],script_entity[2];} expected;
typedef struct {
 const char *name;int low,critical,nargs,invalid,dying,named;
 expected results[4];
} scenario;
static const scenario cases[]={@CASES@};
@ORIGINALS@
static void level_command(s_spawn_entry *result,const int *input) {
 s_spawn_entry next=*result;
#define GET_INT_ARG(n) input[n]
 switch(0) {case 0: @LEVEL@}
#undef GET_INT_ARG
 *result=next;
}
static void entity_from_entry(entity *e,s_spawn_entry *props) {@COPY@}
static LONG visible_threshold(entity *ent,int critical) {
 ScriptVariant value={.vt=VT_EMPTY},*out=&value,**pretvar=&out;
 switch(critical?_gep_maps_dying_critical:_gep_maps_dying_low) {@GETTERS@ default:abort();}
 assert(out==&value && value.vt==VT_INTEGER);return value.lVal;
}
static void require_value(const scenario *c,unsigned revision,const char *phase,int field,int got,int want) {
 if(got!=want) {fprintf(stderr,"%s revision=%u %s field=%d got=%d expected=%d\n",c->name,revision,phase,field,got,want);abort();}
}
static void check(unsigned revision,unsigned era) {
 obor_profile_build=revision;
 for(unsigned i=0;i<sizeof(cases)/sizeof(cases[0]);i++) {
  const scenario *c=&cases[i];const expected *want=&c->results[era];
  entity actor;memset(&actor,0,sizeof(actor));
  actor.per1=obor_flash_entity_value(c->low,revision,0);actor.per2=obor_flash_entity_value(c->critical,revision,1);
  require_value(c,revision,"direct",0,(int)visible_threshold(&actor,0),want->direct[0]);
  require_value(c,revision,"direct",1,(int)visible_threshold(&actor,1),want->direct[1]);
  s_spawn_entry entry;memset(&entry,0,sizeof(entry));int input[]={0,c->dying,c->low,c->critical};
  level_command(&entry,input);require_value(c,revision,"level",0,entry.per1,want->spawn[0]);require_value(c,revision,"level",1,entry.per2,want->spawn[1]);
  actor.per1=7;actor.per2=8;entity_from_entry(&actor,&entry);
  require_value(c,revision,"pipeline",0,(int)visible_threshold(&actor,0),want->pipeline[0]);
  require_value(c,revision,"pipeline",1,(int)visible_threshold(&actor,1),want->pipeline[1]);
  memset(&spawnentry,0,sizeof(spawnentry));spawnentry.per1=7;spawnentry.per2=8;
  ScriptVariant values[4],result={.vt=VT_EMPTY},*out=&result,*args[4];memset(values,0,sizeof(values));
  for(int k=0;k<4;k++) {args[k]=&values[k];values[k].vt=VT_INTEGER;}
  if(c->named) {values[0].vt=VT_STR;values[0].strVal=0;} else values[0].lVal=_sse_dying;
  values[1].lVal=c->dying;values[2].lVal=c->low;values[3].lVal=c->critical;
  if(c->invalid) values[c->invalid].vt=VT_EMPTY;
  HRESULT status=openbor_setspawnentry(args,&out,c->nargs);
  int observed[]={spawnentry.per1,spawnentry.per2,SUCCEEDED(status),out?(int)out->vt:-1,out?(int)out->lVal:-1};
  for(int k=0;k<5;k++) require_value(c,revision,"script",k,observed[k],want->script[k]);
  actor.per1=7;actor.per2=8;entity_from_entry(&actor,&spawnentry);
  require_value(c,revision,"script-entity",0,(int)visible_threshold(&actor,0),want->script_entity[0]);
  require_value(c,revision,"script-entity",1,(int)visible_threshold(&actor,1),want->script_entity[1]);
 }
}
int main(void) {
 assert(sizeof(int)==4 && CHAR_BIT==8);
 @ORIGINAL_CHECKS@
 @CHECKS@
 printf("flash_layout=%zu,%zu,%zu,%zu,%zu\n",sizeof(entity),sizeof(s_spawn_entry),sizeof(s_savedata),sizeof(s_savelevel),sizeof(s_savescore));
 puts("early_flash_widths=1");return 0;
}
