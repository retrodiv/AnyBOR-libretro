"""Check native pause samples and song-title debug positioning/lifetime.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from test_early_jump_walkoff import braced_statement
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-pause-debug-contracts.json'


def program(data, engine):
    core = (engine / 'openbor.c').read_text()
    update = function(core, 'update')
    enter = braced_statement(update, 'if(ingame == 1 && !pause && !nopause &&')
    first = update.index('    if(debug_time == 0xFFFFFFFF)')
    debug = update[first:update.index('    if(usevwait)', first)]
    unload = function(core, 'unload_level')
    first = unload.index('    debug_time = 0;')
    unload = unload[first:unload.index('    neon_time = 0;', first)]
    values = dict(LOAD=function(core, 'load_special_sounds'), MUSIC=function(core, 'music'),
        DEBUG=function((engine / 'source/utils.c').read_text(), 'debug_printf'),
        ENTER=enter, DISPLAY=debug, UNLOAD=unload,
        SLOTS=','.join('&'+row['slot'] for row in data['samples']),
        PATHS=','.join(json.dumps(row['path']) for row in data['samples']),
        CONTEXTS=','.join('{%du,%d,%d}' % (row['revision'], row['pause_sample'], row['debug_position'])
                          for row in data['sources']))
    result = Path(__file__).with_name('forward_pause_debug_contract.c.in').read_text()
    for key, value in values.items():
        result = result.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', result):
        raise ValueError('Unresolved native pause/debug provider')
    return result


class ForwardPauseDebugTests(unittest.TestCase):
    def test_native_pause_loading_entry_and_song_title_lifetime(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for row in data['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_PAUSE_DEBUG_ENGINE', ROOT / 'src/engines' / data['engine']))
        rows = [json.loads(line) for line in native_output(program(data, engine), data,
                engine_source=engine).splitlines()]
        self.assertEqual(rows, [dict(revision=row['revision'], status='PASS') for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
