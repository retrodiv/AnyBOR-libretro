"""Check attack defaults and the original model directives for damage.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_early_jump_walkoff import braced_statement, continued_macro
from test_historical_common_think import ROOT, native_output
from test_historical_model_defaults import model_command_functions
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-attack-initialization-contracts.json'


# The original command registries record the first revision of each spelling.
# Three values also specify a withdrawal and restoration.
MODERN_MODEL_DIRECTIVES = {
    (7380,): (
        'child_spawn_config', 'child_spawn_direction_adjust', 'child_spawn_index',
        'child_spawn_model', 'child_spawn_offset_x', 'child_spawn_offset_y', 'child_spawn_offset_z',
        'child_spawn_velocity_x', 'child_spawn_velocity_y', 'child_spawn_velocity_z',
    ),
    (7384,): (
        'child_spawn_aimove',
    ),
    (7386,): (
        'child_spawn_candamage', 'child_spawn_hostile', 'child_spawn_preset_bomb',
        'child_spawn_preset_shot', 'child_spawn_projectilehit',
    ),
    (7390,): (
        'child_spawn_takedamage',
    ),
    (7432,): (
        'weapon_loss_config',
    ),
    (7435,): (
        'child_spawn_color', 'defense.block.damage.adjust', 'defense.block.damage.max',
        'defense.block.damage.min', 'defense.damage.adjust', 'defense.damage.max',
        'defense.damage.min', 'offense.damage.adjust', 'offense.damage.max', 'offense.damage.min',
        'offense.factor',
    ),
    (7439,): (
        'attack.effect.hit.flash.layer.adjust', 'attack.effect.hit.flash.layer.source',
        'attack.effect.hit.flash.z.source', 'bbox.effect.hit.flash.layer.adjust',
        'bbox.effect.hit.flash.layer.source', 'bbox.effect.hit.flash.z.source',
    ),
    (7445,): (
        'faction_group_damage_direct', 'faction_group_damage_indirect', 'faction_group_hostile',
        'faction_group_member', 'faction_type_damage_direct', 'faction_type_damage_indirect',
        'faction_type_hostile',
    ),
    (7479,): (
        'shadow_config',
    ),
    (7482, 7487, 7489): (
        'death_config',
    ),
    (7483, 7486, 7489): (
        'defense.death.config',
    ),
    (7493,): (
        'block_config',
    ),
    (7494,): (
        'pain_config',
    ),
    (7495,): (
        'enhanced_delay_cap_max', 'enhanced_delay_cap_min', 'enhanced_delay_modifer',
        'enhanced_delay_multiplier', 'enhanced_delay_range_max', 'enhanced_delay_range_min',
    ),
    (7497,): (
        'jump_height', 'jump_speed',
    ),
    (7498,): (
        'child_spawn_move_config', 'move_config',
    ),
    (7512,): (
        'child_follow_offset_x', 'child_follow_offset_y', 'child_follow_offset_z', 'run_config',
    ),
    (7530,): (
        'child_follow_direction_adjust_config', 'child_follow_direction_adjust_range_x_max',
        'child_follow_direction_adjust_range_x_min', 'child_follow_direction_adjust_range_y_max',
        'child_follow_direction_adjust_range_y_min', 'child_follow_direction_adjust_range_z_max',
        'child_follow_direction_adjust_range_z_min', 'child_follow_range_recall_base_max',
        'child_follow_range_recall_base_min', 'child_follow_range_recall_x_max',
        'child_follow_range_recall_x_min', 'child_follow_range_recall_y_max',
        'child_follow_range_recall_y_min', 'child_follow_range_recall_z_max',
        'child_follow_range_recall_z_min', 'child_follow_range_run_x_max',
        'child_follow_range_run_x_min', 'child_follow_range_run_y_max',
        'child_follow_range_run_y_min', 'child_follow_range_run_z_max',
        'child_follow_range_run_z_min', 'child_follow_range_x_max', 'child_follow_range_x_min',
        'child_follow_range_y_max', 'child_follow_range_y_min', 'child_follow_range_z_max',
        'child_follow_range_z_min', 'child_follow_recall_animation', 'child_follow_recall_offset_x',
        'child_follow_recall_offset_y', 'child_follow_recall_offset_z',
    ),
}


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    defaults = []
    for declaration in ('const s_attack emptyattack', 's_axis_principal_float default_model_dropv'):
        match = re.search(r'(?ms)^' + declaration + r'\s*=\s*\{.*?^\};', core)
        if match is None:
            raise ValueError('Complete native attack/default velocity required')
        defaults.append(match[0])
    kill = function(core, 'kill_entity')
    kill, replaced = re.subn(r'^void kill_entity\(', 'void observed_kill_entity(', kill, count=1)
    if replaced != 1:
        raise ValueError('Complete parent-removal caller required')
    parts = dict(DEFAULTS='\n'.join(defaults), FUNCTIONS='\n'.join([
        function(core, 'obor_animation_can_reschedule'), function(core, 'update_frame'),
        kill, function(core, 'checkdamageonlanding')]),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=','.join('{' + ','.join(str(v) for v in row) + '}' for row in data['cases']))
    code = Path(__file__).with_name('modern_attack_initialization_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved attack initializer input')
    return code


class ModernAttackInitializationContracts(unittest.TestCase):
    def test_original_weapon_inheritance_and_basic_assets(self):
        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        model_change = function(source, 'set_model_ex')
        start = model_change.index('// copy the weapon list')
        weapon_copy = model_change[start:]
        opening = re.search(r'(?m)^    (if \([^\n]+)', weapon_copy)
        self.assertIsNotNone(opening)
        rule = braced_statement(weapon_copy, opening[1])
        code = r'''
#include "openbor.h"
#include <stdlib.h>

uint32_t obor_profile_build;

static void inherit_weapon_properties(s_model *newmodel, const s_model *model)
{
@WEAPON_COPY@
}

int main(void)
{
    static const unsigned builds[] = {7369, 7374, 7375, 7391, 7420, 7533};
    static const unsigned flags[] = {0, MODEL_COPY_FLAG_NO_BASIC, MODEL_COPY_FLAG_NO_WEAPON,
                                      MODEL_COPY_FLAG_NO_BASIC | MODEL_COPY_FLAG_NO_WEAPON};
    static int inherited[] = {2, 3}, own[] = {6};
    static s_model source, target;
    source.weapon_properties.weapon_list = inherited;
    source.weapon_properties.weapon_count = 2;
    source.weapon_properties.weapon_index = 3;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        for (size_t j = 0; j < sizeof(flags) / sizeof(*flags); ++j)
        {
            target.model_flag = flags[j];
            const int copies = !(flags[j] & MODEL_COPY_FLAG_NO_WEAPON) &&
                (builds[i] >= 7375u || !(flags[j] & MODEL_COPY_FLAG_NO_BASIC));
            target.weapon_properties.weapon_list = NULL;
            target.weapon_properties.weapon_count = 0;
            target.weapon_properties.weapon_index = 0;
            inherit_weapon_properties(&target, &source);
            if (target.weapon_properties.weapon_list != (copies ? inherited : NULL) ||
                target.weapon_properties.weapon_count != (copies ? 2 : 0) ||
                target.weapon_properties.weapon_index != (copies ? 3 : 0))
            {
                abort();
            }

            target.weapon_properties.weapon_list = own;
            target.weapon_properties.weapon_count = 1;
            inherit_weapon_properties(&target, &source);
            if (target.weapon_properties.weapon_list != own || target.weapon_properties.weapon_count != 1)
            {
                abort();
            }
        }
    }
    return 0;
}
'''
        self.assertEqual(native_output(code.replace('@WEAPON_COPY@', rule), data, engine_source=engine), '')

    def test_original_collision_box_none_arguments(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        _, cases = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        code = r'''
#include <stdint.h>
#include <strings.h>
#include "openbor.h"
#include "commands.h"
#undef assert
#undef printf
#undef stricmp
#include <assert.h>
#define stricmp strcasecmp

uint32_t obor_profile_build;
static s_body body;
static s_attack attack;
static s_hitbox body_box, attack_box;

s_body *collision_body_upsert_property(s_collision_body **head, int index)
{
    (void)head;
    assert(index == 1);
    return &body;
}

s_hitbox *collision_body_upsert_coordinates_property(s_collision_body **head, int index)
{
    (void)head;
    assert(index == 1);
    return &body_box;
}

s_attack *collision_attack_upsert_property(s_collision_attack **head, int index)
{
    (void)head;
    assert(index == 1);
    return &attack;
}

s_hitbox *collision_attack_upsert_coordinates_property(s_collision_attack **head, int index)
{
    (void)head;
    assert(index == 1);
    return &attack_box;
}

@NUMBER_METHODS@

static void load_box(modelCommands cmd, ArgList arglist)
{
    char filename[] = "model.txt";
    char *command = GET_ARG(0);
    char *value;
    int tempInt;
    int temp_collision_index = 1;
    s_collision_body *temp_collision_body_head = NULL;
    s_collision_attack *temp_collision_head = NULL;
    switch (cmd)
    {
        case CMD_MODEL_BBOX:
@BBOX@
        case CMD_MODEL_COLLISION:
@ATTACK@
        default:
            abort();
    }
}

static void check_rectangle(const s_hitbox *box, int early)
{
    assert(box->x == 0);
    assert(box->y == (early ? 3 : 0));
    assert(box->width == (early ? 5 : 0));
    assert(box->height == (early ? 7 : 0));
}

int main(void)
{
    const unsigned builds[] = {7369, 7391, 7420, 7525, 7526, 7533};
    const ArgList bbox = {.count = 7, .args = {"bbox", "NoNe", "3", "5", "7", "9", "11"}};
    const ArgList symmetric = {.count = 6, .args = {"bbox", "2", "3", "5", "7", "9"}};
    const ArgList strike = {.count = 11, .args = {"attack", "NoNe", "3", "5", "7", "13", "4", "1", "1", "8", "9"}};
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        const int early = builds[i] < 7526u;
        body_box = (s_hitbox){.z_background = 17, .z_foreground = 19};
        load_box(CMD_MODEL_BBOX, bbox);
        check_rectangle(&body_box, early);
        assert(body_box.z_background == (early ? 9 : 17));
        assert(body_box.z_foreground == (early ? 11 : 19));

        load_box(CMD_MODEL_BBOX, symmetric);
        assert(body_box.x == 2 && body_box.z_background == 9);
        assert(body_box.z_foreground == (builds[i] < 7420u ? 0 : 9));

        attack_box = (s_hitbox){.z_background = 17, .z_foreground = 19};
        attack = (s_attack){.attack_force = 23, .attack_type = ATK_BURN};
        load_box(CMD_MODEL_COLLISION, strike);
        check_rectangle(&attack_box, early);
        assert(attack_box.z_background == (early ? 9 : 17));
        assert(attack_box.z_foreground == (early ? 9 : 19));
        assert(attack.attack_force == (early ? 13 : 23));
        assert(attack.attack_type == (early ? ATK_NORMAL : ATK_BURN));
    }
    return 0;
}
'''
        methods = ('isNumeric', 'getValidInt', 'getValidFloat')
        code = (code.replace('@NUMBER_METHODS@', '\n'.join(function(source, name) for name in methods))
                .replace('@BBOX@', cases['CMD_MODEL_BBOX']['body'])
                .replace('@ATTACK@', cases['CMD_MODEL_COLLISION_ETC']['body']))
        output = native_output(code, {'engine': '7533'}, engine_source=engine)
        warnings = ''.join(f'WARNING: model.txt tries to load a non-numeric value at {command}, '
                           'where a number is expected!\nerroneus string: NoNe\n' for command in ('bbox', 'attack'))
        self.assertEqual(output, warnings * 4)

    def test_original_animation_range_and_jump_defaults(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        _, cases = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        animation = cases['CMD_MODEL_ANIM']['body']
        ranges = re.search(r'(?ms)^\s*const int range_default_grabdistance = .*?^\s*};', animation)[0]
        jump = re.search(r'(?ms)^\s*newanim->jumpframe = \(s_onframe_move\)\{.*?^\s*};', animation)[0]
        shadow = re.search(r'\bframeshadow\s*=\s*FRAME_SHADOW_NONE;', animation)[0]
        velocity = re.search(r'(?ms)^s_axis_principal_float default_model_dropv\s*=\s*\{.*?^};', source)[0]
        code = r'''
#include "openbor.h"
#undef assert
#include <assert.h>

@VELOCITY@

static int set_defaults(const s_model *newchar, s_anim *newanim)
{
    int frameshadow;
@RANGES@
@JUMP@
@SHADOW@
    return frameshadow;
}

int main(void)
{
    static s_model model;
    static s_anim animation;
    model.grabdistance = 11.75f;
    model.jumpheight = 4.75f;
    assert(set_defaults(&model, &animation) == -1);
    assert(animation.range.x.min == -10 && animation.range.x.max == 80);
    assert(animation.range.y.min == -40 && animation.range.y.max == 80);
    assert(animation.range.z.min == -3 && animation.range.z.max == 3);
    assert(animation.range.base.min == -40 && animation.range.base.max == 80);
    assert(animation.jumpframe.frame == FRAME_NONE && animation.jumpframe.model_index == MODEL_INDEX_NONE);
    assert(animation.jumpframe.velocity.x == default_model_dropv.x &&
           animation.jumpframe.velocity.y == default_model_dropv.y &&
           animation.jumpframe.velocity.z == default_model_dropv.z);

    model.grabdistance = -11.75f;
    model.jumpheight = -4.75f;
    animation.range.x.min = -27;
    assert(set_defaults(&model, &animation) == -1);
    assert(animation.range.x.min == -27 && animation.range.x.max == -80);
    assert(animation.range.y.min == 40 && animation.range.y.max == -80);
    assert(animation.range.z.min == 3 && animation.range.z.max == -3);
    assert(animation.range.base.min == 40 && animation.range.base.max == -80);
    return 0;
}
'''
        for key, value in {'VELOCITY': velocity, 'RANGES': ranges, 'JUMP': jump, 'SHADOW': shadow}.items():
            code = code.replace('@' + key + '@', value)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_model_release_progress(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        release = function(source, 'free_model')
        start = release.index('    if (hasFreetype(model, MF_CHILD_FOLLOW) && model->child_follow)')
        stop = release.index('    if(hasFreetype(model, MF_SCRIPTS))', start)
        code = r'''
#include <stdint.h>
#include "openbor.h"
#undef assert
#undef malloc
#undef printf
#include <assert.h>

uint32_t obor_profile_build;
static unsigned dots;

static void count_dot(const char *text)
{
    assert(strcmp(text, ".") == 0);
    ++dots;
}

@OWNERSHIP@

#define printf count_dot
static void release_follow(s_model *model)
{
@RELEASE@
}
#undef printf

int main(void)
{
    const unsigned builds[] = {7369, 7391, 7420, 7516, 7517, 7533};
    static s_model model;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        dots = 0;
        model.freetypes = MF_CHILD_FOLLOW;
        model.child_follow = malloc(sizeof(*model.child_follow));
        assert(model.child_follow);
        release_follow(&model);
        assert(!model.child_follow && dots == (builds[i] >= 7517u));
        release_follow(&model);
        assert(dots == (builds[i] >= 7517u ? 2u : 0u));
    }
    return 0;
}
'''
        code = code.replace('@OWNERSHIP@', function(source, 'hasFreetype')).replace('@RELEASE@', release[start:stop])
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_type_names_in_model_faction_lists(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        _, cases = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        directives = ('CMD_MODEL_HOSTILE', 'CMD_MODEL_CANDAMAGE', 'CMD_MODEL_PROJECTILEHIT')
        code = r'''
#include <stdarg.h>
#include <stdint.h>
#include <strings.h>
#include "openbor.h"
#undef assert
#include <assert.h>
#undef printf
#undef stricmp
#define stricmp strcasecmp

uint32_t obor_profile_build;
static char diagnostic[120];

static int capture_log(const char *format, ...)
{
    va_list args;
    va_start(args, format);
    int written = vsnprintf(diagnostic, sizeof(diagnostic), format, args);
    va_end(args);
    return written;
}

#define printf capture_log
@METHODS@
#undef printf

enum { CMD_MODEL_HOSTILE, CMD_MODEL_CANDAMAGE, CMD_MODEL_PROJECTILEHIT };

static void read_directive(int cmd, ArgList arglist, s_model *newchar)
{
    switch (cmd)
    {
@DIRECTIVES@
    }
}

int main(void)
{
    const unsigned builds[] = {7369, 7384, 7385, 7391, 7420, 7500, 7501, 7502, 7533};
    const struct {const char *name; e_entity_type type;} common[] = {
        {"enemy", TYPE_ENEMY}, {"item", TYPE_ITEM}, {"npc", TYPE_NPC}, {"obstacle", TYPE_OBSTACLE},
        {"player", TYPE_PLAYER}, {"projectile", TYPE_PROJECTILE}, {"shot", TYPE_SHOT}, {"trap", TYPE_TRAP}
    };
    static s_model model;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        const int legacy = builds[i] < 7501u;
        const e_entity_type end_level = legacy ? TYPE_ENEMY : TYPE_ENDLEVEL;
        const e_entity_type panel = legacy ? TYPE_PANEL : TYPE_UNKNOWN;
        const e_entity_type none = builds[i] < 7385u ? TYPE_UNDELCARED : TYPE_NONE;
        diagnostic[0] = 0;
        for (size_t j = 0; j < sizeof(common) / sizeof(*common); ++j)
        {
            assert(get_type_from_string(common[j].name) == common[j].type);
        }
        /* The two temporary 7501 table entries were corrected in 7502. */
        if (builds[i] != 7501u)
        {
            assert(get_type_from_string("steamer") == TYPE_STEAMER);
            assert(get_type_from_string("text_box") == TYPE_TEXTBOX);
        }
        assert(get_type_from_string("End_Level") == end_level);
        assert(get_type_from_string("NoNe") == none);
        assert(get_type_from_string("PLAYA") == (legacy ? TYPE_UNKNOWN : TYPE_PLAYER));
        assert(get_type_from_string("No_Copy") == (legacy ? TYPE_UNKNOWN : TYPE_NO_COPY));
        assert(!*diagnostic);
        assert(get_type_from_string("panel") == panel);
        assert(strcmp(diagnostic, legacy ? "" : "\n\n Unknown type (panel). \n") == 0);
        diagnostic[0] = 0;
        assert(get_type_from_string("missing") == TYPE_UNKNOWN);
        assert(strcmp(diagnostic, legacy ? "" : "\n\n Unknown type (missing). \n") == 0);

        ArgList args = {.count = 5, .args = {"hostile", "END_LEVEL", "projectile", "", "trap"}};
        read_directive(CMD_MODEL_HOSTILE, args, &model);
        assert(model.faction.type_hostile == (end_level | TYPE_PROJECTILE));
        args = (ArgList){.count = 4, .args = {"candamage", "panel", "NoNe", "panel"}};
        read_directive(CMD_MODEL_CANDAMAGE, args, &model);
        assert(model.faction.type_damage_direct == (panel | none));
        args = (ArgList){.count = 3, .args = {"projectilehit", "no_copy", "playa"}};
        read_directive(CMD_MODEL_PROJECTILEHIT, args, &model);
        assert(model.faction.type_damage_indirect == (legacy ? TYPE_UNKNOWN : (TYPE_NO_COPY | TYPE_PLAYER)));
        args.count = 1;
        read_directive(CMD_MODEL_PROJECTILEHIT, args, &model);
        assert(model.faction.type_damage_indirect == TYPE_UNDELCARED);
        assert(model.faction.type_hostile == (end_level | TYPE_PROJECTILE));
        assert(model.faction.type_damage_direct == (panel | none));
    }
    return 0;
}
'''
        methods = ('get_type_from_string', 'get_type_from_arglist')
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in methods))
        code = code.replace('@DIRECTIVES@', '\n'.join(f'case {name}:\n{cases[name]["body"]}' for name in directives))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_air_control_directives_and_diagnostics(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        _, cases = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        self.assertIn('lcmHandleCommandAirControl(&arglist, newchar);', cases['CMD_MODEL_AIR_CONTROL']['body'])
        code = r'''
#include <stdarg.h>
#include <stdint.h>
#include <strings.h>
#include "openbor.h"
#undef printf
#undef stricmp
#define stricmp strcasecmp
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
static char diagnostic[120];

static int capture_log(const char *format, ...)
{
    va_list args;
    va_start(args, format);
    int written = vsnprintf(diagnostic, sizeof(diagnostic), format, args);
    va_end(args);
    return written;
}

#define printf capture_log
@METHODS@
#undef printf

int main(void)
{
    const unsigned builds[] = {7369, 7391, 7420, 7500, 7501, 7533};
    const struct {const char *name; e_air_control value;} options[] = {
        {"none", AIR_CONTROL_NONE}, {"jump_disable", AIR_CONTROL_JUMP_DISABLE},
        {"jump_turn", AIR_CONTROL_JUMP_TURN}, {"jump_x_adjust", AIR_CONTROL_JUMP_X_ADJUST},
        {"jump_x_move", AIR_CONTROL_JUMP_X_MOVE}, {"jump_x_stop", AIR_CONTROL_JUMP_X_STOP},
        {"jump_y_stop", AIR_CONTROL_JUMP_Y_STOP}, {"jump_z_adjust", AIR_CONTROL_JUMP_Z_ADJUST},
        {"jump_z_initial", AIR_CONTROL_JUMP_Z_INITIAL}, {"jump_z_move", AIR_CONTROL_JUMP_Z_MOVE},
        {"jump_z_stop", AIR_CONTROL_JUMP_Z_STOP}, {"walkoff_turn", AIR_CONTROL_WALKOFF_TURN},
        {"walkoff_x_adjust", AIR_CONTROL_WALKOFF_X_ADJUST}, {"walkoff_x_move", AIR_CONTROL_WALKOFF_X_MOVE},
        {"walkoff_x_stop", AIR_CONTROL_WALKOFF_X_STOP}, {"walkoff_z_adjust", AIR_CONTROL_WALKOFF_Z_ADJUST},
        {"walkoff_z_move", AIR_CONTROL_WALKOFF_Z_MOVE}, {"walkoff_z_stop", AIR_CONTROL_WALKOFF_Z_STOP}
    };
    static s_model model;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        const int legacy = builds[i] < 7501u;
        const char *none_warning = legacy ? "\n\n Unknown air move flag (none), using 'none'. \n" : "";
        for (size_t j = 0; j < sizeof(options) / sizeof(*options); ++j)
        {
            diagnostic[0] = 0;
            assert(find_air_control_from_string(options[j].name) == options[j].value);
            assert(strcmp(diagnostic, j == 0 ? none_warning : "") == 0);
        }

        ArgList args = {.count = 4, .args = {"aircontrol", "WaLkOfF_tUrN", "jump_z_initial", "none"}};
        lcmHandleCommandAirControl(&args, &model);
        assert(model.air_control == (AIR_CONTROL_WALKOFF_TURN | AIR_CONTROL_JUMP_Z_INITIAL));
        assert(strcmp(diagnostic, none_warning) == 0);
        diagnostic[0] = 0;
        args.args[2] = "";
        args.args[3] = "jump_disable";
        lcmHandleCommandAirControl(&args, &model);
        assert(model.air_control == AIR_CONTROL_WALKOFF_TURN);
        args.count = 1;
        lcmHandleCommandAirControl(&args, &model);
        assert(model.air_control == AIR_CONTROL_NONE && !*diagnostic);

        assert(find_air_control_from_string("missing") == AIR_CONTROL_NONE);
        assert(strcmp(diagnostic, legacy ? "\n\n Unknown air move flag (missing), using 'none'. \n"
                                        : "\n\n  Unknown air control flag (missing). \n") == 0);
    }
    return 0;
}
'''
        methods = ('find_air_control_from_string', 'lcmHandleCommandAirControl')
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in methods))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_model_initialization_defaults(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        methods = ('obor_profile_default_defense', 'defense_allocate_object', 'offense_allocate_object',
                   'obor_unspecified_type_mask', 'obor_init_model_faction', 'obor_entity_deadline_value', 'init_model',
                   'defense_free_object', 'offense_free_object')
        entity_init = function(source, 'alloc_ent')
        entity_tables = entity_init[entity_init.index('    ent->object_type = OBJECT_TYPE_ENTITY;'):
                                    entity_init.index('    ent->varlist = ')]
        constants = ('const s_defense default_defense', 'static const s_defense legacy_default_defense',
                     'const s_offense default_offense')
        code = r'''
#include <limits.h>
#include <stdint.h>
#include "openbor.h"
#undef assert
#undef calloc
#include <assert.h>
#define E_OUT_OF_MEMORY "model constructor allocation"

uint32_t obor_profile_build;
static s_modelcache cache = {.name = "test-model", .path = "data/test-model.txt"};
s_modelcache *model_cache = &cache;
int magic_type, max_animations = MAX_ANIS, max_attack_types = MAX_ATKS;
float default_model_jumpspeed = -1, default_model_jumpheight = 4, default_model_grabdistance = 36;
float noatk_duration = 0.75f;

void borShutdown(int status, char *msg, ...)
{
    abort();
}

int get_cached_model_index(char *name)
{
    return strcmp(name, "flash") == 0 ? 3 : MODEL_INDEX_NONE;
}

static void alloc_all_scripts(void *scripts)
{
    (void)scripts;
}

@CONSTANTS@
@METHODS@

static void init_entity_combat_tables(entity *ent)
{
    @ENTITY_TABLES@
}

int main(void)
{
    const unsigned builds[] = {7369, 7391, 7420, 7434, 7435, 7441, 7442, 7443, 7444, 7494, 7495, 7503, 7504, 7533};
    static entity actor;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        magic_type = i % 2;
        s_model *model = init_model(0, 1);
        assert(model->name == cache.name && model->path == cache.path && model->unload == 1);
        assert(model->object_type == OBJECT_TYPE_MODEL && model->index == 0);
        assert(model->test_pointer == cache.name && !strcmp(model->test_fixed, cache.name));
        assert(model->risetime.rise == (builds[i] < 7504u ? UINT32_MAX : ULONG_MAX));
        assert(model->priority == 1 && model->remove == 1);
        assert(model->throwframewait == -1 && model->throwdamage == 21);
        assert(model->icon.def == -1 && model->icon.die == -1 && model->icon.get == -1);
        assert(model->icon.weapon == -1 && model->icon.pain == -1 && model->icon.mphigh == -1);
        assert(model->icon.mplow == -1 && model->icon.mpmed == -1);
        assert(model->icon.mpmax == ICON_NONE && model->icon.mpnone == ICON_NONE);
        assert(model->shadow_config_flags == SHADOW_CONFIG_DEFAULT);
        assert(model->weapon_properties.loss_count == 3 && model->weapon_properties.loss_index == MODEL_INDEX_NONE);
        assert(model->weapon_properties.loss_condition == WEAPON_LOSS_CONDITION_DEFAULT);
        assert(model->mprate == (magic_type == 1 ? 1 : 2) && model->guardrate == 2);
        assert(model->jugglepoints.current == 0 && model->jugglepoints.max == 0 && model->jugglepoints.min == 0);
        assert(model->guardpoints.current == 0 && model->guardpoints.max == 0 && model->guardpoints.min == 0);
        assert(model->profile_guardpoints == 0 && model->profile_jugglepoints == 0);
        assert(model->dust.fall_land == MODEL_INDEX_NONE && model->dust.jump_land == MODEL_INDEX_NONE);
        assert(model->dust.jump_start == MODEL_INDEX_NONE);
        assert(model->flash.model_hit == 3 && model->flash.model_block == 3);
        assert(model->offense[0].factor == 1.0f && model->offense[max_attack_types - 1].factor == 1.0f);
        assert(model->defense[0].factor == 1.0f && model->defense[0].knockdown == 1.0f);
        assert(model->defense[0].blocktype == (builds[i] < 7442 ? BLOCK_TYPE_MP_FIRST : BLOCK_TYPE_GLOBAL));
        e_entity_type unspecified = builds[i] < 7444 ? (e_entity_type)-1 : TYPE_UNDELCARED;
        assert(model->faction.type_damage_direct == unspecified);
        assert(model->faction.type_damage_indirect == unspecified && model->faction.type_hostile == unspecified);
        assert(model->edelay.factor == (builds[i] < 7495 ? 0.0f : 1.0f));
        assert(model->edelay.range.max == (builds[i] < 7495 ? 0 : MAX_INT));
        init_entity_combat_tables(&actor);
        assert(actor.object_type == OBJECT_TYPE_ENTITY);
        assert(actor.offense == actor.obor_offense_owned && actor.defense == actor.obor_defense_owned);
        const float initial_factor = builds[i] < 7435u ? 0.0f : 1.0f;
        for (int slot = 0; slot < max_attack_types; ++slot)
        {
            assert(actor.offense[slot].factor == initial_factor);
            assert(actor.defense[slot].factor == initial_factor && actor.defense[slot].knockdown == initial_factor);
        }
        offense_free_object(actor.obor_offense_owned);
        defense_free_object(actor.obor_defense_owned);
        free(model->animation);
        free(model->special);
        free(model->defense);
        free(model->offense);
        free(model);
    }
    return 0;
}
'''
        declarations = [re.search(r'^' + name + r'\s*=\s*\{[^}]+\};', source, re.MULTILINE)[0]
                        for name in constants]
        code = code.replace('@CONSTANTS@', '\n'.join(declarations))
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in methods))
        code = code.replace('@ENTITY_TABLES@', entity_tables)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_attack_target_selection(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        attack = function(source, 'do_attack')
        snapshot_start = attack.index('const int indirect =')
        snapshot = attack[snapshot_start:attack.index('// Every attack', snapshot_start)]
        death = braced_statement(attack, 'if(target->death_state & DEATH_STATE_DEAD)')
        gate_start = attack.index('const int can_damage =')
        gate = attack[gate_start:attack.index('if (!can_damage)', gate_start)]
        gate += braced_statement(attack, 'if (!can_damage)')
        code = r'''
#include <stdint.h>
#include <string.h>
#include "openbor.h"
#undef assert
#undef printf
#include <assert.h>

uint32_t obor_profile_build;
s_savedata savedata;
s_level *level;
static unsigned hostile_diagnostics;

static void record_faction_diagnostic(const char *format, ...)
{
    assert(strcmp(format, "\n\t\t acting_type & target_type: %d (no)") == 0);
    ++hostile_diagnostics;
}

#define printf record_faction_diagnostic
@FACTIONS@
#undef printf

static int attack_targets(entity *attacking_entity, entity *const *targets,
                          int count, int change_damage_types)
{
    int hits = 0;
    @SNAPSHOT@
    for (int i = 0; i < count; ++i)
    {
        entity *target = targets[i];
        @DEATH@
        @GATE@
        hits |= 1 << i;
        if (change_damage_types)
        {
            attacking_entity->faction.type_damage_direct = TYPE_ITEM;
            attacking_entity->faction.type_damage_indirect = TYPE_ITEM;
        }
    }
    return hits;
}

int main(void)
{
    static entity actor, first, second, third;
    static s_level current_level;
    entity *targets[] = {&first, &second, &third};
    const unsigned builds[] = {7369, 7391, 7420, 7443, 7444, 7445, 7446, 7447, 7533};
    actor.faction.damage_direct = FACTION_GROUP_TYPE_EXCLUSIVE;
    actor.faction.damage_indirect = FACTION_GROUP_TYPE_EXCLUSIVE;
    level = &current_level;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        const int legacy = builds[i] < 7444;
        actor.modeldata.type = TYPE_PLAYER;
        actor.projectile = BLAST_NONE;
        actor.faction.type_damage_direct = TYPE_ENEMY;
        actor.faction.type_damage_indirect = TYPE_NPC;
        first.modeldata.type = second.modeldata.type = TYPE_ENEMY;
        third.modeldata.type = TYPE_ITEM;
        assert(attack_targets(&actor, targets, 3, 1) == (legacy ? 3 : 5));

        actor.projectile = BLAST_ATTACK;
        actor.faction.type_damage_direct = TYPE_ENEMY;
        actor.faction.type_damage_indirect = TYPE_NPC;
        first.modeldata.type = second.modeldata.type = TYPE_NPC;
        assert(attack_targets(&actor, targets, 3, 1) == (legacy ? 3 : 5));

        actor.projectile = BLAST_NONE;
        actor.faction.type_damage_direct = TYPE_PLAYER;
        first.modeldata.type = TYPE_PLAYER;
        savedata.mode = 1;
        assert(attack_targets(&actor, targets, 1, 0) == (builds[i] < 7445u));
        savedata.mode = 0;
        current_level.nohit = DAMAGE_FROM_PLAYER_OFF;
        assert(attack_targets(&actor, targets, 1, 0) == (builds[i] < 7445u));
        actor.faction.damage_direct |= FACTION_GROUP_PLAYER_VERSES;
        savedata.mode = 1;
        assert(attack_targets(&actor, targets, 1, 0) == 1);
        actor.faction.type_damage_direct = TYPE_ENEMY;
        assert(attack_targets(&actor, targets, 1, 0) == 0);
        actor.faction.type_damage_direct = TYPE_PLAYER;
        actor.faction.damage_direct &= ~FACTION_GROUP_PLAYER_VERSES;
        savedata.mode = 0;
        current_level.nohit = DAMAGE_FROM_PLAYER_ON;
        assert(attack_targets(&actor, targets, 1, 0) == 1);
        obor_entity_dead_script_set(&first, 1);
        assert(attack_targets(&actor, targets, 1, 0) == 0);
        obor_entity_dead_script_set(&first, 0);
        assert(attack_targets(&actor, targets, 1, 0) == 1);
        if (!legacy)
        {
            actor.faction.hostile = FACTION_GROUP_TYPE_EXCLUSIVE;
            actor.faction.type_hostile = TYPE_PLAYER;
            savedata.mode = 1;
            assert(faction_check_is_hostile(&actor, &first) == (builds[i] < 7445u));
            savedata.mode = 0;
            actor.faction.type_hostile = TYPE_ENEMY;
            hostile_diagnostics = 0;
            assert(!faction_check_is_hostile(&actor, &first));
            assert(hostile_diagnostics == (builds[i] >= 7447u));
        }
    }
    return 0;
}
'''
        methods = ('faction_check_player_verses', 'faction_check_can_damage', 'faction_check_is_hostile')
        code = code.replace('@FACTIONS@', '\n'.join(function(source, name) for name in methods))
        code = code.replace('@SNAPSHOT@', snapshot).replace('@DEATH@', death).replace('@GATE@', gate)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_recurring_damage_timing(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        core = (engine / 'openbor.c').read_text()
        script = (engine / 'source/openborscript/recursive_damage.c').read_text()
        setter = function(script, 'openbor_set_recursive_damage_property')
        model = function(core, 'load_cached_model')
        model_durations = re.findall(r'collision_attack_upsert_recursive_property\([^\n]+\)->time\s*=\s*([^;]+);', model)
        self.assertEqual(len(model_durations), 2)
        parts = {
            'ENTITY_CLOCK': function(core, 'obor_entity_deadline_value'),
            'EXPIRE': re.search(r'cursor->time = [^;]+;', function(core, 'recursive_damage_check_apply'))[0],
            'TICK': re.search(r'cursor->tick = [^;]+;', function(core, 'recursive_damage_update'))[0],
            'SCRIPT_TIME': '\n'.join(re.search(r'handle->' + field + r' = [^;]+;', setter)[0]
                                     for field in ('tick', 'time')),
            'MODEL_DURATION': '\n'.join(f'parsed[{i}] = {value};' for i, value in enumerate(model_durations)),
        }
        code = r'''
#include <limits.h>
#include <stdint.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
u32 _time;

@ENTITY_CLOCK@

static void start_recurring_damage(s_damage_recursive *cursor, const s_attack *attack)
{
    @EXPIRE@
}

static void schedule_next_tick(s_damage_recursive *cursor)
{
    @TICK@
}

static void set_script_timers(s_damage_recursive *handle, LONG temp_int)
{
    @SCRIPT_TIME@
}

static void read_model_durations(unsigned long parsed[2], int value)
{
    #undef GET_INT_ARG
    #define GET_INT_ARG(index) value
    @MODEL_DURATION@
    #undef GET_INT_ARG
}

int main(void)
{
    static const unsigned builds[] = {7369, 7391, 7420, 7503, 7504, 7509, 7533};
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        const int earlier = builds[i] < 7504u;
        s_damage_recursive authored = {.time = 25};
        s_damage_recursive active = {.rate = 10};
        const s_attack strike = {.recursive = &authored};
        _time = 500;
        start_recurring_damage(&active, &strike);
        schedule_next_tick(&active);
        assert(active.time == 550 && active.tick == 520);

        authored.time = 1u << 25;
        const uint64_t scaled = (uint64_t)authored.time * GAME_SPEED;
        start_recurring_damage(&active, &strike);
        assert(active.time == 500 + ((earlier || ULONG_MAX == UINT32_MAX ? scaled & UINT32_MAX : scaled) / 100));
        active.rate = (unsigned int)-25;
        schedule_next_tick(&active);
        assert(active.tick == (earlier ? 450u : 500u + (UINT32_MAX - 4999u) / 100));

        set_script_timers(&active, -1);
        unsigned long parsed[2];
        read_model_durations(parsed, -1);
        const unsigned long clock_max = earlier ? UINT32_MAX : ULONG_MAX;
        assert(active.tick == clock_max && active.time == clock_max);
        assert(parsed[0] == clock_max && parsed[1] == clock_max);
    }
    return 0;
}
'''
        for key, value in parts.items():
            code = code.replace('@' + key + '@', value)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_rush_counter_and_clock(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        attack = function(source, 'do_attack')
        self.assertIn('obor_record_rush_hit(&topowner->rush);', attack)
        hud = function(source, 'predrawstatus')
        huds = ('if(rush[0] && obor_has_rush_combo(', 'if(rush[0] == 2)')
        scripts = (engine / 'openborscript.c').read_text()
        _, setters = switch_cases(scripts, 'openbor_changeentityproperty', 'propind', outermost=True)
        methods = ('obor_has_rush_combo', 'obor_record_rush_hit')
        level_loop = function(source, 'playlevel')
        reset_record = re.search(r'player\[i\]\.ent->rush\.max = 0;', level_loop)
        carry_record = re.search(r'nomaxrushreset\[i\] = player\[i\]\.ent->rush\.max;', level_loop)
        self.assertIsNotNone(reset_record, 'Expected a fresh rush record when spawning at level start')
        self.assertIsNotNone(carry_record, 'Expected the rush record to carry into level cleanup')
        code = r'''
#include <stdarg.h>
#include <stdint.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
u32 _time;
s_player player[MAX_PLAYERS];
s_videomodes videomodes;
int rush[6] = {1, 2};
int prush[MAX_PLAYERS][8];
int nomaxrushreset[MAX_PLAYERS + 1];
char rush_names[2][MAX_NAME_LEN];
static int rows, numbers[2];

void font_printf(int x, int y, int font, int layer, char *format, ...)
{
    if (!strcmp(format, "%i"))
    {
        assert(rows < 2);
        va_list args;
        va_start(args, format);
        numbers[rows++] = va_arg(args, int);
        va_end(args);
    }
}

HRESULT ScriptVariant_IntegerValue(ScriptVariant *value, LONG *result)
{
    *result = value->lVal;
    return S_OK;
}

@METHODS@

static void draw_rush(void)
{
    const int i = 0;
    rows = 0;
    @HUD@
}

static void set_rush_time(entity *ent, LONG input)
{
    LONG ltemp;
    ScriptVariant value = {.vt = VT_INTEGER, .lVal = input};
    ScriptVariant *varlist[] = {NULL, NULL, &value};
    do {
        @SET_TIME@
    } while (0);
}

static void check_level_rush_record(void)
{
    const int i = 0;
    player[i].ent->rush.max = (uint32_t)-5;
    @CARRY_RECORD@
    assert(nomaxrushreset[i] == -5);
    @RESET_RECORD@
    assert(player[i].ent->rush.max == 0);
}

int main(void)
{
    static entity actor;
    player[0].ent = &actor;
    static const uint32_t builds[] = {7369, 7391, 7420, 7509, 7510, 7511, 7533};
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        const int signed_record = builds[i] < 7511;
        check_level_rush_record();
        _time = 40;
        actor.rush.count = (uint32_t)-3;
        actor.rush.max = 7;
        obor_record_rush_hit(&actor.rush);
        assert(actor.rush.count == (uint32_t)-2);
        assert(actor.rush.max == (signed_record ? 7u : (uint32_t)-2));
        assert(actor.rush.time == 40 + 2 * GAME_SPEED);
        draw_rush();
        assert(rows == (signed_record ? 0 : 2));
        if (!signed_record)
        {
            assert(numbers[0] == -2 && numbers[1] == -2);
        }

        actor.rush.count = 1;
        actor.rush.max = (uint32_t)-5;
        obor_record_rush_hit(&actor.rush);
        draw_rush();
        assert(rows == 2 && numbers[0] == 2 && numbers[1] == (signed_record ? 2 : -5));
        _time = (u32)actor.rush.time + 1;
        draw_rush();
        assert(rows == 0);

        set_rush_time(&actor, -1);
        assert(actor.rush.time == (builds[i] < 7510 ? (unsigned long)UINT32_MAX : ULONG_MAX));
    }
    return 0;
}
'''
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in methods))
        code = code.replace('@HUD@', '\n'.join(braced_statement(hud, anchor) for anchor in huds))
        code = code.replace('@SET_TIME@', setters['_ep_rush_time']['body'])
        code = code.replace('@CARRY_RECORD@', carry_record[0]).replace('@RESET_RECORD@', reset_record[0])
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_model_ai_argument_positions_and_repeated_directives(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        _, commands = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        methods = ('obor_add_model_aimove', 'lcmHandleCommandType',
                   'obor_find_aimove_constant', 'get_aimove_constant_from_string',
                   'obor_read_legacy_aimove', 'get_aimove_from_arguments', 'lcmHandleCommandAiattack')
        code = r'''
#include <stdarg.h>
#include <stdint.h>
#include <strings.h>
#include "openbor.h"
#undef printf
#undef stricmp
#define stricmp strcasecmp
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
s_videomodes videomodes;
static char diagnostic[160];

void borShutdown(int status, char *format, ...)
{
    assert(status == 1 && !*diagnostic);
    va_list args;
    va_start(args, format);
    vsnprintf(diagnostic, sizeof(diagnostic), format, args);
    va_end(args);
}

@METHODS@

static void move_directive(s_model *newchar, int *loaded, char *main, char *sub, char *extra)
{
    char *filename = "model.txt";
    int aimoveset = *loaded;
    ArgList arglist = {.count = 4, .args = {"aimove", main, sub, extra}};
    do {
        @AIMOVE@
    } while (0);
    *loaded = aimoveset;
}

static void attack_directive(s_model *newchar, int *loaded, char *value)
{
    char *filename = "model.txt";
    int aiattackset = *loaded;
    ArgList arglist = {.count = 2, .args = {"aiattack", value}};
    do {
        @AIATTACK@
    } while (0);
    *loaded = aiattackset;
}

int main(void)
{
    static const uint32_t builds[] = {7369, 7381, 7382, 7383, 7391, 7420, 7533};
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        const int positional = builds[i] < 7383;
        const e_aimove normal = builds[i] < 7382 ? 0 : AIMOVE1_NORMAL;
        s_model model = {.aimove = AIMOVE1_BIKER, .aiattack = -1};
        int loaded = 0;
        move_directive(&model, &loaded, "wander", "ignoreholes", "bomb");
        assert(model.aimove == (normal | AIMOVE1_WANDER | AIMOVE2_IGNOREHOLES |
            (positional ? 0 : AIMOVE1_BOMB)));
        move_directive(&model, &loaded, "ArRoW", "notargetidle", "star");
        assert(model.aimove == (normal | AIMOVE1_ARROW | AIMOVE2_NOTARGETIDLE |
            (positional ? AIMOVE1_WANDER | AIMOVE2_IGNOREHOLES : AIMOVE1_STAR)));
        assert(model.offscreenkill == (positional ? 200 : 0));
        model.offscreenkill = 52;
        move_directive(&model, &loaded, "arrow", "", "");
        assert(model.offscreenkill == 52);

        diagnostic[0] = 0;
        move_directive(&model, &loaded, "ignoreholes", "chase", "");
        if (positional)
        {
            assert(!strcmp(diagnostic, "Model 'model.txt' has invalid A.I. move switch: 'ignoreholes'"));
            diagnostic[0] = 0;
            move_directive(&model, &loaded, "chase", "arrow", "");
            assert(!strcmp(diagnostic, "Model 'model.txt' has invalid A.I. move switch: 'arrow'"));
        }
        else
        {
            assert(model.aimove == (AIMOVE1_NORMAL | AIMOVE2_IGNOREHOLES | AIMOVE1_CHASE));
            assert(!*diagnostic);
        }

        loaded = 0;
        move_directive(&model, &loaded, "", "", "");
        assert(model.aimove == normal);
        loaded = 0;
        attack_directive(&model, &loaded, "always");
        attack_directive(&model, &loaded, "noattack");
        assert(model.aiattack == (AIATTACK1_ALWAYS | AIATTACK1_NOATTACK));

        ArgList obstacle = {.count = 2, .args = {"type", "obstacle"}};
        model.aimove = obor_unspecified_aimove();
        lcmHandleCommandType(&obstacle, &model, "model.txt");
        assert(model.aimove == (builds[i] < 7382 ? AIMOVE1_NOMOVE | AIMOVE1_CHASEX :
            AIMOVE1_NORMAL | AIMOVE1_NOMOVE | AIMOVE1_CHASEZ));
        assert(model.aiattack == (AIATTACK1_ALWAYS | AIATTACK1_NOATTACK));
    }
    puts("PASS");
}
'''
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in methods))
        for name in ('AIMOVE', 'AIATTACK'):
            code = code.replace('@' + name + '@', commands['CMD_MODEL_' + name]['body'])
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), 'PASS\n')

    def test_model_copy_flags_follow_original_argument_readers(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        _, commands = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        methods = ('isNumeric', 'getValidInt', 'get_weapon_loss_from_argument',
                   'get_model_flag_from_legacy_int', 'get_model_flag_from_argument',
                   'lcmHandleCommandModelFlag')
        code = r'''
#include <stdint.h>
#include <strings.h>
#include "openbor.h"
#undef printf
#undef stricmp
#define stricmp strcasecmp
#undef assert
#include <assert.h>

uint32_t obor_profile_build;

@METHODS@

static e_model_copy read_copy_flags(char *first, char *second)
{
    s_model model = {.model_flag = MODEL_COPY_FLAG_NO_BASIC};
    s_model *newchar = &model;
    char *filename = "model.txt";
    char *command = "modelflag";
    ArgList arglist = {.count = second ? 3 : 2, .args = {command, first, second}};
    do {
        @MODELFLAG@
    } while (0);
    return model.model_flag;
}

int main(void)
{
    const e_model_copy all = MODEL_COPY_FLAG_NO_BASIC | MODEL_COPY_FLAG_NO_WEAPON | MODEL_COPY_FLAG_NO_SCRIPT;
    const e_model_copy original_default = (e_model_copy)WEAPON_LOSS_CONDITION_DEFAULT;
    const struct {uint32_t build; e_model_copy numeric, weapon_names, model_names;} cases[] = {
        {7369, MODEL_COPY_FLAG_NO_SCRIPT, 0, 0},
        {7374, MODEL_COPY_FLAG_NO_SCRIPT, 0, 0},
        {7375, original_default, MODEL_COPY_FLAG_NO_WEAPON | MODEL_COPY_FLAG_NO_SCRIPT, original_default},
        {7391, original_default, MODEL_COPY_FLAG_NO_WEAPON | MODEL_COPY_FLAG_NO_SCRIPT, original_default},
        {7420, original_default, MODEL_COPY_FLAG_NO_WEAPON | MODEL_COPY_FLAG_NO_SCRIPT, original_default},
        {7431, original_default, MODEL_COPY_FLAG_NO_WEAPON | MODEL_COPY_FLAG_NO_SCRIPT, original_default},
        {7432, all, MODEL_COPY_FLAG_NO_BASIC, MODEL_COPY_FLAG_NO_BASIC | MODEL_COPY_FLAG_NO_SCRIPT},
        {7533, all, MODEL_COPY_FLAG_NO_BASIC, MODEL_COPY_FLAG_NO_BASIC | MODEL_COPY_FLAG_NO_SCRIPT},
    };
    for (size_t i = 0; i < sizeof(cases) / sizeof(*cases); ++i)
    {
        obor_profile_build = cases[i].build;
        assert(read_copy_flags("4", NULL) == cases[i].numeric);
        assert(read_copy_flags("death", "fall") == cases[i].weapon_names);
        assert(read_copy_flags("no_basic", "no_script") == cases[i].model_names);
    }
    puts("PASS");
}
'''
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in methods))
        code = code.replace('@MODELFLAG@', commands['CMD_MODEL_MODELFLAG']['body'])
        output = native_output(code, {'engine': '7533'}, engine_source=engine,
                               extra_cflags=('-Wno-error=implicit-fallthrough',))
        self.assertEqual(re.findall(r'erroneus string: (\w+)', output),
                         ['death', 'no_basic'] * 2 + ['death', 'fall'] * 2)
        self.assertEqual(re.findall(r'Unknown weapon loss flag \((\w+)\)', output),
                         ['4', 'no_basic', 'no_script'] * 4)
        self.assertTrue(output.endswith('PASS\n'))

    def test_original_defense_model_attack_selection_and_values(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        _, commands = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        self.assertIn('defense_setup_from_arg(filename, command, newchar->defense, &arglist, DEFENSE_PARAMETER_LEGACY);',
                      commands['CMD_MODEL_DEFENSE']['body'])
        methods = ('isNumeric', 'getValidInt', 'getValidFloat', 'is_attack_type_special',
                   'defense_apply_setup_to_property', 'defense_setup_from_arg')
        code = r'''
#include <stdint.h>
#include <strings.h>
#include "openbor.h"
#undef stricmp
#undef strnicmp
#define stricmp strcasecmp
#define strnicmp strncasecmp
#undef assert
#include <assert.h>

int max_attack_types = MAX_ATKS + 12;
void writeToLogFile(const char *format, ...) { abort(); }
e_death_config_flags death_get_config_flags_from_arguments(const ArgList *arguments, int start) { abort(); }

@METHODS@

int main(void)
{
    s_defense defense[MAX_ATKS + 12] = {0};
    ArgList legacy = {.count = 9, .args = {"defense", "normal", "1.75", "-1.5", "2.5",
                                          "3.25", "4.5", "0.25", "2"}};
    defense_setup_from_arg("model.txt", legacy.args[0], defense, &legacy, DEFENSE_PARAMETER_LEGACY);
    assert(defense[ATK_NORMAL].factor == 1.75f && defense[ATK_NORMAL].pain == -1);
    assert(defense[ATK_NORMAL].knockdown == 2.5f && defense[ATK_NORMAL].blockpower == 3);
    assert(defense[ATK_NORMAL].blockthreshold == 4 && defense[ATK_NORMAL].blockratio == 0.25f);
    assert(defense[ATK_NORMAL].blocktype == 2);

    ArgList factor = {.count = 3, .args = {"defense.factor", "normal11", "2.5"}};
    defense_setup_from_arg("model.txt", factor.args[0], defense, &factor, DEFENSE_PARAMETER_FACTOR);
    assert(defense[STA_ATKS + 10].factor == 2.5f);
    factor.args[1] = "boss_death";
    defense_setup_from_arg("model.txt", factor.args[0], defense, &factor, DEFENSE_PARAMETER_FACTOR);
    assert(defense[ATK_BOSS_DEATH].factor == 2.5f);
    factor.args[1] = "ALL";
    factor.args[2] = "0.75";
    defense_setup_from_arg("model.txt", factor.args[0], defense, &factor, DEFENSE_PARAMETER_FACTOR);
    assert(defense[ATK_NORMAL].factor == 0.75f && defense[ATK_NORMAL2].factor == 0.75f);
    assert(defense[STA_ATKS + 10].factor == 0.75f && defense[ATK_BOSS_DEATH].factor == 2.5f);
    puts("PASS");
}
'''
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in methods))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), 'PASS\n')

    def test_original_offense_factor_values(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        loader = function(source, 'load_cached_model')
        self.assertRegex(loader, r'case CMD_MODEL_OFFENSE:\s*offense_setup_from_arg\([^;]+OFFENSE_PARAMETER_LEGACY\);')
        methods = ('isNumeric', 'getValidInt', 'getValidFloat', 'is_attack_type_special',
                   'offense_apply_setup_to_property', 'offense_setup_from_arg')
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"
#undef assert
#define assert(value) do { if (!(value)) abort(); } while (0)
#undef printf
#undef stricmp
#undef strnicmp
#define stricmp strcasecmp
#define strnicmp strncasecmp

uint32_t obor_profile_build;
int max_attack_types = MAX_ATKS + 12;
void writeToLogFile(const char *format, ...) { (void)format; abort(); }
@METHODS@

static void load_factor(s_offense *offense, char *name, char *number, e_offense_parameters parameter)
{
    ArgList args = {.count = 3, .args = {"offense", name, number}};
    offense_setup_from_arg("model.txt", args.args[0], offense, &args, parameter);
}

static void check(float result, float expected, const char *name)
{
    if (result != expected)
    {
        fprintf(stderr, "%s for profile %u gave %.3f, expected %.3f\n",
                name, obor_profile_build, (double)result, (double)expected);
        abort();
    }
}

int main(void)
{
    static const uint32_t profiles[] = {7369, 7391, 7420, 7434, 7435, 7530, 7533};
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        const int earlier = obor_profile_build < 7435;
        s_offense offense[MAX_ATKS + 12] = {0};
        load_factor(offense, "normal", "1.75", OFFENSE_PARAMETER_LEGACY);
        check(offense[ATK_NORMAL].factor, earlier ? 1.75f : 1.f, "Fractional named factor");
        load_factor(offense, "normal2", "-0.5", OFFENSE_PARAMETER_LEGACY);
        check(offense[ATK_NORMAL2].factor, earlier ? -0.5f : 0.f, "Signed fractional factor");
        load_factor(offense, "normal11", "2.5", OFFENSE_PARAMETER_LEGACY);
        check(offense[STA_ATKS + 10].factor, earlier ? 2.5f : 2.f, "Additional attack type");
        load_factor(offense, "Boss_Death", "7", OFFENSE_PARAMETER_LEGACY);
        load_factor(offense, "ALL", "175%", OFFENSE_PARAMETER_LEGACY);
        check(offense[ATK_NORMAL].factor, earlier ? 1.75f : 175.f, "Percentage factor");
        check(offense[ATK_NORMAL2].factor, earlier ? 1.75f : 175.f, "All regular attack types");
        check(offense[STA_ATKS + 10].factor, earlier ? 1.75f : 175.f, "All includes additional attack types");
        check(offense[ATK_BOSS_DEATH].factor, 7.f, "All preserves special attack types");
        if (earlier)
        {
            load_factor(offense, "ALL", "invalid", OFFENSE_PARAMETER_LEGACY);
            check(offense[ATK_NORMAL].factor, 0.f, "Invalid factor");
            check(offense[ATK_BOSS_DEATH].factor, 7.f, "Invalid factor preserves special attack types");
        }
        if (!earlier)
        {
            load_factor(offense, "normal", "1.75", OFFENSE_PARAMETER_FACTOR);
            check(offense[ATK_NORMAL].factor, 1.f, "Explicit factor");
        }
    }
    return 0;
}
'''
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in methods))
        output = native_output(code, {'engine': '7533'}, engine_source=engine)
        warning = ('WARNING: model.txt tries to load a non-numeric value at offense, where a number is expected!\n'
                   'erroneus string: invalid')
        self.assertEqual(output.splitlines(), (warning.splitlines() * 4))

    def test_child_inherits_original_offense_entries(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        spawn = function(source, 'child_spawn_execute_object')
        condition = re.search(r'(?m)^ +(?P<if>if [^\n]+CHILD_SPAWN_CONFIG_OFFENSE_PARENT[^\n]*)$', spawn)
        self.assertIsNotNone(condition)
        branch = braced_statement(spawn, condition['if'])
        default = re.search(r'(?ms)^const s_offense default_offense\s*=\s*\{.*?^\};', source)[0]
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef calloc

uint32_t obor_profile_build;
int max_attack_types = 3;
@DEFAULT@
@ALLOCATE@

static void inherit_offense(s_child_spawn *object, entity *parent, entity *child_entity)
{
    @BRANCH@
}

int main(void)
{
    static const struct {
        uint32_t build;
        int count;
    } cases[] = {
        {7369, 0}, {7381, 0}, {7382, 1}, {7391, 1}, {7420, 1}, {7434, 1},
        {7435, 3}, {7533, 3},
    };
    s_offense parent_values[] = {
        {.factor = 1.75f, .damage_adjust = 6},
        {.factor = -0.5f, .damage_adjust = 7},
        {.factor = 3.5f, .damage_adjust = 8},
    };
    entity parent = {.offense = parent_values};
    s_child_spawn object = {0};
    for (size_t i = 0; i < sizeof(cases) / sizeof(*cases); ++i)
    {
        obor_profile_build = cases[i].build;
        s_offense child_values[] = {
            {.factor = 0.25f, .damage_adjust = -6},
            {.factor = 1.25f, .damage_adjust = -7},
            {.factor = 2.25f, .damage_adjust = -8},
        };
        entity child = {.offense = child_values};
        object.config = 0;
        inherit_offense(&object, &parent, &child);
        if (child_values[0].factor != 0.25f || child_values[2].damage_adjust != -8)
        {
            return 1;
        }
        object.config = CHILD_SPAWN_CONFIG_OFFENSE_PARENT;
        inherit_offense(&object, &parent, &child);
        for (int type = 0; type < max_attack_types; ++type)
        {
            float factor = type < cases[i].count ? parent_values[type].factor : 0.25f + type;
            int adjust = cases[i].count == max_attack_types ? parent_values[type].damage_adjust : -6 - type;
            if (child_values[type].factor != factor || child_values[type].damage_adjust != adjust)
            {
                fprintf(stderr, "Profile %u inherited the wrong properties for attack type %d\n",
                        obor_profile_build, type);
                return 2;
            }
        }
    }
    entity child = {.offense = offense_allocate_object()};
    memcpy(child.offense, parent_values, sizeof(parent_values));
    entity parent_without_offense = {0};
    inherit_offense(&object, &parent_without_offense, &child);
    for (int type = 0; type < max_attack_types; ++type)
    {
        if (child.offense[type].factor != 1.f || child.offense[type].damage_adjust != 0 ||
            child.offense[type].damage_min != MIN_INT || child.offense[type].damage_max != MAX_INT)
        {
            return 3;
        }
    }
    free(child.offense);
    return 0;
}
'''
        code = (code.replace('@DEFAULT@', default)
                    .replace('@ALLOCATE@', function(source, 'offense_allocate_object'))
                    .replace('@BRANCH@', branch))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_animation_executes_child_spawns_from_original_revision(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        update = function(source, 'update_frame')
        condition = re.search(r'(?m)^ +(?P<if>if [^\n]+anim->child_spawn\[f\][^\n]*)$', update)
        self.assertIsNotNone(condition)
        branch = braced_statement(update, condition['if'])
        code = r'''
#include <stdint.h>
#include "openbor.h"

uint32_t obor_profile_build;
static entity actor;
static s_child_spawn child;
static unsigned calls;

void child_spawn_execute_list(s_child_spawn *head, entity *parent)
{
    if (head != &child || parent != &actor)
    {
        abort();
    }
    ++calls;
}

static void advance(s_anim *anim, entity *ent, unsigned f)
{
    @BRANCH@
}

int main(void)
{
    static const uint32_t profiles[] = {7369, 7380, 7381, 7382, 7391, 7420, 7533};
    s_child_spawn *frames[] = {NULL, &child};
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        s_anim animation = {0};
        calls = 0;
        advance(&animation, &actor, 1);
        animation.child_spawn = frames;
        advance(&animation, &actor, 0);
        if (calls != 0)
        {
            return 1;
        }
        advance(&animation, &actor, 1);
        if (calls != (unsigned)(obor_profile_build >= 7382))
        {
            return 2;
        }
    }
    return 0;
}
'''
        self.assertEqual(native_output(code.replace('@BRANCH@', branch), {'engine': '7533'},
                                       engine_source=engine), '')

    def test_original_child_spawn_options_and_placement(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        spawn = function(source, 'child_spawn_execute_object')
        initialization = spawn[:spawn.index('    /*\n    * Populate relationship properties')]
        aimove = braced_statement(spawn, 'if (obor_profile_build < 7432u\n')
        colors = spawn[spawn.index('    const int legacy_color'):spawn.index('    /* Populate common behavior flags. */')]
        methods = (
            'child_spawn_get_config_bit_from_argument', 'child_spawn_allocate_object',
            'obor_find_aimove_constant', 'get_aimove_constant_from_string',
            'direction_get_adjustment_result', 'child_spawn_position_x',
        )
        code = Path(__file__).with_name('modern_legacy_child_options_contract.c.in').read_text()
        for symbol, fragment in (
            ('METHODS', '\n'.join(function(source, name) for name in methods)),
            ('SPAWN', initialization + '    return child_entity;\n}'),
            ('AIMOVE', aimove),
            ('COLORS', colors),
        ):
            code = code.replace('@' + symbol + '@', fragment)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_npc_recall_range_and_position(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        methods = ('diff', 'check_range_target_x', 'check_range_target_y', 'check_range_target_z',
                   'check_range_target_base', 'npc_recall', 'ai_check_recall')
        code = r'''
#include <stdint.h>
#include "openbor.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
entity *self;
static int picked_animation;

void common_spawn(void) {}

void ent_set_anim(entity *actor, int animation, int resetable)
{
    assert(actor == self && resetable == 0);
    picked_animation = animation;
}

@METHODS@

int main(void)
{
    const unsigned builds[] = {7369, 7391, 7420, 7515, 7516, 7529, 7530, 7533};
    static s_anim idle = {.numframes = 1, .range = {.x.max = 20, .z.max = 3}};
    static s_anim action = {.numframes = 1};
    static s_anim *animations[MAX_ANIS];
    static entity child, parent;
    s_child_follow follow = {
        .follow_offset = {.x = 7}, .recall_offset = {.x = 9, .y = 3, .z = -5},
        .recall_range = {.x = {.min = -20, .max = 20}, .z = {.min = -20, .max = 20},
                         .y = {.min = -2, .max = 2}, .base = {.min = -2, .max = 2}},
        .recall_animation = ANI_PAIN
    };
    parent.position = (s_axis_principal_float){.x = 60, .y = 12, .z = 80};
    parent.base = 10;
    parent.direction = DIRECTION_LEFT;
    self = &child;
    child.modeldata.animation = animations;
    child.modeldata.animation_capacity = MAX_ANIS;
    child.modeldata.subtype = SUBTYPE_FOLLOW;
    child.direction = DIRECTION_RIGHT;

    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        const int legacy = builds[i] < 7516u;
        child.modeldata.child_follow = legacy ? NULL : &follow;
        child.position = parent.position;
        child.position.z += 20;
        child.base = parent.base;
        child.parent = &parent;
        child.takeaction = NULL;
        animations[ANI_IDLE] = &idle;
        animations[ANI_SPAWN] = animations[ANI_RESPAWN] = animations[ANI_PAIN] = &action;
        assert(!ai_check_recall() && child.takeaction == NULL);

        child.position.z += 0.25f;
        assert(ai_check_recall() == legacy);
        child.takeaction = NULL;
        child.position.z += 1;
        child.link = &parent;
        assert(!ai_check_recall());
        child.link = NULL;
        child.parent = NULL;
        assert(!ai_check_recall());
        child.parent = &parent;
        if (legacy)
        {
            animations[ANI_IDLE] = NULL;
            assert(!ai_check_recall());
            animations[ANI_IDLE] = &idle;
        }
        assert(ai_check_recall() && child.takeaction == npc_recall);
        child.velocity = (s_axis_principal_float){.x = 1, .y = -2, .z = 3};
        picked_animation = ANI_NONE;
        child.takeaction();
        const float x = parent.position.x + (legacy ? 0 : builds[i] < 7530u ? 9 : -7);
        assert(child.position.x == x && child.position.y == parent.position.y + (legacy ? 0 : 3));
        assert(child.position.z == parent.position.z - (legacy ? 0 : 5));
        assert(child.base == parent.base && !child.velocity.x && !child.velocity.y && !child.velocity.z);
        assert(child.takeaction == common_spawn && picked_animation == (legacy ? ANI_RESPAWN : ANI_PAIN));

        animations[ANI_RESPAWN] = animations[ANI_PAIN] = NULL;
        npc_recall();
        assert(child.takeaction == common_spawn && picked_animation == ANI_SPAWN);
    }
    return 0;
}
'''
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in methods))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_player_spawn_type_timing(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        spawn = function(source, 'spawnplayer')
        setup = spawn[spawn.index('    memset(&p, 0, sizeof(p));'):spawn.index('    if(level->scrolldir')]
        finish = spawn[spawn.index('    currentspawnplayer = index;'):spawn.index('    memset(player[index].combokey')]
        smartspawn = function(source, 'smartspawn')
        copy_type = braced_statement(smartspawn, 'if(props->spawntype)')
        self.assertLess(smartspawn.index('if(props->spawntype)'), smartspawn.index('execute_onspawn_script(e);'))
        code = r'''
#include <stdint.h>
#include "openbor.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
s_player player[MAX_PLAYERS];
int currentspawnplayer, nomaxrushreset[5];
static entity actor;
static e_spawn_type observed;
static int callback_calls, change_spawn_type;

_Static_assert(sizeof(e_entity_type) == sizeof(int) && (e_entity_type)-1 < 0,
               "Spawn entry types preserve signed integer values");

void borShutdown(int status, char *message, ...)
{
    abort();
}

void execute_onspawn_script(entity *spawned)
{
    observed = spawned->spawntype;
    ++callback_calls;
    if (change_spawn_type)
    {
        spawned->spawntype = SPAWN_TYPE_NONE;
    }
}

entity *smartspawn(s_spawn_entry *props)
{
    entity *e = &actor;
    memset(e, 0, sizeof(*e));
    @COPY_TYPE@
    execute_onspawn_script(e);
    return e;
}

static void spawn_main_player(int index)
{
    s_spawn_entry p;
    @SETUP@
    @FINISH@
}

int main(void)
{
    const unsigned profiles[] = {7369, 7391, 7420, 7446, 7447, 7533};
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        const e_spawn_type main_player = obor_profile_spawn_type(SPAWN_TYPE_PLAYER_MAIN);
        const int legacy = profiles[i] < 7447u;
        nomaxrushreset[2] = 23;
        for (int scripted = 0; scripted < 2; ++scripted)
        {
            callback_calls = 0;
            change_spawn_type = scripted;
            nomaxrushreset[4] = scripted;
            spawn_main_player(2);
            assert(callback_calls == 1 && observed == (legacy ? SPAWN_TYPE_NONE : main_player));
            assert(actor.spawntype == (legacy || !scripted ? main_player : SPAWN_TYPE_NONE));
            assert(player[2].ent == &actor && actor.playerindex == 2 && currentspawnplayer == 2);
            assert(actor.rush.max == (scripted ? 23u : 0u));
        }
    }
    return 0;
}
'''
        code = code.replace('@SETUP@', setup).replace('@FINISH@', finish).replace('@COPY_TYPE@', copy_type)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_child_spawn_script_constants_and_types(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        script = (engine / 'openborscript.c').read_text()
        constants = (engine / 'source/openborscript/constants.c').read_text()
        source = (engine / 'openbor.c').read_text()
        fixture = FIXTURE.with_name('modern-child-spawn-script-values.json')
        snapshots = json.loads(fixture.read_text())
        profiles = {7369, 7388, 7391, 7420, 7533}
        profiles.update(build for snapshot in snapshots[1:] for build in (snapshot['build'] - 1, snapshot['build']))
        names = sorted({prefix + name for row in snapshots for key, prefix in
                        (('child_flags', 'CHILD_SPAWN_CONFIG_'), ('spawn_types', 'SPAWN_TYPE_'))
                        for name in row[key]})
        queries, types = [], []
        temporary = {'CHILD_BOMB', 'CHILD_NORMAL', 'CHILD_PROJECTILE'}
        for build in sorted(profiles):
            row = next(row for row in reversed(snapshots) if row['build'] <= build)
            expected = {'CHILD_SPAWN_CONFIG_' + name: value for name, value in row['child_flags'].items()}
            for name, value in row['spawn_types'].items():
                if name != 'DUST_DROP':
                    expected['SPAWN_TYPE_' + name] = value
                physical = 'NONE' if name == 'UNDEFINED' else name
                if name in temporary:
                    physical = 'LEGACY_' + name
                types.append(f'{{{build}, SPAWN_TYPE_{physical}, {value}}}')
            queries.extend(f'{{{build}, {json.dumps(name)}, {expected.get(name, -1)}}}' for name in names)

        mapper = function(constants, 'mapstrings_transconst')
        registrations = '\n'.join(line for line in mapper.splitlines() if re.search(
            r'\bICMPCONST(?:_\w+)?\((?:SPAWN_TYPE_|CHILD_SPAWN_CONFIG_)', line))
        self.assertTrue(registrations)
        macros = ('ICMPCONST', 'ICMPCONST_SINCE', 'ICMPCONST_ALIAS_RANGE', 'ICMPCONST_PROFILE_NAME')
        _, properties = switch_cases(script, 'openbor_getentityproperty', 'propind', outermost=True)
        spawn = function(source, 'child_spawn_execute_object')
        spawn_arms = ('if (obor_profile_build >= 7390u)',
                      'if (object->config & CHILD_SPAWN_CONFIG_BEHAVIOR_SHOT)',
                      'if (object->config & CHILD_SPAWN_CONFIG_BEHAVIOR_BOMB)')
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"
#undef stricmp
#define stricmp strcasecmp

uint32_t obor_profile_build;
@MAPPER@
@MACROS@

static LONG constant_value(const char *constname)
{
    ScriptVariant v = {0};
    if (0) { }
    @ENTRIES@
    else return -1;
    return v.lVal;
}

void ScriptVariant_ChangeType(ScriptVariant *value, VARTYPE type)
{
    value->vt = type;
}

static LONG spawn_type(e_spawn_type type)
{
    entity actor = {.spawntype = type}, *ent = &actor;
    ScriptVariant result = {0}, *out = &result, **pretvar = &out;
    switch (0)
    {
    case 0:
        @GETTER@
    }
    return result.vt == VT_INTEGER ? result.lVal : -1;
}

static LONG child_type(e_child_spawn_config config)
{
    entity child = {0}, *child_entity = &child;
    s_child_spawn data = {.config = config}, *object = &data;
    @SPAWN_TYPES@
    return spawn_type(child.spawntype);
}

int main(void)
{
    static const struct { uint32_t build; const char *name; LONG want; } constants[] = {
        @QUERIES@
    };
    static const struct { uint32_t build; e_spawn_type type; LONG want; } types[] = {
        @TYPES@
    };
    for (size_t i = 0; i < sizeof(constants) / sizeof(*constants); ++i)
    {
        obor_profile_build = constants[i].build;
        if (constant_value(constants[i].name) != constants[i].want)
        {
            fprintf(stderr, "Profile %u resolved %s incorrectly\n", obor_profile_build, constants[i].name);
            return 1;
        }
    }
    for (size_t i = 0; i < sizeof(types) / sizeof(*types); ++i)
    {
        obor_profile_build = types[i].build;
        if (spawn_type(obor_profile_spawn_type(types[i].type)) != types[i].want)
        {
            fprintf(stderr, "Profile %u returned the wrong spawn type for %d\n",
                    obor_profile_build, (int)types[i].type);
            return 2;
        }
    }
    obor_profile_build = 7369;
    if (spawn_type((e_spawn_type)3) != 3 || spawn_type((e_spawn_type)77) != 77) return 3;
    obor_profile_build = 7382;
    if (child_type(0) != 0 || child_type(CHILD_SPAWN_CONFIG_BEHAVIOR_SHOT) != 4 ||
        child_type(CHILD_SPAWN_CONFIG_BEHAVIOR_BOMB) != 0) return 4;
    obor_profile_build = 7388;
    if (child_type(CHILD_SPAWN_CONFIG_BEHAVIOR_BOMB) != 2) return 5;
    obor_profile_build = 7390;
    if (child_type(0) != 2 || child_type(CHILD_SPAWN_CONFIG_BEHAVIOR_SHOT) != 2 ||
        child_type(CHILD_SPAWN_CONFIG_BEHAVIOR_BOMB) != 2) return 6;
    return 0;
}
'''
        inputs = {
            'MAPPER': function(constants, 'obor_profile_property_constant'),
            'MACROS': '\n'.join(continued_macro(constants, name) for name in macros),
            'ENTRIES': registrations,
            'GETTER': properties['_ep_spawntype']['body'],
            'SPAWN_TYPES': '\n'.join(braced_statement(spawn, anchor) for anchor in spawn_arms),
            'QUERIES': ',\n'.join(queries),
            'TYPES': ',\n'.join(types),
        }
        for key, content in inputs.items():
            code = code.replace('@' + key + '@', content)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_child_spawn_speed_diagnostics(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        spawn = function((engine / 'openbor.c').read_text(), 'child_spawn_execute_object')
        diagnostics = braced_statement(spawn, 'if (obor_profile_build >= 7382u && obor_profile_build < 7421u)')
        code = r'''
#include "openbor.h"
#include <stdlib.h>
#include <string.h>
#undef printf

uint32_t obor_profile_build;
static entity actor;
static unsigned calls;

static void record_speed(const char *format, void *value)
{
    if (strcmp(format, "\n\t child_entity->modeldata.speed: %p") || value != &actor.modeldata.speed)
    {
        abort();
    }
    ++calls;
}

#define printf record_speed
static void report_child_speed(entity *child_entity)
{
@DIAGNOSTICS@
}
#undef printf

int main(void)
{
    static const unsigned builds[] = {7369, 7381, 7382, 7391, 7420, 7421, 7533};
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        calls = 0;
        report_child_speed(&actor);
        if (calls != (builds[i] >= 7382u && builds[i] < 7421u ? 2 : 0))
        {
            abort();
        }
    }
    return 0;
}
'''
        self.assertEqual(native_output(code.replace('@DIAGNOSTICS@', diagnostics),
                                       {'engine': '7533'}, engine_source=engine), '')

    def test_child_spawn_debug_fields_follow_original_revisions(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        code = r'''
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef assert
#undef printf
#include <assert.h>

uint32_t obor_profile_build;
static unsigned colors, moves;
static int printed_move;
static const char *movement_label;

static void record_field(const char *format, ...)
{
    if (strcmp(format, "\n\t\t %-*s %d") != 0) return;
    char line[96];
    va_list args;
    va_start(args, format);
    vsnprintf(line, sizeof(line), format, args);
    va_end(args);
    if (strstr(line, "->color:"))
    {
        assert(strcmp(strrchr(line, ' '), " 3") == 0);
        ++colors;
    }
    else if (strstr(line, "->move_constraint:") || strstr(line, "->move_config_flags:"))
    {
        movement_label = strstr(line, "->move_constraint:") ? "->move_constraint:" : "->move_config_flags:";
        printed_move = (int)strtol(strrchr(line, ' ') + 1, NULL, 10);
        ++moves;
    }
}

#define printf record_field
@DUMP@
#undef printf

int main(void)
{
    static const struct
    {
        unsigned build;
        int bits;
    } profiles[] = {
        {7391, (1 << 8) | (1 << 10)}, {7420, (1 << 8) | (1 << 10)},
        {7426, (1 << 8) | (1 << 10)}, {7427, (1 << 10) | (1 << 12)},
        {7434, (1 << 10) | (1 << 12)}, {7435, (1 << 10) | (1 << 12)},
        {7446, (1 << 10) | (1 << 12)}, {7447, (1 << 14) | (1 << 16)},
        {7497, (1 << 14) | (1 << 16)}, {7498, (1 << 16) | (1 << 18)},
        {7533, (1 << 16) | (1 << 18)}
    };
    s_child_spawn child = {.color = 3,
        .move_config_flags = MOVE_CONFIG_SUBJECT_TO_PLATFORM | MOVE_CONFIG_SUBJECT_TO_WALL};
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i].build;
        colors = moves = 0;
        child_spawn_dump_object(&child);
        assert(colors == (obor_profile_build >= 7435u));
        assert(moves == 1 && printed_move == profiles[i].bits);
        const char *expected = obor_profile_build < 7498u ? "->move_constraint:" : "->move_config_flags:";
        assert(strcmp(movement_label, expected) == 0);
    }
    return 0;
}
'''
        code = code.replace('@DUMP@', function(source, 'child_spawn_dump_object'))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_child_spawn_faction_and_movement(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        constants = (engine / 'source/openborscript/constants.c').read_text()
        mapper = function(constants, 'mapstrings_transconst')
        spawn = function(source, 'child_spawn_execute_object')
        first = spawn.index('    if (object->config & CHILD_SPAWN_CONFIG_FACTION_DAMAGE_PARAMETER)')
        last = spawn.index('    /*\n    * Execute event scripts.', first)
        code = Path(__file__).with_name('modern_legacy_child_movement_contract.c.in').read_text()
        inputs = {
            'MACRO': continued_macro(constants, 'ICMPCONST_MOVE_FLAG'),
            'CONSTANTS': '\n'.join(line for line in mapper.splitlines() if 'ICMPCONST_MOVE_FLAG(' in line),
            'METHODS': '\n'.join(function(source, name) for name in
                                 ('find_move_config_flags_from_string', 'get_move_config_flags_from_arguments',
                                  'obor_profile_static_move_flags')),
            'INHERIT': spawn[first:last],
        }
        for key, content in inputs.items():
            code = code.replace('@' + key + '@', content)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_model_directive_spellings_follow_original_revisions(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        loader, arms = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        lookup = 'obor_profile_model_command(getModelCommand(modelcmdlist, command), command)'
        self.assertIn('cmd = ' + lookup + ';', loader)

        commands = model_command_functions((engine / 'source/openborscript/commands.c').read_text(),
                                           (engine / 'source/utils.c').read_text())
        profiles = {7369, 7391, 7420, 7533}
        cases = []
        for revisions, names in MODERN_MODEL_DIRECTIVES.items():
            profiles.update(candidate for revision in revisions for candidate in (revision - 1, revision))
            for name in names:
                for revision in revisions:
                    for candidate in (revision - 1, revision):
                        recognized = sum(change <= candidate for change in revisions) % 2
                        cases.append((candidate, name.upper(), recognized))
                cases.extend((p, name, sum(change <= p for change in revisions) % 2)
                             for p in (7369, 7391, 7420, 7533))
        for name, introduced, replaced in (
            ('move_constraint', 0, 7498), ('child_spawn_move_constraint', 7386, 7498),
            ('noshadow', 7409, 7475), ('weapon_loss_condition', 0, 7432),
        ):
            controls = {7369, 7391, 7420, 7530, replaced - 1, replaced}
            if introduced:
                previous = 7406 if introduced == 7409 else introduced - 1
                controls.update((previous, introduced))
            cases.extend((p, name.upper(), int(introduced <= p < replaced)) for p in sorted(controls))
        for revision in sorted(profiles):
            cases.extend((revision, name, recognized) for name, recognized in (
                ('JUMPHEIGHT', 1), ('JUMPSPEEDF', 1), ('defense', 1), ('offense', 1),
                ('unrecognized_directive', 0),
            ))

        code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#include "source/openborscript/commands.h"
#include "source/scriptlib/List.c"
#undef printf
#undef stricmp
#undef strnicmp
#define stricmp strcasecmp
#define strnicmp strncasecmp

uint32_t obor_profile_build;

void *checkAlloc(void *pointer, size_t size, const char *function, const char *file, int line)
{
    (void)size;
    (void)function;
    (void)file;
    (void)line;
    if (!pointer) abort();
    return pointer;
}

void writeToLogFile(const char *format, ...) { (void)format; abort(); }

s_child_spawn *child_spawn_upsert_property(s_child_spawn **head, int index)
{
    if (!*head || index != 2) abort();
    return *head;
}

int arrow_takedamage(entity *other, s_attack *attack, int fall_flag, s_defense *defense_object)
{
    abort();
}

@METHODS@

static void configure_model(s_model *newchar, s_child_spawn *child, List *modelcmdlist, ArgList arglist)
{
    char *filename = "model.txt";
    char command[80];
    strcpy(command, GET_ARG(0));
    s_child_spawn *temp_child_spawn_head = child;
    const int temp_child_spawn_index = 2;
    int tempInt;
    modelCommands cmd = @LOOKUP@;
    switch (cmd)
    {
@ACTIONS@
    default:
        fprintf(stderr, "Unexpected model directive %s in profile %u\n", command, obor_profile_build);
        abort();
    }
}

static void check_value(const char *field, unsigned int value, unsigned int expected)
{
    if (value != expected)
    {
        fprintf(stderr, "%s gave %u in profile %u, expected %u\n", field, value, obor_profile_build, expected);
        abort();
    }
}

static void check_legacy_settings(List *modelcmdlist)
{
    const uint32_t profiles[] = {7369, 7391, 7420};
    const unsigned int initial_shadow = SHADOW_CONFIG_GRAPHIC_STATIC_AIR | SHADOW_CONFIG_BASE_PLATFORM;
    const unsigned int all_constraints = MOVE_CONFIG_NO_ADJUST_BASE | MOVE_CONFIG_NO_HIT_HEAD |
        MOVE_CONFIG_SUBJECT_TO_BASEMAP | MOVE_CONFIG_SUBJECT_TO_GRAVITY | MOVE_CONFIG_SUBJECT_TO_HOLE |
        MOVE_CONFIG_SUBJECT_TO_MAX_Z | MOVE_CONFIG_SUBJECT_TO_MIN_Z | MOVE_CONFIG_SUBJECT_TO_OBSTACLE |
        MOVE_CONFIG_SUBJECT_TO_PLATFORM | MOVE_CONFIG_SUBJECT_TO_SCREEN | MOVE_CONFIG_SUBJECT_TO_WALL;
    s_model model = {0};
    s_child_spawn child = {0};
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        configure_model(&model, &child, modelcmdlist,
                        (ArgList){.count = 3, .args = {"move_constraint", "no_hit_head", "Subject_To_Wall"}});
        check_value("model movement", model.move_config_flags, MOVE_CONFIG_NO_HIT_HEAD | MOVE_CONFIG_SUBJECT_TO_WALL);
        configure_model(&model, &child, modelcmdlist, (ArgList){.count = 12, .args = {
            "move_constraint", "no_adjust_base", "no_hit_head", "subject_to_basemap", "subject_to_gravity",
            "subject_to_hole", "subject_to_max_z", "subject_to_min_z", "subject_to_obstacle",
            "subject_to_platform", "subject_to_screen", "subject_to_wall"}});
        check_value("all original movement constraints", model.move_config_flags, all_constraints);
        configure_model(&model, &child, modelcmdlist,
                        (ArgList){.count = 2, .args = {"move_constraint", "none"}});
        check_value("reset original movement constraints", model.move_config_flags, MOVE_CONFIG_NONE);
        if (profiles[i] >= 7386)
        {
            configure_model(&model, &child, modelcmdlist,
                            (ArgList){.count = 2, .args = {"child_spawn_move_constraint", "subject_to_platform"}});
            check_value("child movement", child.move_config_flags, MOVE_CONFIG_SUBJECT_TO_PLATFORM);
        }
        configure_model(&model, &child, modelcmdlist,
                        (ArgList){.count = 3, .args = {"weapon_loss_condition", "death", "fall"}});
        check_value("weapon loss flags", model.weapon_properties.loss_condition,
                    WEAPON_LOSS_CONDITION_DEATH | WEAPON_LOSS_CONDITION_FALL);
    }

    obor_profile_build = 7420;
    model.shadow_config_flags = initial_shadow;
    configure_model(&model, &child, modelcmdlist, (ArgList){.count = 2, .args = {"noshadow", "1"}});
    check_value("original shadow disable value", model.legacy_noshadow, 1);
    configure_model(&model, &child, modelcmdlist, (ArgList){.count = 2, .args = {"noshadow", "2"}});
    check_value("original shadow enable value", model.legacy_noshadow, 2);
    check_value("shadow layout flags", model.shadow_config_flags, initial_shadow);

    obor_profile_build = 7430;
    configure_model(&model, &child, modelcmdlist,
                    (ArgList){.count = 2, .args = {"move_constraint", "projectile_wall_bounce"}});
    check_value("early projectile flag", model.move_config_flags, MOVE_CONFIG_NONE);
    obor_profile_build = 7431;
    configure_model(&model, &child, modelcmdlist,
                    (ArgList){.count = 2, .args = {"move_constraint", "projectile_wall_bounce"}});
    check_value("new projectile flag", model.move_config_flags, MOVE_CONFIG_PROJECTILE_WALL_BOUNCE);
    configure_model(&model, &child, modelcmdlist, (ArgList){.count = 2, .args = {"weapon_loss_condition", "none"}});
    check_value("original weapon loss fallback", model.weapon_properties.loss_condition, WEAPON_LOSS_CONDITION_DEFAULT);
    obor_profile_build = 7432;
    configure_model(&model, &child, modelcmdlist, (ArgList){.count = 2, .args = {"weapon_loss_config", "none"}});
    check_value("new weapon loss fallback", model.weapon_properties.loss_condition, WEAPON_LOSS_CONDITION_DEFAULT);
    obor_profile_build = 7446;
    configure_model(&model, &child, modelcmdlist, (ArgList){.count = 2, .args = {"move_constraint", "no_move"}});
    check_value("early no_move flag", model.move_config_flags, MOVE_CONFIG_NONE);
    obor_profile_build = 7447;
    configure_model(&model, &child, modelcmdlist, (ArgList){.count = 2, .args = {"move_constraint", "no_move"}});
    check_value("new no_move flag", model.move_config_flags, MOVE_CONFIG_NO_MOVE);
    obor_profile_build = 7498;
    configure_model(&model, &child, modelcmdlist, (ArgList){.count = 2, .args = {"move_config", "unused"}});
    check_value("new movement fallback", model.move_config_flags, MOVE_CONFIG_NONE);
    configure_model(&model, &child, modelcmdlist, (ArgList){.count = 2, .args = {"shadow_config", "base_platform"}});
    check_value("new shadow settings", model.shadow_config_flags, SHADOW_CONFIG_BASE_PLATFORM);
}

static void check_model_reactions(List *modelcmdlist)
{
    const uint32_t profiles[] = {7369, 7391, 7420, 7446, 7447, 7493, 7494, 7533};
    const e_move_config_flags static_flags = MOVE_CONFIG_NO_MOVE | MOVE_CONFIG_NO_FLIP;
    const e_pain_config_flags fall_flags = PAIN_CONFIG_FALL_DISABLE | PAIN_CONFIG_FALL_DISABLE_AIR;
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        const int legacy_move = obor_profile_build < 7447;
        const int legacy_reactions = obor_profile_build < 7494;
        s_model model = {0};
        configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 3, .args = {"nomove", "1", "-2"}});
        check_value("static movement flags", obor_profile_static_move_flags(&model), static_flags);
        check_value("nomove fall response", obor_profile_pain_flags(&model), PAIN_CONFIG_FALL_DISABLE);

        configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 3, .args = {"nomove", "0", "0"}});
        check_value("repeated nomove", obor_profile_static_move_flags(&model), legacy_move ? 0 : static_flags);
        check_value("nomove retains fall response", obor_profile_pain_flags(&model), PAIN_CONFIG_FALL_DISABLE);

        configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"nodrop", "-3"}});
        check_value("negative nodrop", obor_profile_pain_flags(&model), legacy_reactions ? PAIN_CONFIG_FALL_DISABLE : 0);
        configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"nodrop", "3"}});
        check_value("high nodrop", obor_profile_pain_flags(&model), legacy_reactions ? fall_flags : 0);
        configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"nodrop", "2"}});
        check_value("ground and air fall response", obor_profile_pain_flags(&model), fall_flags);

        configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"nopain", "-4"}});
        configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"backpain", "-7"}});
        check_value("pain response flags", obor_profile_pain_flags(&model),
                    fall_flags | PAIN_CONFIG_BACK_PAIN | PAIN_CONFIG_PAIN_DISABLE);
        if (legacy_reactions)
        {
            check_value("stored nopain", model.legacy_nopain, -4);
            check_value("stored backpain", model.legacy_backpain, -7);
        }
        configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"nopain", "0"}});
        configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"backpain", "0"}});
        check_value("cleared pain response", obor_profile_pain_flags(&model), fall_flags);

        if (legacy_move)
        {
            configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 3, .args = {"nomove", "1", "1"}});
            configure_model(&model, NULL, modelcmdlist,
                            (ArgList){.count = 2, .args = {"move_constraint", "subject_to_basemap"}});
            check_value("independent static flags", obor_profile_static_move_flags(&model), static_flags);
            check_value("independent move constraint", model.move_config_flags, MOVE_CONFIG_SUBJECT_TO_BASEMAP);
        }
    }
}

static void check_model_death_values(List *modelcmdlist)
{
    static const struct { uint32_t profile; int legacy; } contexts[] = {
        {7369, 1}, {7391, 1}, {7420, 1}, {7481, 1}, {7482, 0}, {7486, 0},
        {7487, 1}, {7488, 1}, {7489, 0}, {7530, 0}, {7533, 0},
    };
    for (size_t i = 0; i < sizeof(contexts) / sizeof(*contexts); ++i)
    {
        obor_profile_build = contexts[i].profile;
        s_model model = {0};
        check_value("death representation", obor_uses_legacy_death_config(), contexts[i].legacy);
        if (contexts[i].legacy)
        {
            configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"falldie", "-4"}});
            configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"nodieblink", "5"}});
            check_value("original falldie", model.legacy_falldie, -4);
            check_value("original nodieblink", model.legacy_nodieblink, 5);
            configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"death", "2"}});
            check_value("original death alias", model.legacy_falldie, 2);
            check_value("separate death configuration", model.death_config_flags, DEATH_CONFIG_NONE);
        }
        else
        {
            configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"falldie", "1"}});
            check_value("instant death flags", model.death_config_flags,
                        DEATH_CONFIG_MACRO_DEATH | DEATH_CONFIG_SOURCE_MODEL);
            configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"nodieblink", "0"}});
            check_value("modern blink flag", model.death_config_flags & DEATH_CONFIG_BLINK_REMOVE_AIR,
                        DEATH_CONFIG_BLINK_REMOVE_AIR);
        }
    }
}

static void check_model_block_values(List *modelcmdlist)
{
    static const unsigned profiles[] = {7369, 7391, 7420, 7492, 7493, 7533};
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        s_model model = {0};
        configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"holdblock", "4"}});
        configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"blockback", "-7"}});
        if (profiles[i] < 7493)
        {
            check_value("original holdblock", model.legacy_holdblock, 4);
            check_value("original blockback", model.legacy_blockback, -7);
            check_value("separate block state", model.block_config_flags, BLOCK_CONFIG_NONE);
        }
        else
        {
            check_value("modern blockback", model.block_config_flags, BLOCK_CONFIG_BACK);
            configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"holdblock", "2"}});
            check_value("modern holdblock", model.block_config_flags,
                        BLOCK_CONFIG_BACK | BLOCK_CONFIG_HOLD_IMPACT | BLOCK_CONFIG_HOLD_INFINITE);
        }
        configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"nopassiveblock", "-2"}});
        check_value("active block truth value", model.block_config_flags & BLOCK_CONFIG_ACTIVE, BLOCK_CONFIG_ACTIVE);
        configure_model(&model, NULL, modelcmdlist, (ArgList){.count = 2, .args = {"nopassiveblock", "0"}});
        check_value("cleared active block", model.block_config_flags & BLOCK_CONFIG_ACTIVE, 0);
    }
}

static void check_model_child_projectile_presets(List *modelcmdlist)
{
    static const unsigned profiles[] = {7386, 7391, 7420, 7426, 7427, 7446, 7447, 7497, 7498, 7533};
    const unsigned common = CHILD_SPAWN_CONFIG_AUTOKILL_HIT | CHILD_SPAWN_CONFIG_FACTION_DAMAGE_PARENT |
                            CHILD_SPAWN_CONFIG_FACTION_HOSTILE_PARENT | CHILD_SPAWN_CONFIG_FACTION_INDIRECT_PARENT |
                            CHILD_SPAWN_CONFIG_MOVE_CONFIG_PARAMETER | CHILD_SPAWN_CONFIG_RELATIONSHIP_OWNER;
    const unsigned movement = MOVE_CONFIG_NO_ADJUST_BASE | MOVE_CONFIG_SUBJECT_TO_HOLE |
                              MOVE_CONFIG_SUBJECT_TO_PLATFORM | MOVE_CONFIG_SUBJECT_TO_WALL |
                              MOVE_CONFIG_SUBJECT_TO_MAX_Z | MOVE_CONFIG_SUBJECT_TO_MIN_Z;
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        s_model model = {0};
        s_child_spawn bomb = {0}, shot = {0};
        obor_profile_build = profiles[i];
        configure_model(&model, &bomb, modelcmdlist, (ArgList){.count = 1, .args = {"child_spawn_preset_bomb"}});
        configure_model(&model, &shot, modelcmdlist, (ArgList){.count = 1, .args = {"child_spawn_preset_shot"}});
        check_value("bomb options", bomb.config, common | CHILD_SPAWN_CONFIG_BEHAVIOR_BOMB | CHILD_SPAWN_CONFIG_LAUNCH_TOSS);
        check_value("shot options", shot.config, common | CHILD_SPAWN_CONFIG_BEHAVIOR_SHOT |
                    CHILD_SPAWN_CONFIG_GRAVITY_OFF | CHILD_SPAWN_CONFIG_LAUNCH_THROW);
        check_value("bomb movement", bomb.move_config_flags, movement);
        check_value("shot movement", shot.move_config_flags, movement);
        check_value("bomb aimove", bomb.aimove, AIMOVE1_BOMB);
        check_value("shot aimove", shot.aimove, AIMOVE1_ARROW);
        check_value("bomb direction", bomb.direction_adjust, DIRECTION_ADJUST_SAME);
        check_value("shot direction", shot.direction_adjust, DIRECTION_ADJUST_SAME);
        if (shot.takedamage != arrow_takedamage) abort();
    }
}

static void check_model_running_values(List *modelcmdlist)
{
    static const unsigned profiles[] = {7369, 7391, 7420, 7497, 7498, 7511, 7512, 7528, 7529, 7533};
    const unsigned int z_enabled = RUN_CONFIG_Z_DOWN_ENABLED | RUN_CONFIG_Z_UP_ENABLED;
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        s_model model = {0};
        configure_model(&model, NULL, modelcmdlist,
                        (ArgList){.count = 6, .args = {"running", "25", "4.5", "1.5", "-6", "-3"}});
        if (model.runspeed != 2.5f || model.runjumpheight != 4.5f || model.runjumpdist != 1.5f)
        {
            abort();
        }
        check_value("running movez", model.runupdown, profiles[i] < 7512 ? -6 : 0);
        check_value("running land", model.legacy_runhold, profiles[i] < 7529 ? -3 : 0);
        check_value("running typed state", model.run_config_flags & z_enabled,
                    profiles[i] < 7512 ? 0 : z_enabled);

        configure_model(&model, NULL, modelcmdlist,
                        (ArgList){.count = 2, .args = {"run.move.z", "50%"}});
        check_value("run.move.z parser", model.runupdown,
                    profiles[i] < 7498 ? 0 : profiles[i] < 7512 ? 50 : 0);
        check_value("run.move.z typed state", model.run_config_flags & z_enabled,
                    profiles[i] < 7512 ? 0 : z_enabled);

        configure_model(&model, NULL, modelcmdlist,
                        (ArgList){.count = 2, .args = {"run.jump.continue", "-250%"}});
        check_value("run.jump.continue raw value", model.legacy_runhold, profiles[i] < 7529 ? -2 : 0);
        configure_model(&model, NULL, modelcmdlist,
                        (ArgList){.count = 2, .args = {"run.jump.continue", "50%"}});
        check_value("run.jump.continue parser", model.run_config_flags & RUN_CONFIG_LAND,
                    profiles[i] < 7529 ? 0 : RUN_CONFIG_LAND);
    }
}

int main(void)
{
    static const struct {
        uint32_t revision;
        const char *spelling;
        int recognized;
    } cases[] = {
@CASES@
    };
    List *modelcmdlist = createModelCommandList();
    for (size_t i = 0; i < sizeof(cases) / sizeof(*cases); ++i)
    {
        char command[80];
        strcpy(command, cases[i].spelling);
        obor_profile_build = cases[i].revision;
        modelCommands result = @LOOKUP@;
        if ((result != 0) != cases[i].recognized)
        {
            fprintf(stderr, "Model directive %s gave %d in profile %u (expected recognition %d)\n",
                    command, (int)result, obor_profile_build, cases[i].recognized);
            freeCommandList(modelcmdlist);
            return 1;
        }
    }
    check_legacy_settings(modelcmdlist);
    check_model_reactions(modelcmdlist);
    check_model_death_values(modelcmdlist);
    check_model_block_values(modelcmdlist);
    check_model_child_projectile_presets(modelcmdlist);
    check_model_running_values(modelcmdlist);
    freeCommandList(modelcmdlist);
    return 0;
}
'''
        methods = ('obor_profile_model_command', 'isNumeric', 'getValidInt', 'getValidFloat', 'get_weapon_loss_from_argument',
                   'lcmHandleCommandWeaponLossCondition', 'find_move_config_flags_from_string',
                   'get_move_config_flags_from_arguments', 'shadow_get_config_flag_from_string',
                   'shadow_get_config_flags_from_arguments', 'obor_profile_pain_flags',
                   'obor_profile_static_move_flags', 'death_config_get_value_from_falldie',
                   'death_config_get_value_from_nodieblink')
        dispatch = ('CMD_MODEL_MOVE_CONFIG', 'CMD_MODEL_CHILD_SPAWN_MOVE_CONSTRAINT', 'CMD_MODEL_SHADOW_CONFIG',
                    'CMD_MODEL_WEAPON_LOSS_CONFIG', 'CMD_MODEL_NOMOVE', 'CMD_MODEL_NODROP',
                    'CMD_MODEL_NOPAIN', 'CMD_MODEL_PAIN_BACK', 'CMD_MODEL_FALLDIE', 'CMD_MODEL_DEATH',
                    'CMD_MODEL_NODIEBLINK', 'CMD_MODEL_HOLDBLOCK', 'CMD_MODEL_BLOCKBACK', 'CMD_MODEL_NOPASSIVEBLOCK',
                    'CMD_MODEL_RUNNING', 'CMD_MODEL_RUNNING_CONTINUE', 'CMD_MODEL_RUNNING_Z_MOVE',
                    'CMD_MODEL_CHILD_SPAWN_PRESET_BOMB', 'CMD_MODEL_CHILD_SPAWN_PRESET_SHOT')
        code = (code.replace('@METHODS@', commands + '\n' + '\n'.join(function(source, name) for name in methods))
                .replace('@ACTIONS@', '\n'.join('case ' + name + ':' + arms[name]['body'] for name in dispatch))
                .replace('@LOOKUP@', lookup)
                .replace('@CASES@', '\n'.join('        {%du, %s, %d},' %
                                           (revision, json.dumps(name), recognized)
                                           for revision, name, recognized in cases)))
        output = native_output(code, {'engine': '7533'}, engine_source=engine)
        self.assertEqual([line.strip() for line in output.splitlines() if line.strip()], [
            *["Unknown move constraint flag (none), using 'none'."] * 3,
            "Unknown move constraint flag (projectile_wall_bounce), using 'none'.",
            "Unknown weapon loss flag (none), using 'default'.",
            "Unknown weapon loss config value (none), using 'default'.",
            "Unknown move constraint flag (no_move), using 'none'.",
            "Unknown move constraint flag (unused), using 'none'.",
        ])

    def test_legacy_death_animation_and_removal(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        routines = ('diff', 'inair', 'checkdeath', 'obor_legacy_lie_after_death', 'common_lie',
                    'obor_damage_death_handled', 'star_move')
        player = function(source, 'player_die')
        start = player.index('    const int legacy = obor_uses_legacy_death_config();')
        end = player.index('    if(player[playerindex].lives <= 0)', start)
        obstacle = braced_statement(function(source, 'obstacle_takedamage'),
                                   'if (obor_uses_legacy_death_config() ? !self->modeldata.legacy_nodieblink')
        damage = function(source, 'common_takedamage')
        landing = braced_statement(damage,
            'if(acting_entity->die_on_landing && acting_entity->energy_state.health_current <= 0)')
        timeout = function(source, 'kill_all_players_by_timeover')
        writes = {}
        for number, flag in ((1, 'DEATH_CONFIG_MACRO_DEATH'), (2, 'DEATH_CONFIG_MACRO_DEATH_FALL_LAND')):
            pattern = (r'if \(obor_uses_legacy_death_config\(\)\)\s*\{\s*'
                       rf'self->modeldata\.legacy_falldie = {number};\s*\}}\s*else\s*\{{\s*'
                       rf'self->modeldata\.death_config_flags \|= {flag};\s*\}}')
            writes[number] = re.search(pattern, timeout)[0]
        template = Path(__file__).with_name('modern_legacy_death_contract.c.in').read_text()
        fall = braced_statement(damage, 'if(acting_entity->drop || acting_entity->energy_state.health_current <= 0)')
        code = (template.replace('@METHODS@', '\n'.join(function(source, name) for name in routines))
                .replace('@FINISH_PLAYER_DEATH@', player[start:end].rstrip())
                .replace('@OBSTACLE_BLINK@', obstacle).replace('@FALLDIE_ON_LANDING@', landing)
                .replace('@DAMAGE_FALL@', fall)
                .replace('@TIMEOUT_FALL@', writes[2]).replace('@TIMEOUT_INSTANT@', writes[1]))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_grab_vault_player_and_ai_routes(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        player_check = function(source, 'player_grab_check')
        vault = braced_statement(
            player_check, 'else if(player[self->playerindex].playkeys & FLAG_JUMP && validanim(self, ANI_VAULT))')
        table = re.search(r'(?ms)^int[ \t]+grab_attacks\[[^\n]+\n\{.*?^\};', source)[0]
        code = r'''
#include <stdint.h>
#include <string.h>
#include "openbor.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
u32 _time = 100;
int nolost;
s_player player[MAX_PLAYERS];
static entity actor, held;
entity *self = &actor;
static s_anim available_animation = {.numframes = 1};
static s_anim *animations[MAX_ANIS];
static u32 random_choice;
static unsigned animation_calls;

u32 rand32(void) { return random_choice; }
void ent_set_anim(entity *ent, int animation, int reset)
{
    assert(ent == &actor && reset == 0);
    ent->animnum = animation;
    ++animation_calls;
}

void common_grabattack(void) { assert(0); }
void dropweapon(int mode) { assert(0); }
void ent_unlink(entity *ent) { assert(0); }
int set_idle(entity *ent) { assert(0); return 0; }
void doprethrow(void) { assert(0); }
void dothrow(void) { assert(0); }

@TABLE@
@FUNCTIONS@

static void player_vault(void)
{
    if (0) {}
    @PLAYER_VAULT@
}

static void prepare_grab(void)
{
    actor = (entity){.link = &held, .releasetime = _time, .animnum = ANI_NONE};
    held = (entity){.link = &actor};
    actor.modeldata.animation = animations;
    actor.modeldata.animation_capacity = sizeof(animations) / sizeof(*animations);
    actor.velocity.x = 3;
    held.velocity.z = 7;
    actor.combostep[0] = 2;
    animation_calls = 0;
}

static void check_player(unsigned build)
{
    prepare_grab();
    player[0].playkeys = FLAG_JUMP;
    player_vault();
    const int finisher = build >= 7394u && build < 7424u;
    const int sets_action = build < 7424u || build >= 7430u;
    assert(animation_calls == 1 && actor.animnum == (finisher ? ANI_GRABATTACK2 : ANI_VAULT));
    assert(actor.takeaction == (sets_action ? common_grabattack : NULL));
    assert(actor.attacking == (sets_action ? ATTACKING_ACTIVE : ATTACKING_NONE));
    assert(!(player[0].playkeys & FLAG_JUMP));
    assert(actor.velocity.x == (build < 7424u ? 0 : 3) && held.velocity.z == (build < 7424u ? 0 : 7));
    assert(actor.combostep[0] == (build < 7394u || !sets_action ? 2u : 0u));
    assert(actor.combostep[GRAB_ACTION_SELECT_VAULT] == (build < 7394u ? 1u : 0u));
}

static void check_ai(unsigned build)
{
    prepare_grab();
    random_choice = 17;
    common_grab_check();
    assert(animation_calls == (build < 7394u ? 1u : 0u));
    assert(actor.animnum == (build < 7394u ? ANI_VAULT : ANI_NONE));

    prepare_grab();
    random_choice = 5;
    common_grab_check();
    assert(animation_calls == (build >= 7509u ? 1u : 0u));
    assert(actor.animnum == (build >= 7509u ? ANI_VAULT : ANI_NONE));
}

int main(void)
{
    static const unsigned builds[] = {7369, 7391, 7394, 7420, 7421, 7424, 7427, 7430, 7504, 7509, 7533};
    animations[ANI_VAULT] = animations[ANI_ATTACK3] = animations[ANI_GRABATTACK2] = &available_animation;
    for (size_t p = 0; p < sizeof(builds) / sizeof(*builds); ++p)
    {
        obor_profile_build = builds[p];
        check_player(builds[p]);
        check_ai(builds[p]);
        prepare_grab();
        animations[ANI_GRABATTACK2] = NULL;
        assert(do_grab_attack_finish(&actor, GRAB_ACTION_SELECT_ATTACK) ==
               (builds[p] < 7424u ? ANI_VAULT : ANI_ATTACK3));
        animations[ANI_GRABATTACK2] = &available_animation;
    }
    return 0;
}
'''
        functions = '\n'.join(function(source, name) for name in (
            'do_grab_attack_finish', 'dograbattack', 'common_grab_check'))
        code = code.replace('@TABLE@', table).replace('@FUNCTIONS@', functions).replace('@PLAYER_VAULT@', vault)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine,
                                       extra_cflags=('-Wno-enum-conversion',)), '')

    def test_original_animation_completion_and_loop_boundary(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        code = r'''
#include <stdint.h>
#include "openbor.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
u32 _time = 17;
unsigned long long bothnewkeys;
float scrolldx, scrolldy;
s_level *level;
static entity actor;
entity *self = &actor;
static unsigned advanced, retired;
static e_kill_entity_trigger reason;

int colorset_timed_expire(entity *ent) { assert(ent == &actor); return 0; }
void unfrozen(entity *ent) { assert(0); }

void update_frame(entity *ent, unsigned f)
{
    assert(ent == &actor);
    ent->animpos = f;
    ++advanced;
}

void kill_entity(entity *ent, e_kill_entity_trigger trigger)
{
    assert(ent == &actor && ent->animating == ANIMATING_NONE);
    reason = trigger;
    ++retired;
}

@FUNCTIONS@

static void check_animation(int explicit_loop, unsigned autokill)
{
    s_anim animation = {.numframes = 4};
    animation.loop.mode = explicit_loop;
    animation.loop.frame.min = explicit_loop ? 1 : 0;
    animation.loop.frame.max = explicit_loop ? 3 : 0;
    actor = (entity){.animation = &animation, .animating = ANIMATING_FORWARD,
                     .nextanim = _time, .animpos = 3,
                     .autokill = autokill ? AUTOKILL_ANIMATION_COMPLETE : 0};
    advanced = retired = 0;
    update_animation();
    assert(advanced == 0 && retired == autokill);
    assert(actor.animating == ANIMATING_NONE);
    if (autokill)
    {
        assert(reason == (explicit_loop ? KILL_ENTITY_TRIGGER_AUTOKILL_ANIMATION_COMPLETE_DEFINED_LOOP_MAX
                                       : KILL_ENTITY_TRIGGER_AUTOKILL_ANIMATION_COMPLETE_UNDEFINED_LOOP_MAX));
    }

    if (explicit_loop)
    {
        actor.animating = ANIMATING_FORWARD;
        actor.animpos = 2;
        advanced = retired = 0;
        update_animation();
        assert(advanced == 1 && retired == 0 && actor.animpos == 1);
    }
}

int main(void)
{
    static const unsigned builds[] = {7369, 7391, 7420, 7424, 7425, 7494, 7495, 7533};
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        check_animation(0, 0);
        check_animation(0, 1);
        check_animation(1, 0);
        check_animation(1, 1);
    }
    return 0;
}
'''
        methods = ('obor_animation_can_reschedule', 'update_animation')
        code = code.replace('@FUNCTIONS@', '\n'.join(function(source, name) for name in methods))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_arrow_and_bike_damage_endpoints(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        code = r'''
#include <stdint.h>
#include "openbor.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
static entity actor;
entity *self = &actor;
static unsigned damage_calls, removal_calls;
static int fatal_hit;
static const e_move_config_flags flight = MOVE_CONFIG_SUBJECT_TO_BASEMAP |
    MOVE_CONFIG_SUBJECT_TO_GRAVITY | MOVE_CONFIG_SUBJECT_TO_HOLE |
    MOVE_CONFIG_SUBJECT_TO_PLATFORM | MOVE_CONFIG_SUBJECT_TO_WALL;

int common_takedamage(entity *other, s_attack *attack, int fall, s_defense *defense)
{
    assert(other == &actor && fall == 0 && defense == NULL);
    assert(actor.modeldata.move_config_flags == flight);
    obor_entity_dead_script_set(&actor, fatal_hit ? -7 : 0);
    ++damage_calls;
    return 1;
}

void kill_entity(entity *ent, e_kill_entity_trigger trigger)
{
    assert(ent == &actor && trigger == KILL_ENTITY_TRIGGER_TAKE_DAMAGE_BIKER_PIT);
    ++removal_calls;
}

void checkdamage(entity *target, entity *other, s_attack *attack, s_defense *defense)
{
    assert(target == &actor && other == &actor && defense == NULL);
    ++damage_calls;
}

void set_opponent(entity *ent, entity *other) { assert(0); }
int check_backpain(entity *attacker, entity *defender) { assert(0); return 0; }
int set_pain(entity *ent, int type, int reset) { assert(0); return 0; }
void bike_crash(void) { assert(0); }
entity *drop_driver(entity *ent) { assert(0); return NULL; }
void checkdeath(void) { assert(0); }

@DAMAGE@

int main(void)
{
    static const unsigned builds[] = {7369, 7391, 7420, 7424, 7425, 7533};
    for (size_t p = 0; p < sizeof(builds) / sizeof(*builds); ++p)
    {
        obor_profile_build = builds[p];
        s_attack hit = {.no_pain = 1};
        actor = (entity){0};
        damage_calls = removal_calls = 0;
        for (fatal_hit = 0; fatal_hit <= 1; ++fatal_hit)
        {
            actor.modeldata.move_config_flags = MOVE_CONFIG_NO_ADJUST_BASE;
            assert(arrow_takedamage(&actor, &hit, 1, NULL) == fatal_hit);
        }
        assert(damage_calls == 2 && removal_calls == 0);

        actor.position.y = PIT_DEPTH - 1;
        assert(biker_takedamage(&actor, &hit, 0, NULL) == 0 && removal_calls == 0);
        obor_entity_dead_script_set(&actor, 0);
        assert(biker_takedamage(&actor, &hit, 0, NULL) == 0 && removal_calls == 1);
        actor.position.y = 0;
        actor.energy_state.health_current = 10;
        assert(biker_takedamage(&actor, &hit, 0, NULL) == 1);
        assert(damage_calls == 3 && removal_calls == 1);
    }
    return 0;
}
'''
        functions = '\n'.join(function(source, name) for name in ('arrow_takedamage', 'biker_takedamage'))
        self.assertEqual(native_output(code.replace('@DAMAGE@', functions),
                                       {'engine': '7533'}, engine_source=engine), '')

    def test_original_frame_summon_with_live_and_departed_companions(self):
        data = load_contract_fixture(FIXTURE)
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        revisions = (7369, 7391, 7420, 7424, 7425, 7533)
        departures = [[0, variant] for variant in (0, 1, 2, 4)]
        reference = data['contracts'][data['sources'][0]['contract']]
        expected = [reference[data['cases'].index(case)] for case in departures]
        controls = dict(data, cases=[[3, state] for state in range(4)] + departures,
                        sources=[{'revision': build} for build in revisions])
        rows = json.loads(native_output(program(controls), controls, engine_source=engine))['profiles']
        self.assertEqual([row['revision'] for row in rows], list(revisions))
        for row in rows:
            with self.subTest(build=row['revision']):
                self.assertEqual([case['state'] for case in row['cases'][:4]],
                                 [[1, 1], [0, 1], [1, 1], [0, 1]])
                self.assertEqual(row['cases'][4:], expected)

    def test_unsummon_parent_removal_and_landing_defaults(self):
        data = load_contract_fixture(FIXTURE)
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data, engine_source=engine)), expected)

    def test_original_landing_defense_and_callback_order(self):
        data = load_contract_fixture(FIXTURE)
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        reference = data['contracts'][data['sources'][0]['contract']]
        selected = [[2, variant] for variant in (1, 2, 3, 4, 5, 9)]
        expected = [reference[data['cases'].index(case)] for case in selected]
        revisions = (7369, 7391, 7420, 7434, 7435, 7533)
        controls = dict(data, cases=selected, sources=[{'revision': build} for build in revisions])
        actual = json.loads(native_output(program(controls), controls, engine_source=engine))
        self.assertEqual([row['revision'] for row in actual['profiles']], list(revisions))
        for row in actual['profiles']:
            comparison = list(expected)
            if row['revision'] < 7435:
                # The original preliminary defense lookup used the live opponent.
                last = comparison[-1]
                comparison[-1] = dict(last, defenses=[[1, last['defenses'][0][1]]])
            with self.subTest(build=row['revision']):
                self.assertEqual(row['cases'], comparison)


if __name__ == '__main__':
    unittest.main()
