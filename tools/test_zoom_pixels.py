"""Check bounded zoom against native crop-copy and fixed-point scalers.

Native records and raster helpers are real source. Screen allocation/extent
providers are bounded fixtures. The reference creates the native aligned crop,
copies into it, then calls the unchanged scaler; the candidate samples directly.
Only previously unassigned crop pixels receive the explicit zero policy.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import sys
import unittest

from test_historical_player import function
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


def program(engine, profiles):
    source = (engine / 'source/gamelib/screen.c').read_text(encoding='latin1')
    copy = function(source, 'copyscreen_o')
    helpers = [copy, function(source, 'scalescreen')]
    for suffix in ['16', '32']:
        helpers.append(function((engine / ('source/gamelib/screen'+suffix+'.c')).read_text(
            encoding='latin1'), 'scalescreen'+suffix))
    parts = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        MAGIC_INIT='' if engine.name == '3400' else 'screen->magic=screen_magic;',
        INVALID_MAGIC='' if engine.name == '3400' else
            'int old_magic=src->magic;src->magic=0;unchanged(dest,src,256,256);src->magic=old_magic;',
        HAS_CLIP=str(int('useclip' in copy)), NATIVE_HELPERS='\n'.join(helpers),
        STORAGE=function(source, 'obor_zoom_storage'), ZOOM=function(source, 'zoomscreen'),
        PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u' for p in profiles))
    text = (HERE / 'zoom_pixels.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native zoom dependency')
    return text


class ZoomPixelTests(unittest.TestCase):
    def test_native_crop_pixels_and_bounded_inputs_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
            with self.subTest(engine=row['build']):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['profiles'], len(profiles))
                self.assertEqual(value['status'], 'PASS')
                self.assertGreaterEqual(value['pixel_cases'], 48*len(profiles))
                print(json.dumps(dict(engine=row['build'], **value), sort_keys=True), file=sys.stderr)

    def test_unrounded_crop_width_is_detected(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        row = pin['engines'][0]
        engine = ROOT / 'src/engines' / row['build']
        profile = next(p for p in pin['profiles'] if p['engine'] == row['build'])
        text = program(engine, [profile])
        guard = 'width &= ~INT64_C(3);'
        self.assertEqual(text.count(guard), 1)
        result = run_native(engine, text.replace(guard, '(void)0;'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('zoom pixel mismatch', result.stderr)


if __name__ == '__main__':
    unittest.main()
