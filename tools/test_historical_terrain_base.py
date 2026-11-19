"""Check native basemap participation, base updates and hole callbacks.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-terrain-base-contracts.json'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [row['revision'] for row in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own terrain base sources and boundary controls required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not re.fullmatch('[0-9a-f]{64}', row['source_sha256']['openbor.c']) or
                any(row[name] not in (0, 1) for name in
                    ('basemap_gated', 'selected_hole', 'writes_holez'))):
            raise ValueError('Complete original terrain base observations required')
    return data


def program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    names = ('obor_terrain_between', 'testhole', 'testplatform', 'testwall',
             'checkwall_below', 'checkhole_in', 'checkholeindex_in', 'ent_unlink', 'adjust_base')
    rows = ['{%du,%d,%d,%d}' % (r['revision'], r['basemap_gated'],
            r['selected_hole'], r['writes_holez']) for r in data['sources']]
    values = dict(FUNCTIONS='\n'.join(function(core, n) for n in names),
                  BASEMAP=rename_identifiers(function(core, 'check_basemap'),
                      {'check_basemap': 'probe_native_check_basemap'}),
                  CONTEXTS=','.join(rows))
    text = Path(__file__).with_name('terrain_base_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native terrain base dependency')
    return text


class TerrainBaseContracts(unittest.TestCase):
    def test_participation_native_cells_walls_and_falling_order(self):
        data = fixture_data()
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], status='PASS')
                                  for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
