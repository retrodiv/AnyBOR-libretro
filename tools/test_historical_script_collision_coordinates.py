"""Compare native script reads and writes of attack and body coordinates.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_entity_namespace import declaration
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-script-collision-coordinate-contracts.json'
ATTACK_PROPERTIES = (
    'ATTACK_PROP_POSITION_X', 'ATTACK_PROP_POSITION_Y', 'ATTACK_PROP_SIZE_X',
    'ATTACK_PROP_SIZE_Y', 'ATTACK_PROP_SIZE_Z_1', 'ATTACK_PROP_SIZE_Z_2',
)
BODY_PROPERTIES = (
    'BODY_COLLISION_PROP_POSITION_X', 'BODY_COLLISION_PROP_POSISTION_Y', 'BODY_COLLISION_PROP_SIZE_X',
    'BODY_COLLISION_PROP_SIZE_Y', 'BODY_COLLISION_PROP_SIZE_Z_1', 'BODY_COLLISION_PROP_SIZE_Z_2',
)
METHODS = (
    ('openbor_get_attack_property', ATTACK_PROPERTIES),
    ('openbor_set_attack_property', ATTACK_PROPERTIES),
    ('openbor_get_body_collision_property', BODY_PROPERTIES),
    ('openbor_set_body_collision_property', BODY_PROPERTIES),
)
VARIANTS = ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')


def coordinate_dispatch(source, name, properties):
    method, cases = switch_cases(source, name, 'property')
    prefix = method[:min(case['label_start'] for case in cases.values())]
    body = ''.join('case ' + prop + ':' + cases[prop]['body'] for prop in properties)
    return prefix + body + method[cases['default']['label_start']:]


def source_parts(engine):
    script = (engine / 'openborscript.c').read_text(encoding='latin1')
    header = (engine / 'openbor.h').read_text(encoding='latin1')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin1')
    parts = {name: coordinate_dispatch(script, name, properties) for name, properties in METHODS}
    parts.update((name, function(variant, name)) for name in VARIANTS)
    for kind, name in (('struct', 's_hitbox'), ('enum', 'e_attack_properties'),
                       ('enum', 'e_body_collision_properties')):
        parts[name] = declaration(header, rf'typedef\s+{kind}[^{{;]*\{{[^{{}}]*\}}\s+{name};')
    parts['helper'] = function(script, 'obor_script_collision_coordinates')
    return parts


def program(data, original=None, *, separate_coordinates=True):
    engine = ROOT / 'src/engines' / data['engine']
    parts = source_parts(engine) if original is None else original
    values = {
        'COORDINATES': parts['s_hitbox'],
        'ENUMS': '\n'.join(parts[name] for name in ('e_attack_properties', 'e_body_collision_properties')),
        'COORDINATE_FIELD': 's_hitbox *' if separate_coordinates else 's_hitbox',
        'VARIANTS': '\n'.join(parts[name] for name in VARIANTS),
        'HELPERS': parts.get('helper', ''),
        'METHODS': '\n'.join(parts[name] for name, _ in METHODS),
        'ATTACK_PROPERTIES': ', '.join(ATTACK_PROPERTIES),
        'BODY_PROPERTIES': ', '.join(BODY_PROPERTIES),
        'ASSIGN_BOX': '(inputs[input].backed ? &box : NULL)' if separate_coordinates else 'box',
        'ASSIGN_PEER': '&peer_box' if separate_coordinates else 'peer_box',
        'SELECT_BOX': '&box' if separate_coordinates else '(family ? &body.coords : &attack.coords)',
        'SELECT_PEER': 'peer.coords' if separate_coordinates else '&peer.coords',
        'CASES': ',\n'.join('{%s, %.17g, %d}' % (row['type'], row['value'], row['backed'])
                            for row in data['cases']),
        'CHECKS': '\n'.join(
            f'    obor_profile_build = {row["revision"]};\n'
            '    for(unsigned int family = 0; family < 2; ++family)\n'
            '        for(unsigned int coord = 0; coord < 6; ++coord)\n'
            '            for(unsigned int i = 0; i < sizeof(inputs) / sizeof(inputs[0]); ++i)\n'
            '                observe(family, coord, i);'
            for row in data['sources']),
    }
    template = Path(__file__).with_name('script_collision_coordinate_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


class CollisionCoordinateContracts(unittest.TestCase):
    def test_native_coordinate_getters_and_setters(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        expected = [[row['revision'], *outcome] for row in data['sources']
                    for outcome in data['contracts'][row['contract']]]
        self.assertEqual(len(actual), len(expected))
        for result, reference in zip(actual, expected):
            with self.subTest(revision=reference[0], family=reference[1], axis=reference[2], case=reference[3]):
                self.assertEqual(result, reference)

    def test_checked_coordinate_backing(self):
        data = load_contract_fixture(FIXTURE)
        control = data['checked_backing']
        case = data['cases'][control['input']]
        sample = data | {'sources': [{'revision': control['revision']}], 'cases': [case | {'backed': 0}]}
        actual = [json.loads(line) for line in native_output(program(sample), data).splitlines()]
        expected = [[control['revision'], *row[:2], 0, *row[3:]]
                    for row in data['contracts'][control['reference_contract']] if row[2] == control['input']]
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
