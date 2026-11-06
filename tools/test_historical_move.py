"""Check native movement caller decisions against own-source profile contracts.

Target/item services, geometry and movement helpers are observed providers.
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
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-move-contracts.json'
INTS = {'model': 9, 'state': 5, 'objects': 5, 'animation': 3, 'services': 7, 'path': 2}
FLOATS = {'position': 4, 'velocity': 2, 'destination': 2, 'target': 4, 'item': 3,
          'owner': 2, 'speeds': 3, 'motion': 2, 'waypoint': 2}
UNSIGNED = {'clockstall': 2, 'random': 2}


def data():
    d = load_contract_fixture(FIXTURE)
    rows = d['sources']
    revisions = {r['revision'] for r in rows}
    if (len(revisions) != len(rows) or
            revisions != contract_revisions(d, d['expected_revisions']) or
            not set(d['boundary_controls']) <= revisions or
            not isinstance(d['cases'], list) or not 1 <= len(d['cases']) <= 512 or
            not isinstance(d['contracts'], dict) or not 1 <= len(d['contracts']) <= 64):
        raise ValueError('Explicit own-source movement coverage required')
    for c in d['cases']:
        if (set(c) != {'name', 'first'} | set(INTS) | set(FLOATS) | set(UNSIGNED) or
                not isinstance(c['name'], str) or not 0 < len(c['name']) <= 96 or
                type(c['first']) is not int or not 0 <= c['first'] <= 0xffffffff):
            raise ValueError('Named bounded movement cases required')
        for fields, lo, hi, integer in ((INTS, -32768, 0x7fffffff, True),
                                       (UNSIGNED, 0, 0xffffffff, True),
                                       (FLOATS, -32768, 32767, False)):
            for key, count in fields.items():
                if (not isinstance(c[key], list) or len(c[key]) != count or any(
                        type(v) not in ((int,) if integer else (int, float)) or
                        not math.isfinite(v) or not lo <= v <= hi for v in c[key])):
                    raise ValueError('Explicit bounded movement field vectors required')
        if c['path'][0] not in (0, 1) or not 0 <= c['path'][1] <= 2:
            raise ValueError('Bounded owned waypoint storage required')
    for results in d['contracts'].values():
        if not isinstance(results, list) or len(results) != len(d['cases']):
            raise ValueError('One expected movement result per shared case required')
        for result in results:
            if result is None:
                continue
            if (set(result) != {'state', 'vectors', 'trace'} or
                    not isinstance(result['state'], list) or len(result['state']) != 8 or
                    any(type(v) is not int for v in result['state']) or
                    not isinstance(result['vectors'], list) or len(result['vectors']) != 4 or
                    any(type(v) is not int or not 0 <= v <= 0xffffffff for v in result['vectors']) or
                    not isinstance(result['trace'], str) or len(result['trace']) > 1023):
                raise ValueError('Explicit movement state and service trace required')
    for r in rows:
        if (r['engine'] != '3741' or type(r['revision']) is not int or r['revision'] <= 0 or
                r['contract'] not in d['contracts'] or
                not re.fullmatch('[0-9a-f]{40}', r['commit']) or not r['source_sha256'] or
                any(not re.fullmatch('[0-9a-f]{64}', v) for v in r['source_sha256'].values()) or
                any((e is None) != (r['revision'] < c['first']) for c, e in
                    zip(d['cases'], d['contracts'][r['contract']]))):
            raise ValueError('Bound own-source identities, applicability and results required')
    return d


def program(d):
    source = (ROOT / 'src/engines/3741/openbor.c').read_text()
    cases = []
    for c in d['cases']:
        vectors = []
        for fields, kind in ((INTS, 'int'), (FLOATS, 'float'), (UNSIGNED, 'unsigned')):
            for key in fields:
                values = [float(v).hex() + 'f' if kind == 'float' else
                          str(v) + ('u' if kind == 'unsigned' else '') for v in c[key]]
                vectors.append('{' + ','.join(values) + '}')
        cases.append('{' + str(c['first']) + 'u,' + ','.join(vectors) + '}')
    return Path(__file__).with_name('move_contract.c.in').read_text().replace(
        '@FUNCTION@', function(source, 'common_move')).replace(
        '@DISTANCE@', function(source, 'diff')).replace('@CASES@', ',\n'.join(cases)).replace(
        '@PROFILES@', ','.join(str(r['revision']) + 'u' for r in d['sources']))


class MoveContracts(unittest.TestCase):
    def test_native_decisions_and_state_by_profile(self):
        d = data()
        engine = ROOT / 'src/engines/3741'
        includes = [ROOT / 'src/port/libretro', engine, engine / 'source'] + [p for p in sorted(
            (engine / 'source').iterdir()) if p.is_dir()]
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
            'clang' in Path(word).name for word in compiler) else []
        with tempfile.TemporaryDirectory(prefix='anybor-move-') as temporary:
            source = Path(temporary) / 'contract.c'
            executable = Path(temporary) / 'contract'
            source.write_text(program(d))
            subprocess.run(compiler + warnings + ['-std=gnu99', '-fsigned-char', '-O2',
                '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-Wno-unused-variable',
                '-Wno-error=deprecated-declarations', '-Wno-error=sign-compare', '-DOBOR_ENGINE_BUILD=3741', '-DLIBRETRO=1',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-g',
                *('-I' + str(p) for p in includes), str(source), '-o', str(executable)],
                check=True, timeout=45)
            raw = subprocess.check_output([str(executable)], text=True, timeout=30,
                                          env=sanitizer_environment())
        observed = [json.loads(line) for line in raw.splitlines()]
        expected = [(r, i, e) for r in d['sources'] for i, e in enumerate(
            d['contracts'][r['contract']]) if e is not None]
        self.assertEqual(len(observed), len(expected))
        for result, (row, i, oracle) in zip(observed, expected):
            with self.subTest(revision=row['revision'], case=d['cases'][i]['name']):
                self.assertEqual(result, dict(revision=row['revision'], case=i, **oracle))


if __name__ == '__main__':
    unittest.main()
