"""Check native player item geometry, candidate filtering and lookup extent.

The complete thinker and its item predicates execute. Animation, item handling
and unrelated gameplay services are declared observers or traps.
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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-player-items-contracts.json'


def program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    names = list(data['functions'])
    if re.search(r'(?m)^static int obor_legacy_player_weapon_allowed\(', core):
        names.append('obor_legacy_player_weapon_allowed')
    if re.search(r'(?m)^static unsigned int obor_legacy_direction_value\(', core):
        names.append('obor_legacy_direction_value')
    traps = [function(core, name).split('{', 1)[0] + '{abort();}\n'
             for name in data['trapping_services'] if name != 'sound_play_sample']
    parts = dict(FUNCTIONS='\n'.join(function(core, name) for name in names),
                 THINKER=function(core, 'player_think'), TRAPS='\n'.join(traps),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
                 CASES=',\n'.join('{%s}' % ','.join(str(row[key]) for key in data['parameters'])
                                   for row in data['cases']))
    text = Path(__file__).with_name('player_items_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native player item dependency')
    return text


class PlayerItemContracts(unittest.TestCase):
    def test_native_parent_geometry_filtering_and_lookup_extent(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        expected = [(row, i, value) for row in data['sources'] for i, value in
                    enumerate(data['contracts'][row['contract']])]
        self.assertEqual(len(actual), len(expected))
        for result, (row, i, value) in zip(actual, expected):
            with self.subTest(profile=row['revision'], case=data['cases'][i]['name']):
                self.assertEqual(result, dict(revision=row['revision'], case=i, result=value))


if __name__ == '__main__':
    unittest.main()
