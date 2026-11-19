"""Execute native introduction, failed-level and main-options caller branches.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import copy
import io
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers, switch_cases
import test_historical_native_menu_actions as actions

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-main-menu-flow-contracts.json'


def intro_branch(main):
    start = main.index('while(!quit)')
    start = main.index('{', start) + 1
    return main[start:main.index('if(!started)', start)]


def failed_level_branch(game):
    start = game.index('else if(!playlevel(le->filename))')
    return game[start:game.index('if(le->gonext', start)].rstrip()


def options_branch(main):
    _, arms = switch_cases(main, 'openborMain', 'selector', outermost=False)
    return arms['1']['body']


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [r['revision'] for r in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own main-menu sources and preceding controls required')
    for row in data['sources']:
        if (row['intro_condition'] not in ('set', 'set_or_bit', 'set_without_bit') or
                row['intro_reset'] not in ('none', 'else', 'after') or
                type(row['game_skip_bits']) is not bool or type(row['game_reset']) is not bool or
                type(row['main_options_merged']) is not bool or row['game_speed'] != 200 or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch('[0-9a-f]{64}', v) for v in row['source_sha256'].values()) or
                not all(re.fullmatch('[0-9a-f]{64}', v) for v in row['branch_sha256'].values())):
            raise ValueError('Explicit source-owned main-menu policies required')
    for case in data['intro_cases']:
        if (len(case) != 7 or case[0] not in (-1, 0, 3) or
                any(case[i] not in (0, 1) for i in (1, 3, 4)) or
                not 0 <= case[2] <= 15 or case[5] not in (-1, 0, 3, 8) or
                case[6] not in (-1, 0, 1)):
            raise ValueError('Bounded introduction provider recipe required')
    for case in data['game_cases']:
        if (len(case) != 7 or not 0 <= case[0] <= 15 or not 0 <= case[1] <= 3 or
                not -1 <= case[2] < 4 or case[3] not in (2, 4) or case[4] not in (0, 1) or
                any(v not in (-1, 0, 3, 4, 15) for v in case[5:])):
            raise ValueError('Bounded failed-level provider recipe required')
    return data


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    end = header.index('} e_key_def;') + len('} e_key_def;')
    start = header.rfind('typedef enum', 0, end)
    main = function(core, 'openborMain')
    intro = ','.join('{%s}' % ','.join(map(str, c)) for c in data['intro_cases'])
    game = ','.join('{%s}' % ','.join(map(str, c)) for c in data['game_cases'])
    speed = re.search(r'^#define\s+GAME_SPEED\s+\d+[^\n]*', header, re.M)
    if speed is None: raise ValueError('Native introduction clock scale required')
    values = dict(FLAGS=header[start:end], GAME_SPEED=speed[0], INTRO=intro_branch(main),
        GAME=failed_level_branch(function(core, 'playgame')),
        CONTEXTS=','.join(str(r['revision']) + 'u' for r in data['sources']),
        INTRO_CASES=intro, GAME_CASES=game)
    text = Path(__file__).with_name('main_menu_flow_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native main-menu dependency')
    return text


def expected_intro(row, case):
    # Each row records its own source condition and reset placement, including
    # intermediate versions that differ from both endpoints.
    skip, due, flag, escape, custom, callback_flag, callback_escape = case
    branch = skip < 0
    if row['intro_condition'] == 'set_or_bit': branch |= bool(flag & 8)
    if row['intro_condition'] == 'set_without_bit': branch &= not bool(flag & 8)
    time, deadline, started, relback, quit_menu, events = 40, (40 if due else 41), 7, 9, 0, []
    if branch:
        if due:
            events = [['scene', 'custom/intro.txt' if custom else 'data/scenes/intro.txt', flag],
                      ['update', 0, 0, flag]]
            time += 7
            if callback_flag >= 0: flag = callback_flag
            if callback_escape >= 0: escape = callback_escape
            deadline, relback, started = time + row['game_speed'] * 20, 1, 0
        quit_menu = int(bool(escape))
    else:
        started, relback = 1, 0
        if row['intro_reset'] == 'else': flag = 0
    if row['intro_reset'] == 'after': flag = 0
    return dict(events=events, state=[flag, started, relback, quit_menu, deadline, time, escape])


def expected_game(row, case):
    flag, suppress, alive, maxplayers, successful, gameover_flag, hall_flag = case
    events = [['play', flag]]
    lives = [-1, 0, -2, 0]
    if alive >= 0: lives[alive] = 3
    played, weapons, reached = [10, 11, 12, 13], [20, 21, 22, 23], int(bool(successful))
    if not successful and alive < 0:
        if not suppress & 1 and not (row['game_skip_bits'] and flag & 2):
            events.append(['gameover', flag])
            if gameover_flag >= 0: flag = gameover_flag
        if not suppress & 2 and not (row['game_skip_bits'] and flag & 4):
            events.append(['hall', 1, flag])
            if hall_flag >= 0: flag = hall_flag
        for i in range(maxplayers): played[i] = weapons[i] = 0
        if row['game_reset']: flag = 0
    return dict(events=events, state=[flag, reached, *played, *weapons, *lives])


def main_options_program(data, config):
    text = actions.program(data, config)
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    arm = rename_identifiers(options_branch(function(core, 'openborMain')),
                             {'menu_options': 'run_menu_options'})
    native_entry = 'static void script_options(void){switch(1){case 1:' + arm + '}}'
    old_entry = function(text, 'script_options')
    return text.replace(old_entry, native_entry, 1)


class MainMenuFlowContracts(unittest.TestCase):
    def test_native_intro_and_failed_level_order_and_state(self):
        data = fixture_data()
        actual = iter(io.StringIO(native_output(program(data), data)))
        count = 0
        for row in data['sources']:
            for kind, cases, oracle in [('intro', data['intro_cases'], expected_intro),
                                        ('game', data['game_cases'], expected_game)]:
                for index, case in enumerate(cases):
                    line = next(actual, None)
                    self.assertIsNotNone(line)
                    wanted = dict(revision=row['revision'], kind=kind, case=index,
                                  **oracle(row, case))
                    self.assertEqual(json.loads(line), wanted,
                                     '%s revision=%d case=%d' % (kind, row['revision'], index))
                    count += 1
        self.assertIsNone(next(actual, None))
        self.assertGreater(count, 0)

    def test_main_options_caller_enters_complete_native_menu_loops(self):
        flow = fixture_data()
        data = copy.deepcopy(actions.fixture_data())
        own = {r['revision']: r for r in flow['sources']}
        for row in data['sources']:
            self.assertIn(row['revision'], own)
            self.assertEqual(row['commit'], own[row['revision']]['commit'])
            self.assertEqual(row['view']['root_merged'], own[row['revision']]['main_options_merged'])
        for case in data['cases']:
            case['domains'] = ['root'] if 'root' in case['domains'] else []
        config = next(c for c in data['compiler_conditions'] if c['name'] == 'generic')
        actual = iter(io.StringIO(native_output(main_options_program(data, config), data)))
        count = 0
        for row in data['sources']:
            for index, case in enumerate(data['cases']):
                wanted = actions.expected(data, row, case, 'root', config['name'])
                if wanted is None: continue
                line = next(actual, None)
                self.assertIsNotNone(line)
                self.assertEqual(json.loads(line), dict(revision=row['revision'],
                    domain=data['domains'].index('root'), case=index, **wanted),
                    'main options revision=%d case=%d' % (row['revision'], index))
                count += 1
        self.assertIsNone(next(actual, None))
        self.assertGreater(count, 0)


if __name__ == '__main__':
    unittest.main()
