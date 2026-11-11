"""Keep native pickup navigation results with defined absent-object handling.

Complete helpers and real records run with the native distance function and
an observing animation callback. This does not authenticate arbitrary handles
or validate the complete animation/lifetime implementation.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture
from test_historical_player import function, rename_identifiers
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))
FIXTURE = HERE / 'fixtures/pickup-native-baseline.json'


def program(engine, profiles, *, reject_alias=False):
    core = (engine / 'openbor.c').read_text(encoding='latin1')
    oracle = load_contract_fixture(FIXTURE)
    helper = function(core, 'common_try_pick')
    guard = 'if(!self || !other) return 0;'
    if helper.count(guard) != 1:
        raise ValueError('One native pickup presence guard required')
    if reject_alias:
        helper = helper.replace(guard, 'if(!self || !other || self == other) return 0;', 1)
    structured = 'self->position.x' in helper
    vector_speed = 'self->modeldata.speed.x' in helper
    has_dest = 'self->destx' in helper
    own = oracle['engines'][engine.name]
    distance = function(core, 'diff')
    # Only pickup presence is changed; the native distance routine is exact.
    if re.sub(r'\s+', '', distance) != re.sub(r'\s+', '', own['diff']):
        raise ValueError('Unexpected native distance change')
    contexts = []
    for p in profiles:
        row = oracle['profiles'][p['build']]
        contexts.append('{%du,%d}' % (row['revision'], row['has_destination']))
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        X='position.x' if structured else 'x', Z='position.z' if structured else 'z',
        VX='velocity.x' if structured else 'xdir', VZ='velocity.z' if structured else 'zdir',
        SPEED='modeldata.speed.x' if vector_speed else 'modeldata.speed',
        NO_MOVE='modeldata.move_config_flags' if vector_speed else 'modeldata.nomove',
        NO_MOVE_VALUE='MOVE_CONFIG_NO_MOVE' if vector_speed else '1',
        HAS_DEST=str(int(has_dest)), HELPER=helper, DISTANCE=distance,
        ORIGINAL=rename_identifiers(own['helper'], {'common_try_pick': 'original_pick'}),
        CONTEXTS=','.join(contexts))
    text = (HERE / 'pickup_inputs.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved pickup fixture input')
    return text


class PickupInputTests(unittest.TestCase):
    def test_native_movement_and_missing_objects_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        oracle = load_contract_fixture(FIXTURE)
        self.assertEqual(set(oracle['profiles']), {p['build'] for p in pin['profiles']})
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == engine.name]
            with self.subTest(engine=engine.name):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout), {
                    'status': 'PASS', 'profiles': len(profiles), 'cases': 134 * len(profiles)})

    def test_alias_is_a_valid_object_pair(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        row = pin['engines'][0]
        engine = ROOT / 'src/engines' / row['build']
        profile = next(p for p in pin['profiles'] if p['engine'] == engine.name)
        result = run_native(engine, '#define ALIAS_ONLY 1\n' + program(engine, [profile], reject_alias=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('actual.returned == expected.returned', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
