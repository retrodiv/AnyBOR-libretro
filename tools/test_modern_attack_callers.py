"""Check default attack payloads in item, enemy and time-over callers.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-attack-caller-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    default = re.search(r'(?ms)^const s_attack emptyattack\s*=\s*\{.*?^\};', core)
    velocity = re.search(r'(?ms)^s_axis_principal_float default_model_dropv\s*=\s*\{.*?^\};', core)
    if default is None or velocity is None:
        raise ValueError('Complete default attack and velocity required')
    parts = dict(DEFAULT=default[0], VELOCITY=velocity[0],
        FUNCTIONS='\n'.join(function(core, name) for name in (
            'do_item_script', 'kill_all_enemies', 'kill_all_players_by_timeover')),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=','.join('{' + ','.join(str(v) for v in row) + '}' for row in data['cases']))
    code = Path(__file__).with_name('modern_attack_callers_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved attack caller input')
    return code


class ModernAttackCallerContracts(unittest.TestCase):
    def test_item_enemy_and_timeover_defaults_and_reuse(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
