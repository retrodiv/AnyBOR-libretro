"""Check own-profile AI attack preparation with observed external services.

The complete native caller executes with native entity and animation records.
Target/range, energy/cost, random samples, chains and animation are providers;
their arguments and ordering are checked, not their implementations.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
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
from test_historical_common_think import native_output

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-ai-prepare-contracts.json'
INPUTS = ('target', 'flip', 'noflip', 'wait', 'weapon', 'chain', 'chain_ok',
          'valid', 'range', 'mp', 'hp', 'cost', 'mutate')
OUTPUTS = ('animation', 'action', 'idling', 'attacking', 'turning', 'direction')


def rows():
    fixture = load_contract_fixture(FIXTURE)
    data = fixture['sources']
    revisions = [row['revision'] for row in data]
    if (len(set(revisions)) != len(data) or
            set(revisions) != contract_revisions(fixture, fixture['expected_revisions']) or
            not set(fixture['boundary_controls']) <= set(revisions)):
        raise ValueError('Own-source AI preparation coverage differs')
    for row in data:
        if (row['engine'] != '3741' or type(row['revision']) is not int or row['revision'] <= 0 or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not row['source_sha256'] or any(not re.fullmatch('[0-9a-f]{64}', v)
                    for v in row['source_sha256'].values()) or
                not isinstance(row['cases'], list) or not 1 <= len(row['cases']) <= 128):
            raise ValueError('Bound original identities and bounded AI cases required')
        for case in row['cases']:
            if (set(case) != {'name', 'inputs', 'random', 'expected'} or
                    not isinstance(case['name'], str) or not 0 < len(case['name']) <= 96 or
                    set(case['inputs']) != set(INPUTS) or
                    set(case['expected']) != set(OUTPUTS) | {'trace'} or
                    any(type(v) is not int or not 0 <= v <= 511 for v in case['inputs'].values()) or
                    any(type(case['expected'][k]) is not int or not -1 <= case['expected'][k] <= 511
                        for k in OUTPUTS) or not isinstance(case['random'], list) or
                    not 0 <= len(case['random']) <= 16 or
                    any(type(v) is not int or not 0 <= v <= 0x7fffffff for v in case['random']) or
                    not isinstance(case['expected']['trace'], str) or
                    not re.fullmatch(r'[A-Z0-9:;\-]{0,1024}', case['expected']['trace'])):
                raise ValueError('Explicit bounded AI inputs and ordered observations required')
    return data


def program(data):
    source = (ROOT / 'src/engines/3741/openbor.c').read_text()
    cases = []
    for row in data:
        for case in row['cases']:
            values = [str(row['revision']) + 'u', json.dumps(case['name'])]
            values += [str(case['inputs'][k]) for k in INPUTS]
            values += [str(case['expected'][k]) for k in OUTPUTS]
            values += [json.dumps(case['expected']['trace']), str(len(case['random'])),
                       '{' + ','.join(map(str, case['random'] or [0])) + '}']
            cases.append('{' + ','.join(values) + '}')
    template = Path(__file__).with_name('ai_prepare_contract.c.in').read_text()
    return template.replace('@PREPARE@', function(source, 'normal_prepare')).replace(
        '@CASES@', ',\n'.join(cases))


class AIPreparationContracts(unittest.TestCase):
    def test_screen_coordinate_queries_and_level_absence(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') /
                                     'profile-screen-coordinate-contracts.json')
        profiles = data['sources']
        self.assertEqual(len(profiles), len({r['revision'] for r in profiles}))
        self.assertEqual({r['revision'] for r in profiles},
                         contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in profiles})
        self.assertTrue(all(type(r['level_guard']) is bool for r in profiles))
        self.assertTrue(data['advances'])
        for pair in data['advances']:
            self.assertEqual(len(pair), 2)
            self.assertTrue(all(type(v) in (int, float) and -32768 <= v <= 32767 for v in pair))
        program = Path(__file__).with_name('screen_coordinate_contract.c.in').read_text().replace(
            '@PROFILES@', ','.join('{%du,%d}' % (r['revision'], r['level_guard']) for r in profiles)
        ).replace('@ADVANCES@', ','.join('{%s,%s}' % tuple(pair) for pair in data['advances']))
        actual = [json.loads(line) for line in native_output(program, data).splitlines()]
        self.assertEqual(actual, [{'revision': r['revision'], 'cases': len(data['advances'])*16}
                                  for r in profiles])

    def test_target_range_limits_and_coordinate_conversions(self):
        fixture = load_contract_fixture(Path(__file__).with_name('fixtures') /
                                        'profile-target-range-contracts.json')
        profiles, cases = fixture['sources'], fixture['cases']
        self.assertEqual(len(profiles), len({r['revision'] for r in profiles}))
        self.assertEqual({r['revision'] for r in profiles},
                         contract_revisions(fixture, fixture['expected_revisions']))
        self.assertTrue(set(fixture['boundary_controls']) <= {r['revision'] for r in profiles})
        self.assertTrue(all(type(r['regime']) is int and 0 <= r['regime'] < 3 for r in profiles))
        self.assertTrue(cases)
        self.assertEqual(len(cases), len({r['name'] for r in cases}))
        entries = []
        for case in cases:
            for key in ('self', 'target'):
                self.assertEqual(len(case[key]), 4)
                self.assertTrue(all(type(v) in (int, float) and -32768 <= v <= 32767
                                    for v in case[key]))
            self.assertEqual(len(case['range']), 8)
            self.assertTrue(all(type(v) is int and -32768 <= v <= 32767 for v in case['range']))
            self.assertIn(case['direction'], (0, 1))
            self.assertIn(case['present'], (0, 1))
            self.assertEqual(len(case['expected']), 3)
            self.assertTrue(all(len(pair) == 2 and all(type(v) is int and v in (0, 1)
                                                      for v in pair)
                                for pair in case['expected']))
            vector = lambda values: '{' + ','.join(map(str, values)) + '}'
            entries.append('{' + ','.join((json.dumps(case['name']), vector(case['self']),
                vector(case['target']), vector(case['range']), str(case['direction']),
                str(case['present']), '{' + ','.join(vector(pair) for pair in
                                                   case['expected']) + '}')) + '}')
        program = Path(__file__).with_name('target_range_contract.c.in').read_text().replace(
            '@PROFILES@', ','.join('{%du,%d}' % (r['revision'], r['regime']) for r in profiles)
        ).replace('@CASES@', ',\n'.join(entries))
        observed = [json.loads(line) for line in native_output(program, fixture).splitlines()]
        self.assertEqual(observed, [{'revision': r['revision'], 'cases': len(cases),
                                    'predicates': 2} for r in profiles])

    def test_attack_queries_random_selection_and_callback_order(self):
        engine = ROOT / 'src/engines/3741'
        port = ROOT / 'src/port/libretro'
        paths = [port, engine, engine / 'source'] + [p for p in sorted(
            (engine / 'source').iterdir()) if p.is_dir()]
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
            'clang' in Path(word).name for word in compiler) else []
        with tempfile.TemporaryDirectory(prefix='anybor-ai-prepare-') as temporary:
            source = Path(temporary) / 'contract.c'
            executable = Path(temporary) / 'contract'
            source.write_text(program(rows()))
            subprocess.run(compiler + warnings + ['-std=gnu99', '-fsigned-char', '-Wall', '-Wextra',
                '-Werror', '-Wno-unused-function', '-Wno-unused-variable',
                '-Wno-error=deprecated-declarations', '-DOBOR_ENGINE_BUILD=3741', '-DLIBRETRO=1',
                '-fsanitize=address,undefined', '-g', *('-I' + str(p) for p in paths),
                str(source), '-o', str(executable)], check=True, timeout=45)
            subprocess.run([str(executable)], check=True, timeout=30, env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
