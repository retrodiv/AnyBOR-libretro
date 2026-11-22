"""Check native perception-threshold arithmetic with real entity records.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import native_output
from test_historical_player import function
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


def adjustment_intro():
    fixture = load_contract_fixture(HERE / 'fixtures/profile-early-target-detection.json')
    return min(row['revision'] for row in fixture['sources'] if row['optional_detect'])


def program(engine, profiles, *, remove_promotion=False):
    source = (engine / 'openbor.c').read_text(encoding='latin1')
    target = function(source, 'normal_find_target')
    promotion = '(int64_t)iDetect' if '(int64_t)iDetect' in target else '(int64_t)detect_adj'
    if target.count(promotion) != 1:
        raise ValueError('One explicit native threshold promotion required')
    if remove_promotion:
        target = target.replace(promotion, promotion[len('(int64_t)'):], 1)
    hostility_init = ''
    if '->modeldata.hostile' in target:
        hostility_init = 'actor.modeldata.hostile=2;candidate.modeldata.type=2;'
    elif '->faction.type_hostile' in target:
        hostility_init = 'actor.faction.type_hostile=TYPE_ENEMY;candidate.modeldata.type=TYPE_ENEMY;'
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
                  DIFF=function(source, 'diff'), TARGET=target, INTRO=str(adjustment_intro())+'u',
                  HOSTILITY_INIT=hostility_init,
                  POSITION_INIT=('candidate.position.x=10;' if '->position.x' in target else 'candidate.x=10;'),
                  PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u'
                                    for p in profiles))
    text = (HERE / 'target_detection_arithmetic.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    return text


class TargetDetectionArithmeticTests(unittest.TestCase):
    def test_native_threshold_selection_in_each_family_and_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for row in pin['engines']:
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
            engine = ROOT / 'src/engines' / row['build']
            with self.subTest(engine=row['build']):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                self.assertEqual(json.loads(result.stdout),
                                 dict(status='PASS', profiles=len(profiles), cases=450+4*len(profiles)))

    def test_late_promotion_is_detected(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        row = pin['engines'][0]
        engine = ROOT / 'src/engines' / row['build']
        profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
        profile = max(profiles, key=lambda p: int(p.get('revision', p['build'].split('-')[0])))
        result = run_native(engine, program(engine, [profile], remove_promotion=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('signed integer overflow', result.stderr)


class NormalTargetSelectionContracts(unittest.TestCase):
    def test_7533_combat_range_keeps_original_coordinate_comparisons(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text(encoding='latin1')
        axes = ('x', 'y', 'z', 'base', 'all')
        functions = '\n\n'.join(function(source, 'check_range_target_' + axis) for axis in axes)
        functions += '\n' + function((engine / 'openborscript.c').read_text(), 'openbor_checkrange')
        template = (HERE / 'combat_range_contract.c.in').read_text()
        code = template.replace('@FUNCTIONS@', functions)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), 'PASS\n')

    def check_normal_target_selection(self, engine_id):
        data = load_contract_fixture(HERE / 'fixtures/profile-normal-target-selection.json')
        rows = [row for row in data['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][engine_id])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / engine_id))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        ranges = ('obor_check_range_5134', 'check_range_target_base', 'check_range_target_x',
                  'check_range_target_y', 'check_range_target_z', 'check_range_target_all')
        values = dict(DIFF=function(source, 'diff'), TARGET=function(source, 'normal_find_target'),
                      RANGES='\n'.join(function(source, name) for name in ranges) if engine_id == '6391' else '',
                      ROWS=',\n'.join('{%du,%d,%d}' % (
                          row['revision'], row['inclusive_distance'], row['fractional_range']) for row in rows))
        template = (HERE / 'normal_target_selection_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, {'engine': engine_id}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',), libraries=('m',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_normal_target_selection(self):
        self.check_normal_target_selection('4432')

    def test_6391_normal_target_selection(self):
        self.check_normal_target_selection('6391')


if __name__ == '__main__':
    unittest.main()
