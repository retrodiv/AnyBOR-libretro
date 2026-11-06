"""Check complete wandering functions against own-profile movement oracles.

Native records, distance and caller arithmetic execute. Attack choice and
random words are observed providers; their implementations remain separate.
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
import sys
import tempfile
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from native_sanitizers import sanitizer_environment
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-wander-contracts.json'
VECTORS = {'video': 2, 'camera': 2, 'zrange': 2, 'position': 2, 'target': 4, 'range': 2}
SCALARS = ('present', 'nomove', 'dox', 'doz', 'speed', 'grab', 'health', 'sortid',
           'pathblocked', 'aggression', 'clock', 'pick')


def data(path=FIXTURE):
    d = load_contract_fixture(path)
    rows = d['sources']
    revisions = [r['revision'] for r in rows]
    if (len(set(revisions)) != len(rows) or
            set(revisions) != contract_revisions(d, d['expected_revisions']) or
            not set(d['boundary_controls']) <= set(revisions) or
            not isinstance(d['cases'], list) or not 1 <= len(d['cases']) <= 512 or
            not isinstance(d['contracts'], dict) or not 1 <= len(d['contracts']) <= 64):
        raise ValueError('Explicit own-source wander coverage and bounded cases required')
    def number(v):
        return type(v) in (int, float) and math.isfinite(v) and -32768 <= v <= 0xffffffff
    for c in d['cases']:
        if (set(c) != {'name', 'random'} | set(VECTORS) | set(SCALARS) or
                not isinstance(c['name'], str) or not 0 < len(c['name']) <= 96 or
                any(not isinstance(c[k], list) or len(c[k]) != n or
                    any(not number(v) for v in c[k]) for k, n in VECTORS.items()) or
                any(not number(c[k]) for k in SCALARS) or
                not isinstance(c['random'], list) or len(c['random']) != 3 or
                any(type(v) is not int or not 0 <= v <= 0xffffffff for v in c['random'])):
            raise ValueError('Explicit bounded native movement inputs required')
    for results in d['contracts'].values():
        if not isinstance(results, list) or len(results) != len(d['cases']):
            raise ValueError('One own-source movement result per shared case required')
        for result in results:
            if (set(result) != {'velocity', 'destination', 'stalltime', 'result', 'trace'} or
                    any(not isinstance(result[k], list) or len(result[k]) != 2 or
                        any(not number(v) for v in result[k]) for k in ('velocity', 'destination')) or
                    type(result['stalltime']) is not int or not 0 <= result['stalltime'] <= 0xffffffff or
                    result['result'] not in (0, 1) or not isinstance(result['trace'], str) or
                    not re.fullmatch(r'[DP0-9;]{0,128}', result['trace'])):
                raise ValueError('Explicit movement state and random/choice trace required')
    for row in rows:
        if (row['engine'] != '3741' or type(row['revision']) is not int or row['revision'] <= 0 or
                row['contract'] not in d['contracts'] or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or not row['source_sha256'] or
                any(not re.fullmatch('[0-9a-f]{64}', v) for v in row['source_sha256'].values())):
            raise ValueError('Bound own-source movement identities and result group required')
    return d


def program(d, *, routine='common_try_wander'):
    calls = {
        'common_try_wander': 'common_try_wander(test->present?&target:NULL,test->dox,test->doz)',
        'common_try_wandercompletely': 'common_try_wandercompletely(test->dox,test->doz)',
    }
    if routine not in calls:
        raise ValueError('An explicit wandering routine is required')
    source = (ROOT / 'src/engines/3741/openbor.c').read_text()
    keys = sorted(d['contracts'])
    def vector(values):
        return '{' + ','.join(float(v).hex() + 'f' for v in values) + '}'
    cases = []
    for c in d['cases']:
        fields = [json.dumps(c['name'])] + [vector(c[k]) for k in VECTORS]
        fields += [float(c[k]).hex() + 'f' if k in ('speed', 'grab') else
                   str(c[k]) + ('u' if k == 'clock' else '') for k in SCALARS]
        fields.append('{' + ','.join(str(v) + 'u' for v in c['random']) + '}')
        cases.append('{' + ','.join(fields) + '}')
    results = []
    for key in keys:
        results.append('{' + ',\n'.join('{' + ','.join([
            vector(r['velocity']), vector(r['destination']), str(r['stalltime']) + 'u',
            str(r['result']), json.dumps(r['trace'])]) + '}' for r in d['contracts'][key]) + '}')
    return Path(__file__).with_name('wander_contract.c.in').read_text().replace(
        '@FUNCTION@', function(source, routine)).replace('@CALL@', calls[routine]).replace(
        '@DISTANCE@', function(source, 'diff')).replace('@CASES@', ',\n'.join(cases)).replace(
        '@RESULTS@', ',\n'.join(results)).replace('@PROFILES@', ',\n'.join(
            '{%du,%d}' % (r['revision'], keys.index(r['contract'])) for r in d['sources']))


class WanderContracts(unittest.TestCase):
    fixture = FIXTURE
    routine = 'common_try_wander'

    def test_native_velocity_destination_and_draws_by_profile(self):
        engine = ROOT / 'src/engines/3741'
        paths = [ROOT / 'src/port/libretro', engine, engine / 'source'] + [p for p in sorted(
            (engine / 'source').iterdir()) if p.is_dir()]
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
            'clang' in Path(word).name for word in compiler) else []
        with tempfile.TemporaryDirectory(prefix='anybor-wander-') as temporary:
            source = Path(temporary) / 'contract.c'
            executable = Path(temporary) / 'contract'
            source.write_text(program(data(self.fixture), routine=self.routine))
            subprocess.run(compiler + warnings + ['-std=gnu99', '-fsigned-char', '-O2',
                '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-Wno-unused-variable',
                '-Wno-error=deprecated-declarations', '-DOBOR_ENGINE_BUILD=3741', '-DLIBRETRO=1',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-g',
                *('-I' + str(p) for p in paths), str(source), '-o', str(executable)],
                check=True, timeout=45)
            subprocess.run([str(executable)], check=True, timeout=30, env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
