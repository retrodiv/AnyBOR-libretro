"""Check own level-set scalar, parser and player-menu contracts.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_level_entries import program as entry_program
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-level-set-contracts.json'


def player_menu_display(menu):
    """Retain the player display independently of its native row expression."""
    if not isinstance(menu, str) or len(menu) > 8 << 20:
        raise ValueError('Bounded native player menu required')
    starts = list(re.finditer(r'_menutext\(\(selector==2\), col1, [^\r\n]*, "Players: "\);', menu))
    if len(starts) != 1:
        raise ValueError('One native player display label required')
    stop = re.search(r'_menutext\(\(selector==3\)', menu[starts[0].end():])
    if stop is None:
        raise ValueError('Complete native player display required')
    return menu[starts[0].start():starts[0].end() + stop.start()]


def program(data, *, selectors=False):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openbor.c').read_text()
    code = entry_program(data)
    code = code[:code.index('int main(void)')]
    header = (engine / 'source/gamelib/commands.h').read_text()
    match = re.search(r'typedef enum levelOrderCommand\s*\{[^{}]*\}\s*levelOrderCommands;', header)
    if match is None:
        raise AssertionError('Missing level command enum')
    loader, cases = switch_cases(source, 'load_levelorder', 'cmd', outermost=True)
    commands = ('SET', 'IFCOMPLETE', 'FILE', 'SCENE', 'SELECT', 'NEXT', 'END',
        'LIVES', 'DISABLEHOF', 'CANSAVE', 'MUSICOVERLAP', 'CUSTFADE', 'CONTINUESCORE',
        'CREDITS', 'TYPEMP', 'SINGLE', 'MAXPLAYERS', 'NOSAME')
    if selectors:
        commands += ('SKIPSELECT',)
    branches = '\n'.join('case CMD_LEVELORDER_' + name + ':' +
        cases['CMD_LEVELORDER_' + name]['body'] for name in commands)
    guard = re.search(r'^#define CHKDEF[^\n]+', loader, re.M)
    if guard is None:
        raise AssertionError('Missing native set prerequisite')
    initial = re.findall(r'^[ \t]*s_(?:set|level)_entry[ \t]*\*[ \t]*(?:set|le)'
                         r'[ \t]*=[^;]+;', loader, re.M)
    if len(initial) != 2:
        raise AssertionError('Missing native parser cursors')
    value = re.search(r'^[ \t]*char[ \t]+value\[[^\]\r\n]+\][ \t]*=[^;]+;', loader, re.M)
    empty = re.search(r'if\(!set\)\s*errormessage = "No levels were loaded!";', loader)
    if empty is None:
        raise AssertionError('Missing native empty level-order result')
    menu, selections = switch_cases(source, 'system_options', 'selector', outermost=True)
    display = player_menu_display(menu)
    reset = ''
    if 'obor_legacy_set_options(' in source:
        reset = ('s_obor_level_set_defaults *options=obor_legacy_set_options();'
                 'memset(options,0,sizeof(*options)*MAX_DIFFICULTIES);'
                 'for(int i=0;i<MAX_DIFFICULTIES;++i)options[i].maxplayers=2;')
    tail = Path(__file__).with_name('level_set_contract.c.in').read_text()
    values = dict(ENUM=match[0], ADD_SET=function(source, 'add_set'),
        GUARD=guard[0], CASES=branches, DISPLAY=display,
        INITIALS='\n'.join(initial), VALUE=value[0] if value else '', EMPTY=empty[0],
        MENU=selections['2']['body'], RESET=reset,
        SELECT_STATE='static char *selector_args[4]; static int selector_count=2;' if selectors else '',
        SELECT_DECLARATIONS='int i;char *arg;struct {int count;} arglist={selector_count};' if selectors else '',
        GET_ARGUMENT=('((index)==1?text:((index)>1 && (index)<=4 && selector_args[(index)-1]?'
                      'selector_args[(index)-1]:""))' if selectors else '((index)==1?text:"")'),
        CONTEXTS=','.join('{%d,%d,%d,%d,%d}' % (r['revision'], r['persistent_values'],
            r['pre_set_players'], r['name_limit'], r['filename_limit']) for r in data['sources']))
    for name, value in values.items():
        tail = tail.replace('@' + name + '@', value)
    if re.search(r'@[A-Z_]+@', tail):
        raise AssertionError('Unresolved level-set contract input')
    return code + tail


class HistoricalLevelSetContracts(unittest.TestCase):
    def test_defaults_reload_parser_limits_and_player_menu(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual([row['revision'] for row in actual], revisions)
        for row in actual:
            self.assertEqual(row['status'], 'PASS')
            self.assertEqual(row['commands'], 54)


if __name__ == '__main__':
    unittest.main()
