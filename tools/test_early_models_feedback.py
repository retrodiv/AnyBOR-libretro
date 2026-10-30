"""Check historical file-command feedback and the model-list zero-enum alias.

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
from test_early_command_case import dispatch_prefix
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-models-feedback.json'


class EarlyModelsFeedbackTests(unittest.TestCase):
    def test_script_load_labels_and_feedback(self):
        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-model-script-feedback.json'))
        rows, labels = fixture['sources'], fixture['labels']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        self.assertTrue(1 <= len(labels) <= 64)
        self.assertEqual(len(labels), len(set(labels)))
        self.assertTrue(all(isinstance(label, str) and re.fullmatch(r'[A-Za-z_]+', label) for label in labels))
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        entries = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(len(row['messages']), len(labels))
            self.assertTrue(all(isinstance(message, str) and len(message) < 512 for message in row['messages']))
            entries.append('{%d,{%s}}' % (row['revision'], ','.join(map(json.dumps, row['messages']))))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        port = (ROOT / 'src/port/libretro/libretroport.c').read_text()
        macros = re.findall(r'(?m)^#define GET_ARGP\(z\) [^\n]+', source)
        self.assertEqual(len(macros), 1)
        program = r'''
#include <assert.h>
#include <setjmp.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef assert
#undef exit
#undef shutdown
#undef time
#undef pause
uint32_t obor_profile_build;
static unsigned revision_at,script_at,path_at,scenario,phase,stops;
static char message[512];
#define CHECK(c) do {if(!(c)){fprintf(stderr,"Model script feedback revision=%u script=%u scenario=%u phase=%u line=%d: %s\n%s\n",obor_profile_build,script_at,scenario,phase,__LINE__,#c,message);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
static int engine_alive,engine_exit_status,frontend_token;
static void *co_frontend=&frontend_token;static jmp_buf frontend_return;
static Script script;static ArgList arguments;
static const char *const labels[]={@LABELS@};
static const char *const paths[]={"data/script.c","scripts/events/entry.c"};
static char filename[]="data/model.txt",input_line[256];
void co_switch(void *target) {
 CHECK(target==co_frontend&&!engine_alive&&engine_exit_status==1);
 ++stops;longjmp(frontend_return,1);
}
@STOP@
static void capture_shutdown(int status,const char *format,...) {
 CHECK(status==1&&phase==2);++phase;
 va_list ap;va_start(ap,format);int n=vsnprintf(message,sizeof(message),format,ap);va_end(ap);
 CHECK(n>=0&&(size_t)n<sizeof(message));borExit(status);
}
void Script_Init(Script *object,char *name,int first) {
 CHECK(object==&script&&!strcmp(name,labels[script_at])&&!first&&phase==0);++phase;
}
int load_script(Script *object,char *path) {
 CHECK(object==&script&&!strcmp(path,paths[path_at])&&phase==1);++phase;return !scenario;
}
int Script_Compile(Script *object) {CHECK(object==&script&&phase==2);++phase;return 1;}
@FINDARG@
@LEGACY_ARG@
@ARG_MACRO@
#define shutdown capture_shutdown
@HELPER@
#undef shutdown
struct expectation {uint32_t revision;const char *messages[@LABEL_COUNT@];};
static const struct expectation contexts[]={@CONTEXTS@};
int main(void) {
 for(revision_at=0;revision_at<sizeof(contexts)/sizeof(*contexts);++revision_at)
 for(script_at=0;script_at<sizeof(labels)/sizeof(*labels);++script_at)
 for(path_at=0;path_at<sizeof(paths)/sizeof(*paths);++path_at)
 for(scenario=0;scenario<2;++scenario) {
  obor_profile_build=contexts[revision_at].revision;
  phase=stops=0;engine_alive=1;engine_exit_status=0;message[0]=0;
  memset(&script,0,sizeof(script));memset(&arguments,0,sizeof(arguments));
  int n=snprintf(input_line,sizeof(input_line),"%s %s\n",labels[script_at],paths[path_at]);CHECK(n>0&&(size_t)n<sizeof(input_line));
  arguments.count=2;arguments.args[0]=(char *)labels[script_at];arguments.args[1]=(char *)paths[path_at];
  arguments.arglen[0]=strlen(labels[script_at]);arguments.arglen[1]=strlen(paths[path_at]);arguments.source=input_line;
  if(!setjmp(frontend_return)) {
   lcmHandleCommandScripts(&arguments,&script,(char *)labels[script_at],filename);
   CHECK(!scenario&&phase==3&&!stops&&engine_alive&&!message[0]);
  } else {
   char expected[512];n=snprintf(expected,sizeof(expected),contexts[revision_at].messages[script_at],paths[path_at],filename);
   CHECK(n>=0&&(size_t)n<sizeof(expected)&&scenario==1&&phase==3&&stops==1);
   CHECK(!strcmp(message,expected));
  }
 }
 puts("early_model_script_feedback=1");return 0;
}
'''
        for key, value in dict(STOP=function(port, 'borExit'), FINDARG=function(source, 'findarg'),
                               LEGACY_ARG=function(source, 'obor_legacy_arg'), ARG_MACRO=macros[0],
                               HELPER=function(source, 'lcmHandleCommandScripts'),
                               LABEL_COUNT=str(len(labels)), LABELS=','.join(map(json.dumps, labels)),
                               CONTEXTS=',\n'.join(entries)).items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-model-script-feedback-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            includes = [engine, ROOT / 'src/port/libretro', ROOT / 'src/glue', engine / 'source',
                        *sorted(p for p in (engine / 'source').iterdir() if p.is_dir())]
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
            warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
            flags = ['-std=gnu11', '-O1', '-g', '-UNDEBUG', '-DLIBRETRO=1',
                     '-DOBOR_ENGINE_BUILD='+fixture['engine'], '-fsigned-char', '-fcommon',
                     '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-error=deprecated-declarations', '-Wno-sign-compare', '-Wno-unused-parameter',
                     '-Wno-unused-function', '-Wno-unused-variable', *warnings]
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            build = subprocess.run(compiler + flags + ['-I'+str(p) for p in includes] +
                                   [str(unit), *links, '-o', str(binary)], capture_output=True,
                                   text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20, env=sanitizer_environment())
            if os.environ.get('OBOR_MODEL_SCRIPT_FEEDBACK_OBSERVATIONS'):
                Path(os.environ['OBOR_MODEL_SCRIPT_FEEDBACK_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=compiler, contexts=len(rows), labels=len(labels), cases_per_context=len(labels)*4,
                    probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    model_sha256=hashlib.sha256(source.encode()).hexdigest(), returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr, scope=fixture['scope'],
                    retirement='TemporaryDirectory removes source and binary'), indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_model_script_feedback=1', run.stdout)

    def test_unknown_commands_and_idle_count_sequences(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {r['revision'] for r in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertEqual((min(revisions), max(revisions)), tuple(fixture['range']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        header = (engine / 'openbor.h').read_text()
        commands = (engine / 'source/gamelib/commands.c').read_text()
        utility = (engine / 'source/utils.c').read_text()
        args = re.findall(r'typedef struct ArgList\s*\{[^}]+}\s*ArgList;', header)
        self.assertEqual(len(args), 1)
        self.assertEqual(re.findall(r'(?m)^#define\s+MAX_IDLES\s+(\d+)\b', header), [str(fixture['minimum'])])
        macros = []
        for name in ['GET_ARG', 'GET_INT_ARG']:
            values = re.findall(r'(?m)^#define ' + name + r'\(z\)[^\n]*', source)
            self.assertEqual(len(values), 1)
            macros += values
        idle = re.findall(r'case CMD_MODELSTXT_MAXIDLES:\s*([\s\S]*?)\bbreak;',
                          function(source, 'load_models'))
        self.assertEqual(len(idle), 1)
        loader = function(source, 'load_models')
        pass_initializer = re.findall(r'\bint\s+model_pass\s*=[^;]+;', loader)
        self.assertEqual(len(pass_initializer), 1)
        self.assertRegex(loader, r'model_pass\s*=\s*1\s*;\s*goto parse_model_pass;')
        bodies = '\n'.join(function(source, n) for n in [
            'ParseArgs', 'findarg', 'obor_legacy_arg', 'obor_lookup_command', 'isNumeric', 'getValidInt'])
        bodies += '\n' + function(utility, 'lc')
        for name in ['getCommandlistCommand', 'getModelstxtCommand', 'prepareList',
                     'createModelstxtCommandList', 'freeCommandList']:
            bodies += '\n' + function(commands, name) + '\n#undef LIST_ADD\n'
        cases, arrays, checks = fixture['cases'], [], []
        callers = fixture['callers']
        self.assertEqual(callers, ['load_menu_txt', 'load_cached_model', 'selectplayer', 'keyboard_setup'])
        wrappers = []
        for name in callers:
            calls = re.findall(r'obor_profile_file_feedback\(command, filename, [^;]+;', function(source, name))
            self.assertEqual(len(calls), 1)
            wrappers.append('static void call_' + name + '(char *command,char *filename) {' + calls[0] + '}')
        self.assertTrue(0 < len(fixture['files']) <= 4)
        self.assertTrue(all(isinstance(name, str) and 0 < len(name) < 128 for name in fixture['files']))
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['function_sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(len(row['results']), len(cases))
            values = []
            for result in row['results']:
                self.assertIn(result['outcome'], [0, 1, 2])
                self.assertIs(type(result['max_idles']), int)
                self.assertIn(result['loads'], [0, 1])
                values.append('{%d,%d,%d,%s}' % (
                    result['outcome'], result['max_idles'], result['loads'], json.dumps(result['diagnostic'])))
            label = 'expected_' + str(row['revision'])
            arrays.append('static const expectation %s[]={%s};' % (label, ','.join(values)))
            checks.append('check(%d,%s);' % (row['revision'], label))
            self.assertEqual(len(row['file_results']), len(callers))
            file_values = []
            for result in row['file_results']:
                self.assertIn(result['outcome'], [1, 2])
                self.assertIs(type(result['release']), bool)
                file_values.append('{%d,%d,%s}' % (result['outcome'], result['release'],
                                                 json.dumps(result['format'])))
            label = 'file_expected_' + str(row['revision'])
            arrays.append('static const file_expectation %s[]={%s};' % (label, ','.join(file_values)))
            checks.append('check_files(%d,%s);' % (row['revision'], label))
        program = r'''
#include <assert.h>
#include <ctype.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "commands.h"
#define MAX_ARG_LEN @MAX_ARG_LEN@
#define MAX_IDLES @MINIMUM@
@ARGLIST@
uint32_t obor_profile_build;
List *modelstxtcmdlist;
static jmp_buf stopped;
static int max_idles,outcome,loads;
static char diagnostic[512];
static int warning(const char *format,...) {
 va_list args;va_start(args,format);int size=vsnprintf(diagnostic,sizeof(diagnostic),format,args);
 va_end(args);assert(size>=0 && (size_t)size<sizeof(diagnostic));outcome=1;return size;
}
static void engine_stop(int code,const char *format,...) {
 va_list args;va_start(args,format);int size=vsnprintf(diagnostic,sizeof(diagnostic),format,args);
 va_end(args);assert(code==1 && size>=0 && (size_t)size<sizeof(diagnostic));
 outcome=2;longjmp(stopped,1);
}
#define printf warning
#define shutdown engine_stop
@HELPER@
#undef shutdown
#undef printf
@MACROS@
@BODIES@
static void dispatch(char *buf,char *filename) {
 @PASS_INITIALIZER@
 /* A single-line command window follows the loader's two phase values.
    The complete loader test separately covers work between the phases. */
 for(;model_pass<2;++model_pass) {
 ArgList arglist;char argbuf[MAX_ARG_LEN+1]={0},*command="";size_t pos=0;
 int limit_command;
 modelstxtCommands cmd=(modelstxtCommands)0;
#define printf warning
#define shutdown engine_stop
 @PREFIX@
#undef shutdown
#undef printf
 switch(cmd) {
 case CMD_MODELSTXT_MAXIDLES:
 @IDLE@
 break;
 case CMD_MODELSTXT_LOAD:loads++;break;
 default:abort();
 }
 model_next_line:;
 }
}
typedef struct {int outcome,max_idles,loads;const char *diagnostic;} expectation;
typedef struct {int outcome,release;const char *format;} file_expectation;
static char *buf;
@WRAPPERS@
static void (*file_callers[])(char *,char *)={@CALLERS@};
static const char *cases[]={@CASES@};
static char *filenames[]={@FILENAMES@};
@ARRAYS@
static void check(unsigned revision,const expectation *expected) {
 obor_profile_build=revision;modelstxtcmdlist=createModelstxtCommandList();assert(modelstxtcmdlist);
 for(Node *a=modelstxtcmdlist->first;a;a=a->next) for(Node *b=a->next;b;b=b->next)
  assert(stricmp(a->name,b->name)!=0);
 for(size_t file=0;file<sizeof(filenames)/sizeof(filenames[0]);file++)
 for(size_t i=0;i<sizeof(cases)/sizeof(cases[0]);i++) {
  char input[MAX_ARG_LEN+1],baseline[]="maxidles 20\n";
  char *filename=filenames[file];
  max_idles=MAX_IDLES;outcome=loads=0;diagnostic[0]=0;
  if(!setjmp(stopped)) dispatch(baseline,filename);else abort();
  assert(max_idles==20 && !outcome && !loads);
  assert(strlen(cases[i])<sizeof(input));strcpy(input,cases[i]);
  if(!setjmp(stopped)) dispatch(input,filename);
  assert(outcome==expected[i].outcome && max_idles==expected[i].max_idles && loads==expected[i].loads);
  char message[512];
  if(expected[i].diagnostic[0]) {
   int count=snprintf(message,sizeof(message),"%s%s'!",expected[i].diagnostic,filename);
   assert(count>=0 && (size_t)count<sizeof(message));
  } else message[0]=0;
  assert(!strcmp(diagnostic,message));
 }
 freeCommandList(modelstxtcmdlist);modelstxtcmdlist=NULL;
}
static void check_files(unsigned revision,const file_expectation *expected) {
 obor_profile_build=revision;
 for(volatile size_t i=0;i<sizeof(file_callers)/sizeof(file_callers[0]);i++)
 for(volatile size_t file=0;file<sizeof(filenames)/sizeof(filenames[0]);file++) {
  buf=malloc(8);assert(buf);buf[0]=0;outcome=0;diagnostic[0]=0;
  if(!setjmp(stopped)) file_callers[i]((char *)"NoSuchCommand",filenames[file]);
  assert(outcome==expected[i].outcome);
  assert((buf==NULL)==expected[i].release);
  char message[512];int n=snprintf(message,sizeof(message),expected[i].format,"NoSuchCommand",filenames[file]);
  assert(n>=0 && (size_t)n<sizeof(message) && !strcmp(diagnostic,message));
  free(buf);buf=NULL;
  for(volatile int empty=0;empty<2;empty++) {
   buf=malloc(8);assert(buf);buf[0]=0;outcome=0;diagnostic[0]=0;
   if(!setjmp(stopped)) file_callers[i](empty?NULL:(char *)"",filenames[file]);else abort();
   assert(!outcome && !diagnostic[0] && buf);free(buf);buf=NULL;
  }
 }
}
int main(void) {@CHECKS@ puts("early_models_feedback=1");return 0;}
'''
        replacements = dict(MAX_ARG_LEN=str(fixture['max_arg_len']), MINIMUM=str(fixture['minimum']),
                            ARGLIST=args[0], MACROS='\n'.join(macros), BODIES=bodies,
                            HELPER=function(source, 'obor_profile_file_feedback'),
                            WRAPPERS='\n'.join(wrappers),
                            CALLERS=','.join('call_' + name for name in callers),
                            PREFIX=dispatch_prefix(source, 'load_models'), IDLE=idle[0],
                            PASS_INITIALIZER=pass_initializer[0],
                            CASES=','.join(json.dumps(case) for case in cases),
                            FILENAMES=','.join(json.dumps(name) for name in fixture['files']),
                            ARRAYS='\n'.join(arrays), CHECKS='\n'.join(checks))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-models-feedback-') as name:
            work = Path(name)
            unit, obj, binary = work / 'probe.c', work / 'list.o', work / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            common = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-Dstricmp=strcasecmp',
                      '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                      '-I' + str(engine / 'source/scriptlib'), '-I' + str(engine / 'source/gamelib')]
            build = subprocess.run(cc + common + ['-c', str(engine / 'source/scriptlib/List.c'), '-o', str(obj)],
                                   capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            build = subprocess.run(cc + common + ['-Wall', '-Wextra', '-Werror', '-Wno-sign-compare',
                                   '-Wno-error=deprecated-declarations', '-Wno-implicit-fallthrough',
                                   str(unit), str(obj), *([] if sys.platform == 'darwin' else ['-no-pie']),
                                   '-o', str(binary)], capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=15, env=sanitizer_environment())
            if os.environ.get('OBOR_MODELS_FEEDBACK_OBSERVATIONS'):
                Path(os.environ['OBOR_MODELS_FEEDBACK_OBSERVATIONS']).write_text(json.dumps({
                    'compiler': cc, 'flags': common, 'contexts': len(rows), 'cases': len(cases),
                    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                    'probe_sha256': hashlib.sha256(program.encode()).hexdigest(),
                    'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                    'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr,
                    'retirement': 'TemporaryDirectory removes source/object/binary',
                }, indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_models_feedback=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
