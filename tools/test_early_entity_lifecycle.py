"""Check idle movement and offscreen expiry against own-source contracts.

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
from test_historical_player import function


ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-entity-lifecycle.json'


class EarlyEntityLifecycleTests(unittest.TestCase):

    def test_grab_storage_and_zero_copy(self):
        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-grab-copy.json'))
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
            for key in ['grab_reads_entity', 'copy_fills_zero', 'antigrab_getter', 'antigrab_setter_entity']:
                self.assertIs(type(row[key]), bool)
            entries.append('{%d,%d,%d}' % (row['revision'], row['grab_reads_entity'], row['copy_fills_zero']))
        engine = Path(os.environ.get('OBOR_EARLY_ENTITY_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef assert
#undef printf
#undef exit
#undef shutdown
#undef time
#undef pause
uint32_t obor_profile_build;
static unsigned scenario;
#define CHECK(c) do {if(!(c)){fprintf(stderr,"Grab copy revision=%u scenario=%u line=%d: %s\n",obor_profile_build,scenario,__LINE__,#c);abort();}}while(0)
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
@BODIES@
typedef struct {unsigned revision;int entity_storage,copy_zero;} Row;
static Row rows[]={@ROWS@};
int main(void) {
 unsigned contexts=sizeof(rows)/sizeof(rows[0]);
 for(unsigned r=0;r<contexts;++r) {
  obor_profile_build=rows[r].revision;
  for(unsigned mask=0;mask<8;++mask) {
   ++scenario;entity object,expected;s_model previous;
   memset(&object,0,sizeof(object));memset(&previous,0,sizeof(previous));
   object.modeldata.health=64;object.modeldata.mp=32;object.health=7;object.mp=3;
   object.modeldata.antigrab=(mask&1)?11:0;
   object.modeldata.grabforce=(mask&2)?13:0;
   object.modeldata.paingrab=(mask&4)?15:0;
   previous.antigrab=5;previous.grabforce=7;previous.paingrab=9;
   memcpy(&expected,&object,sizeof(expected));
   if(rows[r].copy_zero) {
    expected.modeldata.antigrab=(mask&1)?11:5;
    expected.modeldata.grabforce=(mask&2)?13:7;
    expected.modeldata.paingrab=(mask&4)?15:9;
   }
   ent_copy_uninit(&object,&previous);
   CHECK(!memcmp(&object,&expected,sizeof(object)));
  }
  for(unsigned mask=0;mask<64;++mask) for(int pain=0;pain<=2;pain+=2) {
   ++scenario;entity actor,other;s_model actor_model,other_model;s_anim actor_anim,other_anim;
   short vulnerable=1;
   memset(&actor,0,sizeof(actor));memset(&other,0,sizeof(other));
   memset(&actor_model,0,sizeof(actor_model));memset(&other_model,0,sizeof(other_model));
   memset(&actor_anim,0,sizeof(actor_anim));memset(&other_anim,0,sizeof(other_anim));
   actor.model=&actor_model;other.model=&other_model;
   actor.animation=&actor_anim;other.animation=&other_anim;other_anim.vulnerable=&vulnerable;
   actor.modeldata.type=other.modeldata.type=TYPE_ENEMY;other.inpain=pain;
   int shared_anti=(mask&1)?4:0,shared_force=(mask&2)?5:0,shared_pain=(mask&4)?3:0;
   int own_anti=(mask&8)?4:0,own_force=(mask&16)?5:0,own_pain=(mask&32)?3:0;
   other_model.antigrab=shared_anti;actor_model.grabforce=shared_force;other_model.paingrab=shared_pain;
   other.modeldata.antigrab=own_anti;actor.modeldata.grabforce=own_force;other.modeldata.paingrab=own_pain;
   int anti=rows[r].entity_storage?own_anti:shared_anti;
   int force=rows[r].entity_storage?own_force:shared_force;
   int paingrab=rows[r].entity_storage?own_pain:shared_pain;
   int expected=anti-force+(paingrab?paingrab-pain:0)<=0;
   entity *actorptr=&actor,*otherptr=&other;
   CHECK((!!cangrab(actorptr,otherptr))==expected);
   if(mask==0&&!pain) {
    ++scenario;other.invincible=1;CHECK(!cangrab(actorptr,otherptr));other.invincible=0;
    ++scenario;vulnerable=0;CHECK(!cangrab(actorptr,otherptr));vulnerable=1;
    ++scenario;actor.a=1;CHECK(!cangrab(actorptr,otherptr));actor.a=0;
   }
  }
 }
 printf("early_grab_copy=1 contexts=%u cases=%u\n",contexts,scenario);
 return 0;
}
'''
        program = program.replace('@BODIES@', '\n'.join(function(source, n) for n in
            ['diff', 'inair', 'ent_copy_uninit'])).replace('@ROWS@', ',\n'.join(entries))
        with tempfile.TemporaryDirectory(prefix='early-grab-copy-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            includes = [engine, ROOT / 'src/port/libretro', ROOT / 'src/glue', engine / 'source',
                        *sorted(p for p in (engine / 'source').iterdir() if p.is_dir())]
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
            warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else ['-Wno-type-limits']
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            flags = ['-std=gnu11', '-O1', '-g', '-UNDEBUG', '-DLIBRETRO=1',
                     '-DOBOR_ENGINE_BUILD='+fixture['engine'], '-fsigned-char', '-fcommon',
                     '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-error=deprecated-declarations', '-Wno-sign-compare',
                     '-Wno-unused-parameter', '-Wno-unused-function', '-Wno-unused-variable', *warnings]
            build = subprocess.run(compiler + flags + ['-I'+str(p) for p in includes] +
                                   [str(unit), *links, '-o', str(binary)], capture_output=True,
                                   text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                 env=sanitizer_environment())
            if os.environ.get('OBOR_GRAB_COPY_OBSERVATIONS'):
                Path(os.environ['OBOR_GRAB_COPY_OBSERVATIONS']).write_text(json.dumps(dict(
                    contexts=len(rows), compiler=compiler, probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr, scope=fixture['scope'],
                    retirement='TemporaryDirectory removes source and binary'), indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_grab_copy=1', run.stdout)


    def test_idle_velocity_and_offscreen_outcomes(self):
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
        checks = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIs(type(row['stop_type_none']), bool)
            self.assertIn(row['default_offscreen'], (1000, 3000))
            for digest in [row['source_sha256'], *row['function_sha256'].values()]:
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            self.assertEqual(set(row['function_sha256']), {'common_idle_anim', 'check_lost'})
            checks.append('check_profile(%d,%d,%d);' % (
                row['revision'], row['stop_type_none'], row['default_offscreen']))
        engine = Path(os.environ.get('OBOR_EARLY_ENTITY_ENGINE',
                                     ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        bodies = '\n'.join(function(source, name) for name in ('common_idle_anim', 'check_lost'))
        # The mutable default is part of the complete expiry function's provider.
        default = re.search(r'(?m)^static int DEFAULT_OFFSCREEN_KILL\s*=\s*\d+;', source)
        self.assertIsNotNone(default)
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
enum {TYPE_NONE=0,TYPE_PLAYER=1,TYPE_ENEMY=2,SUBTYPE_BIKER=7,
 ANI_IDLE=0,ANI_FAINT=1,ANI_SLEEP=2,SCROLL_UP=1,SCROLL_DOWN=2,SCROLL_RIGHT=4};
#define PIT_DEPTH (-100)
typedef struct {float dropv[3];int attack_force,attack_type;} s_attack;
typedef struct {int type,subtype,health,offscreenkill;} model;
typedef struct entity {
 model *model;model modeldata;int health,animating;unsigned sleeptime;
 float xdir,zdir,x,z,a,lifespancountdown;
 int (*takedamage)(struct entity *,s_attack *);
} entity;
uint32_t obor_profile_build;
static unsigned time=20;
static int max_idles=1,animidles[]={3},valid_bits,target_present,selected,sets;
static int killed,died,frozen,max_attack_types=20;
static entity *self;
static struct {int scrolldir;} current_level,*level=&current_level;
static struct {int hRes,vRes;} videomodes={320,240};
static float advancex=10,advancey=20;
static const s_attack emptyattack={{0,0,0},0,0};
@DEFAULT@
static int validanim(entity *ent,int animation) {
 assert(ent==self && animation>=0 && animation<4);return (valid_bits>>animation)&1;
}
static void ent_set_anim(entity *ent,int animation,int reset) {
 assert(ent==self && !reset);selected=animation;sets++;
}
static int normal_find_target(int animation,int flags) {
 assert(animation==3 && !flags);return target_present;
}
static void kill(entity *ent) {assert(ent==self);killed++;}
static void player_die(void) {died++;}
static int is_frozen(entity *ent) {assert(ent==self);return frozen;}
@BODIES@
static model shared;
static entity object;
static void reset(void) {
 memset(&object,0,sizeof(object));memset(&shared,0,sizeof(shared));
 self=&object;self->model=&shared;shared.type=TYPE_ENEMY;
 self->modeldata.type=TYPE_ENEMY;self->modeldata.health=self->health=100;
 self->xdir=1.25f;self->zdir=-2.5f;self->sleeptime=30;self->animating=1;
 self->x=advancex;self->z=advancey;self->lifespancountdown=100;
 selected=-1;sets=killed=died=frozen=0;target_present=0;valid_bits=1<<ANI_IDLE;
 level->scrolldir=SCROLL_RIGHT;
}
static void idle_case(int shared_type,int copied_type,int subtype,int bits,int hp,
                      unsigned sleep,int target,int expected_stop,int expected_anim) {
 reset();shared.type=shared_type;shared.subtype=subtype;self->modeldata.type=copied_type;
 valid_bits=bits;self->health=hp;self->sleeptime=sleep;target_present=target;
 int result=common_idle_anim(self);
 assert(result==(expected_anim>=0) && sets==(expected_anim>=0) && selected==expected_anim);
 assert(self->xdir==(expected_stop?0:1.25f) && self->zdir==(expected_stop?0:-2.5f));
}
static void expiry(float x,float z,int explicit_limit,int scrolling,int expected_kill) {
 reset();self->x=x;self->z=z;self->modeldata.offscreenkill=explicit_limit;
 level->scrolldir=scrolling;check_lost();
 assert(killed==expected_kill && !died);
 assert(self->lifespancountdown==(expected_kill?100:99));
}
static void check_profile(unsigned revision,int stop_none,int offscreen) {
 obor_profile_build=revision;
 idle_case(TYPE_ENEMY,TYPE_NONE,0,1,100,30,0,1,ANI_IDLE);
 idle_case(TYPE_NONE,TYPE_ENEMY,0,1,100,30,0,stop_none,ANI_IDLE);
 idle_case(TYPE_NONE,TYPE_NONE,0,0,100,30,0,stop_none,-1);
 idle_case(TYPE_ENEMY,TYPE_ENEMY,SUBTYPE_BIKER,1,100,30,0,0,ANI_IDLE);
 idle_case(TYPE_NONE,TYPE_NONE,0,15,25,0,1,stop_none,ANI_FAINT);
 idle_case(TYPE_NONE,TYPE_NONE,0,15,100,0,1,stop_none,ANI_SLEEP);
 idle_case(TYPE_NONE,TYPE_NONE,0,9,100,30,1,stop_none,3);
 idle_case(TYPE_NONE,TYPE_NONE,0,9,100,30,0,stop_none,ANI_IDLE);
 expiry(-1490,20,0,SCROLL_RIGHT,offscreen==1000);
 expiry(-1490,20,1000,SCROLL_RIGHT,1);
 expiry(-1490,20,3000,SCROLL_RIGHT,0);
 expiry(advancex-offscreen,20,0,SCROLL_RIGHT,0);
 expiry(advancex-offscreen-1,20,0,SCROLL_RIGHT,1);
 expiry(advancex+videomodes.hRes+offscreen,20,0,SCROLL_RIGHT,0);
 expiry(advancex+videomodes.hRes+offscreen+1,20,0,SCROLL_RIGHT,1);
 expiry(10,advancey-offscreen-1,0,SCROLL_RIGHT,1);
 expiry(10,-offscreen,0,SCROLL_UP,0);
 expiry(10,-offscreen-1,0,SCROLL_UP,1);
 expiry(-10000,100000,0,SCROLL_RIGHT,0);
 reset();self->a=2*PIT_DEPTH-1;check_lost();assert(killed==1 && !died);
 reset();self->modeldata.type=TYPE_PLAYER;self->x=advancex-offscreen-1;
 check_lost();assert(!killed && died==1);
 reset();frozen=1;check_lost();assert(!killed && !died && self->lifespancountdown==100);
}
int main(void) {@CHECKS@ puts("early_entity_lifecycle=1");return 0;}
'''.replace('@DEFAULT@', default[0]).replace('@BODIES@', bodies).replace('@CHECKS@', '\n'.join(checks))
        with tempfile.TemporaryDirectory(prefix='early-entity-lifecycle-') as name:
            work = Path(name)
            unit = work / 'probe.c'
            binary = work / 'probe'
            unit.write_text(program)
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-Wno-error=deprecated-declarations', '-fsanitize=address,undefined',
                '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                str(unit), *links, '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=10, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_entity_lifecycle=1', run.stdout)


    def test_animation_diagnostics_and_valid_updates(self):
        fixture = load_contract_fixture(Path(__file__).parent /
                                        'fixtures/profile-early-set-animation.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        profiles = json.loads((ROOT / 'src/pin.json').read_text())['profiles']
        for profile in contract_profiles(fixture, profiles):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        checks = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIn(row['fatal'], (0, 1))
            checks.append('check_profile(%d,%d);' % (row['revision'], row['fatal']))
        engine = Path(os.environ.get('OBOR_EARLY_ENTITY_ENGINE',
                                     ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        header = (engine / 'openbor.h').read_text()
        body = function(source, 'ent_set_anim')
        macro = re.search(r'(?m)^#define validanim(?:[^\n]*\\\n)*[^\n]*', header)
        sleep = re.search(r'(?m)^#define\s+ANI_SLEEP\s+(\d+)', header)
        self.assertIsNotNone(macro)
        self.assertIsNotNone(sleep)
        port = (ROOT / 'src/port/libretro/libretroport.c').read_text()
        stop = function(port, 'borExit')
        self.assertRegex(header, r'#define\s+shutdown\s+borShutdown')
        self.assertRegex(header, r'#define\s+exit\s+borExit')
        self.assertIn('exit(status);', function(source, 'shutdown'))
        program = r'''
#include <assert.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
enum {ANI_SLEEP=@SLEEP@};
typedef struct {int numframes,animhits;} s_anim;
typedef struct entity {
 char name[8];
 struct {s_anim **animation;int animation_capacity,sleepwait;} modeldata;
 s_anim *animation;
 int animnum,lastanimpos,animating,altbase;
 unsigned sleeptime;
 struct entity *grabbing,*lasthit;
} entity;
static uint32_t obor_profile_build;
static unsigned time=20;
static int max_animations=ANI_SLEEP+4;
static int engine_alive,engine_exit_status,updates,diagnostics,stopped;
static int frontend_token;
static void *co_frontend=&frontend_token;
static jmp_buf frontend_return;
static char message[256];
static entity object,peer,before;
static s_anim animations[ANI_SLEEP+4],*table[ANI_SLEEP+4],before_animations[ANI_SLEEP+4];
static void co_switch(void *target) {
 assert(target==co_frontend && !engine_alive && engine_exit_status==1);
 stopped=1;longjmp(frontend_return,1);
}
@STOP@
static int probe_printf(const char *format,...) {
 va_list args;va_start(args,format);
 int count=vsnprintf(message,sizeof(message),format,args);
 va_end(args);assert(count>=0 && count<(int)sizeof(message));diagnostics++;return count;
}
static void probe_shutdown(int status,char *format,...) {
 va_list args;va_start(args,format);
 int count=vsnprintf(message,sizeof(message),format,args);
 va_end(args);assert(count>=0 && count<(int)sizeof(message));diagnostics++;
 borExit(status);
}
static void update_frame(entity *ent,int frame) {
 assert(ent==&object && frame==0 && ent->animation==table[ent->animnum]);
 assert(ent->animating==1 && ent->lasthit==ent->grabbing && !ent->altbase);
 assert(!ent->animation->animhits);updates++;
}
@VALID@
#define printf probe_printf
#define shutdown probe_shutdown
@BODY@
#undef printf
#undef shutdown
static void reset(void) {
 memset(&object,0,sizeof(object));memset(animations,0,sizeof(animations));
 for(int i=0;i<max_animations;i++){animations[i].numframes=2;animations[i].animhits=9;table[i]=&animations[i];}
 strcpy(object.name,"actor");object.modeldata.animation=table;
 object.modeldata.animation_capacity=max_animations;object.modeldata.sleepwait=7;
 object.sleeptime=4;object.lastanimpos=5;object.animnum=-1;object.altbase=8;
 object.grabbing=&peer;engine_alive=1;engine_exit_status=0;
 updates=diagnostics=stopped=0;message[0]=0;
}
static void invoke(entity *ent,int index,int resetable) {
 if(!setjmp(frontend_return)) ent_set_anim(ent,index,resetable);
}
static void invalid_case(int kind,int fatal) {
 reset();int index=0;entity *ent=&object;
 if(kind==0)ent=NULL;
 if(kind==1)index=-1;
 if(kind==2)index=max_animations;
 if(kind==3)table[0]=NULL;
 if(kind==4)animations[0].numframes=0;
 before=object;memcpy(before_animations,animations,sizeof(animations));
 invoke(ent,index,0);
 assert(diagnostics==1 && !updates && stopped==fatal);
 assert(engine_alive==!fatal && engine_exit_status==fatal);
 assert(!memcmp(&before,&object,sizeof(object)));
 assert(!memcmp(before_animations,animations,sizeof(animations)));
 char expected[256];
 if(kind==0)snprintf(expected,sizeof(expected),"FATAL: tried to set animation with invalid address (no such object)");
 else snprintf(expected,sizeof(expected),kind<3?
  "FATAL: tried to set animation with invalid index (%s, %i)":
  "FATAL: tried to set animation with invalid address (%s, %i)",object.name,index);
 assert(!strcmp(message,expected));
}
static void check_profile(unsigned revision,int fatal) {
 obor_profile_build=revision;
 for(int i=0;i<5;i++)invalid_case(i,fatal);
 reset();invoke(&object,0,0);
 assert(updates==1 && !diagnostics && !stopped && object.animation==table[0]);
 assert(object.animnum==0 && object.sleeptime==27 && object.lastanimpos==-1);
 reset();object.animation=table[0];before=object;
 invoke(&object,0,0);
 assert(!updates && !diagnostics && !memcmp(&before,&object,sizeof(object)));
 reset();object.animation=table[0];invoke(&object,0,1);
 assert(updates==1 && object.lastanimpos==5 && object.sleeptime==27);
 reset();invoke(&object,ANI_SLEEP,0);
 assert(updates==1 && object.sleeptime==4 && object.animnum==ANI_SLEEP);
}
int main(void) {@CHECKS@ puts("early_set_animation=1");return 0;}
'''.replace('@SLEEP@', sleep[1]).replace('@STOP@', stop).replace(
            '@VALID@', macro[0]).replace('@BODY@', body).replace('@CHECKS@', '\n'.join(checks))
        with tempfile.TemporaryDirectory(prefix='early-set-animation-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(program)
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-Wno-error=deprecated-declarations', '-fsanitize=address,undefined',
                '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                str(unit), *links, '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=10, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_set_animation=1', run.stdout)


    def test_grab_first_frame_direction_and_motion(self):
        from test_early_system_callbacks import block
        fixture = load_contract_fixture(Path(__file__).parent /
                                        'fixtures/profile-early-grab-order.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_ENTITY_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        move = function(core, 'common_trymove')
        start = re.search(r'if\s*\(\s*\(validanim\(self,ANI_THROW\)', move)
        self.assertIsNotNone(start)
        grab = block(move, start.start())
        frame = function(core, 'update_frame')
        start = frame.index('if(level && (self->animation->move || self->animation->movez))')
        motion = block(frame, start)
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIn(row['early_flip'], (0, 1))
            self.assertIn(row['grabflip'], (0, 1))
            checks.append('check(%d,%d,%d);' % (row['revision'], row['early_flip'], row['grabflip']))
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
#undef printf
#undef cangrab
uint32_t obor_profile_build;
static unsigned time=100;
static entity actor,target,*self=&actor;
static s_model model;
static s_anim grab_anim,throw_anim,pain_anim,*actor_table[MAX_ANIS],*target_table[MAX_ANIS];
static int max_animations=MAX_ANIS,grabbed,old_throw,frames,observed[2],pain_callbacks,throws;
static short actor_motion[]={4},target_motion[]={3};
static s_level level_value,*level=&level_value;
static void probe_shutdown(int status,char *format,...) {(void)status;(void)format;abort();}
#define shutdown probe_shutdown
void update_frame(entity *ent,int f) {
 entity *saved=self;float move,movez;self=ent;
 assert(f==0 && frames<2);
 observed[frames++]=target.direction;
 @MOTION@
 self=saved;
}
@ANIMATION@
static int probe_pain(entity *victim,int type,int reset) {
 assert(victim==&target && type==-1 && !reset);
 ent_set_anim(victim,ANI_GRABBED,reset);pain_callbacks++;
 return 1;
}
#define set_pain probe_pain
#define find_ent_here(...) (&target)
#define cangrab(...) 1
#define adjust_grabposition(...) 1
#define set_opponent(...) ((void)0)
#define ents_link(...) ((void)0)
static void probe_throw(void){throws++;}
#define dothrow probe_throw
void common_grabbed(void){abort();}
void common_grab(void){abort();}
void common_prethrow(void){abort();}
void common_throw_wait(void){abort();}
static int grab_window(void) {entity *other;float x=0,z=0;(void)x;(void)z;@GRAB@ return -1;}
static void reset(int flags,int actor_dir,int target_dir,int right) {
 memset(&actor,0,sizeof(actor));memset(&target,0,sizeof(target));memset(&model,0,sizeof(model));
 memset(actor_table,0,sizeof(actor_table));memset(target_table,0,sizeof(target_table));
 memset(&grab_anim,0,sizeof(grab_anim));memset(&throw_anim,0,sizeof(throw_anim));memset(&pain_anim,0,sizeof(pain_anim));
 self=&actor;actor.model=&model;model.grabflip=flags;
 actor.direction=actor_dir;target.direction=target_dir;actor.idling=1;
 actor.x=100;target.x=right?200:0;actor.attacking=target.attacking=1;
 actor.running=1;actor.xdir=2;target.xdir=3;actor.zdir=target.zdir=1;
 actor.modeldata.animation=actor_table;target.modeldata.animation=target_table;
 actor.modeldata.animation_capacity=target.modeldata.animation_capacity=MAX_ANIS;
 actor.modeldata.throwframewait=old_throw?-1:0;
 grab_anim.numframes=throw_anim.numframes=pain_anim.numframes=1;
 grab_anim.move=throw_anim.move=actor_motion;pain_anim.move=target_motion;
 actor_table[ANI_THROW]=&throw_anim;if(grabbed)actor_table[ANI_GRAB]=&grab_anim;
 target_table[ANI_GRABBED]=&pain_anim;
 for(int i=0;i<5;i++)actor.combostep[i]=1;
 frames=pain_callbacks=throws=0;observed[0]=observed[1]=-1;
}
static void check(unsigned revision,int early,int flags_supported) {
 obor_profile_build=revision;
 for(int flags=0;flags<4;flags++)for(int ad=0;ad<2;ad++)for(int td=0;td<2;td++)
 for(int right=0;right<2;right++)for(int route=0;route<3;route++) {
  grabbed=route==0;old_throw=route==2;reset(flags,ad,td,right);
  int actor_direction=!flags_supported || (flags&1)?right:ad;
  int flipped=!flags_supported || (flags&2);
  int final_target=flipped?!actor_direction:td;
  float target_x=target.x;
  assert(grab_window()==0);
  assert(!actor.idling && !actor.running && !actor.xdir && !actor.zdir &&
         !target.xdir && !target.zdir && !target.attacking);
  assert(actor.direction==actor_direction);
  if(old_throw){assert(throws==1 && !frames && !pain_callbacks && target.direction==td);continue;}
  int frame_direction=grabbed?(early?!actor_direction:td):final_target;
  assert(frames==2 && pain_callbacks==1 && !throws);
  assert(observed[0]==frame_direction && observed[1]==frame_direction);
  assert(target.direction==final_target);
  assert(actor.x==100+(actor_direction?4:-4));
  assert(target.x==target_x+(frame_direction?3:-3));
  if(grabbed) {
   assert(!actor.attacking && actor.takeaction==common_grab && target.takeaction==common_grabbed);
   for(int i=0;i<5;i++)assert(!actor.combostep[i]);
   assert(target.stalltime==time+GRAB_STALL && actor.releasetime==time+GAME_SPEED/2);
  } else assert(actor.takeaction==common_throw_wait && target.takeaction==common_prethrow);
 }
}
int main(void){@CHECKS@ puts("early_grab_order=1");return 0;}
'''
        for key, value in dict(MOTION=motion, ANIMATION=function(core, 'ent_set_anim'),
                               GRAB=grab, CHECKS='\n'.join(checks)).items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-grab-order-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            flags = ['-std=gnu99', '-O1', '-g', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                     '-fcommon', '-fsigned-char', '-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-unused-parameter', '-Wno-unused-variable', '-Wno-unused-function',
                     '-Wno-sign-compare', '-Wno-misleading-indentation', '-Wno-error=deprecated-declarations']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib',
                            'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + flags + [
                str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)],
                capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10,
                                 env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_grab_order=1', run.stdout)


    def test_special_link_and_level_branch_contracts(self):
        from test_early_system_callbacks import block
        fixture = load_contract_fixture(Path(__file__).parent /
                                        'fixtures/profile-early-special-branch.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_ENTITY_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        game = function(core, 'playgame')
        branch = block(game, game.index('if(branch_name[0])'))
        cleanup = game[game.index('// clear global script variant list'):game.index('max_global_var_index = -1;')]
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertIn(row['modern'], (0, 1))
            checks.append('check(%d,%d);' % (row['revision'], row['modern']))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#define stricmp strcasecmp
#include "openbor.h"
#undef exit
#undef time
#undef pause
#undef shutdown
#undef set_attacking
uint32_t obor_profile_build;
static entity actor,target,*self=&actor,*smartbomber;
static s_anim animation,*table[MAX_ANIS];
static s_attack bomb;
static s_level level_value,*level=&level_value;
static int nocost,healthcheat,mana,energy,unlinks,idles,at;
static char trace[16];
static void event(char c){assert(at<15);trace[at++]=c;trace[at]=0;}
static int probe_energy(int use_mp,int anim){assert(anim==ANI_SPECIAL);return energy && (!use_mp || mana);}
static void old_action(void){abort();}
static int probe_attack(entity *ent){assert(ent==self);event('A');return 1;}
static int probe_idle(entity *ent){assert(ent==&target && ent->takeaction==old_action);idles++;event('I');return 1;}
static void probe_unlink(entity *ent){
 assert(ent==self);
 if(ent->link)assert(ent->link->takeaction==(idles?NULL:old_action));
 event('U');unlinks++;ent->link=NULL;
}
static void probe_bomb(entity *ent,s_attack *attack){assert(ent==self && attack==&bomb);event('B');}
static void probe_anim(entity *ent,int anim,int reset){
 assert(ent==self && anim==ANI_SPECIAL && !reset && !self->running && !self->xdir && !self->zdir);
 for(int i=0;i<5;i++)assert(!self->combostep[i]);event('X');
}
void common_attack_proc(void){abort();}
#define check_energy probe_energy
#define set_attacking probe_attack
#define set_idle probe_idle
#define ent_unlink probe_unlink
#define smart_bomb probe_bomb
#define ent_set_anim probe_anim
@SPECIAL@
static struct {char *branchname;} entries[3]={{"first"},{"next"},{"end"}};
static struct {char *branchname;} *unused_entry;
static int num_levels[]={3},current_level;
static char branch_name[32];
/* The branch window only reads branchname from this pointer table. */
static void branch_window(void) {
 unsigned which_set=0;int i;
 struct {char *branchname;} *levelorder[1][3];
 /* Use one explicitly declared compatible local record type below. */
 @BRANCH_SETUP@
 @BRANCH@
}
static void finish_window(void) {@CLEANUP@}
static void reset(int linked) {
 memset(&actor,0,sizeof(actor));memset(&target,0,sizeof(target));
 memset(&level_value,0,sizeof(level_value));memset(&animation,0,sizeof(animation));
 self=&actor;actor.link=linked?&target:NULL;target.takeaction=old_action;
 actor.modeldata.animation=table;table[ANI_SPECIAL]=&animation;
 animation.energycost.cost=3;actor.health=actor.mp=100;
 actor.running=1;actor.xdir=2;actor.zdir=1;
 for(int i=0;i<5;i++)actor.combostep[i]=1;
 mana=energy=1;nocost=healthcheat=0;smartbomber=NULL;
 at=unlinks=idles=0;trace[0]=0;
}
static void check(unsigned revision,int modern) {
 obor_profile_build=revision;
 for(int linked=0;linked<2;linked++)for(int freeze=0;freeze<2;freeze++)
 for(int smart=0;smart<2;smart++)for(int use_mp=0;use_mp<2;use_mp++)
 for(int free_cost=0;free_cost<3;free_cost++) {
  reset(linked);actor.modeldata.dofreeze=freeze;actor.modeldata.smartbomb=smart?&bomb:NULL;
  mana=use_mp;nocost=free_cost==1;healthcheat=free_cost==2;
  assert(check_special()==1);
  char expected[16]="A";
  if(modern && linked)strcat(expected,"I");
  if(!modern || linked)strcat(expected,"U");
  if(smart && !freeze)strcat(expected,"B");strcat(expected,"X");
  assert(!strcmp(trace,expected) && idles==(modern && linked) && unlinks==(!modern || linked));
  assert(!actor.link && target.takeaction==(modern && linked?NULL:old_action));
  assert(actor.takeaction==common_attack_proc && smartbomber==(freeze?self:NULL));
  assert(actor.health==100-(!use_mp && !free_cost?3:0) && actor.mp==100-(use_mp && !free_cost?3:0));
 }
 for(int reason=0;reason<3;reason++) {
  reset(1);if(reason==0)level->nospecial=1;if(reason==1)actor.cantfire=1;if(reason==2)energy=0;
  assert(!check_special() && !at && actor.link==&target && actor.health==100 && actor.mp==100);
 }
 reset(0);level->nospecial=3;assert(check_special()==1);
 current_level=1;branch_name[0]=0;branch_window();assert(current_level==1 && !branch_name[0]);
 current_level=0;strcpy(branch_name,"NEXT");branch_window();assert(current_level==1 && !branch_name[0]);
 current_level=1;strcpy(branch_name,"missing");branch_window();
 assert(current_level==1 && (!modern?!strcmp(branch_name,"missing"):!branch_name[0]));
 /* A later iteration may now match a previously unresolved old branch. */
 if(!modern)entries[2].branchname="missing";branch_window();
 assert(current_level==(modern?1:2) && !branch_name[0]);entries[2].branchname="end";
 strcpy(branch_name,"left-over");finish_window();
 assert(!modern?!strcmp(branch_name,"left-over"):!branch_name[0]);
}
int main(void){@CHECKS@ puts("early_special_branch=1");return 0;}
'''
        # Keep the branch-only provider independent from all other level fields.
        program = program.replace('static struct {char *branchname;} entries[3]', 'typedef struct {char *branchname;} branch_entry;\nstatic branch_entry entries[3]')
        program = program.replace('static struct {char *branchname;} *unused_entry;\n', '')
        program = program.replace('struct {char *branchname;} *levelorder[1][3];', 'branch_entry *levelorder[1][3];')
        for key, value in dict(SPECIAL=function(core, 'check_special'), BRANCH=branch, CLEANUP=cleanup,
                               BRANCH_SETUP='for(int j=0;j<3;j++)levelorder[0][j]=&entries[j];',
                               CHECKS='\n'.join(checks)).items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-special-branch-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            flags = ['-std=gnu99', '-O1', '-g', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                     '-fcommon', '-fsigned-char', '-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-unused-parameter', '-Wno-unused-variable', '-Wno-unused-function',
                     '-Wno-sign-compare', '-Wno-misleading-indentation', '-Wno-error=deprecated-declarations']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib',
                            'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + flags + [
                str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)],
                capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10,
                                 env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_special_branch=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
