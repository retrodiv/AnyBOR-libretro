/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#include "commands.h"
#undef exit
#undef time
#undef pause
#undef shutdown
#undef printf
uint32_t obor_profile_build;
unsigned int time;
static char diagnostic[2048];
static int warnings,log_warnings,animation_calls,animation_value,reset_value;
static int report(const char *format,...) {
 va_list ap;va_start(ap,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,ap);va_end(ap);
 assert(n>=0 && n<(int)sizeof(diagnostic));warnings++;return n;
}
void writeToLogFile(const char *format,...) {(void)format;log_warnings++;}
void ent_set_anim(entity *ent,int animation,int reset) {
 assert(ent);animation_calls++;animation_value=animation;reset_value=reset;
}
static void previous_action(void) {abort();}
#define printf report
@MACROS@
@PIECES@
#undef printf
typedef struct {const char *text;float value[2];int warnings[2];} number_case;
static const number_case numbers[]={@NUMBERS@};
typedef struct {float values[7];int warnings,log_warnings;} defense_result;
typedef struct {const char *line;int targets[20],target_count;defense_result result[2];} defense_case;
static const defense_case defenses[]={@DEFENSE@};
typedef struct {int input[3],prior[3],health[4],expected[2][3];} copy_case;
static const copy_case copies[]={@COPY@};
typedef struct {int nargs,handle,types[3];double values[3];unsigned now;
 int success,mutated,called,animation,reset;unsigned stall;} idle_case;
static const idle_case idles[]={@IDLE@};
static void model_line(s_model *newchar,const char *line) {
 ArgList arglist;char input[MAX_ARG_LEN+1],argbuf[MAX_ARG_LEN+1];
 char filename[]="fixture.txt",command[]="defense",*value;int tempInt,i,max_attack_types=20;
 assert(strlen(line)<=MAX_ARG_LEN);strcpy(input,line);ParseArgs(&arglist,input,argbuf);
 switch(CMD_MODEL_DEFENSE) {@DEFENSE_CASE@ default:abort();}
}
static void same_float(float actual,float expected) {assert(!memcmp(&actual,&expected,sizeof(actual)));}
static void check(unsigned revision,int copy_zero,int percent,const char *idle_diagnostic) {
 obor_profile_build=revision;
 for(unsigned n=0;n<sizeof(numbers)/sizeof(numbers[0]);n++) {
  const number_case *c=&numbers[n];warnings=0;diagnostic[0]=0;
  float actual=getValidFloat((char*)c->text,"fixture.txt","number");same_float(actual,c->value[percent]);
  assert(warnings==c->warnings[percent]);
  if(warnings) {
   char expected[2048];snprintf(expected,sizeof(expected),"WARNING: %s tries to load a nonnumeric value at %s, where a number is expected!\nerroneus string: %s\n","fixture.txt","number",c->text);
   assert(!strcmp(diagnostic,expected));
  }
 }
 for(unsigned n=0;n<sizeof(defenses)/sizeof(defenses[0]);n++) {
  const defense_case *c=&defenses[n];const defense_result *want=&c->result[percent];
  s_model model;memset(&model,0,sizeof(model));float storage[7][20];
  model.defense_factors=storage[0];model.defense_pain=storage[1];model.defense_knockdown=storage[2];
  model.defense_blockpower=storage[3];model.defense_blockthreshold=storage[4];
  model.defense_blockratio=storage[5];model.defense_blocktype=storage[6];
  for(int f=0;f<7;f++) for(int i=0;i<20;i++) storage[f][i]=(float)(101+f);
  warnings=log_warnings=0;model_line(&model,c->line);
  assert(warnings==want->warnings && log_warnings==want->log_warnings);
  for(int i=0;i<20;i++) {
   int selected=0;for(int j=0;j<c->target_count;j++) selected|=i==c->targets[j];
   for(int f=0;f<7;f++) same_float(storage[f][i],selected?want->values[f]:(float)(101+f));
  }
 }
 for(unsigned n=0;n<sizeof(copies)/sizeof(copies[0]);n++) {
  const copy_case *c=&copies[n];entity object,expected;s_model prior;
  memset(&object,0,sizeof(object));memset(&prior,0,sizeof(prior));
  object.modeldata.antigrab=c->input[0];object.modeldata.grabforce=c->input[1];object.modeldata.paingrab=c->input[2];
  prior.antigrab=c->prior[0];prior.grabforce=c->prior[1];prior.paingrab=c->prior[2];
  object.health=c->health[0];object.mp=c->health[1];object.modeldata.health=c->health[2];object.modeldata.mp=c->health[3];
  memcpy(&expected,&object,sizeof(expected));
  const int *values=c->expected[copy_zero?0:1];expected.modeldata.antigrab=values[0];expected.modeldata.grabforce=values[1];expected.modeldata.paingrab=values[2];
  if(expected.health>expected.modeldata.health) expected.health=expected.modeldata.health;
  if(expected.mp>expected.modeldata.mp) expected.mp=expected.modeldata.mp;
  ent_copy_uninit(&object,&prior);assert(!memcmp(&object,&expected,sizeof(object)));
 }
 for(unsigned n=0;n<sizeof(idles)/sizeof(idles[0]);n++) {
  const idle_case *c=&idles[n];entity object,expected;ScriptVariant values[5],result={.vt=VT_EMPTY},*out=&result,*args[5];
  memset(&object,0,sizeof(object));memset(values,0,sizeof(values));
  object.takeaction=previous_action;object.attacking=object.drop=object.falling=object.inpain=object.blocking=object.nograb=1;
  object.stalltime=73;object.health=53;memcpy(&expected,&object,sizeof(expected));
  for(int i=0;i<5;i++) {args[i]=&values[i];values[i].vt=VT_INTEGER;}
  values[0].vt=c->handle==1?VT_EMPTY:c->handle==2?VT_INTEGER:VT_PTR;values[0].ptrVal=c->handle==3?NULL:&object;
  for(int i=0;i<3;i++) {
   if(c->types[i]==1) {values[i+1].vt=VT_DECIMAL;values[i+1].dblVal=c->values[i];}
   else if(c->types[i]==2) values[i+1].vt=VT_PTR;
   else values[i+1].lVal=(LONG)c->values[i];
  }
  time=c->now;warnings=animation_calls=0;animation_value=reset_value=-99;diagnostic[0]=0;
  HRESULT status=openbor_setidle(args,&out,c->nargs);
  assert(status==(c->success?S_OK:E_FAIL) && !out);
  assert(animation_calls==c->called && animation_value==c->animation && reset_value==c->reset);
  if(c->mutated) {
   expected.takeaction=NULL;expected.attacking=expected.drop=expected.falling=expected.inpain=expected.blocking=expected.nograb=0;expected.idling=1;
  }
  expected.stalltime=c->stall;assert(!memcmp(&object,&expected,sizeof(object)));
  assert(warnings==!c->success);if(warnings) assert(!strcmp(diagnostic,idle_diagnostic));
 }
}
int main(void) {@CHECKS@ puts("early_model_defaults=1");return 0;}
