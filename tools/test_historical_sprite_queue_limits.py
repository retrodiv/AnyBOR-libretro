"""Check native queue admission and readouts at own-source size boundaries.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-sprite-queue-limit-contracts.json'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    rows = data['sources']
    revisions = [r['revision'] for r in rows]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own queue contexts and both source-boundary controls required')
    for row in rows:
        if (row['engine'] != data['engine'] or type(row['limit']) is not int or
                not 0 < row['limit'] <= 5000 or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not re.fullmatch('[0-9a-f]{64}', row['source_sha256']['source/gamelib/spriteq.c'])):
            raise ValueError('Bound original queue source and literal admission limit required')
    return data


def program(data):
    queue = (ROOT / 'src/engines' / data['engine'] / 'source/gamelib/spriteq.c').read_text()
    begin = re.search(r'(?m)^#define[ \t]+MAXQSPRITES\b', queue)
    if begin is None:
        raise ValueError('Native queue storage declaration missing')
    stop = queue.index('void spriteq_add_frame(', begin.start())
    names = ('spriteq_add_frame', 'spriteq_add_sprite', 'spriteq_add_screen',
             'spriteq_add_dot', 'spriteq_add_line', 'spriteq_add_box',
             'spriteq_lock', 'spriteq_unlock', 'spriteq_clear', 'spriteq_islocked')
    values = dict(STORAGE=queue[begin.start():stop],
        FUNCTIONS='\n'.join(function(queue, n) for n in names),
        PROFILES=','.join('{%du,%du}' % (r['revision'], r['limit']) for r in data['sources']))
    text = Path(__file__).with_name('sprite_queue_limit_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native queue dependency')
    return text


class SpriteQueueLimitContracts(unittest.TestCase):
    def test_admission_drop_readouts_and_locked_prefix_by_profile(self):
        data = fixture_data()
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(status='PASS', contexts=len(data['sources']),
                                      routes=len(data['sources']) * 7)])


if __name__ == '__main__':
    unittest.main()
