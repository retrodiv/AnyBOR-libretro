"""Check ordered native function registration and reverse names per profile.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-script-registry-contracts.json'
MODULE_FIXTURE = FIXTURE.with_name('profile-4432-script-module-registry.json')
SETTER_NAMES = {'openbor_changesystemvariant': 'openbor_setsystemvariant'}


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
    return registry_program(data, symbols, methods), symbols


def registry_program(data, symbols, methods, mapping=False):
    parts = dict(STUBS='\n'.join('static void ' + name + '(void){}' for name in symbols),
                 POINTERS=','.join('(void*)' + name for name in symbols),
                 SYMBOLS=','.join(json.dumps(name) for name in symbols),
                 METHODS=('#define CHECK_REGISTRY_MAPPERS\n' if mapping else '') + methods,
                 PROFILES=','.join(str(row['revision'])+'u' for row in data['sources']))
    text = Path(__file__).with_name('script_registry_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved registry dependency')
    return text


def table_identity(rows):
    ordered = sorted(rows, key=lambda row: row[0])
    raw = json.dumps(ordered, separators=(',', ':')).encode()
    return {'entries': len(ordered), 'sha256': hashlib.sha256(raw).hexdigest()}


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

    def test_4432_registry_after_script_module_split(self):
        data = load_contract_fixture(MODULE_FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openborscript.c').read_text()
        methods = '\n'.join(function(source, name) for name in (
            'obor_has_computed_damage', 'Script_GetFunctionName', 'Script_GetStringMapFunction',
            'Script_LoadSystemFunctions'))
        symbols = sorted(set(re.findall(r'\b(?:openbor|mapstrings|math|system)_\w+\b', methods)))
        self.assertLessEqual(len(symbols), 512)
        code = registry_program(data, symbols, methods, mapping=True)
        results = [json.loads(line) for line in native_output(code, data, engine_source=engine).splitlines()]
        self.assertEqual([result['revision'] for result in results], revisions)
        for row, result in zip(data['sources'], results, strict=True):
            with self.subTest(profile=row['revision']):
                self.assertEqual(result['unknown'], '<unknown function>')
                self.assertEqual(len({name for _, name in result['register']}), len(result['register']))
                registered = [[SETTER_NAMES.get(symbol, symbol), name]
                              for symbol, name in result['register']]
                reverse = [[SETTER_NAMES.get(symbol, symbol), name]
                           for symbol, name in zip(symbols, result['reverse'], strict=True)
                           if name != result['unknown']]
                mappers = [[SETTER_NAMES.get(symbol, symbol), name]
                           for symbol, name in zip(symbols, result['mappers'], strict=True) if name]
                self.assertEqual({
                    'register': table_identity(registered),
                    'reverse': table_identity(reverse),
                    'mappers': table_identity(mappers),
                }, row['tables'])


if __name__ == '__main__':
    unittest.main()
