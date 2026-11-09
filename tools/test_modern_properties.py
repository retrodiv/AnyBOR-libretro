"""Check profile-owned property constants, numeric maps and script access.

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


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-property-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    constants = (engine / 'source/openborscript/constants.c').read_text()
    mapper = function(constants, 'mapstrings_transconst')
    selected = [line for line in mapper.splitlines() if re.fullmatch(
        r'\s*ICMPCONST(?:_SINCE)?\((?:ENTITY|MODEL)_PROPERTY_\w+(?:,\s*\d+)?\)\s*', line)]
    if len(selected) < 100:
        raise ValueError('Expected the complete entity/model constant registration chains')
    helpers = [function(constants, 'obor_profile_property_constant')]
    maps, entries = [], []
    for family in ('entity', 'model'):
        source = (engine / 'source/openborscript' / (family + '.c')).read_text()
        helpers.append(function(source, 'obor_profile_' + family + '_property_end'))
        maps.append(function(source, family + '_get_property_map'))
        entries.extend(function(source, 'openbor_' + op + '_' + family + '_property')
                       for op in ('get', 'set'))
    addresses = []
    switches = []
    for index, row in enumerate(data['sources']):
        contract = data['contracts'][row['contract']]
        for family, object_name in [('entity', 'actor'), ('model', 'model')]:
            values = []
            for field in contract['field_refs'][family]:
                if not re.fullmatch(r'&acting_object->[A-Za-z0-9_.\[\]]+', field):
                    raise ValueError('Expected one source-owned property field reference')
                # The physical model retains the older unsigned structs too.
                if family == 'model' and field == '&acting_object->guardpoints':
                    field = '&acting_object->profile_guardpoints'
                values.append(field.replace('acting_object->', object_name + '.'))
            addresses.append('static const void *const ' + family + '_fields_' + str(index) +
                             '[] = {' + ','.join(values) + '};')
        switches.append('case ' + str(index) + ': return family ? model_fields_' + str(index) +
                        '[index] : entity_fields_' + str(index) + '[index];')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    common = (engine / 'source/openborscript/common_property.c').read_text()
    parts = dict(HELPERS='\n'.join(helpers), MAPS='\n'.join(maps), ENTRIES='\n'.join(entries),
                 VARIANTS='\n'.join(function(variant, name) for name in
                                    ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
                                     'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
                 COMMON='\n'.join(function(common, name) for name in
                                  ('property_access_get_member', 'property_access_set_member')),
                 MACROS='\n'.join(continued_macro(constants, name) for name in
                                  ('ICMPCONST', 'ICMPCONST_SINCE')),
                 CONSTANT_CHAIN='\n'.join(selected), ADDRESSES='\n'.join(addresses),
                 ADDRESS_SWITCH='\n'.join(switches),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
                 DIRECT_INDICES=',\n'.join('{' + ','.join(str(value) for value in
                     data['contracts'][row['contract']]['value_indices']) + '}'
                     for row in data['sources']),
                 CONSTANT_QUERIES=','.join(json.dumps(name) for name in data['constant_queries']),
                 VALUE_QUERIES=','.join('{' + str(row['family']) + ',' + json.dumps(row['name']) + '}'
                                        for row in data['value_queries']))
    code = Path(__file__).with_name('modern_property_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved property contract input')
    return code


class ModernPropertyContracts(unittest.TestCase):
    def test_original_constants_numeric_maps_fields_and_script_boundaries(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[
            dict(revision=row['revision'], **{key: value for key, value in
                 data['contracts'][row['contract']].items()
                 if key not in ('field_refs', 'value_indices')})
            for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
