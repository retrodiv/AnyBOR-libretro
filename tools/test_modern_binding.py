"""Check historical binding APIs with allocated and embedded engine records.

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


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-binding-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    binding = (engine / 'source/openborscript/binding.c').read_text()
    core = (engine / 'openbor.c').read_text()
    initialize = function(core, 'ent_default_init')
    anchor = '    switch(e->modeldata.type)'
    if initialize.count(anchor) != 1:
        raise ValueError('Expected one entity initialization switch')
    initialize = initialize[:initialize.index(anchor)] + '}\n'
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    common = (engine / 'source/openborscript/common_property.c').read_text()
    parts = dict(HELPERS='\n'.join(function(binding, name) for name in
                                  ('obor_profile_bind_get_property_map',
                                   'obor_profile_get_bind_property',
                                   'obor_profile_set_bind_property')),
                 ENTRIES='\n'.join(function(binding, name) for name in
                                   ('openbor_get_bind_property', 'openbor_set_bind_property',
                                    'openbor_update_bind')),
                 VARIANTS='\n'.join(function(variants, name) for name in
                                    ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
                                     'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
                 COMMON='\n'.join(function(common, name) for name in
                                  ('property_access_get_member', 'property_access_set_member')),
                 ALLOCATE=function(core, 'bind_allocate_object'), INITIALIZE=initialize,
                 PROFILES=','.join('{' + str(row['revision']) + 'u,' +
                                   str(row['signed_points']) + '}' for row in data['sources']),
                 CASES=',\n'.join('{' + ','.join(str(case[field]) for field in
                     data['case_fields']) + '}' for case in data['cases']))
    code = Path(__file__).with_name('modern_binding_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved binding contract input')
    return code


class ModernBindingContracts(unittest.TestCase):
    def test_binding_values_producers_admission_returns_and_argument_limits(self):
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
