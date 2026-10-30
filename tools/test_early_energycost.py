"""Check historical energycost signatures, conversions and mapper boundaries.

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
from test_historical_player import function, switch_cases

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-energycost.json'


class EarlyEnergycostTests(unittest.TestCase):
    def test_signatures_results_and_diagnostics(self):
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
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        model_source = (engine / 'openbor.c').read_text()
        loader = function(model_source, 'load_cached_model')
        begin = loader.index('case CMD_MODEL_ENERGYCOST:')
        loader_cases = loader[begin:loader.index('case CMD_MODEL_CHARGETIME:', begin)]
        enum_get = source[source.index('enum getentityproperty_enum'):source.index('void mapstrings_getentityproperty(')]
        enum_set = source[source.index('enum changeentityproperty_enum'):source.index('void mapstrings_changeentityproperty(')]
        descriptor = namespace_descriptor(source, 'obor_property_namespace')
        self.assertIsNotNone(descriptor)
        macro = re.search(r'(?m)^#define MAPSTRINGS\([^\n]+(?:\n[^\n]*)*?\n}', source)
        self.assertIsNotNone(macro)
        pieces = [descriptor, '\n'.join('static const obor_property_namespace *' + name + '(void);' for name in [
            'obor_get_property_namespace', 'obor_set_property_namespace', 'obor_get_aiflag_namespace', 'obor_set_aiflag_namespace']),
            function(source, 'obor_property_index'), function(source, 'obor_legacy_energycost'), enum_get, enum_set,
            function((engine / 'source/utils.c').read_text(), 'searchList'), macro[0],
            function(source, 'mapstrings_getentityproperty'), function(source, 'mapstrings_changeentityproperty')]
        pieces += [function(variant, name) for name in ['ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue']]
        pieces += [selected_dispatch(source, 'openbor_getentityproperty', ['_gep_energycost']),
                   selected_dispatch(source, 'openbor_changeentityproperty', ['_cep_energycost'])]
        checks = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIs(type(row['legacy']), bool)
            self.assertIs(type(row['integer_animation']), bool)
            checks.append('check(%d,%d,%d,%d,%d);' % (row['revision'], row['legacy'], row['integer_animation'], row['getter_id'], row['setter_id']))
        program = r'''
#include <assert.h>
#include <ctype.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#include "commands.h"
#undef exit
#undef time
#undef kill
#undef pause
#undef shutdown
#undef printf
static char diagnostic[8192];
static int probe_printf(const char *format,...) {va_list ap;va_start(ap,format);int count=vsnprintf(diagnostic+strlen(diagnostic),sizeof(diagnostic)-strlen(diagnostic),format,ap);va_end(ap);assert(count>=0);return count;}
#define printf probe_printf
uint32_t obor_profile_build;
static char *cache[4096];
CHAR *StrCache_Get(int index) {assert(index>=0 && index<4096 && cache[index]);return cache[index];}
void StrCache_Collect(int index) {assert(index>=0 && index<4096);}
int StrCache_Pop(void) {abort();}
@PIECES@
typedef struct {@OLD_FIELD@} obor_original_animation;
@MODERN_ORACLE@
static const int storage_values[]={@STORAGE_VALUES@};
static ScriptVariant values[8],result,*args[8],*out;
static entity e;
static s_anim animations[3],*table[3];
static void setup(int property,int selector,int animation,int legacy,int setter) {
 memset(values,0,sizeof(values));memset(&result,0,sizeof(result));memset(&e,0,sizeof(e));memset(animations,0,sizeof(animations));
 for(int i=0;i<8;i++) {args[i]=&values[i];values[i].vt=VT_INTEGER;}
 values[0].vt=VT_PTR;values[0].ptrVal=&e;values[1].lVal=property;
 values[2].lVal=(legacy && !setter)?animation:selector;values[3].lVal=(legacy && !setter)?selector:animation;
 if(legacy && setter) {values[2].lVal=animation;values[3].lVal=11;values[4].lVal=12;values[5].lVal=13;}
 else if(setter)values[4].lVal=11;
 for(int i=0;i<3;i++) {
  table[i]=i==1?NULL:&animations[i];animations[i].numframes=1;
  animations[i].energycost.cost=21+i;animations[i].energycost.mponly=31+i;animations[i].energycost.disable=41+i;
 }
 e.modeldata.animation=table;e.modeldata.animation_capacity=3;out=&result;diagnostic[0]=0;
}
#define GET_INT_ARG(index) input[index]
static void model_values(int command,int value) {
 s_anim *newanim=&animations[0];int input[]={0,value,value,value};
 switch(command) {@LOADER_CASES@ default:abort();}
}
#undef GET_INT_ARG
static void text(int at,const char *value) {cache[1000+at]=(char*)value;values[at].vt=VT_STR;values[at].strVal=1000+at;}
static int expected(int selector,int animation,int legacy) {
 if(legacy) {const int values[]={21+animation,31+animation,41+animation};return values[selector];}
 const int values[]={21+animation,41+animation,31+animation};return values[selector];
}
static void fields(int animation,int cost,int mp,int disable) {
 assert(animations[animation].energycost.cost==cost && animations[animation].energycost.mponly==mp && animations[animation].energycost.disable==disable);
}
static void check(unsigned revision,int legacy,int integer_animation,int getter,int setter) {
 obor_profile_build=revision;
 const char *subnames[]={"cost","disable","mponly"};
 for(int animation=0;animation<3;animation+=2)for(int selector=0;selector<3;selector++)for(int named=0;named<2;named++) {
  setup(getter,selector,animation,legacy,0);if(named) {text(1,"energycost");if(!legacy)text(2,subnames[selector]);}
  mapstrings_getentityproperty(args,4);mapstrings_getentityproperty(args,4);
  assert(values[1].vt==VT_INTEGER && values[1].lVal==getter);
  assert(openbor_getentityproperty(args,&out,4)==S_OK && out==&result && out->vt==VT_INTEGER && out->lVal==expected(selector,animation,legacy));
  assert(!diagnostic[0]);
 }
 for(int count=2;count<=7;count++) {
  setup(getter,0,0,legacy,0);HRESULT hr=openbor_getentityproperty(args,&out,count);
  if(legacy && count!=4) {assert(hr==E_FAIL && out==&result && out->vt==VT_EMPTY);assert(!strcmp(diagnostic,@OLD_GET_COUNT@));}
  else if(count<4)assert(hr==S_OK && out && out->vt==VT_EMPTY);
  else assert(hr==S_OK && out && out->vt==VT_INTEGER && out->lVal==21);
 }
 for(int animation=-1;animation<=3;animation++)if(animation!=0 && animation!=2) {
  setup(getter,0,animation,legacy,0);HRESULT hr=openbor_getentityproperty(args,&out,4);
  assert(out && out->vt==VT_EMPTY);if(legacy) {assert(hr==E_FAIL);assert(!strcmp(diagnostic,@OLD_GET_ANIMATION@));}else assert(hr==S_OK && !diagnostic[0]);
 }
 setup(getter,0,0,legacy,0);values[legacy?2:3].vt=VT_EMPTY;values[legacy?2:3].lVal=0;
 HRESULT hr=openbor_getentityproperty(args,&out,4);
 if(integer_animation) {assert(hr==E_FAIL && out && out->vt==VT_EMPTY);assert(!strcmp(diagnostic,legacy?@OLD_GET_COUNT@:@MID_GET_TYPES@));}
 else assert(hr==S_OK && out && out->vt==VT_INTEGER && out->lVal==21 && !diagnostic[0]);
 setup(getter,0,0,legacy,0);values[legacy?3:2].vt=VT_EMPTY;values[legacy?3:2].lVal=0;
 assert(openbor_getentityproperty(args,&out,4)==E_FAIL);
 assert(!strcmp(diagnostic,legacy?@OLD_GET_COUNT@:(integer_animation?@MID_GET_TYPES@:@NEW_GET_TYPE@)));
 for(int invalid=-1;invalid<=3;invalid+=4) {setup(getter,invalid,0,legacy,0);assert(openbor_getentityproperty(args,&out,4)==E_FAIL && out);}
 /* Old positional writes perform independent conversions and keep their successful ones. */
 if(legacy)for(int mask=0;mask<8;mask++) {
  setup(setter,0,2,legacy,1);for(int i=0;i<3;i++)if(!(mask&(1<<i)))values[i+3].vt=VT_EMPTY;
  assert(openbor_changeentityproperty(args,&out,6)==S_OK && out && out->vt==VT_INTEGER && out->lVal==1);
  fields(2,mask&1?11:23,mask&2?12:33,mask&4?13:43);fields(0,21,31,41);
 }
 if(!legacy)for(int selector=0;selector<3;selector++)for(int named=0;named<2;named++)for(int value_type=0;value_type<3;value_type++) {
  setup(setter,selector,2,legacy,1);if(named) {text(1,"energycost");text(2,subnames[selector]);}
  if(value_type==1) {values[4].vt=VT_DECIMAL;values[4].dblVal=11.75;}else if(value_type==2)values[4].vt=VT_EMPTY;
  mapstrings_changeentityproperty(args,5);mapstrings_changeentityproperty(args,5);
  assert(openbor_changeentityproperty(args,&out,5)==S_OK && out && out->vt==VT_INTEGER && out->lVal==1);
  fields(2,selector==0 && value_type!=2?11:23,selector==2 && value_type!=2?11:33,selector==1 && value_type!=2?11:43);
 }
 for(int count=3;count<=7;count++) {
  setup(setter,0,0,legacy,1);HRESULT hr=openbor_changeentityproperty(args,&out,count);
  if(count==(legacy?6:5))assert(hr==S_OK && out && out->lVal==1);
  else {assert(hr==E_FAIL && !out);assert(!strcmp(diagnostic,legacy?@OLD_SET_COUNT@:@NEW_SET_COUNT@));}
 }
 setup(setter,0,0,legacy,1);values[legacy?2:3].vt=VT_EMPTY;
 assert(openbor_changeentityproperty(args,&out,legacy?6:5)==S_OK && out && out->lVal==1);
 fields(0,11,legacy?12:31,legacy?13:41);
 setup(setter,0,1,legacy,1);assert(openbor_changeentityproperty(args,&out,legacy?6:5)==E_FAIL && !out);
 assert(!strcmp(diagnostic,legacy?@OLD_SET_ANIMATION@:@NEW_SET_ANIMATION@));
 if(!legacy) {
  setup(setter,0,0,legacy,1);text(2,"unknown-cost");assert(openbor_changeentityproperty(args,&out,5)==E_FAIL && !out);
  setup(setter,-1,0,legacy,1);assert(openbor_changeentityproperty(args,&out,5)==E_FAIL && !out && !strcmp(diagnostic,"Unknown Energycost flag.\n"));
 }
 /* Own original declarations provide the compiler-dependent narrowing control. */
 for(size_t at=0;at<sizeof(storage_values)/sizeof(storage_values[0]);at++) {
  int value=storage_values[at];obor_original_animation old={0};obor_original_energycost modern={0};
  for(int i=0;i<3;i++)old.energycost[i]=value;modern.cost=value;modern.mponly=value;modern.disable=value;
  int cost=legacy?old.energycost[0]:modern.cost,mp=legacy?old.energycost[1]:modern.mponly,disable=legacy?old.energycost[2]:modern.disable;
  setup(setter,0,0,legacy,1);
  if(legacy) {values[3].lVal=value;values[4].lVal=value;values[5].lVal=value;assert(openbor_changeentityproperty(args,&out,6)==S_OK && out && out->lVal==1);fields(0,cost,mp,disable);}
  else for(int selector=0;selector<3;selector++) {setup(setter,selector,0,legacy,1);values[4].lVal=value;assert(openbor_changeentityproperty(args,&out,5)==S_OK && out && out->lVal==1);fields(0,selector==0?cost:21,selector==2?mp:31,selector==1?disable:41);}
  setup(getter,0,0,legacy,0);const int commands[]={CMD_MODEL_ENERGYCOST,CMD_MODEL_MPCOST};
  for(int c=0;c<2;c++) {model_values(commands[c],value);fields(0,cost,mp,disable);}
  for(int selector=0;selector<3;selector++) {
   values[1].vt=VT_INTEGER;values[1].lVal=getter;values[2].vt=VT_INTEGER;values[3].vt=VT_INTEGER;
   values[2].lVal=legacy?0:selector;values[3].lVal=legacy?selector:0;out=&result;
   const int expected[]={cost,legacy?mp:disable,legacy?disable:mp};
   assert(openbor_getentityproperty(args,&out,4)==S_OK && out && out->vt==VT_INTEGER && out->lVal==expected[selector]);
  }
  setup(getter,0,0,legacy,0);model_values(CMD_MODEL_MPONLY,value);fields(0,21,mp,41);
 }
 /* Exact-size argument vectors check the mapper separately from callback count validation. */
 for(int count=0;count<=2;count++) {
  setup(setter,0,0,legacy,1);text(1,"energycost");ScriptVariant **short_args=count?malloc(count*sizeof(*args)):NULL;
  for(int i=0;i<count;i++)short_args[i]=args[i];mapstrings_changeentityproperty(short_args,count);free(short_args);
  if(count==2)assert(values[1].vt==(legacy?VT_STR:VT_INTEGER));
 }
}
int main(void) {@CHECKS@ puts("early_energycost=1");return 0;}
'''
        replacements = dict(PIECES='\n'.join(pieces), CHECKS='\n'.join(checks), LOADER_CASES=loader_cases,
                            OLD_FIELD=fixture['storage_oracle']['legacy_field'], MODERN_ORACLE=fixture['storage_oracle']['modern_struct'],
                            STORAGE_VALUES=','.join(map(str, fixture['storage_values'])),
                            **{key: json.dumps(value) for key, value in fixture['diagnostics'].items()})
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        self.assertNotRegex(program, r'@[A-Z_]+@')
        with tempfile.TemporaryDirectory(prefix='early-energycost-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                     '-Dstricmp=strcasecmp', '-fcommon', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                     '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror', '-Wno-unused-variable', '-Wno-unused-function',
                     '-Wno-sign-compare', '-Wno-misleading-indentation', '-Wno-error=deprecated-declarations']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib', 'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)],
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20, env=sanitizer_environment())
            if os.environ.get('OBOR_ENERGYCOST_OBSERVATIONS'):
                Path(os.environ['OBOR_ENERGYCOST_OBSERVATIONS']).write_text(json.dumps({
                    'compiler': cc, 'flags': flags, 'contexts': len(rows), 'probe_sha256': hashlib.sha256(program.encode()).hexdigest(),
                    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                    'header_sha256': hashlib.sha256((engine / 'openbor.h').read_bytes()).hexdigest(),
                    'model_source_sha256': hashlib.sha256(model_source.encode()).hexdigest(), 'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr, 'scope': fixture['scope'],
                    'retirement': 'TemporaryDirectory removes source/binary'}, indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_energycost=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
