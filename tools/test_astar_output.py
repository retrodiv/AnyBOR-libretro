"""Check the native path output prefix and its final initialized point.

Terrain queries and allocations are bounded providers; the complete search runs
with real native entity and waypoint records. This is not movement acceptance.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from test_historical_player import function
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


def program(engine, profiles, *, remove_initialization=False, wrong_element_size=False):
    source = (engine / 'openbor.c').read_text(encoding='latin1')
    body = function(source, 'astar')
    position = 'position.' if 'ent->position.x' in body else ''
    point = re.search(r'float\s+step,\s*(\w+)\s*\*\*\s*wp', body)
    dimensions = re.search(r'(?m)^#define astarw[^\n]*\n#define astarh[^\n]*\n#define starts[^\n]*', source)
    if point is None or dimensions is None:
        raise ValueError('Native waypoint type and search dimensions required')
    allocation = '*wp = malloc(sizeof(**wp)*result);'
    if body.count(allocation) != 1:
        raise ValueError('One allocation using the native element extent required')
    if wrong_element_size:
        body = body.replace(allocation, '*wp = malloc(sizeof(*wp)*result);', 1)
    for axis in ('x', 'z'):
        statement = '(*wp)[result-1].'+axis+' = ent->'+position+axis+';'
        if body.count(statement) != 1:
            raise ValueError('One final-point initialization per axis required')
        if remove_initialization:
            body = body.replace(statement, '(void)0;', 1)
    values = dict(POINT=point[1], POSITION=position, DIMENSIONS=dimensions[0],
                  DIFF=function(source, 'diff'), ASTAR=body,
                  PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u'
                                    for p in profiles))
    text = (HERE / 'astar_output.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    return text


class AstarOutputTests(unittest.TestCase):
    def test_native_search_prefix_and_initialized_tail_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        present = []
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            source = (engine / 'openbor.c').read_text(encoding='latin1')
            if not re.search(r'\bint\s+astar\(', source):
                continue
            present.append(row['build'])
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build'] and
                        int(p.get('revision', p['build'].split('-')[0])) >= 3529]
            with self.subTest(engine=row['build']):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                self.assertEqual(json.loads(result.stdout),
                                 dict(profiles=len(profiles), cases=13*len(profiles)))
        self.assertEqual(len(present), len(pin['engines'])-1)

    def test_missing_initialization_is_detected(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        row = next(r for r in pin['engines'] if r['build'] == '3741')
        engine = ROOT / 'src/engines' / row['build']
        profile = next(p for p in pin['profiles'] if p['engine'] == row['build'] and
                       int(p.get('revision', p['build'].split('-')[0])) >= 3529)
        result = run_native(engine, program(engine, [profile], remove_initialization=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('waypoint contract', result.stderr)

    def test_wrong_element_extent_is_detected_before_use(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        row = next(r for r in pin['engines'] if r['build'] == '4086')
        engine = ROOT / 'src/engines' / row['build']
        profile = next(p for p in pin['profiles'] if p['engine'] == row['build'])
        result = run_native(engine, program(engine, [profile], wrong_element_size=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('bytes==expected_output_bytes', result.stderr)


if __name__ == '__main__':
    unittest.main()
