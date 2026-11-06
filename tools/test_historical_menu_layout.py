"""Check native menu render prefixes against source-owned layout contracts.

Input polling, score insertion, settings IO and rasterization are separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from historical_menu_layout import frame_prefix
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-menu-layout-contracts.json'


def program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    functions = []
    for index, menu in enumerate(data['menus']):
        body = function(source, menu['name'])
        prefix = frame_prefix(body, condition=menu['condition'], boundary='update')
        setup = ''
        for name in menu['native_declarations']:
            found = re.findall(r'(?m)^\s*int\s+'+re.escape(name)+r'\s*=[^\r\n;]+;', body)
            if len(found) != 1:
                raise ValueError('One native layout declaration required: '+name)
            setup += found[0]+'\n'
        if menu['bar_setup']:
            found = re.findall(r'(?m)^\s*barx\s*=[^\r\n]+;', body)
            if len(found) != 1:
                raise ValueError('One native difficulty bar setup required')
            setup += found[0]+'\n'
        functions.append('static void frame_%d(void){\n%s\n%s\n%s\n}\n' % (
            index, menu['locals'], setup, prefix))
    parts = dict(FUNCTIONS='\n'.join(functions),
        CALLS='\n'.join('menu_index=%d;frame_%d();emit();' % (i, i) for i in range(len(data['menus']))),
        PROFILES=','.join(str(r['revision'])+'u' for r in data['sources']),
        CASES=','.join('{'+','.join(str(c[k]) for k in data['case_fields'])+'}' for c in data['cases']))
    text = Path(__file__).with_name('menu_layout_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native menu dependency')
    return text


class DifficultyScrollbarContracts(unittest.TestCase):
    def test_native_outer_box_blend_matches_own_source(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') / 'profile-difficulty-scrollbar-contracts.json')
        rows = data['sources']
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        self.assertTrue(set(data['boundary_controls']) <= {r['revision'] for r in rows})
        source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        body = function(source, 'choose_difficulty')
        initialization = re.findall(r's_drawmethod drawmethod = plainmethod;\s*drawmethod\.alpha = [^;]+;', body)
        calls = [line.strip() for line in body.splitlines() if '//outerbox' in line]
        self.assertEqual(len(initialization), 1)
        self.assertEqual(len(calls), 1)
        text = Path(__file__).with_name('difficulty_scrollbar_contract.c.in').read_text()
        for key, value in dict(INITIALIZATION=initialization[0], CALL=calls[0],
                              PROFILES=','.join(str(r['revision'])+'u' for r in rows)).items():
            text = text.replace('@'+key+'@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        self.assertEqual(len(actual), len(rows))
        for row, result in zip(rows, actual):
            with self.subTest(revision=row['revision']):
                self.assertEqual(result, dict(revision=row['revision'], alpha=data['contracts'][row['contract']]))


class MenuLayoutContracts(unittest.TestCase):
    def test_every_profile_keeps_own_render_coordinates_and_call_order(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        expected = [dict(revision=row['revision'], case=i, menu=n, draws=draws)
            for row in data['sources'] for i, case in enumerate(data['contracts'][row['contract']])
            for n, draws in enumerate(case)]
        self.assertEqual(len(actual), len(expected))
        for observed, oracle in zip(actual, expected):
            with self.subTest(revision=oracle['revision'], case=oracle['case'], menu=oracle['menu']):
                self.assertEqual(observed, oracle)


if __name__ == '__main__':
    unittest.main()
