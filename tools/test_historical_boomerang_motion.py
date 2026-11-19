"""Compare each original boomerang movement route and its caller outputs.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-boomerang-motion-contracts.json'
INPUTS = (
    'aimove', 'parent', 'direction', 'parent_direction', 'parent_type',
    'x', 'y', 'z', 'vx', 'vz', 'dest', 'accel', 'distance', 'speed',
    'count', 'sortid', 'nomove', 'wall_toggle', 'wall_index', 'wall_animation',
    'catch_ground', 'catch_air', 'min', 'max', 'parent_y', 'parent_pain', 'parent_falling', 'parent_dead',
)


def movement_dispatch(text):
    start = text.index('    else if(aimove & AIMOVE1_NOMOVE)')
    end = re.search(r'(?m)^    else\s*\n', text[start:])
    if end is None:
        raise ValueError('Native special-movement dispatcher did not terminate before other AI')
    return text[:start+end.start()] + '    return -19;\n}\n'


def candidate_movement(source):
    names = (
        'obor_boomerang_oscillate', 'obor_boomerang_turn_by_distance', 'obor_boomerang_catch', 'boomerang_move'
    )
    if 'obor_profile_animation_base' in source:
        names = ('obor_profile_animation_base',) + names
    return '\n'.join(function(source, name) for name in names) + '\n' + movement_dispatch(
        function(source, 'common_move'))


def program(data, movement=None):
    engine = ROOT / 'src/engines' / data['engine']
    if movement is None:
        movement = candidate_movement((engine/'openbor.c').read_text(encoding='latin1'))
    params = ['{' + ','.join(str(row[name]) for name in INPUTS) + '}' for row in data['cases']]
    values = {'MOVEMENT': movement, 'CASES': ',\n'.join(params),
              'REVISIONS': ','.join(str(row['revision']) for row in data['sources'])}
    template = Path(__file__).with_name('boomerang_motion_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda m: values[m[1]], template)


class BoomerangMotionTests(unittest.TestCase):
    def test_original_motion_contracts(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        expected = [[row['revision'], *result] for row in data['sources']
                    for result in data['contracts'][row['contract']]]
        self.assertEqual(len(actual), len(expected))
        for result, reference in zip(actual, expected):
            with self.subTest(revision=reference[0], case=data['cases'][reference[1]]['name']):
                self.assertEqual(result, reference)

    def test_parentless_launch_keeps_vertical_position(self):
        data = load_contract_fixture(FIXTURE)
        launch = next(case for case in data['cases'] if case['name'] == 'launch_right')
        sample = data | {
            'sources': [{'revision': 4432}],
            'cases': [launch | {'parent': 0, 'x': 88, 'y': 9, 'z': 4}],
        }
        result = json.loads(native_output(program(sample), data))
        self.assertEqual(result[:6], [4432, 0, 1, [88, 9, 4], [12, 0, 0], 1])


if __name__ == '__main__':
    unittest.main()
