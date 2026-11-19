"""Observe coordinates, model name labels and collision boxes in the native overlay.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-debug-geometry-contracts.json'


def program(data, previous=None):
    engine = ROOT / 'src/engines' / data['engine']
    source = previous if previous is not None else (engine / 'openbor.c').read_text(encoding='latin1')
    fonts = (engine / 'source/gamelib/font.c').read_text(encoding='latin1')
    native = function(fonts, 'font_string_width_max') + '\n' + '\n'.join(
        function(source, name) for name in (
            'obor_collision_attack_frame', 'draw_position_entity',
            'draw_features_entity', 'draw_box_on_entity', 'draw_visual_debug'))
    template = Path(__file__).with_name('debug_geometry_contract.c.in').read_text()
    return template.replace('@NATIVE@', native).replace(
        '@PROFILES@', ','.join(str(row['revision']) for row in data['sources']))


class HistoricalDebugGeometryTests(unittest.TestCase):
    def test_native_geometry_and_text(self):
        data = load_contract_fixture(FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        observed = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(len(observed), len(rows))
        for actual, row in zip(observed, rows):
            expected = data['contracts'][row['contract']]
            with self.subTest(revision=row['revision']):
                self.assertEqual(actual, dict(revision=row['revision'], cases=expected))


if __name__ == '__main__':
    unittest.main()
