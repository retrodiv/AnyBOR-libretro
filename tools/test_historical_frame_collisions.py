"""Check native frame collision records, vulnerability and offsets by profile.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-frame-collision-construction-contracts.json'
METHODS = ('alloc_frames', 'free_frames', 'collision_alloc_coords',
           'collision_alloc_attack_instance', 'collision_alloc_attack_list',
           'collision_alloc_body_instance', 'collision_alloc_body_list', 'addframe')


def program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text(encoding='latin1')
    cases = []
    for case in data['cases']:
        values = [str(case['slots']), str(case['damage'])]
        values.extend('{' + ','.join(str(value) for value in case[name]) + '}'
                      for name in ('body', 'attack', 'offset'))
        cases.append('{' + ','.join(values) + '}')
    values = {
        'FUNCTIONS': '\n'.join(function(source, name) for name in METHODS),
        'REVISIONS': ','.join(str(row['revision']) for row in data['sources']),
        'CASES': ',\n'.join(cases),
    }
    template = Path(__file__).with_name('frame_collision_construction_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


class FrameCollisionConstructionTests(unittest.TestCase):
    def test_original_construction_contracts(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        expected = [[row['revision'], *result] for row in data['sources']
                    for result in data['contracts'][row['contract']]]
        self.assertEqual(len(actual), len(expected))
        for result, reference in zip(actual, expected):
            with self.subTest(revision=reference[0], case=data['cases'][reference[1]]['name']):
                self.assertEqual(result, reference)


if __name__ == '__main__':
    unittest.main()
