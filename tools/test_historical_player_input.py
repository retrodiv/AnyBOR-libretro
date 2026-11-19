"""Verify the backward-run and charge-release routes in the native player code.

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


FIXTURE = Path(__file__).with_name('fixtures') / 'profile-player-input-contracts.json'


def between(source, first, following):
    start = source.index(first)
    return source[start:source.index(following, start + len(first))]


def program(data, engine):
    source = (engine / 'openbor.c').read_text(encoding='latin1')
    player = function(source, 'player_think')
    walk = function(source, 'adjust_walk_animation')
    setter = function(source, 'ent_set_anim')
    names = ['obor_profile_animation_base', 'match_combo', 'is_in_backrun']
    if 'charge_release_animation' in source:
        names.append('charge_release_animation')
    parts = {
        'HELPERS': '\n'.join(function(source, name) for name in names),
        'ANIMATION_GATE': setter[setter.index('{') + 1:setter.index('    ani = ')],
        'MOVE_INPUT': between(player, '    if((pl->playkeys & (FLAG_MOVELEFT | FLAG_MOVERIGHT)))',
                              '    if(!ajspecial'),
        'WALK_SELECTION': between(walk, '    if(self->running)', '    if(validanim(self, ANI_UP)'),
        'THINK_SELECTION': between(player, '    case 4:', '    default:'),
        'RELEASE_INPUT': between(player, '    if((pl->releasekeys & FLAG_ATTACK))',
                                 '    if((pl->playkeys & FLAG_ATTACK)'),
        'PROFILES': ','.join(str(row['revision']) for row in data['sources']),
    }
    for kind in ('movement', 'running', 'charge'):
        parts[kind.upper()] = ',\n'.join('{' + ','.join(map(str, row['input'])) + '}'
                                        for row in data['cases'][kind])
    template = Path(__file__).with_name('player_input_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda field: parts[field[1]], template)


class HistoricalPlayerInputTests(unittest.TestCase):
    def test_native_double_taps_running_and_charge_release(self):
        data = load_contract_fixture(FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = ROOT / 'src/engines' / data['engine']
        results = [json.loads(line) for line in native_output(program(data, engine), data).splitlines()]
        self.assertEqual(len(results), len(rows))
        for row, (revision, observed) in zip(rows, results):
            self.assertEqual(row['revision'], revision)
            expected = data['contracts'][row['contract']]
            for group, actual in zip(('movement', 'running', 'charge'), observed, strict=True):
                self.assertEqual(len(actual), len(expected[group]))
                for scenario, got, want in zip(data['cases'][group], actual, expected[group], strict=True):
                    with self.subTest(revision=revision, scenario=scenario['name']):
                        self.assertEqual(got, want)


if __name__ == '__main__':
    unittest.main()
