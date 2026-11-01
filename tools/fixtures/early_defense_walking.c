/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <ctype.h>
#include <float.h>
#include <limits.h>
#include <math.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#undef exit
#undef time
#undef kill
#undef pause
#undef shutdown
#undef printf
uint32_t obor_profile_build;
int max_attack_types=3;
static char diagnostic[4096];
static char *cache[8];
CHAR *StrCache_Get(int index) {assert(index>=0 && index<8 && cache[index]);return cache[index];}
void StrCache_Collect(int index) {assert(index>=0 && index<8);}
int StrCache_Pop(void) {abort();}
static int message(const char *format,...) {
 va_list args;va_start(args,format);int n=vsnprintf(diagnostic+strlen(diagnostic),sizeof(diagnostic)-strlen(diagnostic),format,args);va_end(args);assert(n>=0);return n;
}
#define printf message
@PIECES@
typedef struct {int ok,type;double value;int turning;const char *diagnostic;} expected;
typedef struct {
 const char *name;int family,root_name,nargs,attack_type;double attack;
 int option_type;double option;const char *subname;
 int null_attack,null_option,missing_array,fraction;
 expected results[3];
} scenario;
static const scenario cases[]={@CASES@};
static entity e;
static float values_by_property[7][4];
static void scalar(ScriptVariant *v,int type,double value,int index,const char *text) {
 v->vt=type;
 if(type==VT_STR) {cache[index]=(char*)text;v->strVal=index;}
 else if(type==VT_DECIMAL) v->dblVal=value;
 else v->lVal=(LONG)value;
}
static void check(unsigned revision,unsigned era,int defense_id,int getflag_id,int setflag_id) {
 assert(FLT_MANT_DIG==24);obor_profile_build=revision;
 for(unsigned i=0;i<sizeof(cases)/sizeof(cases[0]);i++) {
  const scenario *c=&cases[i];const expected *want=&c->results[era];
  memset(&e,0,sizeof(e));e.turning=1;
  for(int p=0;p<7;p++) for(int k=0;k<4;k++) values_by_property[p][k]=(float)(10*(p+1)+k+0.25);
  if(c->fraction) {values_by_property[4][0]=0.1f;values_by_property[4][2]=0.2f;}
#define ARRAY(p,field) e.modeldata.field=c->missing_array==p?NULL:values_by_property[p]
  ARRAY(0,defense_blockpower);ARRAY(1,defense_blockratio);ARRAY(2,defense_blockthreshold);ARRAY(3,defense_blocktype);
  ARRAY(4,defense_factors);ARRAY(5,defense_knockdown);ARRAY(6,defense_pain);
#undef ARRAY
  ScriptVariant values[5],result={.vt=VT_EMPTY},*out=&result,*args[5];
  memset(values,0,sizeof(values));
  for(int k=0;k<5;k++)args[k]=&values[k];
  values[0].vt=VT_PTR;values[0].ptrVal=&e;
  scalar(&values[1],c->root_name?VT_STR:VT_INTEGER,c->family==0?defense_id:c->family==1?getflag_id:setflag_id,1,c->family==0?"defense":"aiflag");
  if(!c->family) {
   scalar(&values[2],c->attack_type,c->attack,2,"invalid_attack");scalar(&values[3],c->option_type,c->option,3,c->subname);
   if(c->null_attack)args[2]=NULL;
   if(c->null_option)args[3]=NULL;
  } else {
   scalar(&values[2],c->option_type,c->option,2,c->subname);scalar(&values[3],VT_INTEGER,c->attack,3,"");
   if(c->null_option)args[3]=NULL;
  }
  unsigned char original[sizeof(e)];entity expected_entity;
  memcpy(&expected_entity,&e,sizeof(e));expected_entity.turning=want->turning;memcpy(original,&expected_entity,sizeof(e));
  diagnostic[0]=0;
  HRESULT status=c->family==2?openbor_changeentityproperty(args,&out,c->nargs):openbor_getentityproperty(args,&out,c->nargs);
  int type=out?(int)out->vt:-1;double value=type==VT_DECIMAL?out->dblVal:type==VT_INTEGER?out->lVal:0;
  if(SUCCEEDED(status)!=want->ok || type!=want->type || value!=want->value || strcmp(diagnostic,want->diagnostic) || memcmp(&e,original,sizeof(e))) {
   fprintf(stderr,"%s revision=%u got={%d,%d,%.17g,%d,%s} expected={%d,%d,%.17g,%d,%s}\n",c->name,revision,SUCCEEDED(status),type,value,e.turning,diagnostic,want->ok,want->type,want->value,want->turning,want->diagnostic);abort();
  }
 }
}
int main(void) {@CHECKS@ puts("early_defense_walking=1");return 0;}
