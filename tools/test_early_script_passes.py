"""Check source-defined initializer and string-mapping passes by profile.

The candidate pass/call functions execute with native records and List storage.
Instruction evaluation, compilation and name conversion use explicit providers.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from native_sanitizers import sanitizer_environment
from native_allocation_policy import bind_named_allocation_support
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-script-passes.json'


class EarlyScriptPassTests(unittest.TestCase):
    def test_compiler_and_call_feedback(self):
        from test_historical_player import switch_cases
        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-interpreter-feedback.json'))
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_SCRIPT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        script = engine / 'source/scriptlib'
        source = (script / 'Interpreter.c').read_text()
        branches = {}
        for name, label in [('Interpreter_CompileInstructions', 'CALL'), ('Interpreter_EvalInstruction', 'CHECKARG')]:
            body = function(source, name)
            # The common extractor names scalar selectors; only rename the
            # selector for extraction, retaining the native case body exactly.
            body, count = re.subn(r'switch\s*\(\s*pInstruction->OpCode\s*\)', 'switch(opcode)', body)
            self.assertEqual(count, 1)
            branches[label] = switch_cases(body, name, 'opcode')[1][label]['body']
        functions = '\n'.join(function((script / file).read_text(), name) for file, name in [
            ('ScriptVariant.c', 'ScriptVariant_Init'), ('Instruction.c', 'Instruction_NewData'),
            ('Instruction.c', 'Instruction_CallReferenceCount')])
        entries = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIs(type(row['runtime_original_defined']), bool)
            for name in ('runtime_format', 'missing_function_format'):
                self.assertIsInstance(row[name], str)
                self.assertLess(len(row[name]), 512)
            entries.append('{%d,%s,%s}' % (row['revision'], json.dumps(row['runtime_format']),
                                           json.dumps(row['missing_function_format'])))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Interpreter.h"
#undef printf
#undef assert
uint32_t obor_profile_build;
static unsigned scenario,logs;
static char messages[1024];
#define CHECK(c) do {if(!(c)){fprintf(stderr,"Interpreter feedback revision=%u scenario=%u line=%d: %s\n%s\n",obor_profile_build,scenario,__LINE__,#c,messages);abort();}}while(0)
static void reset_log(void) {logs=0;messages[0]=0;}
static int observed_log(const char *format,...) {
 va_list ap;va_start(ap,format);int n=vsnprintf(messages,sizeof(messages),format,ap);va_end(ap);
 CHECK(n>=0&&(size_t)n<sizeof(messages));++logs;return n;
}
@FUNCTIONS@
#define printf observed_log
static HRESULT compile_call(Interpreter *pinterpreter,Instruction *pInstruction) {
 HRESULT hr=S_OK;LPCSTR pLabel;Token *pToken;ScriptVariant *pSVar1,*pSVar2;int j;
 switch(pInstruction->OpCode) {case CALL:@CALL@ default:abort();}
 return hr;
}
static HRESULT check_arguments(Interpreter *pinterpreter,Instruction *pInstruction) {
 HRESULT hr=S_OK;Instruction *currentCall;
 switch(pInstruction->OpCode) {case CHECKARG:@CHECKARG@ default:abort();}
 return hr;
}
#undef printf
static HRESULT marker(ScriptVariant **args,ScriptVariant **result,int count) {
 (void)args;(void)result;(void)count;abort();
}
struct expectation {uint32_t revision;const char *runtime_format,*missing_format;};
static const struct expectation contexts[]={@CONTEXTS@};
static void compiler_checks(const struct expectation *ctx) {
 for(int target=0;target<3;++target)for(int keep_result=0;keep_result<2;++keep_result)
 for(int nargs=0;nargs<=2;nargs+=2) {
  ++scenario;reset_log();Interpreter owner={0};Instruction code[3]={{0}};Token token={0};
  ScriptVariant args[2],count={0};List functions;memset(args,0,sizeof(args));
  List_Init(&owner.theInstructionList);Stack_Init(&owner.theDataStack);List_Init(&functions);
  owner.ptheFunctionList=&functions;code[0].OpCode=CALL;code[0].theToken=&token;
  code[1].OpCode=keep_result?NOOP:CLEAN;code[2].OpCode=NOOP;
  const char *names[]={"missing","known_script","known_native"};
  strcpy(token.theSource,names[target]);
  List_InsertAfter(&owner.theInstructionList,code,"callsite");
  List_InsertAfter(&owner.theInstructionList,code+1,"next");
  List_InsertAfter(&owner.theInstructionList,code+2,"known_script");
  List_InsertAfter(&functions,(void *)marker,"known_native");List_Reset(&owner.theInstructionList);
  for(int i=0;i<nargs;++i) {args[i].vt=VT_INTEGER;args[i].lVal=10+i;Stack_Push(&owner.theDataStack,args+i);}
  count.vt=VT_INTEGER;count.lVal=nargs;Stack_Push(&owner.theDataStack,&count);
  CHECK(compile_call(&owner,code)==(target?S_OK:E_FAIL));
  CHECK(List_Retrieve(&owner.theInstructionList)==code);
  CHECK(code[0].theRefList&&code[0].theRefList->size==nargs&&code[0].theVal&&code[0].theVal->vt==VT_EMPTY);
  for(int i=0;i<nargs;++i)CHECK(code[0].theRefList->solidlist[i]==args+nargs-1-i);
  CHECK(owner.theDataStack.size==keep_result);
  if(keep_result)CHECK(Stack_Top(&owner.theDataStack)==code[0].theVal);
  if(!target) {
   char expected[512];snprintf(expected,sizeof(expected),ctx->missing_format,names[target]);
   CHECK(logs==(unsigned)(ctx->missing_format[0]!=0)&&!strcmp(messages,expected));
   CHECK(code[0].jumpTargetType==INSTRUCTION_TARGET_NONE&&!code[0].functionRef);
  } else {
   CHECK(!logs&&!messages[0]);
   if(target==1)CHECK(code[0].jumpTargetType==INSTRUCTION_TARGET_INDEX&&code[0].theJumpTargetIndex==2);
   else CHECK(code[0].jumpTargetType==INSTRUCTION_TARGET_FUNCTION&&code[0].functionRef==marker);
  }
  List_Clear(code[0].theRefList);free(code[0].theRefList);free(code[0].theVal);
  List_Clear(&owner.theDataStack);List_Clear(&owner.theInstructionList);List_Clear(&functions);
 }
}
static void runtime_checks(const struct expectation *ctx) {
 Interpreter owner={0};Instruction call={0},check={0};ScriptVariant declared={0},values[2];memset(values,0,sizeof(values));
 List list;List_Init(&list);for(int i=0;i<2;++i)List_InsertAfter(&list,values+i,NULL);
 CallReferenceList *packed=calloc(1,sizeof(*packed)+2*sizeof(*packed->values));CHECK(packed);packed->size=2;
 call.OpCode=CALL;check.OpCode=CHECKARG;check.theVal=&declared;owner.pCurrentCall=&call;
 for(int compact=0;compact<2;++compact)for(int count=1;count<=3;++count) {
  ++scenario;reset_log();declared.vt=VT_INTEGER;declared.lVal=count;
  call.referenceStorageType=compact?INSTRUCTION_REFERENCE_COMPACT:INSTRUCTION_REFERENCE_LIST;
  if(compact)call.callReferences=packed;else call.theRefList=&list;
  CHECK(Instruction_CallReferenceCount(&call)==2);
  CHECK(check_arguments(&owner,&check)==(count==2?S_OK:E_FAIL));
  if(count==2)CHECK(!logs&&!messages[0]);
  else {char expected[512];snprintf(expected,sizeof(expected),ctx->runtime_format,count);CHECK(logs==1&&!strcmp(messages,expected));}
 }
 ++scenario;reset_log();owner.pCurrentCall=NULL;CHECK(check_arguments(&owner,&check)==S_OK&&!logs);
 List_Clear(&list);free(packed);
}
int main(void) {
 for(unsigned i=0;i<sizeof(contexts)/sizeof(*contexts);++i) {
  obor_profile_build=contexts[i].revision;compiler_checks(contexts+i);runtime_checks(contexts+i);
 }
 puts("early_interpreter_feedback=1");return 0;
}
'''
        for key, value in dict(FUNCTIONS=functions, CALL=branches['CALL'], CHECKARG=branches['CHECKARG'],
                               CONTEXTS=',\n'.join(entries)).items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-interpreter-feedback-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            includes = [engine, engine / 'source', *sorted(p for p in (engine / 'source').iterdir() if p.is_dir()),
                        ROOT / 'src/port/libretro', ROOT / 'src/glue']
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu11', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                     '-fcommon', '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-error=deprecated-declarations', '-Wno-sign-compare', '-Wno-unused-parameter',
                     '-Wno-unused-function', '-Wno-unused-variable', '-Wno-error=int-to-pointer-cast',
                     '-Wno-error=pointer-to-int-cast']
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            build = subprocess.run(compiler + flags + ['-I'+str(p) for p in includes] +
                                   [str(unit), str(script / 'List.c'), str(script / 'Stack.c'), *links, '-o', str(binary)],
                                   capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                 env=sanitizer_environment())
            if os.environ.get('OBOR_INTERPRETER_FEEDBACK_OBSERVATIONS'):
                Path(os.environ['OBOR_INTERPRETER_FEEDBACK_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=compiler, contexts=len(rows), cases_per_context=19,
                    probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    interpreter_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    returncode=run.returncode, stdout=run.stdout, stderr=run.stderr, scope=fixture['scope'],
                    retirement='TemporaryDirectory removes source and binary'), indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_interpreter_feedback=1', run.stdout)

    def test_initializer_mapping_main_and_argument_counts(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertEqual((min(revisions), max(revisions)), tuple(fixture['range']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for row in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(row.get('revision', row['build']))
            if row['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        checks = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['function_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            self.assertEqual(set(row['passes']), {'initializers', 'string_mapping'})
            self.assertTrue(all(type(value) is bool for value in row['passes'].values()))
            checks.append('check(%d,%d,%d);' % (
                row['revision'], row['passes']['initializers'], row['passes']['string_mapping']))
        engine = Path(os.environ.get('OBOR_EARLY_SCRIPT_ENGINE',
                                     ROOT / 'src/engines' / fixture['engine']))
        interpreter = engine / 'source/scriptlib/Interpreter.c'
        script = engine / 'openborscript.c'
        instruction = engine / 'source/scriptlib/Instruction.c'
        functions = '\n'.join(
            function(path.read_text(), name) for path, names in [
                (instruction, ['Instruction_CallReferenceCount', 'Instruction_CallReferenceValues']),
                (interpreter, ['Interpreter_EvaluateCall', 'Interpreter_Call',
                               'Interpreter_EvaluateImmediate', 'Interpreter_Reset']),
                (script, ['Script_MapStringConstants', 'Script_Compile'])]
            for name in names)
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openborscript.h"
uint32_t obor_profile_build;
static Instruction *active_code;
static int initial_value,main_calls,native_arguments,maps,copies,queries,compiles;
void writeToLogFile(const char *format,...) {(void)format;assert(!"Unexpected pass diagnostic");}
void exitIfFalse(int value,const char *condition,const char *func,const char *file,int line) {
 (void)condition;(void)func;(void)file;(void)line;if(!value)abort();
}
void ScriptVariant_Copy(ScriptVariant *out,ScriptVariant *value) {
 assert(value->vt==VT_INTEGER);*out=*value;copies++;
}
HRESULT Interpreter_EvalInstruction(Interpreter *owner) {
 Instruction *ins=owner->pCurrentInstruction;
 assert(ins>=active_code && ins<active_code+8);
 if(ins==active_code+3) {assert(ins->OpCode==SAVE);initial_value+=17;}
 if(ins==active_code+6) {assert(ins->OpCode==CALL);main_calls++;}
 if(ins->OpCode==RET) owner->bCallCompleted=TRUE;
 owner->pCurrentInstruction++;return S_OK;
}
HRESULT Interpreter_CompileInstructions(Interpreter *owner,List *exports) {
 assert(owner && !exports);compiles++;return S_OK;
}
void Script_Clear(Script *script,int local) {(void)script;(void)local;abort();}
void shutdown(int status,char *format,...) {(void)status;(void)format;abort();}
static HRESULT native_marker(ScriptVariant **args,ScriptVariant **result,int count) {
 assert(count==3 && result && *result);native_arguments=count;
 (*result)->vt=VT_INTEGER;(*result)->lVal=0;
 for(int i=0;i<count;i++) {assert(args[i]->vt==VT_INTEGER);(*result)->lVal+=args[i]->lVal;}
 return S_OK;
}
static HRESULT native_ignore(ScriptVariant **args,ScriptVariant **result,int count) {
 (void)args;(void)result;(void)count;abort();
}
static void map_names(ScriptVariant **args,int count) {
 assert(count==3);maps++;
 for(int i=0;i<count;i++) {
  if(args[i]->vt==VT_STR) {args[i]->vt=VT_INTEGER;args[i]->lVal=41+i;}
  else assert(args[i]->vt==VT_INTEGER && args[i]->lVal==41+i);
 }
}
typedef void (*map_function)(ScriptVariant**,int);
static map_function Script_GetStringMapFunction(SCRIPTFUNCTION callback) {
 queries++;return callback==native_marker?map_names:NULL;
}
@FUNCTIONS@
static void pack(List *list,Instruction *code,int count) {
 List_Init(list);
 for(int i=0;i<count;i++) List_InsertAfter(list,code+i,NULL);
 List_Solidify(list);assert(List_GetSize(list)==count);
 for(int i=0;i<count;i++) assert(list->solidlist[i]==code+i);
}
static void check(unsigned revision,int immediate,int mapping) {
 Interpreter owner;Instruction code[8];Script script;
 memset(&owner,0,sizeof(owner));memset(code,0,sizeof(code));memset(&script,0,sizeof(script));
 obor_profile_build=revision;initial_value=main_calls=native_arguments=0;
 active_code=code;
 for(int i=0;i<8;i++) code[i].OpCode=NOOP;
 code[0].OpCode=DEFERRED;code[2].OpCode=IMMEDIATE;code[3].OpCode=SAVE;
 code[4].OpCode=DEFERRED;code[5].OpCode=SAVE;code[6].OpCode=CALL;code[7].OpCode=RET;
 pack(&owner.theInstructionList,code,8);
 owner.instructionStorage=code;owner.pMainEntry=code+6;owner.bHasImmediateCode=TRUE;
 assert(Interpreter_EvaluateImmediate(&owner)==S_OK);
 assert(initial_value==17*immediate && main_calls==1 && owner.bMainCompleted);
 assert(Interpreter_EvaluateImmediate(&owner)==S_OK);
 assert(initial_value==34*immediate && main_calls==1);
 owner.bHasImmediateCode=FALSE;Interpreter_Reset(&owner);
 assert(Interpreter_EvaluateImmediate(&owner)==S_OK && main_calls==2);
 assert(initial_value==34*immediate && owner.theInstructionList.size==8);
 for(int i=0;i<8;i++) assert(owner.theInstructionList.solidlist[i]==code+i);
 List_Clear(&owner.theInstructionList);assert(!owner.theInstructionList.size);

 /* A packed parameter list keeps its native argument count in every profile. */
 ScriptVariant values[3],result;List arguments;Instruction call;
 memset(values,0,sizeof(values));memset(&result,0,sizeof(result));memset(&call,0,sizeof(call));
 List_Init(&arguments);
 for(int i=0;i<3;i++) {values[i].vt=VT_INTEGER;values[i].lVal=i+1;List_InsertAfter(&arguments,values+i,NULL);}
 List_Solidify(&arguments);
 call.OpCode=CALL;call.jumpTargetType=INSTRUCTION_TARGET_FUNCTION;
 call.referenceStorageType=INSTRUCTION_REFERENCE_LIST;call.functionRef=native_marker;
 call.theRefList=&arguments;call.theVal=&result;owner.pCurrentInstruction=&call;
 assert(Instruction_CallReferenceCount(&call)==3);
 assert(Interpreter_Call(&owner)==S_OK && native_arguments==3 && result.lVal==6);
 assert(arguments.size==3 && owner.pCurrentInstruction==&call && !owner.pCurrentCall);
 List_Clear(&arguments);

 /* The postcompile pass visits actual call references and propagates each
    converted value into its constant instruction. No name-service API is
    inferred from this deterministic conversion provider. */
 Instruction mapped_code[6];ScriptVariant originals[3],mapped[3];List refs;
 memset(&owner,0,sizeof(owner));memset(mapped_code,0,sizeof(mapped_code));
 memset(originals,0,sizeof(originals));memset(mapped,0,sizeof(mapped));
 for(int i=0;i<6;i++) mapped_code[i].OpCode=NOOP;
 List_Init(&refs);
 for(int i=0;i<3;i++) {
  originals[i].vt=mapped[i].vt=VT_STR;originals[i].strVal=mapped[i].strVal=100+i;
  mapped_code[i+1].OpCode=CONSTSTR;mapped_code[i+1].theVal=originals+i;
  mapped_code[i+1].theVal2=mapped+i;List_InsertAfter(&refs,mapped+i,NULL);
 }
 List_Solidify(&refs);
 mapped_code[4].OpCode=CALL;mapped_code[4].jumpTargetType=INSTRUCTION_TARGET_FUNCTION;
 mapped_code[4].functionRef=native_marker;mapped_code[4].theRefList=&refs;
 mapped_code[4].referenceStorageType=INSTRUCTION_REFERENCE_LIST;
 mapped_code[5].OpCode=CALL;mapped_code[5].jumpTargetType=INSTRUCTION_TARGET_FUNCTION;
 mapped_code[5].functionRef=native_ignore;
 pack(&owner.theInstructionList,mapped_code,6);owner.instructionStorage=mapped_code;
 script.pinterpreter=&owner;script.initialized=1;
 maps=copies=queries=compiles=0;
 for(int pass=1;pass<=2;pass++) {
  assert(Script_Compile(&script)==1 && compiles==pass);
  assert(maps==pass*mapping && copies==3*pass*mapping && queries==2*pass*mapping);
  for(int i=0;i<3;i++) {
   assert(originals[i].vt==(mapping?VT_INTEGER:VT_STR) && mapped[i].vt==originals[i].vt);
   if(mapping) assert(originals[i].lVal==41+i && mapped[i].lVal==41+i);
   else assert(originals[i].strVal==100+i && mapped[i].strVal==100+i);
  }
  assert(refs.size==3 && owner.theInstructionList.size==6);
 }
 List_Clear(&refs);List_Clear(&owner.theInstructionList);
 assert(!refs.size && !owner.theInstructionList.size);
}
int main(void) {@CHECKS@ puts("early_script_passes=1");return 0;}
'''.replace('@FUNCTIONS@', functions).replace('@CHECKS@', '\n'.join(checks))
        with tempfile.TemporaryDirectory(prefix='early-script-passes-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            includes = [engine, engine / 'source/scriptlib', engine / 'source/preprocessorlib',
                        engine / 'source', engine / 'source/gamelib',
                        ROOT / 'src/port/libretro', ROOT / 'src/glue']
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-fcommon', '-ffunction-sections', '-fdata-sections',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                '-DSAFEALLOC_H=1', '-Dstricmp=strcasecmp', '-Dstrnicmp=strncasecmp',
                '-Wno-deprecated-declarations', '-Wno-pointer-to-int-cast', '-Wno-int-to-pointer-cast',
                *['-I'+str(path) for path in includes], str(unit),
                str(engine / 'source/scriptlib/List.c'), *links, '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=15, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_script_passes=1', run.stdout)
            if os.environ.get('OBOR_PASS_OBSERVATIONS'):
                inputs = [unit, interpreter, instruction, script, engine / 'source/scriptlib/List.c']
                for root in [engine, ROOT / 'src/port/libretro', ROOT / 'src/glue']:
                    inputs += sorted(root.rglob('*.h'))
                bindings = [dict(path=str(path), bytes=path.stat().st_size,
                                 sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                            for path in dict.fromkeys(inputs)]
                Path(os.environ['OBOR_PASS_OBSERVATIONS']).write_text(json.dumps(dict(
                    command=command, contexts=len(rows), inputs=bindings,
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    binary_bytes=binary.stat().st_size,
                    retirement='TemporaryDirectory removes program and binary after this test',
                    header_scope='Conservative source/header bindings, not a claim every header compiled'),
                    indent=2)+'\n')


if __name__ == '__main__':
    unittest.main()
