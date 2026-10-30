"""Check historical level dispatch, diagnostics and controlled-stop requests.

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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-level-feedback.json'


class EarlyLevelFeedbackTests(unittest.TestCase):
    def test_unknown_and_known_command_feedback(self):
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
        arglist = re.findall(r'typedef struct ArgList\s*\{[^}]+}\s*ArgList;', header)
        self.assertEqual(len(arglist), 1)
        macros = re.findall(r'(?m)^#define GET_ARG\(z\)[^\n]*', source)
        self.assertEqual(len(macros), 1)
        feedback = re.findall(r'(?m)^\t{3}default:\n([\s\S]*?)\n\t{2}\}\n\n\t{2}// Go to next line',
                              function(source, 'load_level'))
        self.assertEqual(len(feedback), 1)
        bodies = '\n'.join(function(source, n) for n in ['ParseArgs', 'findarg', 'obor_legacy_arg', 'obor_lookup_command'])
        bodies += '\n' + function(utility, 'lc')
        for name in ['getCommandlistCommand', 'getLevelCommand', 'prepareList',
                     'createLevelCommandList', 'freeCommandList']:
            bodies += '\n' + function(commands, name) + '\n#undef LIST_ADD\n'
        cases = fixture['cases']
        arrays, checks = [], []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['function_sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(len(row['results']), len(cases))
            values = []
            for case, result in zip(cases, row['results']):
                label = case['constant'] or '0'
                self.assertRegex(label, r'^(?:0|CMD_LEVEL_[A-Z0-9_]+)$')
                self.assertIn(result['outcome'], [0, 1, 2])
                self.assertIs(type(result['recognized']), bool)
                values.append('{%d,%s,%s}' % (result['outcome'], label if result['recognized'] else '0',
                                             json.dumps(result['diagnostic'])))
            label = 'expected_' + str(row['revision'])
            arrays.append('static const expectation %s[]={%s};' % (label, ','.join(values)))
            checks.append('check(%d,%s);' % (row['revision'], label))
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
@ARGLIST@
uint32_t obor_profile_build;
List *levelcmdlist;
static jmp_buf stopped;
static int outcome,recognized;
static char diagnostic[256];
static int warning(const char *format,...) {
 va_list args;va_start(args,format);int size=vsnprintf(diagnostic,sizeof(diagnostic),format,args);
 va_end(args);assert(size>=0 && (size_t)size<sizeof(diagnostic));outcome=1;return size;
}
static void engine_stop(int code,const char *format,...) {
 va_list args;va_start(args,format);int size=vsnprintf(diagnostic,sizeof(diagnostic),format,args);
 va_end(args);assert(code==1 && size>=0 && (size_t)size<sizeof(diagnostic));
 outcome=2;longjmp(stopped,1);
}
@MACROS@
@BODIES@
static void dispatch(char *buf) {
 ArgList arglist;char argbuf[MAX_ARG_LEN+1]={0},*command="";size_t pos=0;
 levelCommands cmd=(levelCommands)0;
 @PREFIX@
 recognized=cmd;
 switch(cmd) {
 case CMD_LEVEL_LOADINGBG:case CMD_LEVEL_SCROLLX:case CMD_LEVEL_ITEMALPHA:case CMD_LEVEL_AT:break;
 default:
#define printf warning
#define shutdown engine_stop
 @FEEDBACK@
#undef shutdown
#undef printf
 }
}
typedef struct {int outcome,command;const char *diagnostic;} expectation;
static const char *cases[]={@CASES@};
@ARRAYS@
static void check(unsigned revision,const expectation *expected) {
 obor_profile_build=revision;levelcmdlist=createLevelCommandList();assert(levelcmdlist);
 for(Node *a=levelcmdlist->first;a;a=a->next) for(Node *b=a->next;b;b=b->next)
  assert(stricmp(a->name,b->name)!=0);
 for(size_t i=0;i<sizeof(cases)/sizeof(cases[0]);i++) {
  char input[MAX_ARG_LEN+1];assert(strlen(cases[i])<sizeof(input));strcpy(input,cases[i]);
  outcome=recognized=0;diagnostic[0]=0;
  if(!setjmp(stopped)) dispatch(input);
  assert(outcome==expected[i].outcome && recognized==expected[i].command);
  assert(!strcmp(diagnostic,expected[i].diagnostic));
 }
 freeCommandList(levelcmdlist);levelcmdlist=NULL;
}
int main(void) {@CHECKS@ puts("early_level_feedback=1");return 0;}
'''
        replacements = dict(MAX_ARG_LEN=str(fixture['max_arg_len']), ARGLIST=arglist[0], MACROS=macros[0],
                            BODIES=bodies, PREFIX=dispatch_prefix(source, 'load_level'), FEEDBACK=feedback[0],
                            CASES=','.join(json.dumps(case['text']) for case in cases),
                            ARRAYS='\n'.join(arrays), CHECKS='\n'.join(checks))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-level-feedback-') as name:
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
            if os.environ.get('OBOR_LEVEL_FEEDBACK_OBSERVATIONS'):
                inputs = [unit, engine / 'openbor.c', engine / 'openbor.h',
                          engine / 'source/gamelib/commands.c', engine / 'source/gamelib/commands.h',
                          engine / 'source/utils.c', engine / 'source/scriptlib/List.c']
                Path(os.environ['OBOR_LEVEL_FEEDBACK_OBSERVATIONS']).write_text(json.dumps({
                    'compiler': cc, 'flags': common, 'contexts': len(rows), 'cases': len(cases),
                    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                    'inputs': [{'path': str(p), 'bytes': p.stat().st_size,
                                'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in inputs],
                    'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr,
                    'retirement': 'TemporaryDirectory removes source/object/binary',
                }, indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_level_feedback=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
