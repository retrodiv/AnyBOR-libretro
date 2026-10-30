#!/usr/bin/env python3
"""Check own optional target-detection arguments and stealth thresholds."""
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 retrodiv <retrodiv@proton.me>
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from native_sanitizers import sanitizer_environment
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-target-detection.json'


class EarlyTargetDetectionTests(unittest.TestCase):
    def test_optional_argument_and_native_target_result(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        script = (engine / 'openborscript.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        variants = '\n'.join(function(variant, name) for name in
                             ['ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue'])
        target = function(core, 'diff') + function(core, 'normal_find_target')
        callback = function(script, 'openbor_findtarget')
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertIn(row['core_interface'], (0, 1, 2))
            checks.append('check(%d,%d);' % (row['revision'], row['optional_detect']))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef exit
#undef time
#undef pause
#undef shutdown
#undef check_range
uint32_t obor_profile_build;
static entity actor,candidate,sentinel,*self,*ent_list[2]={&actor,&candidate};
static int ent_max=2,range_ok,range_calls,find_calls,extra_seen,animation_seen,third_reads;
static ScriptVariant *third_argument;
CHAR *StrCache_Get(int index){(void)index;abort();}
void StrCache_Collect(int index){(void)index;abort();}
int StrCache_Pop(void){abort();}
static int probe_range(entity *source,entity *target,int anim){
 assert(source==&actor && target==&candidate && anim==2);range_calls++;return range_ok;
}
#define check_range probe_range
@VARIANTS@
@TARGET@
static entity *record_target(int anim,int detect){
 assert(self==&actor);find_calls++;extra_seen=detect;animation_seen=anim;
 return normal_find_target(anim,detect);
}
static HRESULT record_integer(ScriptVariant *value,LONG *out){
 if(value==third_argument)third_reads++;
 return ScriptVariant_IntegerValue(value,out);
}
#define normal_find_target record_target
#define ScriptVariant_IntegerValue record_integer
@CALLBACK@
#undef normal_find_target
#undef ScriptVariant_IntegerValue
static void check(unsigned revision,int enabled){
 static const struct {int argc,anim,type,extra,hide,range;} cases[]={
  {1,-1,VT_INTEGER,4,11,1},{2,-1,VT_INTEGER,4,11,1},
  {3,-1,VT_INTEGER,2,12,1},{3,-1,VT_INTEGER,2,13,1},
  {3,2,VT_INTEGER,-4,7,1},{3,2,VT_DECIMAL,2,12,1},
  {3,2,VT_EMPTY,4,11,1},{3,2,VT_STR,4,11,1},
  {3,2,VT_INTEGER,4,12,0}
 };
 obor_profile_build=revision;memset(&actor,0,sizeof(actor));memset(&candidate,0,sizeof(candidate));memset(&sentinel,0,sizeof(sentinel));
 actor.exists=candidate.exists=1;actor.modeldata.hostile=2;actor.modeldata.stealth.detect=10;candidate.modeldata.type=2;
 actor.direction=1;candidate.x=10;candidate.z=0;
 for(unsigned k=0;k<sizeof(cases)/sizeof(cases[0]);k++){
  ScriptVariant owner={0},animation={0},extra={0},result={0},*out=&result,*args[]={&owner,&animation,&extra};
  owner.vt=VT_PTR;owner.ptrVal=&actor;animation.vt=VT_INTEGER;animation.lVal=cases[k].anim;
  extra.vt=cases[k].type;if(extra.vt==VT_DECIMAL)extra.dblVal=cases[k].extra+0.75;else if(extra.vt==VT_INTEGER)extra.lVal=cases[k].extra;
  candidate.modeldata.stealth.hide=cases[k].hide;range_ok=cases[k].range;
  result.vt=VT_INTEGER;result.lVal=123;third_argument=&extra;
  self=&sentinel;range_calls=find_calls=third_reads=0;extra_seen=animation_seen=-99;
  int adjustment=enabled && cases[k].argc>2 && (extra.vt==VT_INTEGER || extra.vt==VT_DECIMAL)?cases[k].extra:0;
  int anim=cases[k].argc>1?cases[k].anim:-1;
  int found=(anim<0 || range_ok) && candidate.modeldata.stealth.hide<=10+adjustment;
  assert(openbor_findtarget(args,&out,cases[k].argc)==S_OK && out==&result && self==&sentinel);
  assert(find_calls==1 && extra_seen==adjustment && animation_seen==anim && third_reads==(enabled && cases[k].argc>2));
  assert(range_calls==(anim>=0));
  if(found)assert(result.vt==VT_PTR && result.ptrVal==&candidate);else assert(result.vt==VT_EMPTY);
  ScriptVariant_Clear(&result);
 }
 /* Every old internal caller uses the defined zero extra argument. The
  * common typed function also ignores an extra value before its introduction. */
 self=&actor;candidate.modeldata.stealth.hide=11;range_ok=1;third_argument=NULL;
 for(int extra=-4;extra<=4;extra+=4){
  int found=11<=10+(enabled?extra:0);
  assert(normal_find_target(-1,extra)==(found?&candidate:NULL));
 }
 ScriptVariant result={0},owner={0},*out=&result,*args[]={&owner};owner.vt=VT_PTR;owner.ptrVal=NULL;
 self=&sentinel;find_calls=0;
 assert(openbor_findtarget(args,&out,1)==S_OK && out==&result && result.vt==VT_EMPTY && self==&sentinel && !find_calls);
 out=&result;assert(openbor_findtarget(NULL,&out,0)==E_FAIL && !out && self==&sentinel);
}
int main(void){@CHECKS@ puts("early_target_detection=1");return 0;}
'''
        for key, value in dict(VARIANTS=variants, TARGET=target, CALLBACK=callback,
                               CHECKS='\n'.join(checks)).items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-target-detection-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                     '-fcommon', '-fsigned-char', '-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-unused-parameter', '-Wno-unused-variable', '-Wno-unused-function',
                     '-Wno-sign-compare', '-Wno-misleading-indentation', '-Wno-error=deprecated-declarations']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib',
                            'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']),
                                                 '-o', str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                 env=sanitizer_environment())
            if os.environ.get('OBOR_TARGET_DETECT_OBSERVATIONS'):
                Path(os.environ['OBOR_TARGET_DETECT_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=cc, flags=flags, contexts=len(rows), probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    core_sha256=hashlib.sha256(core.encode()).hexdigest(),
                    script_sha256=hashlib.sha256(script.encode()).hexdigest(), returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr, scope=fixture['scope'],
                    retirement='TemporaryDirectory removes source/binary'), indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_target_detection=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
