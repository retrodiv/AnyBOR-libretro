"""Check source-owned music dispatch and inactive/unknown modes.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-music-dispatch-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    source = (engine / 'source/gamelib/soundmix.c').read_text()
    declaration = re.search(r'(?m)^static (?:int|e_sound_file_type) music_type\s*=\s*[^;]+;', source)
    if declaration is None:
        raise ValueError('Source-owned initial music mode required')
    parts = dict(DECLARATION=declaration[0],
        FUNCTIONS='\n'.join(function(source, name) for name in (
            'sound_close_music', 'sound_update_music', 'sound_query_music', 'sound_music_tempo')),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        MODES=','.join(str(mode) for mode in data['modes']))
    code = Path(__file__).with_name('modern_music_dispatch_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved music dispatch input')
    return code


class ModernMusicDispatchContracts(unittest.TestCase):
    def test_dispatch_queries_tempo_and_close(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({s['revision'] for s in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', initial_mode=0, file_modes=[-1,0,1], profiles=[
            dict(revision=s['revision'], **data['contracts'][s['contract']]) for s in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
