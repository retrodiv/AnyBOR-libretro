"""Check player action state before and after animation/script callbacks.

The complete native thinker executes selected action paths. Input matching
and delegated services are declared providers, with trigger/ring algorithms
remaining separate contracts.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-player-actions-contracts.json'


def program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    traps = [function(source, name).split('{', 1)[0] + '{abort();}\n'
             for name in data['trapping_services'] if name not in
             ('perform_atchain', 'check_costmove', 'tryjump', 'addscore')]
    text = Path(__file__).with_name('player_actions_contract.c.in').read_text()
    helpers = ['isSubtypeTouch', 'isSubtypeWeapon', 'obor_legacy_player_weapon_allowed',
               'obor_legacy_direction_value']
    available = [function(source, name) for name in helpers if
                 re.search(r'(?m)^(?:static )?(?:unsigned )?int ' + name + r'\(', source)]
    parts = dict(THINKER='\n'.join(available + [function(source, 'player_think')]), DIFF=function(source, 'diff'),
                 TRAPS='\n'.join(traps),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
                 CASES=',\n'.join('{%s}' % ','.join(str(int(row[key])) for key in data['parameters'])
                                   for row in data['cases']))
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native player action dependency')
    return text


class PlayerActionContracts(unittest.TestCase):
    def test_native_action_state_and_callback_continuation(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        for row in data['sources']:
            self.assertEqual(len(data['contracts'][row['contract']]), len(data['cases']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        expected = [(row, i, value) for row in data['sources'] for i, value in
                    enumerate(data['contracts'][row['contract']])]
        self.assertEqual(len(actual), len(expected))
        for result, (row, i, value) in zip(actual, expected):
            with self.subTest(profile=row['revision'], case=data['cases'][i]['name']):
                self.assertEqual(result, dict(revision=row['revision'], case=i, **value))


if __name__ == '__main__':
    unittest.main()
