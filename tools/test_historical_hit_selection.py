"""Compare the collision selection and target-admission route of native attacks.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-hit-selection-contracts.json'
COORDS = ('x', 'y', 'width', 'height', 'z1', 'z2')
OPTIONS = (
    'attacker_z', 'target_z', 'attacker_direction', 'target_direction', 'counter_level',
    'opposing_level', 'slots', 'vulnerable', 'exists', 'dead', 'invincible', 'falling',
    'juggle', 'points', 'otg', 'grounded', 'same_id',
)


def attack_route(text):
    """Keep the native gates through the point that would invoke callbacks."""
    entry = text.index('temp = self;')
    prefix = text[:entry]
    without_literals = re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"', '', prefix)
    depth = without_literals.count('{') - without_literals.count('}')
    if depth not in (2, 3) or 'checkhit(' not in without_literals:
        raise ValueError('Incomplete native pre-callback route')
    return rename_identifiers(prefix, {'printf': 'ignored_diagnostic'}) + (
        '\n    (void)fdefense_blockthreshold; ++callbacks; selected = attack; force_out = force; return;\n'
        + '}\n' * depth + '#undef followed\n')


def source_parts(engine):
    text = (engine / 'openbor.c').read_text(encoding='latin1')
    return {
        'HIT': function(text, 'checkhit'),
        'CALLER': attack_route(function(text, 'do_attack')),
        'HELPERS': function(text, 'obor_collision_attack_frame'),
    }


def program(data, parts=None, *, pointer=True, attack_instances=True,
            body_instances=True, old_names=False):
    engine = ROOT / 'src/engines' / data['engine']
    if parts is None:
        parts = source_parts(engine)
    prefix = '&' if pointer else ''
    attack_member = 'collision' if old_names else 'collision_attack'
    body_member = 'body_collision' if old_names else 'collision_body'
    attack_type = 's_collision_attack_list' if attack_instances else 's_collision_attack'
    body_type = 's_collision_body_list' if body_instances else 's_collision_body'
    attack = '&attack_frame' if attack_instances else '&a0'
    opposing = '&opposing_frame' if attack_instances else '&opposition'
    body = '&body_frame' if body_instances else '&b0'
    table = [f'{attack_type} *attack_table[] = {{{attack}}}, *opposing_table[] = {{{opposing}}};',
             f'{body_type} *body_table[] = {{{body}}};']
    inputs = []
    for case in data['cases']:
        attack_boxes = ['{' + ','.join(str(box[key]) for key in COORDS) + '}' for box in case['attack']]
        body_boxes = ['{' + ','.join(str(box[key]) for key in COORDS) + '}' for box in case['body']]
        opponent = ','.join(str(case['opposition'][key]) for key in COORDS)
        inputs.append('{{' + ','.join(attack_boxes) + '},{' + ','.join(body_boxes) + '},{' + opponent
                      + '},' + ','.join(str(case[key]) for key in OPTIONS) + '}')
    values = parts | {
        'COORDINATES': 's_hitbox *' if pointer else 's_hitbox',
        'ATTACK_TABLE': f'{attack_type} **{attack_member};',
        'BODY_TABLE': f'{body_type} **{body_member};',
        'TABLES': '\n    '.join(table),
        'ATTACKER_INIT': f'.{attack_member} = attack_table',
        'TARGET_INIT': f'.{attack_member} = opposing_table, .{body_member} = body_table',
        'A0': prefix + 'attack_boxes[0]', 'A1': prefix + 'attack_boxes[1]',
        'B0': prefix + 'body_boxes[0]', 'B1': prefix + 'body_boxes[1]',
        'AP': prefix + 'opposing_box',
        'INPUTS': ',\n'.join(inputs),
        'REVISIONS': ','.join(str(row['revision']) for row in data['sources']),
    }
    template = Path(__file__).with_name('historical_hit_selection_contract.c.in').read_text()
    return re.sub(r'@([A-Z0-9_]+)@', lambda match: values[match[1]], template)


class HitSelectionContracts(unittest.TestCase):
    def test_4432_blocker_target_selection(self):
        fixture = FIXTURE.with_name('profile-4432-blocker-target-contracts.json')
        data = load_contract_fixture(fixture)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for profile in contract_profiles(data, pin['profiles'], source_range=data['range']):
            if profile['engine'] == data['engine']:
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertIs(type(row['multiple_instances']), bool)
            self.assertIs(type(row['guarded_lookup']), bool)
        core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text(encoding='latin1')
        methods = ['diff', 'obor_collision_attack_frame']
        if 'static int obor_blockable_attack(' in core:
            methods.append('obor_blockable_attack')
        methods.append('block_find_target')
        values = {
            'METHODS': '\n'.join(function(core, name) for name in methods),
            'PROFILES': ',\n'.join('{%du,%d}' % (row['revision'], row['multiple_instances'])
                                  for row in rows),
        }
        template = Path(__file__).with_name('historical_blocker_target_contract.c.in').read_text()
        probe = re.sub(r'@([A-Z_]+)@', lambda item: values[item[1]], template)
        result = json.loads(native_output(probe, data, extra_cflags=('-fgnu89-inline',)))
        self.assertEqual(result, {'contexts': len(rows), 'cases': 18 * len(rows)})

    def test_native_hit_entry_checks(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual(data['cases'][0]['name'], 'both_match')
        probe = '#define COLLISION_ENTRY_GATE_PROBE 1\n' + program(data)
        actual = [json.loads(line) for line in native_output(probe, data).splitlines()]
        self.assertEqual(actual, [[row['revision'], 5] for row in data['sources']])

    def test_original_pair_and_caller_selection(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        observations = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        expected = [[row['revision'], *result] for row in data['sources']
                    for result in data['contracts'][row['contract']]]
        self.assertEqual(len(observations), len(expected))
        for actual, reference in zip(observations, expected):
            with self.subTest(revision=reference[0], case=data['cases'][reference[1]]['name']):
                self.assertEqual(actual, reference)


if __name__ == '__main__':
    unittest.main()
