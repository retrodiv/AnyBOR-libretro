"""Check spawn metadata publication and historical projectile-type setters.

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
from test_early_entity_namespaces import namespace_descriptor, selected_dispatch
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-entity-origin-masks.json'


class EarlyEntityOriginMaskTests(unittest.TestCase):
    def test_markers_callbacks_and_projectile_types(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openborscript.c').read_text()
        core = (engine / 'openbor.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        descriptor = namespace_descriptor(source, 'obor_property_namespace')
        macro = re.search(r'(?m)^#define MAPSTRINGS\([^\n]+(?:\n[^\n]*)*?\n}', source)
        self.assertIsNotNone(descriptor)
        self.assertIsNotNone(macro)
        pieces = [descriptor, '\n'.join('static const obor_property_namespace *' + name + '(void);' for name in [
            'obor_get_property_namespace', 'obor_set_property_namespace', 'obor_get_aiflag_namespace', 'obor_set_aiflag_namespace']),
            function(source, 'obor_property_index'),
            source[source.index('enum getentityproperty_enum'):source.index('void mapstrings_getentityproperty(')],
            source[source.index('enum changeentityproperty_enum'):source.index('void mapstrings_changeentityproperty(')],
            function((engine / 'source/utils.c').read_text(), 'searchList'), macro[0],
            function(source, 'mapstrings_getentityproperty'), function(source, 'mapstrings_changeentityproperty')]
        pieces += [function(variant, name) for name in ['ScriptVariant_ChangeType', 'ScriptVariant_Clear']]
        pieces += [selected_dispatch(source, 'openbor_getentityproperty', ['_gep_exists', '_gep_spawntype']),
                   selected_dispatch(source, 'openbor_changeentityproperty', ['_cep_projectilehit'])]
        marker = re.findall(r'(?m)^\s*next\.spawntype\s*=[^;\n]*;', function(core, 'load_level'))
        self.assertEqual(len(marker), 1)
        arrays, checks = [], []
        for row in rows:
            suffix = str(row['revision'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertTrue(all(re.fullmatch(r'0|TYPE_[A-Z_]+', item) for item in row['entity_type_constants']))
            arrays += ['static const int types' + suffix + '[]={' + ','.join(row['entity_type_constants']) + '};',
                       'static const char *names' + suffix + '[]={' + ','.join(map(json.dumps, row['entity_type_names'])) + '};']
            checks.append('check(%d,%d,%d,%d,%d,%s,%s,%s,%s,types%s,names%s);' % (
                row['revision'], row['origin_mode'], row['exists_id'], row['origin_id'], row['projectile_id'],
                json.dumps(row['exists_literal']), json.dumps(row['origin_literal']), json.dumps(row['projectile_literal']),
                json.dumps(row['projectile_error']), suffix, suffix))
        program = r'''
#include <assert.h>
#include <ctype.h>
#include <limits.h>
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
uint32_t obor_profile_build;
static char diagnostic[4096],cache[1024][128],trace[8];
static int trace_at,reject_spawn,mutate_exists,expected_exists,expected_origin,exists_id,origin_id;
static s_level instance;
s_level *level;
float advancex,advancey;
static entity spawned;
static s_model model;
static ScriptVariant values[8],result,*args[8],*out;
CHAR *StrCache_Get(int index){assert(index>=0 && index<1024);return cache[index];}
void StrCache_Collect(int index){(void)index;}
int StrCache_Pop(void){abort();}
static int probe_printf(const char *format,...){va_list ap;va_start(ap,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,ap);va_end(ap);return n;}
#define printf probe_printf
@PIECES@
static void setup(int property){memset(values,0,sizeof(values));memset(&result,0,sizeof(result));for(int i=0;i<8;i++){args[i]=&values[i];values[i].vt=VT_INTEGER;}values[0].vt=VT_PTR;values[0].ptrVal=&spawned;values[1].lVal=property;out=&result;diagnostic[0]=0;}
static void text(int at,const char *value){strcpy(cache[700+at],value);values[at].vt=VT_STR;values[at].strVal=700+at;}
static void query(int property,int expected){setup(property);assert(openbor_getentityproperty(args,&out,2)==S_OK && out && out->vt==VT_INTEGER && out->lVal==expected);}
static void record(char c){assert(trace_at<7);trace[trace_at++]=c;trace[trace_at]=0;}
entity *spawn(float x,float z,float a,int direction,char *name,int index,s_model *m){(void)x;(void)z;(void)a;(void)direction;assert(name && !strcmp(name,"model") && index==0 && m==&model);if(reject_spawn)return NULL;memset(&spawned,0,sizeof(spawned));spawned.exists=1;record('S');return &spawned;}
int count_ents(int types){assert(types==TYPE_PLAYER);return 1;}
void ent_set_colourmap(entity *e,unsigned int index){(void)e;(void)index;abort();}
void set_weapon(entity *e,int index,int anim){(void)e;(void)index;(void)anim;abort();}
int music(char *file,int loop,long offset){(void)file;(void)loop;(void)offset;abort();}
void execute_onspawn_script(entity *e){assert(e==&spawned);query(exists_id,expected_exists);if(origin_id>=0)query(origin_id,expected_origin);record('O');if(mutate_exists)e->exists=0;}
void execute_spawn_script(s_spawn_entry *props,entity *e){assert(props && e==&spawned);query(exists_id,mutate_exists?0:expected_exists);if(origin_id>=0)query(origin_id,expected_origin);record('P');}
@SMARTSPAWN@
static void entry_marker(s_spawn_entry *props){s_spawn_entry next=*props;@MARKER@ *props=next;}
@ARRAYS@
static void check(unsigned revision,int mode,int exid,int orid,int pid,const char *exists_literal,const char *origin_literal,const char *projectile_literal,const char *type_error,const int *types,const char *const *names){
 obor_profile_build=revision;exists_id=exid;origin_id=orid;memset(&instance,0,sizeof(instance));level=&instance;
 s_spawn_entry props;memset(&props,0,sizeof(props));props.name=(char*)"model";props.model=&model;props.spawntype=127;
 entry_marker(&props);assert(props.spawntype==mode);
 const int flags[]={0,1,2,-1,127,-128};
 for(int i=0;i<6;i++)for(int mutation=0;mutation<2;mutation++){
  props.spawntype=flags[i];expected_exists=mode==2 && flags[i]?2:1;expected_origin=mode==1?flags[i]:0;mutate_exists=mutation;
  trace_at=0;trace[0]=0;reject_spawn=0;assert(smartspawn(&props)==&spawned && !strcmp(trace,"SOP"));
  assert(spawned.exists==(mutation?0:expected_exists) && spawned.spawntype==expected_origin);
 }
 mutate_exists=0;reject_spawn=1;trace_at=0;trace[0]=0;assert(!smartspawn(&props) && !trace[0]);reject_spawn=0;
 assert(!smartspawn(NULL));level=NULL;assert(!smartspawn(&props));level=&instance;
 spawned.exists=2;spawned.spawntype=-7;setup(exid);text(1,exists_literal);mapstrings_getentityproperty(args,2);mapstrings_getentityproperty(args,2);assert(openbor_getentityproperty(args,&out,2)==S_OK && out && out->lVal==2);
 if(orid>=0){setup(orid);text(1,origin_literal);assert(openbor_getentityproperty(args,&out,2)==S_OK && out && out->lVal==-7);}
 else {setup(0);text(1,"spawntype");mapstrings_getentityproperty(args,2);assert(values[1].vt==VT_STR);}
 setup(0);text(1,"projectilehit");mapstrings_getentityproperty(args,2);assert(values[1].vt==VT_STR);
 if(pid<0){spawned.modeldata.projectilehit=777;setup(0);text(1,"projectilehit");assert(openbor_changeentityproperty(args,&out,3)==E_FAIL && !out && spawned.modeldata.projectilehit==777);return;}
 for(int i=0;i<6;i++)for(int named=0;named<2;named++){
  spawned.modeldata.projectilehit=777;setup(pid);values[2].lVal=i;
  if(named){text(1,projectile_literal);text(2,names[i]);mapstrings_changeentityproperty(args,3);mapstrings_changeentityproperty(args,3);}
  assert(openbor_changeentityproperty(args,&out,3)==S_OK && out && out->vt==VT_INTEGER && out->lVal==0 && spawned.modeldata.projectilehit==types[i]);
 }
 setup(pid);int mask=0;for(int i=0;i<6;i++){text(i+2,names[i]);mask|=types[i];}assert(openbor_changeentityproperty(args,&out,8)==S_OK && out && spawned.modeldata.projectilehit==mask);
 setup(pid);values[2].lVal=1;values[3].vt=VT_EMPTY;assert(openbor_changeentityproperty(args,&out,4)==E_FAIL && !out && spawned.modeldata.projectilehit==types[1] && !strcmp(diagnostic,type_error));
 const int invalid[]={-1,6,INT_MIN,INT_MAX};
 for(int i=0;i<4;i++){setup(pid);values[2].lVal=1;values[3].lVal=invalid[i];assert(openbor_changeentityproperty(args,&out,4)==E_FAIL && !out && spawned.modeldata.projectilehit==types[1]);}
}
int main(void){@CHECKS@ puts("early_entity_origin_masks=1");return 0;}
'''
        for key, value in dict(PIECES='\n'.join(pieces), ARRAYS='\n'.join(arrays), CHECKS='\n'.join(checks),
                               SMARTSPAWN=function(core, 'smartspawn'), MARKER=marker[0]).items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-entity-origin-masks-') as name:
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
            if os.environ.get('OBOR_ENTITY_ORIGIN_MASK_OBSERVATIONS'):
                Path(os.environ['OBOR_ENTITY_ORIGIN_MASK_OBSERVATIONS']).write_text(json.dumps(dict(compiler=cc,flags=flags,
                    contexts=len(rows),probe_sha256=hashlib.sha256(program.encode()).hexdigest(),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    core_sha256=hashlib.sha256(core.encode()).hexdigest(),script_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    returncode=run.returncode,stdout=run.stdout,stderr=run.stderr,scope=fixture['scope'],retirement='TemporaryDirectory removes source/binary'),indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_entity_origin_masks=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
