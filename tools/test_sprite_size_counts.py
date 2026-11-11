"""Check native sprite size queries, encoded bytes and independent decoding.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import unittest

from test_historical_player import function
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


def program(engine, profiles, reference=None):
    source_path = engine / 'source/gamelib/sprite.c'
    if not source_path.exists():
        source_path = engine / 'source/gamelib/spritef.c'
    source = source_path.read_text(encoding='latin1')
    encoder = function(source, 'encodesprite')
    methods = encoder + '\n' + function(source, 'fakey_encodesprite')
    if 'obor_profile_build' in methods:
        raise ValueError('Review new profile-dependent sprite encoding separately')
    cropped = 'bitmap->clipped_width' in encoder
    text = (HERE / 'sprite_size_counts.c.in').read_text()
    values = dict(METHODS=methods,
                  REFERENCE='' if reference is None else reference.replace(
                      'encodesprite(', 'reference_encodesprite(', 1),
                  HAS_REFERENCE=str(int(reference is not None)),
                  NOTIFIES=str(int('obor_resources_sprite_encoded' in encoder)),
                  CROPPED=str(int(cropped)),
                  CROP_INIT=('bitmap->clipped_width=width;bitmap->clipped_height=height;'
                             'bitmap->clipped_x_offset=left;bitmap->clipped_y_offset=top;'
                             if cropped else ''),
                  PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u'
                                    for p in profiles))
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    return text


class SpriteSizeCountTests(unittest.TestCase):
    def test_size_queries_and_native_pixel_roundtrip(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
            with self.subTest(engine=row['build']):
                text = program(engine, profiles)
                result = run_native(engine, text)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['profiles'], len(profiles))
                self.assertEqual(value['reference'], False)
                self.assertEqual(value['cases'],
                                 (1920 if '#define CROPPED 1' in text else 960)+3*len(profiles))

    def test_missing_end_marker_count_is_detected(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        row = pin['engines'][0]
        engine = ROOT / 'src/engines' / row['build']
        profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
        text = program(engine, profiles[:1])
        self.assertIn('++encoded_size;', text)
        # Spare physical backing bounds this negative control; a runtime size
        # guard assertion, rather than compiler rejection, must detect it.
        result = run_native(engine, text.replace('++encoded_size;', '(void)0;', 1))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('encoded size guard', result.stderr)


if __name__ == '__main__':
    unittest.main()
