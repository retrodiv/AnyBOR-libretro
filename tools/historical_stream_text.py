"""Render native stream text and cursor contracts with real variant storage.

Copy/format observers refuse an oversized fixed destination before writing.
They preserve valid native operations; parser dispatch and file I/O are separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import math
import re

PARTS=('openbor_getfilestreamline','openbor_filestreamnextline',
       'openbor_getfilestreamposition','openbor_setfilestreamposition',
       'openbor_filestreamappend')


def render_text(*,revisions,callbacks,helpers,slots,physical_fixed,owned_extent,
                header_includes,dynamic_strings,cases,record=None,record_pack=None,
                level_streams=False,argument_reader=None,argument_parser=None,
                parser_capacity=None,saving=None):
    if (not isinstance(revisions,list)or not 0<len(revisions)<=128 or
        any(type(n)is not int or not 0<n<=0xffffffff for n in revisions)or
        revisions!=sorted(set(revisions))or type(slots)is not int or not 4<=slots<=1024 or
        any(type(v)is not bool for v in [physical_fixed,owned_extent,dynamic_strings,level_streams])or
        level_streams and not physical_fixed):
        raise ValueError('Explicit bounded stream representation required')
    if not isinstance(callbacks,dict)or set(callbacks)!=set(PARTS):
        raise ValueError('Every complete selected native callback is required')
    for name,source in callbacks.items():
        if(not isinstance(source,str)or not 0<len(source)<=32768 or '\0'in source or
           not re.match(r'\s*HRESULT\s+'+name+r'\s*\(',source)):
            raise ValueError('Complete bounded native callbacks required')
    if not isinstance(helpers,str)or len(helpers)>32768 or '\0'in helpers:
        raise ValueError('Bounded native helpers required')
    if(not isinstance(header_includes,list)or not 0<len(header_includes)<=16 or
       any(not isinstance(n,str)or len(n)>256 or not re.fullmatch(r'[A-Za-z0-9_./-]+\.h',n)or
           n.startswith('/')or '..'in n.split('/')for n in header_includes)or
       len(set(header_includes))!=len(header_includes)):
        raise ValueError('Ordered native headers required')
    if record is None:
        if record_pack is not None:raise ValueError('Packing requires an original record')
    elif(not isinstance(record,str)or not 0<len(record)<=8192 or '\0'in record or
         not re.fullmatch(r'\s*typedef\s+struct\s*\{[^{}]*\}\s*s_filestream\s*;\s*',record)or
         type(record_pack)is not int or record_pack not in (1,2,4,8,16)):
        raise ValueError('Complete original stream record and packing required')
    def byte_values(value):
        return isinstance(value,list)and len(value)<=8192 and all(type(n)is int and 0<=n<=255 for n in value)
    def integer(value):return type(value)is int and -(1<<31)<=value<(1<<31)
    def numeric_index(value):
        return integer(value)or(type(value)is float and math.isfinite(value)and -(1<<31)<=math.trunc(value)<(1<<31))
    def variant_input(value):
        if not isinstance(value,dict)or set(value)!={'kind','value'}:return False
        kind,data=value['kind'],value['value']
        return((kind=='empty'and data is None)or
               (kind=='integer'and integer(data))or
               (kind=='decimal'and type(data)is float and math.isfinite(data))or
               (kind=='string'and byte_values(data)and 0 not in data))
    def conversion_number(value):
        return(integer(value)or(type(value)is float and math.isfinite(value))or
               (isinstance(value,str)and value in ['nan','+inf','-inf']))
    arguments=any(v is not None for v in [argument_reader,argument_parser,parser_capacity])
    if saving is not None and(not isinstance(saving,str)or not 0<len(saving)<=32768 or
        '\0'in saving or not re.match(r'\s*HRESULT\s+openbor_savefilestream\s*\(',saving)):
        raise ValueError('Complete native save callback required for defined errors')
    if arguments and(not isinstance(argument_reader,str)or not 0<len(argument_reader)<=32768 or
        '\0'in argument_reader or not re.match(r'\s*HRESULT\s+openbor_getfilestreamargument\s*\(',argument_reader)or
        not isinstance(argument_parser,str)or not 0<len(argument_parser)<=32768 or '\0'in argument_parser or
        not re.match(r'\s*char\s*\*\s*findarg\s*\(',argument_parser)or
        type(parser_capacity)is not int or not 4<=parser_capacity<=65536):
        raise ValueError('Complete native argument reader, parser and capacity required together')
    def query_expected(value):
        if(not isinstance(value,dict)or value.get('status')not in ['S_OK','E_FAIL']or
           value.get('out')not in ['retained','null']):return False
        common={'status','out','type'};kind=value.get('type')
        if kind in ['empty','unchanged']:return set(value)==common
        if kind=='integer':return set(value)==common|{'value'}and integer(value['value'])
        if kind=='decimal':
            return set(value)==common|{'value'}and type(value['value'])is float and math.isfinite(value['value'])
        return(kind=='string'and set(value)==common|{'value','terminated'}and
               byte_values(value['value'])and type(value['terminated'])is bool)
    if not isinstance(cases,list)or not 0<len(cases)<=16:
        raise ValueError('Explicit bounded text cases required')
    for case in cases:
        if(not isinstance(case,dict)or set(case)!={'input','steps'}or
           not byte_values(case['input'])or not case['input']or case['input'][-1]!=0 or
           not isinstance(case['steps'],list)or not 0<len(case['steps'])<=128):
            raise ValueError('Terminated owned input and bounded operations required')
        for step in case['steps']:
            if not isinstance(step,dict):raise ValueError('Explicit operation required')
            op=step.get('operation')
            if op=='line':
                valid=(set(step)=={'operation','expected','terminated'}and
                       byte_values(step['expected'])and type(step['terminated'])is bool)
            elif op in ['position','next']:
                valid=set(step)=={'operation','expected'}and integer(step['expected'])
            elif op=='seek':valid=set(step)=={'operation','value'}and integer(step['value'])
            elif op=='release_input':valid=set(step)=={'operation'}
            elif op=='set_extent':
                valid=(owned_extent and set(step)=={'operation','bytes'}and
                       type(step['bytes'])is int and 0<=step['bytes']<=len(case['input']))
            elif op=='error_call':
                arity=dict(zip(PARTS,[1,1,1,2,3]))
                if arguments:arity['openbor_getfilestreamargument']=3
                if saving is not None:arity['openbor_savefilestream']=2
                call=step.get('callback');values=step.get('arguments')
                valid=(set(step)=={'operation','callback','arguments','expected','diagnostics'}and
                       isinstance(call,str)and call in arity and isinstance(values,list)and
                       len(values)<=arity[call]and all(variant_input(v)for v in values)and
                       query_expected(step['expected'])and
                       step['expected']['type']in ['empty','unchanged']and
                       type(step['diagnostics'])is int and 0<=step['diagnostics']<=16)
            elif op=='prime':
                valid=(arguments and set(step)=={'operation','text'}and byte_values(step['text'])and
                       bool(step['text'])and step['text'][-1]==0)
            elif op in ['argument','argument_conversion_refusal']:
                check_number=numeric_index if op=='argument'else conversion_number
                valid=(arguments and {'operation','which','kind','expected'}<=set(step)<=
                       {'operation','which','kind','expected','stream'}and check_number(step['which'])and
                       check_number(step.get('stream',0))and
                       byte_values(step['kind'])and 0 not in step['kind']and query_expected(step['expected']))
                if op=='argument_conversion_refusal':
                    valid=(valid and not(numeric_index(step['which'])and numeric_index(step.get('stream',0)))and
                           step['expected']==dict(status='S_OK',out='retained',type='unchanged'))
            elif op in ['append','append_refusal']:
                kind=step.get('kind');value=step.get('value')
                valid=(set(step)=={'operation','kind','value','mode','expected'}and integer(step['mode'])and
                       byte_values(step['expected'])and step['expected']and step['expected'][-1]==0 and
                       ((kind=='string'and byte_values(value)and 0 not in value)or
                        (kind=='integer'and integer(value))or
                        (kind=='decimal'and type(value)is float and math.isfinite(value))))
            else:valid=False
            if not valid:raise ValueError('Bounded typed operation and independent expectation required')
    code=r'''
#include <stdint.h>
#include <stddef.h>
#include <limits.h>
#include <math.h>
#include <strings.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
@RENAME@
@HEADERS@
@RECORD@
#undef malloc
#undef calloc
#undef realloc
#undef free
#undef printf
#define CHECK(c,m) do{if(!(c)){fprintf(stderr,"Stream text mismatch: %s\n",m);abort();}}while(0)
#ifdef NDEBUG
#error Stream text checks require active assertions
#endif
#ifndef LEVEL_MAX_FILESTREAMS
#define LEVEL_MAX_FILESTREAMS @SLOTS@
#endif
uint32_t obor_profile_build;
@STREAMS@
static unsigned observations;
static unsigned diagnostic_events;
static int callback_printf(const char *format,...){
 va_list args;va_start(args,format);++diagnostic_events;
 int written=vfprintf(stderr,format,args);va_end(args);return written;
}
static int refuse_buffer_allocation;
static unsigned buffer_refusals;
static void *callback_malloc(size_t bytes){
 if(refuse_buffer_allocation){++buffer_refusals;return NULL;}return malloc(bytes);
}
static void *callback_calloc(size_t count,size_t bytes){
 if(refuse_buffer_allocation){++buffer_refusals;return NULL;}return calloc(count,bytes);
}
void exitIfFalse(int v,const char *condition,const char *function,const char *file,int line){
 (void)condition;(void)function;(void)file;(void)line;CHECK(v,"native assertion");
}
void abortIfFalse(int v,const char *condition,const char *function,const char *file,int line){
 exitIfFalse(v,condition,function,file,line);
}
void *checkAlloc(void *p,size_t size,const char *function,const char *file,int line){
 exitIfFalse(!size||p,"native allocation",function,file,line);return p;
}
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
static char *bounded_copy(char *out,const char *input,size_t capacity){
 CHECK(strlen(input)<capacity,"fixed copy destination extent");return strcpy(out,input);
}
static int bounded_format(char *out,size_t capacity,const char *format,...){
 va_list args,copy;va_start(args,format);va_copy(copy,args);
 int length=vsnprintf(NULL,0,format,copy);va_end(copy);
 CHECK(length>=0&&(size_t)length<capacity,"fixed format destination extent");
 int written=vsprintf(out,format,args);va_end(args);return written;
}
@HELPERS@
@ARGUMENT_PARSER@
#define strcpy(out,input) bounded_copy(out,input,__builtin_object_size(out,0))
#define sprintf(out,...) bounded_format(out,__builtin_object_size(out,0),__VA_ARGS__)
#define malloc callback_malloc
#define calloc callback_calloc
#define printf(...) callback_printf(__VA_ARGS__)
#define obor_profile_malloc_named(name, bytes) callback_malloc(bytes)
#define obor_profile_calloc_named(name, bytes) callback_calloc(1, bytes)
@CALLBACKS@
@ARGUMENT_READER@
@SAVE_ERRORS@
#undef obor_profile_malloc_named
#undef obor_profile_calloc_named
#undef printf
#undef malloc
#undef calloc
#undef strcpy
#undef sprintf
static void string_value(ScriptVariant *value,const unsigned char *bytes,size_t length){
 ScriptVariant_Clear(value);ScriptVariant_ChangeType(value,VT_STR);
 @STRING_VALUE@
}
static void fixture_seed(const unsigned char *input,size_t bytes){
 @SEED@
 filestreams[0].buf=malloc(bytes);CHECK(filestreams[0].buf,"owned input");
 memcpy(filestreams[0].buf,input,bytes);filestreams[0].pos=0;filestreams[0].size=71;
 @EXTENT@
}
static void fixture_retire(void){
 for(unsigned n=0;n<@SLOTS@;++n)free(filestreams[n].buf);
 @RESET@
 StrCache_Clear();
}
@CASE_DEFINITIONS@
int main(void){
 const uint32_t revisions[]={@REVISIONS@};
 for(unsigned n=0;n<sizeof(revisions)/sizeof(*revisions);++n){
  obor_profile_build=revisions[n];
  @RUN_CASES@
 }
 printf("{\"status\":\"PASS\",\"contexts\":%u,\"checks\":%u}\n",
  (unsigned)(sizeof(revisions)/sizeof(*revisions)),observations);return 0;
}
'''
    definitions=[];calls=[]
    def array(name,values):
        definitions.append('static const unsigned char '+name+'[]={'+(','.join(map(str,values))or'0')+'};')
    for n,case in enumerate(cases):
        array('input_'+str(n),case['input']);body=[]
        for k,step in enumerate(case['steps']):
            tag=str(n)+'_'+str(k);op=step['operation']
            body.append('ScriptVariant_Clear(&result);result.vt=VT_INTEGER;result.lVal=777;out=&result;')
            if op=='line':
                array('expected_'+tag,step['expected'])
                if not dynamic_strings:
                    body.append('ScriptVariant_ChangeType(&result,VT_STR);memset(StrCache_Get(result.strVal),0x5a,MAX_STR_VAR_LEN+1);')
                body.append('CHECK(openbor_getfilestreamline(args,&out,1)==S_OK&&out==&result&&result.vt==VT_STR,"line result");')
                body.append('CHECK(!memcmp(StrCache_Get(result.strVal),expected_'+tag+','+str(len(step['expected']))+'),"line prefix");')
                if step['terminated']:
                    body.append('CHECK(!StrCache_Get(result.strVal)['+str(len(step['expected']))+'],"line result terminator");')
            elif op=='position':
                body.append('CHECK(openbor_getfilestreamposition(args,&out,1)==S_OK&&out==&result&&result.vt==VT_INTEGER&&result.lVal=='+str(step['expected'])+',"position result");')
            elif op=='next':
                body.append('CHECK(openbor_filestreamnextline(args,&out,1)==S_OK&&out==&result&&result.vt==VT_INTEGER&&result.lVal==777&&filestreams[0].pos=='+str(step['expected'])+',"next line and retained result");')
            elif op=='seek':
                body.append('ScriptVariant_Clear(&value);value.vt=VT_INTEGER;value.lVal='+str(step['value'])+';')
                body.append('CHECK(openbor_setfilestreamposition(args,&out,2)==S_OK&&out==&result&&result.vt==VT_INTEGER&&result.lVal==777&&filestreams[0].pos=='+str(step['value'])+',"seek result");')
            elif op=='release_input':
                body.append('free(filestreams[0].buf);filestreams[0].buf=NULL;')
                if owned_extent:body.append('filestreams[0].obor_capacity=0;')
            elif op=='set_extent':
                body.append('filestreams[0].obor_capacity='+str(step['bytes'])+';')
            elif op=='error_call':
                expected=step['expected']
                for i,(name,value)in enumerate(zip(['index','value','mode'],step['arguments'])):
                    kind,data=value['kind'],value['value']
                    body.append('ScriptVariant_Clear(&'+name+');')
                    if kind=='string':
                        array('error_value_'+tag+'_'+str(i),data+[0])
                        body.append('string_value(&'+name+',error_value_'+tag+'_'+str(i)+','+str(len(data))+');')
                    elif kind=='empty':body.append(name+'.vt=VT_EMPTY;')
                    else:
                        body.append(name+'.vt='+('VT_INTEGER;'+name+'.lVal='if kind=='integer'else
                            'VT_DECIMAL;'+name+'.dblVal=')+repr(data)+';')
                body.append('unsigned saved_diagnostics_'+tag+'=diagnostic_events;')
                body.append('int saved_position_'+tag+'=filestreams[0].pos;')
                body.append('ScriptVariant *error_args_'+tag+'[]={'+
                            (','.join('&'+n for n in ['index','value','mode'][:len(step['arguments'])])or'NULL')+'};')
                body.append('HRESULT error_status_'+tag+'='+step['callback']+'(error_args_'+tag+',&out,'+
                            str(len(step['arguments']))+');')
                body.append('CHECK(error_status_'+tag+'=='+expected['status']+'&&out=='+
                            ('&result'if expected['out']=='retained'else'NULL')+',"defined error status and result pointer");')
                condition='result.vt==VT_EMPTY'if expected['type']=='empty'else'result.vt==VT_INTEGER&&result.lVal==777'
                body.append('CHECK('+condition+',"defined error result value");')
                body.append('CHECK(diagnostic_events-saved_diagnostics_'+tag+'=='+str(step['diagnostics'])+
                            ',"defined error diagnostic count");')
                body.append('CHECK(filestreams[0].pos==saved_position_'+tag+'&&filestreams[0].size==71,"defined error retained stream fields");')
                body.append('ScriptVariant_Clear(&index);index.vt=VT_INTEGER;index.lVal=0;')
            elif op=='prime':
                array('prime_'+tag,step['text']);body.append('(void)findarg((char*)prime_'+tag+',0);')
            elif op in ['argument','argument_conversion_refusal']:
                expected=step['expected'];kind=expected['type'];which=step['which'];stream=step.get('stream',0)
                for name,number in [('value',which),('index',stream)]:
                    literal=({'nan':'NAN','+inf':'INFINITY','-inf':'(-INFINITY)'}[number]
                             if isinstance(number,str)else repr(number))
                    body.append('ScriptVariant_Clear(&'+name+');'+name+'.vt='+
                        ('VT_INTEGER;'+name+'.lVal='if type(number)is int else'VT_DECIMAL;'+name+'.dblVal=')+literal+';')
                array('kind_'+tag,step['kind']+[0]);body.append('string_value(&mode,kind_'+tag+','+str(len(step['kind']))+');')
                if kind=='string'and not dynamic_strings:
                    body.append('ScriptVariant_ChangeType(&result,VT_STR);memset(StrCache_Get(result.strVal),0x5a,MAX_STR_VAR_LEN+1);')
                body.append('int saved_position_'+tag+'=filestreams[0].pos;')
                body.append('HRESULT query_status_'+tag+'=openbor_getfilestreamargument(args,&out,3);')
                body.append('CHECK(query_status_'+tag+'=='+expected['status']+'&&out=='+
                            ('&result'if expected['out']=='retained'else'NULL')+',"argument status and result pointer");')
                if kind=='unchanged':condition='result.vt==VT_INTEGER&&result.lVal==777'
                elif kind=='empty':condition='result.vt==VT_EMPTY'
                elif kind in ['integer','decimal']:
                    condition='result.vt=='+('VT_INTEGER&&result.lVal=='if kind=='integer'else'VT_DECIMAL&&result.dblVal==')+repr(expected['value'])
                else:condition='result.vt==VT_STR'
                body.append('CHECK('+condition+',"argument value type and scalar result");')
                if kind=='string':
                    array('argument_expected_'+tag,expected['value'])
                    if not dynamic_strings:body.append('CHECK('+str(len(expected['value']))+'<=MAX_STR_VAR_LEN,"expected native string extent");')
                    body.append('CHECK(!memcmp(StrCache_Get(result.strVal),argument_expected_'+tag+','+str(len(expected['value']))+'),"argument byte prefix");')
                    if expected['terminated']:body.append('CHECK(!StrCache_Get(result.strVal)['+str(len(expected['value']))+'],"argument result terminator");')
                body.append('CHECK(filestreams[0].pos==saved_position_'+tag+'&&filestreams[0].size==71,"argument retained stream fields");')
                body.append('ScriptVariant_Clear(&index);index.vt=VT_INTEGER;index.lVal=0;')
            else:
                array('expected_'+tag,step['expected']);kind=step['kind'];value=step['value']
                if kind=='string':
                    array('value_'+tag,value+[0]);body.append('string_value(&value,value_'+tag+','+str(len(value))+');')
                else:
                    body.append('ScriptVariant_Clear(&value);value.vt='+('VT_INTEGER;value.lVal='if kind=='integer'else'VT_DECIMAL;value.dblVal=')+repr(value)+';')
                body.append('ScriptVariant_Clear(&mode);mode.vt=VT_INTEGER;mode.lVal='+str(step['mode'])+';int saved_position_'+tag+'=filestreams[0].pos;')
                if op=='append_refusal':
                    body.append('char *saved_buffer_'+tag+'=filestreams[0].buf;unsigned refusals_'+tag+'=buffer_refusals;refuse_buffer_allocation=1;')
                    body.append('HRESULT status_'+tag+'=openbor_filestreamappend(args,&out,3);refuse_buffer_allocation=0;')
                    body.append('CHECK(status_'+tag+'==E_FAIL&&out==NULL&&filestreams[0].buf==saved_buffer_'+tag+'&&buffer_refusals==refusals_'+tag+'+1,"append allocation refusal and retained owner");')
                else:
                    body.append('CHECK(openbor_filestreamappend(args,&out,3)==S_OK&&out==&result&&result.vt==VT_EMPTY,"append result");')
                body.append('CHECK(filestreams[0].pos==saved_position_'+tag+'&&filestreams[0].size==71&&!memcmp(filestreams[0].buf,expected_'+tag+','+str(len(step['expected']))+'),"append bytes and retained fields");')
            body.append('++observations;')
        definitions.append('static void case_'+str(n)+'(void){\nfixture_seed(input_'+str(n)+',sizeof(input_'+str(n)+'));\n'
            'ScriptVariant index={0},value={0},mode={0},result={0},*out=&result;\n'
            'index.vt=VT_INTEGER;index.lVal=0;ScriptVariant *args[]={&index,&value,&mode};\n'+
            '\n'.join(body)+'\nScriptVariant_Clear(&value);ScriptVariant_Clear(&mode);ScriptVariant_Clear(&result);fixture_retire();\n}\n')
        calls.append('case_'+str(n)+'();')
    # Only generated fixture expressions use this alias. Native callbacks retain
    # their own level/global expressions and record access unchanged.
    code=re.sub(r'\bfilestreams\b','FIXTURE_STREAMS',code)
    definitions=[re.sub(r'\bfilestreams\b','FIXTURE_STREAMS',s)for s in definitions]
    save_errors=r'''
static void forbidden_save_io(void){CHECK(0,"unexpected filesystem service in error-only save");}
static int forbidden_save_int(void){forbidden_save_io();return 0;}
static size_t forbidden_save_size(void){forbidden_save_io();return 0;}
static FILE *forbidden_save_file(void){forbidden_save_io();return NULL;}
char fixture_packfile[256]="fixture.pak";
#define packfile fixture_packfile
#define getBasePath(...) forbidden_save_io()
#define getPakName(...) forbidden_save_io()
#define dirExists(...) forbidden_save_int()
#define obor_pak_path_append(...) forbidden_save_int()
#define fopen(...) forbidden_save_file()
#define fwrite(...) forbidden_save_size()
#define fclose(...) forbidden_save_int()
@SAVING@
#undef packfile
#undef getBasePath
#undef getPakName
#undef dirExists
#undef obor_pak_path_append
#undef fopen
#undef fwrite
#undef fclose
'''.replace('@SAVING@',saving or'')if saving is not None else''
    values=dict(RENAME='#define s_filestream anchor_filestream'if record is not None else'',
        HEADERS='\n'.join('#include "'+n+'"'for n in header_includes),
        RECORD=('#undef s_filestream\n#pragma pack(push,'+str(record_pack)+')\n'+record+'\n#pragma pack(pop)')if record is not None else'',
        SLOTS=str(slots),STREAMS='s_filestream filestreams['+str(slots)+'];'if physical_fixed else's_filestream *filestreams;int numfilestreams;',
        HELPERS=helpers,CALLBACKS='\n'.join(callbacks[n]for n in PARTS),
        ARGUMENT_PARSER=('#undef MAX_ARG_LEN\n#define MAX_ARG_LEN '+str(parser_capacity)+'\n'+argument_parser)if arguments else'',
        ARGUMENT_READER=argument_reader or'',
        SAVE_ERRORS=save_errors,
        STRING_VALUE=('char *text=malloc(length+1);CHECK(text,"string input");memcpy(text,bytes,length);text[length]=0;value->strVal=StrCache_CreateNewFrom(text);free(text);'if dynamic_strings else
                      'CHECK(length<=MAX_STR_VAR_LEN,"native string extent");memcpy(StrCache_Get(value->strVal),bytes,length);StrCache_Get(value->strVal)[length]=0;'),
        SEED='memset(filestreams,0,sizeof(filestreams));'if physical_fixed else'size_t count='+str(slots)+';numfilestreams=(int)count;filestreams=calloc(count,sizeof(*filestreams));CHECK(filestreams,"owned table");',
        EXTENT='filestreams[0].obor_capacity=bytes;'if owned_extent else'',
        RESET='memset(filestreams,0,sizeof(filestreams));'if physical_fixed else'free(filestreams);filestreams=NULL;numfilestreams=0;',
        CASE_DEFINITIONS='\n'.join(definitions),RUN_CASES='\n'.join(calls),REVISIONS=','.join(str(n)+'u'for n in revisions))
    values['STREAMS']+='\n#define FIXTURE_STREAMS filestreams'
    if level_streams:
        values['STREAMS']='s_level *level;\n#define FIXTURE_STREAMS (level->filestreams)'
        values['SEED']='level=calloc(1,sizeof(*level));CHECK(level,"owned level");level->numfilestreams=1;'
        values['RESET']='free(level);level=NULL;'
    for key in ['SEED','EXTENT','RESET']:
        values[key]=re.sub(r'\bfilestreams\b','FIXTURE_STREAMS',values[key])
    result=re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],code)
    if len(result)>2<<20:raise ValueError('Split excessive text contracts')
    return result
