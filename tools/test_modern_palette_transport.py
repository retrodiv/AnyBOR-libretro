"""Check native palette bytes, failure results and standard-palette copying.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-palette-transport-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    parts = dict(FUNCTIONS='\n'.join(function(core, name) for name in ('load_palette', 'standard_palette')),
                 COLOR=function((engine / 'source/gamelib/pixelformat.c').read_text(), 'colour32'),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
                 CASES=','.join('{' + ','.join(str(row[key]) for key in data['parameters']) + '}'
                                for row in data['cases']))
    code = Path(__file__).with_name('modern_palette_transport_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved palette loader contract input')
    return code


class ModernPaletteTransportContracts(unittest.TestCase):
    def test_native_palette_bytes_and_standard_palette_copy(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
