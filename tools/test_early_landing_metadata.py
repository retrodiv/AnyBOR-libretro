"""Check own landframe metadata loading policy and safe landing bounds.

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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-landing-metadata.json'


class EarlyLandingMetadataTests(unittest.TestCase):
    def test_loader_policy_and_landing(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        load = function(source, 'load_cached_model')
        self.assertEqual(load.count('obor_landframe_load_check(newanim);'), 1)
        self.assertEqual(load.count('obor_landframe_model_check(newchar);'), 1)
        self.assertTrue('obor_landframe_load_check(newanim);\n\t\t\t\t\t\tnewchar->animation[ani_id] = newanim;' in load, "Early landframe check precedes animation publication")
        self.assertTrue('printf("Loading \'%s\' from %s\\n", newchar->name, filename);\n\tobor_landframe_model_check(newchar);' in load, "Final landframe check follows the loading diagnostic")
        gravity = function(source, 'check_gravity')
        begin = gravity.index('if(self->animation->landframe.frame>=0')
        end = gravity.index('// takedamage if thrown or basted', begin)
        landing = gravity[begin:end]
        self.assertIn('landframe.frame<= self->animation->numframes', landing)
        pieces = [function(source, 'obor_landframe_load_check'), function(source, 'obor_landframe_model_check')]
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            checks.append('check(%d,%d,%s);' % (row['revision'], row['disable'], json.dumps(row['warning'])))
        program = r'''
#include <assert.h>
#include <ctype.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#undef exit
#undef time
#undef kill
#undef pause
#undef shutdown
#undef printf
static char diagnostic[2048];
static int probe_printf(const char *format,...) {va_list ap;va_start(ap,format);int count=vsnprintf(diagnostic,sizeof(diagnostic),format,ap);va_end(ap);assert(count>=0);return count;}
#define printf probe_printf
uint32_t obor_profile_build;

int max_animations;
entity *self;
static entity dust;
static int updates,accepted,spawns,callbacks;
void update_frame(entity *ent,int frame){updates++;if(frame>=ent->animation->numframes)return;accepted++;ent->animpos=frame;}
entity *spawn(float x,float z,float a,int direction,char *name,int model,s_model *owner){
 (void)x;(void)z;(void)a;(void)direction;(void)name;(void)owner;assert(model==7);spawns++;return &dust;
}
void execute_onspawn_script(entity *ent){assert(ent==&dust && ent->base==self->a && ent->autokill==1);callbacks++;}
@PIECES@
static void land(void){entity *dust;@LANDING@}
static void check(unsigned revision,int disable,const char *warning){
 s_anim anims[3],*pointers[3];s_model model;entity ent;
 obor_profile_build=revision;
 for(int frame=-2;frame<=5;frame++)for(int frames=0;frames<=4;frames++){
  memset(anims,0,sizeof(anims));anims[0].landframe.frame=frame;anims[0].numframes=frames;diagnostic[0]=0;
  obor_landframe_load_check(&anims[0]);
  int changed=disable && frame>=frames;
  assert(anims[0].landframe.frame==(changed?-1:frame));
  assert(!strcmp(diagnostic,changed?warning:""));
 }
 memset(anims,0,sizeof(anims));memset(&model,0,sizeof(model));model.animation=pointers;model.animation_capacity=3;max_animations=2;
 for(int i=0;i<3;i++){pointers[i]=&anims[i];anims[i].numframes=2;anims[i].landframe.frame=2+i;}
 pointers[0]=NULL;diagnostic[0]=0;obor_landframe_model_check(&model);
 assert(anims[1].landframe.frame==(disable?-1:3) && anims[2].landframe.frame==4);
 assert(!strcmp(diagnostic,disable?warning:""));
 model.animation_capacity=1;obor_landframe_model_check(&model);
 obor_landframe_load_check(NULL);obor_landframe_model_check(NULL);model.animation=NULL;obor_landframe_model_check(&model);
 for(int frame=-1;frame<=4;frame++)for(int position=0;position<=3;position++)for(int effect=0;effect<2;effect++){
  memset(&ent,0,sizeof(ent));memset(anims,0,sizeof(anims));memset(&dust,0,sizeof(dust));self=&ent;ent.animation=&anims[0];ent.a=12.5;ent.animpos=position;
  anims[0].numframes=3;anims[0].landframe.frame=frame;anims[0].landframe.ent=effect?7:-1;
  updates=accepted=spawns=callbacks=0;land();
  int active=frame>=0 && frame<=3 && position<frame;
  assert(updates==active && accepted==(active && frame<3));
  assert(spawns==(active && effect) && callbacks==spawns);
  assert(ent.animpos==((active && frame<3)?frame:position));
 }
}
int main(void){@CHECKS@ puts("early_landing_metadata=1");return 0;}

'''
        program = program.replace('@PIECES@', '\n'.join(pieces)).replace('@CHECKS@', '\n'.join(checks)).replace('@LANDING@', landing)
        with tempfile.TemporaryDirectory(prefix='early-landing-metadata-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1', '-Dstricmp=strcasecmp',
                     '-fcommon', '-fsigned-char', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                     '-Wall', '-Wextra', '-Werror', '-Wno-unused-variable', '-Wno-unused-function', '-Wno-sign-compare',
                     '-Wno-misleading-indentation', '-Wno-error=deprecated-declarations']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib', 'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20, env=sanitizer_environment())
            if os.environ.get('OBOR_LANDING_METADATA_OBSERVATIONS'):
                Path(os.environ['OBOR_LANDING_METADATA_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=cc, flags=flags, contexts=len(rows), probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(), binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    returncode=run.returncode, stdout=run.stdout, stderr=run.stderr, scope=fixture['scope'],
                    retirement='TemporaryDirectory removes source/binary'), indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_landing_metadata=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
