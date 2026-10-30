"""Check historical jump eligibility, walkoff and dynamic animation numbering.

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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-jump-walkoff.json'


def braced_statement(source, anchor):
    """Retain one exact condition/body, using the C-aware function extractor."""
    if source.count(anchor) != 1:
        raise AssertionError('Expected one native statement: ' + anchor)
    start = source.index(anchor)
    opening = source.index('{', start)
    body = function('void extracted(void)\n' + source[opening:], 'extracted')
    return source[start:opening] + body[body.index('{'):]


def continued_macro(source, name):
    lines = source.splitlines()
    starts = [i for i, line in enumerate(lines) if re.match(r'#define\s+' + name + r'\b', line)]
    if len(starts) != 1:
        raise AssertionError('Expected one native macro: ' + name)
    start = end = starts[0]
    while lines[end].endswith('\\'):
        end += 1
    return '\n'.join(lines[start:end + 1])


class EarlyJumpWalkoffTests(unittest.TestCase):
    def test_jump_walkoff_and_animation_ids(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertEqual((min(revisions), max(revisions)), tuple(fixture['range']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for profile in contract_profiles(fixture, pin['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source, header, script = ((engine / name).read_text() for name in ['openbor.c', 'openbor.h', 'openborscript.c'])
        constants = re.search(r'(?ms)^#define\s+MAX_ATKS\b.*?^#define OBOR_PROFILE_BASE_ANIMATIONS[^\n]*', header)
        self.assertIsNotNone(constants)
        default_constants = []
        for limit in sorted({row[3] for row in fixture['layout']} - {'MAX_ATKS'}):
            found = re.findall(r'(?m)^#define\s+' + limit + r'\s+[^\n]+', header)
            self.assertEqual(len(found), 1)
            default_constants += found
        loader = function(source, 'load_models')
        reset = re.search(r'(?ms)^\s*max_idles\s*=.*?^\s*max_animations\s*=[^;]+;', loader)
        counter = re.search(r'\bint maxanim\s*=[^;]+;', loader)
        self.assertIsNotNone(reset)
        self.assertIsNotNone(counter)
        calculation = re.search(r'// calculate max animations[\s\S]+?for\(i=MAX_ATKS;[^\n]*animdies\[i\] = maxanim\+\+;', loader)
        self.assertIsNotNone(calculation)
        arrays, declarations, frees, mode_checks = [], [], [], []
        for pointer, default, count, limit in fixture['layout']:
            found = re.findall(r'(?ms)^int\s+' + default + r'\[[^]]+\]\s*=\s*\{[^}]+\};', source)
            self.assertEqual(len(found), 1)
            arrays += found
            declarations.append('static int *%s;' % pointer)
            frees.append('free(%s);%s=NULL;' % (pointer, pointer))
        counters = dict((row[2], row[3]) for row in fixture['layout'])
        declarations += ['static int %s;' % name for name in [*counters, 'max_animations']]
        for mode in fixture['modes']:
            check = [reset[0]]
            check += ['%s += %d;' % (name, value) for name, value in mode['bumps'].items()]
            check += ['{', counter[0], 'int i;', calculation[0],
                      'assert(max_animations==base+%d && maxanim==max_animations);' % mode['extra']]
            for index, (pointer, default, count, limit) in enumerate(fixture['layout']):
                values = fixture['default_ids'][default]
                check.append('{static const int expected[%s]={%s};' % (limit, ','.join(map(str, values))))
                check.append('assert(sizeof(expected)/sizeof(expected[0])==%s);' % limit)
                check.append('for(int k=0;k<%s;k++)assert(%s[k]==expected[k]);' % (limit, pointer))
                check.append('for(int k=%s;k<%s;k++)assert(%s[k]==base+%d+k-%s);}' %
                             (limit, count, pointer, mode['starts'][index], limit))
            check += frees + ['}']
            mode_checks.append('\n'.join(check))
        walk_prefix = braced_statement(source, 'if(strnicmp(value, "walk", 4)==0 &&')
        duck = braced_statement(source, 'if(stricmp(value, "duckattack")==0)')
        walkoff = braced_statement(source, 'if(obor_profile_build >= 3398 && stricmp(value, "walkoff")==0)')
        # Retain the loader's own final rejection branch, not a substitute return.
        tail_start = source.index('else {', source.index('stricmp(value, "walkoff")'))
        rejection = braced_statement(source[tail_start:source.index('if(!model_animation_reserve', tail_start)], 'else {')
        transition = braced_statement(function(source, 'check_gravity'),
                                      'if(obor_profile_build >= 3398 && self->idling && validanim(self, ANI_WALKOFF))')
        constant = braced_statement(script, 'if(obor_profile_build < 3398 && stricmp("MAX_ANIS", constname)==0)')
        self.assertEqual(script.count('ICMPCONST(MAX_ANIS)'), 1)
        checks = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['function_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            for flag in ['jump_wide', 'walkoff']:
                self.assertIs(type(row[flag]), bool)
            checks.append('check(%d,%d,%d,%d);' %
                          (row['revision'], row['jump_wide'], row['walkoff'], row['base_animations']))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
uint32_t obor_profile_build;
@MODEL_ERROR@
@MODEL_ERROR_MACRO@
@CONSTANTS@
@VALID@
typedef struct {int numframes;struct {int xmin,xmax;} range;} animation;
typedef struct {
 animation **animation;int animation_capacity,jumpmovez;
 float runjumpheight,jumpspeed,runjumpdist,jumpheight;
} model;
typedef struct entity {model modeldata;int direction,running,idling,animating;
 float x,z,a,zdir;void (*takeaction)(void);} entity;
static entity actor,*self=&actor;
static struct {float walls[1][8];} stage,*level=&stage;
static int environment,airborne,requests,requested_animation,idle_calls,animation_calls;
static float requested_height,requested_speed,requested_z;
static int checkwall_below(float x,float z,float a) {(void)x;(void)z;(void)a;return environment==1||environment==2?0:-1;}
static int checkhole(float x,float z) {(void)z;return environment==3 && (x==2 || x==-2);}
static int checkwall(float x,float z) {(void)x;(void)z;return -1;}
static int inair(entity *e) {assert(e==self);return airborne;}
static void tryjump(float h,float s,float z,int ani) {requests++;requested_height=h;requested_speed=s;requested_z=z;requested_animation=ani;}
static void set_idle(entity *e) {assert(e==self);idle_calls++;}
static void ent_set_anim(entity *e,int ani,int reset) {assert(e==self && !reset);animation_calls++;requested_animation=ani;}
@JUMP@
@WALKOFF@
static void walkoff_transition(void) {@TRANSITION@}
static int animation_name(char *value) {
 int ani_id=-1,tempInt=0,animwalks[2]={ANI_WALK,200};char *shutdownmessage=NULL;
 @MODEL_ERROR_STORAGE@
 @WALK_PREFIX@
 else @DUCK@
 else @WALKOFF_NAME@
 @REJECTION@
 return ani_id;
/* Exact own-source diagnostic strings are covered by the model feedback suite. */
lCleanup:assert(shutdownmessage && shutdownmessage[0]);return -1;
}
typedef long LONG;
enum {VT_STR,VT_INTEGER};
typedef struct {int vt;LONG lVal;} ScriptVariant;
static void ScriptVariant_ChangeType(ScriptVariant *v,int t) {v->vt=t;}
@CONSTANT_MACRO@
static void max_anis_constant(const char *constname,ScriptVariant **varlist) {@CONSTANT@ ICMPCONST(MAX_ANIS)}
@ARRAYS@
@DECLARATIONS@
static void dynamic_ids(int base) {@MODE_CHECKS@}
static void check(unsigned revision,int wide,int walkoff,int base) {
 obor_profile_build=revision;
 animation records[MAX_ANIS]={0},*slots[MAX_ANIS]={0};
 for(int i=0;i<MAX_ANIS;i++)slots[i]=&records[i];
 actor=(entity){.modeldata={.animation=slots,.animation_capacity=MAX_ANIS,
  .runjumpheight=7,.jumpspeed=2,.runjumpdist=3,.jumpheight=4},.zdir=2};
 records[ANI_JUMP].range.xmin=3;records[ANI_JUMP].range.xmax=10;
 records[ANI_RUNJUMP].range.xmin=5;records[ANI_RUNJUMP].range.xmax=15;
 for(int mask=0;mask<8;mask++)for(int direction=0;direction<2;direction++)
 for(int running=0;running<2;running++)for(int movez=0;movez<2;movez++)for(int env=0;env<4;env++) {
  records[ANI_JUMP].numframes=(mask&1)?2:0;records[ANI_FORWARDJUMP].numframes=(mask&2)?2:0;
  records[ANI_RUNJUMP].numframes=(mask&4)?2:0;
  actor.direction=direction;actor.running=running;actor.modeldata.jumpmovez=movez;
  environment=env;level->walls[0][7]=env==2?12:5;airborne=0;requests=0;
  int j=(((mask&1)||(wide && mask)) && (env==1||env==3))?1:0;
  if(!j && (mask&4) && env)j=2;
  assert(common_try_jump()==!!j && requests==!!j);
  if(j) {
   int run=running || j==2;
   int expected=run && (mask&4)?ANI_RUNJUMP:(mask&2)?ANI_FORWARDJUMP:ANI_JUMP;
   assert(requested_animation==expected && requested_height==(run?7:4));
   assert(requested_speed==(run?6:2) && requested_z==(movez?2:0));
  }
 }
 // Candidate-only stability controls; the own-source oracle covers initialized
 // jump records above, including a present record with zero valid frames.
 slots[ANI_JUMP]=NULL;records[ANI_RUNJUMP].numframes=0;records[ANI_FORWARDJUMP].numframes=2;
 environment=1;requests=0;assert(!common_try_jump() && !requests);
 records[ANI_RUNJUMP].numframes=2;requests=0;assert(common_try_jump() && requests==1 && requested_animation==ANI_RUNJUMP);
 actor.modeldata.animation=NULL;requests=0;assert(!common_try_jump() && !requests);actor.modeldata.animation=slots;
 assert(animation_name("walk")==ANI_WALK && animation_name("WALK2")==200);
 assert(animation_name("duckattack")==ANI_DUCKATTACK);
 assert(animation_name("walkoff")== (walkoff?ANI_WALKOFF:-1));
 assert(animation_name("WALKOFF")== (walkoff?ANI_WALKOFF:-1));
 assert(animation_name("walkoff2")==-1);
 for(int enabled=0;enabled<2;enabled++)for(int idling=0;idling<2;idling++) {
  records[ANI_WALKOFF].numframes=enabled;actor.idling=idling;actor.takeaction=NULL;animation_calls=0;
  walkoff_transition();int expected=walkoff && enabled && idling;
  assert(animation_calls==expected && actor.idling==(expected?0:idling));
  assert(actor.takeaction==(expected?common_walkoff:NULL));
  if(expected)assert(requested_animation==ANI_WALKOFF);
 }
 for(int air=0;air<2;air++)for(int animating=0;animating<2;animating++) {
  airborne=air;actor.animating=animating;actor.takeaction=common_walkoff;idle_calls=0;
  common_walkoff();assert(idle_calls==(!air && !animating));
  assert(actor.takeaction==((air||animating)?common_walkoff:NULL));
 }
 ScriptVariant v={VT_STR,0},*args[]={&v};max_anis_constant("mAx_AnIs",args);assert(v.vt==VT_INTEGER && v.lVal==base);
 dynamic_ids(base);
}
int main(void) {@CHECKS@ puts("early_jump_walkoff=1");return 0;}
'''
        replacements = dict(CONSTANTS='\n'.join(default_constants) + '\n' + constants[0], VALID=continued_macro(header, 'validanim'),
                            MODEL_ERROR=function(source, 'obor_model_error'),
                            MODEL_ERROR_MACRO=continued_macro(source, 'OBOR_MODEL_ERROR'),
                            MODEL_ERROR_STORAGE=re.search(r'char legacy_model_error\[\d+\][^;]*;', function(source, 'load_cached_model')).group(),
                            JUMP=function(source, 'common_try_jump'), WALKOFF=function(source, 'common_walkoff'),
                            TRANSITION=transition, WALK_PREFIX=walk_prefix, DUCK=duck, WALKOFF_NAME=walkoff,
                            REJECTION=rejection, CONSTANT_MACRO=continued_macro(script, 'ICMPCONST'), CONSTANT=constant,
                            ARRAYS='\n'.join(arrays), DECLARATIONS='\n'.join(declarations),
                            MODE_CHECKS='\n'.join(mode_checks), CHECKS='\n'.join(checks))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-jump-walkoff-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-Dstricmp=strcasecmp', '-Dstrnicmp=strncasecmp',
                     '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                     '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare', '-Wno-error=deprecated-declarations']
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)],
                                   capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15, env=sanitizer_environment())
            if os.environ.get('OBOR_JUMP_WALKOFF_OBSERVATIONS'):
                Path(os.environ['OBOR_JUMP_WALKOFF_OBSERVATIONS']).write_text(json.dumps({
                    'compiler': cc, 'flags': flags, 'contexts': len(rows), 'jump_cases_per_context': 256,
                    'probe_sha256': hashlib.sha256(program.encode()).hexdigest(),
                    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                    'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                    'header_sha256': hashlib.sha256(header.encode()).hexdigest(),
                    'script_sha256': hashlib.sha256(script.encode()).hexdigest(),
                    'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr,
                    'scope': fixture['scope'], 'retirement': 'TemporaryDirectory removes source/binary',
                }, indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_jump_walkoff=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
