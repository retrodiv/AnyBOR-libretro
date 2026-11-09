"""Check native model palette commands and controlled cleanup diagnostics.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-model-palette-paths.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    body = function((engine / 'openbor.c').read_text(), 'load_cached_model')
    start = body.index('            case CMD_MODEL_PALETTE:')
    end = body.index('            case CMD_MODEL_GLOBALMAP:', start)
    cleanup = body[body.index('lCleanup:'):body.rfind('}')]
    cleanup = cleanup.replace('lCleanup:',
        'lCleanup:\n    cleanup_owners[3]=mapflag;\n    (void)nopalette;', 1)
    parts = dict(COMMANDS=body[start:end], CLEANUP=cleanup,
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    code = Path(__file__).with_name('modern_model_palette_paths_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved model palette input')
    return code


class ModernModelPalettePaths(unittest.TestCase):
    def test_native_model_palette_result_and_cleanup(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
