"""Render exact coordinate getter cases with explicit native-shaped fixtures.

Numeric property routing and model tables are fixtures. Selected entry/case
bytes and variant conversions remain unchanged; this is not a VM/model test.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re
from test_historical_player import switch_cases


def coordinate_entry(source):
    if not isinstance(source,str) or not 0<len(source)<=2<<20:
        raise ValueError('Bounded native getter source required')
    method,cases=switch_cases(source,'openbor_getentityproperty','propind')
    for name,row in sorted(cases.items(),key=lambda pair:pair[1]['label_start'],reverse=True):
        if name not in ('_ep_attack','_ep_bbox','default'):
            method=method[:row['label_start']]+method[row['end']:]
    method,cases=switch_cases(method,'openbor_getentityproperty','ltemp')
    selected=[name for name in ('_gep_attack_coords','_ep_attack_coords') if name in cases]
    if len(selected)!=1:
        raise ValueError('Exact native attack coordinate case required')
    for name,row in sorted(cases.items(),key=lambda pair:pair[1]['label_start'],reverse=True):
        if name not in (selected[0],'default'):
            method=method[:row['label_start']]+method[row['end']:]
    return method


def render_reads(parts, *, scalar, components, visible_components, revision,
                 labels, check_invalid=False):
    if (not isinstance(parts,dict) or set(parts)!={'entry','clear','change_type'} or
            any(not isinstance(s,str) or not s.strip() or len(s)>32768 for s in parts.values())):
        raise ValueError('Bounded exact entry and variant source components required')
    if (scalar not in ('short','int') or type(components) is not int or components not in (5,6) or
            type(visible_components) is not int or visible_components not in (5,6) or
            visible_components>components):
        raise ValueError('Explicit native and visible coordinate shapes required')
    if type(check_invalid) is not bool:
        raise ValueError('Invalid-input checks must be distinct from original valid-call oracles')
    if type(revision) is not int or not 0<=revision<=0x7fffffff:
        raise ValueError('Bounded native profile context required')
    if (not isinstance(labels,list) or not 0<len(labels)<=256 or
            any(not isinstance(label,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,127}',label)
                for label in labels) or len(set(labels))!=len(labels)):
        raise ValueError('Unique bounded source identifiers required')
    program=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef NDEBUG
#error Native contract assertions must remain enabled
#endif
typedef int32_t LONG;
typedef double DOUBLE;
typedef int HRESULT;
typedef void VOID;
typedef enum {VT_EMPTY=0,VT_INTEGER=1,VT_DECIMAL=2,VT_PTR=5,VT_STR=6} VARTYPE;
typedef struct {union {LONG lVal;DOUBLE dblVal;void *ptrVal;int strVal;};VARTYPE vt;} ScriptVariant;
typedef @SCALAR@ coord_t;
enum {COMPONENTS=@COMPONENTS@,VISIBLE=@VISIBLE@};
enum {_ep_attack=1,_ep_bbox=2,_gep_attack_coords=3,_ep_attack_coords=3};
typedef struct {int unused;} s_sprite;
typedef struct {coord_t attack_coords[COMPONENTS];} s_attack;
typedef struct {int numframes;coord_t (*bbox_coords)[COMPONENTS];
                s_attack **attacks;short *vulnerable;} s_anim;
typedef struct {struct {s_anim **animation;int animation_capacity;} modeldata;} entity;
#define S_OK 0
#define E_FAIL (-1)
#define validanim(e,i) ((i)>=0 && (i)<(e)->modeldata.animation_capacity && \
 (e)->modeldata.animation && (e)->modeldata.animation[i] && \
 (e)->modeldata.animation[i]->numframes)
static uint32_t obor_profile_build=@REVISION@;
static char cache[2];
static char *StrCache_Get(int index) {assert(index==0);return cache;}
static int StrCache_Pop(void) {return 0;}
static void StrCache_Collect(int index) {assert(index==0);}
void ScriptVariant_ChangeType(ScriptVariant *var,VARTYPE type);
@CLEAR@
@CHANGE@
static int quiet_printf(const char *format,...) {(void)format;return 0;}
#define printf quiet_printf
static void mapstrings_getentityproperty(ScriptVariant **args,int count) {(void)args;(void)count;}
static void mapstrings_entityproperty(ScriptVariant **args,int count) {(void)args;(void)count;}
static int obor_entity_get_property_native(int value) {return value;}
@ENTRY@
#undef printf
static s_attack attacks[2][2],*attack_rows[2][2];
static coord_t boxes[2][2][COMPONENTS];
static short vulnerable[2][2]={{1,1},{1,1}};
static s_anim animations[2],*table[2];
static entity actor;
static ScriptVariant args[7],*argv[7];
static void setup(int property,int animation,int frame,int axis) {
 for(unsigned a=0;a<2;++a) {
  table[a]=&animations[a];animations[a]=(s_anim){.numframes=2,.bbox_coords=boxes[a],
                          .attacks=attack_rows[a],.vulnerable=vulnerable[a]};
  for(unsigned f=0;f<2;++f) {
   vulnerable[a][f]=1;attack_rows[a][f]=&attacks[a][f];
   for(unsigned i=0;i<COMPONENTS;++i) {
    int value=(int)(a*200+f*20+i)+40001;
    boxes[a][f][i]=(coord_t)value;attacks[a][f].attack_coords[i]=(coord_t)-value;
   }
  }
 }
 actor.modeldata.animation=table;actor.modeldata.animation_capacity=2;
 for(unsigned i=0;i<7;++i) {args[i]=(ScriptVariant){.vt=VT_INTEGER};argv[i]=&args[i];}
 args[0]=(ScriptVariant){.vt=VT_PTR,.ptrVal=&actor};args[1].lVal=property;
 if(property==_ep_attack) {
  args[2].lVal=_gep_attack_coords;args[3].lVal=1;args[4].lVal=animation;
  args[5].lVal=frame;args[6].lVal=axis;
 } else {args[2].lVal=1;args[3].lVal=animation;args[4].lVal=frame;args[5].lVal=axis;}
}
static void valid_checks(void) {
 unsigned cases=0;
 for(int property=1;property<=2;++property)for(int a=0;a<2;++a)
 for(int f=0;f<2;++f)for(int axis=0;axis<VISIBLE;++axis) {
  setup(property,a,f,axis);ScriptVariant result={.vt=VT_INTEGER,.lVal=99},*out=&result;
  int count=property==_ep_attack?7:6;
  assert(openbor_getentityproperty(argv,&out,count)==S_OK && out==&result);
  LONG expected=(LONG)(property==_ep_attack?attacks[a][f].attack_coords[axis]:boxes[a][f][axis]);
  assert(result.vt==VT_INTEGER && result.lVal==expected);++cases;
 }
 assert(cases==8*VISIBLE);
 setup(_ep_bbox,0,0,0);vulnerable[0][0]=0;
 ScriptVariant result={.vt=VT_INTEGER,.lVal=99},*out=&result;
 assert(openbor_getentityproperty(argv,&out,6)==S_OK && out==&result && result.vt==VT_EMPTY);
 setup(_ep_attack,0,0,0);animations[0].attacks=NULL;out=&result;
 assert(openbor_getentityproperty(argv,&out,7)==S_OK && out==&result && result.vt==VT_EMPTY);
 setup(_ep_attack,0,0,0);args[0]=(ScriptVariant){.vt=VT_EMPTY,.ptrVal=NULL};out=&result;
 assert(openbor_getentityproperty(argv,&out,7)==S_OK && out==&result && result.vt==VT_EMPTY);
}
static void empty_repeat(int count) {
 ScriptVariant first={.vt=VT_INTEGER,.lVal=77},second=first,*a=&first,*b=&second;
 int status=openbor_getentityproperty(argv,&a,count);
 assert(status==S_OK || status==E_FAIL);
 assert((a==NULL && status==E_FAIL) || (a==&first && first.vt==VT_EMPTY));
 assert(openbor_getentityproperty(argv,&b,count)==status);
 assert((a==NULL && b==NULL) || (b==&second && second.vt==first.vt));
}
static void invalid_checks(void) {
 const int bad_axes[]={-1,VISIBLE,VISIBLE+1,INT32_MAX};
 const int bad_indices[]={-1,2,INT32_MAX};unsigned cases=0;
 for(int property=1;property<=2;++property) {
  int count=property==_ep_attack?7:6;
  for(unsigned i=0;i<4;++i) {setup(property,0,0,bad_axes[i]);empty_repeat(count);++cases;}
  for(unsigned i=0;i<3;++i) {
   setup(property,bad_indices[i],0,0);empty_repeat(count);++cases;
   setup(property,0,bad_indices[i],0);empty_repeat(count);++cases;
  }
  setup(property,0,0,0);args[count-1]=(ScriptVariant){.vt=VT_DECIMAL,.dblVal=1.25};
  empty_repeat(count);++cases;
  for(int n=0;n<count;++n) {setup(property,0,0,0);empty_repeat(n);++cases;}
  setup(property,0,0,0);actor.modeldata.animation=NULL;empty_repeat(count);++cases;
 }
 setup(_ep_bbox,0,0,0);animations[0].bbox_coords=NULL;empty_repeat(6);++cases;
 setup(_ep_bbox,0,0,0);animations[0].vulnerable=NULL;empty_repeat(6);++cases;
 assert(cases==39);
}
int main(void) {
 @CALLS@
 puts(@OUTPUT@);return 0;
}
'''
    values=dict(SCALAR=scalar,COMPONENTS=str(components),VISIBLE=str(visible_components),
                REVISION=str(revision),ENTRY=parts['entry'],CLEAR=parts['clear'],CHANGE=parts['change_type'],
                CALLS='\n'.join('valid_checks();'+('invalid_checks();' if check_invalid else '') for label in labels),
                OUTPUT=json.dumps(json.dumps({'status':'PASS','sources':len(labels),
                    'valid_queries_each':8*visible_components,'defined_empty_cases_each':3,
                    'invalid_queries_each':39 if check_invalid else 0})))
    for name,value in values.items():program=program.replace('@'+name+'@',value)
    return program
