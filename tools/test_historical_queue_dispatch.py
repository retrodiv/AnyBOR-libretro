"""Check source-owned queue coordinates and depth/lock dispatch.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-queue-dispatch-contracts.json'


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    queue = (engine / 'source/gamelib/spriteq.c').read_text()
    draw = (engine / 'source/gamelib/draw.c').read_text()
    starts = list(re.finditer(r'(?m)^#define[ \t]+MAXQSPRITES\b', queue))
    if len(starts) != 1:
        raise ValueError('One native queue storage declaration required')
    end = queue.index('void spriteq_add_frame(', starts[0].start())
    parts = dict(STORAGE=queue[starts[0].start():end],
        QUEUE='\n'.join(function(queue, n) for n in ('spriteq_sort', 'spriteq_draw')),
        WRAPPERS='\n'.join(function(draw, n) for n in ('draw_init', 'putpixel', 'putline', 'putbox')),
        CONTEXTS=','.join('{%du,%d}' % (r['revision'], r['offsets']) for r in data['sources']),
        CASES=',\n'.join('{%s}' % ','.join(str(r[k]) for k in data['parameters'])
                           for r in data['cases']))
    text = Path(__file__).with_name('queue_dispatch_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved queue dispatch dependency')
    return text


class QueueDispatchContracts(unittest.TestCase):
    def test_native_coordinates_formats_depth_and_locked_prefix(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({r['revision'] for r in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len({r['revision'] for r in data['sources']}), len(data['sources']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], cases=len(data['cases']))
                                  for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
