"""Check complete native movement callers with original hole-query periods.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-terrain-movement-contracts.json'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [row['revision'] for row in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Original movement contexts and transition controls required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not re.fullmatch('[0-9a-f]{64}', row['source_sha256']['openbor.c']) or
                any(row[name] not in (0, 1) for name in
                    ('testmove_height', 'trymove_height', 'height_writes_holez')) or
                len(row['height_hits']) != 4 or
                any(value not in (0, 1) for value in row['height_hits'])):
            raise ValueError('Own-source movement selection and hole observations required')
    return data


def program(data, *, movement_decisions=False):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    names = ('diff', 'inair', 'obor_terrain_between', 'testhole', 'checkhole',
             'checkhole_in', 'testmove', 'common_trymove')
    decisions = ''
    if movement_decisions:
        rows = ['{%du,0,0,0,{0,0,0,0}}' % row['revision'] for row in data['sources']]
        decisions = Path(__file__).with_name('terrain_movement_decisions.c.in').read_text()
        decisions = decisions.replace('@DECISION_ROWS@', ','.join('{%d,%d,%d}' %
            (row['wander_draw'], row['item_draw'], row['negative_wall']) for row in data['sources']))
        wander = re.search(r'(?ms)^    //mod = [^\n]*\n(.*?)^    if\(dox\)',
                           function(core, 'common_try_wander'))[1]
        item = re.search(r'(?ms)^[ \t]*//other = [^\n]*normal_find_item[^\n]*\n(.*?)'
                         r'^[ \t]*owner = self->parent;', function(core, 'common_move'))[1]
        decisions = decisions.replace('@WANDER@', wander).replace('@ITEM@', item)
    else:
        rows = ['{%du,%d,%d,%d,{%s}}' % (r['revision'], r['testmove_height'],
                r['trymove_height'], r['height_writes_holez'],
                ','.join(str(value) for value in r['height_hits'])) for r in data['sources']]
    text = Path(__file__).with_name('terrain_movement_contract.c.in').read_text()
    for key, value in dict(FUNCTIONS='\n'.join(function(core, n) for n in names),
                           CONTEXTS=','.join(rows), MOVEMENT_DECISIONS=decisions).items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native movement dependency')
    return text


class TerrainMovementContracts(unittest.TestCase):
    def test_4432_wander_item_draws_and_wall_participation(self):
        fixture = Path(__file__).with_name('fixtures') / 'profile-movement-decision-contracts.json'
        data = load_contract_fixture(fixture)
        self.assertEqual(data['engine'], '4432')
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        for row in data['sources']:
            for key in ('wander_draw', 'item_draw', 'negative_wall'):
                self.assertIs(type(row[key]), bool)
        actual = [json.loads(line) for line in native_output(
            program(data, movement_decisions=True), data).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], status='PASS') for row in data['sources']])
        print(f'{len(revisions)} movement decision contexts passed.', flush=True)

    def test_height_query_periods_axis_results_and_movement_callbacks(self):
        data = fixture_data()
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], status='PASS')
                                  for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
