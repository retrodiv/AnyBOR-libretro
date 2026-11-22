"""Check complete native movement callers with original hole-query periods.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-terrain-movement-contracts.json'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [row['revision'] for row in data['sources']]
    if (data['engine'] != '4432' or len(revisions) != len(set(revisions)) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Original movement contexts and transition controls required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not re.fullmatch('[0-9a-f]{64}', row['source_sha256']['openbor.c']) or
                any(row[name] not in (0, 1) for name in
                    ('testmove_height', 'trymove_height', 'height_writes_holez')) or
                len(row['height_hits']) != 4 or
                any(value not in (0, 1) for value in row['height_hits'])):
            raise ValueError('Own-source movement selection and hole observations required')
    return data


def program(data, *, movement_decisions=False):
    core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    names = ('diff', 'inair', 'obor_terrain_between', 'testhole', 'checkhole',
             'checkhole_in', 'testmove', 'common_trymove')
    decisions = ''
    if movement_decisions:
        rows = ['{%du,0,0,0,{0,0,0,0}}' % row['revision'] for row in data['sources']]
        decisions = Path(__file__).with_name('terrain_movement_decisions.c.in').read_text()
        decisions = decisions.replace('@DECISION_ROWS@', ','.join('{%d,%d,%d}' %
            (row['wander_draw'], row['item_draw'], row['negative_wall']) for row in data['sources']))
        wander = re.search(r'(?ms)^    //mod = [^\n]*\n(.*?)^    if\(dox\)',
                           function(core, 'common_try_wander'))[1]
        item = re.search(r'(?ms)^[ \t]*//other = [^\n]*normal_find_item[^\n]*\n(.*?)'
                         r'^[ \t]*owner = self->parent;', function(core, 'common_move'))[1]
        decisions = decisions.replace('@WANDER@', wander).replace('@ITEM@', item)
    else:
        rows = ['{%du,%d,%d,%d,{%s}}' % (r['revision'], r['testmove_height'],
                r['trymove_height'], r['height_writes_holez'],
                ','.join(str(value) for value in r['height_hits'])) for r in data['sources']]
    text = Path(__file__).with_name('terrain_movement_contract.c.in').read_text()
    for key, value in dict(FUNCTIONS='\n'.join(function(core, n) for n in names),
                           CONTEXTS=','.join(rows), MOVEMENT_DECISIONS=decisions).items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native movement dependency')
    return text


class TerrainMovementContracts(unittest.TestCase):
    def test_7533_original_movement_terrain_and_path_recovery(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        core = (engine / 'openbor.c').read_text()
        code = r'''
#include <stdint.h>
#include "openbor.h"
#undef assert
#undef printf
#include <assert.h>

uint32_t obor_profile_build;
u32 _time = 50;
int PLAYER_MIN_Z = 20, PLAYER_MAX_Z = 110;
float advancex;
s_videomodes videomodes;
static entity actor, obstacle_platform;
static s_terrain wall;
static s_level stage;
s_level *level = &stage;
entity *self = &actor;
static unsigned between_calls, below_calls, wall_calls, walk_calls;
static int allow_platform_floor;

entity *check_platform_between(float x, float z, float lower, float upper, entity *exclude)
{
    assert(x == 11 && z == 30 && lower == 20 && upper == 30 && exclude == &actor);
    ++between_calls;
    return &obstacle_platform;
}

entity *check_platform_below(float x, float z, float height, entity *exclude)
{
    assert(x == 11 && z == 30 && height == actor.position.y + T_WALKOFF && exclude == &actor);
    ++below_calls;
    return allow_platform_floor ? &obstacle_platform : NULL;
}

int checkwall_below(float x, float z, float height)
{
    assert(x == 11 && z == 25 && height == T_MAX_CHECK_ALTITUDE);
    ++wall_calls;
    return 0;
}

float get_platform_base(entity *platform) { assert(platform == &obstacle_platform); return 20; }
void adjust_walk_animation(entity *other) { assert(other == NULL); ++walk_calls; }
float randf(float max) { assert(max == 1); return 0.8f; }
int checkhole(float x, float z) { assert(0); return 0; }
int checkwall_index(float x, float z) { assert(0); return -1; }
entity *find_ent_here(entity *exclude, float x, float z, e_entity_type types, int (*test)(entity *, entity *))
{ assert(0); return NULL; }
entity *normal_find_target(int anim, int detect) { assert(0); return NULL; }
int astar(entity *ent, float x, float z, float step, s_axis_plane_lateral_float **waypoints)
{ assert(0); return 0; }

@METHODS@

static void check_movement(void)
{
    s_anim animation = {.numframes = 1, .size.y = 10, .range.x.max = 15};
    s_anim *animations[ANI_JUMP + 1] = {0};
    actor = (entity){.position.y = 20, .animation = &animation};
    actor.modeldata.animation = animations;
    actor.modeldata.animation_capacity = sizeof(animations) / sizeof(*animations);

    between_calls = below_calls = wall_calls = 0;
    actor.modeldata.move_config_flags = MOVE_CONFIG_SUBJECT_TO_PLATFORM;
    allow_platform_floor = 0;
    assert(testmove(&actor, 10, 30, 11, 30) == 0);
    allow_platform_floor = 1;
    assert(testmove(&actor, 10, 30, 11, 30) == 1);
    assert(between_calls == 2 && below_calls == 2 && wall_calls == 0);

    actor.modeldata.move_config_flags = MOVE_CONFIG_SUBJECT_TO_WALL;
    wall = (s_terrain){.height = 30, .z = 25, .depth = 10};
    assert(testmove(&actor, 10, 20, 11, 25) == 0);
    animations[ANI_JUMP] = &animation;
    assert(testmove(&actor, 10, 20, 11, 25) == -1);
    actor.position.y = 30;
    assert(testmove(&actor, 10, 20, 11, 25) == 1);
    assert(wall_calls == 3);
}

static void check_path_recovery(void)
{
    actor = (entity){.stalltime = _time, .running = RUN_STATE_START_X};
    actor.position.z = 109;
    actor.velocity.z = 3;
    actor.modeldata.move_config_flags = MOVE_CONFIG_SUBJECT_TO_MAX_Z;
    walk_calls = 0;
    assert(checkpathblocked() == 1);
    assert(walk_calls == 1 && actor.velocity.z == -3 && actor.destz == 86);
    actor.position.z = 21;
    actor.modeldata.move_config_flags = MOVE_CONFIG_SUBJECT_TO_MIN_Z;
    assert(checkpathblocked() == 1);
    assert(walk_calls == 2 && actor.velocity.z == 3 && actor.destz == 44);

    actor.modeldata.move_config_flags = MOVE_CONFIG_NONE;
    actor.modeldata.speed.x = 4;
    actor.velocity.x = 2;
    actor.velocity.z = 0;
    actor.pathblocked = 41;
    assert(checkpathblocked() == 1);
    assert(walk_calls == 3 && actor.running == RUN_STATE_NONE && actor.pathblocked == 0);
    assert(actor.velocity.x == 0 && actor.velocity.z == 4 && actor.destz == 61);
}

int main(void)
{
    static const unsigned builds[] = {7369, 7390, 7391, 7420, 7426, 7427, 7446, 7447, 7497, 7498, 7533};
    stage.walls = &wall;
    videomodes.vRes = 240;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        check_movement();
        check_path_recovery();
    }
    return 0;
}
'''
        methods = ('diff', 'obor_profile_static_move_flags', 'testmove', 'checkpathblocked')
        code = code.replace('@METHODS@', '\n'.join(function(core, name) for name in methods))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_4432_wander_item_draws_and_wall_participation(self):
        fixture = Path(__file__).with_name('fixtures') / 'profile-movement-decision-contracts.json'
        data = load_contract_fixture(fixture)
        self.assertEqual(data['engine'], '4432')
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        for row in data['sources']:
            for key in ('wander_draw', 'item_draw', 'negative_wall'):
                self.assertIs(type(row[key]), bool)
        actual = [json.loads(line) for line in native_output(
            program(data, movement_decisions=True), data).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], status='PASS') for row in data['sources']])
        print(f'{len(revisions)} movement decision contexts passed.', flush=True)

    def test_height_query_periods_axis_results_and_movement_callbacks(self):
        data = fixture_data()
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], status='PASS')
                                  for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
