"""Check complete GIF decoders with bounded I/O and storage providers.

Native records, color conversion and freescreen remain in the probe. This
checks decoded bytes and decoder ownership, not native allocscreen arithmetic,
the complete player, arbitrary object pointers or frontend acceptance.
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


def program(engine, profiles, *, remove_horizontal_bound=False):
    decoder = (engine / 'source/gamelib/anigif.c').read_text(encoding='latin1')
    stream = 'info->info[n]' in decoder
    if remove_horizontal_bound:
        bound = 'byte < width && '
        if decoder.count(bound) != 1:
            raise ValueError('One native horizontal pixel guard required')
        decoder = decoder.replace(bound, '', 1)
    screen = (engine / 'source/gamelib/screen.c').read_text(encoding='latin1')
    colors = (engine / 'source/gamelib/pixelformat.c').read_text(encoding='latin1')
    values = dict(
        STREAM='1' if stream else '0', DECODER=decoder,
        COLORS='\n'.join(function(colors, name) for name in ('colour16', 'colour32')),
        FREE_SCREEN=function(screen, 'freescreen'),
        RAW='obor_profile_build < 3477' if engine.name == '3400' else '0',
        OPEN='anigif_open_ex' if 'int anigif_open_ex(' in decoder else 'anigif_open',
        CLOSE='anigif_close_ex' if 'void anigif_close_ex(' in decoder else 'anigif_close',
        DECODE='anigif_decode_ex' if 'int anigif_decode_ex(' in decoder else 'anigif_decode',
        PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u' for p in profiles))
    text = (HERE / 'gif_memory_bounds.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved GIF dependency')
    return text


class GifMemoryBoundsTests(unittest.TestCase):
    def test_legacy_pixel_formats_and_byte_aligned_palettes_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            if 'info->info[n]' in (engine / 'source/gamelib/anigif.c').read_text(encoding='latin1'):
                continue
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
            with self.subTest(engine=row['build']):
                result = run_native(engine, '#define PIXEL_FORMAT_ONLY 1\n'+program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                self.assertGreaterEqual(value['checks'], 1000*len(profiles))

    def test_native_pixels_boundaries_names_and_owned_cleanup_by_profile(self):
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
                self.assertGreaterEqual(value['checks'], 100*len(profiles))

    def test_missing_pixel_bound_fails_a_logical_result_in_spare_backing(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines/3400'
        profile = next(p for p in pin['profiles'] if p['build'] == '3400')
        text = '#define PIXEL_BOUND_ONLY 1\n'+program(engine, [profile], remove_horizontal_bound=True)
        result = run_native(engine, text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('pixels_match', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
