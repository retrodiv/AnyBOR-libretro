/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */

#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <string.h>
#include "source/openborscript/animation.c"
#undef assert
#define assert(x) ((x)?(void)0:__builtin_trap())
uint32_t obor_profile_build;
void ScriptVariant_Clear(ScriptVariant *v) { memset(v,0,sizeof(*v)); }
void ScriptVariant_ChangeType(ScriptVariant *v,VARTYPE t) { ScriptVariant_Clear(v);v->vt=t; }
static char *property_name = "hit_count";
char *StrCache_Get(int n) { (void)n;return property_name; }
int searchList(const char *list[],const char *value,int length) {
 for(int i=0;i<length;++i)if(!strcmp(list[i],value))return i;return -1;
}
void writeToLogFile(const char *s,...) { (void)s; }
CONVERSIONS
int main(void) {
 const uint32_t profiles[]={7086,7123,7142};
 for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
  obor_profile_build=profiles[p];
  s_anim a={0};a.hit_count=17;a.subject_to_gravity=false;a.attack_one=true;
  a.bounce_factor=2.5f;a.cancel=(e_anim_cancel)-3;a.charge_time=9;a.numframes=31;
  for(int present=0;present<2;++present) {
   a.obor_counter_present=present;
   a.collision_attack=present?(void *)&a:NULL;
   a.collision_body=present?(void *)&a:NULL;
   a.collision_entity=present?(void *)&a:NULL;
   for(int property=-1;property<=44;++property) {
    ScriptVariant h={.ptrVal=&a,.vt=VT_PTR},prop={.lVal=property,.vt=VT_INTEGER};
    ScriptVariant result={.lVal=88,.vt=VT_INTEGER},*out=&result,*args[]={&h,&prop};
    if(p==2)continue;
    int kind=VT_EMPTY;LONG integer=0;double decimal=0;void *ptr=NULL;int supported=1;
    switch(property) {
     case 0:kind=VT_INTEGER;integer=17;break;
     case 1:kind=VT_DECIMAL;decimal=1;break;
     case 2:case 4:case 5:if(present){kind=VT_PTR;ptr=&a;}break;
     case 3:kind=VT_INTEGER;integer=1;break;
     case 6:kind=VT_DECIMAL;decimal=2.5;break;
     case 7:kind=VT_INTEGER;integer=-3;break;
     case 8:kind=VT_INTEGER;integer=9;break;
     case 9:if(present){kind=VT_PTR;ptr=&a.counter_action;}break;
     case 25:kind=VT_INTEGER;integer=31;break;
     default:supported=0;
    }
    assert(openbor_get_animation_property(args,&out,2)==(supported?S_OK:E_FAIL));
    assert(out==&result && result.vt==kind);
    if(kind==VT_INTEGER)assert(result.lVal==integer);
    if(kind==VT_DECIMAL)assert(result.dblVal==decimal);
    if(kind==VT_PTR)assert(result.ptrVal==ptr);
   }
  }
  {
   ScriptVariant h={.ptrVal=&a,.vt=VT_PTR},prop={.strVal=0,.vt=VT_STR};
   ScriptVariant result={0},*out=&result,*args[]={&h,&prop};
   property_name="hit_count";
   assert(mapstrings_animation_property(args,2));
   assert(prop.vt==VT_INTEGER && prop.lVal==_ANIMATION_PROP_HIT_COUNT+(p==2?0:OBOR_ANIMATION_NAMED_BASE));
   assert(openbor_get_animation_property(args,&out,2)==S_OK && result.vt==VT_INTEGER && result.lVal==17);
   property_name="no_such_animation_property";prop=(ScriptVariant){.strVal=0,.vt=VT_STR};
   assert(!mapstrings_animation_property(args,2) && prop.vt==VT_STR);
  }
  if(p==2) {
   ScriptVariant h={.ptrVal=&a,.vt=VT_PTR},prop={.lVal=_ANIMATION_PROP_HIT_COUNT,.vt=VT_INTEGER};
   ScriptVariant result={0},*out=&result,*args[]={&h,&prop};
   assert(openbor_get_animation_property(args,&out,2)==S_OK && out==&result && result.vt==VT_INTEGER && result.lVal==17);
   continue;
  }
  for(int property=-1;property<=44;++property)for(int kind=VT_EMPTY;kind<=VT_STR;++kind) {
   a.hit_count=17;a.subject_to_gravity=false;a.numframes=31;
   ScriptVariant h={.ptrVal=&a,.vt=VT_PTR},prop={.lVal=property,.vt=VT_INTEGER};
   ScriptVariant value={.lVal=7,.vt=kind},result={.lVal=88,.vt=VT_INTEGER},*out=&result,*args[]={&h,&prop,&value};
   if(kind==VT_DECIMAL)value.dblVal=7.75;
   int supported=(property==0||property==1||property==25),numeric=(kind==VT_INTEGER||kind==VT_DECIMAL);
   assert(openbor_set_animation_property(args,&out,3)==(supported?S_OK:E_FAIL));
   assert(out==&result && result.vt==VT_INTEGER && result.lVal==88);
   assert(a.hit_count==((property==0&&numeric)?7:17));
   assert(a.subject_to_gravity==false);
   assert(a.numframes==((property==25&&numeric)?7:31));
  }
  ScriptVariant h={.ptrVal=NULL,.vt=VT_PTR},prop={.lVal=0,.vt=VT_INTEGER},v={.lVal=0,.vt=VT_INTEGER};
  ScriptVariant result={.vt=VT_INTEGER},*out=&result,*args[]={&h,&prop,&v};
  assert(openbor_get_animation_property(args,&out,2)==E_FAIL && out==NULL);
  out=&result;assert(openbor_set_animation_property(args,&out,3)==E_FAIL && out==NULL);
  h.ptrVal=&a;prop.lVal=1;out=&result;
  assert(openbor_set_animation_property(args,&out,3)==S_OK && a.subject_to_gravity);
  assert(openbor_get_animation_property(args,&out,2)==S_OK && result.vt==VT_DECIMAL && result.dblVal==0);
 }
}
