"""Check drawing enable and queued drawing records against historical sources.

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


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-drawing-queue-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    queue = (engine / 'source/gamelib/spriteq.c').read_text()
    pixel = (engine / 'source/gamelib/pixelformat.c').read_text()
    draw = (engine / 'source/gamelib/draw.c').read_text()
    stop = queue.index('} qstruct;') + len('} qstruct;')
    start = queue.rindex('typedef struct', 0, stop)
    definitions = queue[queue.index('#define\t\t\tMAXQSPRITES'):stop]
    if definitions.count('typedef struct') != 1 or definitions[-len(queue[start:stop]):] != queue[start:stop]:
        raise ValueError('One native drawing queue record required')
    parts = dict(
        QUEUE_RECORD=definitions,
        QUEUE_FUNCTIONS='\n'.join(function(queue, name) for name in data['functions']),
        PIXEL_INIT=function(pixel, 'drawmethod_global_init'),
        DRAW_INIT=function(draw, 'draw_init'),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    text = Path(__file__).with_name('modern_drawing_queue_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved drawing queue contract dependency')
    return text


class ModernDrawingQueueContracts(unittest.TestCase):
    def test_enable_initialization_and_queue_records(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[
            dict(revision=row['revision'], **data['contracts'][row['contract']])
            for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
