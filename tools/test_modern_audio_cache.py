"""Check source-owned sample caching, list selection and initialization.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-audio-cache-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    source = (engine / 'source/gamelib/soundmix.c').read_text()
    wanted = ('channelstruct', 'samplestruct', 's_soundcache', 's_sound_parameters', 's_audio_global')
    typedefs = {m[1]: m[0] for m in re.finditer(
        r'(?ms)^typedef struct(?:\s+\w+)?\s*\{.*?^\}\s*(\w+)\s*;', source) if m[1] in wanted}
    if set(typedefs) != set(wanted):
        raise ValueError('Complete source-owned audio types required')
    globals_ = []
    for declaration in ('s_sound_parameters sound_parameters', 's_audio_global audio_global'):
        match = re.search(r'(?ms)^' + declaration + r'\s*=\s*\{[^}]*\}\s*;', source)
        if match is None:
            raise ValueError('Complete source-owned audio initializer required')
        globals_.append(match[0])
    definitions = []
    for name in ('MAX_CHANNELS', 'MIXBUF_SIZE', 'SB_BUFFER_SIZE', 'OBOR_AUDIO_SAMPLE_LIST'):
        match = re.search(r'(?m)^#define\s+' + name + r'\b[^\n]*', source)
        if match is None:
            raise ValueError('Source-owned mixer definition required')
        definitions.append(match[0])
    parts = dict(TYPES='\n'.join(typedefs[name] for name in wanted), GLOBALS='\n'.join(globals_),
        DEFINITIONS='\n'.join(definitions),
        FUNCTIONS='\n'.join(function(source, name) for name in (
            'sound_profile_sample_limit', 'sound_profile_sample_play_id', 'sound_reload_sample',
            'sound_load_sample', 'sound_unload_sample', 'sound_unload_all_samples',
            'sound_init', 'sound_exit')),
        LOWERCASE=function((engine / 'source/utils.c').read_text(), 'lc'),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        NAME=json.dumps(data['name']), ALIAS=json.dumps(data['alias']),
        RELOAD_NAME=json.dumps(data['reload_name']), SECOND=json.dumps(data['second']),
        FAILURE=json.dumps(data['failure']), ARCHIVE=json.dumps(data['archive']))
    code = Path(__file__).with_name('modern_audio_cache_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved cache contract input')
    return code


class ModernAudioCacheContracts(unittest.TestCase):
    def test_cache_list_lifecycle_and_sample_ids(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[
            dict(revision=row['revision'], **data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
