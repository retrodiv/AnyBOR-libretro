"""Check profile-owned energy admission and its non-monotonic seal boundary.

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


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-energy-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    body = function((engine / 'openbor.c').read_text(), 'check_energy')
    rows = []
    for case in data['cases']:
        values = [str(case[name]) for name in data['case_fields']]
        if any(re.fullmatch(r'-?[0-9]+|[A-Z][A-Z0-9_]*', value) is None
               for value in values):
            raise ValueError('Expected a literal or named source constant')
        rows.append('{' + ','.join(values) + '}')
    parts = dict(FUNCTION=body, CASES=',\n'.join(rows),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    code = Path(__file__).with_name('modern_energy_contract.c.in').read_text()
    for name, value in parts.items():
        code = code.replace('@' + name + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved energy contract input')
    return code


class ModernEnergyContracts(unittest.TestCase):
    def test_energy_admission_and_both_seal_boundaries(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        for row in data['sources']:
            self.assertEqual(len(data['contracts'][row['contract']]), len(data['cases']))
        actual = json.loads(native_output(program(data), data))
        expected = dict(status='PASS', profiles=[
            dict(revision=row['revision'], results=data['contracts'][row['contract']])
            for row in data['sources']])
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
