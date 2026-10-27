"""Render native property-name contracts with the matching variant library.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re


def render_string_mapper(*, revisions, header_includes, declarations, method,
                         method_name, cases, nullable_inputs=False,
                         return_type='int', input_setup='fixed'):
    if return_type not in ('int','void') or input_setup not in ('fixed','created'):
        raise ValueError('Explicit native return and string-storage contracts required')
    if (not isinstance(revisions, list) or not 0 < len(revisions) <= 128 or
        any(type(n) is not int or not 0 < n <= 0xffffffff for n in revisions) or
        revisions != sorted(set(revisions)) or type(nullable_inputs) is not bool):
        raise ValueError('Explicit bounded revisions and input-presence checks required')
    if (not isinstance(header_includes, list) or not 0 < len(header_includes) <= 16 or
        any(not isinstance(n, str) or len(n)>256 or
            not re.fullmatch(r'[A-Za-z0-9_./-]+\.h',n) or n.startswith('/') or
            '..' in n.split('/') for n in header_includes) or
        len(set(header_includes))!=len(header_includes)):
        raise ValueError('Explicit native variant headers required')
    if (not isinstance(method_name,str) or not re.fullmatch(r'[A-Za-z_]\w*',method_name) or
        not isinstance(method,str) or not 0<len(method)<=32768 or '\0' in method or
        not re.match(r'\s*'+return_type+r'\s+'+method_name+r'\s*\(',method) or
        not isinstance(declarations,str) or len(declarations)>65536 or '\0' in declarations):
        raise ValueError('Complete native mapper with matching return type and declarations required')
    if not isinstance(cases,list) or not 0<len(cases)<=256:
        raise ValueError('Bounded explicit mapper observations required')
    operations=[]
    capture=any(isinstance(c,dict) and 'diagnostic_text' in c for c in cases)
    for case in cases:
        if (not isinstance(case,dict) or
            set(case)-{'diagnostic_text'}!={'input','mapped','status','diagnostics'} or
            not (type(case['input']) is int and -(1<<31)<=case['input']<(1<<31) or
                 isinstance(case['input'],str) and len(case['input'])<=128 and
                 re.fullmatch(r'[A-Za-z0-9_]*',case['input'])) or
            not (case['mapped'] is None or type(case['mapped']) is int and
                 -(1<<31)<=case['mapped']<(1<<31)) or
            not (case['status'] is None if return_type=='void' else
                 type(case['status']) is int and case['status'] in (0,1)) or
            type(case['diagnostics']) is not int or not 0<=case['diagnostics']<=128):
            raise ValueError('Typed input, mapped value, return and diagnostic count required')
        if 'diagnostic_text' in case and (
            not isinstance(case['diagnostic_text'],str) or '\0' in case['diagnostic_text'] or
            len(case['diagnostic_text'].encode('utf-8'))>4096 or
            bool(case['diagnostic_text'])!=bool(case['diagnostics'])):
            raise ValueError('Bounded exact diagnostic text must agree with its count')
        if type(case['input']) is int:
            if case['mapped']!=case['input']:
                raise ValueError('Numeric selectors must retain their declared native value')
            setup='b.vt=VT_INTEGER;b.lVal='+str(case['input'])+';'
        else:
            literal=json.dumps(case['input'])
            setup='ScriptVariant_ChangeType(&b,VT_STR);strcpy(StrCache_Get(b.strVal),'+literal+');'
            if input_setup=='created':
                setup=('b.vt=VT_STR;b.strVal=StrCache_CreateNewFrom('+literal+');'
                       'CHECK(b.strVal>=0,"native created string");')
        observe=('b.vt==VT_STR&&!strcmp(StrCache_Get(b.strVal),'+json.dumps(case['input'])+')'
                 if case['mapped'] is None else 'b.vt==VT_INTEGER&&b.lVal=='+str(case['mapped']))
        call='CHECK(@METHOD@(argv,2)=='+str(case['status'])+',"native mapper return");'
        repeat='CHECK(@METHOD@(argv,2)==1&&'+observe+',"numeric lowering is stable");'
        if return_type=='void':
            call='@METHOD@(argv,2);'
            repeat='@METHOD@(argv,2);CHECK('+observe+',"numeric lowering is stable");'
        diagnostic_check='CHECK(diagnostics=='+str(case['diagnostics'])+',"native mapper diagnostics");'
        if 'diagnostic_text' in case:
            diagnostic_check+='\n CHECK(!strcmp(diagnostic_text,'+json.dumps(case['diagnostic_text'])+'),"native diagnostic text");'
        operations.append('''{
 ScriptVariant a={0},b={0},*argv[]={&a,&b};
 @SETUP@
 diagnostics=0;@RESET@@CALL@
 CHECK(@OBSERVE@,"native property result");
 @DIAGNOSTICS@
 @REPEAT@
 ScriptVariant_Clear(&a);ScriptVariant_Clear(&b);++checks;
}'''.replace('@SETUP@',setup).replace('@CALL@',call)
            .replace('@RESET@',"diagnostic_text[0]='\\0';diagnostic_length=0;" if capture else '')
            .replace('@OBSERVE@',observe).replace('@DIAGNOSTICS@',diagnostic_check)
            .replace('@REPEAT@',repeat if case['mapped'] is not None else ''))
    source=r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
#ifndef stricmp
#define stricmp strcasecmp
#endif
#define searchList anchor_searchList
@HEADERS@
#undef searchList
#undef malloc
#undef calloc
#undef realloc
#undef free
#undef printf
#define CHECK(c,m) do{if(!(c)){fprintf(stderr,"Property mapper: %s at line %d\n",m,__LINE__);abort();}}while(0)
#ifdef NDEBUG
#error Native mapper assertions must remain active
#endif
uint32_t obor_profile_build;
static unsigned diagnostics,checks;
void exitIfFalse(int v,const char *condition,const char *function,const char *file,int line){
 (void)condition;(void)function;(void)file;(void)line;CHECK(v,"native assertion");
}
void abortIfFalse(int v,const char *condition,const char *function,const char *file,int line){
 exitIfFalse(v,condition,function,file,line);
}
void *checkAlloc(void *p,size_t bytes,const char *function,const char *file,int line){
 exitIfFalse(!bytes||p,"native allocation",function,file,line);return p;
}
static int native_printf(const char *format,...){
 va_list ap;va_start(ap,format);++diagnostics;int n=vfprintf(stderr,format,ap);va_end(ap);return n;
}
#define printf native_printf
@DECLARATIONS@
@BODY@
#undef printf
static void run(void){
 @LOW_COUNT@++checks;
 @NULLABLE@
 @OPERATIONS@
 StrCache_Clear();
}
int main(void){
 const uint32_t revisions[]={@REVISIONS@};
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i){obor_profile_build=revisions[i];run();}
 printf("{\"status\":\"PASS\",\"contexts\":%u,\"checks\":%u}\n",
        (unsigned)(sizeof(revisions)/sizeof(*revisions)),checks);return 0;
}
'''
    if capture:
        source=source.replace('static int native_printf(const char *format,...){',r'''
static char diagnostic_text[8192];
static size_t diagnostic_length;
static int native_printf(const char *format,...){'''.lstrip()).replace(
            'va_list ap;va_start(ap,format);++diagnostics;int n=vfprintf(stderr,format,ap);va_end(ap);return n;',r'''
va_list ap,copy;va_start(ap,format);va_copy(copy,ap);++diagnostics;
 int written=vsnprintf(diagnostic_text+diagnostic_length,sizeof(diagnostic_text)-diagnostic_length,format,copy);
 va_end(copy);CHECK(written>=0&&(size_t)written<sizeof(diagnostic_text)-diagnostic_length,"bounded diagnostic capture");
 diagnostic_length+=(size_t)written;int n=vfprintf(stderr,format,ap);va_end(ap);return n;'''.lstrip())
    low_count='CHECK(@METHOD@(NULL,1)==1,"native low-count return");'
    nullable=('CHECK(@METHOD@(NULL,2)==1,"absent input array");++checks;'
              '{ScriptVariant *argv[]={NULL,NULL};CHECK(@METHOD@(argv,2)==1,"absent property");++checks;}')
    if return_type=='void':
        low_count='@METHOD@(NULL,1);'
        nullable=('@METHOD@(NULL,2);++checks;'
                  '{ScriptVariant *argv[]={NULL,NULL};@METHOD@(argv,2);++checks;}')
    if capture:
        low_count='diagnostics=0;'+low_count+'CHECK(diagnostics==0,"low-count diagnostics");'
        if nullable_inputs:
            nullable='diagnostics=0;'+nullable+'CHECK(diagnostics==0,"absent-input diagnostics");'
    values=dict(HEADERS='\n'.join('#include "'+n+'"' for n in header_includes),
                DECLARATIONS=declarations,BODY=method,METHOD=method_name,
                REVISIONS=','.join(str(n)+'u' for n in revisions),OPERATIONS='\n'.join(operations),
                LOW_COUNT=low_count.replace('@METHOD@',method_name),
                NULLABLE=nullable if nullable_inputs else '')
    # Expand operation placeholders before inserting complete native code.
    values['OPERATIONS']=values['OPERATIONS'].replace('@METHOD@',method_name)
    values['NULLABLE']=values['NULLABLE'].replace('@METHOD@',method_name)
    return re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],source)
