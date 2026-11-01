/* Native layer property controls; expected fields follow the own-source contract.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */
#include <assert.h>
#include <stddef.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#undef printf
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Layer property mismatch: revision=%u line=%d\n",obor_profile_build,__LINE__);abort();}}while(0)
uint32_t obor_profile_build;
static s_level storage,*level=&storage;
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
static const char *names[]={
 "alpha","amplitude","bgspeedratio","enabled","transparency","watermode",
 "wavelength","wavespeed","xoffset","xratio","xrepeat","xspacing",
 "zoffset","zratio","zrepeat","zspacing","unknown_layer_property"
};
static int strings_collected;
CHAR *StrCache_Get(int index) {assert(index>=0 && index<17);return (CHAR*)names[index];}
void StrCache_Collect(int index) {assert(index>=0 && index<17);++strings_collected;}
int StrCache_Pop(void) {abort();}
@VARIANTS@
@SEARCH@
@MACRO@
@ENTRIES@
typedef HRESULT (*entry)(ScriptVariant**,ScriptVariant**,int);
struct field {size_t flat_bg,flat_fg,nested_bg,nested_fg;int decimal,stored_float;};
#define F(flat,nested,decimal,floating) {offsetof(s_bglayer,flat),offsetof(s_fglayer,flat),offsetof(s_bglayer,nested),offsetof(s_fglayer,nested),decimal,floating}
static const struct field fields[]={
 {offsetof(s_bglayer,alpha),offsetof(s_fglayer,alpha),0,0,0,0},F(amplitude,drawmethod.water.amplitude,0,0),
 F(bgspeedratio,bgspeedratio,1,1),F(enabled,enabled,0,0),
 {offsetof(s_bglayer,transparency),offsetof(s_fglayer,transparency),0,0,0,0},F(watermode,drawmethod.water.watermode,0,0),
 F(wavelength,drawmethod.water.wavelength,0,0),F(wavespeed,drawmethod.water.wavespeed,1,1),
 F(xoffset,xoffset,0,0),F(xratio,xratio,1,1),F(xrepeat,xrepeat,0,0),F(xspacing,xspacing,0,0),
 F(zoffset,zoffset,0,0),F(zratio,zratio,1,1),F(zrepeat,zrepeat,0,0),F(zspacing,zspacing,0,0)
};
static unsigned char *slot(int foreground,int nested,int property) {
 if(nested && (property==0 || property==4))return NULL;
 const struct field *f=fields+property;
 return (foreground?(unsigned char*)level->fglayers:(unsigned char*)level->bglayers)+
   (foreground?(nested?f->nested_fg:f->flat_fg):(nested?f->nested_bg:f->flat_bg));
}
static int float_slot(int nested,int property) {return fields[property].stored_float || (nested && property==6);}
static void layer_seed(int foreground,int nested,int property,double value) {
 if(nested && (property==0 || property==4)) {
  s_drawmethod *m=foreground?&level->fglayers[0].drawmethod:&level->bglayers[0].drawmethod;
  if(property==0)m->alpha=(int)value;else m->transbg=(int)value;return;
 }
 unsigned char *p=slot(foreground,nested,property);
 if(float_slot(nested,property)){float v=(float)value;memcpy(p,&v,sizeof(v));}
 else {int v=(int)value;memcpy(p,&v,sizeof(v));}
}
static double read_field(int foreground,int nested,int property) {
 if(nested && (property==0 || property==4)) {
  s_drawmethod *m=foreground?&level->fglayers[0].drawmethod:&level->bglayers[0].drawmethod;
  return property==0?m->alpha:m->transbg;
 }
 unsigned char *p=slot(foreground,nested,property);
 if(float_slot(nested,property)){float v;memcpy(&v,p,sizeof(v));return v;}
 int v;memcpy(&v,p,sizeof(v));return v;
}
static void reset(void) {memset(level,0,sizeof(*level));level->numbglayers=level->numfglayers=1;}
static ScriptVariant integer(LONG value) {ScriptVariant v={0};v.vt=VT_INTEGER;v.lVal=value;return v;}
static ScriptVariant decimal(double value) {ScriptVariant v={0};v.vt=VT_DECIMAL;v.dblVal=value;return v;}
static void result_is(ScriptVariant *v,int property,double value) {
 assert(v->vt==(fields[property].decimal?VT_DECIMAL:VT_INTEGER));
 if(!fields[property].decimal && !(value>=-2147483648.0 && value<2147483648.0))value=0;
 if(fields[property].decimal)assert(v->dblVal==value);else assert(v->lVal==(LONG)value);
}
static void check(int nested) {
 entry getters[]={openbor_getbglayerproperty,openbor_getfglayerproperty};
 entry setters[]={openbor_changebglayerproperty,openbor_changefglayerproperty};
 const double inputs[]={13.75,-13.75,1000000001.0,2147483647.0,-2147483648.0};
 for(int fg=0;fg<2;++fg)for(int named=0;named<2;++named)for(int p=0;p<16;++p)
 for(int kind=0;kind<2;++kind)for(unsigned sample=0;sample<sizeof(inputs)/sizeof(*inputs);++sample) {
  reset();layer_seed(fg,0,p,31.5);layer_seed(fg,1,p,47.5);
  double before=read_field(fg,nested,p),untouched=read_field(fg,!nested,p);
  ScriptVariant index=integer(0),property=integer(p),value=kind?decimal(inputs[sample]):integer((LONG)inputs[sample]);
  if(named){property.vt=VT_STR;property.strVal=p;}
  ScriptVariant result=integer(73),*out=&result,*args[]={&index,&property,&value};
  strings_collected=0;
  assert(getters[fg](args,&out,2)==S_OK && out==&result);
  result_is(&result,p,before);
  assert(property.vt==VT_INTEGER && property.lVal==p && strings_collected==named);
  result=integer(73);out=&result;
  assert(setters[fg](args,&out,3)==S_OK && out==&result && result.vt==VT_INTEGER && result.lVal==1);
  double expected=fields[p].decimal?(double)(float)(kind?inputs[sample]:(double)(LONG)inputs[sample]):(double)(LONG)inputs[sample];
  if(nested && p==0)expected=(int8_t)(int)expected;
  if(nested && p==4)expected=(unsigned)(int)expected&1;
  if(nested && p==6)expected=(float)(int)expected;
  assert(read_field(fg,nested,p)==expected);
  if(slot(fg,0,p)!=slot(fg,1,p))assert(read_field(fg,!nested,p)==untouched);
  out=&result;assert(getters[fg](args,&out,2)==S_OK && out==&result);result_is(&result,p,expected);
  value.vt=VT_EMPTY;result=integer(73);out=&result;
  assert(setters[fg](args,&out,3)==S_OK && out==&result && result.lVal==73);
  assert(read_field(fg,nested,p)==expected);
 }
 for(int fg=0;fg<2;++fg)for(int setter=0;setter<2;++setter) {
  entry call=setter?setters[fg]:getters[fg];
  ScriptVariant index=integer(0),property=integer(0),value=integer(5),result=integer(73),*out=&result;
  ScriptVariant *args[]={&index,&property,&value};
  reset();assert(call(args,&out,setter?2:1)==E_FAIL && out==NULL);
  index.vt=VT_EMPTY;out=&result;assert(call(args,&out,setter?3:2)==E_FAIL && out==NULL);
  for(int invalid=0;invalid<2;++invalid){index=integer(invalid?1:-1);out=&result;result=integer(73);
   assert(call(args,&out,setter?3:2)==S_OK && out==&result && result.vt==VT_INTEGER && result.lVal==0);}
  index=integer(0);property=integer(16);out=&result;assert(call(args,&out,setter?3:2)==E_FAIL && out==NULL);
  property.vt=VT_STR;property.strVal=16;out=&result;assert(call(args,&out,setter?3:2)==E_FAIL && out==NULL);
 }
 /* The newer representation deliberately aliases water/plane members. */
 for(int fg=0;fg<2;++fg) {
  reset();s_drawmethod *method=fg?&level->fglayers[0].drawmethod:&level->bglayers[0].drawmethod;
  method->water.beginsize=1.5f;method->water.endsize=1.75f;method->water.perspective=0x3f800000;
  level->bglayers[0].amplitude=level->fglayers[0].amplitude=9;
  level->bglayers[0].wavelength=level->fglayers[0].wavelength=11;
  level->bglayers[0].wavespeed=level->fglayers[0].wavespeed=2.5f;
  int props[]={1,6,7};double expected[]={nested?0x3fc00000:9,nested?1:11,nested?1.0:2.5};
  for(int i=0;i<3;++i){ScriptVariant index=integer(0),property=integer(props[i]),result=integer(73),*out=&result,*args[]={&index,&property};
   assert(getters[fg](args,&out,2)==S_OK && out==&result);result_is(&result,props[i],expected[i]);}
  if(nested) {
   const float invalid[]={INFINITY,-INFINITY,NAN,2147483648.0f,-4294967296.0f};
   for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);++i) {
    method->water.endsize=invalid[i];ScriptVariant index=integer(0),property=integer(6),result=integer(73),*out=&result,*args[]={&index,&property};
    assert(getters[fg](args,&out,2)==S_OK && out==&result && result.vt==VT_INTEGER && result.lVal==0);
   }
  }
 }
}
int main(void) {@CHECKS@ return 0;}
