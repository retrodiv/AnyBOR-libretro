"""Check saved-game slots, file bytes and validation against own-source contracts.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-level-save-contracts.json'


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    end = re.search(r'\}\s*s_savelevel\s*;', header)
    if end is None:
        raise AssertionError('Missing saved-game record')
    record = header[header.rfind('typedef struct', 0, end.start()):end.end()]
    constants = []
    for name in ('MAX_NAME_LEN', 'MAX_PLAYERS', 'MAX_DIFFICULTIES', 'CV_SAVED_GAME'):
        match = re.search(r'^#define\s+' + name + r'\s+[^\n]+', header, re.M)
        if match is None:
            raise AssertionError('Missing own constant ' + name)
        constants.append(match[0])
    helper = function(source, 'obor_legacy_saved_game') if 'obor_legacy_saved_game(' in source else ''
    constructor = function(source, 'load_levelorder')
    initialization = re.search(r'(?:if\(obor_profile_build < 3666\) savelevel = obor_legacy_saved_game\(\);\s*else )?'
        r'if\(!savelevel\) savelevel = calloc\(num_difficulties, sizeof\(s_savelevel\)\);', constructor)
    if initialization is None:
        raise AssertionError('Missing saved-game storage initialization')
    text = Path(__file__).with_name('level_save_contract.c.in').read_text()
    substitutions = dict(CONSTANTS='\n'.join(constants), RECORD=record, HELPER=helper,
        CLEAR=function(source, 'clearSavedGame'), SAVE=function(source, 'saveGameFile'),
        LOAD=function(source, 'loadGameFile'), INITIALIZE=initialization[0],
        RECORD_BYTES=','.join(str(value) for value in bytes.fromhex(data['record_hex'])),
        CONTEXTS=','.join('{%d,%d,%d}' % (r['revision'], r['fixed_slots'], r['invalid_returns_failure'])
                          for r in data['sources']))
    for name, value in substitutions.items():
        text = text.replace('@' + name + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise AssertionError('Unresolved saved-game probe input')
    return text


class HistoricalLevelSaveContracts(unittest.TestCase):
    def test_slots_record_bytes_clear_and_file_validation(self):
        data = load_contract_fixture(FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['fixed_slots'], row['revision'] < 3666)
            self.assertEqual(row['invalid_returns_failure'], row['revision'] >= 3708)
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], cases=60) for row in rows])


if __name__ == '__main__':
    unittest.main()
