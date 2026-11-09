"""Check profile-specific flash property access and registration.

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
from test_historical_player import function


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-flash-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    source = (engine / 'source/openborscript/flash.c').read_text()
    common = (engine / 'source/openborscript/common_property.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    constants = (engine / 'source/openborscript/constants.c').read_text()
    index = (engine / 'source/openborscript/index.c').read_text()
    chain = [line for line in function(constants, 'mapstrings_transconst').splitlines()
             if re.fullmatch(r'\s*ICMPCONST_SINCE\(FLASH_PROPERTY_\w+,\s*\d+\)\s*', line)]
    if len(chain) != 5:
        raise ValueError('Expected five source-owned flash constant registrations')
    registry = function(index, 'Script_LoadSystemFunctions')
    registration = re.findall(r'if\(obor_profile_build >= 7557\)\s*\{[^}]+\}', registry)
    if len(registration) != 1 or registration[0].count('List_InsertAfter') != 2:
        raise ValueError('Expected complete flash registration boundary')
    names = re.findall(
        r'else if\s*\((?:obor_profile_build >= 7557 && )?functionRef == \(\(void\*\)openbor_(?:get|set)_flash_property\)\)\s*\{[^}]+\}',
        function(index, 'Script_GetFunctionName'))
    if len(names) != 2:
        raise ValueError('Expected two source-owned flash function names')
    parts = dict(
        VARIANTS='\n'.join(function(variants, name) for name in
                            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
                             'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        COMMON='\n'.join(function(common, name) for name in
                          ('property_access_get_member', 'property_access_set_member')),
        ENTRIES='\n'.join(function(source, name) for name in
                           ('obor_profile_flash_property_end', 'flash_get_property_map',
                            'openbor_get_flash_property', 'openbor_set_flash_property')),
        REGISTRATION=registration[0], NAMES='\n'.join(names),
        CONSTANT_HELPER=function(constants, 'obor_profile_property_constant'),
        MACRO=continued_macro(constants, 'ICMPCONST_SINCE'), CONSTANT_CHAIN='\n'.join(chain),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CONSTANT_QUERIES=','.join(json.dumps(n) for n in data['constant_queries']),
        CASES=',\n'.join('{' + ','.join(str(v) for v in row) + '}' for row in data['cases']))
    code = Path(__file__).with_name('modern_flash_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved flash contract input')
    return code


class ModernFlashContracts(unittest.TestCase):
    def test_property_values_classes_constants_and_availability(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[
            dict(revision=row['revision'], **data['contracts'][row['contract']])
            for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
