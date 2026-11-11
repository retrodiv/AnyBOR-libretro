"""Preserve fixed saved bytes and valid restored player-name bytes.

Native copy/termination statements run with real record types. Complete saved
stream loading, game entry and player/model lifetime remain separate controls.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture
from test_historical_player import function
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))
FIXTURE = HERE / 'fixtures/saved-player-name-native-baseline.json'


def program(engine, profiles, *, mode='normal'):
    oracle = load_contract_fixture(FIXTURE)
    data = oracle['engines'][engine.name]
    source = function((engine / 'openbor.c').read_text(encoding='latin1'), 'playgame')
    copy = data['copy']
    if source.count(copy) != 1:
        raise ValueError('One native fixed player-name restore required')
    tail = source[source.index(copy) + len(copy):]
    match = re.match(r'\s*(if\(!memchr\(player\[i\]\.name, 0, sizeof\(player\[i\]\.name\)\)\)\s*'
                     r'player\[i\]\.name\[sizeof\(player\[i\]\.name\) - 1\] = 0;)', tail)
    if match is None:
        raise ValueError('The native restore must supply its own termination check')
    guard = match[1]
    if mode == 'omit':
        guard = ''
    elif mode == 'unconditional':
        guard = 'player[i].name[sizeof(player[i].name) - 1] = 0;'
    elif mode != 'normal':
        raise ValueError('Unknown name-restore control')
    header = (engine / 'openbor.h').read_text(encoding='latin1')
    storage = '#define records savelevel' if re.search(r'^s_savelevel\s+savelevel\[', header, re.M) else (
        'static s_savelevel records[2];\ns_savelevel *savelevel=records;')
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        SCRIPT_HEADER='openborscript.h' if (engine / 'openborscript.h').is_file() else 'scriptcommon.h',
        SAVE_STORAGE=storage, BEFORE=copy, AFTER=copy+'\n'+guard,
        PROFILES=','.join(str(oracle['profiles'][p['build']]['revision'])+'u' for p in profiles))
    text = (HERE / 'saved_player_name_restore.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native player-name restore input')
    return text


class SavedPlayerNameRestoreTests(unittest.TestCase):
    def test_valid_bytes_saved_records_and_defined_live_names_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        self.assertEqual(set(load_contract_fixture(FIXTURE)['profiles']), {p['build'] for p in pin['profiles']})
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == engine.name]
            with self.subTest(engine=engine.name):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout),
                                 dict(status='PASS', profiles=len(profiles), cases=80 * len(profiles)))

    def control(self, mode, diagnostic):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines' / pin['engines'][0]['build']
        profile = next(p for p in pin['profiles'] if p['engine'] == engine.name)
        result = run_native(engine, program(engine, [profile], mode=mode))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(diagnostic, result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)

    def test_missing_termination_is_detected_without_scanning_past_field(self):
        self.control('omit', 'memchr(player[i].name,0,sizeof(player[i].name))')

    def test_already_valid_destination_bytes_are_preserved(self):
        self.control('unconditional', '!memcmp(player,expected_players,sizeof(player))')


if __name__ == '__main__':
    unittest.main()
