"""Check historical global configuration values, names and constants.

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


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-global-config-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    source = (engine / 'source/openborscript/global_config.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    common = (engine / 'source/openborscript/common_property.c').read_text()
    constants = (engine / 'source/openborscript/constants.c').read_text()
    mapper = function(constants, 'mapstrings_transconst')
    chain = [line for line in mapper.splitlines() if re.fullmatch(
        r'\s*ICMPCONST_(?:SINCE|RANGE)\(GLOBAL_CONFIG_PROPERTY_\w+,\s*\d+(?:,\s*\d+)?\)\s*', line)]
    if len(chain) != 9:
        raise ValueError('Expected all nine global configuration constant registrations')
    core = (engine / 'openbor.c').read_text()
    initializer = core[core.index('s_global_config global_config ='):]
    initializer = initializer[:initializer.index('};') + 2]
    index = function((engine / 'source/openborscript/index.c').read_text(),
                     'Script_GetStringMapFunction')
    branches = re.findall(
        r'else if\s*\(functionRef == \(\(void\*\)openbor_(?:get|set)_global_config_property\)\)\s*\{[^}]+\}', index)
    if len(branches) != 2:
        raise ValueError('Expected two global configuration preconversion branches')
    parts = dict(
        INITIALIZER=initializer,
        HELPERS='\n'.join(function(source, name) for name in
                           ('obor_profile_global_config_property_end',
                            'obor_profile_global_config_get_property_map',
                            'obor_profile_get_global_config_property',
                            'obor_profile_set_global_config_property')),
        ENTRIES='\n'.join(function(source, name) for name in
                           ('mapstrings_global_config_property',
                            'openbor_get_global_config_property',
                            'openbor_set_global_config_property')),
        VARIANTS='\n'.join(function(variants, name) for name in
                            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
                             'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        COMMON='\n'.join(function(common, name) for name in
                          ('property_access_get_member', 'property_access_set_member')),
        SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
        PRECONVERSION='\n'.join(branches),
        CONSTANT_HELPER=function(constants, 'obor_profile_property_constant'),
        MACROS='\n'.join(continued_macro(constants, name) for name in
                          ('ICMPCONST_SINCE', 'ICMPCONST_RANGE')),
        CONSTANT_CHAIN='\n'.join(chain),
        CONSTANT_QUERIES=','.join(json.dumps(n) for n in data['constant_queries']),
        STRINGS=','.join(json.dumps(n) for n in data['strings']),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=',\n'.join('{' + ','.join(str(v) for v in row) + '}' for row in data['cases']))
    code = Path(__file__).with_name('modern_global_config_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved global configuration contract input')
    return code


class ModernGlobalConfigContracts(unittest.TestCase):
    def test_values_names_constants_tags_and_preconversion(self):
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
