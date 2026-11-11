"""Check native perception-threshold arithmetic with real entity records.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import unittest

from contract_fixtures import load_contract_fixture
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
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
                  DIFF=function(source, 'diff'), TARGET=target, INTRO=str(adjustment_intro())+'u',
                  HOSTILITY_INIT=('actor.modeldata.hostile=2;candidate.modeldata.type=2;'
                                  if '->modeldata.hostile' in target else ''),
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


if __name__ == '__main__':
    unittest.main()
