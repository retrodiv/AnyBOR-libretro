"""Check legacy matrix matching, input priority and callback continuation.

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
from test_historical_combo_loading import program as loading_program

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-legacy-combo-contracts.json'


def program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    # Reuse actual loader windows and real record types, not a second parser.
    load = loading_program(dict(engine=data['engine'], sources=[data['sources'][0]],
        cases=[dict(conflicts=0, seed=0, operations=[])]))
    load = load.replace(function(load, 'main'), '')
    cases = []
    for row in data['cases']:
        operations = ['{%d,{%s}}' % (kind, ','.join(json.dumps(s) for s in args))
                      for kind, args in row['operations']]
        fields = [str(row[key]) for key in data['parameters']]
        cases.append('{%s,%d,{%s}}' % (','.join(fields), len(operations), ','.join(operations)))
    helpers = ['diff', 'obor_check_combo_key']
    if re.search(r'(?m)^static unsigned int obor_legacy_direction_value\(', source):
        helpers.insert(0, 'obor_legacy_direction_value')
    parts = dict(LOAD=load, FUNCTIONS='\n'.join(function(source, name) for name in helpers), PREINPUT=function(source, 'player_preinput'),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=',\n'.join(cases))
    text = Path(__file__).with_name('legacy_combo_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved legacy combo dependency')
    return text


class LegacyComboContracts(unittest.TestCase):
    def test_native_matrix_input_and_loaded_rows(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        for row in data['sources']:
            self.assertEqual(len(data['contracts'][row['contract']]), len(data['cases']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        expected = [(row, i, value) for row in data['sources'] for i, value in
                    enumerate(data['contracts'][row['contract']])]
        self.assertEqual(len(actual), len(expected))
        for result, (row, i, value) in zip(actual, expected):
            with self.subTest(profile=row['revision'], case=data['cases'][i]['name']):
                self.assertEqual(result, dict(revision=row['revision'], case=i, **value))


if __name__ == '__main__':
    unittest.main()
