"""Check landing damage eligibility through the native gravity caller.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-landing-damage-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    parts = dict(FUNCTION=function((engine / 'openbor.c').read_text(), 'check_gravity'),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    rows = []
    for row in data['cases']:
        values = [str(v) for v in row]
        if any(re.fullmatch(r'-?[0-9]+|[A-Z][A-Z0-9_]*', v) is None for v in values):
            raise ValueError('Literal or source constant required')
        rows.append('{' + ','.join(values) + '}')
    parts['CASES'] = ','.join(rows)
    code = Path(__file__).with_name('modern_landing_damage_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved landing damage input')
    return code


class ModernLandingDamageContracts(unittest.TestCase):
    def test_health_cheat_type_and_native_landing_gates(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
