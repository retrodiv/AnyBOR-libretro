"""Observe the complete native selection and game-entry callers by build.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-saved-character-contracts.json'
FIELDS = ('game', 'with_file', 'mode', 'save_flag', 'menu', 'global_allow', 'saved_skip', 'level_kind',
          'background', 'music_fallback')


def program(data, previous=None):
    engine = ROOT / 'src/engines' / data['engine']
    source = previous if previous is not None else (engine / 'openbor.c').read_text(encoding='latin1')
    utility = (engine / 'source/utils.c').read_text(encoding='latin1')
    storage = re.search(r'(?m)^char[ \t]+skipselect\[[^;\r\n]+;', source)
    if not storage:
        raise ValueError('Native skip selection storage declaration required')
    base = ('#pragma GCC diagnostic push\n'
            '#pragma GCC diagnostic ignored "-Wimplicit-fallthrough"\n' +
            function(source, 'ParseArgs') + '#pragma GCC diagnostic pop\n' +
            '\n'.join(function(source, name) for name in ('isNumeric', 'getValidInt')) +
            '\n' + function(utility, 'getNewLineStart'))
    if 'obor_profile_copy_name(' in source:
        base += '\n' + '\n'.join(function(source, name) for name in
                                 ('obor_profile_name_limit', 'obor_profile_copy_name'))
    values = {
        'BASE': base,
        'NAME_STORAGE': storage[0],
        'RESET': function(source, 'reset_playable_list'),
        'ALLOW': function(source, 'load_playable_list'),
        'NATIVE': '\n'.join(function(source, name) for name in (
            'add_skipselect', 'load_skipselect', 'save_skipselect',
            'load_select_screen_info', 'selectplayer', 'playgame')),
        'RECORD_WRITER': (
            '#if defined(__GNUC__) && !defined(__clang__)\n'
            '#pragma GCC diagnostic push\n'
            '#pragma GCC diagnostic ignored "-Wstringop-truncation"\n'
            '#endif\n'
            '#define savelevelinfo native_savelevelinfo\n' + function(source, 'savelevelinfo') +
            '#undef savelevelinfo\n'
            '#if defined(__GNUC__) && !defined(__clang__)\n'
            '#pragma GCC diagnostic pop\n'
            '#endif\n'),
        'PROFILES': ','.join('{%d,%d}' % (row['revision'], row['allow_extent']) for row in data['sources']),
        'CASES': ',\n'.join('{' + ','.join(str(row[key]) for key in FIELDS) + '}' for row in data['cases']),
    }
    template = Path(__file__).with_name('saved_character_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


class HistoricalSavedCharacterTests(unittest.TestCase):
    def test_native_selection_capture_replay_and_skipselect(self):
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
                self.assertEqual(actual['record_copy'], row['record_copy'])
                self.assertEqual(len(actual['cases']), len(data['cases']))
                for case, result, want in zip(data['cases'], actual['cases'], expected):
                    self.assertEqual(result, want, case['name'])


if __name__ == '__main__':
    unittest.main()
