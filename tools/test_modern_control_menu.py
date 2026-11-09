"""Check native control menu selection, rumble and binding transactions.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-control-menu-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    parts = dict(FUNCTION=function((engine / 'openbor.c').read_text(), 'keyboard_setup'),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    code = Path(__file__).with_name('modern_control_menu_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved control menu input')
    return code


class ModernControlMenuContracts(unittest.TestCase):
    def test_native_menu_commit_cancel_default_and_rumble(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
