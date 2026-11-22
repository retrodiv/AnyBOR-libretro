"""Check source-specific saved-file bytes and completion/menu state.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import tempfile
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-progress-record-contracts.json'


def conditional(source, marker):
    start = source.rfind(marker)
    if start < 0:
        raise ValueError('Missing native progress branch')
    opening = source.index('{', start)
    depth = 1
    for end in range(opening + 1, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end + 1]
    raise ValueError('Incomplete native progress branch')


def program(data, kind):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    source = (engine / 'openbor.c').read_text()
    parts = dict(PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    if kind in ('records', 'android'):
        names = ('obor_profile_record_io', 'obor_profile_settings_io',
                 'obor_profile_game_record_size', 'obor_profile_game_io',
                 'savesettings', 'saveasdefault', 'loadsettings', 'loadfromdefault',
                 'clearSavedGame', 'clearHighScore', 'saveGameFile', 'loadGameFile',
                 'saveHighScoreFile', 'loadHighScoreFile')
        parts['FUNCTIONS'] = '\n'.join(function(source, name) for name in names)
        parts['CASES'] = ',\n'.join('{' + ','.join(str(row[key]) for key in
            ('kind', 'base', 'delta', 'bad_signature', 'failed_open', 'missing')) + '}'
            for row in data['cases'])
        template = 'modern_progress_records_contract.c.in'
    elif kind == 'completion':
        parts['COMPLETION'] = conditional(function(source, 'playgame'),
                                         'if(current_level >= set->numlevels)')
        parts['MISSING'] = conditional(function(source, 'load_saved_game'),
                                      'if(saveslot >= num_difficulties)')
        template = 'modern_progress_completion_contract.c.in'
    else:
        raise ValueError('Declared progress contract kind required')
    code = Path(__file__).with_name(template).read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved native progress dependency')
    return ('#define ANDROID 1\n' if kind == 'android' else '') + code


class ModernProgressRecordContracts(unittest.TestCase):
    def test_original_input_recording_layout(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        row = re.search(r'typedef struct\s*\{[^{}]+\}\s*obor_replay_row_32;', source)
        self.assertIsNotNone(row)
        methods = ('obor_read_replay', 'obor_write_replay', 'recordInputs', 'playRecordedInputs',
                   'stopRecordInputs', 'freeRecordedInputs')
        template = Path(__file__).with_name('modern_replay_contract.c.in').read_text()
        with tempfile.TemporaryDirectory(prefix='anybor-replay-records-') as directory:
            code = (template.replace('@RECORD@', row[0])
                    .replace('@METHODS@', '\n'.join(function(source, name) for name in methods))
                    .replace('@DIRECTORY@', json.dumps(Path(directory).as_posix() + '/')))
            self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine, libraries=('m',)), '')

    def run_contract(self, kind):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']][kind]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data, kind), data)), expected)

    def test_settings_game_and_score_file_bytes_and_reads(self):
        self.run_contract('records')

    def test_completion_and_missing_save_selection(self):
        self.run_contract('completion')

    def test_android_settings_record_tail(self):
        self.run_contract('android')


if __name__ == '__main__':
    unittest.main()
