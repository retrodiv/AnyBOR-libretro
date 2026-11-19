"""Check native vertical layer admission, clocks and queued geometry.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-background-contracts.json'
SCROLLED_FIXTURE = FIXTURE.with_name('profile-4432-scrolled-background-contracts.json')


def program(data, engine):
    core = (engine / 'openbor.c').read_text()
    commands = (engine / 'source/gamelib/commands.c').read_text()
    utility = (engine / 'source/utils.c').read_text()
    loader, cases = switch_cases(core, 'load_level', 'cmd', outermost=True)
    prefix = loader[loader.index('        ParseArgs(&arglist, buf + pos, argbuf);'):loader.index('switch(cmd)')]
    first = loader.index('    bgtravelled = 0;')
    reset = loader[first:loader.index('    nopause = 0;', first)]
    numbers = function(core, 'ParseArgs').replace('done = 1;', 'done = 1; /* fall through */')
    numbers += '\n'.join(function(core, n) for n in ['isNumeric', 'getValidInt', 'getValidFloat'])
    factory = function(utility, 'lc') + '\n'
    factory += '\n'.join(function(commands, n)+'\n#undef LIST_ADD' for n in
                         ['getCommandlistCommand', 'getLevelCommand', 'prepareList', 'createLevelCommandList', 'freeCommandList'])
    contexts = []
    for row in data['sources']:
        contexts.append('{%du,%d,%d,{%s}}' % (row['revision'], row['vertical'],
                         len(row['names']), ','.join(json.dumps(n) for n in row['names'])))
    draw_cases = []
    for c in data['draw_cases']:
        draw_cases.append('{%s}' % ','.join(str(c[k]) for k in data['draw_fields']))
    expected = []
    for key in ['old', 'vertical']:
        expected.append('{' + ','.join('{' + ','.join('{' + ','.join(map(str, row)) + '}'
                    for row in case) + '}' for case in data['draw_expected'][key]) + '}')
    plain = re.findall(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{[^;]+\};', core)
    if len(plain) != 1:
        raise ValueError('One complete native default draw method required')
    values = dict(LIST=(engine / 'source/scriptlib/List.c').read_text(), NUMBERS=numbers,
        FACTORY=factory, PREFIX=prefix, RESET=reset,
        CASES=''.join('case '+n+':'+cases[n]['body'] for n in
                     ['CMD_LEVEL_BGSPEED', 'CMD_LEVEL_VBGSPEED', 'CMD_LEVEL_SCROLLSPEED']),
        DEFAULT=cases['default']['body'], PLAIN=plain[0],
        UPDATE=function(core, 'update_scrolled_bg'),
        DRAW='\n'.join(function(core, n) for n in ['obor_background_coordinate', 'obor_background_shift']
                       if re.search(r'\b'+n+r'\s*\(', core))+'\n'+function(core, 'draw_scrolled_bg'),
        CONTEXTS=','.join(contexts), DRAW_CASES=','.join(draw_cases), EXPECTED=','.join(expected),
        VALUES=','.join('{%s,%s,%d}' % (json.dumps(c['text']), float(c['value']).hex()+'f', c['warning'])
                        for c in data['values']))
    result = Path(__file__).with_name('forward_background_contract.c.in').read_text()
    for key, value in values.items():
        result = result.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', result):
        raise ValueError('Unresolved native background dependency')
    return result


def scrolled_background_program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    loader = function(source, 'load_background')
    update = function(source, 'update_scrolled_bg')
    draw = function(source, 'draw_scrolled_bg')
    load = loader[loader.index('    unload_background();'):loader.index('    if(createtables)')]
    neon = update[update.index('    int pb ='):update.index('    if(!freezeall)')]
    table = draw[draw.index('        if(layer->neon)'):draw.index('        screenmethod.water.wavetime')]
    replacements = dict(LOAD=load, NEON=neon, TABLE=table,
        CONTEXTS=',\n'.join('{%d,%d,%d,%d,%d,%d}' % (row['revision'], row['fixed_palette_width'],
            row['indexed_first'], row['always_rotate'], row['select_palette_all_modes'],
            row['always_neon']) for row in data['sources']))
    rendered = Path(__file__).with_name('later_scrolled_background_contract.c.in').read_text()
    for key, value in replacements.items():
        rendered = rendered.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', rendered):
        raise ValueError('Unresolved 4432 background dependency')
    return rendered


class ForwardBackgroundTests(unittest.TestCase):
    def test_native_command_parser_clocks_and_layer_requests(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        for row in data['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_BACKGROUND_ENGINE', ROOT / 'src/engines' / data['engine']))
        rows = [json.loads(line) for line in native_output(program(data, engine), data,
                engine_source=engine).splitlines()]
        self.assertEqual(rows, [dict(revision=row['revision'], status='PASS') for row in data['sources']])

    def test_4432_scrolled_background_palette_routes(self):
        data = load_contract_fixture(SCROLLED_FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        observed = [json.loads(line) for line in native_output(scrolled_background_program(data), data).splitlines()]
        self.assertEqual(observed, [dict(revision=r, status='PASS') for r in revisions])


if __name__ == '__main__':
    unittest.main()
