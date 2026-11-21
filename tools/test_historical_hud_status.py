"""Check the native HUD tail and Start-to-selection routes by source revision.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-hud-status-contracts.json'
HUD_VARIANTS = FIXTURE.with_name('profile-6391-hud-variants.json')


def program(data, source=None):
    if source is None:
        source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text(encoding='latin1')
    predraw = function(source, 'predrawstatus')
    start = predraw.index('    }// end of for\n') + len('    }// end of for\n')
    values = {
        'UPDATE': ('\n'.join(function(source, name) for name in
                             ('obor_profile_name_limit', 'obor_profile_copy_name'))
                   if 'obor_profile_copy_name(' in source else '') + function(source, 'updatestatus'),
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

    def test_6391_original_join_credit_prompt(self):
        self.check_join_credit_prompt(FIXTURE.with_name('profile-6391-join-credit-prompt.json'))

    def test_6391_join_credit_boundaries(self):
        self.check_join_credit_prompt(HUD_VARIANTS)

    def check_join_credit_prompt(self, fixture):
        data = load_contract_fixture(fixture)
        rows = data['sources']
        self.assertEqual({row['revision'] for row in rows}, contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text(encoding='latin1')
        predraw = function(source, 'predrawstatus')
        branch = re.search(r'(?ms)^        else (if\(player\[i\]\.credits \|\| credits \|\| '
                           r'\(!player\[i\]\.hasplayed && noshare\)\).*?)(?=^    \}// end of for)', predraw)[1]
        checks = []
        for row in rows:
            for case, expected in zip(data['cases'], data['messages'][row['family']], strict=True):
                values = ','.join(str(value) for value in case)
                checks.append(f'check({row["revision"]}u,{values},{json.dumps(expected)});')
        template = Path(__file__).with_name('join_credit_prompt_contract.c.in').read_text()
        code = template.replace('@CREDIT_BRANCH@', branch).replace('@CHECKS@', '\n    '.join(checks))
        count = len(rows) * len(data['cases'])
        self.assertEqual(native_output(code, data, engine_source=engine), f'PASS {count}\n')

    def test_6391_original_performance_overlay(self):
        self.check_performance_overlay(FIXTURE.with_name('profile-6391-performance-overlay.json'))

    def test_6391_performance_layer_and_unit_boundaries(self):
        self.check_performance_overlay(HUD_VARIANTS)

    def check_performance_overlay(self, fixture):
        from test_early_jump_walkoff import braced_statement
        data = load_contract_fixture(fixture)
        rows = data['sources']
        self.assertEqual({row['revision'] for row in rows}, contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text(encoding='latin1')
        utilities = (engine / 'source/utils.c').read_text(encoding='latin1')
        predraw = function(source, 'predrawstatus')
        branch = braced_statement(predraw, 'if(savedata.debuginfo)')
        contexts = ',\n'.join('{%du,%d,%d,%d,%d}' % (row['revision'], row['box_layer'], row['text_layer'],
                                data['free_bytes'] // row['byte_divisor'], data['used_bytes'] // row['byte_divisor'])
                                for row in rows)
        template = Path(__file__).with_name('performance_overlay_contract.c.in').read_text()
        code = (template.replace('@SUBJECT@', branch).replace('@FORMAT@', function(utilities, 'commaprint'))
                .replace('@CONTEXTS@', contexts).replace('@FREE_BYTES@', str(data['free_bytes']))
                .replace('@USED_BYTES@', str(data['used_bytes'])))
        self.assertEqual(native_output(code, data, engine_source=engine), f'PASS {len(rows)}\n')

    def test_6391_original_entity_collision_overlay(self):
        from test_early_jump_walkoff import braced_statement
        data = load_contract_fixture(HUD_VARIANTS)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text(encoding='latin1')
        gate = braced_statement(function(source, 'predrawstatus'), 'if(savedata.debug_position')
        cases = '\n    '.join('check(%du, %du);' % (row['revision'], row['entity_collision_draw'])
                             for row in rows)
        template = Path(__file__).with_name('entity_collision_overlay_contract.c.in').read_text()
        code = (template.replace('@DRAW@', function(source, 'draw_visual_debug'))
                .replace('@ENTRY@', gate).replace('@CASES@', cases))
        self.assertEqual(native_output(code, data, engine_source=engine),
                         ''.join(f'PASS {revision}\n' for revision in revisions))


if __name__ == '__main__':
    unittest.main()
