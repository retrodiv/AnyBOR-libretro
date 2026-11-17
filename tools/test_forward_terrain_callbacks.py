"""Execute complete native terrain callbacks and movement callers.

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
from test_historical_player import function, switch_cases
from test_early_jump_walkoff import braced_statement

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-terrain-callbacks-contracts.json'


def program(data, engine):
    core = (engine / 'openbor.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    loader, cases = switch_cases(core, 'load_level', 'cmd', outermost=True)
    values = dict(FUNCTIONS='\n'.join(function(core, name) for name in data['functions']),
        CONTEXTS=','.join('{%du,%d,%d,%d,%d}' % (row['revision'], row['platform'],
                          row['wall_index'], row['hole'], row['base_event']) for row in data['sources']),
        LOAD_CASE=cases['CMD_LEVEL_HOLE']['body'],
        EXIT_HOLE=braced_statement(loader, 'if(exit_hole)'),
        PARSER='#pragma GCC diagnostic push\n#pragma GCC diagnostic ignored "-Wimplicit-fallthrough"\n' +
            function(core, 'ParseArgs') + '#pragma GCC diagnostic pop\n' +
            '\n'.join(function(core, name) for name in ('isNumeric','getValidFloat')),
        HOLE_VALUES=','.join('{%s,%sf,%d}' % (json.dumps(row['text']),
            float(row['value']).hex(), row['warning']) for row in data['hole_values']),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Init','ScriptVariant_Clear','ScriptVariant_ChangeType','ScriptVariant_Copy')))
    code = Path(__file__).with_name('forward_terrain_callbacks_contract.c.in').read_text()
    for key, value in values.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved native terrain callback input')
    return code


class ForwardTerrainCallbackTests(unittest.TestCase):
    def test_native_locals_cleanup_axis_events_and_height_movement(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_TERRAIN_CALLBACKS_ENGINE', ROOT / 'src/engines' / data['engine']))
        actual = [json.loads(line) for line in native_output(program(data, engine), data, engine_source=engine).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], status='PASS') for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
