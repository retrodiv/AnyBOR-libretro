/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <stdint.h>
#include <string.h>
#include "source/openborscript/scriptcommon.h"
#undef assert
#define assert(x) ((x)?(void)0:(fprintf(stderr,"assertion line %d: %s\n",__LINE__,#x),__builtin_trap()))
uint32_t obor_profile_build;
enum { _ep_dropframe, _ep_energy_cost, _ep_landframe };
enum { _ep_energy_cost_cost, _ep_energy_cost_disable, _ep_energy_cost_mponly };
enum { _ep_landframe_ent, _ep_landframe_frame };
void writeToLogFile(const char *text,...) { (void)text; }
void ScriptVariant_ChangeType(ScriptVariant *var,VARTYPE type) {
 if(var->vt!=type) { memset(var,0,sizeof(*var));var->vt=type; }
}
CONVERSIONS
static HRESULT get(entity *ent,int selector,ScriptVariant **varlist,ScriptVariant **pretvar,int paramCount) {
 LONG ltemp=0;int i=0;ScriptVariant *arg;
 switch(selector) { GETTER_CASES }
 return S_OK;
}
static HRESULT set(entity *ent,ScriptVariant **varlist,ScriptVariant **pretvar,int paramCount) {
 LONG ltemp=0;int i=0;
 switch(_ep_energy_cost) { SETTER_CASE }
 return S_OK;
changeentityproperty_error:
 *pretvar=NULL;return E_FAIL;
}
int main(void) {
 const unsigned profiles[]={7086,7123,7142};
 for(unsigned p=0;p<3;++p)for(int present=0;present<2;++present) {
  obor_profile_build=profiles[p];int available=p==2||present;
  s_anim animation={0};s_anim *animations[]={&animation};entity ent={0};
  ent.modeldata.animation=animations;ent.modeldata.animation_capacity=1;animation.numframes=1;
  animation.obor_energy_present=animation.obor_drop_present=animation.obor_land_present=present;
  animation.dropframe.frame=8;animation.landframe.frame=9;animation.landframe.model_index=10;
  animation.energy_cost.cost=11;animation.energy_cost.disable=-2;animation.energy_cost.mponly=2;
  ScriptVariant value[5]={{.vt=VT_PTR,.ptrVal=&ent},{.vt=VT_INTEGER},
   {.vt=VT_INTEGER},{.vt=VT_INTEGER},{.vt=VT_INTEGER,.lVal=37}};
  ScriptVariant *args[]={&value[0],&value[1],&value[2],&value[3],&value[4]},out,*result;
  for(int selector=0;selector<3;++selector) {
   value[2].lVal=0;out=(ScriptVariant){.vt=VT_EMPTY};result=&out;
   assert(get(&ent,selector,args,&result,selector==_ep_dropframe?3:4)==S_OK);
   assert(result==&out);
   if(selector==_ep_landframe && !available)assert(out.vt==VT_EMPTY);
   else { assert(out.vt==VT_INTEGER);assert(out.lVal==(available?(selector==0?8:selector==1?11:10):0)); }
  }
  for(int sub=0;sub<3;++sub) {
   value[2].lVal=sub;out=(ScriptVariant){.vt=VT_EMPTY};result=&out;
   assert(set(&ent,args,&result,5)==S_OK && result==&out);
   int actual=sub==0?animation.energy_cost.cost:sub==1?animation.energy_cost.disable:animation.energy_cost.mponly;
   assert(actual==(available?37:sub==0?11:sub==1?-2:2));
  }
 }
}
