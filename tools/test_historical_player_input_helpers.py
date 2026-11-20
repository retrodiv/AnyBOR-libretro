"""Check source-owned player input consumption and helper callback order.

The native helpers execute; special, rise, idle and preinput services are
declared observers. Their internal algorithms and full gameplay are separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-player-input-helpers-contracts.json'
AIRBORNE_FIXTURE = FIXTURE.with_name('profile-airborne-state.json')


def program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    parts = dict(FUNCTIONS='\n'.join(function(core, name) for name in data['functions']),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
                 CASES=',\n'.join('{%s}' % ','.join(str(row[key]) for key in data['parameters'])
                                   for row in data['cases']))
    text = Path(__file__).with_name('player_input_helpers_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native input helper dependency')
    return text


class PlayerInputHelperContracts(unittest.TestCase):
    def check_airborne_state(self, physical):
        data = load_contract_fixture(AIRBORNE_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == physical]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][physical])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / physical))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        names = ('player_fall_check', 'player_jump_check', 'player_lie_check', 'trap_think')
        template = Path(__file__).with_name('airborne_state_contract.c.in').read_text()
        code = (template.replace('@FUNCTIONS@', '\n'.join(function(source, name) for name in names))
                .replace('@ROWS@', ','.join('{%du,%d,%d}' % (row['revision'], row['attack'], row['landing'])
                                          for row in rows)))
        output = native_output(code, {'engine': physical}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_airborne_state(self):
        self.check_airborne_state('4432')

    def test_6391_airborne_state(self):
        self.check_airborne_state('6391')

    def test_native_input_consumption_and_callback_continuation(self):
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
