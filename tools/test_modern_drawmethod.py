"""Check source-defined drawing property APIs and copy boundaries.

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
from test_historical_player import function, rename_identifiers


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-drawmethod-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    port = Path(os.environ.get('OBOR_TEST_PORT', ROOT / 'src/port/libretro'))
    source = (engine / 'source/openborscript/drawmethod.c').read_text()
    core = (engine / 'openbor.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    common = (engine / 'source/openborscript/common_property.c').read_text()
    match = re.search(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{', core)
    if match is None:
        raise ValueError('Source-owned default drawing record required')
    default = core[match.start():core.index('\n};', match.end()) + 3]
    fields, seeds = [], []
    for row in data['fields']:
        name, kind, seed = row
        if (not re.fullmatch(r'[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*', name) or
                kind not in ('WORD', 'BYTE', 'FLOAT', 'POINTER')):
            raise ValueError('Bounded typed drawing member required')
        fields.append('{offsetof(s_drawmethod,%s),sizeof(((s_drawmethod*)0)->%s),%s}' %
                      (name, name, 'FIXTURE_' + kind))
        seeds.append('actor.%s=%s;' % (name, '&token_a' if kind == 'POINTER' else str(seed)))
    parts = dict(
        DEFAULT=default, FIELDS=','.join(fields), SEED='\n'.join(seeds),
        PROFILES=','.join('{%du,%d,%d}' % (row['revision'], row['table_property'], row['modern_api'])
                          for row in data['sources']),
        VARIANTS='\n'.join(function(variant, n) for n in ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
                                                       'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        COMMON='\n'.join(function(common, n) for n in ('property_access_get_member', 'property_access_set_member')),
        MAP=function(source, 'obor_profile_drawmethod_get_property_map'),
        ADAPTER=(port / 'obor_drawmethod_member.inc').read_text(),
        API='\n'.join(function(source, n) for n in (
            'obor_profile_get_drawmethod_property', 'obor_profile_set_drawmethod_property',
            'obor_profile_copy_drawmethod', 'openbor_get_drawmethod_property',
            'openbor_set_drawmethod_property', 'openbor_copy_drawmethod', 'openbor_allocate_drawmethod')),
        CONSTRUCTOR=rename_identifiers(function(core, 'allocate_drawmethod'), {'malloc': 'fixture_allocate'}))
    code = Path(__file__).with_name('modern_drawmethod_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved drawing API contract input')
    return code


class ModernDrawmethodContracts(unittest.TestCase):
    def test_values_typed_members_copy_order_and_argument_limits(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            **data['contracts'][row['contract']], copies=data['copies'][row['copy_contract']])
            for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
