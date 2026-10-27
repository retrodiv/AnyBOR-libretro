"""Render source-defined script callback entry and dispatch contracts.

Copy/compile/helper bodies and entry lookup statements are inserted unchanged.
VM compilation/evaluation, local variables and destination cleanup are fixtures;
this is not a complete interpreter, ownership or gameplay acceptance test.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re


def render_callback_storage(engine, fixture):
    """Exercise actual entry unions, post-compilation conversion and reset."""
    from test_historical_player import function
    compiler = (engine / 'source/scriptlib/Interpreter.c').read_text()
    header = (engine / 'source/scriptlib/Interpreter.h').read_text()
    script = (engine / 'openborscript.c').read_text()
    body = function(compiler, 'Interpreter_CompileInstructions')
    first = body.index('// convert mainEntryIndex')
    pointers = body[first:body.index('// convert theJumpTargetIndex', first)]
    reset = re.search(r'(?m)^[ \t]*pinterpreter->mainEntryIndex = -1;\n'
                      r'[ \t]*pinterpreter->clearEntryIndex = -1;\n'
                      r'[ \t]*pinterpreter->initEntryIndex = -1;', body)[0]
    first = header.index('   union {')
    fields = header[first:header.index('   int bHasImmediateCode;', first)]
    checks = '\n'.join('obor_profile_build=%d;check(%s,%s);' % (
        row['revision'], 'NULL' if row['create_name'] is None else json.dumps(row['create_name']),
        json.dumps(row['destroy_name'])) for row in fixture['sources'])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int32_t LONG;
#define FALSE 0
#define FAILED(x) ((x)<0)
enum {VT_EMPTY,VT_INTEGER};
typedef struct {int vt;LONG lVal;} ScriptVariant;
typedef struct {int id;} Instruction;
typedef struct {const char *names[5];int count,index;} List;
typedef struct Interpreter {List theInstructionList;Instruction *instructionStorage;
@FIELDS@
    Instruction *pCurrentInstruction;int bReset;
    struct {char *name;} theSymbolTable;
} Interpreter;
typedef struct Script {int initialized;Interpreter *pinterpreter;char *comment;} Script;
static uint32_t obor_profile_build;
static unsigned cases,mask,phase,executions,resets,writes;
static int iscopy_value,localclear_value;
static Script *pcurrentscript,*expected_script;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"callback storage profile=%u mask=%u phase=%u line=%d\n",obor_profile_build,mask,phase,__LINE__);abort();}}while(0)
static int name_index(List *list,const char *name){
    if(!name)return -1;
    for(int i=0;i<list->count;++i)if(!strcmp(list->names[i],name))return i;
    return -1;
}
static int List_FindByName(List *list,const char *name){
    list->index=name_index(list,name);return list->index>=0;
}
static int List_GetIndex(List *list){return list->index;}
static void entry_conversion(Interpreter *pinterpreter){@POINTERS@}
static void failed_entry_reset(Interpreter *pinterpreter){@RESET@
    entry_conversion(pinterpreter);
}
static void ScriptVariant_Init(ScriptVariant *v){*v=(ScriptVariant){0};}
static void ScriptVariant_ChangeType(ScriptVariant *v,int type){v->vt=type;v->lVal=0;}
static void ScriptVariant_Clear(ScriptVariant *v){*v=(ScriptVariant){0};}
static void Script_Set_Local_Variant(Script *s,char *name,ScriptVariant *v){
    assert(s==expected_script && s==pcurrentscript);++writes;
    assert(!strcmp(name,"iscopy") || !strcmp(name,"localclear"));
    if(!strcmp(name,"iscopy"))iscopy_value=v->vt==VT_INTEGER?v->lVal:0;
    else localclear_value=v->vt==VT_INTEGER?v->lVal:0;
}
static void Interpreter_Reset(Interpreter *p){
    assert(p==expected_script->pinterpreter);++resets;p->bReset=1;
}
static int Interpreter_EvaluateCall(Interpreter *p){
    assert(p==expected_script->pinterpreter && p->pCurrentInstruction==p->pInitEntry);
    assert(p->pInitEntry && iscopy_value==1 && localclear_value==2);++executions;return 0;
}
static void shutdown(int code,char *format,...){(void)code;(void)format;assert(0);}
@INIT@
static void check(const char *create_name,const char *destroy_name){
    const char *names[]={"main","clear","init","ondestroy","oncreate"};
    for(mask=0;mask<32;++mask){
        phase=0;Instruction storage[8];Interpreter value={.instructionStorage=storage};
        Interpreter *pinterpreter=&value;
        for(int i=0;i<8;++i)storage[i].id=i;
        for(int i=0;i<5;++i)if(mask&(1u<<i))
            value.theInstructionList.names[value.theInstructionList.count++]=names[i];
        value.mainEntryIndex=value.clearEntryIndex=value.initEntryIndex=-1;
        @ENTRIES@
        int main_index=name_index(&value.theInstructionList,"main");
        int clear_index=name_index(&value.theInstructionList,destroy_name);
        int init_index=name_index(&value.theInstructionList,create_name);
        entry_conversion(pinterpreter);
        assert(value.pMainEntry==(main_index<0?NULL:&storage[main_index]));
        assert(value.pClearEntry==(clear_index<0?NULL:&storage[clear_index]));
        assert(value.pInitEntry==(init_index<0?NULL:&storage[init_index]));
        Script s={1,&value,"test"},sentinel={0};expected_script=&s;pcurrentscript=&sentinel;
        executions=resets=writes=0;iscopy_value=localclear_value=0;value.bReset=1;
        execute_init_method(&s,1,2);
        unsigned expected=init_index>=0;
        assert(executions==expected && resets==expected && writes==4*expected);
        assert(pcurrentscript==&sentinel && !iscopy_value && !localclear_value);
        assert(value.bReset==!expected);++cases;
        phase=1;failed_entry_reset(pinterpreter);
        assert(!value.pMainEntry && !value.pClearEntry && !value.pInitEntry);
        executions=resets=writes=0;value.bReset=1;execute_init_method(&s,1,2);
        assert(!executions && !resets && !writes && value.bReset==1 && pcurrentscript==&sentinel);
        ++cases;
    }
    pcurrentscript=NULL;
}
int main(void){@CHECKS@
    printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''.replace('@FIELDS@', fields).replace('@POINTERS@', pointers).replace('@RESET@', reset).replace(
        '@INIT@', function(script, 'execute_init_method')).replace('@ENTRIES@', entry_lookup(body)).replace(
        '@CHECKS@', checks)


def entry_lookup(compile_body):
    """Select the native entry lookup block from an explicit compiler body."""
    if not isinstance(compile_body, str) or not 0 < len(compile_body) <= 131072:
        raise ValueError('Bounded complete compiler source required')
    starts = list(re.finditer(
        r'(?m)^[ \t]*if\s*\(List_FindByName\([^\n]*"main"\)\)', compile_body))
    if len(starts) != 1:
        raise ValueError('One explicit native main entry lookup required')
    start = starts[0].start()
    end = re.search(r'(?m)^[ \t]*List_Reset\s*\(\s*&\s*\('
                    r'pinterpreter->theInstructionList\)\s*\)\s*;', compile_body[start:])
    if end is None:
        raise ValueError('Native instruction-list reset after entry lookup required')
    return compile_body[start:start + end.start()]


def render_callbacks(parts, *, create_name, destroy_name, dispatch_init,
                     compile_resets, revision, labels):
    if (not isinstance(parts, dict) or set(parts) != {'copy', 'compile', 'init_helper', 'entries'}
            or any(not isinstance(value, str) or len(value) > 32768 for value in parts.values())
            or any(not parts[key].strip() for key in ('copy', 'compile', 'entries'))):
        raise ValueError('Bounded exact copy, compile, optional helper and entry bodies required')
    if type(dispatch_init) is not bool or type(compile_resets) is not bool:
        raise ValueError('Explicit source dispatch and reset expectations required')
    if dispatch_init and not parts['init_helper'].strip():
        raise ValueError('Automatic dispatch requires its actual source helper')
    for name in (create_name, destroy_name):
        if name is not None and (not isinstance(name, str) or
                not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', name)):
            raise ValueError('Bounded native callback identifiers required')
    if type(revision) is not int or not 0 <= revision <= 0x7fffffff:
        raise ValueError('Explicit bounded profile context required')
    if (not isinstance(labels, list) or not 0 < len(labels) <= 256 or
            any(not isinstance(label, str) or not re.fullmatch(
                r'[A-Za-z0-9_-]{1,127}', label) for label in labels) or
            len(set(labels)) != len(labels)):
        raise ValueError('Unique bounded source identifiers required')
    names = sorted({'clear', 'init', 'ondestroy', 'oncreate', create_name, destroy_name} - {None})
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int32_t LONG;
enum {VT_EMPTY,VT_INTEGER};
#define FALSE 0
#define SUCCEEDED(x) ((x)>=0)
#define FAILED(x) ((x)<0)
typedef struct {int vt; LONG lVal;} ScriptVariant;
typedef struct {const char *names[8]; int count,index;} List;
typedef struct {List theInstructionList; int mainEntryIndex,clearEntryIndex,initEntryIndex;
 void *pInitEntry,*pCurrentInstruction;int bReset;
 struct {char name[16];} theSymbolTable;} Interpreter;
typedef struct Script {int initialized,interpreterowner;Interpreter *pinterpreter;
 char *comment; ScriptVariant *vars;} Script;
static uint32_t obor_profile_build=@REVISION@;
static Script *pcurrentscript,*expected_script;
static int evaluated,resets,cleared,compiles,mapped,iscopy_value,localclear_value;
static int iscopy_set,localclear_set,expected_iscopy,expected_localclear;
static const char *names[]={@NAMES@};
static const char *create_name=@CREATE@,*destroy_name=@DESTROY@;
static int name_index(List *list,const char *name) {
 if(!name)return -1;
 for(int i=0;i<list->count;++i) if(!strcmp(list->names[i],name))return i;
 return -1;
}
static int List_FindByName(List *list,const char *name) {
 list->index=name_index(list,name);return list->index>=0;
}
static int List_GetIndex(List *list) {return list->index;}
static void select_entries(Interpreter *pinterpreter,unsigned mask) {
 *pinterpreter=(Interpreter){0};pinterpreter->theInstructionList.names[0]="main";
 pinterpreter->theInstructionList.count=1;
 for(unsigned i=0;i<sizeof(names)/sizeof(*names);++i) if(mask&(1u<<i))
  pinterpreter->theInstructionList.names[pinterpreter->theInstructionList.count++]=names[i];
 pinterpreter->mainEntryIndex=pinterpreter->clearEntryIndex=pinterpreter->initEntryIndex=-1;
 @ENTRIES@
 pinterpreter->pInitEntry=pinterpreter->initEntryIndex<0?NULL:pinterpreter;
 pinterpreter->bReset=1;
}
static void ScriptVariant_Init(ScriptVariant *v) {*v=(ScriptVariant){0};}
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) {v->vt=type;v->lVal=0;}
static void ScriptVariant_Clear(ScriptVariant *v) {*v=(ScriptVariant){0};}
static void Script_Set_Local_Variant(Script *s,const char *name,ScriptVariant *v) {
 assert(s==pcurrentscript && s==expected_script);
 assert(!strcmp(name,"iscopy") || !strcmp(name,"localclear"));
 int *present=!strcmp(name,"iscopy")?&iscopy_set:&localclear_set;
 int *value=!strcmp(name,"iscopy")?&iscopy_value:&localclear_value;
 *present=v->vt==VT_INTEGER;if(*present)*value=v->lVal;
}
static void Interpreter_Reset(Interpreter *p) {
 assert(p && pcurrentscript==expected_script);++resets;p->bReset=1;
}
static int Interpreter_EvaluateCall(Interpreter *p) {
 assert(p && pcurrentscript==expected_script && p->pCurrentInstruction==p->pInitEntry);
 assert(iscopy_set && localclear_set);
 assert(iscopy_value==expected_iscopy && localclear_value==expected_localclear);
 ++evaluated;return 0;
}
static int Interpreter_CompileInstructions(Interpreter *p,...) {assert(p);++compiles;return 0;}
static int Script_MapStringConstants(Script *s) {assert(s);++mapped;return 1;}
static void Script_Clear(Script *s,int method) {
 assert(s && method>=0 && method<=2);++cleared;s->initialized=0;
}
static int obor_script_share_references(Script *dest,Script *source) {
 assert(dest && source && source->initialized);return 1;
}
static void shutdown(int status,const char *format,...) {
 (void)status;(void)format;assert(!"Unexpected callback contract failure");
}
@HELPER@
@COPY@
@COMPILE@
static void reset_counts(void) {
 evaluated=resets=cleared=compiles=mapped=iscopy_set=localclear_set=0;
 expected_script=NULL;
}
static void lookup_checks(void) {
 for(unsigned mask=0;mask<(1u<<(sizeof(names)/sizeof(*names)));++mask) {
  Interpreter p;select_entries(&p,mask);
  assert(p.mainEntryIndex==0);
  assert(p.clearEntryIndex==name_index(&p.theInstructionList,destroy_name));
  // An extra private cache slot predating the public creation callback has no
  // original counterpart. Dispatch is still checked with that slot populated.
  if(create_name)assert(p.initEntryIndex==name_index(&p.theInstructionList,create_name));
 }
}
static void dispatch_checks(void) {
 const unsigned all=(1u<<(sizeof(names)/sizeof(*names)))-1;
 for(int present=0;present<=1;++present) for(int method=0;method<=2;++method)
  for(int destination_initialized=0;destination_initialized<=1;++destination_initialized) {
   Interpreter p;select_entries(&p,present?all:0);
   ScriptVariant src_vars[1]={{0}},dest_vars[1]={{0}};
   Script source={.initialized=1,.interpreterowner=1,.pinterpreter=&p,.vars=src_vars};
   Interpreter old_interpreter={0};
   Script dest={.initialized=destination_initialized,.interpreterowner=1,
    .pinterpreter=destination_initialized?&old_interpreter:NULL,
    .comment=destination_initialized?"old destination":NULL,.vars=dest_vars};
   Script sentinel={0};
   reset_counts();expected_script=&dest;expected_iscopy=1;expected_localclear=method;
   pcurrentscript=&sentinel;Script_Copy(&dest,&source,method);
   const int expected=@DISPATCH@ && p.pInitEntry!=NULL;
   assert(evaluated==expected && resets==expected && cleared==destination_initialized);
   assert(pcurrentscript==&sentinel && !iscopy_set && !localclear_set);
   assert(dest.initialized==1 && !dest.interpreterowner && dest.pinterpreter==&p);
   assert(dest.vars==dest_vars && source.vars==src_vars);
  }
 for(int present=0;present<=1;++present) {
  Interpreter p;select_entries(&p,present?all:0);Script s={.initialized=1,.pinterpreter=&p};
  Script sentinel={0};reset_counts();expected_script=&s;expected_iscopy=0;expected_localclear=1;
  pcurrentscript=&sentinel;assert(Script_Compile(&s)==1);
  const int expected=@DISPATCH@ && p.pInitEntry!=NULL;
  assert(compiles==1 && evaluated==expected && resets==expected && !cleared);
  assert(p.bReset==!(@RESET@ || expected));
  assert(pcurrentscript==&sentinel && !iscopy_set && !localclear_set);
 }
 pcurrentscript=NULL;
}
int main(void) {
 @CHECKS@
 puts(@OBSERVATION@);return 0;
}
'''
    values = {'REVISION': str(revision), 'NAMES': ','.join(map(json.dumps, names)),
              'CREATE': 'NULL' if create_name is None else json.dumps(create_name),
              'DESTROY': 'NULL' if destroy_name is None else json.dumps(destroy_name),
              'ENTRIES': parts['entries'], 'HELPER': parts['init_helper'],
              'COPY': parts['copy'], 'COMPILE': parts['compile'],
              'DISPATCH': str(int(dispatch_init)), 'RESET': str(int(compile_resets)),
              'CHECKS': '\n'.join('lookup_checks();dispatch_checks();' for _ in labels),
              'OBSERVATION': json.dumps(json.dumps({'status': 'PASS', 'sources': len(labels),
                  'entry_cases_each': 1 << len(names), 'copy_cases_each': 12,
                  'compile_cases_each': 2}))}
    return re.sub(r'@('+'|'.join(values)+r')@', lambda match: values[match[1]], code)
