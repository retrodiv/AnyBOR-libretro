"""Exercise the historical unknown-constant result at the actual API entry.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles, contract_revisions
import json
import os
from pathlib import Path
import re
from test_historical_player import function
import subprocess
import tempfile
import unittest


def constants_fixture(members):
    result = dict(members)
    result['data/script.txt'] = b'alwaysupdate 1\n'
    result['data/scripts/updated.c'] = b'''void main() {
    if(getglobalvar("constant_checked") == 1) return;
    setglobalvar("constant_checked", 1);
    if(openborconstant("ATK_NORMAL") != 0) {
        log("CONSTANT_CONTRACT_BAD_KNOWN\\n"); return;
    }
    log("CONSTANT_CONTRACT_BEFORE_UNKNOWN\\n");
    void result = openborconstant("SYNTHETIC_UNKNOWN_CONSTANT");
    if(result == NULL()) log("CONSTANT_CONTRACT_EMPTY_CONTINUATION\\n");
    else log("CONSTANT_CONTRACT_BAD_RESULT\\n");
}
'''
    return result


def check_constants_continuation(log, profile, restarts=0):
    legacy = int(profile) < 3826
    expected = ['CONSTANT_CONTRACT_BEFORE_UNKNOWN']
    if legacy:
        expected.append('CONSTANT_CONTRACT_EMPTY_CONTINUATION')
    markers = re.findall(r'(?m)^(?:\[(?:OpenBOR(?::[0-9]+)?|game)\][ \t]*)?'
                         r'(CONSTANT_CONTRACT_[A-Z_]+)[ \t]*\r?$', log)
    exception = "There's an exception while executing script" in log
    if markers != expected * (1 + restarts) or exception == legacy:
        raise RuntimeError('Historical unknown-constant contract differs: ' + log)


class UnknownConstantsTests(unittest.TestCase):
    def test_mapper_names_values_and_mapping_phase_per_profile(self):
        from historical_constant_mapper import render_constant_mapper
        from test_historical_behavior import native
        from native_sanitizers import sanitizer_environment
        from unittest.mock import patch
        root = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
        fixture = load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-constant-mapper-contracts.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(contract_revisions(fixture, {3761, 3769, 3773, *fixture['boundary_controls']}) <= revisions)
        for profile in contract_profiles(fixture, json.loads((root / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['suffix_in_mapper'], row['revision'] >= 3826)
            self.assertEqual(row['unknown_empty_success'], row['revision'] < 3826)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in [row['header_sha256'], *row['source_sha256'].values()]:
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        with patch.dict(os.environ, sanitizer_environment()):
            native(render_constant_mapper(root / 'src/engines/3842', fixture),
                   extra_flags=('-fsanitize=pointer-overflow', '-fno-sanitize-recover=all'))

    def test_compiled_continuation_requires_executed_markers(self):
        legacy = "[game] CONSTANT_CONTRACT_BEFORE_UNKNOWN\n[game] CONSTANT_CONTRACT_EMPTY_CONTINUATION\n"
        modern = ("[OpenBOR] CONSTANT_CONTRACT_BEFORE_UNKNOWN\n"
                  "There's an exception while executing script updated\n"
                  'log("CONSTANT_CONTRACT_EMPTY_CONTINUATION\\n");')
        check_constants_continuation(legacy, '3824')
        check_constants_continuation(modern, '3829')
        check_constants_continuation(legacy + legacy, '3780', restarts=1)
        for log, profile in ((legacy, '3829'), (modern, '3780'),
                             (legacy + legacy, '3780'),
                             ('log("CONSTANT_CONTRACT_BEFORE_UNKNOWN");', '3780')):
            with self.subTest(profile=profile), self.assertRaises(RuntimeError):
                check_constants_continuation(log, profile)

    def test_profile_boundary_empty_result_known_values_and_bad_arguments(self):
        root = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
        source = (root / 'src/engines/3842/openborscript.c').read_text()
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
typedef long LONG;
#define strnicmp strncasecmp
#define OBOR_ATTACK_BASE 16
#define OBOR_ATTACK_SPECIAL 6
static int *animdowns,*animups,*animbackwalks,*animwalks,*animidles;
static int *animfalls,*animrises,*animriseattacks,*animpains,*animdies;
static int *animattacks,*animfollows,*animspecials;
int max_downs,max_ups,max_backwalks,max_walks,max_idles,max_attack_types;
int max_attacks,max_follows,max_freespecials;
enum { VT_EMPTY, VT_INTEGER, VT_DECIMAL, VT_PTR, VT_STR };
typedef struct { int vt; long lVal; const char *text; } ScriptVariant;
#define strVal text
static const char *StrCache_Get(const char *text) { return text; }
typedef int HRESULT;
#define S_OK 0
#define E_FAIL (-1)
static uint32_t obor_profile_build;
static unsigned cleared;
static void ScriptVariant_Clear(ScriptVariant *value) {
    ++cleared; memset(value,0,sizeof(*value));
}
static void ScriptVariant_ChangeType(ScriptVariant *value,int type) {
    memset(value,0,sizeof(*value));value->vt=type;
}
static void ScriptVariant_Copy(ScriptVariant *to,const ScriptVariant *from) { *to=*from; }
static void ScriptVariant_ToString(const ScriptVariant *value,char *text) {
    snprintf(text,128,"%.100s",value->vt==VT_STR?value->text:"non-string");
}
/* Keep mapping separate from the result/error contract under test. The
 * compiled script fixture additionally exercises the complete real mapper. */
static void mapstrings_transconst(ScriptVariant **args,int count) {
    assert(count>=1);
    if(args[0]->vt==VT_STR && !strcmp(args[0]->text,"ATK_NORMAL")) {
        args[0]->vt=VT_INTEGER;args[0]->lVal=0;
    }
}
METHOD
int main(void) {
    (void)&ScriptVariant_Clear;
    (void)obor_profile_build;
    const unsigned profiles[]={3780,3783,3789,3793,3797,3805,3814,3818,
        3822,3824,3825,3826,3829,3831,3837,3839,3842};
    const char *unknown[]={"UNKNOWN_SYNTHETIC_CONSTANT","","ANI_UNKNOWN17"};
    for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
        obor_profile_build=profiles[p];
        for(unsigned n=0;n<sizeof(unknown)/sizeof(*unknown);++n) {
            ScriptVariant arg={VT_STR,19,unknown[n]},before=arg;
            ScriptVariant result={VT_STR,71,"old-result"},*out=&result,*args[]={&arg};
            unsigned previous=cleared;
            int status=openbor_transconst(args,&out,1);
            assert(!memcmp(&arg,&before,sizeof(arg)));
            if(profiles[p]<3826) {
                assert(status==S_OK && out==&result && result.vt==VT_EMPTY);
                assert(!result.lVal && !result.text && cleared==previous+1);
            } else assert(status==E_FAIL && out==NULL && cleared==previous);
        }
        ScriptVariant arg={VT_STR,0,"ATK_NORMAL"},result={VT_EMPTY,0,NULL};
        ScriptVariant *out=&result,*args[]={&arg};
        assert(openbor_transconst(args,&out,1)==S_OK && out==&result);
        assert(result.vt==VT_INTEGER && result.lVal==0 && arg.vt==VT_INTEGER);
        arg=(ScriptVariant){VT_INTEGER,-17,NULL};out=&result;
        assert(openbor_transconst(args,&out,1)==S_OK && out==&result && result.lVal==-17);
        const int bad_types[]={VT_EMPTY,VT_DECIMAL,VT_PTR};
        for(unsigned n=0;n<sizeof(bad_types)/sizeof(*bad_types);++n) {
            arg=(ScriptVariant){bad_types[n],0,NULL};out=&result;
            assert(openbor_transconst(args,&out,1)==E_FAIL && out==NULL);
        }
        out=&result;
        assert(openbor_transconst(NULL,&out,0)==E_FAIL && out==NULL);
    }
    return 0;
}
'''.replace('METHOD', function(source, 'openbor_transconst'))
        with tempfile.TemporaryDirectory(prefix='anybor-unknown-constant-') as temp:
            work = Path(temp)
            (work / 'probe.c').write_text(program)
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                            '-g', '-fsanitize=address,undefined', str(work / 'probe.c'),
                            '-o', str(work / 'probe')], check=True, timeout=30)
            subprocess.run([str(work / 'probe')], check=True, timeout=10,
                           stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    unittest.main()
