"""Check historical palette API values, availability and bounded byte access.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_early_jump_walkoff import braced_statement, continued_macro
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-palette-api-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    source = (engine / 'source/openborscript/drawmethod.c').read_text()
    index = (engine / 'source/openborscript/index.c').read_text()
    constants = (engine / 'source/openborscript/constants.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    names = function(index, 'Script_GetFunctionName')
    others = set(re.findall(r'\(\s*\(\s*void\s*\*\s*\)\s*(\w+)\s*\)', names)) - set(data['callbacks'])
    providers = {n: 'fixture_other_' + str(i) for i, n in enumerate(sorted(others))}
    names = rename_identifiers(names, providers)
    registry = function(index, 'Script_LoadSystemFunctions')
    selected = []
    for anchor in re.findall(r'if\(obor_profile_build >= \d+\)', registry):
        block = braced_statement(registry, anchor)
        if any(re.search(r'\b' + name + r'\b', block) for name in data['callbacks']):
            selected.append(block)
    if len(selected) != 3:
        raise ValueError('Expected complete palette registration boundaries')
    chain = [line for line in function(constants, 'mapstrings_transconst').splitlines()
             if re.fullmatch(r'\s*ICMPCONST_SINCE\(COLOR_COMPONENT_\w+,\s*\d+\)\s*', line)]
    if len(chain) != len(data['constant_queries']):
        raise ValueError('Expected complete color-component constant inventory')
    pixel = (engine / 'source/gamelib/pixelformat.c').read_text()
    pixelbytes = re.findall(r'(?m)^int pixelbytes[^;]+;', pixel)
    if len(pixelbytes) != 1:
        raise ValueError('Native palette allocation pixel sizes required')
    api = '\n'.join(function(source, name) for name in data['callbacks'])
    api = rename_identifiers(api, {'malloc': 'fixture_allocate'})
    parts = dict(
        API=api, PIXEL_BYTES=pixelbytes[0],
        VARIANTS='\n'.join(function(variants, n) for n in ('ScriptVariant_Clear', 'ScriptVariant_ChangeType')),
        PROVIDERS='\n'.join('static void %s(void) { marker=%d; }' % (name, i + 10)
                            for i, name in enumerate(providers.values())),
        GETNAME=names,
        GLOBAL_QUERIES=','.join('(void *)' + providers[name] for name in
                                ('openbor_get_global_config_property', 'openbor_set_global_config_property')),
        REGISTER=rename_identifiers('\n'.join(selected), {'List_InsertAfter': 'fixture_register', 'theFunctionList': 'fixture_list'}),
        CONSTANT_HELPER=function(constants, 'obor_profile_property_constant'),
        CONSTANT_MACRO=continued_macro(constants, 'ICMPCONST_SINCE'),
        CONSTANT_CHAIN='\n'.join(chain),
        QUERIES=','.join(json.dumps(n) for n in data['constant_queries']),
        CALLBACKS=','.join('(void *)' + n for n in data['callbacks']),
        PROFILES=','.join(str(s['revision']) + 'u' for s in data['sources']),
        CASES=','.join('{' + ','.join(str(v) for v in row) + '}' for row in data['cases']))
    code = Path(__file__).with_name('modern_palette_api_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved palette API contract input')
    return code


class ModernPaletteAPIContracts(unittest.TestCase):
    def test_names_constants_byte_access_copy_and_loading_wrapper(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [s['revision'] for s in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=s['revision'], **data['contracts'][s['contract']])
                                               for s in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
