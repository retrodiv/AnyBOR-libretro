"""Check profile-owned projectile speed sources and explosion animation flags.

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


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-projectile-contracts.json'
SPAWN_HELPERS = ('obor_profile_static_move_flags', 'obor_legacy_projectile_direction', 'obor_projectile_spawn_x',
                 'obor_fill_projectile_faction', 'obor_copy_projectile_faction', 'obor_apply_knife_inheritance')


def program(data, engine):
    core = (engine / 'openbor.c').read_text()
    launches = []
    for case in data['launch_cases']:
        values = [str(case[name]) for name in data['launch_fields']]
        vectors = ['{' + ','.join('.' + axis + '=' + str(value)
                                  for axis, value in zip(('x', 'y', 'z'), case[name])) + '}'
                   for name in ('model_speed', 'argument_velocity')]
        launches.append('{' + ','.join(values + vectors) + '}')
    detonations = ['{' + ','.join(str(case[name]) for name in data['detonation_fields']) + '}'
                   for case in data['detonation_cases']]
    parts = dict(FUNCTIONS='\n'.join(function(core, name) for name in
                                   (*SPAWN_HELPERS, 'knife_spawn', 'bomb_spawn', 'bomb_try_detonate')),
                 LAUNCH_CASES=',\n'.join(launches), DETONATION_CASES=',\n'.join(detonations),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    code = Path(__file__).with_name('modern_projectile_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved projectile contract input')
    return code


class ModernProjectileContracts(unittest.TestCase):
    def test_projectile_model_types_preserve_original_ai_and_terrain_defaults(self):
        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        code = r'''
#include <stdint.h>
#include <strings.h>
#include "openbor.h"
#undef stricmp
#define stricmp strcasecmp
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
s_videomodes videomodes = {.hRes = 600};

void borShutdown(int status, char *message, ...) { abort(); }

@READ_TYPE@

static void check_model(int generic, int preset, e_move_config_flags movement, e_aimove default_ai)
{
    ArgList args = {.count = 2, .args = {"type", generic ? "projectile" : "pshot"}};
    s_model model = {
        .type = generic ? TYPE_ENEMY : TYPE_OBSTACLE,
        .aimove = preset ? AIMOVE1_AVOID : obor_unspecified_aimove(),
        .offscreenkill = preset ? 53 : 0,
        .move_config_flags = MOVE_CONFIG_SUBJECT_TO_SCREEN | MOVE_CONFIG_SUBJECT_TO_OBSTACLE |
            MOVE_CONFIG_SUBJECT_TO_BASEMAP | MOVE_CONFIG_SUBJECT_TO_PLATFORM | MOVE_CONFIG_SUBJECT_TO_WALL
    };
    lcmHandleCommandType(&args, &model, "projectile-model");
    assert(model.type == (generic ? (TYPE_ENEMY | TYPE_PROJECTILE) : TYPE_SHOT));
    assert(model.offscreenkill == (preset ? 53 : (generic ? 300 : 200)));
    assert(model.move_config_flags == (movement | MOVE_CONFIG_SUBJECT_TO_OBSTACLE));
    const e_aimove expected_ai = preset ? (AIMOVE1_AVOID | (default_ai & AIMOVE1_ARROW)) : default_ai;
    assert(model.aimove == expected_ai);
}

int main(void)
{
    const int airborne = MOVE_CONFIG_SUBJECT_TO_GRAVITY |
        MOVE_CONFIG_SUBJECT_TO_MIN_Z | MOVE_CONFIG_SUBJECT_TO_MAX_Z;
    const int terrain = MOVE_CONFIG_SUBJECT_TO_BASEMAP | MOVE_CONFIG_SUBJECT_TO_HOLE |
        MOVE_CONFIG_SUBJECT_TO_PLATFORM | MOVE_CONFIG_SUBJECT_TO_WALL;
    const int bounce = MOVE_CONFIG_PROJECTILE_WALL_BOUNCE;
    const int fixed_base = MOVE_CONFIG_NO_ADJUST_BASE;
    const struct {
        uint32_t build;
        int projectile_move, shot_move;
        int projectile_ai, shot_ai;
    } cases[] = {
        {7369, fixed_base, fixed_base, AIMOVE1_ARROW, AIMOVE1_ARROW},
        {7381, fixed_base, fixed_base, AIMOVE1_ARROW, AIMOVE1_ARROW},
        {7382, fixed_base, fixed_base, AIMOVE1_NORMAL, AIMOVE1_ARROW | AIMOVE1_NORMAL},
        {7391, fixed_base, fixed_base, AIMOVE1_NORMAL, AIMOVE1_ARROW | AIMOVE1_NORMAL},
        {7420, fixed_base, fixed_base, AIMOVE1_NORMAL, AIMOVE1_ARROW | AIMOVE1_NORMAL},
        {7426, fixed_base, fixed_base, AIMOVE1_NORMAL, AIMOVE1_ARROW | AIMOVE1_NORMAL},
        {7427, bounce, fixed_base, AIMOVE1_NORMAL, AIMOVE1_ARROW | AIMOVE1_NORMAL},
        {7431, bounce, fixed_base, AIMOVE1_NORMAL, AIMOVE1_ARROW | AIMOVE1_NORMAL},
        {7432, terrain | bounce | MOVE_CONFIG_PROJECTILE_BASE_DIE, fixed_base | bounce,
            AIMOVE1_NORMAL, AIMOVE1_ARROW | AIMOVE1_NORMAL},
        {7533, terrain | bounce | MOVE_CONFIG_PROJECTILE_BASE_DIE, fixed_base | bounce,
            AIMOVE1_NORMAL, AIMOVE1_ARROW | AIMOVE1_NORMAL},
    };
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i)
    {
        obor_profile_build = cases[i].build;
        for (int preset = 0; preset <= 1; ++preset)
        {
            check_model(1, preset, airborne | cases[i].projectile_move, cases[i].projectile_ai);
            check_model(0, preset, airborne | cases[i].shot_move, cases[i].shot_ai);
        }
    }
    puts("PASS");
}
'''
        code = code.replace('@READ_TYPE@', '\n'.join(function(source, name) for name in
                                                    ('obor_add_model_aimove', 'lcmHandleCommandType')))
        self.assertEqual(native_output(code, data, engine_source=engine), 'PASS\n')

    def test_7533_projectile_initialization_uses_original_shot_defaults(self):
        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        core = (engine / 'openbor.c').read_text(encoding='latin1')
        initialize = function(core, 'ent_default_init')
        start = initialize.index('case TYPE_PROJECTILE:')
        stop = initialize.index('case TYPE_NONE:', start)
        template = Path(__file__).with_name('modern_projectile_initialization_contract.c.in').read_text()
        code = (template.replace('@DEFAULTS@', initialize[start:stop])
                .replace('@MOVE_FLAGS@', function(core, 'obor_profile_static_move_flags')))
        self.assertEqual(native_output(code, data, engine_source=engine), 'PASS\n')

    def test_7533_wall_deflection_uses_original_motion_and_terrain(self):
        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        core = (engine / 'openbor.c').read_text(encoding='latin1')
        template = Path(__file__).with_name('modern_legacy_ricochet_contract.c.in').read_text()
        code = template.replace('@DEFLECT@', function(core, 'projectile_wall_deflect'))
        self.assertEqual(native_output(code, data, engine_source=engine), 'PASS\n')

    def test_legacy_projectile_spawn_coordinates_inheritance_and_terrain(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        names = ('allocate_projectile', 'direction_get_adjustment_result', *SPAWN_HELPERS,
                 'knife_spawn', 'bomb_spawn', 'star_spawn')
        template = Path(__file__).with_name('modern_legacy_projectile_spawn_contract.c.in').read_text()
        default_start = source.index('const s_projectile projectile_default_config = {')
        default_end = source.index('\n};', default_start) + 3
        definitions = [source[default_start:default_end], *(function(source, name) for name in names)]
        code = template.replace('@FUNCTIONS@', '\n'.join(definitions))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_speed_sources_argument_mutation_and_shared_animation_gravity(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[
            dict(revision=row['revision'], **data['contracts'][row['contract']])
            for row in data['sources']])
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        self.assertEqual(json.loads(native_output(program(data, engine), data, engine_source=engine)), expected)


if __name__ == '__main__':
    unittest.main()
