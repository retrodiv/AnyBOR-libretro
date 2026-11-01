#!/usr/bin/env python3
"""Check own AI path counters, movement decisions and item concealment."""
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 retrodiv <retrodiv@proton.me>
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
from test_historical_player import function
from test_early_system_callbacks import block

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-ai-path.json'
PICKUP_FIXTURE = Path(__file__).parent / 'fixtures/profile-early-pickup.json'


class EarlyAIPathTests(unittest.TestCase):
    def test_counter_movement_item_and_hole_contracts(self):
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
        ai = function(core, 'check_ai')
        before = ai[:ai.index('self->pathblocked++')]
        start = list(re.finditer(r'if\s*\(\s*self->xdir\s*\|\|\s*self->zdir\s*\)', before))[-1].start()
        move = 'static void ai_move_window(void){' + block(ai, start) + '}'
        pieces = [function(core, name) for name in
                  ['diff', 'isItem', 'isSubtypeTouch', 'isSubtypeWeapon', 'isSubtypeProjectile',
                   'canBeDamaged', 'normal_find_item', 'common_trymove', 'checkpathblocked']]
        pieces.append(move)
        declarations = []
        for kind in ['signed', 'unsigned']:
            declaration = fixture['original_counter_declarations'][kind]
            self.assertRegex(declaration, r'^\s*(?:unsigned\s+)?char\s+pathblocked\s*:\s*8\s*;\s*$')
            declarations.append('typedef struct {' + declaration + '} original_' + kind + ';')
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertEqual(row['counter_signed'], 1 - row['modern_ai'])
            checks.append('check(%d,%d);' % (row['revision'], row['modern_ai']))
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
#undef validanim
#undef randf
#undef inair
#undef cangrab
uint32_t obor_profile_build;
static entity actor,item,*self=&actor,*ent_list[1]={&item};
static s_anim animation;
static int ent_max=1,PLAYER_MIN_Z=160,PLAYER_MAX_Z=232;
static unsigned time=100;
static float advancex;
static s_videomodes videomodes;
static s_level instance,*level=&instance;
static int idle_calls,walk_calls,idle_counter,rng_calls,roll,move_result,move_calls;
static int hole_mask,hole_at,moved_mask;
static char hole_trace[8];
static int probe_valid(entity *e,int anim){assert(e==self);return anim==ANI_GET;}
static int probe_air(entity *e){assert(e==self);return 0;}
static int probe_idle(entity *e){assert(e==self && !self->xdir && !self->zdir);idle_calls++;idle_counter=self->pathblocked;return 1;}
static void probe_walk(entity *e){assert(!e && !self->pathblocked && !self->running && self->stalltime==time+GAME_SPEED);walk_calls++;}
static float probe_random(float limit){
 int i=rng_calls++;if(!i){assert(limit==1);return roll==0?0.75f:roll==1?0.5f:0.125f;}
 assert(roll==2 && limit==2 && i<=2);return i==1?1.5f:0.5f;
}
static int probe_move(float x,float z){assert(x==2 && z==1);move_calls++;return move_result;}
static int axis(float x,float z){
 if(x==104 && z==160)return 1;
 if(x==100 && z==162)return 2;
 abort();
}
int checkhole(float x,float z){int side=axis(x,z);assert(hole_at<7);hole_trace[hole_at++]=side==1?'X':'Z';hole_trace[hole_at]=0;return !!(hole_mask&side);}
int checkwall(float x,float z){(void)axis(x,z);return -1;}
entity *check_platform(float x,float z,entity *exclude){assert(exclude==self);(void)axis(x,z);return NULL;}
static void moved(entity *e,int side){assert(e==self);moved_mask|=side;}
#define validanim probe_valid
#define randf probe_random
#define inair probe_air
#define set_idle probe_idle
#define adjust_walk_animation probe_walk
#define check_link_move(...) abort()
#define execute_onblockz_script(...) abort()
#define execute_onblocks_script(...) abort()
#define execute_onblocko_script(...) abort()
#define execute_onblockw_script(...) abort()
#define execute_onmovex_script(e) moved(e,1)
#define execute_onmovez_script(e) moved(e,2)
#define find_ent_here(...) (abort(),(entity*)NULL)
static entity *probe_platform_between(float x,float z,float low,float high,entity *exclude){(void)x;(void)z;(void)low;(void)high;(void)exclude;abort();}
#define check_platform_between probe_platform_between
#define cangrab(...) (abort(),0)
#define adjust_grabposition(...) (abort(),0)
#define set_opponent(...) abort()
#define ents_link(...) abort()
#define ent_set_anim(...) abort()
#define set_pain(...) abort()
#define dothrow(...) abort()
void common_grabbed(void){abort();}
void common_grab(void){abort();}
void common_prethrow(void){abort();}
void common_throw_wait(void){abort();}
@DECLARATIONS@
@PIECES@
static int original_value(int modern,int raw){
 original_signed old;original_unsigned newer;old.pathblocked=raw;newer.pathblocked=raw;
 return modern?newer.pathblocked:old.pathblocked;
}
static int original_increment(int modern,int raw){
 original_signed old;original_unsigned newer;old.pathblocked=raw;newer.pathblocked=raw;old.pathblocked++;newer.pathblocked++;
 return modern?(unsigned char)newer.pathblocked:(unsigned char)old.pathblocked;
}
static void reset_actor(void){
 memset(&actor,0,sizeof(actor));self=&actor;actor.animation=&animation;actor.modeldata.speed=4;actor.modeldata.stealth.detect=10;
}
static void verify_counter_window(int modern){
 static const int raw[]={10,127,255};
 for(unsigned k=0;k<sizeof(raw)/sizeof(raw[0]);k++)for(int idle=0;idle<2;idle++)for(int result=0;result<3;result++){
  reset_actor();actor.xdir=2;actor.zdir=1;actor.idling=idle;actor.trymove=probe_move;actor.pathblocked=raw[k];move_result=result;move_calls=0;
  ai_move_window();
  int expected=result!=1 && idle?original_increment(modern,raw[k]):modern?0:raw[k];
  assert(actor.pathblocked==expected && move_calls==1);
 }
 reset_actor();actor.xdir=2;actor.zdir=1;actor.pathblocked=7;ai_move_window();assert(actor.x==2 && actor.z==1 && actor.pathblocked==7);
}
static void verify_steering(int modern){
 static const struct {int raw,chase,subtype,active;} cases[]={
  {10,0,0,1},{11,0,0,1},{20,AIMOVE1_CHASEX,0,1},{21,AIMOVE1_CHASEX,0,1},
  {200,0,0,1},{201,0,0,1},{127,0,0,1},{128,0,0,1},{255,0,0,1},
  {21,0,SUBTYPE_CHASE,1},{21,AIMOVE1_CHASEZ,0,1},{201,0,0,0}
 };
 for(unsigned k=0;k<sizeof(cases)/sizeof(cases[0]);k++)for(roll=0;roll<3;roll++){
  reset_actor();actor.pathblocked=cases[k].raw;actor.modeldata.aimove=cases[k].chase;actor.modeldata.subtype=cases[k].subtype;
  actor.xdir=2;actor.zdir=-3;actor.running=1;actor.stalltime=cases[k].active?time:time-1;
  idle_calls=walk_calls=rng_calls=0;idle_counter=-1;
  int counter=original_value(modern,cases[k].raw);
  int chased=cases[k].chase || cases[k].subtype==SUBTYPE_CHASE;
  int trigger=cases[k].active && (modern?(counter>200 || (counter>20 && chased)):counter>10);
  checkpathblocked();
  if(!trigger){assert(actor.pathblocked==cases[k].raw && actor.xdir==2 && actor.zdir==-3 && !idle_calls && !walk_calls && !rng_calls);}
  else if(!modern){assert(!actor.pathblocked && !actor.xdir && !actor.zdir && actor.stalltime==time+GAME_SPEED/4 && idle_calls==1 && idle_counter==cases[k].raw && !walk_calls && !rng_calls);}
  else{
   assert(!actor.pathblocked && !actor.running && actor.stalltime==time+GAME_SPEED && !idle_calls && walk_calls==1 && rng_calls==(roll==2?3:1));
   assert(actor.xdir==(roll==0?2:roll==1?-2:2) && actor.zdir==(roll==0?4:roll==1?-4:-1));
  }
 }
}
static void verify_items(int modern){
 short vulnerable[]={1};s_anim item_animation={0};item_animation.vulnerable=vulnerable;
 for(int hidden=9;hidden<=11;hidden+=2){
  reset_actor();memset(&item,0,sizeof(item));item.exists=1;item.modeldata.type=TYPE_ITEM;item.modeldata.stealth.hide=hidden;
  item.animation=&item_animation;item.x=10;item.health=25;actor.health=50;actor.modeldata.health=100;
  assert(normal_find_item()==(!modern || hidden<=10?&item:NULL));
 }
}
static void verify_holes(int modern){
 for(hole_mask=0;hole_mask<4;hole_mask++){
  reset_actor();memset(&instance,0,sizeof(instance));actor.modeldata.type=TYPE_ENEMY;actor.idling=1;actor.modeldata.subject_to_hole=1;
  actor.x=100;actor.z=160;hole_at=moved_mask=0;hole_trace[0]=0;
  int result=common_trymove(4,2),xmove=!(hole_mask&1),zmove=!(hole_mask&2);
  assert(!strcmp(hole_trace,modern?"ZX":"XZ"));
  assert(actor.x==100+4*xmove && actor.z==160+2*zmove && moved_mask==(xmove|zmove<<1));
  assert(result==(!xmove && !zmove?0:xmove && zmove?1:2));
 }
}
static void check(unsigned revision,int modern){
 obor_profile_build=revision;memset(&animation,0,sizeof(animation));verify_counter_window(modern);verify_steering(modern);verify_items(modern);verify_holes(modern);
}
int main(void){@CHECKS@ puts("early_ai_path=1");return 0;}
'''
        for key, value in dict(DECLARATIONS='\n'.join(declarations), PIECES='\n'.join(pieces),
                               CHECKS='\n'.join(checks)).items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-ai-path-') as name:
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
            if os.environ.get('OBOR_AI_PATH_OBSERVATIONS'):
                Path(os.environ['OBOR_AI_PATH_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=cc, flags=flags, contexts=len(rows), probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    core_sha256=hashlib.sha256(core.encode()).hexdigest(), returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr, scope=fixture['scope'],
                    original_snippets='Two own pathblocked bitfield declarations; full original units are not compiled.',
                    retirement='TemporaryDirectory removes source/binary'), indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_ai_path=1', run.stdout)

    def test_pickup_animation_and_touch_damage_contracts(self):
        fixture = load_contract_fixture(PICKUP_FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue({3214, 3215, 3217, 3218} <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        pieces = [function(core, name) for name in
                  ['diff', 'isItem', 'isSubtypeTouch', 'isSubtypeWeapon', 'isSubtypeProjectile', 'canBeDamaged']]
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertIn(row['pickup_touch'], (0, 1))
            self.assertIn(row['damage_filter'], (0, 1))
            self.assertIn(row['pickup_damage_filter'], (0, 1))
            checks.append('check(%d,%d,%d,%d);' % (row['revision'], row['pickup_touch'],
                                                 row['damage_filter'], row['pickup_damage_filter']))
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
#undef validanim
#undef set_getting
uint32_t obor_profile_build;
static entity actor,item,*self=&actor,*ent_list[1]={&item};
static s_anim animation;
static s_videomodes videomodes;
static int ent_max=1,has_get,mask_calls,at;
static unsigned time=100;
static char trace[8];
static void event(char c){assert(at<7);trace[at++]=c;trace[at]=0;}
static int probe_valid(entity *e,int anim){assert(e==self && anim==ANI_GET);return has_get;}
static void probe_animation(entity *e,int anim,int reset){assert(e==self && anim==ANI_GET && !reset);event('A');}
static void probe_getting(entity *e){assert(e==self && !strcmp(trace,"A"));event('G');}
static void probe_didhit(entity *e,entity *who,int a,int b,int kind,int c,int d,int f,int g,int h){
 assert(e==&item && who==self && !a && !b && !c && !d && !f && !g && !h && kind==item.modeldata.subtype);
 assert(item.z==100000 && !item.health && item.takeaction==suicide && item.nextthink==time+GAME_SPEED*3);event('D');
}
#define validanim probe_valid
#define ent_set_anim probe_animation
#define set_getting probe_getting
#define execute_didhit_script probe_didhit
#define dropweapon(...) abort()
#define set_weapon(...) abort()
void common_get(void){abort();}
void suicide(void){abort();}
static void previous_action(void){abort();}
@HELPERS@
static int record_mask(entity *who,entity *by){mask_calls++;return canBeDamaged(who,by);}
#define canBeDamaged record_mask
@FINDER@
@PICKUP@
#undef canBeDamaged
static void setup(int touch,int mask,int actor_type){
 memset(&actor,0,sizeof(actor));memset(&item,0,sizeof(item));
 videomodes.hRes=320;
 actor.animation=item.animation=&animation;actor.health=70;actor.modeldata.health=100;actor.modeldata.type=actor_type;
 actor.xdir=3;actor.zdir=-2;actor.takeaction=previous_action;actor.modeldata.stealth.detect=10;
 item.exists=1;item.modeldata.type=TYPE_ITEM;item.modeldata.subtype=touch?SUBTYPE_TOUCH:0;
 item.modeldata.candamage=mask;item.health=50;item.x=10;
 self=&actor;mask_calls=at=0;trace[0]=0;
}
static void check(unsigned revision,int touch_get,int damage_filter,int pickup_damage_filter){
 obor_profile_build=revision;short vulnerable[]={1};memset(&animation,0,sizeof(animation));animation.vulnerable=vulnerable;
 for(has_get=0;has_get<2;has_get++)for(int touch=0;touch<2;touch++)for(int actor_type=TYPE_PLAYER;actor_type<=(TYPE_PLAYER|TYPE_ENEMY);actor_type+=(TYPE_PLAYER|TYPE_ENEMY)-TYPE_PLAYER)for(int mask=0;mask<4;mask++){
  int accepts=(mask&actor_type)==actor_type;
  setup(touch,mask,actor_type);
  int found=has_get || (touch && (!damage_filter || accepts));
  assert(normal_find_item()==(found?&item:NULL));
  assert(mask_calls==(damage_filter && !has_get && touch));
  setup(touch,mask,actor_type);
  int matching_touch=touch_get?touch:!touch;
  int animate=has_get && matching_touch && (!pickup_damage_filter || accepts);
  common_pickupitem(&item);
  assert(!strcmp(trace,animate?"AGD":"D") && mask_calls==(has_get && matching_touch && pickup_damage_filter));
  assert(actor.health==100 && !item.health && item.z==100000 && item.takeaction==suicide && item.nextthink==time+GAME_SPEED*3);
  assert(actor.takeaction==(animate?common_get:previous_action));
  assert(actor.xdir==(animate?0:3) && actor.zdir==(animate?0:-2));
 }
 if(damage_filter)for(int type=0;type<4;type++)for(int mask=0;mask<4;mask++){
  setup(1,mask,type);assert(canBeDamaged(&item,&actor)==((mask&type)==type));
 }
}
int main(void){@CHECKS@ puts("early_pickup=1");return 0;}
'''
        for key, value in dict(HELPERS='\n'.join(pieces), FINDER=function(core, 'normal_find_item'),
                               PICKUP=function(core, 'common_pickupitem'), CHECKS='\n'.join(checks)).items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-pickup-') as name:
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
            if os.environ.get('OBOR_PICKUP_OBSERVATIONS'):
                Path(os.environ['OBOR_PICKUP_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=cc, flags=flags, contexts=len(rows), probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    core_sha256=hashlib.sha256(core.encode()).hexdigest(), returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr, scope=fixture['scope'],
                    original_snippets='None; own predicates are source-defined.',
                    retirement='TemporaryDirectory removes source/binary'), indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_pickup=1', run.stdout)


    def test_blocked_steering_boundaries_and_callback_order(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-ai-blocked.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {r['revision'] for r in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        fields = ['revision', 'delay', 'z_reversal', 'limit', 'returns_active',
                  'nomove_guard', 'callback_before_reset']
        rows = ',\n'.join('{' + ','.join(str(row[k]) for k in fields) + '}' for row in fixture['sources'])
        code = (fixture_path.parent / 'early_ai_blocked.c').read_text()
        code = code.replace('@FUNCTION@', function(core, 'checkpathblocked')).replace('@ROWS@', rows)
        self._run_steering_probe(engine, code, 'early_ai_blocked')

    def test_avoid_axis_edges_distance_bands_and_native_services(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-ai-avoid.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {r['revision'] for r in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        fields = ['x', 'z', 'tx', 'tz', 'width', 'height', 'vertical', 'aimove',
                  'dox', 'doz', 'nomove', 'present', 'random_zero']
        cases = []
        for row in fixture['cases']:
            self.assertEqual(len(row['results']), 5)
            self.assertTrue(all(len(values) == 6 for values in row['results']))
            values = [json.dumps(row['name']), *(str(row[k]) for k in fields)]
            values += ['{' + ','.join('{' + ','.join(map(str, result)) + '}' for result in row['results']) + '}']
            cases.append('{' + ','.join(values) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        code = (fixture_path.parent / 'early_ai_avoid.c').read_text()
        code = code.replace('@FUNCTIONS@', function(core, 'diff') + function(core, 'common_try_avoid'))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (row['revision'], row['era']) for row in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_ai_avoid')


    def test_chase_axis_speed_edges_and_near_target_response(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-ai-chase.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {r['revision'] for r in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        fields = ['x', 'z', 'tx', 'tz', 'xdir', 'zdir', 'direction', 'aimove', 'subtype_chase',
                  'dox', 'doz', 'nomove', 'present', 'has_run', 'runupdown', 'roll', 'zero_mask', 'width', 'height', 'grab']
        cases = []
        for row in fixture['cases']:
            self.assertEqual(len(row['results']), 5)
            self.assertTrue(all(len(values) == 8 for values in row['results']))
            values = [json.dumps(row['name']), *(str(row[k]) for k in fields)]
            values += ['{' + ','.join('{' + ','.join(map(str, result)) + '}' for result in row['results']) + '}']
            cases.append('{' + ','.join(values) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        code = (fixture_path.parent / 'early_ai_chase.c').read_text()
        code = code.replace('@FUNCTIONS@', function(core, 'diff') + function(core, 'common_try_chase'))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (row['revision'], row['era']) for row in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_ai_chase')

    def test_follow_parent_target_axes_and_native_distance_results(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-ai-follow.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {r['revision'] for r in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        fields = ['x', 'z', 'tx', 'tz', 'xdir', 'zdir', 'direction', 'running', 'nomove',
                  'parent_present', 'target_present', 'alternate_parent', 'idle_present', 'distance',
                  'has_run', 'runupdown', 'dox', 'doz']
        cases = []
        for row in fixture['cases']:
            self.assertEqual(len(row['results']), 3)
            self.assertTrue(all(len(values) == 7 for values in row['results']))
            values = [json.dumps(row['name']), *(str(row[k]) for k in fields)]
            values += ['{' + ','.join('{' + ','.join(map(str, result)) + '}' for result in row['results']) + '}']
            cases.append('{' + ','.join(values) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        code = (fixture_path.parent / 'early_ai_follow.c').read_text()
        code = code.replace('@FUNCTIONS@', function(core, 'diff') + function(core, 'common_try_follow'))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (row['revision'], row['era']) for row in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_ai_follow')

    def test_free_wander_draw_turn_edge_and_fixed_model_boundaries(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-ai-wander-free.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {r['revision'] for r in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        fields = ['x', 'z', 'direction', 'noflip', 'nomove', 'has_turn', 'r0', 'r1',
                  'vertical', 'dox', 'doz', 'width', 'height']
        cases = []
        for row in fixture['cases']:
            self.assertEqual(len(row['results']), 6)
            self.assertTrue(all(len(values) == 8 for values in row['results']))
            values = [json.dumps(row['name']), *(str(row[k]) for k in fields)]
            values += ['{' + ','.join('{' + ','.join(map(str, result)) + '}' for result in row['results']) + '}']
            cases.append('{' + ','.join(values) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        code = (fixture_path.parent / 'early_ai_wander_free.c').read_text()
        code = code.replace('@FUNCTION@', function((engine / 'openbor.c').read_text(), 'common_try_wandercompletely'))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (row['revision'], row['era']) for row in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_ai_wander_free')

    def test_target_wander_distances_random_order_axes_and_edge_waits(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-ai-wander-target.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        fields = ['x', 'z', 'tx', 'tz', 'grab', 'aggression', 'target_direction',
                  'target_attacking', 'nomove', 'present', 'r0', 'r1', 'r2', 'vertical',
                  'dox', 'doz', 'width', 'height']
        cases = []
        self.assertEqual(len({row['name'] for row in fixture['cases']}), len(fixture['cases']))
        for row in fixture['cases']:
            self.assertEqual(len(row['results']), 6)
            self.assertTrue(all(len(values) == 7 for values in row['results']))
            values = [json.dumps(row['name']), *(str(row[key]) for key in fields)]
            values += ['{' + ','.join('{' + ','.join(map(str, result)) + '}' for result in row['results']) + '}']
            cases.append('{' + ','.join(values) + '}')
        for row in fixture['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')
            self.assertIn(row['era'], range(6))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        code = (fixture_path.parent / 'early_ai_wander_target.c').read_text()
        code = code.replace('@FUNCTIONS@', function(core, 'diff') + function(core, 'common_try_wander'))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (row['revision'], row['era'])
                                                for row in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_ai_wander_target')

    def test_legacy_callers_missing_target_and_normal_stall_boundaries(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-ai-callers.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        cases = []
        for row in fixture['cases']:
            self.assertEqual(len(row['results']), 4)
            self.assertTrue(all(len(result) == 4 for result in row['results']))
            values = [json.dumps(row['name']), *(str(row[key]) for key in
                      ('family', 'follow', 'idle_flag', 'aggression', 'initial_stall'))]
            values += ['{' + ','.join('{' + ','.join([json.dumps(result[0]), *map(str, result[1:])]) + '}'
                                      for result in row['results']) + '}']
            cases.append('{' + ','.join(values) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        code = (fixture_path.parent / 'early_ai_callers.c').read_text()
        code = code.replace('@GAME_SPEED@', str(fixture['game_speed']))
        code = code.replace('@FUNCTIONS@', '\n'.join(function(core, name) for name in
                            ('diff', 'normal_move', 'avoid_move', 'chase_move')))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (row['revision'], row['era'])
                                                for row in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_ai_callers')

    def test_movement_dispatch_pickup_order_axis_selection_and_waits(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-ai-dispatch.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        defaults = dict(aimove=0, air=0, target=1, item=0, owner=0, noflip=1, running=0,
                        turn=0, jump=0, blocked=0, follow=0, item_here=0, vulnerable=0,
                        altitude=0, seta=-1, stall=900, aggression=0, subtype=0, npc=0,
                        grab=0, r0=4294967295, r1=4294967295, helper_wait=0, xdir=7,
                        zdir=9, runupdown=0, direction=1, near=0)
        cases = []
        self.assertEqual(len(fixture['cases']), len({row['name'] for row in fixture['cases']}))
        for row in fixture['cases']:
            self.assertLessEqual(set(row['input']), set(defaults))
            inputs = {**defaults, **row['input']}
            self.assertEqual(len(row['results']), 5)
            self.assertTrue(all(len(result) == 9 for result in row['results']))
            expected = ','.join('{' + ','.join([json.dumps(result[0]), *map(str, result[1:])]) + '}'
                                for result in row['results'])
            cases.append('{' + ','.join([json.dumps(row['name']), *map(str, inputs.values()),
                                        '{' + expected + '}']) + '}')
        for row in fixture['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')
            self.assertIn(row['era'], range(5))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        code = (fixture_path.parent / 'early_ai_dispatch.c').read_text()
        code = code.replace('@FUNCTIONS@', '\n'.join(function(core, name) for name in
                            ('diff', 'obor_profile_move_pickup', 'obor_profile_modern_move', 'common_move')))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (row['revision'], row['era'])
                                                for row in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_ai_dispatch')

    def test_bomb_airborne_schedule_and_single_explosion_transition(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-ai-bomb.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        cases = []
        for row in fixture['cases']:
            self.assertEqual(len(row['results']), 2)
            self.assertTrue(all(len(result) == 13 for result in row['results']))
            expected = ','.join('{' + ','.join([json.dumps(result[0]), *map(str, result[1:])]) + '}'
                                for result in row['results'])
            cases.append('{' + ','.join([json.dumps(row['name']), *map(str, row['input']),
                                        '{' + expected + '}']) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        code = (fixture_path.parent / 'early_ai_bomb.c').read_text()
        code = code.replace('@FUNCTION@', function((engine / 'openbor.c').read_text(), 'bomb_move'))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (row['revision'], row['era'])
                                                for row in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_ai_bomb')

    def test_weapon_loss_lie_deadline_and_linked_air_escape(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-action-state.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        cases = []
        for row in fixture['cases']:
            self.assertEqual(len(row['input']), 19)
            self.assertEqual(len(row['results']), 4)
            self.assertTrue(all(len(result) == 7 for result in row['results']))
            expected = ','.join('{' + ','.join([json.dumps(result[0]), *map(str, result[1:])]) + '}'
                                for result in row['results'])
            cases.append('{' + ','.join([json.dumps(row['name']), *map(str, row['input']),
                                        '{' + expected + '}']) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        code = (fixture_path.parent / 'early_action_state.c').read_text()
        code = code.replace('@FUNCTIONS@', '\n'.join(function(core, name) for name in
                            ('diff', 'common_lie', 'common_think', 'common_takedamage')))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (row['revision'], row['era'])
                                                for row in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_action_state')

    def test_wall_threshold_and_platform_nonpositive_altitude_boundaries(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-platform-altitude.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        cases = []
        for row in fixture['cases']:
            self.assertEqual(len(row['input']), 9)
            self.assertEqual(len(row['results']), 2)
            cases.append('{' + ','.join([json.dumps(row['name']), *map(str, row['input']),
                                        '{' + ','.join(map(str, row['results'])) + '}']) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        code = (fixture_path.parent / 'early_platform_altitude.c').read_text()
        code = code.replace('@FUNCTIONS@', '\n'.join(function(core, name) for name in
                            ('testwall', 'testplatform', 'checkwall_below', 'check_platform_below')))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (row['revision'], row['era'])
                                                for row in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_platform_altitude')

    def test_platform_exclusion_identity_and_script_null_query(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-platform-exclude.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        cases = []
        for row in fixture['cases']:
            self.assertEqual(len(row['input']), 4)
            self.assertEqual(len(row['results']), 2)
            self.assertTrue(all(len(result) == 5 for result in row['results']))
            expected = ','.join('{' + ','.join(map(str, result)) + '}' for result in row['results'])
            cases.append('{' + ','.join([json.dumps(row['name']), *map(str, row['input']),
                                        '{' + expected + '}']) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        code = (fixture_path.parent / 'early_platform_exclude.c').read_text()
        code = code.replace('@FUNCTIONS@', '\n'.join(function(core, name) for name in
                            ('testplatform', 'check_platform', 'check_platform_between',
                             'check_platform_above', 'check_platform_below')))
        code = code.replace('@SCRIPT@', function((engine / 'openborscript.c').read_text(), 'openbor_checkplatformbelow'))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (row['revision'], row['era'])
                                                for row in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_platform_exclude')

    def test_platform_movement_jump_veto_stuck_release_and_effect_result(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-platform-motion.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        cases = []
        for row in fixture['cases']:
            self.assertEqual(len(row['input']), 20)
            self.assertEqual(len(row['results']), 2)
            self.assertTrue(all(len(result) == 4 for result in row['results']))
            expected = ','.join('{' + ','.join(map(str, result)) + '}' for result in row['results'])
            cases.append('{' + ','.join([json.dumps(row['name']), *map(str, row['input']),
                                        '{' + expected + '}']) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        code = (fixture_path.parent / 'early_platform_motion.c').read_text()
        code = code.replace('@FUNCTIONS@', '\n'.join(function(core, name) for name in
                            ('testplatform', 'check_platform', 'check_platform_between',
                             'common_trymove', 'common_stuck_underneath', 'common_try_jump', 'dojump')))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (row['revision'], row['era'])
                                                for row in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_platform_motion')

    def test_historical_base_query_and_movement_predicate_components(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-platform-base.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        cases = []
        for row in fixture['cases']:
            self.assertEqual(len(row['input']), 28)
            self.assertEqual(len(row['result']), 3)
            cases.append('{' + ','.join([json.dumps(row['name']), *map(str, row['input']),
                                        '{' + ','.join(map(str, row['result'])) + '}']) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        code = (fixture_path.parent / 'early_platform_base.c').read_text()
        code = code.replace('@FUNCTIONS@', '\n'.join(function(core, name) for name in
                            ('testplatform', 'check_platform', 'check_platform_between',
                             'check_platform_below', 'checkbase', 'testmove')))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d,%d);' %
                            (row['revision'], row['has_base'], row['has_move']) for row in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_platform_base')

    def test_grab_position_geometry_and_historical_validation_routes(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-grab-position.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        cases = []
        array = lambda values: '{' + ','.join(map(str, values)) + '}'
        for row in fixture['cases']:
            self.assertEqual(len(row['initial']), 8)
            self.assertEqual(len(row['targets']), 4)
            self.assertEqual(len(row['results']), 3)
            expected = ','.join('{' + ','.join([str(result['returned']), array(result['positions']),
                                              json.dumps(result['trace'])]) + '}' for result in row['results'])
            cases.append('{' + ','.join([json.dumps(row['name']), array(row['initial']), array(row['targets']),
                        str(row['distance']), str(row['grabin']), *(array(row[key]) for key in
                        ('screen', 'walls', 'wall_heights', 'holes', 'bases', 'moves')), '{' + expected + '}']) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        code = (fixture_path.parent / 'early_grab_position.c').read_text()
        code = code.replace('@FUNCTION@', function((engine / 'openbor.c').read_text(), 'adjust_grabposition'))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' %
                            (row['revision'], row['era']) for row in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_grab_position')

    def test_default_entity_and_dropped_weapon_exclusion_owners(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-platform-owners.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        cases = []
        for row in fixture['cases']:
            self.assertEqual(len(row['input']), 13)
            self.assertTrue(len(row['results']) == 3 and all(len(result) == 4 for result in row['results']))
            expected = ','.join('{' + ','.join(map(str, result)) + '}' for result in row['results'])
            cases.append('{' + ','.join([json.dumps(row['name']), *map(str, row['input']),
                                        '{' + expected + '}']) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        body = function(core, 'ent_default_init')
        needle = 'if(e->modeldata.subject_to_platform>0'
        self.assertEqual(body.count(needle), 1)
        tail = body[body.index(needle):body.rfind('}')]
        self.assertTrue(tail.rstrip().endswith('e->base += level->walls[wall][7];'))
        code = (fixture_path.parent / 'early_platform_owners.c').read_text()
        code = code.replace('@QUERIES@', '\n'.join(function(core, name) for name in
                            ('testplatform', 'check_platform', 'check_platform_below')))
        code = code.replace('@DEFAULT_TAIL@', tail).replace('@DROP@', function(core, 'dropweapon'))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (row['revision'], row['era'])
                                                for row in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_platform_owners')

    def test_gravity_platform_landing_events_damage_type_and_effect_result(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-gravity.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        cases = []
        fields = fixture['input_fields']
        array = lambda values: '{' + ','.join(map(str, list(values) + [0] * (3 - len(values)))) + '}'
        for row in fixture['cases']:
            self.assertEqual(len(row['results']), 4)
            expected = []
            for result in row['results']:
                self.assertLessEqual(len(result['models']), 3)
                self.assertLessEqual(len(result['frames']), 3)
                expected.append('{' + ','.join([json.dumps(result['trace']), *map(str, result['state']),
                    array(result['models']), str(len(result['models'])), array(result['frames']),
                    str(len(result['frames']))]) + '}')
            cases.append('{' + ','.join([json.dumps(row['name']), *(str(row['input'][key]) for key in fields),
                                        '{' + ','.join(expected) + '}']) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        code = (fixture_path.parent / 'early_gravity.c').read_text()
        code = code.replace('@FUNCTIONS@', '\n'.join(function(core, name) for name in
                            ('diff', 'inair', 'testplatform', 'check_platform_above', 'check_gravity')))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (row['revision'], row['era'])
                                                for row in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_gravity')

    def test_passive_platform_ai_and_animation_following_boundaries(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-platform-follow.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        cases = []
        for row in fixture['cases']:
            self.assertEqual(len(row['results']), 3)
            expected = ['{' + ','.join([*map(str, r['state']), json.dumps(r['trace'])]) + '}'
                        for r in row['results']]
            cases.append('{' + ','.join([json.dumps(row['name']),
                *(str(row['input'][key]) for key in fixture['input_fields']),
                '{' + ','.join(expected) + '}']) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        code = (fixture_path.parent / 'early_platform_follow.c').read_text()
        code = code.replace('@FUNCTIONS@', '\n'.join(function(core, name) for name in
            ('testplatform', 'check_platform_below', 'check_ai', 'update_animation')))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (r['revision'], r['era'])
                                                for r in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_platform_follow')

    def test_platform_layer_plane_shadow_and_dying_palette_boundaries(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-platform-render.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        cases = []
        for row in fixture['cases']:
            self.assertEqual(len(row['results']), 4)
            expected = []
            for r in row['results']:
                self.assertLessEqual(len(r['draws']), 4)
                draws = ['{' + ','.join(map(str, d)) + '}' for d in r['draws']]
                expected.append('{' + ','.join([str(r['colourmap']), str(r['restored']),
                    str(len(draws)), '{' + ','.join(draws + ['{0}'] * (4-len(draws))) + '}']) + '}')
            cases.append('{' + ','.join([json.dumps(row['name']),
                *(str(row['input'][key]) for key in fixture['input_fields']),
                '{' + ','.join(expected) + '}']) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        code = (fixture_path.parent / 'early_platform_render.c').read_text()
        code = code.replace('@FUNCTIONS@', '\n'.join(function(core, name) for name in
            ('diff', 'inair', 'testplatform', 'check_platform', 'check_platform_below',
             'update_animation', 'display_ents')))
        code = code.replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (r['revision'], r['era'])
                                                for r in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_platform_render')

    def test_player_duck_platform_queries_exclude_the_player(self):
        fixture_path = Path(__file__).parent / 'fixtures/profile-early-player-platform.json'
        fixture = load_contract_fixture(fixture_path)
        revisions = {r['revision'] for r in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        cases = []
        for row in fixture['cases']:
            self.assertEqual(len(row['results']), 2)
            results = ','.join('{' + ','.join(map(str, r)) + '}' for r in row['results'])
            cases.append('{' + ','.join([json.dumps(row['name']),
                *(str(row['input'][key]) for key in fixture['input_fields']), '{' + results + '}']) + '}')
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        player = function(core, 'player_think')
        needle = 'if(self->modeldata.subject_to_platform>0 && validanim(self,ANI_DUCK)'
        self.assertEqual(player.count(needle), 1)
        gate = block(player, player.index(needle))
        self.assertEqual(gate.count('check_platform_between('), 2)
        code = (fixture_path.parent / 'early_player_platform.c').read_text()
        code = code.replace('@QUERIES@', function(core, 'testplatform') + '\n' +
            function(core, 'check_platform_between').replace('check_platform_between(', 'native_between(', 1))
        code = code.replace('@GATE@', gate).replace('@CASES@', ',\n'.join(cases))
        code = code.replace('@CHECKS@', '\n'.join('check(%d,%d);' % (r['revision'], r['era'])
                                                for r in fixture['sources']))
        self._run_steering_probe(engine, code, 'early_player_platform')

    def _run_steering_probe(self, engine, code, marker):
        with tempfile.TemporaryDirectory(prefix=marker.replace('_', '-') + '-') as directory:
            source, binary = Path(directory) / 'probe.c', Path(directory) / 'probe'
            source.write_text(code)
            flags = ['-std=gnu11', '-O0', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                     '-fcommon', '-fsigned-char', '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-error=deprecated-declarations', '-fsanitize=address,undefined,pointer-overflow',
                     '-fno-sanitize-recover=all']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib',
                            'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + flags +
                                   [str(source), *([] if sys.platform == 'darwin' else ['-no-pie']),
                                    '-o', str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30,
                                 env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn(marker + '=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
