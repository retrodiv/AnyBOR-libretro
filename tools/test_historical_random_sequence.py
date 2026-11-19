"""Compare historical random results and state with original-source observations.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-random-sequence-contracts.json'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    rows, cases, contracts = data['sources'], data['cases'], data['contracts']
    revisions = [row['revision'] for row in rows]
    if (data['engine'] != '4432' or len(set(revisions)) != len(rows) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions) or
            not 1 <= len(cases) <= 32 or set(contracts) != {'magnitude', 'raw'}):
        raise ValueError('Explicit source coverage, boundary controls and observations required')
    for row in rows:
        if (row['engine'] != data['engine'] or type(row['revision']) is not int or
                row['revision'] <= 0 or row['contract'] not in contracts or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not re.fullmatch('[0-9a-f]{64}', row['source_sha256']['source/randlib/rand32.c'])):
            raise ValueError('Bound original source and observed sequence required')
    for index, case in enumerate(cases):
        if (not re.fullmatch('0x[0-9a-f]{16}', case['seed']) or
                not 1 <= len(case['states']) <= 128 or
                any(not re.fullmatch('0x[0-9a-f]{16}', state) for state in case['states'])):
            raise ValueError('Explicit unsigned seed and state observations required')
        for values in contracts.values():
            if (len(values) != len(cases) or len(values[index]) != len(case['states']) or
                    any(type(v) is not int or not 0 <= v <= 0xffffffff for v in values[index])):
                raise ValueError('One observed unsigned result per state required')
    return data


def program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'source/randlib/rand32.c').read_text()
    initial = re.findall(r'(?m)^u64 seed[ \t]*=[^;\n]+;', source)
    if len(initial) != 1:
        raise ValueError('One native generator seed initializer required')
    names = ('rotl64', 'rotr64', 'rand32', 'srand32', 'getseed')
    keys = sorted(data['contracts'])
    cases, results, states = [], [], []
    for index, case in enumerate(data['cases']):
        cases.append('{UINT64_C(%s),%du}' % (case['seed'], len(case['states'])))
        states.append('{' + ','.join('UINT64_C(%s)' % v for v in case['states']) + '}')
    for key in keys:
        results.append('{' + ','.join('{' + ','.join(str(v) + 'u' for v in row) + '}'
                                     for row in data['contracts'][key]) + '}')
    return r'''
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
typedef uint64_t u64;
static @INITIAL@
static uint32_t obor_profile_build;
@FUNCTIONS@
static const struct {u64 seed; unsigned draws;} cases[]={@CASES@};
static const u64 states[][128]={@STATES@};
static const uint32_t expected[2][sizeof(cases)/sizeof(*cases)][128]={@RESULTS@};
static const struct {uint32_t revision;unsigned contract;} profiles[]={@PROFILES@};
int main(void) {
    unsigned total=0;
    assert(CHAR_BIT==8 && sizeof(unsigned int)==4 && sizeof(u64)==8);
    assert(getseed()==UINT64_C(1234567890));
    for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
        obor_profile_build=profiles[p].revision;
        for(unsigned c=0;c<sizeof(cases)/sizeof(*cases);++c) {
            srand32(cases[c].seed);
            assert(getseed()==cases[c].seed);
            for(unsigned i=0;i<cases[c].draws;++i) {
                assert(rand32()==expected[profiles[p].contract][c][i]);
                assert(getseed()==states[c][i]);
                ++total;
            }
        }
    }
    printf("{\"status\":\"PASS\",\"cases\":%u}\n",total);
    return 0;
}
'''.replace('@INITIAL@', initial[0]).replace(
        '@FUNCTIONS@', '\n'.join(function(source, name) for name in names)).replace(
        '@CASES@', ','.join(cases)).replace('@STATES@', ','.join(states)).replace(
        '@RESULTS@', ','.join(results)).replace('@PROFILES@', ','.join(
            '{%du,%du}' % (r['revision'], keys.index(r['contract'])) for r in data['sources']))


class RandomSequenceContracts(unittest.TestCase):
    def test_original_results_seed_reset_and_state_by_profile(self):
        data = fixture_data()
        expected = sum(len(c['states']) for c in data['cases']) * len(data['sources'])
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(status='PASS', cases=expected)])


if __name__ == '__main__':
    unittest.main()
