"""Check real music producers with bounded file and codec observers.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output, ogg_configuration
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-music-lifecycle-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    source = (engine / 'source/gamelib/soundmix.c').read_text()
    types = {m[1]: m[0] for m in re.finditer(
        r'(?ms)^typedef struct(?:\s+\w+)?\s*\{.*?^\}\s*(\w+)\s*;', source)}
    declaration = re.search(r'(?ms)^musicchannelstruct musicchannel\s*=\s*\{[^}]*\}\s*;', source)
    if 'bor_header' not in types or declaration is None:
        raise ValueError('Complete source-owned music representation required')
    defines = []
    for name in ('BOR_IDENTIFIER', 'BOR_MUSIC_VERSION_MONO', 'BOR_MUSIC_VERSION_STEREO'):
        match = re.search(r'(?m)^#define\s+' + name + r'\b[^\n]*', source)
        if match is None:
            raise ValueError('Source-owned music header definition required')
        defines.append(match[0])
    names = ('sound_music_channel_clear', 'sound_close_adpcm', 'sound_open_adpcm',
             'sound_update_adpcm', 'sound_query_adpcm', 'sound_close_ogg', 'sound_open_ogg',
             'sound_query_ogg', 'sound_close_music', 'sound_query_music')
    parts = dict(TYPE=types['bor_header'], GLOBAL=declaration[0], DEFINES='\n'.join(defines),
        FUNCTIONS='\n'.join(function(source, name) for name in names),
        PROFILES=','.join(str(s['revision']) + 'u' for s in data['sources']),
        CASES=','.join('{' + ','.join(str(n) for n in row) + '}' for row in data['cases']))
    code = Path(__file__).with_name('modern_music_lifecycle_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved music lifecycle input')
    return code


class ModernMusicLifecycleContracts(unittest.TestCase):
    def test_open_update_query_close_and_channel_class(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({s['revision'] for s in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', header_size=160, profiles=[
            dict(revision=s['revision'], **data['contracts'][s['contract']]) for s in data['sources']])
        includes = [ROOT / 'src/deps' / name / 'include' for name in data['dependencies']]
        self.assertEqual(json.loads(native_output(program(data), data, extra_includes=includes,
                                                 configure_ogg=True)), expected)

    def test_unrecognized_ogg_configuration_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unresolved vendored Ogg'):
            ogg_configuration('typedef @UNKNOWN_INTEGER_TYPE@ ogg_int64_t;')


if __name__ == '__main__':
    unittest.main()
