"""Check native saved-selection bytes, level-local ownership and progression.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-level-order-contracts.json'


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
