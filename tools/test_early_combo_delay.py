"""Check combo-delay command routing, idle-limit aliases and attack timing.

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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-combo-delay.json'


class EarlyComboDelayTests(unittest.TestCase):
    def test_command_idle_limit_and_timer(self):
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
        source, header = ((engine / name).read_text() for name in ['openbor.c', 'openbor.h'])
        commands = (engine / 'source/gamelib/commands.c').read_text()
        utility = (engine / 'source/utils.c').read_text()
        arglist = re.findall(r'typedef struct ArgList\s*\{[^}]+}\s*ArgList;', header)
        self.assertEqual(len(arglist), 1)
        macros = []
        for name in ['GET_ARG', 'GET_INT_ARG']:
            found = re.findall(r'(?m)^#define ' + name + r'\(z\)[^\n]*', source)
            self.assertEqual(len(found), 1)
            macros += found
        constants = []
        for name in ['GAME_SPEED', 'MAX_IDLES', 'MAX_ARG_LEN']:
            found = re.findall(r'(?m)^#define\s+' + name + r'\s+\d+[^\n]*', header)
            self.assertEqual(len(found), 1)
            constants += found
        timer = re.findall(r'topowner->combotime\s*=\s*time\s*\+\s*[^;]+;', function(source, 'do_attack'))
        clock = re.findall(r'(?m)^u32\s+time\s*=\s*0;[^\n]*', source)
        clock_field = re.findall(r'(?m)^\s*unsigned int\s+combotime;[^\n]*', header)
        delay = re.findall(r'(?m)^int\s+combodelay\s*=\s*[^;]+;[^\n]*', source)
        self.assertEqual((len(timer), len(clock), len(clock_field), len(delay)), (1, 1, 1, 1))
        _, cases = switch_cases(source, 'load_models', 'cmd')
        bodies = '\n'.join(function(source, name) for name in [
            'ParseArgs', 'findarg', 'obor_legacy_arg', 'obor_lookup_command', 'isNumeric', 'getValidInt'])
        bodies += '\n' + function(utility, 'lc')
        for name in ['getCommandlistCommand', 'getModelstxtCommand', 'prepareList', 'createModelstxtCommandList', 'freeCommandList']:
            bodies += '\n' + function(commands, name) + '\n#undef LIST_ADD\n'
        arrays, checks = [], []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for value in row['function_sha256'].values():
                self.assertRegex(value, r'^[0-9a-f]{64}$')
            self.assertEqual(len(row['results']), len(fixture['cases']))
            values = []
            for result in row['results']:
                self.assertIn(result['outcome'], [0, 1, 2])
                self.assertIs(type(result['idle_count']), int)
                self.assertIs(type(result['delay']), int)
                values.append('{%d,%d,%d}' % (result['outcome'], result['idle_count'], result['delay']))
            name = 'expected_' + str(row['revision'])
            arrays.append('static const expectation %s[]={%s};' % (name, ','.join(values)))
            checks.append('check(%d,%d,%d,%s);' % (row['revision'], row['variable_timer'], row['check_default'], name))
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
typedef uint32_t u32;
@CONSTANTS@
@ARGLIST@
@MACROS@
@CLOCK@
@DELAY@
struct owner {
@CLOCK_FIELD@
};
uint32_t obor_profile_build;
List *modelstxtcmdlist;
static int max_idles,outcome;
static jmp_buf stopped;
static char diagnostic[256];
static int warning(const char *format,...) {
 va_list args;va_start(args,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);
 assert(n>=0 && (size_t)n<sizeof(diagnostic));outcome=1;return n;
}
static void stop_request(int code,const char *format,...) {
 va_list args;va_start(args,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);
 assert(code==1 && n>=0 && (size_t)n<sizeof(diagnostic));outcome=2;longjmp(stopped,1);
}
@BODIES@
#define printf warning
#define shutdown stop_request
@FEEDBACK@
static void dispatch(char *buf) {
 for(int model_pass=0;model_pass<(obor_profile_build<3256?2:1);model_pass++) {
 int limit_command;
 ArgList arglist;char argbuf[MAX_ARG_LEN+1]={0},*command="",*filename=(char *)"data/models.txt";size_t pos=0;
 modelstxtCommands cmd=(modelstxtCommands)0;
 @PREFIX@
 switch(cmd) {
 case CMD_MODELSTXT_MAXIDLES:@IDLE@
 case CMD_MODELSTXT_COMBODELAY:@COMBO@
 default:abort();
 }
model_next_line:;
 }
}
#undef shutdown
#undef printf
static uint32_t next_combo_time(uint32_t now) {struct owner value={0},*topowner=&value;time=now;@TIMER@ return value.combotime;}
typedef struct {int outcome,idles,delay;} expectation;
static const char *cases[]={@CASES@};
@ARRAYS@
static void check(unsigned revision,int variable,int check_default,const expectation *expected) {
 obor_profile_build=revision;modelstxtcmdlist=createModelstxtCommandList();assert(modelstxtcmdlist);
 // Every selected source has this initial delay; an unselected transient
 // initializer is source evidence only, rather than a selectable profile.
 combodelay=GAME_SPEED/2;
 if(check_default)assert(next_combo_time(21)==21+GAME_SPEED/2);
 for(volatile size_t i=0;i<sizeof(cases)/sizeof(cases[0]);i++) {
  char baseline[]="maxidles 20\n",line[MAX_ARG_LEN+1];
  outcome=0;diagnostic[0]=0;max_idles=MAX_IDLES;combodelay=GAME_SPEED/2;
  if(!setjmp(stopped))dispatch(baseline);else abort();assert(max_idles==20 && !outcome);
  assert(strlen(cases[i])<sizeof(line));strcpy(line,cases[i]);
  if(!setjmp(stopped))dispatch(line);
  assert(outcome==expected[i].outcome && max_idles==expected[i].idles && combodelay==expected[i].delay);
  if(outcome)assert(strstr(diagnostic,"not understood in file 'data/models.txt'!"));else assert(!diagnostic[0]);
  uint32_t now=UINT32_MAX-3;
  uint32_t wanted=now+(uint32_t)(variable?expected[i].delay:GAME_SPEED/2);
  assert(next_combo_time(now)==wanted);
 }
 const int seeds[]={-7,0,17,100};
 for(size_t i=0;i<sizeof(seeds)/sizeof(seeds[0]);i++) {
  combodelay=seeds[i];
  assert(next_combo_time(31)==31+(uint32_t)(variable?seeds[i]:GAME_SPEED/2));
 }
 freeCommandList(modelstxtcmdlist);modelstxtcmdlist=NULL;
}
int main(void) {assert(sizeof(unsigned int)==4 && combodelay==GAME_SPEED/2);@CHECKS@ puts("early_combo_delay=1");return 0;}
'''
        replacements = dict(CONSTANTS='\n'.join(constants), ARGLIST=arglist[0], MACROS='\n'.join(macros),
                            CLOCK=clock[0], CLOCK_FIELD=clock_field[0], DELAY=delay[0], BODIES=bodies,
                            FEEDBACK=function(source, 'obor_profile_file_feedback'), PREFIX=dispatch_prefix(source, 'load_models'),
                            IDLE=cases['CMD_MODELSTXT_MAXIDLES']['body'], COMBO=cases['CMD_MODELSTXT_COMBODELAY']['body'],
                            TIMER=timer[0], CASES=','.join(map(json.dumps, fixture['cases'])),
                            ARRAYS='\n'.join(arrays), CHECKS='\n'.join(checks))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-combo-delay-') as name:
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
            build = subprocess.run(cc + flags + ['-Wall', '-Wextra', '-Werror', '-Wno-sign-compare', '-Wno-implicit-fallthrough',
                                   '-Wno-error=deprecated-declarations', str(unit), str(obj),
                                   *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)],
                                   capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15, env=sanitizer_environment())
            if os.environ.get('OBOR_COMBO_DELAY_OBSERVATIONS'):
                Path(os.environ['OBOR_COMBO_DELAY_OBSERVATIONS']).write_text(json.dumps({
                    'compiler': cc, 'flags': flags, 'contexts': len(rows), 'cases': len(fixture['cases']),
                    'probe_sha256': hashlib.sha256(program.encode()).hexdigest(),
                    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                    'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                    'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr,
                    'retirement': 'TemporaryDirectory removes source/object/binary',
                }, indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_combo_delay=1', run.stdout)


    def test_collision_continuation_after_animation_callbacks(self):
        from test_early_system_callbacks import block
        fixture = load_contract_fixture(Path(__file__).parent /
                                        'fixtures/profile-early-collision-continue.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        body = function((engine / 'openbor.c').read_text(), 'do_attack')
        state = re.search(r'int obor_followed = 0;\s*\n#define followed[^\n]*', body)
        loop = re.search(r'for\s*\(i=0;\s*i<ent_max\s*&&\s*!followed;\s*i\+\+\)', body)
        self.assertIsNotNone(state)
        self.assertIsNotNone(loop)
        follow = block(body, body.index('if((e->animation->followanim)'))
        checks = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIn(row['modern'], (0, 1))
            checks.append('check(%d,%d);' % (row['revision'], row['modern']))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct animation {
 int attackone,followanim,followcond;
 struct {int framestart;} counterrange;
} s_anim;
typedef struct entity {
 s_anim *animation;
 struct {s_anim **animation;int type;} modeldata;
 int health;
} entity;
static uint32_t obor_profile_build;
static s_anim original,changed,followed_animation,*table[3];
static entity attacker,target,*self=&target;
static int animfollows[1],can_grab,animation_calls,visits;
static int validanim(entity *e,int index) {
 assert(e==&attacker);return index>=0 && index<3 && e->modeldata.animation[index]!=NULL;
}
static int cangrab(entity *e,entity *other) {
 assert(e==&attacker && other==self);return can_grab;
}
static void ent_set_anim(entity *e,int index,int reset) {
 assert(e==&attacker && validanim(e,index) && reset==1);
 animation_calls++;e->animation=e->modeldata.animation[index];
}
static void sweep(int callback) {
 int i,ent_max=3,current_follow_id=0,didblock=0,them=1;
 entity *e=&attacker;
 s_anim *current_anim=e->animation;
 @STATE@
 @LOOP@ {
  visits++;
  if(i==0 && callback==1)e->animation=&changed;
  if(i==0 && callback==2){e->animation=&changed;e->animation=&original;}
  @FOLLOW@
 }
#undef followed
}
static void reset(int destination) {
 memset(&original,0,sizeof(original));memset(&changed,0,sizeof(changed));
 memset(&followed_animation,0,sizeof(followed_animation));
 memset(&attacker,0,sizeof(attacker));memset(&target,0,sizeof(target));
 original.counterrange.framestart=changed.counterrange.framestart=-1;
 original.attackone=changed.attackone=3;followed_animation.attackone=-1;
 table[0]=&original;table[1]=destination==1?&original:destination==2?NULL:&followed_animation;
 table[2]=&changed;attacker.animation=&original;attacker.modeldata.animation=table;
 target.modeldata.type=target.health=1;can_grab=1;animfollows[0]=1;animation_calls=visits=0;
}
static void check(unsigned revision,int modern) {
 obor_profile_build=revision;
 reset(0);sweep(0);assert(visits==3 && !animation_calls);
 reset(0);sweep(1);assert(visits==(modern?1:3) && !animation_calls && attacker.animation==&changed);
 reset(0);sweep(2);assert(visits==3 && !animation_calls && attacker.animation==&original);
 for(int destination=0;destination<3;destination++) {
  reset(destination);original.followanim=1;original.followcond=1;
  sweep(0);
  int expected=modern && destination!=0?3:1;
  assert(visits==expected && animation_calls==(destination==2?0:expected));
  assert(attacker.animation==(destination==0?&followed_animation:&original));
  if(destination!=2)assert(table[1]->attackone==3);
 }
 for(int gate=0;gate<4;gate++) {
  reset(0);original.followanim=1;
  if(gate==0)original.counterrange.framestart=0;
  if(gate==1){original.followcond=2;target.modeldata.type=0;}
  if(gate==2){original.followcond=3;target.health=0;}
  if(gate==3){original.followcond=4;can_grab=0;}
  sweep(0);assert(visits==3 && !animation_calls && attacker.animation==&original);
 }
 /* A callback's new animation is the one inspected by the follow branch. */
 reset(0);changed.followanim=1;changed.followcond=1;sweep(1);
 assert(visits==1 && animation_calls==1 && attacker.animation==&followed_animation);
}
int main(void){@CHECKS@ puts("collision_continue=1");return 0;}
'''
        for key, value in dict(STATE=state[0], LOOP=loop[0], FOLLOW=follow,
                               CHECKS='\n'.join(checks)).items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-collision-continue-') as folder:
            unit, binary = Path(folder) / 'probe.c', Path(folder) / 'probe'
            unit.write_text(program)
            command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-Wno-error=deprecated-declarations', '-fsanitize=address,undefined',
                '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', str(unit),
                *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10,
                                 env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('collision_continue=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
