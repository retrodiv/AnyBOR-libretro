"""Check source-defined level-list command feedback and error presentation.

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
from test_historical_player import function, switch_cases

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-levelorder-feedback.json'


class EarlyLevelOrderFeedbackTests(unittest.TestCase):
    def test_command_feedback_and_error_routes(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertEqual((min(revisions), max(revisions)), tuple(fixture['range']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source, header = ((engine / name).read_text() for name in ['openbor.c', 'openbor.h'])
        commands = (engine / 'source/gamelib/commands.c').read_text()
        utility = (engine / 'source/utils.c').read_text()
        arglist = re.findall(r'typedef struct ArgList\s*\{[^}]+}\s*ArgList;', header)
        self.assertEqual(len(arglist), 1)
        self.assertEqual(re.findall(r'(?m)^#define\s+MAX_DIFFICULTIES\s+(\d+)\b', header),
                         [str(fixture['max_difficulties'])])
        macros = re.findall(r'(?m)^#define GET_ARG\(z\)[^\n]*', source)
        self.assertEqual(len(macros), 1)
        method = function(source, 'load_levelorder')
        # Name only the outer selector for extraction: nested command switches
        # remain intact and cannot be mistaken for sibling cases.
        method, cases = switch_cases(method.replace('switch(cmd)', 'switch(order_command)', 1),
                                     'load_levelorder', 'order_command')
        guards = {name: case['body'].split('CHKDEF;', 1)[0] + 'CHKDEF;'
                  for name, case in cases.items() if 'CHKDEF;' in case['body']}
        self.assertEqual(sorted(guards), fixture['guarded_commands'])
        self.assertTrue(all(not re.sub(r'//[^\n]*|/\*.*?\*/', '', text.split('CHKDEF;')[0], flags=re.S).strip()
                            for text in guards.values()))
        check_macro = re.findall(r'(?m)^#define CHKDEF[^\n]*', method)
        self.assertEqual(len(check_macro), 1)
        self.assertEqual(re.findall(r'\bint line = 0;', method), ['int line = 0;'])
        increments = re.findall(r'(?m)^\s*line\+\+;', method)
        self.assertEqual(len(increments), 1)
        set_guard = cases['CMD_LEVELORDER_SET']['body'].split('++num_difficulties;', 1)[0]
        next_guards = {name: cases[name]['body'].split('levelorder[current_set][num_levels[current_set]-1]->gonext', 1)[0]
                       for name in ['CMD_LEVELORDER_NEXT', 'CMD_LEVELORDER_END']}
        for name, text in next_guards.items():
            self.assertIn('if(num_levels[current_set]<1)', text)
            # Only the complete prerequisite/error checks precede this write.
            self.assertTrue(text.rstrip().endswith('}'))
        end = method[method.rindex('if(current_set<0)'):method.rindex('}')]
        self.assertIn('lCleanup:', end)
        bodies = '\n'.join(function(source, name) for name in [
            'ParseArgs', 'findarg', 'obor_legacy_arg', 'obor_lookup_command'])
        bodies += '\n' + function(utility, 'lc')
        for name in ['getCommandlistCommand', 'getLevelOrderCommand', 'prepareList',
                     'createLevelOrderCommandList', 'freeCommandList']:
            bodies += '\n' + function(commands, name) + '\n#undef LIST_ADD\n'
        arrays, checks = [], []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['function_sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(len(row['results']), len(fixture['cases']))
            values = []
            for case, result in zip(fixture['cases'], row['results']):
                self.assertIn(result['outcome'], [0, 1, 2])
                self.assertIs(type(result['released']), bool)
                label = case['constant'] or '0'
                self.assertRegex(label, r'^(?:0|CMD_LEVELORDER_[A-Z0-9_]+)$')
                values.append('{%d,%d,%s,%s,%s}' % (result['outcome'], result['released'], label,
                              json.dumps(result['diagnostic']), json.dumps(result['command'])))
            label = 'expected_' + str(row['revision'])
            arrays.append('static const expectation %s[]={%s};' % (label, ','.join(values)))
            checks.append('check(%d,%s,%d,%s);' % (row['revision'], label, row['wrapped_errors'],
                                                 json.dumps(row['too_many'])))
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
#define MAX_DIFFICULTIES @MAX_DIFFICULTIES@
@ARGLIST@
@MACROS@
uint32_t obor_profile_build;
List *levelordercmdlist;
static jmp_buf stopped;
static int outcome,recognized,released;
static char diagnostic[512],retained_command[128],*owned;
static void release(void *pointer) {assert(pointer==owned && !released);released=1;free(pointer);}
static int warning(const char *format,...) {
 va_list args;va_start(args,format);int size=vsnprintf(diagnostic,sizeof(diagnostic),format,args);
 va_end(args);assert(size>=0 && (size_t)size<sizeof(diagnostic));outcome=1;return size;
}
static void engine_stop(int code,const char *format,...) {
 va_list args;va_start(args,format);int size=vsnprintf(diagnostic,sizeof(diagnostic),format,args);
 va_end(args);assert(code==1 && size>=0 && (size_t)size<sizeof(diagnostic));
 outcome=2;longjmp(stopped,1);
}
@BODIES@
#define free release
#define printf warning
#define shutdown engine_stop
@HELPERS@
static void dispatch(void) {
 char *buf=owned,*command="",argbuf[MAX_ARG_LEN+1]={0};size_t pos=0;ArgList arglist;
 levelOrderCommands cmd=(levelOrderCommands)0;
 @PREFIX@
 recognized=cmd;
 assert(strlen(command)<sizeof(retained_command));strcpy(retained_command,command);
 switch(cmd) {
 case CMD_LEVELORDER_BLENDFX:case CMD_LEVELORDER_SET:case CMD_LEVELORDER_SCOREFORMAT:case CMD_LEVELORDER_P1LIFE:break;
 default:@DEFAULT@
 }
}
static void error_route(int kind,int current_set,int num_difficulties,int levels,char *filename,int iterations) {
 static const char *defaulterr="Error in level order: a set must be specified.";
 char *errormessage=NULL,*buf=owned;int num_levels[]={levels};
 int line = 0;
 for(int i=0;i<iterations;i++) {@LINE_INCREMENT@}
 @CHKDEF@
 switch(kind) {
 @GUARDS@
 case @SET_KIND@: @SET_GUARD@ break;
 @NEXT_GUARDS@
 default:break;
 }
 @END@
}
#undef CHKDEF
#undef shutdown
#undef printf
#undef free
typedef struct {int outcome,released,command;const char *diagnostic,*text;} expectation;
static const char *cases[]={@CASES@};
static char *filenames[]={@FILENAMES@};
@ARRAYS@
static void reset(const char *input) {
 outcome=recognized=released=0;diagnostic[0]=retained_command[0]=0;
 owned=malloc(strlen(input)+1);assert(owned);strcpy(owned,input);
}
static void finish(void) {if(!released)free(owned);owned=NULL;}
static void check(unsigned revision,const expectation *expected,int wrapped,const char *too_many) {
 obor_profile_build=revision;levelordercmdlist=createLevelOrderCommandList();assert(levelordercmdlist);
 for(size_t i=0;i<sizeof(cases)/sizeof(cases[0]);i++) {
  reset(cases[i]);if(!setjmp(stopped))dispatch();
  assert(outcome==expected[i].outcome && released==expected[i].released && recognized==expected[i].command);
  assert(!strcmp(diagnostic,expected[i].diagnostic) && !strcmp(retained_command,expected[i].text));finish();
 }
 for(volatile size_t file=0;file<sizeof(filenames)/sizeof(filenames[0]);file++)
 for(volatile int kind=0;kind<@ERROR_KINDS@;kind++)
 for(volatile int valid=0;valid<2;valid++) {
  int is_set=kind==@SET_KIND@,is_next=kind>@SET_KIND@;
  volatile int current_set=valid?0:(is_set || is_next?0:-1);
  const char *volatile message=is_set?too_many:is_next?"Error in level order (next before file)!":"Error in level order: a set must be specified.";
  if(kind==@EOF_KIND@){current_set=valid?0:-1;message="No levels were loaded!";}
  reset("input");
  if(!setjmp(stopped))error_route(kind,current_set,is_set&&!valid?MAX_DIFFICULTIES:0,valid?1:0,filenames[file],7);
  assert(released==1 && outcome==(valid?0:2));
  char wanted[512]="";
  if(!valid) {
   if(wrapped)snprintf(wanted,sizeof(wanted),"load_levelorder ERROR in %s at %d, msg: %s\n",filenames[file],7,message);
   else snprintf(wanted,sizeof(wanted),"%s",message);
  }
  assert(!strcmp(diagnostic,wanted));finish();
 }
 freeCommandList(levelordercmdlist);levelordercmdlist=NULL;
}
int main(void) {@CHECKS@ puts("early_levelorder_feedback=1");return 0;}
'''
        # Each guard executes directly from its real command case; data writes after
        # successful checks are separate contracts, not reduced stand-ins for them.
        guard_code = '\n'.join('case %d: %s break;' % (index, text)
                               for index, text in enumerate(guards.values()))
        set_kind = len(guards)
        next_code = '\n'.join('case %d: %s break;' % (set_kind + 1 + index, text)
                              for index, text in enumerate(next_guards.values()))
        replacements = dict(MAX_ARG_LEN=str(fixture['max_arg_len']), MAX_DIFFICULTIES=str(fixture['max_difficulties']),
                            ARGLIST=arglist[0], MACROS=macros[0], BODIES=bodies,
                            HELPERS='\n'.join(function(source, name) for name in [
                                'obor_profile_levelorder_feedback', 'obor_profile_levelorder_error']),
                            PREFIX=dispatch_prefix(source, 'load_levelorder'), DEFAULT=cases['default']['body'],
                            CHKDEF=check_macro[0], LINE_INCREMENT=increments[0], GUARDS=guard_code,
                            SET_KIND=str(set_kind), SET_GUARD=set_guard,
                            NEXT_GUARDS=next_code, END=end, ERROR_KINDS=str(set_kind + 4), EOF_KIND=str(set_kind + 3),
                            CASES=','.join(json.dumps(case['text']) for case in fixture['cases']),
                            FILENAMES=','.join(map(json.dumps, fixture['files'])),
                            ARRAYS='\n'.join(arrays), CHECKS='\n'.join(checks))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-levelorder-feedback-') as name:
            work = Path(name)
            unit, obj, binary = work / 'probe.c', work / 'list.o', work / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-Dstricmp=strcasecmp',
                     '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                     '-I' + str(engine / 'source/scriptlib'), '-I' + str(engine / 'source/gamelib')]
            build = subprocess.run(cc + flags + ['-c', str(engine / 'source/scriptlib/List.c'), '-o', str(obj)],
                                   capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            build = subprocess.run(cc + flags + ['-Wall', '-Wextra', '-Werror', '-Wno-sign-compare',
                                   '-Wno-error=deprecated-declarations', '-Wno-implicit-fallthrough',
                                   str(unit), str(obj), *([] if sys.platform == 'darwin' else ['-no-pie']),
                                   '-o', str(binary)], capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=15, env=sanitizer_environment())
            if os.environ.get('OBOR_LEVELORDER_FEEDBACK_OBSERVATIONS'):
                Path(os.environ['OBOR_LEVELORDER_FEEDBACK_OBSERVATIONS']).write_text(json.dumps({
                    'compiler': cc, 'flags': flags, 'contexts': len(rows), 'cases': len(fixture['cases']),
                    'error_checks': len(guards) + 4, 'probe_sha256': hashlib.sha256(program.encode()).hexdigest(),
                    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                    'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                    'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr,
                    'retirement': 'TemporaryDirectory removes source/object/binary',
                }, indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_levelorder_feedback=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
