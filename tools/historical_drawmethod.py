"""Render native draw-method mapping and setter observations.

The engine header supplies the real records. Cache lifetime is observed;
rendering, the script VM and model lifecycle remain separate contracts.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re

from native_header_fixtures import graphics_refusals, inline_refusals
from test_historical_player import function


def drawmethod_parts(script, variants, utils):
    declaration=re.search(r'(?ms)^enum(?: drawmethod_enum)?\s*\{\s*_dm_alpha,.*?^\};',script)
    if declaration is None:raise ValueError('Complete native draw-method enumeration required')
    start=script.index('#define MAPSTRINGS(')
    parts=dict(enum=declaration[0],macro=script[start:script.index('\n\n',start)])
    for name in ('mapstrings_drawmethodproperty','openbor_changedrawmethod'):parts[name]=function(script,name)
    parts['searchList']=function(utils,'searchList')
    for name in ('ScriptVariant_ChangeType','ScriptVariant_IntegerValue','ScriptVariant_DecimalValue'):
        parts[name]=function(variants,name)
    return parts


def render_drawmethod(parts, *, revision, cases, unused_graphics_inlines=False,
                      unused_inline_declarations=None, align_embedded_method=False):
    required={'enum','macro','mapstrings_drawmethodproperty','openbor_changedrawmethod',
              'searchList','ScriptVariant_ChangeType','ScriptVariant_IntegerValue','ScriptVariant_DecimalValue'}
    if (not isinstance(parts,dict) or set(parts)!=required or
            any(not isinstance(v,str) or not v.strip() or len(v)>16384 for v in parts.values()) or
            type(revision) is not int or not 0<revision<=0xffffffff or
            type(align_embedded_method) is not bool):
        raise ValueError('Complete bounded native mapper, setter, lookup and conversion sources required')
    if not isinstance(cases,list) or not 1<=len(cases)<=2048:
        raise ValueError('Bounded independent draw-method observations required')
    calls=[]
    for case in cases:
        fields={'name','index','member','value_kind','target','input','expected_mapped','message'}
        if (not isinstance(case,dict) or set(case)!=fields or
                not isinstance(case['name'],str) or not re.fullmatch('[a-z]+',case['name']) or
                type(case['index']) is not int or not -1<=case['index']<=1024 or
                type(case['expected_mapped']) is not int or not -1<=case['expected_mapped']<=1024 or
                (case['member'] is not None and (not isinstance(case['member'],str) or not
                    re.fullmatch(r'[a-z]+(?:\.[a-z]+)?',case['member']))) or
                case['value_kind'] not in ('integer','decimal','pointer','reset','wavetime','rectangle') or
                case['target'] not in ('global','entity') or case['input'] not in ('string','lowered','numeric') or
                not isinstance(case['message'],str) or len(case['message'])>512 or
                not case['message'].isascii() or '\0' in case['message']):
            raise ValueError('Explicit native property numbering, target, input and independent result required')
        if case['value_kind']=='reset' and case['member'] is not None:
            raise ValueError('Reset observes the complete plain method, not one field')
        setup={'integer':'value.vt=VT_INTEGER;value.lVal=5;',
               'decimal':'value.vt=VT_DECIMAL;value.dblVal=5.25;',
               'pointer':'value.vt=VT_PTR;value.ptrVal=&marker;',
               'reset':'value.vt=VT_INTEGER;value.lVal=1;',
               'wavetime':'value.vt=VT_INTEGER;value.lVal=5;',
               'rectangle':'value.vt=VT_INTEGER;value.lVal=5;'}[case['value_kind']]
        expectation=''
        if case['value_kind']=='reset':expectation='expected=plainmethod;'
        elif case['value_kind']=='rectangle':
            expectation='expected.clipx=5;expected.clipy=6;expected.clipw=7;expected.cliph=8;'
        elif case['member'] is not None:
            value={'integer':'integer_value','decimal':'decimal_value','pointer':'(void*)&marker',
                   'wavetime':'(int)(integer_value*expected.water.wavespeed)'}[case['value_kind']]
            expectation='expected.'+case['member']+'='+value+';'
        named=case['input']!='numeric'
        property_setup=('property.vt=VT_STR;property.strVal=63;cache='+json.dumps(case['name'])+';'
                        if named else 'property.vt=VT_INTEGER;property.lVal='+str(case['index'])+';')
        target='target.vt=VT_PTR;target.ptrVal=&owner;' if case['target']=='entity' else 'target.vt=VT_EMPTY;'
        selected='owner.drawmethod' if case['target']=='entity' else 'drawmethod'
        other='drawmethod' if case['target']=='entity' else 'owner.drawmethod'
        count=6 if case['value_kind']=='rectangle' else 3
        lowered='mapstrings_drawmethodproperty(args,'+str(count)+');' if case['input']=='lowered' else ''
        mapped=(f'assert(property.vt==VT_INTEGER && property.lVal=={case["expected_mapped"]});'
                if case['expected_mapped']>=0 else 'assert(property.vt==VT_STR && property.strVal==63);')
        calls.append('''{
 ++active_case;memset(&owner,0,sizeof(owner));memset(&drawmethod,0,sizeof(drawmethod));
 drawmethod.scalex=owner.drawmethod.scalex=301;drawmethod.scaley=owner.drawmethod.scaley=302;
 drawmethod.water.wavespeed=owner.drawmethod.water.wavespeed=2.0f;
 s_drawmethod expected='''+selected+''',untouched='''+other+''';
 ScriptVariant target={0},property={0},value={0},result={0},*returned=&result,extra[3];
 memset(extra,0,sizeof(extra));
 for(int i=0;i<3;++i){extra[i].vt=VT_INTEGER;extra[i].lVal=6+i;}
 ScriptVariant *args[]={&target,&property,&value,extra,extra+1,extra+2};diagnostics=collects=0;diagnostic[0]=0;
 '''+target+property_setup+setup+'''
 ScriptVariant target_before=target,value_before=value;
 '''+expectation+lowered+'''
 assert(openbor_changedrawmethod(args,&returned,'''+str(count)+''')==S_OK && returned==NULL);
 assert(!memcmp(&expected,&'''+selected+''',sizeof(expected)));
 assert(!memcmp(&untouched,&'''+other+''',sizeof(untouched)));
 assert(!memcmp(&target,&target_before,sizeof(target)) && !memcmp(&value,&value_before,sizeof(value)));
 '''+(mapped if named else 'assert(property.vt==VT_INTEGER && property.lVal=='+str(case['index'])+');')+'''
 assert(collects=='''+str(int(named and case['expected_mapped']>=0))+''');
 assert(!strcmp(diagnostic,'''+json.dumps(case['message'])+'''));
 assert(diagnostics=='''+str(int(bool(case['message']))*(2 if case['input']=='lowered' else 1))+''');
}''')
    code=r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#ifndef stricmp
#define stricmp strcasecmp
#endif
#undef assert
#undef printf
#ifdef NDEBUG
#error Native draw-method assertions must remain enabled
#endif
static unsigned active_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Native draw-method mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
@GRAPHICS@
@REFUSALS@
const s_drawmethod plainmethod={.alpha=-1,.scalex=256,.scaley=256};
s_drawmethod drawmethod;
static entity owner;
@ALIGNED_STORAGE@
static int marker,collects,diagnostics;
static const char *cache;
static char diagnostic[1024];
CHAR *StrCache_Get(int index){assert(index==63 && cache);return (CHAR*)cache;}
void StrCache_Collect(int index){assert(index==63);++collects;}
int StrCache_Pop(void){abort();}
static int observed_printf(const char *format,...){
 va_list args;va_start(args,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);
 assert(n>=0 && (size_t)n<sizeof(diagnostic));++diagnostics;return n;
}
#define printf observed_printf
@SOURCES@
#undef printf
static volatile int integer_value=5;
static volatile double decimal_value=5.25;
@CASE_FUNCTIONS@
int main(void){
 @ALIGN_OWNER@
 @CALLS@
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    order=['enum','macro','searchList','ScriptVariant_ChangeType','ScriptVariant_IntegerValue',
           'ScriptVariant_DecimalValue','mapstrings_drawmethodproperty','openbor_changedrawmethod']
    if align_embedded_method:
        # Some original 32-bit records pack the containing entity, while their
        # unpacked method acquires pointer alignment on this 64-bit host. Bias
        # only the owned oracle fixture; native types and code stay unchanged.
        code=code.replace('static entity owner;','static entity *owner;').replace(
            'memset(&owner,0,sizeof(owner))','memset(owner,0,sizeof(*owner))').replace(
            'owner.drawmethod','owner->drawmethod').replace('target.ptrVal=&owner;','target.ptrVal=owner;')
        calls=[body.replace('memset(&owner,0,sizeof(owner))','memset(owner,0,sizeof(*owner))').replace(
            'owner.drawmethod','owner->drawmethod').replace('target.ptrVal=&owner;','target.ptrVal=owner;')
            for body in calls]
        storage='static union {max_align_t alignment;unsigned char bytes[sizeof(entity)+_Alignof(s_drawmethod)];} owner_storage;'
        align='''size_t alignment=_Alignof(s_drawmethod);
 size_t bias=(alignment-((uintptr_t)owner_storage.bytes+offsetof(entity,drawmethod))%alignment)%alignment;
 owner=(entity*)(owner_storage.bytes+bias);
 assert((uintptr_t)owner%_Alignof(entity)==0 && (uintptr_t)&owner->drawmethod%alignment==0);'''
    else:
        storage=''
        align='assert((uintptr_t)&owner.drawmethod%_Alignof(s_drawmethod)==0);'
    return code.replace('@ALIGNED_STORAGE@',storage).replace('@ALIGN_OWNER@',align).replace(
        '@REVISION@',str(revision)+'u').replace('@SOURCES@','\n'.join(parts[n] for n in order)).replace(
        '@GRAPHICS@',graphics_refusals(unused_graphics_inlines)).replace(
        '@REFUSALS@',inline_refusals(unused_inline_declarations)).replace(
        '@CASE_FUNCTIONS@','\n'.join('static __attribute__((noinline)) void observe_case_'+str(i)+'(void)'+body
                                    for i,body in enumerate(calls))).replace(
        '@CALLS@','\n'.join('observe_case_'+str(i)+'();' for i in range(len(calls))))
