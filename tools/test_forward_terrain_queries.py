"""Execute native geometry, terrain queries and targeted registry bindings.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-terrain-queries-contracts.json'


def program(data, engine):
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    owned = ['openbor_' + name for name in data['names']]
    if any(not re.fullmatch(r'openbor_[A-Za-z_]\w*', name) for name in owned):
        raise ValueError('Explicit native query names required')
    registry = '\n'.join(function(script, name) for name in
                         ('Script_GetFunctionName', 'Script_LoadSystemFunctions'))
    stubs = sorted(set(re.findall(r'\(void\s*\*\)\s*(\w+)', registry)) - set(owned))
    registry = rename_identifiers(registry, {name:'probe_symbol_'+name for name in stubs})
    rows = []
    for row in data['sources']:
        if (len(row['registry']) != len(owned) or
                any(value is not None and value not in owned for value in row['registry'])):
            raise ValueError('Complete independent native query bindings required')
        rows.append('{%du,%d,%d,%d,%d,%d,{%s}}' % (row['revision'], row['platform_api'],
            row['index_api'], row['height'], row['inclusive'], row['platform_pointer'],
            ','.join('(void*)'+name if name else 'NULL' for name in row['registry'])))
    values = dict(BACKENDS='\n'.join(function(core, name) for name in data['backend_functions']),
        WRAPPERS='\n'.join(function(script, name) for name in owned),
        REGISTRY=registry,
        STUBS='\n'.join('static void probe_symbol_%s(void){abort();}' % name for name in stubs),
        CONTEXTS=','.join(rows), NAMES=','.join(json.dumps(name) for name in data['names']),
        FUNCTIONS=','.join(owned),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Init','ScriptVariant_Clear','ScriptVariant_ChangeType',
             'ScriptVariant_IntegerValue','ScriptVariant_DecimalValue')))
    text = Path(__file__).with_name('forward_terrain_queries_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native terrain query input')
    return text


class ForwardTerrainQueryTests(unittest.TestCase):
    def test_native_geometry_query_defaults_arguments_and_registry_aliases(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_TERRAIN_QUERIES_ENGINE', ROOT / 'src/engines' / data['engine']))
        actual = [json.loads(line) for line in native_output(program(data, engine), data, engine_source=engine).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], status='PASS') for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
