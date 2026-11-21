/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include "source/openborscript/scriptcommon.h"
#undef assert
#define assert(x) ((x)?(void)0:(fprintf(stderr,"assertion line %d: %s\n",__LINE__,#x),__builtin_trap()))
uint32_t obor_profile_build;
enum { _ep_dropframe, _ep_energy_cost, _ep_landframe, _ep_animhits };
enum { _ep_energy_cost_cost, _ep_energy_cost_disable, _ep_energy_cost_mponly };
enum { _ep_landframe_ent, _ep_landframe_frame };
static char diagnostic[256];
void writeToLogFile(const char *text,...) {
 va_list arguments;
 va_start(arguments,text);
 vsnprintf(diagnostic,sizeof(diagnostic),text,arguments);
 va_end(arguments);
}
void ScriptVariant_ChangeType(ScriptVariant *var,VARTYPE type) {
 if(var->vt!=type) { memset(var,0,sizeof(*var));var->vt=type; }
}
CONVERSIONS
static HRESULT get(entity *ent,int selector,ScriptVariant **varlist,ScriptVariant **pretvar,int paramCount) {
 LONG ltemp=0;int i=0;ScriptVariant *arg;
 switch(selector) { GETTER_CASES }
 return S_OK;
}
static HRESULT set(entity *ent,int selector,ScriptVariant **varlist,ScriptVariant **pretvar,int paramCount) {
 LONG ltemp=0;int i=0;
 switch(selector) { SETTER_CASES }
 return S_OK;
changeentityproperty_error:
 *pretvar=NULL;return E_FAIL;
}
int main(void) {
 const unsigned profiles[]={6997,7039,7086,7091,7123,7142};
 for(unsigned p=0;p<sizeof(profiles)/sizeof(profiles[0]);++p)for(int present=0;present<2;++present) {
  obor_profile_build=profiles[p];int available=obor_profile_build==7142||present;
  s_anim animation={0};s_anim *animations[]={&animation};entity ent={0};
  ent.animation=&animation;animation.hit_count=9;
  ent.modeldata.animation=animations;ent.modeldata.animation_capacity=1;animation.numframes=1;
  animation.obor_energy_present=animation.obor_drop_present=animation.obor_land_present=present;
  animation.dropframe.frame=8;animation.landframe.frame=9;animation.landframe.model_index=10;
  animation.energy_cost.cost=11;animation.energy_cost.disable=-2;animation.energy_cost.mponly=2;
  ScriptVariant value[5]={{.vt=VT_PTR,.ptrVal=&ent},{.vt=VT_INTEGER},
   {.vt=VT_INTEGER},{.vt=VT_INTEGER},{.vt=VT_INTEGER,.lVal=37}};
  ScriptVariant *args[]={&value[0],&value[1],&value[2],&value[3],&value[4]},out,*result;
  const int landed[]={10,9},costs[]={11,-2,2};
  for(int sub=0;sub<3;++sub) {
   value[2].lVal=sub;out=(ScriptVariant){.vt=VT_EMPTY};result=&out;
   assert(get(&ent,_ep_energy_cost,args,&result,4)==S_OK && result==&out);
   assert(out.vt==VT_INTEGER && out.lVal==(available?costs[sub]:0));
  }
  for(int sub=0;sub<2;++sub) {
   value[2].lVal=sub;out=(ScriptVariant){.vt=VT_EMPTY};result=&out;
   assert(get(&ent,_ep_landframe,args,&result,4)==S_OK && result==&out);
   if(available)assert(out.vt==VT_INTEGER && out.lVal==landed[sub]);
   else assert(out.vt==VT_EMPTY);
  }
  const int slots[]={0,-1,1};
  for(size_t slot=0;slot<sizeof(slots)/sizeof(slots[0]);++slot) {
   value[2].lVal=slots[slot];out=(ScriptVariant){.vt=VT_EMPTY};result=&out;
   assert(get(&ent,_ep_dropframe,args,&result,3)==S_OK && result==&out);
   assert(out.vt==VT_INTEGER && out.lVal==(!slot&&available?8:0));
  }
  out=(ScriptVariant){.vt=VT_EMPTY};result=&out;
  assert(get(&ent,_ep_animhits,args,&result,2)==S_OK && out.vt==VT_INTEGER && out.lVal==9);
  value[2].lVal=12;
  assert(set(&ent,_ep_animhits,args,&result,3)==S_OK && animation.hit_count==12);
  for(int sub=0;sub<3;++sub) {
   value[2].lVal=sub;out=(ScriptVariant){.vt=VT_EMPTY};result=&out;
   assert(set(&ent,_ep_energy_cost,args,&result,5)==S_OK && result==&out);
   int actual=sub==0?animation.energy_cost.cost:sub==1?animation.energy_cost.disable:animation.energy_cost.mponly;
   assert(actual==(available?37:sub==0?11:sub==1?-2:2));
  }
  value[2].lVal=3;result=&out;diagnostic[0]=0;
  assert(set(&ent,_ep_energy_cost,args,&result,5)==E_FAIL && result==NULL);
  int early=profiles[p]==6997||profiles[p]==7039||profiles[p]==7091;
  assert(strcmp(diagnostic,early?"Unknown Energycost flag.\n":"Unknown energy_cost flag.\n")==0);
 }
}
