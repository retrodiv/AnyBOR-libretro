"""Render native level text collection/count property observations.

Complete accessors and the matching variant library retain native types.
Sequences preserve complete level fields across calls. These observations do
not execute table growth, rendering or owner release.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import math
import re


def render_text_collection(*, revisions, header_includes, getter, setter,
                           declarations, properties, cases):
    if (not isinstance(revisions,list) or not 0<len(revisions)<=128 or
        any(type(n)is not int or not 0<n<=0xffffffff for n in revisions) or
        revisions!=sorted(set(revisions))):
        raise ValueError('Explicit sorted native revisions required')
    if (not isinstance(header_includes,list) or not 0<len(header_includes)<=16 or
        any(not isinstance(n,str) or len(n)>256 or
            not re.fullmatch(r'[A-Za-z0-9_./-]+\.h',n) or n.startswith('/') or
            '..'in n.split('/') for n in header_includes) or
        len(set(header_includes))!=len(header_includes)):
        raise ValueError('Explicit native headers required')
    for body,name in [(getter,'openbor_get_level_property'),
                      (setter,'openbor_set_level_property')]:
        if (not isinstance(body,str) or not 0<len(body)<=65536 or '\0'in body or
            not re.match(r'\s*HRESULT\s+'+name+r'\s*\(',body)):
            raise ValueError('Complete native level property accessors required')
    if not isinstance(declarations,str) or len(declarations)>32768 or '\0'in declarations:
        raise ValueError('Bounded native declarations required')
    if (not isinstance(properties,dict) or set(properties)!={'collection','count'} or
        any(not isinstance(v,str) or not re.fullmatch(r'[A-Za-z_]\w*',v)
            for v in properties.values()) or len(set(properties.values()))!=2):
        raise ValueError('Own collection and count enum constants required')
    if not isinstance(cases,list) or not 0<len(cases)<=128:
        raise ValueError('Bounded independent native observations required')
    chunks=[]
    base={'call','handle','property','initial_counts','initial_tables','expected'}
    extra={'value','argument_count','argument_array_present','missing_arguments',
           'result_slot_present','result_entry_present','active_level_present',
           'continue_previous'}
    previous_expected=None
    for case in cases:
        if not isinstance(case,dict) or not base<=set(case)<=base|extra:
            raise ValueError('Explicit call, handle, property and initial state required')
        if case['call'] not in ('get','set') or case['handle'] not in ('primary','secondary','fallback','null'):
            raise ValueError('Declared native call and handle required')
        prop=case['property']
        if not (isinstance(prop,str) and prop in properties or
                type(prop)is int and -(1<<31)<=prop<(1<<31)):
            raise ValueError('Own property constant or bounded integer required')
        for field,low,high in [('initial_counts',-8,8),('initial_tables',0,2)]:
            if (not isinstance(case[field],list) or len(case[field])!=2 or
                any(type(n)is not int or not low<=n<=high for n in case[field])):
                raise ValueError('Two bounded initial levels required')
        continued=case.get('continue_previous',False)
        if type(continued)is not bool:
            raise ValueError('Continuation must be an explicit boolean')
        if continued and (previous_expected is None or
            case['initial_counts']!=previous_expected['counts'] or
            case['initial_tables']!=previous_expected['tables']):
            raise ValueError('Continued calls must match the previous complete level snapshot')
        count=case.get('argument_count',2 if case['call']=='get' else 3)
        missing=case.get('missing_arguments',[])
        if (type(count)is not int or not 0<=count<=3 or not isinstance(missing,list) or
            any(type(n)is not int or not 0<=n<=2 for n in missing) or
            missing!=sorted(set(missing))):
            raise ValueError('Explicit bounded argument presence required')
        flags={n:case.get(n,True) for n in ['argument_array_present','result_slot_present',
                                          'result_entry_present','active_level_present']}
        if any(type(v)is not bool for v in flags.values()):
            raise ValueError('Argument, result and active-level presence must be boolean')
        value=case.get('value',{'kind':'empty'})
        if not isinstance(value,dict) or set(value) not in ({'kind'},{'kind','value'}):
            raise ValueError('Typed native value required')
        kind=value['kind'];v=value.get('value');setup='input[2].vt=VT_EMPTY;'
        if kind=='empty' and set(value)=={'kind'}:
            pass
        elif kind=='integer' and type(v)is int and -(1<<31)<=v<(1<<31):
            setup='input[2].vt=VT_INTEGER;input[2].lVal='+str(v)+';'
        elif kind=='decimal' and type(v)in(int,float) and math.isfinite(v) and -(1<<30)<=v<=(1<<30):
            setup='input[2].vt=VT_DECIMAL;input[2].dblVal='+repr(float(v))+';'
        elif kind=='pointer' and type(v)is int and 0<=v<=2:
            setup='input[2].vt=VT_PTR;input[2].ptrVal=table('+str(v)+');'
        elif kind=='string' and isinstance(v,str) and re.fullmatch(r'[A-Za-z0-9_+\-]{0,32}',v):
            setup=('input[2].vt=VT_STR;input[2].strVal=StrCache_CreateNewFrom('+json.dumps(v)+');'
                   'CHECK(input[2].strVal>=0,"native input string");')
        else:
            raise ValueError('Bounded native input value required')
        expected=case['expected']
        required={'status','out','result_type','counts','tables','diagnostics'}
        if (not isinstance(expected,dict) or not required<=set(expected)<=required|{'result_value'} or
            expected['status']not in('S_OK','E_FAIL') or expected['out']not in('retained','null') or
            expected['result_type']not in('integer','empty') or
            type(expected['diagnostics'])is not int or not 0<=expected['diagnostics']<=8):
            raise ValueError('Independent return, result, levels and diagnostics required')
        if expected['result_type']=='integer':
            if type(expected.get('result_value'))is not int or not -(1<<31)<=expected['result_value']<(1<<31):
                raise ValueError('Bounded integer result required')
        elif 'result_value'in expected:
            raise ValueError('Empty results have no numeric value contract')
        for field,low,high in [('counts',-8,8),('tables',0,2)]:
            if (not isinstance(expected[field],list) or len(expected[field])!=2 or
                any(type(n)is not int or not low<=n<=high for n in expected[field])):
                raise ValueError('Bounded complete level snapshots required')
        handle={'primary':'input[0].vt=VT_PTR;input[0].ptrVal=&owners[0];',
                'secondary':'input[0].vt=VT_PTR;input[0].ptrVal=&owners[1];',
                'null':'input[0].vt=VT_PTR;input[0].ptrVal=NULL;',
                'fallback':'input[0].vt=VT_EMPTY;'}[case['handle']]
        lines=['{','ScriptVariant input[3],result={0},*out='+
               ('&result' if flags['result_entry_present'] else 'NULL')+';',
               'ScriptVariant *argv[]={&input[0],&input[1],&input[2]};',
               'memset(input,0,sizeof(input));',
               *([] if continued else ['memset(owners,0,sizeof(owners));']),
               'level='+('&owners[0]' if flags['active_level_present'] else 'NULL')+';',
               'result.vt=VT_INTEGER;result.lVal=1234;',handle,
               'input[1].vt=VT_INTEGER;input[1].lVal='+
               (properties[prop] if isinstance(prop,str) else str(prop))+';',setup]
        if not continued:
            for n in range(2):
                lines+=['owners['+str(n)+'].numtextobjs='+str(case['initial_counts'][n])+';',
                        'owners['+str(n)+'].textobjs=table('+str(case['initial_tables'][n])+');']
        lines+=['argv['+str(n)+']=NULL;'for n in missing]
        args='argv' if flags['argument_array_present'] else 'NULL'
        result_arg='&out' if flags['result_slot_present'] else 'NULL'
        lines+=['diagnostics=0;',
                'CHECK(openbor_'+case['call']+'_level_property('+args+','+result_arg+','+str(count)+')=='+expected['status']+',"native status");',
                'CHECK(out=='+('&result' if expected['out']=='retained' else 'NULL')+',"native output pointer");',
                'CHECK(result.vt=='+('VT_INTEGER' if expected['result_type']=='integer' else 'VT_EMPTY')+',"native result type");']
        if expected['result_type']=='integer':
            lines.append('CHECK(result.lVal=='+str(expected['result_value'])+',"native result value");')
        for n in range(2):
            lines+=['CHECK(owners['+str(n)+'].numtextobjs=='+str(expected['counts'][n])+',"native count snapshot");',
                    'CHECK(owners['+str(n)+'].textobjs==table('+str(expected['tables'][n])+'),"native collection snapshot");']
        lines+=['CHECK(diagnostics=='+str(expected['diagnostics'])+',"native diagnostic count");',
                'for(unsigned i=0;i<3;++i)ScriptVariant_Clear(&input[i]);',
                'ScriptVariant_Clear(&result);++checks;','}']
        chunks.append('\n'.join(lines))
        previous_expected=expected
    source=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
@HEADERS@
#undef malloc
#undef calloc
#undef realloc
#undef free
#undef printf
#define CHECK(c,m) do{if(!(c)){fprintf(stderr,"Text collection: %s at line %d\n",m,__LINE__);abort();}}while(0)
#ifdef NDEBUG
#error Native collection assertions must stay active
#endif
uint32_t obor_profile_build;
s_level *level;
static s_level owners[2];
static s_textobj tables[2][8];
static unsigned diagnostics,checks;
static s_textobj *table(unsigned n){CHECK(n<=2,"fixture table identity");return n?tables[n-1]:NULL;}
void exitIfFalse(int v,const char *condition,const char *function,const char *file,int line){
 (void)condition;(void)function;(void)file;(void)line;CHECK(v,"native assertion");
}
void abortIfFalse(int v,const char *condition,const char *function,const char *file,int line){exitIfFalse(v,condition,function,file,line);}
void *checkAlloc(void *p,size_t bytes,const char *function,const char *file,int line){exitIfFalse(!bytes||p,"native allocation",function,file,line);return p;}
static int native_printf(const char *format,...){va_list ap;va_start(ap,format);++diagnostics;int n=vfprintf(stderr,format,ap);va_end(ap);return n;}
#define printf native_printf
@DECLARATIONS@
@GETTER@
@SETTER@
#undef printf
static void run(void){
@CASES@
StrCache_Clear();
}
int main(void){const uint32_t revisions[]={@REVISIONS@};
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i){obor_profile_build=revisions[i];run();}
 printf("{\"status\":\"PASS\",\"contexts\":%u,\"checks\":%u}\n",(unsigned)(sizeof(revisions)/sizeof(*revisions)),checks);return 0;
}
'''
    values=dict(HEADERS='\n'.join('#include "'+h+'"'for h in header_includes),
                DECLARATIONS=declarations,GETTER=getter,SETTER=setter,
                CASES='\n'.join(chunks),REVISIONS=','.join(str(n)+'u'for n in revisions))
    return re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],source)
