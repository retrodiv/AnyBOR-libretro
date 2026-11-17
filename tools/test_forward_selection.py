"""Check source-defined player, palette and native credit boundaries.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-selection-contracts.json'


def program(data, engine):
    source = (engine / 'openbor.c').read_text()
    contracts = list(data['contracts'])
    cases = []
    for case in data['cases']:
        fields = [str(case[k]) for k in ['kind', 'slot', 'active', 'nosame', 'current',
                  'action', 'colourselect', 'guard_only']]
        fields += ['{' + ','.join(map(str, case[k])) + '}' for k in ['names', 'colours', 'maps']]
        cases.append('{' + ','.join(fields) + '}')
    expected = []
    for key in contracts:
        if len(data['contracts'][key]) != len(cases):
            raise ValueError('Every selection contract needs its complete case inventory')
        expected.append('{' + ','.join('{' + ','.join(map(str, row)) + '}'
                        for row in data['contracts'][key]) + '}')
    credits = []
    for rows in data['credit_rows']:
        credits.append('{' + ','.join('{%d,%d,%d,%s}' % (row['font'], row['row'], row['column'], json.dumps(row['text']))
                                     for row in rows) + '}')
    values = dict(FUNCTIONS='\n'.join(function(source, name) for name in data['functions']),
        CASES=','.join(cases), EXPECTED=','.join(expected),
        CONTEXTS=','.join('{%du,%d,%d}' % (row['revision'], contracts.index(row['contract']), row['credits'])
                          for row in data['sources']),
        CREDIT_ROWS=','.join(credits), CREDIT_COUNTS=','.join(map(str, map(len, data['credit_rows']))))
    result = Path(__file__).with_name('forward_selection_contract.c.in').read_text()
    for key, value in values.items():
        result = result.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', result):
        raise ValueError('Unresolved source-defined selection dependency')
    return result


class ForwardSelectionTests(unittest.TestCase):
    def test_native_roster_join_preview_palette_and_credit_rows(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for row in data['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')
            self.assertTrue(set(data['functions']) <= row['functions'].keys())
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_SELECTION_ENGINE', ROOT / 'src/engines' / data['engine']))
        actual = [json.loads(line) for line in native_output(program(data, engine), data,
                  engine_source=engine).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], status='PASS') for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
