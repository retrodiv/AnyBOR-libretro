"""Exercise profile-owned loading commands and their diagnostics.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-lifebar-contracts.json'


def lifebar_program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    functions = []
    for name in ('isNumeric', 'getValidInt', 'ParseArgs', '_makecolour', 'lifebar_colors'):
        body = function(core, name)
        if name == 'ParseArgs':
            # The original tokenizer deliberately shares switch case tails.
            body = ('#pragma GCC diagnostic push\n'
                    '#pragma GCC diagnostic ignored "-Wimplicit-fallthrough"\n' +
                    body + '\n#pragma GCC diagnostic pop\n')
        functions.append(body)
    functions = '\n'.join(functions)
    functions = '\n'.join([
        function((engine / 'source/gamelib/pixelformat.c').read_text(), 'colour32'),
        function((engine / 'source/utils.c').read_text(), 'getNewLineStart'), functions])
    cases = []
    for case in data['cases']:
        values = ['NULL' if case[key] is None else json.dumps(case[key], ensure_ascii=True)
                  for key in ('external', 'internal')]
        cases.append('{' + ','.join(values) + '}')
    parts = dict(FUNCTIONS=functions, CASES=',\n'.join(cases),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
                 COLOR_NAMES=','.join('&' + name for name in data['color_fields']),
                 INITIAL_COLORS=','.join(str(value) for value in data['initial']['colors']),
                 INITIAL_ALPHA=str(data['initial']['shadowalpha']),
                 INITIAL_OPACITY=str(data['initial']['shadowopacity']),
                 INITIAL_BARS=str(data['initial']['colorbars']))
    code = Path(__file__).with_name('modern_lifebar_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved lifebar contract input')
    return code


def type_none_program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    initialization = function(core, 'ent_default_init')
    cases = re.findall(r'(?ms)^[ \t]*case TYPE_NONE:.*?(?=^[ \t]*case TYPE_PANEL:)',
                       initialization)
    if len(cases) != 1 or cases[0].count('break;') != 1:
        raise ValueError('Expected the complete native TYPE_NONE switch case')
    inputs = []
    for case in data['cases']:
        inputs.append('{' + json.dumps(case['command']) + ',' +
                      ','.join(str(case[key]) for key in data['case_fields']) + '}')
    parts = dict(TYPE_FUNCTION=function(core, 'lcmHandleCommandType'),
                 ENTITY_CASE=cases[0], CASES=',\n'.join(inputs),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    code = Path(__file__).with_name('modern_type_none_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved type-default contract input')
    return code


class ModernLoadingContracts(unittest.TestCase):
    def test_lifebar_commands_fallback_defaults_and_diagnostics(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        for row in data['sources']:
            self.assertEqual(len(data['contracts'][row['contract']]), len(data['cases']))
        actual = json.loads(native_output(lifebar_program(data), data))
        expected = dict(status='PASS', profiles=[
            dict(revision=row['revision'], cases=data['contracts'][row['contract']])
            for row in data['sources']])
        self.assertEqual(actual, expected)

    def test_type_none_defaults_and_intervening_script_writes(self):
        data = load_contract_fixture(FIXTURE.with_name('modern-type-none-contracts.json'))
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        actual = json.loads(native_output(type_none_program(data), data))
        expected = dict(status='PASS', profiles=[
            dict(revision=row['revision'], cases=data['contracts'][row['contract']])
            for row in data['sources']])
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
