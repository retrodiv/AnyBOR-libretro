"""Check profile-owned blockpain and running-state transitions.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-combat-running-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    parts = dict(FUNCTIONS='\n'.join(function(core, name) for name in (
        'check_blocking_pain', 'set_idle', 'set_fall')),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    for key in ('block_cases', 'idle_cases', 'fall_cases'):
        rows = []
        for row in data[key]:
            values = [str(value) for value in row]
            if any(re.fullmatch(r'-?[0-9]+|[A-Z][A-Z0-9_]*', v) is None for v in values):
                raise ValueError('Contract inputs must be literals or source constants')
            rows.append('{' + ','.join(values) + '}')
        parts[key.upper()] = ','.join(rows)
    code = Path(__file__).with_name('modern_combat_running_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved combat/running contract input')
    return code


class ModernCombatRunningContracts(unittest.TestCase):
    def test_blockpain_and_running_callback_order(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(
            revision=row['revision'], **data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
