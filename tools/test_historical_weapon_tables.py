"""Check native weapon commands, inheritance, selection and item consumers.

Tokenization and model switching are declared services. Their full algorithms
and unrelated model fields remain separate contracts.
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
from test_early_jump_walkoff import braced_statement

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-weapon-table-contracts.json'


def program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    cases = []
    for row in data['cases']:
        commands = ['{%s}' % ','.join(json.dumps(s) for s in args)
                    for args in row['commands']]
        fields = [str(int(row[k])) for k in data['parameters']]
        cases.append('{%s,%d,{%s}}' % (','.join(fields), len(commands), ','.join(commands)))
    parts = dict(FUNCTIONS='\n'.join(function(core, name) for name in data['functions']),
                 INHERIT=braced_statement(function(core, 'set_model_ex'),
                     'if(!(newmodel->model_flag & MODEL_NO_WEAPON_COPY))'),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
                 CASES=',\n'.join(cases))
    text = Path(__file__).with_name('weapon_table_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native weapon table dependency')
    return text


class WeaponTableContracts(unittest.TestCase):
    def test_native_commands_inheritance_and_consumers(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        expected = [(row, i, value) for row in data['sources'] for i, value in
                    enumerate(data['contracts'][row['contract']])]
        self.assertEqual(len(actual), len(expected))
        for result, (row, i, value) in zip(actual, expected):
            with self.subTest(profile=row['revision'], case=data['cases'][i]['name']):
                self.assertEqual(result, dict(revision=row['revision'], case=i, **value))


if __name__ == '__main__':
    unittest.main()
