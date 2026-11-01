"""Check exact knockdowncount case bodies against own-source contracts.

The reduced wrapper supplies valid entity/variant arguments and the native
success/error exits. Name mapping, numeric namespaces and the full callback
prologue are covered separately. This is not an interpreter or gameplay test.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
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
CONTRACTS = load_contract_fixture(Path(__file__).parent /
    'fixtures/profile-knockdowncount-contracts.json')


def program(source, contracts):
    _, get = switch_cases(source, 'openbor_getentityproperty', 'propind')
    _, change = switch_cases(source, 'openbor_changeentityproperty', 'propind')
    rows = []
    for row in contracts['sources']:
        rows.append('{%d,%s,%d,%d,{%s}},' % (
            row['revision'], repr(row['get_current']), row['get_time_status'],
            row['setter_status'], ','.join(str(v) for v in row['setter_effects'])))
    return r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef long LONG;
typedef double DOUBLE;
typedef int HRESULT;
typedef struct { union { LONG lVal; DOUBLE dblVal; }; int vt; } ScriptVariant;
enum { VT_EMPTY, VT_INTEGER, VT_DECIMAL, VT_STR };
enum { _gep_knockdowncount_current, _gep_knockdowncount_max,
       _gep_knockdowncount_time };
enum { _cep_knockdowncount_current, _cep_knockdowncount_max,
       _cep_knockdowncount_time };
#define S_OK 0
#define E_FAIL (-1)
#define SUCCEEDED(x) ((x)>=0)
typedef struct { float knockdowncount; } model;
typedef struct { model modeldata; float knockdowncount; int knockdowntime; } entity;
static unsigned obor_profile_build;
static void ScriptVariant_Clear(ScriptVariant *v) { memset(v,0,sizeof(*v)); }
static void ScriptVariant_ChangeType(ScriptVariant *v,int t) {
    ScriptVariant_Clear(v);v->vt=t;
}
static int ScriptVariant_IntegerValue(ScriptVariant *v,LONG *out) {
    if(v->vt==VT_INTEGER) { *out=v->lVal;return S_OK; }
    if(v->vt==VT_DECIMAL) { *out=(LONG)v->dblVal;return S_OK; }
    return E_FAIL;
}
static int ScriptVariant_DecimalValue(ScriptVariant *v,DOUBLE *out) {
    if(v->vt==VT_INTEGER) { *out=v->lVal;return S_OK; }
    if(v->vt==VT_DECIMAL) { *out=v->dblVal;return S_OK; }
    return E_FAIL;
}
static int get(entity *ent,ScriptVariant **varlist,ScriptVariant **pretvar,int paramCount) {
    LONG ltemp;ScriptVariant *arg;
    switch(0) { case 0: GET_BODY }
    return S_OK;
}
static int change(entity *ent,ScriptVariant **varlist,ScriptVariant **pretvar,int paramCount) {
    LONG ltemp;DOUBLE dbltemp;
    switch(0) { case 0: CHANGE_BODY }
    return S_OK;
changeentityproperty_error:
    *pretvar=NULL;return E_FAIL;
}
static const struct {
    unsigned revision;double current;int time_status,set_status;
    double effects[9];
} cases[]={ CASE_ROWS };
int main(void) {
    for(unsigned c=0;c<sizeof(cases)/sizeof(*cases);++c) {
        obor_profile_build=cases[c].revision;
        entity subject={.modeldata={11.75f},.knockdowncount=6.25f,.knockdowntime=44};
        ScriptVariant args[4]={{.vt=VT_EMPTY},{.vt=VT_EMPTY},
                              {.vt=VT_INTEGER},{.vt=VT_DECIMAL,.dblVal=5.5}};
        ScriptVariant *v[]={args,args+1,args+2,args+3},result,*out;
        for(int field=0;field<3;++field) {
            args[2].lVal=field;out=&result;ScriptVariant_Clear(out);
            int status=get(&subject,v,&out,3);
            assert(status==(field==2?cases[c].time_status:S_OK));
            if(field<2) {
                assert(out==&result && result.vt==VT_DECIMAL);
                assert(result.dblVal==(field==0?cases[c].current:11.75));
            } else if(status==S_OK) {
                assert(out==&result && result.vt==VT_INTEGER && result.lVal==6);
            } else assert(out==&result && result.vt==VT_EMPTY);
        }
        out=&result;ScriptVariant_Clear(out);
        assert(get(&subject,v,&out,2)==S_OK);
        assert(result.vt==VT_DECIMAL && result.dblVal==cases[c].current);
        for(int field=0;field<3;++field) {
            subject=(entity){.modeldata={11.75f},.knockdowncount=6.25f,.knockdowntime=44};
            args[2].lVal=field;out=&result;ScriptVariant_ChangeType(out,VT_INTEGER);
            int status=change(&subject,v,&out,field==2?3:4);
            assert(status==cases[c].set_status);
            if(status==S_OK) assert(out==&result && result.vt==VT_INTEGER && result.lVal==1);
            else assert(out==NULL);
            assert(subject.knockdowncount==cases[c].effects[field*3]);
            assert(subject.modeldata.knockdowncount==cases[c].effects[field*3+1]);
            assert(subject.knockdowntime==cases[c].effects[field*3+2]);
        }
    }
    printf("%zu profile contracts passed\n",sizeof(cases)/sizeof(*cases));
    return 0;
}
'''.replace('GET_BODY', get['_gep_knockdowncount']['body']).replace(
        'CHANGE_BODY', change['_cep_knockdowncount']['body']).replace(
        'CASE_ROWS', '\n'.join(rows))


class HistoricalKnockdowncountTests(unittest.TestCase):
    def test_retained_profile_inventory_is_covered(self):
        with (SOURCE / 'src/pin.json').open() as stream:
            profiles = json.load(stream)['profiles']
        low = min(row['revision'] for row in CONTRACTS['sources'])
        high = max(row['revision'] for row in CONTRACTS['sources'])
        expected = {int(row.get('revision', row['build']))
                    for row in contract_profiles(CONTRACTS, profiles)
                    if row['engine']=='3400' and
                    low <= int(row.get('revision', row['build'])) <= high}
        self.assertTrue(expected)
        self.assertLessEqual(expected, {row['revision'] for row in CONTRACTS['sources']})

    def test_valid_getter_and_setter_results_for_each_retained_profile(self):
        source = (SOURCE / 'src/engines/3400/openborscript.c').read_text()
        with tempfile.TemporaryDirectory(prefix='knockdowncount-') as folder:
            path = Path(folder)
            probe, executable = path / 'probe.c', path / 'probe'
            probe.write_text(program(source, CONTRACTS))
            command = shlex.split(os.environ.get('CC', 'cc'))
            command += ['-std=gnu99', '-Wall', '-Wextra', '-Werror',
                        '-Wno-deprecated-declarations', '-Wno-implicit-fallthrough',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                        '-g', str(probe), '-o', str(executable)]
            compiled = subprocess.run(command, timeout=60, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout+compiled.stderr)
            result = subprocess.run([str(executable)], timeout=20,
                                    capture_output=True, text=True,
                                    env=sanitizer_environment())
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn(str(len(CONTRACTS['sources']))+' profile contracts passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
