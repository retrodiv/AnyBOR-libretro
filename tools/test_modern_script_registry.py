"""Check complete native script registration, reverse names and string maps.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-script-registry-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    source = (engine / 'source/openborscript/index.c').read_text()
    methods = '\n'.join(function(source, name) for name in
        ('Script_GetFunctionName', 'Script_GetStringMapFunction', 'Script_LoadSystemFunctions'))
    symbols = data['symbols']
    if (not 8 <= len(symbols) <= 512 or len(symbols) != len(set(symbols)) or
            any(not re.fullmatch(r'[A-Za-z_]\w*', name) for name in symbols) or
            set(re.findall(r'\(void\s*\*\)\s*(\w+)', methods)) - set(symbols)):
        raise ValueError('Complete bounded registry symbol inventory required')
    parts = dict(STUBS='\n'.join('static void ' + name + '(void){}' for name in symbols),
        POINTERS=','.join('(void*)' + name for name in symbols),
        SYMBOLS=','.join(json.dumps(name) for name in symbols), METHODS=methods,
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    code = Path(__file__).with_name('modern_script_registry_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved registry contract input')
    return code


class ModernScriptRegistryContracts(unittest.TestCase):
    def test_complete_registration_reverse_names_and_string_maps(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({s['revision'] for s in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[
            dict(revision=s['revision'], **data['contracts'][s['contract']]) for s in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
