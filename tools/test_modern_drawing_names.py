"""Check drawing constant names and string preconversion boundaries.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_early_jump_walkoff import continued_macro
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-drawing-name-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    constants = (engine / 'source/openborscript/constants.c').read_text()
    source = (engine / 'source/openborscript/drawmethod.c').read_text()
    index = function((engine / 'source/openborscript/index.c').read_text(), 'Script_GetStringMapFunction')
    retained = {'openbor_get_drawmethod_property', 'openbor_set_drawmethod_property', 'mapstrings_drawmethod'}
    others = set(re.findall(r'\b(?:openbor_|mapstrings_)\w+', index)) - retained
    providers = {name: 'fixture_other_' + str(i) for i, name in enumerate(sorted(others))}
    index = rename_identifiers(index, providers)
    chain = [line for line in function(constants, 'mapstrings_transconst').splitlines()
             if re.fullmatch(r'\s*ICMPCONST_(?:SINCE|PROFILE_VALUE)\(DRAWMETHOD_.*\)\s*', line)]
    if len(chain) != len(data['registered_constants']):
        raise ValueError('Drawing constant inventory changed')
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    parts = dict(
        VARIANTS='\n'.join(function(variants, name) for name in ('ScriptVariant_Clear', 'ScriptVariant_ChangeType')),
        SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
        MAPPER=function(source, 'mapstrings_drawmethod'), INDEX=index,
        OTHER_PROVIDERS='\n'.join('static void %s(void) { marker = %d; }' % (name, i + 10)
                                  for i, name in enumerate(providers.values())),
        CONSTANT_HELPER=function(constants, 'obor_profile_property_constant'),
        MACROS='\n'.join(continued_macro(constants, name) for name in ('ICMPCONST_SINCE', 'ICMPCONST_PROFILE_VALUE')),
        CONSTANT_CHAIN='\n'.join(chain),
        QUERIES=','.join(json.dumps(name) for name in data['constant_queries']),
        STRINGS=','.join(json.dumps(name) for name in data['strings']),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    code = Path(__file__).with_name('modern_drawing_names_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved drawing name contract input')
    return code


class ModernDrawingNameContracts(unittest.TestCase):
    def test_constants_and_public_mapper_callbacks(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'], **data['contracts'][row['contract']])
                                               for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
