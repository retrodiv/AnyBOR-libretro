"""Check the native HUD tail and Start-to-selection routes by source revision.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-hud-status-contracts.json'


def program(data, source=None):
    if source is None:
        source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text(encoding='latin1')
    predraw = function(source, 'predrawstatus')
    start = predraw.index('    }// end of for\n') + len('    }// end of for\n')
    values = {
        'UPDATE': function(source, 'updatestatus'),
        'STATUS_TAIL': predraw[start:predraw.rindex('}')],
        'VISUAL_DEBUG': function(source, 'obor_collision_attack_frame') + '\n' +
                        function(source, 'draw_visual_debug'),
        'PERFORMANCE': function(source, 'obor_draw_status_performance')
                       if 'static void obor_draw_status_performance(' in source else '',
        'PROFILES': ','.join(str(row['revision']) for row in data['sources']),
    }
    template = Path(__file__).with_name('hud_status_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


class HistoricalHudStatusTests(unittest.TestCase):
    def test_native_overlay_order_and_entry(self):
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
                self.assertEqual(actual['revision'], row['revision'])
                self.assertEqual(actual['overlay'], expected['overlay'])
                self.assertEqual(actual['join'], expected['join'])


if __name__ == '__main__':
    unittest.main()
