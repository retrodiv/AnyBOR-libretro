"""Check native screen reference loads/releases and their ownership order.

Image I/O and allocation are bounded providers; record types, loadscreen and
freescreen are native. This does not validate full decoding, allocscreen size
arithmetic, arbitrary pointers or stock frontend acceptance.
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


def program(engine, profiles, *, omit_null_check=False):
    load = function((engine / 'source/gamelib/loadimg.c').read_text(encoding='latin1'), 'loadscreen')
    if omit_null_check:
        check = 'if(!screen) return 0;'
        if load.count(check) != 1:
            raise ValueError('One native output-slot guard required')
        # Bounded negative control: a defined refusal becomes a wrong success.
        load = load.replace(check, 'if(!screen) return 1;', 1)
    values = dict(LOAD_SCREEN=load,
                  FREE_SCREEN=function((engine / 'source/gamelib/screen.c').read_text(encoding='latin1'), 'freescreen'),
                  ASSERT_HEADER='#include "obor_image_assert.h"' if engine.name == '3400' else '',
                  PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u' for p in profiles))
    text = (HERE / 'screen_reference_alignment.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved screen reference dependency')
    return text


class ScreenReferenceAlignmentTests(unittest.TestCase):
    def test_native_screen_load_release_and_output_slots_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
            with self.subTest(engine=row['build']):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                self.assertGreaterEqual(value['checks'], 1000*len(profiles))

    def test_incorrect_refusal_fails_a_logical_result_without_memory_fault(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines/3400'
        profile = next(p for p in pin['profiles'] if p['build'] == '3400')
        text = '#define NULL_ONLY 1\n'+program(engine, [profile], omit_null_check=True)
        result = run_native(engine, text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('loadscreen(', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
