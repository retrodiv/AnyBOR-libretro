"""Render native text-object API contracts with complete matching variants.

Declarations, mapping/search functions, storage shape and observations are
explicit inputs. Owner accounting records and retires original orphaned
allocations without treating their absence in the candidate as lost fidelity.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import math
import re

CALLBACKS=dict(get='openbor_gettextobjproperty',change='openbor_changetextobjproperty',
               set='openbor_settextobj',clear='openbor_cleartextobj')


def render_text_objects(*,revisions,callbacks,mapping,helpers,physical_fixed,
                        seed_slots,slots,header_includes,cases,initializer=None,
                        field_paths=None,create_strings=False,
                        string_limit='MAX_STR_VAR_LEN'):
    if (not isinstance(revisions,list)or not 0<len(revisions)<=128 or
        any(type(n)is not int or not 0<n<=0xffffffff for n in revisions)or
        revisions!=sorted(set(revisions))or type(physical_fixed)is not bool or
        type(slots)is not int or not 4<=slots<=256 or type(seed_slots)is not int or
        not 0<=seed_slots<=256 or physical_fixed and seed_slots!=slots):
        raise ValueError('Explicit bounded native revisions and storage shape required')
    if field_paths is None:
        field_paths={name:name for name in ('x','y','z','font','t')}
    if (not isinstance(field_paths,dict) or set(field_paths)!={'x','y','z','font','t'} or
        any(not isinstance(path,str) or len(path)>128 or
            not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*){0,3}',path)
            for path in field_paths.values())):
        raise ValueError('Explicit bounded native text field paths required')
    if (type(create_strings)is not bool or not isinstance(string_limit,str) or
        len(string_limit)>128 or not re.fullmatch(r'[A-Za-z_]\w*',string_limit)):
        raise ValueError('Explicit native string setup and limit identifier required')
    if not isinstance(callbacks,dict)or set(callbacks)!=set(CALLBACKS):
        raise ValueError('All complete native text callbacks required')
    for key,name in CALLBACKS.items():
        text=callbacks[key]
        if (not isinstance(text,str)or not 0<len(text)<=32768 or '\0'in text or
            not re.match(r'\s*HRESULT\s+'+name+r'\s*\(',text)):
            raise ValueError('Complete bounded native text callbacks required')
    if any(not isinstance(s,str)or len(s)>65536 or '\0'in s for s in [mapping,helpers]):
        raise ValueError('Bounded native mapping and helper declarations required')
    if (not isinstance(header_includes,list)or not 0<len(header_includes)<=16 or
        any(not isinstance(n,str)or len(n)>256 or not re.fullmatch(r'[A-Za-z0-9_./-]+\.h',n)or
            n.startswith('/')or '..'in n.split('/')for n in header_includes)or
        len(set(header_includes))!=len(header_includes)):
        raise ValueError('Explicit ordered native headers required')
    if initializer is not None and (
        not isinstance(initializer,str) or not re.fullmatch(r'[A-Za-z_]\w*',initializer) or
        physical_fixed or seed_slots != 0 or not re.search(
            r'\bint\s+'+re.escape(initializer)+r'\s*\(',helpers)):
        raise ValueError('Native initializer requires its complete helper and empty dynamic storage')
    def integer(v):return type(v)is int and -(1<<31)<=v<(1<<31)
    def bytes_(v):return isinstance(v,list)and len(v)<=8192 and all(type(n)is int and 0<n<=255 for n in v)
    def value(v):
        return(isinstance(v,dict)and set(v)=={'kind','value'}and
            ((v['kind']in ['empty','missing','null_pointer']and v['value']is None)or
             (v['kind']=='integer'and integer(v['value']))or
             (v['kind']=='decimal'and type(v['value'])is float and math.isfinite(v['value']))or
             (v['kind']=='string'and bytes_(v['value']))))
    def expected(v):
        if not isinstance(v,dict)or not {'status','out','type'}<=set(v):return False
        if v['status']not in ['S_OK','E_FAIL']or v['out']not in ['retained','null']:return False
        kind=v['type'];keys={'status','out','type'}
        if kind in ['empty','unchanged']:return set(v)==keys
        if kind=='integer':return set(v)==keys|{'value'}and integer(v['value'])
        if kind=='decimal':return set(v)==keys|{'value'}and type(v['value'])is float and math.isfinite(v['value'])
        return kind=='string'and set(v)==keys|{'value'}and bytes_(v['value'])
    if not isinstance(cases,list)or not 0<len(cases)<=32:
        raise ValueError('Bounded explicit native operation cases required')
    for case in cases:
        if (not isinstance(case,dict)or not {'steps','orphan_allocations'}<=set(case)<={'steps','orphan_allocations','level_present'}or
            type(case.get('level_present',True))is not bool or
            type(case['orphan_allocations'])is not int or not 0<=case['orphan_allocations']<=256 or
            not isinstance(case['steps'],list)or not 0<len(case['steps'])<=128):
            raise ValueError('Explicit operation sequence and original owner observation required')
        for step in case['steps']:
            if not case.get('level_present',True) and isinstance(step,dict) and (step.get('objects') or 'count'in step or 'refuse'in step):
                raise ValueError('Absent level has no objects, table count or owned allocation')
            if (not isinstance(step,dict)or not {'call','arguments','expected','diagnostics','objects'}<=set(step)<=
                {'call','arguments','expected','diagnostics','objects','mapped','count','refuse','prelower','argument_array_present','result_slot_present','result_value_present','repeat','live_allocations'}or
                step['call']not in CALLBACKS or not isinstance(step['arguments'],list)or
                len(step['arguments'])>8 or not all(value(v)for v in step['arguments'])or
                not expected(step['expected'])or type(step['diagnostics'])is not int or
                not 0<=step['diagnostics']<=16 or not isinstance(step['objects'],list)or
                len(step['objects'])>128):
                raise ValueError('Bounded typed native call and independent observations required')
            if type(step.get('repeat',1))is not int or not 1<=step.get('repeat',1)<=1024:
                raise ValueError('Native operation repetitions must be bounded positive integers')
            if 'live_allocations'in step and(type(step['live_allocations'])is not int or not 0<=step['live_allocations']<=1024):
                raise ValueError('Explicit bounded live owner count required')
            for flag in ['argument_array_present','result_slot_present','result_value_present']:
                if flag in step and type(step[flag])is not bool:
                    raise ValueError('Native argument and result presence must be explicit booleans')
            if 'count'in step and(type(step['count'])is not int or not 0<=step['count']<=256 or physical_fixed):
                raise ValueError('Count belongs to explicit dynamic storage')
            if 'refuse'in step and step['refuse']not in ['table','text']:
                raise ValueError('Explicit callback allocation refusal class required')
            if 'mapped'in step and(len(step['arguments'])<2 or not integer(step['mapped'])):
                raise ValueError('Mapped property requires a supplied argument and numeric result')
            if 'prelower'in step:
                name=step['prelower']
                if (step['call']not in ['get','change']or len(step['arguments'])<2 or
                    not isinstance(name,str)or not re.fullmatch(r'[A-Za-z_]\w*',name)or
                    not re.search(r'\b(?:void|int)\s+'+re.escape(name)+r'\s*\(',mapping)or
                    not re.search(r'\bvoid\s*\*\s*Script_GetStringMapFunction\s*\(',helpers)):
                    raise ValueError('Prelowering needs its complete native dispatcher and selected mapper')
            for obj in step['objects']:
                if (not isinstance(obj,dict)or set(obj)!={'index','fields','text'}or
                    type(obj['index'])is not int or not 0<=obj['index']<256 or
                    not isinstance(obj['fields'],dict)or set(obj['fields'])!={'x','y','z','font','t'}or
                    not all(integer(v)for v in obj['fields'].values())or
                    obj['text']is not None and not bytes_(obj['text'])):
                    raise ValueError('Explicit bounded complete object snapshot required')
    if len(revisions)*sum(step.get('repeat',1)for case in cases for step in case['steps'])>1000000:
        raise ValueError('Split excessive repeated native observations')
    code=r'''
#include <stdint.h>
#include <stddef.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
/* Original property search signatures can differ from the current header. */
#define searchList anchor_searchList
@HEADERS@
#undef searchList
#undef malloc
#undef calloc
#undef realloc
#undef free
#undef printf
#define CHECK(c,m) do{if(!(c)){fprintf(stderr,"Text object contract: %s at line %d\n",m,__LINE__);abort();}}while(0)
#ifdef NDEBUG
#error Native text object assertions must remain active
#endif
#ifndef LEVEL_MAX_TEXTOBJS
#define LEVEL_MAX_TEXTOBJS @SLOTS@
#endif
uint32_t obor_profile_build;
s_level *level;
static unsigned observations,diagnostics,orphans;
static uintptr_t owner[1024];
static unsigned live[1024],owners;
static int refusal;
static unsigned refused;
static void remember(void *p){
 if(!p)return;CHECK(owners<1024,"bounded owner ledger");owner[owners]=(uintptr_t)p;live[owners++]=1;
}
static void *native_malloc(size_t bytes){
 CHECK(bytes<=8u*1024u*1024u,"bounded native text allocation");
 if(refusal==1){refusal=0;++refused;return NULL;}
 void *p=malloc(bytes);CHECK(p||!bytes,"fixture text allocation");remember(p);return p;
}
static void *native_calloc(size_t n,size_t bytes){
 CHECK(!n||bytes<=8u*1024u*1024u/n,"bounded native table allocation");
 if(refusal==2){refusal=0;++refused;return NULL;}
 void *p=calloc(n,bytes);CHECK(p||!n||!bytes,"fixture table allocation");remember(p);return p;
}
static void native_free(void *p){
 if(!p)return;
 for(unsigned i=0;i<owners;++i)if(live[i]&&owner[i]==(uintptr_t)p){live[i]=0;free(p);return;}
 CHECK(0,"callback release belongs to its allocator");
}
static void *native_realloc(void *p,size_t bytes){
 CHECK(bytes&&bytes<=8u*1024u*1024u,"bounded native table growth");
 unsigned old=1024;
 if(p){for(unsigned i=0;i<owners;++i)if(live[i]&&owner[i]==(uintptr_t)p){old=i;break;}
       CHECK(old!=1024,"growth preserves the original table owner");}
 if(refusal==2){refusal=0;++refused;return NULL;}
 void *grown=realloc(p,bytes);CHECK(grown,"fixture table growth");
 if(old!=1024)live[old]=0;remember(grown);return grown;
}
static int native_printf(const char *format,...){
 va_list ap;va_start(ap,format);++diagnostics;int n=vfprintf(stderr,format,ap);va_end(ap);return n;
}
void exitIfFalse(int v,const char *condition,const char *function,const char *file,int line){
 (void)condition;(void)function;(void)file;(void)line;CHECK(v,"native assertion");
}
void abortIfFalse(int v,const char *condition,const char *function,const char *file,int line){
 exitIfFalse(v,condition,function,file,line);
}
void *checkAlloc(void *p,size_t bytes,const char *function,const char *file,int line){
 exitIfFalse(!bytes||p,"native variant allocation",function,file,line);return p;
}
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
#define malloc native_malloc
#define calloc native_calloc
#define realloc native_realloc
#define free native_free
#define printf native_printf
@MAPPING@
@HELPERS@
@CALLBACKS@
#undef malloc
#undef calloc
#undef realloc
#undef free
#undef printf
static void string_value(ScriptVariant *v,const unsigned char *bytes,size_t length){
 CHECK(length<=@STRING_LIMIT@,"native input cache extent including terminator");
 ScriptVariant_Clear(v);ScriptVariant_ChangeType(v,VT_STR);
 memcpy(StrCache_Get(v->strVal),bytes,length);StrCache_Get(v->strVal)[length]=0;
}
static s_textobj *object(unsigned index){
 CHECK(level&&index<@COUNT@,"expected native object exists");return &level->textobjs[index];
}
static void fixture_seed(int active){
 owners=diagnostics=0;refusal=0;refused=0;
 level=NULL;if(!active)return;
 level=calloc(1,sizeof(*level));CHECK(level,"fixture level");@SEED@
}
static void retire(unsigned expected_orphans){
 if(level){
  for(unsigned i=0;i<@COUNT@;++i)native_free(level->textobjs[i].text);
  @RETIRE_TABLE@
  free(level);level=NULL;
 }
 unsigned found=0;
 for(unsigned i=0;i<owners;++i)if(live[i]){++found;free((void*)owner[i]);live[i]=0;}
 CHECK(found==expected_orphans,"original orphan allocation observation");orphans+=found;
 StrCache_Clear();
}
@OWNER_COUNT@@CASES@
int main(void){
 const uint32_t revisions[]={@REVISIONS@};
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i){obor_profile_build=revisions[i];@RUN@}
 printf("{\"status\":\"PASS\",\"contexts\":%u,\"checks\":%u,\"original_orphans\":%u}\n",
  (unsigned)(sizeof(revisions)/sizeof(*revisions)),observations,orphans);return 0;
}
'''
    definitions=[];runs=[]
    def byte_array(name,data):
        definitions.append('static const unsigned char '+name+'[]={'+(','.join(map(str,data+[0])))+'};')
    for number,case in enumerate(cases):
        body=['fixture_seed('+('1'if case.get('level_present',True)else'0')+');','ScriptVariant values[8],result,*out=&result,*argv[8]={0};', 'memset(values,0,sizeof(values));memset(&result,0,sizeof(result));']
        for k,step in enumerate(case['steps']):
            tag=str(number)+'_'+str(k)
            if step.get('repeat',1)>1:
                body.append('for(unsigned iteration_'+tag+'=0;iteration_'+tag+'<'+str(step['repeat'])+'u;++iteration_'+tag+'){')
            body.append('for(unsigned i=0;i<8;++i){ScriptVariant_Clear(&values[i]);argv[i]=NULL;}')
            body.append('ScriptVariant_Clear(&result);result.vt=VT_INTEGER;result.lVal=777;out=&result;')
            for i,v in enumerate(step['arguments']):
                name='values['+str(i)+']';kind,data=v['kind'],v['value']
                if kind=='missing':continue
                body.append('argv['+str(i)+']=&'+name+';')
                if kind=='integer':body.append(name+'.vt=VT_INTEGER;'+name+'.lVal='+str(data)+';')
                elif kind=='null_pointer':body.append(name+'.vt=VT_PTR;'+name+'.ptrVal=NULL;')
                elif kind=='decimal':body.append(name+'.vt=VT_DECIMAL;'+name+'.dblVal='+repr(data)+';')
                elif kind=='string':
                    array='input_'+tag+'_'+str(i);byte_array(array,data)
                    body.append('string_value(&'+name+','+array+','+str(len(data))+');')
            arguments='argv'if step.get('argument_array_present',True)else'NULL'
            result_slot='&out'if step.get('result_slot_present',True)else'NULL'
            if not step.get('result_value_present',True):body.append('out=NULL;')
            body.append('unsigned before_'+tag+'=diagnostics;')
            if 'refuse'in step:body.append('refusal='+str(1 if step['refuse']=='text'else 2)+';unsigned refusals_'+tag+'=refused;')
            if 'prelower'in step:
                mapper=step['prelower']
                body.append('CHECK(Script_GetStringMapFunction((void*)'+CALLBACKS[step['call']]+')==(void*)'+mapper+',"native prelowering mapper selection");')
                body.append(mapper+'('+arguments+','+str(len(step['arguments']))+');')
            body.append('HRESULT status_'+tag+'='+CALLBACKS[step['call']]+'('+arguments+','+result_slot+','+str(len(step['arguments']))+');')
            exp=step['expected'];body.append('CHECK(status_'+tag+'=='+exp['status']+'&&out=='+('&result'if exp['out']=='retained'else'NULL')+',"native status and result pointer");')
            kind=exp['type']
            condition={'empty':'result.vt==VT_EMPTY','unchanged':'result.vt==VT_INTEGER&&result.lVal==777',
                       'integer':'result.vt==VT_INTEGER&&result.lVal=='+str(exp.get('value',0)),
                       'decimal':'result.vt==VT_DECIMAL&&result.dblVal=='+repr(exp.get('value',0.0)),
                       'string':'result.vt==VT_STR'}[kind]
            body.append('CHECK('+condition+',"native result value/type");')
            if kind=='string':
                name='result_'+tag;byte_array(name,exp['value'])
                body.append('CHECK(!memcmp(StrCache_Get(result.strVal),'+name+','+str(len(exp['value'])+1)+'),"native result bytes and terminator");')
            body.append('CHECK(diagnostics==before_'+tag+'+'+str(step['diagnostics'])+',"native diagnostic count");')
            if 'mapped'in step:body.append('CHECK(values[1].vt==VT_INTEGER&&values[1].lVal=='+str(step['mapped'])+',"native mapped property argument");')
            if 'count'in step:body.append('CHECK(level->numtextobjs=='+str(step['count'])+',"native table count");')
            if 'refuse'in step:body.append('CHECK(!refusal&&refused==refusals_'+tag+'+1,"controlled allocation refusal");')
            for n,obj in enumerate(step['objects']):
                local='obj_'+tag+'_'+str(n);body.append('s_textobj *'+local+'=object('+str(obj['index'])+');')
                for field,val in obj['fields'].items():body.append('CHECK('+local+'->'+field_paths[field]+'=='+str(val)+',"native object '+field+'");')
                if obj['text']is None:body.append('CHECK(!'+local+'->text,"native absent text");')
                else:
                    name='text_'+tag+'_'+str(n);byte_array(name,obj['text'])
                    body.append('CHECK('+local+'->text&&!memcmp('+local+'->text,'+name+','+str(len(obj['text'])+1)+'),"native owned text bytes");')
            if 'live_allocations'in step:body.append('CHECK(native_owned_count()=='+str(step['live_allocations'])+'u,"native live allocation count");')
            body.append('++observations;')
            if step.get('repeat',1)>1:body.append('}')
        body.append('for(unsigned i=0;i<8;++i)ScriptVariant_Clear(&values[i]);ScriptVariant_Clear(&result);')
        body.append('retire('+str(case['orphan_allocations'])+');')
        definitions.append('static void case_'+str(number)+'(void){\n'+'\n'.join(body)+'\n}')
        runs.append('case_'+str(number)+'();')
    values=dict(HEADERS='\n'.join('#include "'+n+'"'for n in header_includes),SLOTS=str(slots),
        COUNT=str(slots)if physical_fixed else'(unsigned)level->numtextobjs',
        SEED=('CHECK('+initializer+'(level),"native level text initialization");')if initializer else ''if physical_fixed else'level->numtextobjs='+str(seed_slots)+';level->textobjs='+
             ('native_calloc('+str(seed_slots)+',sizeof(*level->textobjs));'if seed_slots else'NULL;'),
        RETIRE_TABLE=''if physical_fixed else'native_free(level->textobjs);level->textobjs=NULL;level->numtextobjs=0;',
        MAPPING=mapping,HELPERS=helpers,CALLBACKS='\n'.join(callbacks[n]for n in CALLBACKS),
        OWNER_COUNT=('static unsigned native_owned_count(void){unsigned count=0;for(unsigned i=0;i<owners;++i)count+=live[i]!=0;return count;}\n')if any('live_allocations'in step for case in cases for step in case['steps'])else'',
        CASES='\n'.join(definitions),RUN=''.join(runs),REVISIONS=','.join(str(n)+'u'for n in revisions),
        STRING_LIMIT=string_limit)
    if create_strings:
        code=code.replace('ScriptVariant_Clear(v);ScriptVariant_ChangeType(v,VT_STR);\n'
            ' memcpy(StrCache_Get(v->strVal),bytes,length);StrCache_Get(v->strVal)[length]=0;',
            'CHECK(strlen((const char *)bytes)==length,"fixture string terminator");\n'
            ' ScriptVariant_Clear(v);v->vt=VT_STR;\n'
            ' v->strVal=StrCache_CreateNewFrom((const char *)bytes);\n'
            ' CHECK(v->strVal>=0,"native string factory");')
    result=re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],code)
    if len(result)>4<<20:raise ValueError('Split excessive native text contracts')
    return result
