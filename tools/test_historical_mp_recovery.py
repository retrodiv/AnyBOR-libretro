"""Check native hit MP recovery against each original profile contract.

The complete native function runs on native entity/model records.
Hit eligibility and other energy consumers remain separate contracts.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import sys
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-mp-recovery-contracts.json'


def program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    parts = dict(FUNCTION=function(source, 'checkmpadd'), PROFILES=',\n'.join(
        '{%du,%d,%d}' % (row['revision'], row['zero_rate_is_one'], row['clamp_negative'])
        for row in data['sources']))
    for name in ('magic_types', 'opponents', 'rates', 'initial_mp', 'maximum_mp'):
        values = data[name]
        if (not isinstance(values, list) or not 1 <= len(values) <= 32 or
                any(type(value) is not int or not -64 <= value <= 64 for value in values)):
            raise ValueError('Bounded integer recovery cases required')
        if name == 'opponents' and not set(values) <= {0, 1, 2}:
            raise ValueError('Explicit opponent modes required')
        parts[name.upper()] = ','.join(str(value) for value in values)
    text = Path(__file__).with_name('mp_recovery_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native MP recovery dependency')
    return text


class MpRecoveryContracts(unittest.TestCase):
    def test_native_rate_bounds_and_opponent_gates(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        cases = 1
        for key in ('magic_types', 'opponents', 'rates', 'initial_mp', 'maximum_mp'):
            cases *= len(data[key])
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r, cases=cases) for r in revisions])
        print(json.dumps(dict(contexts=len(actual), cases=cases * len(actual))), file=sys.stderr)


if __name__ == '__main__':
    unittest.main()
