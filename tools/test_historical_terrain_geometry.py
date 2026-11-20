"""Check original terrain edges, height selection and hole-index side effects.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-terrain-geometry-contracts.json'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [row['revision'] for row in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Original terrain contexts and transition controls required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not re.fullmatch('[0-9a-f]{64}', row['source_sha256']['openbor.c']) or
                any(row[name] not in (0, 1) for name in
                    ('hole_inclusive', 'wall_inclusive', 'platform_inclusive', 'writes_holez')) or
                len(row['selection']) != len(data['selection_cases'])):
            raise ValueError('Complete source-bound terrain expectations required')
    return data


def program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    names = ('obor_terrain_between', 'testhole', 'testwall', 'testplatform',
             'checkhole_in', 'checkholeindex_in')
    contexts = []
    for row in data['sources']:
        contexts.append('{%du,%d,%d,%d,%d,{%s}}' %
                        (row['revision'], row['hole_inclusive'], row['wall_inclusive'],
                         row['platform_inclusive'], row['writes_holez'],
                         ','.join(str(value) for value in row['selection'])))
    cases = []
    for row in data['selection_cases']:
        if not 0 <= len(row['heights']) <= 4:
            raise ValueError('At most four controlled terrain entries required')
        cases.append('{%d,{%s},%s}' % (len(row['heights']),
            ','.join(str(value) for value in row['heights']) or '0', str(row['altitude'])))
    values = dict(FUNCTIONS='\n'.join(function(core, name) for name in names),
                  CONTEXTS=','.join(contexts), CASES=','.join(cases),
                  CASE_COUNT=str(len(cases)))
    text = Path(__file__).with_name('terrain_geometry_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native terrain dependency')
    return text


class TerrainGeometryContracts(unittest.TestCase):
    def test_edges_slopes_height_ties_and_selected_hole_state(self):
        data = fixture_data()
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], status='PASS')
                                  for row in data['sources']])

    def test_6391_original_platform_walkoff_height(self):
        data = load_contract_fixture(FIXTURE.with_name('profile-6391-platform-walkoff.json'))
        rows = data['sources']
        self.assertEqual({row['revision'] for row in rows}, contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        core = (engine / 'openbor.c').read_text(encoding='latin1')
        methods = '\n'.join(function(core, name) for name in (
            'testplatform', 'check_platform_below_entity', 'get_platform_base'))
        controls = ',\n'.join('{%du,{%s}}' % (row['revision'], ','.join(str(i) for i in row['selected']))
                              for row in rows)
        heights = ','.join(f'{float(height)}f' for height in data['heights'])
        template = Path(__file__).with_name('platform_walkoff_contract.c.in').read_text()
        code = (template.replace('@METHODS@', methods).replace('@CONTROLS@', controls)
                .replace('@HEIGHTS@', heights))
        self.assertEqual(native_output(code, data, engine_source=engine), f'PASS {len(rows)}\n')


if __name__ == '__main__':
    unittest.main()
