"""Check native combined/split HUD effects and their frame call ordering.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-hud-schedule-contracts.json'


def native_declarations(core):
    # Use the candidate's actual declarations and native packed types, not a
    # substitute layout. The small counter helpers in this prefix stay unused.
    start = core.index('#include "openbor.h"')
    stop = core.index('void setDrawMethod(')
    declarations = core[start:stop]
    # These unused raster callback tables are outside the HUD observation.
    # Keep their native types/storage, with inert provider initializers.
    declarations, count = re.subn(
        r'(?m)^((?:palette_table_function|blend_table_function)\s+'
        r'blending_table_functions(?:16|32)?\[[^\]]+\])\s*=\s*\{[^}]*\};',
        r'\1 = {0};', declarations)
    if count != 3:
        raise AssertionError('Missing declared raster callback providers')
    return declarations


def program(data, *, zoom_checks=False, model_checks=False):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    declarations = native_declarations(core)
    native = '\n'.join(function(core, name) for name in
        ('obor_legacy_predrawstatus', 'updatestatus', 'predrawstatus')) if (
            'static void obor_legacy_predrawstatus(' in core) else '\n'.join(
                function(core, name) for name in ('updatestatus', 'predrawstatus'))
    native = function(core, 'model_get_colourmap') + '\n' + native
    if model_checks:
        native = ('#define printf model_log\n' + '\n'.join(function(core, name)
            for name in ('prevplayermodel', 'nextplayermodel')) +
            '\n#undef printf\n' + native)
    update = function(core, 'update')
    start = update.index('if(obor_profile_build < 3552)\n    {') if (
        'if(obor_profile_build < 3552)\n    {' in update) else update.index('/************ gfx queueing')
    # Observe the complete graphics phase through its final ordinary queue draw.
    # Screenshot,debug overlay and music have independent source contracts.
    phase = update[start:update.index('if(pause!=2 && !noscreenshot', start)]
    text = Path(__file__).with_name('hud_schedule_contract.c.in').read_text()
    contexts = ('{0,0,0,0,0}' if model_checks else ','.join(
        '{%d,%d,%d,%d,%d}' % (row['revision'], row['combined_status'],
         row['canvas_phase'], row['pause_queue'], row['background_depth_zero'])
        for row in data['sources']))
    fields = dict(DECLARATIONS=declarations, NATIVE=native, PHASE=phase, ZOOM_CHECKS=str(int(zoom_checks)),
        MODEL_CHECKS=str(int(model_checks)),
        MODEL_SERVICES=Path(__file__).with_name('hud_model_lookup_contract.c.in').read_text()
                       if model_checks else '',
        MODEL_CONTEXTS=','.join('{%d,%d}' % (row['revision'], row['epoch'])
                               for row in data['sources']) if model_checks else '{0,0}',
        SAVEDATA='' if re.search(r'(?m)^s_savedata\s+savedata\s*;', declarations)
        else 's_savedata savedata;',
        CONTEXTS=contexts)
    for name, value in fields.items():
        text = text.replace('@' + name + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise AssertionError('Unresolved native HUD input')
    return text


class HistoricalHudScheduleContracts(unittest.TestCase):
    def test_native_join_timer_go_and_frame_order(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r, cases=684, status='PASS') for r in revisions])

    def test_native_zoom_complete_frame_order_and_release(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data, zoom_checks=True), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r, cases=144, status='PASS') for r in revisions])


class PauseCaptureContracts(unittest.TestCase):
    def test_native_pause_capture_input_and_release_order(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') /
                                     'profile-pause-capture-contracts.json')
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        declarations = native_declarations(core)
        values = dict(DECLARATIONS=declarations, NATIVE=function(core, 'pausemenu'),
            SAVEDATA='' if re.search(r'(?m)^s_savedata\s+savedata\s*;', declarations)
            else 's_savedata savedata;',
            CONTEXTS=','.join('{%d,%d}' % (row['revision'], row['capture'])
                              for row in data['sources']))
        text = Path(__file__).with_name('pause_capture_contract.c.in').read_text()
        for key, value in values.items():
            text = text.replace('@' + key + '@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        self.assertEqual(actual, [dict(revision=r, cases=14, status='PASS') for r in revisions])


class HudModelLookupContracts(unittest.TestCase):
    def test_native_selection_lookup_order_and_carried_model(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') /
                                     'profile-hud-model-lookup-contracts.json')
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data, model_checks=True), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r, cases=192, status='PASS') for r in revisions])


if __name__ == '__main__':
    unittest.main()
