"""Check native media storage relationships across moving resizes.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture
from test_historical_common_think import ROOT, native_output

FIXTURE = Path(__file__).with_name('fixtures') / 'media-allocation-links-contracts.json'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    engines = [row['engine'] for row in data['engines']]
    if not engines or len(engines) != len(set(engines)):
        raise ValueError('Distinct native media engine controls required')
    for row in data['engines']:
        if (not re.fullmatch('[0-9]+', row['engine']) or type(row['revision']) is not int or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not re.fullmatch('[0-9a-f]{64}', row['source_sha256']) or
                row.get('expected') != dict(status='PASS', scenarios=5)):
            raise ValueError('Exact own media source identity required')
    return data


class MediaAllocationLinks(unittest.TestCase):
    def test_native_detached_attached_children_and_resize_refusal(self):
        data = fixture_data()
        code = Path(__file__).with_name('media_allocation_links_contract.c.in').read_text()
        for row in data['engines']:
            with self.subTest(engine=row['engine']):
                engine = ROOT / 'src/engines' / row['engine']
                program = code.replace('@REVISION@', str(row['revision']))
                actual = [json.loads(line) for line in native_output(program, row,
                    extra_includes=[engine / 'source/webmlib/halloc']).splitlines()]
                self.assertEqual(actual, [row['expected']])


if __name__ == '__main__':
    unittest.main()
