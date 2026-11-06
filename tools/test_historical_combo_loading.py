"""Check native combo metadata, row retention and default insertion order.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import native_output, ROOT
from test_historical_player import function
from test_early_jump_walkoff import braced_statement

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-combo-loading-contracts.json'


def model_case(core, name):
    method = function(core, 'load_cached_model')
    # The loader also has a nested switch(cmd). Match only its direct labels.
    matches = list(re.finditer(r'(?ms)^\t{4}case CMD_MODEL_' + name +
        r':.*?(?=^\t{4}(?:case CMD_MODEL_|default:))', method))
    if len(matches) != 1:
        raise ValueError('One direct native model command required')
    return matches[0][0]


def program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    branch = model_case(core, 'ANIM')
    anchor = 'else if(strnicmp(value, "freespecial", 11)==0'
    branch = braced_statement(branch, anchor)
    # A standalone wrapper supplies an already selected animation-name branch.
    branch = branch.removeprefix('else ')
    loader = function(core, 'load_cached_model')
    start = loader.index('//temporary patch for conflicting moves')
    end = loader.index('\n\tif(newchar->risetime', start)
    initialize = function(core, 'init_model')
    first = initialize.index('\tnewchar->special ')
    allocate = initialize[first:initialize.index('\n\n', first)]
    cases = []
    for row in data['cases']:
        operations = []
        for command, args in row['operations']:
            if command not in (1, 2, 3) or len(args) > 31:
                raise ValueError('Bounded combo operation required')
            operations.append('{%d,{%s}}' % (command, ','.join(json.dumps(s) for s in args)))
        cases.append('{%d,%d,%d,{%s}}' % (row['conflicts'], row['seed'],
                     len(operations), ','.join(operations)))
    declaration = re.search(r'(?m)^static const char\* E_OUT_OF_MEMORY[^\n]+;', core)
    if declaration is None:
        raise ValueError('Native allocation diagnostic required')
    parts = dict(ERROR_DECL=declaration[0], FUNCTIONS='\n'.join(function(core, name) for name in
        ('alloc_specials', 'is_set', 'obor_combo_default')),
        COM=model_case(core, 'COM'), CANCEL=model_case(core, 'CANCEL'),
        ANIM=branch, DEFAULTS=loader[start:end], ALLOCATE=allocate,
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=',\n'.join(cases))
    text = Path(__file__).with_name('combo_loading_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native combo loading dependency')
    return text


class ComboLoadingContracts(unittest.TestCase):
    def test_native_commands_rows_and_default_order(self):
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
