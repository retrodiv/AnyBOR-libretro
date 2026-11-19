"""Check native saved-selection bytes, level-local ownership and progression.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, contract_revisions, load_contract_fixture
from test_early_jump_walkoff import braced_statement
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-level-order-contracts.json'
SELECTION_FIXTURE = FIXTURE.with_name('profile-4432-player-selection-resume.json')
DIAGNOSTIC_FIXTURE = FIXTURE.with_name('profile-4432-parser-diagnostics.json')


def program(data, engine):
    source = (engine / 'openbor.c').read_text()
    _, cases = switch_cases(source, 'load_levelorder', 'cmd', outermost=True)
    layouts = []
    for row in data['sources']:
        if row['record'] not in layouts:
            layouts.append(row['record'])
    if not 1 <= len(layouts) <= 8:
        raise ValueError('Bounded complete own saved-record layouts required')
    original = '\n'.join(re.sub(r'\bs_savelevel\b', 'original_save_'+str(i), record)
                         for i,record in enumerate(layouts))
    names = ['ParseArgs', 'reset_playable_list', 'load_playable_list',
             'obor_saved_level_record_size', 'obor_profile_write_saved_game',
             'obor_profile_read_saved_game', 'obor_copy_skipselect_name',
             'obor_apply_level_skipselect', 'add_level', 'add_scene', 'add_select',
             'add_skipselect', 'unload_levelorder', 'savelevelinfo']
    methods = '\n'.join(function(source, name) for name in names)
    # Annotate the native intentional fallthrough without changing statements.
    methods = methods.replace('done = 1;', 'done = 1; /* fall through */')
    values = dict(ORIGINALS=original,
        SIZES=','.join('sizeof(original_save_'+str(i)+')' for i in range(len(layouts))),
        METHODS=methods, SKIP=cases['CMD_LEVELORDER_SKIPSELECT']['body'],
        FILES='\n'.join(function(source, name) for name in ('clearSavedGame','saveGameFile','loadGameFile')),
        GAME=function(source,'playgame'), MENU=function(source,'load_saved_game'),
        CONTEXTS=','.join('{%du,%d,%d,%d,%d}' % (row['revision'],row['credits_restore'],
            row['level_selection'],row['saved_selection'],layouts.index(row['record'])) for row in data['sources']))
    code = Path(__file__).with_name('forward_level_order_contract.c.in').read_text()
    for key,value in values.items():
        code = code.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@',code):
        raise ValueError('Unresolved native level-order dependency')
    return code


class ForwardLevelOrderTests(unittest.TestCase):
    def test_4432_level_order_and_video_diagnostic_lines(self):
        data = load_contract_fixture(DIAGNOSTIC_FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and 4510 <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        order, cases = switch_cases(source, 'load_levelorder', 'cmd', outermost=True)
        video = function(source, 'init_videomodes')
        unknown = video[video.rindex('else if(command && command[0])'):]
        values = dict(
            NUMBERS='\n'.join(function(source, name) for name in ('isNumeric', 'getValidInt', 'getValidFloat')),
            LOCALS=re.search(r'(?m)^    const int line_diagnostics[^\n]+\n    int warned_unknown[^\n]+', order)[0],
            ORDER=cases['default']['body'],
            VIDEO=braced_statement(unknown, 'if(command && command[0])'),
            ROWS=',\n'.join('{%d,%d,%d}' % (row['revision'], row['separate_lines'],
                                         row['hyphenated_number_warning']) for row in rows),
        )
        code = Path(__file__).with_name('parser_diagnostics_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda item: values[item[1]], code)
        actual = native_output(code, data, engine_source=engine)
        self.assertEqual([int(line) for line in actual.splitlines()], revisions)

    def test_4432_skip_selection_lives_and_saved_credits(self):
        data = load_contract_fixture(SELECTION_FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and 4510 <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        select = function(source, 'selectplayer')
        setup = select[select.index('    s_set_entry *set ='):select.index('    if(filename && filename[0])')]
        begin = select.index('    else // without select.txt')
        start = select.index('        defaultselect = 1;', begin)
        default = select[start:select.index('        if (!saved_select_screen)', start)]
        tail = select[:select.index('    time = 0;')]
        restore = tail[tail.rindex('    for(i = 0; i < set->maxplayers; i++)'):]
        diagnostic = re.search(r'printf\("Command .*?historical_resume[^;]+;', select, re.S)[0]
        values = dict(
            METHODS='\n'.join(function(source, name) for name in (
                'obor_profile_name_limit', 'obor_profile_copy_name', 'savelevelinfo',
                'obor_restore_selection_player')),
            SETUP=setup, DEFAULT=default, RESTORE=restore, DIAGNOSTIC=diagnostic,
            ROWS=',\n'.join('{%d,%d}' % (row['revision'], row['selection_mode']) for row in data['sources']),
        )
        code = Path(__file__).with_name('player_selection_resume_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda item: values[item[1]], code)
        output = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_native_selection_ownership_saved_rows_menu_and_progression(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions),len(data['sources']))
        self.assertEqual((min(revisions),max(revisions)),tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for profile in contract_profiles(data,json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision',profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision,revisions)
        engine = Path(os.environ.get('OBOR_LEVEL_ORDER_ENGINE',ROOT / 'src/engines' / data['engine']))
        actual = [json.loads(line) for line in native_output(program(data,engine),data,engine_source=engine).splitlines()]
        self.assertEqual(actual,[dict(revision=row['revision'],status='PASS') for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
