"""Check native queue capacity, enemy icon palettes and water diagnostics.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-drawing-details-contracts.json'


def program(data, engine):
    core = (engine / 'openbor.c').read_text()
    queue = (engine / 'source/gamelib/spriteq.c').read_text()
    transform = (engine / 'source/gamelib/transform.c').read_text()
    starts = list(re.finditer(r'(?m)^#define[ \t]+MAXQSPRITES\b', queue))
    if len(starts) != 1:
        raise ValueError('One native queue declaration required')
    end = queue.index('void spriteq_add_frame(', starts[0].start())
    plain = re.findall(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{[^;]+\};', core)
    sine = re.findall(r'(?m)^float _sinfactors\[256\]\s*=\s*\{[^;]+\};', transform)
    distortion = re.findall(r'(?m)^#define distortion[^\n]*', transform)
    if len(plain) != 1 or len(sine) != 1 or len(distortion) != 1:
        raise ValueError('Complete native draw defaults and wave lookup required')
    parts = dict(STORAGE=queue[starts[0].start():end],
        QUEUE='\n'.join(function(queue, n) for n in ('spriteq_add_frame', 'spriteq_add_sprite',
            'spriteq_add_screen', 'spriteq_add_dot', 'spriteq_add_line', 'spriteq_add_box',
            'spriteq_lock', 'spriteq_unlock', 'spriteq_clear')),
        ICON=function(core, 'drawenemystatus'), PLAIN=plain[0],
        WATER=sine[0]+'\n'+distortion[0]+'\n'+function(transform, 'gfx_draw_water'),
        CONTEXTS=','.join('{%du,%d,%d,%d}' % (r['revision'], r['queue_limit'],
            r['icon_usemap'], r['water_log']) for r in data['sources']))
    result = Path(__file__).with_name('forward_drawing_details_contract.c.in').read_text()
    for key, value in parts.items():
        result = result.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', result):
        raise ValueError('Unresolved native drawing dependency')
    return result


class ForwardDrawingDetailsTests(unittest.TestCase):
    def test_queue_admission_icon_requests_and_water_log(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        for row in data['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_DRAWING_DETAILS_ENGINE', ROOT / 'src/engines' / data['engine']))
        rows = [json.loads(line) for line in native_output(program(data, engine), data,
                engine_source=engine).splitlines()]
        self.assertEqual(rows, [dict(revision=row['revision'], status='PASS') for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
