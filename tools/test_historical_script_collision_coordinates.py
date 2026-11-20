"""Compare native script reads and writes of attack and body coordinates.

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
from test_historical_entity_namespace import declaration
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-script-collision-coordinate-contracts.json'
ATTACK_4905_FIXTURE = FIXTURE.with_name('profile-4432-attack-properties-4905.json')
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


def attack_property_mapping(script):
    if 'static LONG obor_attack_property_selector(' not in script:
        return ''
    return (declaration(script, r'^enum \{ OBOR_ATTACK_FALL_VELOCITY [^;]*;') + '\n' +
            function(script, 'obor_attack_property_selector'))


def body_property_mapping(script):
    if 'static LONG obor_body_property_selector(' not in script:
        return ''
    return (declaration(script, r'^enum \{ OBOR_BODY_COLLISION_COORDINATES [^;]*;') + '\n' +
            function(script, 'obor_body_property_selector'))


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
    parts['helper'] = (function(script, 'obor_script_collision_coordinates') +
                       attack_property_mapping(script) + body_property_mapping(script))
    return parts


def program(data, original=None, *, separate_coordinates=True):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
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
    def test_4432_attack_property_ordinals_and_combined_velocity(self):
        data = load_contract_fixture(ATTACK_4905_FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        script = (engine / 'openborscript.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        constants = function(script, 'mapstrings_transconst')
        constant_cases = constants[constants.index('        // Attack properties'):
                                   constants.index('        // Porting')]
        macros = script[script.index('#define ICMPCOLLISIONPROP('):script.index('#define ICMPSUBTYPE(')]
        controls = []
        rendered = []
        for row in rows:
            revision = row['revision']
            name = f'expected_{revision}'
            self.assertTrue(all(re.fullmatch(r'(?:ATTACK_PROP_\w+|OBOR_ATTACK_FALL_VELOCITY|-1)', token)
                                for token in row['selectors']))
            const_items = ',\n'.join('{%s,%d}' % (json.dumps(key), value)
                                     for key, value in row['constants'].items())
            slots = ','.join(row['selectors'])
            rendered.append(f'static const LONG {name}_slots[] = {{{slots}}};\n'
                            f'static const Constant {name}_constants[] = {{{const_items}}};')
            controls.append(f'    check_ordinals({revision}u, {name}_slots, COUNT({name}_slots));\n'
                            f'    check_constants({name}_constants, COUNT({name}_constants));')
        parts = {
            'CACHE': variant[variant.index('typedef struct'):variant.index('// find an existing constant')],
            'CONVERSIONS': '\n'.join(function(variant, name) for name in
                                     ('ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
            'METHODS': function(script, 'obor_script_collision_coordinates') +
                       attack_property_mapping(script) + '\n' + '\n'.join(function(script, name) for name in (
                           'openbor_get_attack_property', 'openbor_set_attack_property')),
            'CONSTANT_MACROS': macros,
            'CONSTANT_CASES': constant_cases,
            'TABLES': '\n'.join(rendered),
            'CHECKS': '\n'.join(controls),
            'NEW_REVISION': str(data['vector']['revision']),
            'VECTOR_ORDINAL': str(data['vector']['ordinal']),
            'RESERVED_ORDINAL': str(data['vector']['reserved_ordinal']),
            'OLD_REVISION': str(data['boundary_controls'][0]),
            'OLD_VELOCITY_Y': str(data['vector']['old_y_ordinal']),
        }
        template = Path(__file__).with_name('attack_properties_4905_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)
        raw = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual(raw.splitlines(), data['vector']['diagnostics'] + ['attack_properties_4905'])

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
