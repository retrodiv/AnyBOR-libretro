"""Check the native action state changes around optional animation clips.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function


FIXTURE = Path(__file__).with_name('fixtures') / 'profile-action-availability-contracts.json'
GROUPS = ('chain', 'grab', 'bomb', 'warp', 'special')


def program(data, engine):
    source = (engine / 'openbor.c').read_text(encoding='latin1')
    functions = ('diff', 'inair', 'perform_atchain', 'dograbattack',
                 'bomb_move', 'ai_check_warp', 'check_energy', 'check_special')
    setter = function(source, 'ent_set_anim')
    table = re.search(r'(?m)^int[ \t]+grab_attacks\[5\]\[2\]\s*=\s*\{[^;]+\};', source)
    if table is None:
        raise ValueError('Missing native grab animation table')
    parts = {
        'NATIVE': '\n'.join(function(source, name) for name in functions),
        'ANIMATION_GATE': setter[setter.index('{') + 1:setter.index('    ani = ')],
        'GRAB_TABLE': table[0],
        'PROFILES': ','.join(str(row['revision']) for row in data['sources']),
    }
    for group in GROUPS:
        parts[group.upper()] = ',\n'.join(
            '{' + ','.join(map(str, row['input'])) + '}' for row in data['cases'][group])
    template = Path(__file__).with_name('action_availability_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda token: parts[token[1]], template)


class HistoricalActionAvailabilityTests(unittest.TestCase):
    def test_native_state_with_declared_and_missing_clips(self):
        data = load_contract_fixture(FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = ROOT / 'src/engines' / data['engine']
        actual = [json.loads(line) for line in native_output(program(data, engine), data).splitlines()]
        self.assertEqual(len(actual), len(rows))
        for row, (revision, observed) in zip(rows, actual, strict=True):
            self.assertEqual(revision, row['revision'])
            expected = data['contracts'][row['contract']]
            for group, cases in zip(GROUPS, observed, strict=True):
                for scenario, result, want in zip(data['cases'][group], cases, expected[group], strict=True):
                    with self.subTest(revision=revision, scenario=scenario['name']):
                        self.assertEqual(result, want)


if __name__ == '__main__':
    unittest.main()
