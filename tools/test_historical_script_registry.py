"""Check ordered native function registration and reverse names per profile.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-script-registry-contracts.json'


def program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openborscript.c').read_text()
    symbols = sorted({row['symbol'] for value in data['contracts'].values()
                      for kind in ('register', 'reverse') for row in value[kind]})
    if not 8 <= len(symbols) <= 512 or any(not re.fullmatch(r'[A-Za-z_]\w*', name)
                                          for name in symbols):
        raise ValueError('Bounded native symbol inventory required')
    for value in data['contracts'].values():
        for kind in ('register', 'reverse'):
            rows = value[kind]
            if len(rows) > len(symbols) or any(not re.fullmatch(r'[A-Za-z_]\w*', row['name'])
                                              for row in rows):
                raise ValueError('Bounded native registry names required')
    methods = '\n'.join(function(source, name) for name in
                         ('obor_script_function_available', 'Script_GetFunctionName',
                          'Script_LoadSystemFunctions'))
    referenced = set(re.findall(r'\(void\*\)\s*(\w+)', methods))
    if referenced - set(symbols):
        raise ValueError('Native registry has unreviewed symbols')
    parts = dict(STUBS='\n'.join('static void ' + name + '(void){}' for name in symbols),
                 POINTERS=','.join('(void*)' + name for name in symbols),
                 SYMBOLS=','.join(json.dumps(name) for name in symbols),
                 METHODS=methods,
                 PROFILES=','.join(str(row['revision'])+'u' for row in data['sources']))
    text = Path(__file__).with_name('script_registry_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved registry dependency')
    return text, symbols


class ScriptRegistryContracts(unittest.TestCase):
    def test_ordered_registry_and_reverse_names(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len({row['revision'] for row in data['sources']}), len(data['sources']))
        code, symbols = program(data)
        actual = [json.loads(line) for line in native_output(code, data).splitlines()]
        self.assertEqual(len(actual), len(data['sources']))
        for result, row in zip(actual, data['sources']):
            contract = data['contracts'][row['contract']]
            reverse = {item['symbol']: item['name'] for item in reversed(contract['reverse'])}
            with self.subTest(profile=row['revision']):
                self.assertEqual(result, dict(revision=row['revision'],
                    register=[[item['symbol'], item['name']] for item in contract['register']],
                    reverse=[reverse.get(name, contract['unknown']) for name in symbols],
                    unknown=contract['unknown']))


if __name__ == '__main__':
    unittest.main()
