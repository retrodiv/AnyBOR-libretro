"""Check source-owned mixer sums, positions, volume caps and sample IDs.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-audio-mixer-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    source = (engine / 'source/gamelib/soundmix.c').read_text()
    wanted = ('channelstruct', 'samplestruct', 's_soundcache', 's_sound_parameters', 's_audio_global')
    typedefs = {m[1]: m[0] for m in re.finditer(
        r'(?ms)^typedef struct(?:\s+\w+)?\s*\{.*?^\}\s*(\w+)\s*;', source) if m[1] in wanted}
    if set(typedefs) != set(wanted):
        raise ValueError('Complete source-owned audio types required')
    globals_ = []
    for declaration in ('s_sound_parameters sound_parameters', 's_audio_global audio_global',
                        'musicchannelstruct musicchannel'):
        match = re.search(r'(?ms)^' + declaration + r'\s*=\s*\{[^}]*\}\s*;', source)
        if match is None:
            raise ValueError('Complete source-owned audio initializer required')
        globals_.append(match[0])
    parts = dict(TYPES='\n'.join(typedefs[name] for name in wanted), GLOBALS='\n'.join(globals_),
        FUNCTIONS='\n'.join(function(source, name) for name in (
            'sound_profile_sample_limit', 'sound_profile_sample_play_id', 'obor_audio_next_sample_id',
            'sound_music_channel_clear', 'sound_reload_sample', 'mixaudio', 'sound_play_sample',
            'sound_volume_sample', 'sound_volume_music')),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    for key in ('mix_cases', 'play_cases', 'volume_cases'):
        parts[key.upper()] = ','.join('{' + ','.join(str(v) for v in row) + '}' for row in data[key])
    code = Path(__file__).with_name('modern_audio_mixer_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved mixer contract input')
    return code


class ModernAudioMixerContracts(unittest.TestCase):
    def test_mixer_sums_fixed_positions_limits_and_counters(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', initial_music_class=7, sizes=[40,24,36], profiles=[
            dict(revision=row['revision'], **data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
