"""Check native script references to frame records and collision collections.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_frame_collisions import METHODS
from test_historical_player import function, switch_cases

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / 'fixtures/profile-collision-frame-handle-contracts.json'


def selected_property(source, name, properties):
    code, cases = switch_cases(source, name, 'property')
    start = min(case['label_start'] for case in cases.values())
    return (code[:start] + ''.join('case ' + prop + ':' + cases[prop]['body'] for prop in properties)
            + code[cases['default']['label_start']:])


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text(encoding='latin1')
    script = (engine / 'openborscript.c').read_text(encoding='latin1')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin1')
    readers = [function(variant, name) for name in
               ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')]
    if 'obor_native_animation_property(' in script:
        readers.extend(function(script, name) for name in
                       ('obor_uses_early_animation_properties', 'obor_native_animation_property'))
    readers.append(selected_property(script, 'openbor_get_animation_property',
                                     ('ANI_PROP_ATTACK', 'ANI_PROP_BODY_COLLISION')))
    readers.extend(function(script, name) for name in (
        'obor_body_collision_frame_is_valid', 'openbor_get_attack_collection',
        'openbor_get_attack_instance', 'openbor_get_body_collision_collection', 'openbor_get_body_collision_instance',
    ))
    for action in ('get', 'set'):
        readers.append(selected_property(script, f'openbor_{action}_attack_property', ('ATTACK_PROP_TAG',)))
        readers.append(selected_property(script, f'openbor_{action}_body_collision_property',
                                         ('BODY_COLLISION_PROP_TAG',)))
    header = (HERE / 'frame_collision_construction_contract.c.in').read_text().split('@FUNCTIONS@')[0]
    template = (HERE / 'collision_frame_handle_contract.c.in').read_text()
    values = {'READERS': '\n'.join(readers),
              'REVISIONS': ','.join(str(row['revision']) for row in data['sources'])}
    return (header + '\n'.join(function(core, name) for name in METHODS) + '\n'
            + re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template))


class CollisionFrameHandleTests(unittest.TestCase):
    def test_original_frame_and_collection_routes(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        expected = [[row['revision'], *data['contracts'][row['contract']]] for row in data['sources']]
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
