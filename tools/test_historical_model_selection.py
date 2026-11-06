"""Check native model rotation, secret metadata reads and diagnostics.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_combo_loading import model_case
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-model-selection-contracts.json'


def program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    cases = []
    for row in data['cases']:
        if not 0 <= len(row['cache']) <= 4 or not -2 <= row['current'] < len(row['cache']):
            raise ValueError('Bounded model cache and current pointer required')
        if not 0 <= len(row['arguments']) <= 3 or any(
                not isinstance(arg, str) or len(arg) > 32 or not arg.isascii()
                for arg in row['arguments']):
            raise ValueError('Bounded supplied argument tokens required')
        models = []
        for entry in row['cache']:
            values = [entry[key] for key in ('present', 'kind', 'secret', 'clearcount', 'selectable')]
            if (values[0] not in (0, 1) or not 0 <= values[1] <= 2 or
                    not all(type(value) is int and -128 <= value <= 127 for value in values[2:])):
                raise ValueError('Defined model-field inputs required')
            models.append('{%s}' % ','.join(map(str, values)))
        cases.append('{%d,%d,%d,%d,%d,{%s},{%s}}' % (
            len(models), row['current'], row['allow_secret'], row['bonus'], row['load'],
            ','.join(models) or '{0}',
            ','.join(['"secret"'] + [json.dumps(arg) for arg in row['arguments']])) )
    macro = re.search(r'(?m)^#define GET_INT_ARG\(z\)[^\n]*', source)
    if macro is None:
        raise ValueError('Native integer argument route required')
    parts = dict(FUNCTIONS='\n'.join(function(source, name) for name in
                 ('isNumeric', 'getValidInt', 'nextplayermodel', 'prevplayermodel')),
                 COMMAND=model_case(source, 'SECRET'), INTEGER_MACRO=macro[0],
                 CONTEXTS=','.join('{%du,%d}' % (row['revision'], row['clear_present'])
                                   for row in data['sources']), CASES=',\n'.join(cases))
    text = Path(__file__).with_name('model_selection_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native model selection dependency')
    return text


class ModelSelectionContracts(unittest.TestCase):
    def test_native_rotation_metadata_and_messages(self):
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
