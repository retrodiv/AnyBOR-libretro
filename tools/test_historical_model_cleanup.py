"""Check whole model cleanup against each profile's ownership contract.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from test_historical_player import function

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))


class ModelCleanupTests(unittest.TestCase):
    def test_owned_and_borrowed_records_match_each_source_profile(self):
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-model-cleanup-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(len(row['defense_fields']),
                             7 if row['separate_defense_arrays'] else 1)
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
        warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        host_flags = [] if sys.platform == 'darwin' else ['-DLINUX=1']
        for engine in sorted({row['engine'] for row in rows}):
            with self.subTest(engine=engine), tempfile.TemporaryDirectory(
                    prefix='anybor-model-cleanup-') as temporary:
                root = SOURCE / 'src/engines' / engine
                source = (root / 'openbor.c').read_text()
                program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
uint32_t obor_profile_build;
static unsigned test_case;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Model cleanup: revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
static int models_loaded,animation_calls,script_clear_calls,script_free_calls,delete_calls;
static void *defense_pointer,*offense_pointer;
static int defense_live,offense_live,defense_released,offense_released;
static s_model subject;
static s_modelcache cache[3];
static int quiet(const char *format,...) {(void)format;return 0;}
static void release(void *pointer) {
 if(!pointer)return;
 if(pointer==defense_pointer){assert(defense_live);defense_live=0;++defense_released;}
 else if(pointer==offense_pointer){assert(offense_live);offense_live=0;++offense_released;}
 else assert(0);
 free(pointer);
}
static void *obor_colourmap_owner_find(s_model *model) {assert(model==&subject);return NULL;}
static void obor_colourmap_owner_release(s_model *model) {(void)model;abort();}
void anim_list_delete(int index) {assert(index==1);++animation_calls;}
void clear_all_scripts(s_scripts *scripts,int method) {
 assert(!scripts && method==2);++script_clear_calls;
}
void free_all_scripts(s_scripts **scripts) {
 assert(scripts==&subject.scripts && !*scripts);++script_free_calls;
}
void deleteModel(char *name) {
 assert(name==subject.name && !cache[1].model);++delete_calls;
}
HAS_FREETYPE
#undef printf
#define printf quiet
#define free release
FREE_MODEL
#undef free
#undef printf
static void check(unsigned mask,unsigned presence) {
 memset(&subject,0,sizeof(subject));memset(cache,0,sizeof(cache));
 subject.name="subject";subject.index=1;subject.freetypes=(ModelFreetype)mask;
 model_cache=cache;cache[0].model=cache[1].model=cache[2].model=&subject;
 animation_calls=script_clear_calls=script_free_calls=delete_calls=0;
 defense_pointer=offense_pointer=NULL;defense_live=offense_live=0;
 defense_released=offense_released=0;
 unsigned char defense_before[3*sizeof(*subject.defense)],offense_before[3*sizeof(*subject.offense_factors)];
 if(presence&1) {
  subject.defense=malloc(sizeof(defense_before));assert(subject.defense);
  memset(subject.defense,0x5a,sizeof(defense_before));memcpy(defense_before,subject.defense,sizeof(defense_before));
  defense_pointer=subject.defense;defense_live=1;
 }
 if(presence&2) {
  subject.offense_factors=malloc(sizeof(offense_before));assert(subject.offense_factors);
  memset(subject.offense_factors,0x36,sizeof(offense_before));memcpy(offense_before,subject.offense_factors,sizeof(offense_before));
  offense_pointer=subject.offense_factors;offense_live=1;
 }
 models_loaded=7;assert(free_model(&subject)==7 && models_loaded==6);
 assert(!cache[1].model && cache[0].model==&subject && cache[2].model==&subject);
 assert(delete_calls==1 && animation_calls==!!(mask&MF_ANIMLIST));
 assert(script_clear_calls==!!(mask&MF_SCRIPTS) && script_free_calls==script_clear_calls);
 int own_defense=!!(presence&1) && !!(mask&MF_DEFENSE);
 int own_offense=!!(presence&2) && !!(mask&MF_OFF_FACTORS);
 assert(defense_released==own_defense && offense_released==own_offense);
 assert(subject.defense==(own_defense?NULL:defense_pointer));
 assert(subject.offense_factors==(own_offense?NULL:offense_pointer));
 if(defense_live){assert(!memcmp(subject.defense,defense_before,sizeof(defense_before)));free(defense_pointer);}
 if(offense_live){assert(!memcmp(subject.offense_factors,offense_before,sizeof(offense_before)));free(offense_pointer);}
}
int main(void) {
 const unsigned revisions[]={REVISIONS};
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i) {
  obor_profile_build=revisions[i];models_loaded=7;test_case=0;
  assert(free_model(NULL)==0 && models_loaded==7);
  for(unsigned mask=0;mask<=MF_ALL;++mask)for(unsigned presence=0;presence<4;++presence){
   ++test_case;check(mask,presence);
  }
 }
 return 0;
}
'''
                for key, value in (
                        ('HAS_FREETYPE', function(source, 'hasFreetype')),
                        ('FREE_MODEL', function(source, 'free_model')),
                        ('REVISIONS', ','.join(str(row['revision']) for row in rows
                                               if row['engine'] == engine))):
                    program = program.replace(key, value)
                work = Path(temporary)
                probe = work / 'probe.c'
                probe.write_text(program)
                includes = [root, SOURCE / 'src/port/libretro', SOURCE / 'src/glue',
                            root / 'source', *sorted(p for p in (root / 'source').iterdir()
                                                    if p.is_dir())]
                command = compiler + ['-I' + str(p) for p in includes] + [
                    '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-Wno-error=deprecated-declarations', '-Wno-error=misleading-indentation',
                    '-Wno-unused-variable',
                    '-Wno-unused-function', '-Wno-unused-parameter', *warnings,
                    '-g', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=' + engine,
                    *host_flags, '-fsigned-char', '-ffunction-sections', '-fdata-sections',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    str(probe), *links, '-o', str(work / 'probe')]
                subprocess.run(command, check=True, timeout=60)
                subprocess.run([str(work / 'probe')], check=True, timeout=30,
                               env=sanitizer_environment(), stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    unittest.main()
