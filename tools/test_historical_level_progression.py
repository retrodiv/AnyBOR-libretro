"""Check native level progression and saved-player updates by profile.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_early_jump_walkoff import braced_statement
from test_historical_common_think import ROOT, native_output
from test_historical_level_consumers import program as consumer_program
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-level-progression-contracts.json'


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    prefix = consumer_program(data, 1)
    prefix = prefix[:prefix.index('int main(void)')]
    end = re.search(r'\}\s*s_savescore\s*;', header)
    if end is None:
        raise AssertionError('Missing native score record')
    record = header[header.rfind('typedef struct', 0, end.start()):end.end()]
    hall = braced_statement(function(source, 'hallfame'), 'if(addtoscore)')
    values = dict(SCORE_RECORD=record, HALL=hall,
        PACK=re.search(r'^#pragma pack\(push,\s*\d+\)', header, re.M)[0],
        SAVE=function(source, 'savelevelinfo'), GAME=function(source, 'playgame'),
        CONTEXTS=','.join('{%d,%d,%d,%d}' % (r['revision'], r['fixed_slots'],
            r['completion_score_save'], r['restore_playable_list']) for r in data['sources']))
    tail = Path(__file__).with_name('level_progression_contract.c.in').read_text()
    for name, value in values.items():
        tail = tail.replace('@' + name + '@', value)
    if re.search(r'@[A-Z_]+@', tail):
        raise AssertionError('Unresolved level progression input')
    return prefix + tail


class HistoricalLevelProgressionContracts(unittest.TestCase):
    def test_saved_players_branches_and_completion(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r, cases=37, status='PASS') for r in revisions])


if __name__ == '__main__':
    unittest.main()
