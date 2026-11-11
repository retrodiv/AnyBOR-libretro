"""Check complete numeric graphics getters and their native conversion targets.

The historical graphics suite covers its own physical-family control. These
checks cover the other native getters with real record types and conversion;
numeric mapping, result initialization and sprite decoding are bounded providers.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture
from test_historical_player import function, rename_identifiers
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


def targets():
    pin = json.loads((ROOT / 'src/pin.json').read_text())
    control = load_contract_fixture(HERE / 'fixtures/profile-gfx-property-contracts.json')['engine']
    result = []
    for entry in pin['engines']:
        engine = ROOT / 'src/engines' / entry['build']
        if entry['build'] == control:
            continue
        core = (engine / 'openborscript.c').read_text(encoding='latin1')
        if re.search(r'(?m)^HRESULT openbor_getgfxproperty\(', core):
            result.append((engine, [p for p in pin['profiles'] if p['engine'] == entry['build']]))
    return result


def program(engine, profiles, *, swap_targets=False):
    core = (engine / 'openborscript.c').read_text(encoding='latin1')
    getter = function(core, 'openbor_getgfxproperty')
    if swap_targets:
        getter, count = re.subn(r'value\s*\+\s*\(i\s*-\s*2\)', 'value + (3 - i)', getter)
        if count != 1:
            raise ValueError('One coordinate destination expression required')
    enum = re.search(r'(?m)^enum gfxproperty_enum\s*\{[\s\S]*?^};', core)
    if enum is None:
        raise ValueError('Complete native graphics property enum required')
    variants = list((engine / 'source').rglob('ScriptVariant.c'))
    if len(variants) != 1:
        raise ValueError('One native variant unit required')
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        BITMAP_CLIP_SETUP='bitmap->clipped_width=3;bitmap->clipped_height=2;' if
            'clipped_width' in (engine / 'source/gamelib/types.h').read_text(encoding='latin1') else '',
        ENUM=enum[0], CONVERSION=function(variants[0].read_text(encoding='latin1'), 'ScriptVariant_IntegerValue'),
        GETTER=rename_identifiers(getter, {
            'mapstrings_gfxproperty': 'fixture_map_numeric',
            'ScriptVariant_ChangeType': 'fixture_result_type',
            'ScriptVariant_IntegerValue': 'fixture_integer',
            'sprite_get_pixel': 'fixture_sprite_pixel', 'printf': 'fixture_diagnostic'}),
        PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u' for p in profiles))
    text = (HERE / 'graphics_query_coordinates.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    return text


class GraphicsQueryCoordinateTests(unittest.TestCase):
    def test_native_getters_preserve_coordinate_results_in_each_later_profile(self):
        entries = targets()
        self.assertTrue(entries)
        for engine, profiles in entries:
            with self.subTest(engine=engine.name):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                self.assertGreaterEqual(value['cases'], 100*len(profiles))

    def test_swapped_targets_fail_before_an_invalid_memory_operation(self):
        engine, profiles = targets()[0]
        text = '#define NEGATIVE_ONLY 1\n'+program(engine, profiles[:1], swap_targets=True)
        result = run_native(engine, text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('coordinate destination', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
