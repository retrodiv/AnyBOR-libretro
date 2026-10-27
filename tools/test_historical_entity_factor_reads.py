"""Check factor getter targets against each profile's own original callback.

Only defense/offense cases execute. Numeric mapping and field layout are reduced
fixtures; actual string domains, native initialization and combat have separate
contracts. Variant conversion and callback entry/exit retain their source code.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from test_historical_player import function, rename_identifiers, switch_cases

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
CONTRACTS = json.loads((Path(__file__).parent /
    'fixtures/profile-entity-factor-read-contracts.json').read_text())


def reader_entry(source, name='openbor_getentityproperty'):
    method, cases = switch_cases(source, 'openbor_getentityproperty', 'propind')
    for label, row in sorted(cases.items(), key=lambda item: item[1]['label_start'], reverse=True):
        if label not in ('_ep_defense', '_ep_offense', 'default'):
            method = method[:row['label_start']] + method[row['end']:]
    return rename_identifiers(method, {'openbor_getentityproperty': name})


def reader_program(components=None, common=None, contracts=None, *, original=False):
    rows = CONTRACTS['sources'] if contracts is None else contracts
    if components is None:
        source = (SOURCE / 'src/engines/3741/openborscript.c').read_text()
        components = {'entries': reader_entry(source),
            'invoke': 'return openbor_getentityproperty(args,output,count);',
            'translation': 'static int obor_entity_get_property_native(int property) {return property;}'}
        variant = (SOURCE / 'src/engines/3741/source/scriptlib/ScriptVariant.c').read_text()
        common = {name: function(variant, name) for name in
            ('ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue')}
    if common is None:
        raise ValueError('Explicit source conversion functions required')
    contracts_c = ','.join('{%d,%d,%d}' % (row['revision'],
        row['defense_target'] == 'model', row['offense_target'] == 'model') for row in rows)
    program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int32_t LONG,HRESULT;
typedef double DOUBLE;
typedef void VOID;
typedef enum {VT_EMPTY=0,VT_INTEGER=1,VT_DECIMAL=2,VT_PTR=5,VT_STR=6} VARTYPE;
typedef struct {union {LONG lVal;DOUBLE dblVal;void *ptrVal;int strVal;};VARTYPE vt;} ScriptVariant;
typedef struct {int marker;} s_sprite,s_attack;
enum {_ep_defense,_ep_offense};
enum {_gep_defense_factor,_gep_defense_pain,_gep_defense_knockdown,
 _gep_defense_blockpower,_gep_defense_blockthreshold,_gep_defense_blockratio,_gep_defense_blocktype};
#define MAX_ATKS 16
#define S_OK 0
#define E_FAIL (-1)
#define FAILED(x) ((x)<0)
#define SUCCEEDED(x) ((x)>=0)
typedef struct {float factor,pain,knockdown,blockpower,blockthreshold,blockratio,blocktype;} s_defense;
typedef struct {
 s_defense *defense;float *offense_factors;
 float *defense_factors,*defense_pain,*defense_knockdown,*defense_blockpower;
 float *defense_blockthreshold,*defense_blockratio,*defense_blocktype;
} s_model;
typedef struct {s_model modeldata;s_defense *defense;float *offense_factors;} entity;
static uint32_t obor_profile_build;
static s_defense shared_defense[MAX_ATKS],private_defense[2][MAX_ATKS];
static float shared_offense[MAX_ATKS],private_offense[2][MAX_ATKS],separate[7][MAX_ATKS];
static entity actors[2];
static int StrCache_Pop(void) {abort();}
static void StrCache_Collect(int index) {(void)index;abort();}
static int quiet_printf(const char *format,...) {(void)format;return 0;}
#define printf quiet_printf
@CONVERSIONS@
static void mapstrings_getentityproperty(ScriptVariant **args,int count) {(void)args;(void)count;}
@TRANSLATION@
@ENTRIES@
static HRESULT invoke(ScriptVariant **args,ScriptVariant **output,int count) {@INVOKE@}
struct contract {int revision,model_defense,model_offense;};
static const struct contract contracts[]={@CONTRACTS@};
static float *field(s_defense *value,int index) {
 switch(index) {case 0:return &value->factor;case 1:return &value->pain;
 case 2:return &value->knockdown;case 3:return &value->blockpower;
 case 4:return &value->blockthreshold;case 5:return &value->blockratio;
 case 6:return &value->blocktype;default:abort();}
}
static void reset(void) {
 s_model model={shared_defense,shared_offense,separate[0],separate[1],separate[2],
  separate[3],separate[4],separate[5],separate[6]};
 for(int actor=0;actor<2;++actor)
  actors[actor]=(entity){model,private_defense[actor],private_offense[actor]};
 for(int index=0;index<MAX_ATKS;++index) {
  shared_offense[index]=4000+index;
  for(int f=0;f<7;++f) {
   *field(&shared_defense[index],f)=separate[f][index]=(float)(1000+10*index+f);
   for(int actor=0;actor<2;++actor)
    *field(&private_defense[actor][index],f)=(float)(2000+1000*actor+10*index+f);
  }
  for(int actor=0;actor<2;++actor) private_offense[actor][index]=(float)(5000+1000*actor+index);
 }
}
static void run(int actor,int property,ScriptVariant index,ScriptVariant selector,
                int count,int status,VARTYPE kind,DOUBLE expected) {
 ScriptVariant values[4]={{.vt=VT_PTR,.ptrVal=&actors[actor]},
  {.vt=VT_INTEGER,.lVal=property},index,selector},*args[4];
 for(int i=0;i<4;++i) args[i]=&values[i];
 ScriptVariant result={.vt=VT_INTEGER,.lVal=999},*output=&result;
 assert(invoke(args,&output,count)==status);assert(output==&result);
 assert(result.vt==kind);
 if(kind==VT_DECIMAL) assert(result.dblVal==expected);
}
static void check(const struct contract *c) {
 obor_profile_build=c->revision;reset();
 for(int actor=0;actor<2;++actor) {
  for(int index=0;index<MAX_ATKS;++index) {
   for(int decimal=0;decimal<2;++decimal) {
    ScriptVariant attack={.vt=VT_INTEGER,.lVal=index};
    if(decimal) attack=(ScriptVariant){.vt=VT_DECIMAL,.dblVal=index+0.75};
    DOUBLE base=c->model_defense?1000:2000+1000*actor;
    run(actor,_ep_defense,attack,(ScriptVariant){0},3,S_OK,VT_DECIMAL,base+10*index);
    for(int f=0;f<7;++f) {
     run(actor,_ep_defense,attack,(ScriptVariant){.vt=VT_INTEGER,.lVal=f},4,
         S_OK,VT_DECIMAL,base+10*index+f);
     run(actor,_ep_defense,attack,(ScriptVariant){.vt=VT_DECIMAL,.dblVal=f+0.75},4,
         S_OK,VT_DECIMAL,base+10*index+f);
    }
    run(actor,_ep_defense,attack,(ScriptVariant){.vt=VT_STR,.strVal=0},4,E_FAIL,VT_EMPTY,0);
    run(actor,_ep_defense,attack,(ScriptVariant){.vt=VT_INTEGER,.lVal=99},4,E_FAIL,VT_DECIMAL,0);
    run(actor,_ep_offense,attack,(ScriptVariant){0},3,S_OK,VT_DECIMAL,
        (c->model_offense?4000:5000+1000*actor)+index);
   }
  }
  run(actor,_ep_defense,(ScriptVariant){.vt=VT_STR,.strVal=0},(ScriptVariant){0},3,E_FAIL,VT_EMPTY,0);
  run(actor,_ep_offense,(ScriptVariant){.vt=VT_STR,.strVal=0},(ScriptVariant){0},3,S_OK,VT_DECIMAL,
      c->model_offense?4000:5000+1000*actor);
  run(actor,_ep_offense,(ScriptVariant){0},(ScriptVariant){0},2,S_OK,VT_DECIMAL,
      c->model_offense?4000:5000+1000*actor);
#if @GENERATED@
  run(actor,_ep_defense,(ScriptVariant){0},(ScriptVariant){0},2,S_OK,VT_EMPTY,0);
  int invalid[]={-1,MAX_ATKS,INT32_MAX,INT32_MIN};
  for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);++i) {
   for(int property=_ep_defense;property<=_ep_offense;++property)
    run(actor,property,(ScriptVariant){.vt=VT_INTEGER,.lVal=invalid[i]},
        (ScriptVariant){.vt=VT_INTEGER,.lVal=0},4,S_OK,VT_EMPTY,0);
  }
  s_defense **defense=c->model_defense?&actors[actor].modeldata.defense:&actors[actor].defense;
  s_defense *saved=*defense;*defense=NULL;
  run(actor,_ep_defense,(ScriptVariant){.vt=VT_INTEGER,.lVal=0},
      (ScriptVariant){.vt=VT_INTEGER,.lVal=0},4,S_OK,VT_EMPTY,0);*defense=saved;
  float **offense=c->model_offense?&actors[actor].modeldata.offense_factors:&actors[actor].offense_factors;
  float *saved_offense=*offense;*offense=NULL;
  run(actor,_ep_offense,(ScriptVariant){.vt=VT_INTEGER,.lVal=0},(ScriptVariant){0},3,S_OK,VT_EMPTY,0);
  *offense=saved_offense;
#endif
 }
}
int main(int argc,char **argv) {
 assert(argc==2);int revision=atoi(argv[1]),matched=0;
 for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i)
  if(contracts[i].revision==revision) {check(&contracts[i]);++matched;}
 assert(matched==1);return 0;
}
'''
    if original:
        program = program[:program.index('int main(int argc,char **argv)')] + (
            'int main(void) {for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i)'
            'check(&contracts[i]);puts(' + json.dumps(json.dumps({
                'status': 'PASS', 'sources': len(rows), 'properties': 2})) + ');return 0;}\n')
    insertions = {'CONVERSIONS': '\n'.join(common[name] for name in
        ('ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue')),
        'TRANSLATION': components.get('translation', ''), 'ENTRIES': components['entries'],
        'INVOKE': components['invoke'], 'CONTRACTS': contracts_c, 'GENERATED': str(int(not original))}
    return re.sub(r'@(' + '|'.join(insertions) + r')@', lambda m: insertions[m[1]], program)


class EntityFactorReadTests(unittest.TestCase):
    def test_registry_contains_each_registered_native_chain_profile(self):
        revisions = [row['revision'] for row in CONTRACTS['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        for profile in pin['profiles']:
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in CONTRACTS['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIn(row['defense_target'], ('model', 'entity'))
            self.assertIn(row['offense_target'], ('model', 'entity'))
            for digest in row['getter_hashes'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')

    def test_own_source_getter_targets_conversions_and_callback_per_profile(self):
        with tempfile.TemporaryDirectory(prefix='anybor-factor-read-') as temporary:
            work=Path(temporary);source=work/'probe.c';executable=work/'probe'
            source.write_text(reader_program())
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-unused-variable','-Wno-unused-function','-g','-fsanitize=address,undefined',
                str(source),'-o',str(executable)],check=True,timeout=60)
            for row in CONTRACTS['sources']:
                with self.subTest(profile=row['revision']):
                    subprocess.run([str(executable),str(row['revision'])],check=True,
                        timeout=20,env=sanitizer_environment())
            print(json.dumps({'executed_sources':[row['revision'] for row in CONTRACTS['sources']],
                'scope':'Defense/offense reads, conversion and actual callback; reduced layouts and numeric mapping'}))


if __name__ == '__main__':
    unittest.main()
