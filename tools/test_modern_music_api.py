"""Check music channel properties, registrations and class lifetime.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-music-api-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    source = (engine / 'source/openborscript/audio.c').read_text()
    common = (engine / 'source/openborscript/common_property.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    constants = (engine / 'source/openborscript/constants.c').read_text()
    index = (engine / 'source/openborscript/index.c').read_text()
    mixer = (engine / 'source/gamelib/soundmix.c').read_text()
    chain = [line for line in function(constants, 'mapstrings_transconst').splitlines()
             if re.fullmatch(r'\s*ICMPCONST_SINCE\((?:CHANNEL_TYPE|MUSIC_CHANNEL_PROPERTY|SOUND_FILE_TYPE|SOUND_SPATIAL_CHANNEL)_\w+,\s*\d+\)\s*', line)]
    registration = re.findall(r'if\(obor_profile_build >= 7590\)\s*\{[^}]+\}',
                              function(index, 'Script_LoadSystemFunctions'))
    names = re.findall(r'else if \(obor_profile_build >= 7590 && functionRef == \(\(void\*\)openbor_(?:get|set)_music_channel_property\)\)\s*\{[^}]+\}',
                       function(index, 'Script_GetFunctionName'))
    if len(chain) != 19 or len(registration) != 1 or registration[0].count('List_InsertAfter') != 2 or len(names) != 2:
        raise ValueError('Complete music/audio constant, name and registration blocks required')
    parts = dict(VARIANTS='\n'.join(function(variant, name) for name in (
            'ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        COMMON='\n'.join(function(common, name) for name in ('property_access_get_member', 'property_access_set_member')),
        ENTRIES=source, CLEAR=function(mixer, 'sound_music_channel_clear'),
        REGISTRATION=registration[0], NAMES='\n'.join(names),
        CONSTANT_HELPER=function(constants, 'obor_profile_property_constant'),
        MACRO=continued_macro(constants, 'ICMPCONST_SINCE'), CONSTANT_CHAIN='\n'.join(chain),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CONSTANT_QUERIES=','.join(json.dumps(v) for v in data['constant_queries']),
        CASES=','.join('{' + ','.join(str(v) for v in row) + '}' for row in data['cases']))
    code = Path(__file__).with_name('modern_music_api_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved music API contract input')
    return code


class ModernMusicApiContracts(unittest.TestCase):
    def test_properties_constants_registry_and_clear(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            **data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
