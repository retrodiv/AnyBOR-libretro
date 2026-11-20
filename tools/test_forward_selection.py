"""Check source-defined player, palette and native credit boundaries.

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
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-selection-contracts.json'
CYCLING = FIXTURE.with_name('profile-selection-cycling.json')
PALETTE = FIXTURE.with_name('profile-selection-palette.json')


def program(data, engine):
    source = (engine / 'openbor.c').read_text()
    contracts = list(data['contracts'])
    cases = []
    for case in data['cases']:
        fields = [str(case[k]) for k in ['kind', 'slot', 'active', 'nosame', 'current',
                  'action', 'colourselect', 'guard_only']]
        fields += ['{' + ','.join(map(str, case[k])) + '}' for k in ['names', 'colours', 'maps']]
        cases.append('{' + ','.join(fields) + '}')
    expected = []
    for key in contracts:
        if len(data['contracts'][key]) != len(cases):
            raise ValueError('Every selection contract needs its complete case inventory')
        expected.append('{' + ','.join('{' + ','.join(map(str, row)) + '}'
                        for row in data['contracts'][key]) + '}')
    credits = []
    for rows in data['credit_rows']:
        credits.append('{' + ','.join('{%d,%d,%d,%s}' % (row['font'], row['row'], row['column'], json.dumps(row['text']))
                                     for row in rows) + '}')
    values = dict(FUNCTIONS='\n'.join(function(source, name) for name in data['functions']),
        CASES=','.join(cases), EXPECTED=','.join(expected),
        CONTEXTS=','.join('{%du,%d,%d}' % (row['revision'], contracts.index(row['contract']), row['credits'])
                          for row in data['sources']),
        CREDIT_ROWS=','.join(credits), CREDIT_COUNTS=','.join(map(str, map(len, data['credit_rows']))))
    result = Path(__file__).with_name('forward_selection_contract.c.in').read_text()
    for key, value in values.items():
        result = result.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', result):
        raise ValueError('Unresolved source-defined selection dependency')
    return result


def palette_selection_program(data, rows, engine):
    source = (engine / 'openbor.c').read_text(encoding='latin-1')
    status = function(source, 'updatestatus')
    preview = function(source, 'spawnexample')
    menu = function(source, 'selectplayer')
    methods = ('nextcolourmap', 'prevcolourmap')
    if data['engine'] == '4432':
        flag = 'if ( colourselect && (set->nosame & 2) )'

        def initializers(body):
            return ['player[i].colourmap = 0;\n' + braced_statement(
                        body[match.end():].split('// NOSAME X 2', 1)[0], flag)
                    for match in re.finditer(r'(?m)^\s*player\[i\]\.colourmap = 0;', body)]

        horizontal, join = initializers(status)
        preview, = initializers(preview)
        menu_start, = re.findall(r'player\[i\]\.colourmap = nextcolourmap\(example\[i\]->model, i - 1\);', menu)
        status_scroll = braced_statement(status, 'else if(player[i].playkeys & (FLAG_MOVEUP | FLAG_MOVEDOWN) && colourselect)')
        status_scroll = status_scroll[status_scroll.index('player[i].colourmap = '):
                                     status_scroll.index('player[i].playkeys = 0;')]
    else:
        methods = ('nextcolourmap', 'prevcolourmap', 'nextcolourmapn', 'prevcolourmapn')
        if 'obor_select_colourmap(' in source:
            methods = methods[:2] + ('obor_select_colourmap',) + methods[2:]
        flag = r'player\[i\]\.colourmap = \(colourselect && \(set->nosame & 2\)\)\s*\?[^;]+;'
        horizontal, _, join = re.findall(flag, status)
        preview, = re.findall(flag, preview)
        menu_start, _ = re.findall(flag, menu)
        status_scroll, = re.findall(r'player\[i\]\.colourmap = \(\(player\[i\]\.playkeys[^;]*?\? nextcolourmapn : prevcolourmapn\)[^;]+;', status)
    menu_scroll, = re.findall(r'player\[i\]\.colourmap = \(\(player\[i\]\.newkeys[^;]*?\? nextcolourmapn? : prevcolourmapn?\)[^;]+;', menu)
    routes = (horizontal, join, preview, menu_start, status_scroll, menu_scroll)
    declarations = {
        2: 'entity *example = &preview_object;',
        3: 'entity *example[MAX_PLAYERS] = {0}; example[i] = &preview_object;',
        5: 'entity *example[MAX_PLAYERS] = {0}; example[i] = &preview_object;',
    }
    fields = ('maps', 'frozen', 'hide_start', 'hide_end', 'current', 'slot', 'colourselect', 'nosame')
    cases = []
    for case in data['cycling']:
        head = ','.join(str(case[name]) for name in fields)
        occupied = ','.join(map(str, case['occupied']))
        expected = ','.join('{' + ','.join(map(str, row)) + '}' for row in case['expected'])
        cases.append(f'{{{head},{{{occupied}}},{{{expected}}}}}')
    initial = []
    for case in data['callers']:
        head = ','.join(str(case[name]) for name in ('current', 'slot', 'colourselect', 'nosame', 'occupied'))
        expected = ','.join('{' + ','.join(map(str, row)) + '}' for row in case['expected'])
        initial.append(f'{{{head},{{{expected}}}}}')
    values = {
        'METHODS': '\n'.join(function(source, name) for name in methods),
        'ROUTES': '\n'.join(f'case {index}: {{\n{declarations.get(index, "")}\n{body}\nbreak;\n}}'
                          for index, body in enumerate(routes)),
        'ROWS': ','.join('{%du,%d}' % (row['revision'], row['palette_policy']) for row in rows),
        'CYCLING': ',\n'.join(cases), 'CALLERS': ',\n'.join(initial),
    }
    template = Path(__file__).with_name('selection_palette_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


class ForwardSelectionTests(unittest.TestCase):
    def check_selection_palette(self, engine_id):
        data = load_contract_fixture(PALETTE) | {'engine': engine_id}
        rows = [row for row in data['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][engine_id])))
        engine = Path(os.environ.get('OBOR_SELECTION_ENGINE', ROOT / 'src/engines' / engine_id))
        output = native_output(palette_selection_program(data, rows, engine), data, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_selection_palette(self):
        self.check_selection_palette('4432')

    def test_6391_selection_palette(self):
        self.check_selection_palette('6391')

    def check_selection_cycling(self, engine_id):
        data = load_contract_fixture(CYCLING) | {'engine': engine_id}
        rows = [row for row in data['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][engine_id])))
        engine = Path(os.environ.get('OBOR_SELECTION_ENGINE', ROOT / 'src/engines' / engine_id))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        methods = ('nextplayermodel', 'prevplayermodel', 'nextplayermodeln', 'prevplayermodeln')
        if engine_id == '6391':
            methods = ('obor_selectable_player',) + methods
        fields = ('selectable', 'allow_secret', 'bonus', 'current', 'slot', 'maxplayers', 'nosame')
        cases = []
        for case in data['cases']:
            head = ','.join(str(case[key]) for key in fields)
            names = ','.join(json.dumps(name) for name in case['names'])
            expected = ','.join(map(str, case['expected'][engine_id]))
            cases.append(f'{{{head},{{{names}}},{{{expected}}}}}')
        values = {
            'FUNCTIONS': '\n'.join(function(source, name) for name in methods),
            'CASES': ',\n'.join(cases),
            'REVISIONS': ','.join(str(revision) + 'u' for revision in revisions),
        }
        template = Path(__file__).with_name('selection_cycling_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_selection_cycling(self):
        self.check_selection_cycling('4432')

    def test_6391_selection_cycling(self):
        self.check_selection_cycling('6391')

    def test_native_roster_join_preview_palette_and_credit_rows(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for row in data['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')
            self.assertTrue(set(data['functions']) <= row['functions'].keys())
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_SELECTION_ENGINE', ROOT / 'src/engines' / data['engine']))
        actual = [json.loads(line) for line in native_output(program(data, engine), data,
                  engine_source=engine).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], status='PASS') for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
