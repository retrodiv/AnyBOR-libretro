"""Check historical combat-factor targets and partial mutations per profile.

The reduced fixture separates shared model buffers from entity-private buffers.
It covers payloads and branch results. The callback entry/exit is exercised
separately by test_historical_entity_returns. Property mapping, complete native
layout, spawning, combat execution and gameplay remain separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from test_historical_player import switch_cases

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
CONTRACTS = json.loads((Path(__file__).parent /
    'fixtures/profile-entity-factor-contracts.json').read_text())


def factor_cases(source):
    _, selected = switch_cases(source, 'openbor_changeentityproperty', 'propind')
    cases = []
    for name in ('defense','offense'):
        label = '_ep_' + name
        if label not in selected:
            raise AssertionError('Unique combat-factor case required')
        cases.append('case ' + label + ':' + selected[label]['body'])
    return '\n'.join(cases)


def factor_program(components=None, contracts=None):
    contracts = CONTRACTS['sources'] if contracts is None else contracts
    original_layout = components.get('original_layout',False) if components else False
    if components is None:
        components = {'cases': factor_cases((SOURCE /
            'src/engines/3741/openborscript.c').read_text())}
    rows = []
    for row in contracts:
        rows.append('{%d,%d,%d,%d,%d},' % (row['revision'],
            row['defense_setter_target']!='entity_struct_array',
            row['offense_setter_target']=='model_array',
            original_layout and row['defense_setter_target']=='model_separate_arrays',
            row['has_result']))
    program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef long LONG;
typedef double DOUBLE;
typedef struct { LONG lVal; DOUBLE dblVal; int vt; } ScriptVariant;
enum { VT_EMPTY, VT_INTEGER, VT_DECIMAL, _ep_defense=101, _ep_offense };
#define MAX_ATKS 16
#define SUCCEEDED(x) ((x)>=0)
typedef struct { float factor,pain,knockdown,blockpower,blockthreshold,blockratio,blocktype; } s_defense;
typedef struct {
    s_defense *defense;
    float *offense_factors;
    float *defense_factors,*defense_pain,*defense_knockdown,*defense_blockpower;
    float *defense_blockthreshold,*defense_blockratio,*defense_blocktype;
} s_model;
typedef struct { s_model modeldata; s_defense *defense; float *offense_factors; } entity;
static uint32_t obor_profile_build;
static int fixture_has_result;
static LONG last_result;
static entity actor,peer;
static s_defense shared_defense[MAX_ATKS],private_defense[2][MAX_ATKS];
static float shared_offense[MAX_ATKS],private_offense[2][MAX_ATKS];
static float separate_defense[7][MAX_ATKS];
static int ScriptVariant_IntegerValue(ScriptVariant *v,LONG *out) {
    if(v->vt!=VT_INTEGER) return -1;
    *out=v->lVal;return 0;
}
static int ScriptVariant_DecimalValue(ScriptVariant *v,DOUBLE *out) {
    if(v->vt==VT_INTEGER) { *out=v->lVal;return 0; }
    if(v->vt==VT_DECIMAL) { *out=v->dblVal;return 0; }
    return -1;
}
static float *field(s_defense *d,int f) {
    switch(f) {
    case 0:return &d->factor;case 1:return &d->pain;case 2:return &d->knockdown;
    case 3:return &d->blockpower;case 4:return &d->blockthreshold;
    case 5:return &d->blockratio;case 6:return &d->blocktype;
    default:abort();
    }
}
static void reset(void) {
    actor=(entity){0};peer=(entity){0};
    s_model model={shared_defense,shared_offense,separate_defense[0],separate_defense[1],
        separate_defense[2],separate_defense[3],separate_defense[4],
        separate_defense[5],separate_defense[6]};
    actor.modeldata=peer.modeldata=model;
    actor.defense=private_defense[0];peer.defense=private_defense[1];
    actor.offense_factors=private_offense[0];peer.offense_factors=private_offense[1];
    for(int i=0;i<MAX_ATKS;++i) {
        shared_offense[i]=400;private_offense[0][i]=500;private_offense[1][i]=600;
        for(int f=0;f<7;++f) {
            *field(&shared_defense[i],f)=separate_defense[f][i]=100+f;
            *field(&private_defense[0][i],f)=200+f;
            *field(&private_defense[1][i],f)=300+f;
        }
    }
}
static void write_factors(int property,ScriptVariant **varlist,int paramCount) {
    entity *ent=&actor;
    LONG ltemp=0,ltemp2=0;DOUBLE dbltemp=0;
    ScriptVariant result={0},*output=fixture_has_result?&result:NULL,**pretvar=&output;
    (void)pretvar;(void)ltemp2;
    switch(property) { CASES }
    last_result=output?output->lVal:-1234;
}
struct contract { int revision,model_defense,model_offense,separate,has_result; };
static const struct contract contracts[]={ CONTRACTS };
static void check(const struct contract *c) {
    obor_profile_build=c->revision;
    fixture_has_result=c->has_result;
    for(int index=-1;index<=MAX_ATKS;++index) {
        for(int count=3;count<=10;++count) for(int bad=-1;bad<7;++bad) {
            reset();ScriptVariant args[10]={{0}};ScriptVariant *varlist[10];
            for(int i=0;i<10;++i) varlist[i]=&args[i];
            args[2]=(ScriptVariant){index,0,VT_INTEGER};
            for(int f=0;f<7;++f) args[3+f]=(ScriptVariant){0,10+f,f==bad?VT_EMPTY:VT_DECIMAL};
            write_factors(_ep_defense,varlist,count);
            int success=count>=4&&index>=0&&index<MAX_ATKS&&
                (bad<0||bad>=count-3);
            assert(last_result==(c->has_result?success:-1234));
            int assigned=count-3;
            if(bad>=0 && bad<assigned) assigned=bad;
            if(index<0 || index>=MAX_ATKS) assigned=0;
            for(int i=0;i<MAX_ATKS;++i) for(int f=0;f<7;++f) {
                int changed=i==index && f<assigned;
                float model_value=c->separate?separate_defense[f][i]:*field(&shared_defense[i],f);
                assert(model_value==(changed&&c->model_defense?10+f:100+f));
                assert(*field(&private_defense[0][i],f)==(changed&&!c->model_defense?10+f:200+f));
                assert(*field(&private_defense[1][i],f)==300+f);
                // The other entity sees the shared model write through its
                // copied model pointer, while its private defense stays intact.
                assert(c->separate || *field(&peer.modeldata.defense[i],f)==model_value);
            }
        }
        for(int count=3;count<=4;++count) for(int bad=0;bad<2;++bad) {
            reset();ScriptVariant a={index,0,VT_INTEGER},value={0,17,bad?VT_EMPTY:VT_DECIMAL};
            ScriptVariant *varlist[]={NULL,NULL,&a,&value};
            write_factors(_ep_offense,varlist,count);
            int changed=count==4&&!bad&&index>=0&&index<MAX_ATKS;
            assert(last_result==(c->has_result?changed:-1234));
            for(int i=0;i<MAX_ATKS;++i) {
                assert(shared_offense[i]==(changed&&i==index&&c->model_offense?17:400));
                assert(private_offense[0][i]==(changed&&i==index&&!c->model_offense?17:500));
                assert(private_offense[1][i]==600);
                assert(peer.modeldata.offense_factors[i]==shared_offense[i]);
            }
        }
    }
}
int main(int argc,char **argv) {
    assert(argc==2);int revision=atoi(argv[1]),matched=0;
    for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i) {
        if(contracts[i].revision==revision) { check(&contracts[i]);++matched; }
    }
    assert(matched==1);return 0;
}
'''
    return program.replace('CASES',components['cases']).replace('CONTRACTS','\n'.join(rows))


class EntityFactorTests(unittest.TestCase):
    def test_registry_covers_native_profiles_with_own_source_records(self):
        revisions=[row['revision'] for row in CONTRACTS['sources']]
        self.assertEqual(len(revisions),len(set(revisions)))
        pin=json.loads((SOURCE/'src/pin.json').read_text())
        for profile in pin['profiles']:
            if profile['engine']=='3741':
                self.assertIn(int(profile.get('revision',profile['build'])),revisions)
        for row in CONTRACTS['sources']:
            self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
            for key in ('setter_sha256','header_sha256','spawn_sha256'):
                self.assertRegex(row[key],r'^[0-9a-f]{64}$')
            self.assertIs(type(row['has_result']),bool)
            self.assertIn(row['defense_setter_target'],
                ('model_separate_arrays','model_struct_array','entity_struct_array'))
            self.assertIn(row['offense_setter_target'],('model_array','entity_array'))

    def test_payload_targets_aliases_partial_updates_and_rejection_per_profile(self):
        with tempfile.TemporaryDirectory(prefix='anybor-entity-factors-') as temporary:
            work=Path(temporary);source=work/'probe.c';exe=work/'probe'
            source.write_text(factor_program())
            subprocess.run(shlex.split(os.environ.get('HOST_CC','cc'))+[
                '-std=c11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-g','-fsanitize=address,undefined',str(source),'-o',str(exe)],check=True,timeout=60)
            executed=[]
            for row in CONTRACTS['sources']:
                with self.subTest(profile=row['revision']):
                    subprocess.run([str(exe),str(row['revision'])],check=True,
                        timeout=15,env=sanitizer_environment())
                    executed.append(row['revision'])
            self.assertEqual(executed,[row['revision'] for row in CONTRACTS['sources']])
            print(json.dumps({'executed_profiles':executed,
                'scope':'factor payloads, aliases and branch results; callback entry tested separately'}))


if __name__=='__main__':
    unittest.main()
