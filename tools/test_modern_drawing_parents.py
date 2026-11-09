"""Check historical drawing dispatch, repeats and source transparency.

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


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-drawing-parent-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    units = {name: (engine / 'source/gamelib' / (name + '.c')).read_text()
             for name in ('sprite', 'screen', 'pixelformat', 'transform')}
    init = function(units['transform'], 'init_gfx_global_draw_stuff')
    key = re.findall(r'^[ \t]*transbg = [^;]+;', init, re.M)
    key = [line for line in key if 'sprite_magic' in line]
    if len(key) != 1:
        raise ValueError('One native source transparency expression required')
    parts = dict(
        FUNCTIONS='\n'.join([function(units['pixelformat'], 'drawmethod_global_init'),
                             function(units['screen'], 'obor_screen_blend_table'),
                             function(units['screen'], '_putscreen'),
                             function(units['screen'], 'putscreen'),
                             function(units['sprite'], '_putsprite'),
                             function(units['sprite'], 'putsprite')]),
        SOURCE_KEY=key[0],
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=','.join('{%d,%uu,%d,%d}' % tuple(row) for row in data['states']))
    code = Path(__file__).with_name('modern_drawing_parent_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved drawing parent contract dependency')
    return code


class ModernDrawingParentContracts(unittest.TestCase):
    def test_parent_dispatch_repeats_and_source_transparency(self):
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
