"""Check complete native entity display with source-reviewed queue observations.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-terrain-display-contracts.json'


def program(data, engine):
    core = (engine / 'openbor.c').read_text()
    contracts = list(data['contracts'])
    expected = []
    for key in contracts:
        rows = data['contracts'][key]
        if len(rows) != len(data['cases']):
            raise ValueError('Complete independent display observations required')
        values = []
        for row in rows:
            if (not isinstance(row['rows'], list) or len(row['rows']) > 8 or
                    any(len(v) != 12 or any(type(n) is not int or not -2147483648 <= n <= 2147483647
                                           for n in v) for v in row['rows'])):
                raise ValueError('Bounded complete sprite/method observations required')
            values.append('{%d,%d,{%s}}' % (len(row['rows']), row['holez'],
                ','.join('{'+','.join(map(str, value))+'}' for value in row['rows'])))
        expected.append('{'+','.join(values)+'}')
    cases = []
    for row in data['cases']:
        cases.append('{%s,%s}' % (json.dumps(row['name']), ','.join(
            float(row[name]).hex()+'f' if name == 'altitude' else str(row[name])
            for name in data['case_fields'])))
    plain = re.findall(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{[^;]+\};', core)
    if len(plain) != 1:
        raise ValueError('One complete native default draw method required')
    values = dict(PLAIN=plain[0], FUNCTIONS='\n'.join(function(core, name) for name in data['functions']),
        CASES=','.join(cases), EXPECTED=','.join(expected),
        CONTEXTS=','.join('{%du,%d}' % (row['revision'], contracts.index(row['contract'])) for row in data['sources']))
    code = Path(__file__).with_name('forward_terrain_display_contract.c.in').read_text()
    for key, value in values.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved native terrain display dependency')
    return code


class ForwardTerrainDisplayTests(unittest.TestCase):
    def test_native_platform_sort_shadow_geometry_and_height_queries(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_TERRAIN_DISPLAY_ENGINE', ROOT / 'src/engines' / data['engine']))
        actual = [json.loads(line) for line in native_output(program(data, engine), data, engine_source=engine).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], cases=len(data['cases']), status='PASS') for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
