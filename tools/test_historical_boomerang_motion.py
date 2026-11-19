"""Compare each original boomerang movement route and its caller outputs.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_early_jump_walkoff import braced_statement
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-boomerang-motion-contracts.json'
TERRAIN = FIXTURE.with_name('profile-4432-projectile-terrain.json')
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
    if 'obor_projectile_hits_platform' in source:
        names = ('obor_projectile_hits_platform',) + names
    return '\n'.join(function(source, name) for name in names) + '\n' + movement_dispatch(
        function(source, 'common_move'))


def source_engine(data):
    return Path(os.environ.get('OBOR_PROJECTILE_TERRAIN_ENGINE', ROOT / 'src/engines' / data['engine']))


def program(data, movement=None):
    engine = source_engine(data)
    if movement is None:
        movement = candidate_movement((engine/'openbor.c').read_text(encoding='latin1'))
    params = ['{' + ','.join(str(row[name]) for name in INPUTS) + '}' for row in data['cases']]
    values = {'MOVEMENT': movement, 'CASES': ',\n'.join(params),
              'REVISIONS': ','.join(str(row['revision']) for row in data['sources'])}
    template = Path(__file__).with_name('boomerang_motion_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda m: values[m[1]], template)


class BoomerangMotionTests(unittest.TestCase):
    def test_projectile_terrain(self):
        data = load_contract_fixture(TERRAIN)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = source_engine(data)
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        names = ('obor_profile_animation_base', 'obor_projectile_hits_platform', 'arrow_move',
                 'obor_boomerang_oscillate', 'obor_boomerang_turn_by_distance', 'obor_boomerang_catch',
                 'boomerang_move', 'bomb_move', 'star_move', 'star_spawn')
        spawn = function(source, 'bomb_spawn')
        entry = spawn.index('    e->modeldata.no_adjust_base = 0;')
        commands = function((engine / 'source/gamelib/commands.c').read_text(), 'createModelCommandList')
        registration = re.search(r'(?m)^    if\([^\n]+\)\n    \{\n'
                                 r'        LIST_ADD\(CMD_MODEL_STAR_VELOCITY, "starvelocity"\);\n    \}', commands)[0]
        _, cases = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        draw_sort = braced_statement(function(source, 'display_ents'), 'if(e->owner &&\n')
        checks = dict(MOVEMENT='\n'.join(function(source, name) for name in names),
                      SPAWN=spawn[entry:spawn.rindex('    return e;')],
                      STAR_REGISTRATION=registration,
                      STAR_COMMAND=cases['CMD_MODEL_STAR_VELOCITY']['body'],
                      STAR_DRAW_SORT=draw_sort,
                      PROFILES=',\n'.join('{%du,%d}' % (row['revision'], row['terrain'])
                                          for row in rows))
        template = Path(__file__).with_name('projectile_terrain_contract.c.in').read_text()
        probe = re.sub(r'@([A-Z_]+)@', lambda m: checks[m[1]], template)
        actual = native_output(probe, data, engine_source=engine)
        self.assertEqual([int(line) for line in actual.splitlines()], revisions)

    def test_original_motion_contracts(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        output = native_output(program(data), data, engine_source=source_engine(data))
        actual = [json.loads(line) for line in output.splitlines()]
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
        result = json.loads(native_output(program(sample), data, engine_source=source_engine(data)))
        self.assertEqual(result[:6], [4432, 0, 1, [88, 9, 4], [12, 0, 0], 1])


if __name__ == '__main__':
    unittest.main()
