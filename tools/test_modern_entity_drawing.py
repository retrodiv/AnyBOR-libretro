"""Check native entity/frame method selection and shadow orientation.

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
from native_header_fixtures import assertion_refusals


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-entity-drawing-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    display = function(core, 'display_ents')
    start = re.search(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{', core)
    if start is None:
        raise ValueError('Native drawing default required')
    selection = display[display.index('drawmethod = e->animation->drawmethods ?'):display.index('// Color selection.')]
    facing = display[display.index('if(e->direction == DIRECTION_LEFT)'):display.index("// don't display if behind the mirror")]
    shadow = display[display.index('shadowmethod = plainmethod;'):]
    last = 'spriteq_add_sprite(qx, sy, sz, f, &shadowmethod, 0);'
    end = shadow.index(last) + len(last)
    shadow = shadow[:shadow.index('}', end) + 1]
    add = function(core, 'addframe')
    storage = add[add.index('if(obor_profile_build >='):add.index('// Idle flag.')]
    spawn = function(core, 'spawn')
    index = spawn.index('acting_entity->drawmethod = allocate_drawmethod();')
    spawn = spawn[index:spawn.index('// add to list', index)]
    hud = function(core, 'predrawstatus')
    index = hud.index('drawmethod.table = 0;')
    hud = hud[index:hud.index('spriteq_add_sprite(40,', index)]
    parts = dict(ASSERTIONS=assertion_refusals(),
        DEFAULT=core[start.start():core.index('\n};', start.end()) + 3],
        HELPERS='\n'.join(function(core, n) for n in ('allocate_drawmethod', 'getDrawMethod', 'setDrawMethod')),
        SELECTION=selection, FACING=facing, SHADOW=shadow, STORAGE=storage, SPAWN=spawn, HUD=hud,
        PROFILES=','.join(str(s['revision']) + 'u' for s in data['sources']),
        STATES=','.join('{' + ','.join(str(v) for v in row) + '}' for row in data['states']),
        LIGHTS=','.join(str(v) for v in data['lights']))
    code = Path(__file__).with_name('modern_entity_drawing_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved entity drawing contract input')
    return code


class ModernEntityDrawingContracts(unittest.TestCase):
    def test_frame_selection_facing_shadow_hud_and_spawn(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [s['revision'] for s in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=s['revision'], **data['contracts'][s['contract']])
                                               for s in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
