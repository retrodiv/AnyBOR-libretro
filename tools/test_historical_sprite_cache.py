"""Check historical sprite-map growth and queued missing-image policy.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-sprite-cache-contracts.json'


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    queue = (engine / 'source/gamelib/spriteq.c').read_text()
    starts = list(re.finditer(r'(?m)^#define[ \t]+MAXQSPRITES\b', queue))
    if len(starts) != 1:
        raise ValueError('One native queue declaration required')
    end = queue.index('void spriteq_add_frame(', starts[0].start())
    helper = Path(__file__).with_name('draw_repeat_script_contract.c.in').read_text()
    parts = dict(STORAGE=queue[starts[0].start():end],
        FUNCTIONS='\n'.join(function(core, name) for name in
                           ('obor_profile_sprite_map_capacity', 'prepare_sprite_map')),
        QUEUE=function(queue, 'spriteq_add_sprite'),
        SAME_METHOD=function(helper, 'same_method'),
        CONTEXTS=','.join('{%du,%d,%d}' % (r['revision'], r['growth'], r['reload'])
                          for r in data['sources']),
        GROWTH=','.join('{%s}' % ','.join(str(r[k]) for k in data['growth_parameters'])
                        for r in data['growth_cases']))
    text = Path(__file__).with_name('sprite_cache_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved sprite cache dependency')
    return text


class SpriteCacheContracts(unittest.TestCase):
    def test_native_map_growth_and_missing_frame_queue_policy(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({r['revision'] for r in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len({r['revision'] for r in data['sources']}), len(data['sources']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], growth_cases=len(data['growth_cases']),
            queue_cases=16, invalid_cases=4) for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
