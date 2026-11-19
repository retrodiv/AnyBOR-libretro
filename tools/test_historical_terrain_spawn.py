"""Check complete native player spawn searches against original hole queries.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-terrain-spawn-contracts.json'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [r['revision'] for r in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own spawn sources and actual transition controls required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or row['height_query'] not in (0, 1) or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not re.fullmatch('[0-9a-f]{64}', row['source_sha256']['openbor.c']) or
                len(row['height_hits']) != 4 or any(v not in (0, 1) for v in row['height_hits'])):
            raise ValueError('Complete source-bound native spawn expectations required')
    return data


def program(data):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    names = ('obor_terrain_between', 'testhole', 'testwall', 'checkhole',
             'checkhole_in', 'checkwall', 'spawnplayer')
    values = dict(FUNCTIONS='\n'.join(function(core, n) for n in names),
        CONTEXTS=','.join('{%du,%d,{%s}}' % (r['revision'], r['height_query'],
            ','.join(str(v) for v in r['height_hits'])) for r in data['sources']))
    text = Path(__file__).with_name('terrain_spawn_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native spawn dependency')
    return text


class TerrainSpawnContracts(unittest.TestCase):
    def test_single_lane_depth_search_walls_and_spawn_coordinates(self):
        data = fixture_data()
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], status='PASS')
                                  for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
