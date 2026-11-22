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
    def test_original_entity_debug_rectangle_edges(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        code = r'''
#include <stdint.h>
#include "openbor.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
s_level *level;
float advancex = 10;
float advancey = 5;
int gfx_x_offset = 3;
int gfx_y_offset = 4;

static s_drawmethod method;
static int box_x, box_y, boxes, edges;

void spriteq_add_box(int x, int y, int width, int height, int depth, int color, s_drawmethod *drawmethod)
{
    assert(boxes == 0 && edges == 0);
    assert(x == box_x && y == box_y && width == 12 && height == 8);
    assert(depth == 82 && color == 37 && drawmethod == &method);
    ++boxes;
}

void spriteq_add_line(int sx, int sy, int ex, int ey, int depth, int color, s_drawmethod *drawmethod)
{
    const int expected[][4] = {
        { box_x, box_y, box_x + 11, box_y },
        { box_x, box_y + 8, box_x + 11, box_y + 8 },
        { box_x, box_y, box_x, box_y + 8 },
        { box_x + 11, box_y, box_x + 11, box_y + 8 },
    };
    assert(boxes == 1 && edges < 4);
    const int *edge = expected[edges++];
    assert(sx == edge[0] && sy == edge[1] && ex == edge[2] && ey == edge[3]);
    assert(depth == 82 && color == 37 && drawmethod == NULL);
}

@DRAW_BOX@

int main(void)
{
    const unsigned builds[] = {7369, 7391, 7420, 7421, 7533};
    static s_level current_level = {.scrolldir = SCROLL_RIGHT};
    static entity actor;
    level = &current_level;
    actor.position.x = 60;
    actor.position.y = 10;
    actor.position.z = 84;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        actor.direction = DIRECTION_RIGHT;
        actor.modeldata.quake_config = 0;
        box_x = 55;
        box_y = 74;
        boxes = edges = 0;
        draw_box_on_entity(&actor, 2, 3, 80, 14, 11, 2, 37, &method);
        assert(boxes == 1 && edges == (builds[i] < 7421 ? 0 : 4));

        actor.direction = DIRECTION_LEFT;
        actor.modeldata.quake_config = QUAKE_CONFIG_DISABLE_SELF;
        box_x = 36;
        box_y = 70;
        boxes = edges = 0;
        draw_box_on_entity(&actor, 2, 3, 80, 14, 11, 2, 37, &method);
        assert(boxes == 1 && edges == (builds[i] < 7421 ? 0 : 4));
    }
    return 0;
}
'''
        code = code.replace('@DRAW_BOX@', function(source, 'draw_box_on_entity'))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

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
