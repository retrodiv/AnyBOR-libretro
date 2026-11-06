"""Check native layer geometry, repetition and graphic-kind boundaries.

Raster operations are typed queue observers. Cache/canvas and parser contracts
are separate from this renderer's declared source range.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_hud_schedule import native_declarations
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-background-layer-contracts.json'


def program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    text = Path(__file__).with_name('background_layer_contract.c.in').read_text()
    values = dict(DECLARATIONS=native_declarations(source),
        DRAW='\n'.join(function(source,name) for name in ('obor_legacy_cached_bg','obor_legacy_canvas_bg','draw_scrolled_bg') if name=='draw_scrolled_bg' or ('static void '+name+'(') in source),
        UPDATE=function(source, 'update_scrolled_bg'),
        CONTEXTS=','.join('{%d,%d,%d,%d,%d,%d,%d}' % (r['revision'], r['nested_repeats'],
            r['precedence_z'], r['old_hole_coordinates'], r['zero_sort_id'], r['stored_gfx_tag'], r['legacy_canvas'])
                          for r in data['sources']))
    for name, value in values.items():
        text = text.replace('@' + name + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise AssertionError('Unresolved native background layer input')
    return text


class HistoricalBackgroundLayerContracts(unittest.TestCase):
    def test_geometry_repetition_queue_order_and_kind(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [r['revision'] for r in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], cases=154 if r['legacy_canvas'] else 378, status='PASS') for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
