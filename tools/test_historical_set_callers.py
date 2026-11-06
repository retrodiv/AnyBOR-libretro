"""Check level-set values at their native caller expressions and loop headers.

The delegated loop bodies and the historical HUD scheduling are separate
contracts. Controller history has its own complete-function regression.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_level_consumers import program as consumer_program
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-level-caller-contracts.json'


def parenthesized(text, opening):
    """Read the balanced, expression-only headers selected by this probe."""
    if text[opening] != '(':
        raise AssertionError('Missing native expression opening')
    depth = 0
    for end in range(opening, len(text)):
        if text[end] == '(':
            depth += 1
        elif text[end] == ')':
            depth -= 1
            if depth == 0:
                return text[opening:end + 1]
    raise AssertionError('Unfinished native expression')


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    prefix = consumer_program(data, 1)
    prefix = prefix[:prefix.index('int main(void)')]
    display = 'static struct {int hRes;} videomodes={320};'
    if prefix.count(display) != 1:
        raise AssertionError('Missing declared display provider')
    prefix = prefix.replace(display,
        'static struct {int hRes,hShift,vShift;} videomodes={.hRes=320};')
    names = ('updatestatus', 'predrawstatus', 'bike_crash', 'update_scroller',
             'inputrefresh', 'execute_keyscripts', 'showcomplete', 'playlevel', 'selectplayer')
    bodies = {name: function(core, name) for name in names}
    binding = re.search(r's_set_entry\s*\*\s*set\s*=[^;]+;', bodies['updatestatus'])
    if binding is None:
        raise AssertionError('Missing native status set binding')
    input_prefix = bodies['inputrefresh'].split('s_player* pl;', 1)[0]
    input_prefix = input_prefix[input_prefix.index('{') + 1:]
    if 'int player_count' not in input_prefix:
        raise AssertionError('Missing bounded native input extent')
    control_call = re.findall(r'control_update\(playercontrolpointers,\s*player_count\);',
                              bodies['inputrefresh'])
    if len(control_call) != 1:
        raise AssertionError('One regular native controller call required')
    loops, calls = [], []
    for name, body in bodies.items():
        for match in re.finditer(r'\bfor\s*\(', body):
            header = 'for' + parenthesized(body, body.index('(', match.start()))
            if not any(token in header for token in ('maxplayers', 'player_count')):
                continue
            index = len(loops)
            counter = re.match(r'for\(\s*([ipx])\s*=', header)
            if counter is None:
                raise AssertionError('Unexpected native player counter')
            counter = counter[1]
            expectation = ('(obor_profile_build<3666?4:count)' if
                           'obor_profile_build < 3666' in header else
                           '(all_inputs?4:count)' if name == 'inputrefresh' else 'count')
            stride = ('assert(j==2+2*seen && k==3+2*seen);' if 'j=2' in header else '')
            if 'to=0' in header:
                stride += 'assert(to==0);'
            actual_input = re.sub(r'\bint p;\s*', '', input_prefix, count=1) if name == 'inputrefresh' else ''
            loops.append('static void loop_%d(int count,int all_inputs) {\n'
                         'int i,x,p,j,k,to; %s\n%s\nint seen=0;\n'
                         '%s {assert(%s==seen && seen<4);%s ++seen;}\n'
                         'assert(seen==%s); }' %
                         (index, binding[0], actual_input, header, counter, stride, expectation))
            calls.append('loop_%d(count,all_inputs);' % index)
    status = bodies['updatestatus']
    joining = re.search(r'if\(\(player\[i\]\.playkeys', status)
    if joining is None:
        raise AssertionError('Missing native join condition')
    join = parenthesized(status, status.index('(', joining.start()))
    model = re.search(r'\bmodel\s*=[^;]*nextplayermodel\(NULL\)[^;]*;', status)
    score = re.findall(r'if\(set->continuescore\s*==[^;]+;', status)
    positions = [line.strip() for line in bodies['selectplayer'].splitlines()
                 if 'set->maxplayers > 2)' in line]
    spawns = [line for line in positions if 'example[i] = spawn(' in line]
    ready = [line for line in positions if 'font_printf(' in line]
    if model is None or len(score) != 2 or len(spawns) != 2 or len(ready) != 1:
        raise AssertionError('Incomplete native status/selection value sites')
    text = Path(__file__).with_name('level_caller_contract.c.in').read_text()
    fields = dict(BINDING=binding[0], LOOPS='\n'.join(loops), LOOP_CALLS='\n'.join(calls),
        INPUT_PREFIX=input_prefix, CONTROL_CALL=control_call[0], JOIN=join,
        MODEL=model[0], SCORE='\n'.join(score), SPAWN_FIRST=spawns[0],
        SPAWN_SECOND=spawns[1], READY=ready[0], LOOP_COUNT=str(len(loops)),
        CONTEXTS=','.join('{%d,%d,%d}' % (r['revision'], r['global_names'], r['input_all_ports'])
                          for r in data['sources']))
    for name, value in fields.items():
        text = text.replace('@' + name + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise AssertionError('Unresolved native level caller input')
    return prefix + text, len(loops)


class HistoricalLevelCallerContracts(unittest.TestCase):
    def test_player_extents_selection_positions_and_score_policy(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        code, loops = program(data)
        actual = [json.loads(line) for line in native_output(code, data).splitlines()]
        self.assertEqual(actual, [dict(revision=r, loops=loops, status='PASS') for r in revisions])


if __name__ == '__main__':
    unittest.main()
