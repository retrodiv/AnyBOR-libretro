"""Check complete native palette loader bytes and transport observations.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-palette-loading-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    parts = dict(FUNCTION=function((engine / 'openbor.c').read_text(), 'load_palette'),
                 COLOR=function((engine / 'source/gamelib/pixelformat.c').read_text(), 'colour32'),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
                 OFFSETS=','.join(str(value) for value in data['byte_offsets']),
                 CASES=','.join('{%s,%d,%d,%d}' % (json.dumps(row['path']), row['length'],
                     row['open_failed'], row['image_result']) for row in data['cases']))
    code = Path(__file__).with_name('modern_palette_loading_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved palette loader contract input')
    return code


class ModernPaletteLoadingContracts(unittest.TestCase):
    def test_native_palette_loader_complete_bytes_and_bounds(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
