"""Check precache and model/level command-case contracts through real callers.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-command-case.json'


def cstrings(values):
    return '{' + ','.join(map(json.dumps, values)) + '}'


def dispatch_prefix(source, name):
    body = function(source, name).split('switch(cmd)', 1)[0]
    marker = 'ParseArgs(&arglist,buf+pos,argbuf);'
    if marker not in body:
        raise ValueError('Missing actual parser/dispatch prefix: ' + name)
    return body[body.rindex(marker):]


class EarlyCommandCaseTests(unittest.TestCase):

    def test_grabflip_command_admission(self):
        from test_historical_player import switch_cases
        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-grabflip.json'))
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        entries = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIs(type(row['supports_grabflip']), bool)
            self.assertEqual(row['default_grabflip'] is not None, row['supports_grabflip'])
            if row['supports_grabflip']:
                self.assertIs(type(row['default_grabflip']), int)
                self.assertTrue(0 <= row['default_grabflip'] < 128)
            error = row['unknown_result']
            if not row['supports_grabflip']:
                self.assertIn(error['outcome'], (1, 2))
                self.assertFalse(error['release'])
                self.assertIsInstance(error['format'], str)
            entries.append('{%d,%d,%d,%d,%s}' % (row['revision'], row['supports_grabflip'],
                row['default_grabflip'] if row['default_grabflip'] is not None else -1,
                error['outcome'] if error else 0, json.dumps(error['format'] if error else '')))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        commands = (engine / 'source/gamelib/commands.c').read_text()
        utility = (engine / 'source/utils.c').read_text()
        port = (ROOT / 'src/port/libretro/libretroport.c').read_text()
        loader = function(source, 'load_cached_model')
        _, cases = switch_cases(loader.replace('switch(cmd)', 'switch(model_command)', 1),
                                'load_cached_model', 'model_command')
        macros = []
        for name in ['GET_ARG', 'GET_INT_ARG']:
            found = re.findall(r'(?m)^#define ' + name + r'\(z\)[^\n]*', source)
            self.assertEqual(len(found), 1)
            macros += found
        bodies = '\n'.join(function(source, n) for n in ['ParseArgs', 'findarg', 'obor_legacy_arg',
            'isNumeric', 'getValidInt', 'obor_lookup_command', 'obor_profile_model_command'])
        bodies += '\n' + function(utility, 'lc')
        for name in ['prepareList', 'getCommandlistCommand', 'getModelCommand',
                     'createModelCommandList', 'freeCommandList']:
            bodies += '\n' + function(commands, name) + '\n#undef LIST_ADD\n'
        defaults = re.findall(r'\bnewchar->grabflip\s*=[^;\n]+;', function(source, 'init_model'))
        self.assertEqual(len(defaults), 1)
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
#include "openbor.h"
#include "commands.h"
#undef assert
#undef printf
#undef exit
#undef shutdown
#undef time
#undef pause
uint32_t obor_profile_build;
static unsigned context,active_value,scenario;
#define CHECK(c) do {if(!(c)){fprintf(stderr,"Grabflip revision=%u value=%u scenario=%u line=%d: %s\n",obor_profile_build,active_value,scenario,__LINE__,#c);abort();}}while(0)
#define assert CHECK
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
static int engine_alive,engine_exit_status,frontend_token,outcome,initial_grabflip;
static void *co_frontend=&frontend_token;
static jmp_buf frontend_return;
static char message[512];
static unsigned prints,stops;
void co_switch(void *target) {
 CHECK(target==co_frontend&&!engine_alive&&engine_exit_status==1);++stops;longjmp(frontend_return,1);
}
@STOP@
static void capture_shutdown(int status,const char *format,...) {
 va_list ap;va_start(ap,format);int n=vsnprintf(message,sizeof(message),format,ap);va_end(ap);
 CHECK(status==1&&n>=0&&(size_t)n<sizeof(message));outcome=2;borExit(status);
}
static int capture_printf(const char *format,...) {
 va_list ap;va_start(ap,format);int n=vsnprintf(message,sizeof(message),format,ap);va_end(ap);
 CHECK(n>=0&&(size_t)n<sizeof(message));++prints;outcome=1;return n;
}
void writeToLogFile(const char *format,...) {(void)format;abort();}
#define printf capture_printf
#define shutdown capture_shutdown
@FEEDBACK@
@MACROS@
@BODIES@
static List *modelcmdlist;
static void dispatch(s_model *newchar,char *buf,char *filename) {
 ArgList arglist;char argbuf[MAX_ARG_LEN+1]="";char *command;size_t pos=0;modelCommands cmd;
 @PREFIX@
 switch(cmd) {
 case CMD_MODEL_GRABFLIP:
 @GRABFLIP@
 default:
 @DEFAULT@
 }
 }
}
static void initial_field(s_model *newchar) {@INITIAL@}
#undef shutdown
#undef printf
typedef struct {unsigned revision;int supported,initial,outcome;const char *format;} Row;
static Row rows[]={@ROWS@};
static char *input;
static s_model model;
int main(void) {
 for(context=0;context<sizeof(rows)/sizeof(rows[0]);++context) {
  obor_profile_build=rows[context].revision;modelcmdlist=createModelCommandList();CHECK(modelcmdlist);
  for(active_value=0;active_value<4;++active_value) {
   ++scenario;memset(&model,0,sizeof(model));initial_field(&model);initial_grabflip=model.grabflip;
   if(rows[context].supported) CHECK(model.grabflip==rows[context].initial);
   char text[64];snprintf(text,sizeof(text),"grabflip %u\n",active_value);
   input=strdup(text);CHECK(input);message[0]=0;prints=stops=0;outcome=0;engine_alive=1;engine_exit_status=0;
   if(!setjmp(frontend_return)) dispatch(&model,input,(char *)"data/model.txt");
   if(rows[context].supported) {
    CHECK(!outcome&&!stops&&!prints&&engine_alive&&model.grabflip==(int)active_value);
   } else {
    CHECK(outcome==rows[context].outcome&&model.grabflip==initial_grabflip);
    CHECK(stops==(unsigned)(outcome==2)&&prints==(unsigned)(outcome==1));
    CHECK(engine_alive==(outcome==1));
    char expected[512];int n=snprintf(expected,sizeof(expected),rows[context].format,"grabflip","data/model.txt");
    CHECK(n>=0&&(size_t)n<sizeof(expected)&&!strcmp(message,expected));
   }
   free(input);input=NULL;
  }
  freeCommandList(modelcmdlist);modelcmdlist=NULL;
 }
 printf("early_grabflip=1 contexts=%u cases=%u\n",context,scenario);
 return 0;
}
'''
        for key, value in dict(STOP=function(port, 'borExit'),
            FEEDBACK=function(source, 'obor_profile_file_feedback'), MACROS='\n'.join(macros),
            BODIES=bodies, PREFIX=dispatch_prefix(source, 'load_cached_model'),
            GRABFLIP=cases['CMD_MODEL_GRABFLIP']['body'], DEFAULT=cases['default']['body'],
            INITIAL=defaults[0], ROWS=',\n'.join(entries)).items():
            program = program.replace('@'+key+'@', value)
        with tempfile.TemporaryDirectory(prefix='early-grabflip-') as name:
            work = Path(name)
            unit, obj, binary = work / 'probe.c', work / 'list.o', work / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            version = subprocess.check_output(cc + ['--version'], text=True, timeout=10)
            warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            flags = ['-std=gnu11', '-O1', '-g', '-UNDEBUG', '-DLIBRETRO=1', '-DSAFEALLOC_H=1',
                     '-DOBOR_ENGINE_BUILD='+fixture['engine'], '-fcommon', '-fsigned-char',
                     '-Dstricmp=strcasecmp', '-Dstrnicmp=strncasecmp',
                     '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
            includes = [engine, ROOT / 'src/port/libretro', ROOT / 'src/glue', engine / 'source',
                        *sorted(p for p in (engine / 'source').iterdir() if p.is_dir())]
            flags += ['-I'+str(p) for p in includes]
            build = subprocess.run(cc + flags + ['-c', str(engine / 'source/scriptlib/List.c'), '-o', str(obj)],
                                   capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            build = subprocess.run(cc + flags + ['-Wall', '-Wextra', '-Werror', '-Wno-sign-compare',
                '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-unused-variable',
                '-Wno-implicit-fallthrough', '-Wno-error=deprecated-declarations', *warnings, str(unit), str(obj), *links, '-o', str(binary)],
                capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                 env=sanitizer_environment())
            if os.environ.get('OBOR_GRABFLIP_OBSERVATIONS'):
                import hashlib
                Path(os.environ['OBOR_GRABFLIP_OBSERVATIONS']).write_text(json.dumps(dict(
                    contexts=len(rows), compiler=cc, probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr, scope=fixture['scope'],
                    retirement='TemporaryDirectory removes source/object/binary'), indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_grabflip=1', run.stdout)

    def test_command_allocation_diagnostics_and_controlled_stop(self):
        from test_historical_player import function
        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-command-allocations.json'))
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertTrue(1 <= len(rows) <= 128)
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        entries = []
        for row in rows:
            self.assertEqual(len(row['lines']), 4)
            self.assertEqual(len(row['functions']), 4)
            self.assertTrue(all(type(n) is int and 0 <= n < 1000000 for n in row['lines']))
            self.assertTrue(all(isinstance(n, str) and len(n) < 64 for n in row['functions']))
            self.assertEqual([bool(n) for n in row['lines']], [bool(n) for n in row['functions']])
            entries.append('{%d,{%s},{%s}}' % (
                row['revision'], ','.join(map(str, row['lines'])),
                ','.join(map(json.dumps, row['functions']))))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        port = (ROOT / 'src/port/libretro/libretroport.c').read_text()
        program = r'''
#include <assert.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef exit
#undef shutdown
#undef time
#undef pause
#undef assert
uint32_t obor_profile_build;
static unsigned active_site,scenario;
static void failed(int line,const char *condition) {
 fprintf(stderr,"Command allocation profile=%u site=%u scenario=%u line=%d: %s\n",
         obor_profile_build,active_site,scenario,line,condition);abort();
}
#define CHECK(c) do{if(!(c))failed(__LINE__,#c);}while(0)
static int engine_alive,engine_exit_status,frontend_token;
static void *co_frontend=&frontend_token;static jmp_buf frontend_return;
static unsigned stopped,diagnostics,flushes,allocations,frees;
static char diagnostic[512];static void *owned_table;
void co_switch(void *target) {
 CHECK(target==co_frontend&&!engine_alive&&engine_exit_status==1);
 ++stopped;longjmp(frontend_return,1);
}
static int capture_fprintf(FILE *file,const char *format,...) {
 CHECK(file==stderr);va_list ap;va_start(ap,format);
 int n=vsnprintf(diagnostic,sizeof(diagnostic),format,ap);va_end(ap);
 CHECK(n>=0&&(size_t)n<sizeof(diagnostic));++diagnostics;return n;
}
static int capture_fflush(FILE *file){CHECK(file==stderr);++flushes;return 0;}
#define fprintf capture_fprintf
#define fflush capture_fflush
@STOP@
@ASSERT@
#undef fprintf
#undef fflush
@LC@
static void *table_malloc(size_t size) {
 CHECK(size==sizeof(List)&&!owned_table);++allocations;
 if(scenario)return NULL;
 owned_table=malloc(size);CHECK(owned_table);return owned_table;
}
static void table_free(void *value) {
 CHECK(value&&value==owned_table);++frees;free(value);owned_table=NULL;
}
#define malloc table_malloc
#define free table_free
#include @COMMAND_FILE@
#undef malloc
#undef free
struct expectation {uint32_t revision;unsigned line[4];const char *function[4];};
static const struct expectation contexts[]={@CONTEXTS@};
typedef List *(*constructor)(void);
static constructor constructors[]={createModelCommandList,createModelstxtCommandList,
                                   createLevelCommandList,createLevelOrderCommandList};
int main(void) {
 for(unsigned r=0;r<sizeof(contexts)/sizeof(*contexts);++r) {
  const struct expectation *ctx=&contexts[r];obor_profile_build=ctx->revision;
  for(active_site=0;active_site<4;++active_site)for(scenario=0;scenario<2;++scenario) {
   engine_alive=1;engine_exit_status=0;stopped=diagnostics=flushes=allocations=frees=0;
   diagnostic[0]=0;CHECK(!owned_table);
   if(!setjmp(frontend_return)) {
    List *list=constructors[active_site]();
    CHECK(!scenario&&list==owned_table&&list->size>0&&list->first&&list->last);
    CHECK(allocations==1&&!frees&&!stopped&&!diagnostics&&engine_alive);
    freeCommandList(list);CHECK(frees==1&&!owned_table);
   } else {
    CHECK(scenario==1&&stopped==1&&allocations==1&&!frees&&!owned_table);
#ifndef NDEBUG
    if(ctx->line[active_site]) {
     char expected[512];snprintf(expected,sizeof(expected),
       "source/gamelib/commands.c:%u: %s: Assertion `result' failed.\n",
       ctx->line[active_site],ctx->function[active_site]);
     CHECK(diagnostics==1&&flushes==1&&!strcmp(diagnostic,expected));
    } else CHECK(!diagnostics&&!flushes);
#else
    CHECK(!diagnostics&&!flushes);
#endif
   }
  }
 }
 puts("early_command_allocation=1");return 0;
}
'''
        program = program.replace('@STOP@', function(port, 'borExit')).replace(
            '@ASSERT@', function(port, 'obor_port_assert')).replace(
            '@LC@', function((engine / 'source/utils.c').read_text(), 'lc')).replace(
            '@COMMAND_FILE@', json.dumps(str((engine / 'source/gamelib/commands.c').resolve()))).replace(
            '@CONTEXTS@', ',\n'.join(entries))
        with tempfile.TemporaryDirectory(prefix='early-command-allocation-') as name:
            work = Path(name)
            unit = work / 'probe.c'
            unit.write_text(bind_named_allocation_support(program, engine))
            includes = [engine, engine / 'source', *sorted(p for p in (engine / 'source').iterdir() if p.is_dir()),
                        ROOT / 'src/port/libretro', ROOT / 'src/glue']
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            common = ['-std=gnu99', '-O1', '-g', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                      '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD='+fixture['engine'],
                      '-ffunction-sections', '-fdata-sections', '-fcommon',
                      '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                      '-Wno-deprecated-declarations', '-Wno-sign-compare', '-Wno-unused-parameter']
            common += [flag for path in includes for flag in ('-I', str(path))]
            for assertions_enabled in (True, False):
                binary = work / ('probe-'+str(int(assertions_enabled)))
                command = shlex.split(os.environ.get('HOST_CC', 'cc')) + common + [
                    '-UNDEBUG' if assertions_enabled else '-DNDEBUG', str(unit),
                    str(engine / 'source/scriptlib/List.c'), *links, '-o', str(binary)]
                build = subprocess.run(command, capture_output=True, text=True, timeout=45)
                self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
                run = subprocess.run([str(binary)], capture_output=True, text=True,
                                     timeout=20, env=sanitizer_environment())
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertIn('early_command_allocation=1', run.stdout)

    def test_precache_and_dispatch_case_results(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        self.assertEqual((min(revisions), max(revisions)), tuple(fixture['range']))
        profiles = json.loads((ROOT / 'src/pin.json').read_text())['profiles']
        for profile in contract_profiles(fixture, profiles):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        cache_cases = fixture['cache_cases']
        model_cases, level_cases = fixture['model_cases'], fixture['level_cases']
        self.assertTrue(0 < len(cache_cases) <= 16)
        self.assertEqual(len(model_cases), len(level_cases))
        self.assertTrue(0 < len(model_cases) <= 16)
        for case in cache_cases:
            self.assertLess(len(case['text']), 128)
            self.assertIs(type(case['check_static_tail']), bool)
        for value in model_cases + level_cases:
            self.assertTrue(isinstance(value, str) and len(value) < 128)
        arrays, checks = [], []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            self.assertEqual(len(row['cache_names']), len(cache_cases))
            for key in ['model_text', 'level_text', 'model_matches', 'level_matches']:
                self.assertEqual(len(row[key]), len(model_cases))
            for key in ['model_matches', 'level_matches']:
                self.assertTrue(all(type(value) is bool for value in row[key]))
            for key in ['cache_names', 'model_text', 'level_text']:
                self.assertTrue(all(isinstance(value, str) and len(value) < 128 for value in row[key]))
            label = 'expected_' + str(row['revision'])
            arrays.append('static const expectation %s={%s,%s,%s,%d,%d};' % (
                label, cstrings(row['cache_names']), cstrings(row['model_text']),
                cstrings(row['level_text']),
                sum(int(value) << i for i, value in enumerate(row['model_matches'])),
                sum(int(value) << i for i, value in enumerate(row['level_matches']))))
            checks.append('check_profile(%d,&%s);' % (row['revision'], label))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE',
                                     ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        header = (engine / 'openbor.h').read_text()
        commands = (engine / 'source/gamelib/commands.c').read_text()
        arglist = re.findall(r'typedef struct ArgList\s*\{[^}]+}\s*ArgList;', header)
        cache = re.findall(r'typedef struct\s*\{[^{}]*}\s*s_modelcache;', header)
        self.assertEqual(len(arglist), 1)
        self.assertEqual(len(cache), 1)
        max_arg = re.findall(r'(?m)^#define\s+MAX_ARG_LEN\s+(\d+)\b', header)
        self.assertEqual(max_arg, [str(fixture['max_arg_len'])])
        macros = re.findall(r'(?m)^#define GET_ARG\(z\)[^\n]*', source)
        self.assertEqual(len(macros), 1)
        bodies = '\n'.join(function(source, name) for name in
                           ['ParseArgs', 'findarg', 'obor_legacy_arg', 'obor_lookup_command'])
        utility = (engine / 'source/utils.c').read_text()
        bodies += '\n' + '\n'.join(function(utility, name) for name in ['lc', 'getNewLineStart'])
        names = ['getCommandlistCommand', 'getModelCommand', 'getModelstxtCommand',
                 'getLevelCommand', 'getLevelOrderCommand', 'prepareList',
                 'createModelCommandList', 'createLevelCommandList',
                 'createModelstxtCommandList', 'createLevelOrderCommandList', 'freeCommandList']
        bodies += '\n' + '\n'.join(function(commands, name) + '\n#undef LIST_ADD' for name in names)
        bodies += '\n' + function(source, 'obor_profile_model_command')
        cache_bodies = '\n'.join(function(source, name) for name in
                                 ['_peek_model_name', 'prepare_cache_map', 'obor_prepare_cache_map',
                                  'cache_model', 'free_modelcache'])
        program = r'''
#include <assert.h>
#include <ctype.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "commands.h"
#define MAX_ARG_LEN @MAX_ARG_LEN@
@ARGLIST@
typedef struct opaque_model s_model;
@CACHE_RECORD@
uint32_t obor_profile_build;
List *modelcmdlist,*levelcmdlist;
static s_modelcache *model_cache;
static int models_cached,cache_map_max_items;
static const char *contents;
static int buffer_pakfile(char *path,char **buffer,size_t *size) {
 assert(!strcmp(path,"fixture.txt") && models_cached==0);
 *size=strlen(contents);*buffer=malloc(*size+1);assert(*buffer);
 memcpy(*buffer,contents,*size+1);return 1;
}
static void cache_shutdown(int code,const char *format,...) {
 (void)code;(void)format;assert(!"Unexpected cache allocation failure");abort();
}
@MACROS@
@BODIES@
#define shutdown cache_shutdown
@CACHE_BODIES@
#undef shutdown
typedef struct {const char *text;int check_static_tail;} cache_case;
static const cache_case cache_cases[]={@CACHE_CASES@};
static const char *model_cases[]=@MODEL_CASES@,*level_cases[]=@LEVEL_CASES@;
typedef struct {
 const char *cache_names[@CACHE_COUNT@],*model_text[@COMMAND_COUNT@],*level_text[@COMMAND_COUNT@];
 unsigned model_mask,level_mask;
} expectation;
@ARRAYS@
static modelCommands dispatch_model(char *buf,char *after) {
 ArgList arglist;char argbuf[MAX_ARG_LEN+1]={0},*command="";size_t pos=0;
 modelCommands cmd=(modelCommands)0;
 @MODEL_PREFIX@
 }
 strcpy(after,command);return cmd;
}
static levelCommands dispatch_level(char *buf,char *after) {
 ArgList arglist;char argbuf[MAX_ARG_LEN+1]={0},*command="";size_t pos=0;
 levelCommands cmd=(levelCommands)0;
 @LEVEL_PREFIX@
 strcpy(after,command);return cmd;
}
static void unique_keys(List *list) {
 for(Node *a=list->first;a;a=a->next)for(Node *b=a->next;b;b=b->next)
  assert(stricmp(a->name,b->name)!=0);
}
static void check_cursor_and_case_helpers(void) {
 /* Absolute next positions, independently transcribed from the original
    callers' two loops. Check every starting position, including the NUL. */
 static const struct {const char *text;size_t next[16];} lines[]={
  {"",{0}},
  {"abc",{3,3,3,3}},
  {"\r\n\r",{3,3,3,3}},
  {"one\r\n\r\ntwo\n",{7,7,7,7,7,7,7,11,11,11,11,11}},
  {"one\n \n#x\r\nend",{4,4,4,4,6,6,10,10,10,10,13,13,13,13}}
 };
 for(size_t c=0;c<sizeof(lines)/sizeof(*lines);++c) {
  size_t size=strlen(lines[c].text);char input[16];strcpy(input,lines[c].text);
  for(size_t pos=0;pos<=size;++pos) {
   assert(pos+getNewLineStart(input+pos)==lines[c].next[pos]);
   assert(!strcmp(input,lines[c].text));
  }
 }
 char tail[]={'a',0,'Z','\n',0};
 assert(getNewLineStart(tail)==1 && getNewLineStart(tail+1)==0);
 assert(tail[2]=='Z' && tail[3]=='\n');
 /* lc takes a byte count rather than a string length; only defined ASCII
    ctype inputs are original-behavior controls. */
 char bytes[]={'A',0,'B','Z','q','!',0},before[sizeof(bytes)];
 memcpy(before,bytes,sizeof(bytes));lc(bytes,0);assert(!memcmp(bytes,before,sizeof(bytes)));
 lc(bytes,3);assert(!memcmp(bytes,(char[]){'a',0,'b','Z','q','!',0},sizeof(bytes)));
 lc(bytes,6);assert(!memcmp(bytes,(char[]){'a',0,'b','z','q','!',0},sizeof(bytes)));
}
static void check_profile(unsigned revision,const expectation *expected) {
 obor_profile_build=revision;
 check_cursor_and_case_helpers();
 modelcmdlist=createModelCommandList();levelcmdlist=createLevelCommandList();
 unique_keys(modelcmdlist);unique_keys(levelcmdlist);
 for(size_t i=0;i<sizeof(cache_cases)/sizeof(cache_cases[0]);i++) {
  char seed[]="ABCDEFGHIJKL\n";assert(!strcmp(findarg(seed,0),"ABCDEFGHIJKL"));
  assert(!model_cache && !models_cached);cache_map_max_items=0;contents=cache_cases[i].text;
  cache_model("Listed","fixture.txt",1);
  assert(models_cached==1 && !strcmp(model_cache[0].name,expected->cache_names[i]));
  assert(!strcmp(model_cache[0].path,"fixture.txt") && model_cache[0].loadflag==1);
  if(cache_cases[i].check_static_tail) {
   char end[]="end";assert(!strcmp(findarg(end,0),"endDEFGHIJKL"));
  }
  free_modelcache();assert(!model_cache && !models_cached);
 }
 for(size_t i=0;i<sizeof(model_cases)/sizeof(model_cases[0]);i++) {
  char input[128],after[MAX_ARG_LEN+1];strcpy(input,model_cases[i]);
  modelCommands model=dispatch_model(input,after);
  assert(model==((expected->model_mask&(1u<<i))?CMD_MODEL_NAME:(modelCommands)0));
  assert(!strcmp(after,expected->model_text[i]));
  strcpy(input,level_cases[i]);levelCommands level=dispatch_level(input,after);
  assert(level==((expected->level_mask&(1u<<i))?CMD_LEVEL_AT:(levelCommands)0));
  assert(!strcmp(after,expected->level_text[i]));
 }
 /* Regression controls for untouched physical helper paths, not historical
    acceptance of these other namespaces. */
 List *models=createModelstxtCommandList(),*order=createLevelOrderCommandList();
 char load[]="LoAd",set[]="SeT";
 assert(getModelstxtCommand(models,load)==CMD_MODELSTXT_LOAD && !strcmp(load,"load"));
 assert(getLevelOrderCommand(order,set)==CMD_LEVELORDER_SET && !strcmp(set,"set"));
 freeCommandList(models);freeCommandList(order);
 assert(!obor_lookup_command(NULL,"name",0));
 assert(!obor_lookup_command(modelcmdlist,NULL,1));
 freeCommandList(modelcmdlist);freeCommandList(levelcmdlist);
}
int main(void) {@CHECKS@ puts("early_command_case=1");return 0;}
'''
        replacements = dict(MAX_ARG_LEN=max_arg[0], ARGLIST=arglist[0], CACHE_RECORD=cache[0],
                            MACROS=macros[0], BODIES=bodies, CACHE_BODIES=cache_bodies,
                            CACHE_CASES=','.join('{%s,%d}' % (json.dumps(case['text']), case['check_static_tail'])
                                                 for case in cache_cases),
                            MODEL_CASES=cstrings(model_cases), LEVEL_CASES=cstrings(level_cases),
                            CACHE_COUNT=str(len(cache_cases)), COMMAND_COUNT=str(len(model_cases)),
                            ARRAYS='\n'.join(arrays), CHECKS='\n'.join(checks),
                            MODEL_PREFIX=dispatch_prefix(source, 'load_cached_model'),
                            LEVEL_PREFIX=dispatch_prefix(source, 'load_level'))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-command-case-') as name:
            work = Path(name)
            unit, obj, binary = work / 'probe.c', work / 'list.o', work / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            common = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1',
                      '-Dstricmp=strcasecmp', '-Dstrnicmp=strncasecmp', '-fsanitize=address,undefined',
                      '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                      '-I', str(engine / 'source/scriptlib'), '-I', str(engine / 'source/gamelib')]
            build = subprocess.run(cc + common + ['-c', str(engine / 'source/scriptlib/List.c'),
                                                  '-o', str(obj)], capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            build = subprocess.run(cc + common + ['-Wall', '-Wextra', '-Werror',
                                   '-Wno-error=deprecated-declarations', '-Wno-sign-compare',
                                   '-Wno-implicit-fallthrough', str(unit), str(obj), *links,
                                   '-o', str(binary)], capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=15, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_command_case=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
