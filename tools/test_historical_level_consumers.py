"""Check native fixed-slot selection, unlocks and saved-game menus.

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
from test_historical_level_sets import program as set_program
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-level-consumer-contracts.json'


def program(data, focus):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    code = set_program(data, selectors=True)
    code = code[:code.index('int main(void)')]
    _, cases = switch_cases(source, 'getsyspropertybyindex', 'index', outermost=True)
    select = function(source, 'selectplayer')
    start = select.index('else // without select.txt')
    tail = select[start:]
    condition = tail[tail.index('if('):tail.index('{', tail.index('if('))].strip()
    selection = braced_statement(tail, condition)
    binding = re.search(r's_set_entry\s*\*\s*set\s*=[^;]+;', select)
    if binding is None:
        raise AssertionError('Missing native selection binding')
    # Preserve the complete body of both actual menus; rendering and keys are providers.
    chooser = function(source, 'choose_difficulty')
    saved = function(source, 'load_saved_game')
    end = re.search(r'\}\s*s_savelevel\s*;', header)
    if end is None:
        raise AssertionError('Missing saved-game record')
    record = header[header.rfind('typedef struct', 0, end.start()):end.end()]
    player = re.search(r'typedef struct\s*\{[^{}]*\}s_player;', header)
    if player is None:
        raise AssertionError('Missing player record')
    flags = '\n'.join(re.search(r'^#define\s+' + name + r'\s+[^\n]+', header, re.M)[0]
        for name in ('FLAG_ESC', 'FLAG_MOVELEFT', 'FLAG_MOVERIGHT', 'FLAG_MOVEUP',
                     'FLAG_MOVEDOWN', 'FLAG_ANYBUTTON', 'FLAG_START', 'FLAG_SPECIAL',
                     'FLAG_ATTACK', 'FLAG_ATTACK2', 'FLAG_ATTACK3', 'FLAG_ATTACK4',
                     'FLAG_JUMP', 'MAX_SPECIAL_INPUTS'))
    slots = function(source, 'obor_saved_game_slots') if 'obor_saved_game_slots(' in chooser else ''
    play = function(source, 'playgame')
    boundary = play.index('allow_secret_chars = ')
    entry = play[:boundary]
    entry = entry[entry.index('{')+1:]
    entry = ('static void entry_prefix(int *players,unsigned which_set,int useSavedGame) {\n' +
             entry + '\n++entered; }')
    players = re.search(r'for\(i=0;[^\n]+players\[i\] = \(player\[i\].lives>0\);', play)
    if players is None:
        raise AssertionError('Missing selection-level player preparation')
    bonus = select[select.index('if(loadGameFile())'):select.index('if(filename')]
    values = dict(RECORD=record, PLAYER=player[0], FLAGS=flags,
        PACK=re.search(r'^#pragma pack\(push,\s*\d+\)', header, re.M)[0],
        GETTER=cases['_sv_maxplayers']['body'], SELECTION=selection,
        SET_BINDING=binding[0],
        CHOOSER=chooser, SAVED=saved, SLOTS=slots, BONUS=bonus, ENTRY=entry,
        PLAYERS=players[0], FOCUS=str(focus),
        HAS_QUERY='1' if 'obor_level_set_player_count(' in source else '0',
        HAS_FIXED='1' if 'obor_legacy_levelsets(' in source else '0',
        CONTEXTS=','.join('{%d,%d,%d}' % (r['revision'], r['fixed_slots'], r['global_names'])
                          for r in data['sources']))
    text = Path(__file__).with_name('level_consumer_contract.c.in').read_text()
    for name, value in values.items():
        text = text.replace('@' + name + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise AssertionError('Unresolved native consumer input')
    return code + text


class HistoricalLevelConsumerContracts(unittest.TestCase):
    def check(self, focus):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(revisions), len(set(revisions)))
        actual = [json.loads(line) for line in native_output(program(data, focus), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r, focus=focus, status='PASS') for r in revisions])

    def test_player_query_selector_buffers_and_selection_ports(self):
        self.check(1)

    def test_unlock_bonus_saved_slots_and_game_entry(self):
        self.check(2)


if __name__ == '__main__':
    unittest.main()
