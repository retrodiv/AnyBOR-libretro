"""Check legacy texture pixels and bounded arguments with complete native units.

The shared source oracle reverses only this validation delta. Storage identity
and capacity are bounded providers; image loading and gameplay are separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import unittest

from contract_fixtures import load_contract_fixture
from test_historical_player import rename_identifiers
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))
FIXTURE = HERE / 'fixtures/legacy-texture-native-baseline.json'


def program(engine, profiles, *, wrong_endpoint=False):
    data = load_contract_fixture(FIXTURE)
    names = ['texture_set_wave', 'texture_wave', 'texture_plane', 'apply_texture_wave',
             'apply_texture_plane', 'texture_wavex8p16', 'texture_planex8p16',
             'texture_wavex8p32', 'texture_planex8p32', '_sinfactors', '_amp']
    native, original = [], []
    if set(data['restorations']) != {'source/gamelib/texture.c',
            'source/gamelib/texture16.c', 'source/gamelib/texture32.c'}:
        raise ValueError('Three complete legacy texture units required')
    for index, (path, edits) in enumerate(data['restorations'].items()):
        text = (engine / path).read_text(encoding='latin1')
        baseline = text
        for edit in edits:
            if set(edit) != {'before', 'after'} or baseline.count(edit['after']) != 1:
                raise ValueError('Native source restoration is missing or ambiguous')
            baseline = baseline.replace(edit['after'], edit['before'], 1)
        if wrong_endpoint and index == 0:
            line = 'if((size_t)s >= source_available) return;'
            if text.count(line) != 1:
                raise ValueError('One native first-unit row bound required')
            text = text.replace(line, 'if((size_t)s > source_available) return;', 1)
        native.append('#undef distortion\n'+rename_identifiers(text, {'draw_plane_line': 'native_line'+str(index)}))
        original.append('#undef distortion\n'+rename_identifiers(baseline,
            dict({name: 'original_'+name for name in names}, draw_plane_line='original_line'+str(index))))
    text = (HERE / 'legacy_texture_bounds.c.in').read_text()
    return text.replace('@UNITS@', '\n'.join(native+original)).replace('@PROFILES@',
        ','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u' for p in profiles))


class LegacyTextureBoundsTests(unittest.TestCase):
    def test_complete_native_units_preserve_pixels_and_bound_inputs_by_profile(self):
        data = load_contract_fixture(FIXTURE)
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        profiles = [p for p in pin['profiles'] if p['engine'] == data['engine'] and
                    data['range'][0] <= int(p.get('revision', p['build'].split('-')[0])) <= data['range'][1]]
        self.assertTrue(profiles)
        engine = ROOT / 'src/engines' / data['engine']
        result = run_native(engine, program(engine, profiles))
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['status'], 'PASS')
        self.assertEqual(value['profiles'], len(profiles))
        self.assertGreaterEqual(value['checks'], 400*len(profiles))

    def test_allowing_the_end_of_storage_fails_a_defined_pixel_control(self):
        data = load_contract_fixture(FIXTURE)
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        profile = next(p for p in pin['profiles'] if p['engine'] == data['engine'])
        engine = ROOT / 'src/engines' / data['engine']
        text = '#define ENDPOINT_ONLY 1\n'+program(engine, [profile], wrong_endpoint=True)
        result = run_native(engine, text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('target[0] == 0xa5', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
