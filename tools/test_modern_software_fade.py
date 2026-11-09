"""Check the native software fade when host color correction is unavailable.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-software-fade-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    port = Path(os.environ.get('OBOR_TEST_PORT', ROOT / 'src/port/libretro'))
    source = (engine / 'openbor.c').read_text()
    match = re.search(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{', source)
    if match is None:
        raise ValueError('Native default drawmethod required')
    parts = dict(DEFAULT=source[match.start():source.index('\n};', match.end()) + 3],
        BACKEND=function((port / 'video.c').read_text(), 'video_set_color_correction'),
        FUNCTIONS='\n'.join(function(source, name) for name in ('set_color_correction', 'fade_out')),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    code = Path(__file__).with_name('modern_software_fade_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved software fade input')
    return code


class ModernSoftwareFadeContracts(unittest.TestCase):
    def test_native_fade_uses_available_software_path(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
