"""Check statistics writes and callback results against each original source.

Callbacks and conversions are extracted source; fields and numeric mapping are
reduced fixtures. Invalid indices exercise the bounded core only. This does
not establish full entity initialization or script/gameplay acceptance.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from test_historical_entity_returns import scalar_entry
from test_historical_player import function

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
CONTRACT_PATH = Path(__file__).parent / 'fixtures/profile-stats-write-contracts.json'
CONVERSIONS = ('ScriptVariant_ChangeType', 'ScriptVariant_Clear',
               'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')


def writer_program(components=None, common=None, contracts=None, *, original=False):
    rows = load_contract_fixture(CONTRACT_PATH)['sources'] if contracts is None else contracts
    if components is None:
        source = (SOURCE / 'src/engines/3741/openborscript.c').read_text()
        entry, actions = scalar_entry(source, ('_ep_stats',))
        components = {'entry': entry, 'actions': sorted(actions),
            'translation': 'static int obor_entity_set_property_native(int p) {return p;}'}
        variant = (SOURCE / 'src/engines/3741/source/scriptlib/ScriptVariant.c').read_text()
        common = {name: function(variant, name) for name in CONVERSIONS}
    if common is None:
        raise ValueError('Explicit source conversions required')
    program = r'''
#include <assert.h>
#include <float.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int32_t LONG;
typedef int HRESULT;
typedef double DOUBLE;
typedef enum {VT_EMPTY=0,VT_INTEGER=1,VT_DECIMAL=2,VT_PTR=5,VT_STR=6} VARTYPE;
typedef struct {union {LONG lVal;DOUBLE dblVal;void *ptrVal;int strVal;};VARTYPE vt;} ScriptVariant;
typedef struct {float stats[20];} s_model;
typedef struct {s_model modeldata;float stats[20];} entity;
enum {_ep_stats};
enum {TYPE_ENEMY=1,TYPE_NPC,TYPE_OBSTACLE,TYPE_PLAYER,TYPE_SHOT};
#define S_OK 0
#define E_FAIL (-1)
#define SUCCEEDED(x) ((x)>=0)
#define FAILED(x) ((x)<0)
static uint32_t obor_profile_build;
static int quiet_printf(const char *format,...) {(void)format;return 0;}
#define printf quiet_printf
static int StrCache_Pop(void) {abort();}
static void StrCache_Collect(int index) {(void)index;abort();}
@CONVERSIONS@
static void mapstrings_changeentityproperty(ScriptVariant **args,int count) {(void)args;(void)count;}
@ACTIONS@
@TRANSLATION@
@ENTRY@
struct contract {int revision,has_result,stats_count;};
static const struct contract contracts[]={@CONTRACTS@};
static ScriptVariant integer(LONG n) {return (ScriptVariant){.vt=VT_INTEGER,.lVal=n};}
static ScriptVariant decimal(DOUBLE n) {return (ScriptVariant){.vt=VT_DECIMAL,.dblVal=n};}
static void run(const struct contract *c,ScriptVariant selector,ScriptVariant index,
                ScriptVariant value,int count,int changed,int expected_index) {
 entity subject,expected;
 for(int i=0;i<20;++i) {
  subject.modeldata.stats[i]=(float)(100+i+0.25);
  subject.stats[i]=(float)(-100-i-0.5);
 }
 expected=subject;
 if(changed) {
  float replacement=(float)(value.vt==VT_INTEGER?(DOUBLE)value.lVal:value.dblVal);
  if(selector.lVal==1) expected.stats[expected_index]=replacement;
  else expected.modeldata.stats[expected_index]=replacement;
 }
 ScriptVariant values[5]={{.vt=VT_PTR,.ptrVal=&subject},integer(_ep_stats),
                         selector,index,value},*args[5];
 for(int i=0;i<5;++i) args[i]=&values[i];
 ScriptVariant result=integer(999),*output=&result;
 assert(openbor_changeentityproperty(args,&output,count)==S_OK);
 assert((output!=NULL)==c->has_result);
 if(output) assert(output==&result && result.vt==VT_INTEGER && result.lVal==0);
 assert(!memcmp(&subject,&expected,sizeof(subject)));
}
static void check(const struct contract *c) {
 obor_profile_build=c->revision;
 LONG selectors[]={-1,0,1,2,INT32_MIN,INT32_MAX};
 ScriptVariant values[]={integer(17),decimal(-12.5),decimal(0.0),decimal(-0.0),
                         decimal(FLT_MAX),decimal(-FLT_MAX)};
 for(unsigned s=0;s<sizeof(selectors)/sizeof(*selectors);++s) {
  ScriptVariant selector=integer(selectors[s]);
  for(int index=0;index<c->stats_count;++index) {
   for(unsigned v=0;v<sizeof(values)/sizeof(*values);++v) {
    run(c,selector,integer(index),values[v],5,1,index);
    run(c,selector,decimal(index+0.75),values[v],5,1,index);
   }
  }
  run(c,selector,decimal(-0.75),decimal(1.5),5,1,0);
  run(c,selector,integer(0),(ScriptVariant){.vt=VT_EMPTY},5,0,0);
  run(c,selector,integer(0),(ScriptVariant){.vt=VT_STR,.strVal=0},5,0,0);
  run(c,selector,(ScriptVariant){.vt=VT_EMPTY},integer(17),4,0,0);
  run(c,selector,(ScriptVariant){.vt=VT_STR,.strVal=0},integer(17),4,0,0);
  run(c,selector,integer(0),integer(17),3,0,0);
 }
 /* The original selector is read directly; retain its initialized value. */
 ScriptVariant other_selectors[]={{.vt=VT_EMPTY,.ptrVal=NULL},
  {.vt=VT_PTR,.ptrVal=NULL},{.vt=VT_STR,.strVal=0},{.vt=VT_STR,.strVal=1},
  {.vt=VT_DECIMAL,.dblVal=0.0}};
 for(unsigned s=0;s<sizeof(other_selectors)/sizeof(*other_selectors);++s)
  run(c,other_selectors[s],integer(19),decimal(2.25),5,1,19);
#if @GENERATED@
 LONG invalid[]={-1,20,INT32_MIN,INT32_MAX};
 DOUBLE invalid_decimal[]={-1.0,20.0,1e100,-1e100,NAN,INFINITY,-INFINITY};
 for(int selector=0;selector<2;++selector) {
  for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);++i)
   run(c,integer(selector),integer(invalid[i]),integer(17),5,0,0);
  for(unsigned i=0;i<sizeof(invalid_decimal)/sizeof(*invalid_decimal);++i)
   run(c,integer(selector),decimal(invalid_decimal[i]),integer(17),5,0,0);
  run(c,integer(selector),integer(0),integer(17),4,0,0);
 }
#endif
}
int main(int argc,char **argv) {
 assert(argc==2);int revision=atoi(argv[1]),matched=0;
 for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i)
  if(contracts[i].revision==revision) {check(&contracts[i]);++matched;}
 assert(matched==1);return 0;
}
'''
    if original:
        observation = {'status': 'PASS', 'sources': len(rows), 'properties': 1}
        program = program[:program.index('int main(int argc,char **argv)')] + (
            'int main(void) {for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i)'
            'check(&contracts[i]);puts(' + json.dumps(json.dumps(observation)) + ');return 0;}\n')
    insertions = {'CONVERSIONS': '\n'.join(common[name] for name in CONVERSIONS),
        'ACTIONS': '\n'.join('static void ' + name + '(void) {abort();}'
            for name in components['actions']),
        'TRANSLATION': components.get('translation', ''), 'ENTRY': components['entry'],
        'GENERATED': str(int(not original)),
        'CONTRACTS': ','.join('{%d,%d,%d}' % (row['revision'], row['has_result'],
            row['stats_count']) for row in rows)}
    return re.sub(r'@(' + '|'.join(insertions) + r')@', lambda m: insertions[m[1]], program)


class StatsWriteTests(unittest.TestCase):
    def test_registry_covers_registered_profiles_and_own_sources(self):
        rows = load_contract_fixture(CONTRACT_PATH)['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        for profile in contract_profiles(Path(__file__).parent / 'fixtures/profile-stats-write-contracts.json', pin['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['stats_count'], 20)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['setter_sha256'], r'^[0-9a-f]{64}$')
            self.assertIn(row['has_result'], (True, False))

    def test_original_mutations_returns_and_bounded_indices_per_profile(self):
        rows = load_contract_fixture(CONTRACT_PATH)['sources']
        with tempfile.TemporaryDirectory(prefix='anybor-stats-write-') as temporary:
            work = Path(temporary); source = work / 'probe.c'; executable = work / 'probe'
            source.write_text(writer_program())
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-unused-variable', '-Wno-unused-function', '-g',
                '-fsanitize=address,undefined,float-cast-overflow',
                str(source), '-o', str(executable)], check=True, timeout=60)
            for row in rows:
                with self.subTest(profile=row['revision']):
                    subprocess.run([str(executable), str(row['revision'])], check=True,
                        timeout=20, env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
