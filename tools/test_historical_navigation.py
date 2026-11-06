"""Check complete native chase, avoidance, following and pickup movement.

Distance and speed adjustment execute; attack choice/random words and the
animation callback are observed providers.
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
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-navigation-contracts.json'
VECTORS = {'position': 2, 'target': 2, 'velocity': 2, 'destination': 2,
           'speeds': 3, 'camera': 2}
INTS = {'flags': 10, 'video': 2, 'range': 4}
ROUTINES = ('common_try_chase', 'common_try_avoid', 'common_try_follow',
            'common_try_pick', 'adjustspeed')


def data():
    d = load_contract_fixture(FIXTURE)
    rows = d['sources']
    revisions = {r['revision'] for r in rows}
    if (len(revisions) != len(rows) or
            revisions != contract_revisions(d, d['expected_revisions']) or
            not set(d['boundary_controls']) <= revisions or
            not isinstance(d['cases'], list) or not 1 <= len(d['cases']) <= 512 or
            not isinstance(d['contracts'], dict) or not 1 <= len(d['contracts']) <= 64):
        raise ValueError('Explicit own-source navigation coverage required')
    for c in d['cases']:
        if (set(c) != {'name', 'routine', 'scroll', 'idle_distance', 'word', 'stall'} |
                set(VECTORS) | set(INTS) or not isinstance(c['name'], str) or
                not 0 < len(c['name']) <= 96 or type(c['routine']) is not int or
                not 0 <= c['routine'] < len(ROUTINES) or c['scroll'] not in (0, 1, 2) or
                type(c['idle_distance']) is not int or not -32768 <= c['idle_distance'] <= 32767 or
                any(type(c[k]) is not int or not 0 <= c[k] <= 0xffffffff
                    for k in ('word', 'stall'))):
            raise ValueError('Named bounded navigation cases required')
        for key, n in (VECTORS | INTS).items():
            if (not isinstance(c[key], list) or len(c[key]) != n or any(
                    type(v) not in ((int,) if key in INTS else (int, float)) or
                    not math.isfinite(v) or not -32768 <= v <= 32767 for v in c[key])):
                raise ValueError('Explicit bounded native navigation field vectors required')
        if (any(v not in (0, 1) for v in c['flags']) or
                (c['routine'] == 3 and not c['flags'][0])):
            raise ValueError('Boolean navigation flags and a valid pickup target required')
    for results in d['contracts'].values():
        if not isinstance(results, list) or len(results) != len(d['cases']):
            raise ValueError('One expected result per shared navigation case required')
        for r in results:
            if (set(r) != {'vectors', 'running', 'stall', 'result', 'trace'} or
                    not isinstance(r['vectors'], list) or len(r['vectors']) != 4 or
                    any(type(v) is not int or not 0 <= v <= 0xffffffff for v in r['vectors']) or
                    r['running'] not in (0, 1) or r['result'] not in (0, 1) or
                    type(r['stall']) is not int or not 0 <= r['stall'] <= 0xffffffff or
                    not isinstance(r['trace'], str) or len(r['trace']) > 255):
                raise ValueError('Explicit navigation state and service trace required')
    for r in rows:
        if (r['engine'] != '3741' or type(r['revision']) is not int or r['revision'] <= 0 or
                r['contract'] not in d['contracts'] or not re.fullmatch('[0-9a-f]{40}', r['commit']) or
                not r['source_sha256'] or any(not re.fullmatch('[0-9a-f]{64}', v)
                                             for v in r['source_sha256'].values())):
            raise ValueError('Bound own-source navigation identities and results required')
    return d


def program(d):
    source = (ROOT / 'src/engines/3741/openbor.c').read_text()
    cases = []
    for c in d['cases']:
        values = [str(c['routine'])]
        for key in INTS:
            values.append('{' + ','.join(str(v) for v in c[key]) + '}')
        for key in VECTORS:
            values.append('{' + ','.join(float(v).hex() + 'f' for v in c[key]) + '}')
        values += [str(c['scroll']), str(c['idle_distance']), str(c['word']) + 'u',
                   str(c['stall']) + 'u']
        cases.append('{' + ','.join(values) + '}')
    code = Path(__file__).with_name('navigation_contract.c.in').read_text().replace(
        '@CASES@', ',\n'.join(cases)).replace('@PROFILES@', ','.join(
            str(r['revision']) + 'u' for r in d['sources']))
    for name in ('diff', 'adjustspeed', *ROUTINES[:4]):
        code = code.replace('@' + name.upper() + '@', function(source, name))
    return code


class NavigationContracts(unittest.TestCase):
    def test_native_navigation_state_by_profile(self):
        d = data()
        engine = ROOT / 'src/engines/3741'
        includes = [ROOT / 'src/port/libretro', engine, engine / 'source'] + [p for p in sorted(
            (engine / 'source').iterdir()) if p.is_dir()]
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
            'clang' in Path(word).name for word in compiler) else []
        with tempfile.TemporaryDirectory(prefix='anybor-navigation-') as temporary:
            source = Path(temporary) / 'contract.c'
            executable = Path(temporary) / 'contract'
            source.write_text(program(d))
            subprocess.run(compiler + warnings + ['-std=gnu99', '-fsigned-char', '-O2',
                '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-Wno-unused-variable',
                '-Wno-error=deprecated-declarations', '-DOBOR_ENGINE_BUILD=3741', '-DLIBRETRO=1',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-g',
                *('-I' + str(p) for p in includes), str(source), '-o', str(executable)],
                check=True, timeout=45)
            raw = subprocess.check_output([str(executable)], text=True, timeout=30,
                                          env=sanitizer_environment())
        observed = [json.loads(line) for line in raw.splitlines()]
        expected = [(r, i, e) for r in d['sources'] for i, e in enumerate(d['contracts'][r['contract']])]
        self.assertEqual(len(observed), len(expected))
        for result, (row, i, oracle) in zip(observed, expected):
            with self.subTest(revision=row['revision'], case=d['cases'][i]['name']):
                self.assertEqual(result, dict(revision=row['revision'], case=i, **oracle))


if __name__ == '__main__':
    unittest.main()
