"""Check native path searches and blocked-movement caller contracts.

The early search and the defined A* output prefix execute against explicit
geometry. The caller observes a separate fully initialized A* service result.
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
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-path-contracts.json'
INTS = {'flags': 10, 'video': 2, 'zrange': 2}
FLOATS = {'position': 2, 'target': 2, 'velocity': 2, 'destination': 2, 'random': 3}


def data():
    d = load_contract_fixture(FIXTURE)
    rows = d['sources']
    revisions = {r['revision'] for r in rows}
    if (len(revisions) != len(rows) or revisions != contract_revisions(d, d['expected_revisions']) or
            not set(d['boundary_controls']) <= revisions or not 1 <= len(d['cases']) <= 256 or
            not isinstance(d['contracts'], dict) or not 1 <= len(d['contracts']) <= 64):
        raise ValueError('Explicit own-source path coverage required')
    for c in d['cases']:
        if (set(c) != {'name', 'routine', 'first', 'last', 'speed', 'step', 'geometry',
                      'exceptional', 'clock', 'stall'} | set(INTS) | set(FLOATS) or
                not isinstance(c['name'], str) or not 0 < len(c['name']) <= 96 or
                c['routine'] not in (0, 1, 2) or c['geometry'] not in (0, 1, 2, 3) or
                c['exceptional'] not in range(6) or
                any(type(c[k]) is not int or not 0 <= c[k] <= 0xffffffff
                    for k in ('first', 'last', 'clock', 'stall')) or c['last'] < c['first']):
            raise ValueError('Named bounded path cases required')
        for fields, lo, hi, integer in ((INTS, -32768, 65535, True),
                                       (FLOATS, -32768, 32767, False)):
            for key, n in fields.items():
                if (not isinstance(c[key], list) or len(c[key]) != n or any(
                        type(v) not in ((int,) if integer else (int, float)) or
                        not math.isfinite(v) or not lo <= v <= hi for v in c[key])):
                    raise ValueError('Explicit bounded path field vectors required')
        if (any(type(c[k]) not in (int, float) or not math.isfinite(c[k]) or
                not -32768 <= c[k] <= 32767 for k in ('speed', 'step')) or
                not all(0 <= v <= 2 for v in c['random']) or
                not 0 <= c['flags'][5] <= 255 or c['flags'][6] not in (0, 1) or
                c['flags'][9] not in (0, 1) or
                (c['routine'] == 2 and (c['step'] <= 0 or c['exceptional'] or c['flags'][9]))):
            raise ValueError('Bounded arguments and defined direct A* input domain required')
    for results in d['contracts'].values():
        if not isinstance(results, list) or len(results) != len(d['cases']):
            raise ValueError('One own-source path result per shared case required')
        for r in results:
            if r is None:
                continue
            if (set(r) != {'state', 'vectors', 'path', 'search', 'trace'} or
                    not isinstance(r['state'], list) or len(r['state']) != 7 or
                    not isinstance(r['vectors'], list) or len(r['vectors']) != 6 or
                    not isinstance(r['path'], list) or len(r['path']) != 2 or
                    not isinstance(r['search'], list) or len(r['search']) != 6 or
                    any(type(v) is not int for k in ('state', 'vectors', 'path', 'search') for v in r[k]) or
                    not isinstance(r['trace'], str) or len(r['trace']) > 511):
                raise ValueError('Explicit path state, initialized-prefix observations and trace required')
    for r in rows:
        if (r['engine'] != '3741' or type(r['revision']) is not int or r['revision'] <= 0 or
                r['contract'] not in d['contracts'] or not re.fullmatch('[0-9a-f]{40}', r['commit']) or
                not r['source_sha256'] or any(not re.fullmatch('[0-9a-f]{64}', v)
                                             for v in r['source_sha256'].values()) or
                any((e is None) != (not c['first'] <= r['revision'] <= c['last']) for c, e in
                    zip(d['cases'], d['contracts'][r['contract']]))):
            raise ValueError('Bound own-source path identities and applicability required')
    return d


def program(d):
    source = (ROOT / 'src/engines/3741/openbor.c').read_text()
    if 'static int obor_profile_pathfind(' not in source:
        raise ValueError('Historical path-search function/storage missing')
    first = source.index('/* Historical path-search scratch;')
    last = source.index('static int obor_profile_pathfind(', first)
    storage = source[first:last]
    constants = re.search(r'(?m)^#define astarw[^\n]*\n#define astarh[^\n]*\n#define starts[^\n]*', source)
    if constants is None:
        raise ValueError('Explicit native A* dimension constants required')
    storage += '\n' + constants[0] + '\n'
    cases = []
    for c in d['cases']:
        values = [str(c['routine']), str(c['first']) + 'u', str(c['last']) + 'u']
        for key in INTS:
            values.append('{' + ','.join(str(v) for v in c[key]) + '}')
        for key in FLOATS:
            values.append('{' + ','.join(float(v).hex() + 'f' for v in c[key]) + '}')
        values += [float(c['speed']).hex() + 'f', float(c['step']).hex() + 'f',
                   str(c['geometry']), str(c['exceptional']), str(c['clock']) + 'u', str(c['stall']) + 'u']
        cases.append('{' + ','.join(values) + '}')
    code = Path(__file__).with_name('path_contract.c.in').read_text().replace(
        '@CASES@', ',\n'.join(cases)).replace('@PROFILES@', ','.join(
            str(r['revision']) + 'u' for r in d['sources'])).replace('@STORAGE@', storage)
    for name in ('diff', 'obor_profile_pathfind', 'astar', 'checkpathblocked'):
        code = code.replace('@' + name.upper() + '@', function(source, name))
    return code


class PathContracts(unittest.TestCase):
    def test_native_path_results_and_caller_by_profile(self):
        d = data()
        engine = ROOT / 'src/engines/3741'
        includes = [ROOT / 'src/port/libretro', engine, engine / 'source'] + [p for p in sorted(
            (engine / 'source').iterdir()) if p.is_dir()]
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
            'clang' in Path(word).name for word in compiler) else []
        with tempfile.TemporaryDirectory(prefix='anybor-paths-') as temporary:
            source = Path(temporary) / 'contract.c'
            executable = Path(temporary) / 'contract'
            source.write_text(program(d))
            subprocess.run(compiler + warnings + ['-std=gnu99', '-fsigned-char', '-O2',
                '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-Wno-unused-variable',
                '-Wno-error=deprecated-declarations', '-Wno-error=misleading-indentation',
                '-DOBOR_ENGINE_BUILD=3741', '-DLIBRETRO=1',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-g',
                *('-I' + str(p) for p in includes), str(source), '-lm', '-o', str(executable)],
                check=True, timeout=45)
            raw = subprocess.check_output([str(executable)], text=True, timeout=45,
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
