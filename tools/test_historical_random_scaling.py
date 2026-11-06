"""Check source-defined floating random scaling and sample consumption.

The complete native randf executes with an observed unsigned random word.
The generator and its seeding/state lifecycle remain separate contracts.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from native_sanitizers import sanitizer_environment
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-random-scaling-contracts.json'


def fixture_data():
    d = load_contract_fixture(FIXTURE)
    rows = d['sources']
    revisions = [r['revision'] for r in rows]
    if (len(set(revisions)) != len(rows) or
            set(revisions) != contract_revisions(d, d['expected_revisions']) or
            not set(d['boundary_controls']) <= set(revisions) or
            not isinstance(d['cases'], list) or not 1 <= len(d['cases']) <= 512 or
            not isinstance(d['contracts'], dict) or not 1 <= len(d['contracts']) <= 16):
        raise ValueError('Explicit own-source scaling coverage and bounded cases required')
    for case in d['cases']:
        if (set(case) != {'maximum', 'sample'} or type(case['sample']) is not int or
                not 0 <= case['sample'] <= 0xffffffff or not isinstance(case['maximum'], str) or
                not re.fullmatch(r'-?0x[0-9a-f]+\.[0-9a-f]+p[+-][0-9]+', case['maximum']) or
                not math.isfinite(float.fromhex(case['maximum'])) or
                abs(float.fromhex(case['maximum'])) > 10000):
            raise ValueError('Explicit finite binary maximum and unsigned sample required')
    for values in d['contracts'].values():
        if (not isinstance(values, list) or len(values) != len(d['cases']) or
                any(type(v) is not int or not 0 <= v <= 0xffffffff for v in values)):
            raise ValueError('One explicit result word per independent scaling case required')
    for row in rows:
        if (row['engine'] != '3741' or type(row['revision']) is not int or row['revision'] <= 0 or
                row['contract'] not in d['contracts'] or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or not row['source_sha256'] or
                any(not re.fullmatch('[0-9a-f]{64}', v) for v in row['source_sha256'].values())):
            raise ValueError('Bound scaling source identities and independent contract required')
    return d


def program(d):
    source = (ROOT / 'src/engines/3741/openbor.c').read_text()
    keys = sorted(d['contracts'])
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <float.h>
_Static_assert(sizeof(float)==4 && FLT_RADIX==2 && FLT_MANT_DIG==24 && FLT_MAX_EXP==128,
               "Native binary float format differs");
_Static_assert(sizeof(unsigned int)==4,"Native random word width differs");
static uint32_t obor_profile_build,sample;
static unsigned draws;
static unsigned int rand32(void) {++draws;return sample;}
@FUNCTION@
static const struct {float maximum;uint32_t sample;} cases[]={@CASES@};
static const uint32_t expected[][sizeof(cases)/sizeof(*cases)]={@EXPECTED@};
static const struct {uint32_t revision;unsigned contract;} profiles[]={@PROFILES@};
int main(void) {
 for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
  obor_profile_build=profiles[p].revision;
  for(unsigned c=0;c<sizeof(cases)/sizeof(*cases);++c) {
   draws=0;sample=cases[c].sample;float value=randf(cases[c].maximum);
   uint32_t bits;memcpy(&bits,&value,sizeof(bits));
   if(bits!=expected[profiles[p].contract][c] || draws!=(cases[c].maximum!=0)) {
    fprintf(stderr,"Random scaling mismatch: profile=%u case=%u bits=%08x expected=%08x draws=%u\n",
            obor_profile_build,c,bits,expected[profiles[p].contract][c],draws);abort();
   }
  }
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",
        (unsigned)((sizeof(cases)/sizeof(*cases))*(sizeof(profiles)/sizeof(*profiles))));return 0;
}
'''.replace('@FUNCTION@', function(source, 'randf')).replace('@CASES@', ',\n'.join(
        '{%sf,%du}' % (c['maximum'], c['sample']) for c in d['cases'])).replace(
        '@EXPECTED@', ',\n'.join('{' + ','.join(str(v) + 'u' for v in d['contracts'][k]) + '}'
                                for k in keys)).replace('@PROFILES@', ',\n'.join(
        '{%du,%d}' % (r['revision'], keys.index(r['contract'])) for r in d['sources']))


class RandomScalingContracts(unittest.TestCase):
    def test_result_bits_and_draw_count_by_profile(self):
        with tempfile.TemporaryDirectory(prefix='anybor-random-scaling-') as temporary:
            source = Path(temporary) / 'contract.c'
            executable = Path(temporary) / 'contract'
            source.write_text(program(fixture_data()))
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O2', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                str(source), '-o', str(executable)], check=True, timeout=30)
            subprocess.run([str(executable)], check=True, timeout=15, env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
