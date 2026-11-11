"""Check music title messages and the native WebM audio initializer.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-music-producer-contracts.json'


def program(data, kind):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    profiles = ','.join(str(row['revision']) + 'u' for row in data['sources'])
    if kind == 'music':
        parts = dict(FUNCTION=function((engine / 'openbor.c').read_text(), 'music'), PROFILES=profiles,
            CASES=','.join('{' + ','.join(str(n) for n in row) + '}' for row in data['music_cases']))
        template = 'modern_music_message_contract.c.in'
    elif kind == 'webm':
        source = (engine / 'source/webmlib/vidplay.c').read_text()
        types = {m[1]: m[0] for m in re.finditer(r'(?ms)^typedef struct\s*\{.*?^}\s*(\w+)\s*;', source)}
        if not {'FixedSizeQueue', 'audio_context'} <= set(types):
            raise ValueError('Complete native media context types required')
        count = re.search(r'(?m)^#define\s+PACKET_QUEUE_SIZE\b[^\n]*', source)
        if count is None:
            raise ValueError('Native packet queue bound required')
        parts = dict(TYPES=types['FixedSizeQueue'] + '\n' + types['audio_context'], QUEUE_BOUND=count[0],
            FUNCTIONS='\n'.join(function(source, n) for n in ('init_audio', 'close_audio')),
            CLEAR=function((engine / 'source/gamelib/soundmix.c').read_text(), 'sound_music_channel_clear'),
            PROFILES=profiles, CASES=','.join('{' + ','.join(str(n) for n in row) + '}' for row in data['webm_cases']))
        template = 'modern_webm_audio_init_contract.c.in'
    else:
        raise ValueError('Declared music producer contract kind required')
    code = Path(__file__).with_name(template).read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved music producer contract input')
    return code


class ModernMusicProducerContracts(unittest.TestCase):
    def run_contract(self, kind):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']][kind]) for row in data['sources']])
        includes = [ROOT / 'src/deps' / name / 'include' for name in data['dependencies']] if kind == 'webm' else []
        self.assertEqual(json.loads(native_output(program(data, kind), data, extra_includes=includes,
                                                 configure_ogg=kind == 'webm')), expected)

    def test_music_messages_and_translation_requests(self):
        self.run_contract('music')

    def test_native_webm_audio_channel_initialization_and_close(self):
        self.run_contract('webm')


if __name__ == '__main__':
    unittest.main()
