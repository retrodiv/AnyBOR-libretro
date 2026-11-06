"""Check native legacy pixel queries, zoom conversion, sampling and composition.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function
from test_early_system_callbacks import block

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-legacy-graphics-contracts.json'


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    script = (engine / 'openborscript.c').read_text()
    screen = (engine / 'source/gamelib/screen.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    update = function((engine / 'openbor.c').read_text(), 'update')
    start = update.index('if(obor_profile_build < 3552 && zoom_scale_x > 0 && zoom_scale_y > 0)')
    first = block(update, start)
    second = block(update, start+len(first))
    parts = dict(VARIANTS='\n'.join(function(variant, name) for name in
                  ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
        FUNCTIONS='\n'.join(function(script, name) for name in
                  ('openbor_zoom', 'obor_legacy_sprite_pixel', 'openbor_getpixel')),
        SAMPLER='\n'.join(function(screen, name) for name in ('obor_zoom_storage', 'zoomscreen')),
        COMPOSE='static void compose(void){'+first+second+'}',
        CHECKS='\n'.join('check(%du,%d,%d);' % (row['revision'],
                data['contracts'][row['contract']]['zoom'],
                data['contracts'][row['contract']]['getpixel']) for row in data['sources']),
        SAMPLES=',\n'.join('{%s,{%s}}' % (
            ','.join(str(row[key]) for key in ('cx', 'cy', 'sx', 'sy')),
            ','.join(map(str, row['pixels']))) for row in data['samples']))
    text = Path(__file__).with_name('legacy_graphics_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved legacy graphics dependency')
    return text


class LegacyGraphicsContracts(unittest.TestCase):
    def test_native_arguments_pixels_sampling_and_frame_window(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len({row['revision'] for row in data['sources']}), len(data['sources']))
        for row in data['samples']:
            self.assertEqual(len(row['pixels']), 12)
            self.assertTrue(all(type(v) is int and 0 <= v <= 255 for v in row['pixels']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], **data['contracts'][row['contract']])
                                  for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
