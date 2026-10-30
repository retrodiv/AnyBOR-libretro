"""Check historical attack names, types and consecutive record updates.

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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-attack-commands.json'


class EarlyAttackCommandsTests(unittest.TestCase):
    def test_attack_names_types_and_record_preservation(self):
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
        records = re.findall(r'typedef struct\s*\{[^{}]*}\s*s_attack\s*;', header)
        self.assertEqual(len(arglist), 1)
        self.assertEqual(len(records), 1)
        macros = []
        for name in ['GET_ARG', 'GET_INT_ARG']:
            values = re.findall(r'(?m)^#define ' + name + r'\(z\)[^\n]*', source)
            self.assertEqual(len(values), 1)
            macros += values
        definitions = re.findall(r'(?m)^#define\s+(?:ATK_\w+|MAX_ATKS|STA_ATKS|GAME_SPEED)\s+[^\n]+', header)
        method = function(source, 'load_cached_model')
        method, cases = switch_cases(method.replace('switch(cmd)', 'switch(model_command)', 1),
                                     'load_cached_model', 'model_command')
        labels = [name for name in cases if re.fullmatch(
            r'CMD_MODEL_(?:ATTACK(?:\d+)?|ATTACK_ETC|SHOCK|BURN|STEAL|FREEZE|ITEMBOX)', name)]
        self.assertTrue(labels)
        attack_case = method[min(cases[name]['label_start'] for name in labels):
                             max(cases[name]['end'] for name in labels)]
        bodies = '\n'.join(function(source, name) for name in [
            'ParseArgs', 'findarg', 'obor_legacy_arg', 'obor_lookup_command', 'isNumeric', 'getValidInt'])
        bodies += '\n' + function(utility, 'lc')
        for name in ['getCommandlistCommand', 'getModelCommand', 'prepareList',
                     'createModelCommandList', 'freeCommandList']:
            bodies += '\n' + function(commands, name) + '\n#undef LIST_ADD\n'
        bodies += '\n' + function(source, 'obor_profile_model_command')
        arrays, checks = [], []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['function_sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(len(row['results']), len(fixture['cases']))
            values = []
            for result in row['results']:
                for flag in ['accepted', 'steal', 'freeze']:
                    self.assertIs(type(result[flag]), bool)
                self.assertIn(result['outcome'], [0, 1, 2])
                if result['accepted']:
                    self.assertIs(type(result['type']), int)
                    self.assertTrue(0 <= result['type'] <= 127)
                else:
                    self.assertIsNone(result['type'])
                values.append('{%d,%d,%d,%d,%d}' % (result['accepted'], result['outcome'],
                              result['type'] if result['accepted'] else 0, result['steal'], result['freeze']))
            name = 'expected_' + str(row['revision'])
            arrays.append('static const expectation %s[]={%s};' % (name, ','.join(values)))
            checks.append('check(%d,%d,%s);' % (row['revision'], row['game_speed'], name))
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
#define MAX_ARG_LEN 512
@ARGLIST@
@RECORD@
@DEFINITIONS@
@MACROS@
uint32_t obor_profile_build;
List *modelcmdlist;
static s_attack attack,expected_attack;
static int abox[4],expected_abox[4],outcome,accepted;
static jmp_buf stopped;
static char diagnostic[512];
static int warning(const char *format,...) {
 va_list args;va_start(args,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);
 va_end(args);assert(n>=0 && (size_t)n<sizeof(diagnostic));outcome=1;return n;
}
static void engine_stop(int code,const char *format,...) {
 va_list args;va_start(args,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);
 va_end(args);assert(code==1 && n>=0 && (size_t)n<sizeof(diagnostic));outcome=2;longjmp(stopped,1);
}
@BODIES@
#define printf warning
#define shutdown engine_stop
@FEEDBACK_HELPER@
static void dispatch(const char *name) {
 char input[MAX_ARG_LEN+1],argbuf[MAX_ARG_LEN+1]={0},*buf=input,*command="",*filename=(char *)"data/model.txt";
 size_t pos=0;ArgList arglist;int tempInt=0;
 modelCommands cmd=(modelCommands)0;
 int n=snprintf(input,sizeof(input),"%s 1 2 3 4 5 6 7 8 9 10\n",name);assert(n>0 && (size_t)n<sizeof(input));
 @PREFIX@
 switch(cmd) {
 @ATTACK_CASE@
 default:@DEFAULT@
 }
 accepted=cmd!=0;
 }
}
#undef shutdown
#undef printf
typedef struct {int accepted,outcome,type,steal,freeze;} expectation;
static const char *names[]={@NAMES@};
@ARRAYS@
static void initialize(void) {
 memset(&attack,0,sizeof(attack));memset(&expected_attack,0,sizeof(expected_attack));
 memset(abox,0,sizeof(abox));memset(expected_abox,0,sizeof(expected_abox));
 attack.hitsound=expected_attack.hitsound=71;attack.hitflash=expected_attack.hitflash=72;
 attack.blockflash=expected_attack.blockflash=73;attack.blocksound=expected_attack.blocksound=74;
 attack.counterattack=expected_attack.counterattack=1;attack.dot_index=expected_attack.dot_index=13;
 attack.staydown[0]=expected_attack.staydown[0]=17;
}
static void apply_expected(const expectation *value,int speed) {
 if(!value->accepted)return;
 for(int i=0;i<4;i++)expected_abox[i]=i+1;
 expected_attack.dropv[0]=3;expected_attack.dropv[1]=(float)1.2;expected_attack.dropv[2]=0;
 expected_attack.attack_force=5;expected_attack.attack_drop=value->freeze?0:6;
 expected_attack.no_block=7;expected_attack.no_flash=8;expected_attack.pause_add=9;
 expected_attack.attack_coords[4]=10;expected_attack.attack_type=value->type;
 if(value->steal)expected_attack.steal=1;
 if(value->freeze){expected_attack.freeze=1;expected_attack.freezetime=6*speed;expected_attack.forcemap=-1;}
}
static void equal_records(void) {
 assert(!memcmp(&attack,&expected_attack,sizeof(attack)));
 assert(!memcmp(abox,expected_abox,sizeof(abox)));
}
static void check(unsigned revision,int speed,const expectation *expected) {
 obor_profile_build=revision;assert(speed==GAME_SPEED);
 assert(CMD_MODEL_ATTACK10-CMD_MODEL_ATTACK1==9);
 modelcmdlist=createModelCommandList();assert(modelcmdlist);
 for(volatile size_t i=0;i<sizeof(names)/sizeof(names[0]);i++) for(volatile int seed=0;seed<4;seed++) {
  initialize();
  if(seed>=2) {
   outcome=accepted=0;diagnostic[0]=0;
   if(!setjmp(stopped))dispatch("freeze");else abort();
   assert(!outcome && accepted);apply_expected(&expected[@FREEZE_INDEX@],speed);equal_records();
  }
  if(seed==1 || seed==3) {
   outcome=accepted=0;diagnostic[0]=0;
   if(!setjmp(stopped))dispatch("steal");else abort();
   assert(!outcome && accepted);apply_expected(&expected[@STEAL_INDEX@],speed);equal_records();
  }
  outcome=accepted=0;diagnostic[0]=0;
  if(!setjmp(stopped))dispatch(names[i]);
  assert(outcome==expected[i].outcome);
  if(!outcome)assert(accepted==expected[i].accepted);
  apply_expected(&expected[i],speed);equal_records();
  if(outcome)assert(strstr(diagnostic,"not understood in file 'data/model.txt'!"));
  else assert(!diagnostic[0]);
 }
 freeCommandList(modelcmdlist);modelcmdlist=NULL;
}
int main(void) {@CHECKS@ puts("early_attack_commands=1");return 0;}
'''
        replacements = dict(ARGLIST=arglist[0], RECORD=records[0], DEFINITIONS='\n'.join(definitions),
                            MACROS='\n'.join(macros), BODIES=bodies,
                            FEEDBACK_HELPER=function(source, 'obor_profile_file_feedback'),
                            PREFIX=dispatch_prefix(source, 'load_cached_model'), ATTACK_CASE=attack_case,
                            DEFAULT=cases['default']['body'], NAMES=','.join(map(json.dumps, fixture['cases'])),
                            FREEZE_INDEX=str(fixture['cases'].index('freeze')),
                            STEAL_INDEX=str(fixture['cases'].index('steal')),
                            ARRAYS='\n'.join(arrays), CHECKS='\n'.join(checks))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-attack-commands-') as name:
            work = Path(name)
            unit, obj, binary = work / 'probe.c', work / 'list.o', work / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-Dstricmp=strcasecmp',
                     '-Dstrnicmp=strncasecmp', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                     '-fno-omit-frame-pointer', '-I' + str(engine / 'source/scriptlib'),
                     '-I' + str(engine / 'source/gamelib')]
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
            if os.environ.get('OBOR_ATTACK_COMMANDS_OBSERVATIONS'):
                Path(os.environ['OBOR_ATTACK_COMMANDS_OBSERVATIONS']).write_text(json.dumps({
                    'compiler': cc, 'flags': flags, 'contexts': len(rows), 'names': len(fixture['cases']), 'seeds': 4,
                    'probe_sha256': hashlib.sha256(program.encode()).hexdigest(),
                    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                    'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                    'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr,
                    'retirement': 'TemporaryDirectory removes source/object/binary',
                }, indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_attack_commands=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
