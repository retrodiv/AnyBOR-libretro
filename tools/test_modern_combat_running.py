"""Check profile-owned blockpain and running-state transitions.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_early_jump_walkoff import braced_statement
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-combat-running-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    parts = dict(FUNCTIONS='\n'.join(function(core, name) for name in (
        'check_blocking_pain', 'set_idle', 'set_fall')),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    for key in ('block_cases', 'idle_cases', 'fall_cases'):
        rows = []
        for row in data[key]:
            values = [str(value) for value in row]
            if any(re.fullmatch(r'-?[0-9]+|[A-Z][A-Z0-9_]*', v) is None for v in values):
                raise ValueError('Contract inputs must be literals or source constants')
            rows.append('{' + ','.join(values) + '}')
        parts[key.upper()] = ','.join(rows)
    code = Path(__file__).with_name('modern_combat_running_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved combat/running contract input')
    return code


class ModernCombatRunningContracts(unittest.TestCase):
    def test_original_entity_queries_after_death(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        code = r'''
#include "openbor.h"
#include <stdlib.h>

static entity dead, hidden, live;
static entity *actors[] = {&dead, &hidden, &live};
entity **ent_list = actors;
int ent_max = sizeof(actors) / sizeof(*actors);
uint32_t obor_profile_build;

@QUERIES@

int main(void)
{
    static const unsigned builds[] = {7369, 7391, 7420, 7487, 7488, 7489, 7533};
    dead.exists = 1;
    dead.death_state = DEATH_STATE_DEAD;
    hidden.modeldata.type = TYPE_ENEMY;
    live.exists = 1;
    live.modeldata.type = TYPE_ENEMY;

    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        dead.modeldata.type = TYPE_ENEMY;
        dead.death_state = DEATH_STATE_DEAD;
        if (findent(TYPE_ENEMY) != &dead || count_ents(TYPE_ENEMY) != 2)
        {
            abort();
        }

        dead.modeldata.type = obor_profile_type_none();
        const int types = TYPE_ENEMY | dead.modeldata.type;
        entity *first = obor_profile_build < 7488u ? &live : &dead;
        if (findent(types) != first ||
            count_ents(types) != (dead.modeldata.type ? 2 : 1))
        {
            abort();
        }

        if (obor_profile_build >= 7488u)
        {
            dead.modeldata.type = TYPE_ENEMY;
            dead.death_state |= DEATH_STATE_CORPSE;
            if (findent(TYPE_ENEMY) != &live ||
                count_ents(TYPE_ENEMY) != (obor_profile_build == 7488u ? 2 : 1))
            {
                abort();
            }
        }
    }
    return 0;
}
'''
        queries = '\n'.join(function(source, name) for name in ('findent', 'count_ents'))
        self.assertEqual(native_output(code.replace('@QUERIES@', queries), {'engine': '7533'},
                                       engine_source=engine), '')

    def test_original_combo_key_comparison(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        think = function(source, 'player_think')
        window = re.search(r'(const unsigned long delay = acting_player->inputtime[^;]+;)\s*if \(([^\n]+)\)', think)
        self.assertIsNotNone(window, 'Expected the backward attack input window')
        code = r'''
#include "openbor.h"
#undef assert
#include <assert.h>
#include <limits.h>

uint32_t obor_profile_build;

@MATCH_COMBO@

static int within_backward_attack_window(const s_player *acting_player)
{
    const int t = 0, t2 = 1;
    @DELAY@
    return @WINDOW@;
}

int main(void)
{
    static s_player player;
    static const unsigned builds[] = {7369, 7391, 7420, 7509, 7511, 7512, 7533};
    static const e_key_def back_attack[] = {FLAG_BACKWARD, FLAG_ATTACK};
    static const e_key_def forward_attack[] = {FLAG_FORWARD, FLAG_ATTACK};
    _Static_assert(RUN_STATE_NONE == 0, "Special moves must clear the running state");
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        player.combostep = 1;
        player.combokey[0] = FLAG_ATTACK | FLAG_JUMP;
        player.combokey[MAX_SPECIAL_INPUTS - 1] = FLAG_BACKWARD | FLAG_MOVELEFT;
        assert(match_combo(back_attack, &player, 2));
        assert(!match_combo(forward_attack, &player, 2));

        player.combokey[MAX_SPECIAL_INPUTS - 1] = FLAG_FORWARD | FLAG_MOVERIGHT;
        assert(match_combo(forward_attack, &player, 2));
        assert(!match_combo(back_attack, &player, 2));
        player.combokey[0] = FLAG_JUMP;
        assert(!match_combo(forward_attack, &player, 2));
    }

    static const unsigned window_builds[] = {7369, 7391, 7420, 7509, 7510, 7533};
    for (size_t i = 0; i < sizeof(window_builds) / sizeof(*window_builds); ++i)
    {
        obor_profile_build = window_builds[i];
        player.inputtime[1] = 100;
        player.inputtime[0] = 119;
        assert(within_backward_attack_window(&player));
        player.inputtime[0] = 120;
        assert(!within_backward_attack_window(&player));
        player.inputtime[1] = UINT32_MAX - 5;
        player.inputtime[0] = 3;
        assert(within_backward_attack_window(&player) == (window_builds[i] < 7510u || ULONG_MAX == UINT32_MAX));
    }
    return 0;
}
'''
        code = code.replace('@MATCH_COMBO@', function(source, 'match_combo'))
        code = code.replace('@DELAY@', window[1]).replace('@WINDOW@', window[2])
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_stalker_approach(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        code = r'''
#include "openbor.h"
#undef assert
#include <assert.h>

entity *self;
entity *stalker;
entity *firstplayer;
int stalking;
u32 _time;
static unsigned animation_updates;

void adjust_walk_animation(entity *actor)
{
    assert(actor == firstplayer);
    ++animation_updates;
}

@METHODS@

int main(void)
{
    static entity enemy;
    static entity target;
    static s_anim run = {.numframes = 1};
    static s_anim *animations[ANI_RUN + 1];
    self = &enemy;
    stalker = &enemy;
    firstplayer = &target;
    enemy.modeldata.animation = animations;
    enemy.modeldata.animation_capacity = sizeof(animations) / sizeof(*animations);
    enemy.modeldata.speed.x = 3;
    enemy.modeldata.runspeed = 5;
    enemy.position.x = 120;
    enemy.velocity.z = 7;
    target.position.x = 90;
    _time = 100;

    checkstalker();
    assert(stalking && enemy.running == RUN_STATE_NONE && animation_updates == 1);
    assert(enemy.velocity.x == -3 && enemy.velocity.z == 0 && enemy.stalltime == 220);
    _time = 219;
    checkstalker();
    assert(stalker == self && animation_updates == 1);
    _time = 220;
    checkstalker();
    assert(stalker == NULL && animation_updates == 1);

    animations[ANI_RUN] = &run;
    stalker = &enemy;
    stalking = 0;
    enemy.position.x = 30;
    target.position.x = 50;
    _time = 100;
    checkstalker();
    assert(stalking && enemy.running == RUN_STATE_START_X && animation_updates == 2);
    assert(enemy.velocity.x == 5 && enemy.velocity.z == 0 && enemy.stalltime == 168);
    firstplayer = NULL;
    checkstalker();
    assert(stalker == NULL && animation_updates == 2);
    return 0;
}
'''
        methods = ('diff', 'checkstalker')
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in methods))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_platform_and_wall_base_adjustment(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        code = Path(__file__).with_name('modern_legacy_base_adjustment_contract.c.in').read_text()
        code = code.replace('@ADJUST_BASE@', function(source, 'adjust_base'))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_bomb_projectile_states(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        routines = ('diff', 'inair', 'bomb_explode', 'bomb_try_detonate', 'bomb_move')
        attack = function(source, 'do_attack')
        contact = '\n'.join(braced_statement(attack, anchor) for anchor in (
            'if ((self->toexplode & obor_bomb_prepare_on_touch_flag())',
            'if (attacking_entity->toexplode & obor_bomb_prepare_on_touch_flag())'))
        spawn = function(source, 'bomb_spawn')
        preparation = re.search(r'(?m)^\s*ent->toexplode \|= .*?;', spawn)[0].strip()
        code = Path(__file__).with_name('modern_legacy_bomb_contract.c.in').read_text()
        code = code.replace('@ROUTINES@', '\n'.join(function(source, name) for name in routines))
        code = code.replace('@ATTACK_CONTACT@', contact).replace('@SPAWN_PREPARATION@', preparation)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_arrow_motion_and_homing_target(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        routines = ('diff', 'obor_profile_static_move_flags', 'faction_check_player_verses',
                    'faction_check_is_hostile', 'obor_target_is_hostile', 'homing_find_target', 'arrow_move')
        code = Path(__file__).with_name('modern_arrow_motion_contract.c.in').read_text()
        code = code.replace('@ROUTINES@', '\n'.join(function(source, name) for name in routines))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_ai_target_selection(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        routines = ('diff', 'get_type_from_string', 'get_type_from_arglist',
                    'faction_check_player_verses', 'faction_check_is_hostile',
                    'faction_check_can_damage', 'find_ent_here', 'normal_find_target',
                    'obor_target_is_hostile', 'obor_target_can_damage', 'common_try_grab',
                    'common_try_duckattack', 'ai_check_ducking', 'check_follow_up_condition',
                    'check_counter_condition', 'block_find_target', 'smart_bomb', 'faction_copy_data',
                    'obor_unspecified_type_mask', 'obor_init_model_faction',
                    'obor_type_mask_is_unspecified', 'obor_finish_model_faction', 'ent_copy_uninit')
        init = function(source, 'ent_default_init')
        start = init.index('/* Faction data. */')
        stop = init.index('if(!e->animation)', start)
        spawn = function(source, 'spawn')
        state_start = spawn.index('acting_entity->timestamp = _time;')
        state_stop = spawn.index('// copy back the value', state_start)
        self.assertLess(state_stop, spawn.index('ent_default_init(acting_entity);', state_stop))
        template = Path(__file__).with_name('modern_legacy_ai_target_contract.c.in').read_text()
        code = template.replace('@ROUTINES@', '\n'.join(function(source, name) for name in routines))
        code = code.replace('@SPAWN_FACTION@', init[start:stop])
        code = code.replace('@SPAWN_STATE@', spawn[state_start:state_stop])
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_owner_facing_and_movement_deadline_follow_original_revisions(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        move = function(source, 'common_move')
        first = move.index('        // temporary solution to turn off running')
        last = move.index('        //pick up the item if possible', first)
        routines = ('obor_npc_stall_deadline', 'obor_profile_static_move_flags',
                    'check_range_target_x', 'check_range_target_y', 'check_range_target_z',
                    'direction_get_adjustment_result')
        code = Path(__file__).with_name('modern_legacy_common_move_contract.c.in').read_text()
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in routines))
        code = code.replace('@STEER@', move[first:last])
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_legacy_npc_chase_and_follow(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        routines = ('diff', 'obor_profile_static_move_flags', 'check_range_target_x', 'check_range_target_z',
                    'common_try_chase', 'obor_legacy_try_follow', 'common_try_follow')
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"

uint32_t obor_profile_build;
s_videomodes videomodes = {.hRes = 320};
static int attack_count;
static int attack_choice = -1;

int pick_random_attack(entity *target, int testonly)
{
    if (target || testonly)
    {
        abort();
    }
    ++attack_count;
    return attack_choice;
}

@ROUTINES@

static void check(int pass, const char *label)
{
    if (!pass)
    {
        fprintf(stderr, "%u: %s\n", obor_profile_build, label);
        abort();
    }
}

static void initialize(entity *npc, s_anim **animations, int capacity)
{
    *npc = (entity){
        .direction = DIRECTION_RIGHT,
        .velocity = {.x = 8.f, .z = 9.f},
        .destx = 11.f,
        .destz = 12.f,
        .running = RUN_STATE_START_X,
        .modeldata = {
            .animation = animations, .animation_capacity = capacity,
            .speed = {.x = 4.f}, .runspeed = 10.f, .grabdistance = 20
        }
    };
}

int main(void)
{
    static const unsigned profiles[] = {7369, 7391, 7420, 7446, 7447, 7511, 7512, 7533};
    static entity npc, target;
    s_anim idle = {.numframes = 1, .range.x.min = 60};
    s_anim run = {.numframes = 1};
    s_anim *animations[] = {[ANI_IDLE] = &idle, [ANI_RUN] = &run};
    const int count = sizeof(animations) / sizeof(*animations);
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        const int legacy = profiles[i] < 7512;
        initialize(&npc, animations, count);
        target.position.x = 251;
        target.position.z = -101;
        npc.modeldata.runupdown = -2;
        attack_count = 0;
        check(common_try_chase(&npc, &target, true, true) == 1 && attack_count == 1,
              "Chase samples one attack range before choosing the path");
        check(npc.destx == 232.f && npc.destz == -101.f && npc.velocity.x == 10.f && npc.velocity.z == -5.f,
              "Chase destinations and signed speeds");
        check(npc.running == (legacy ? RUN_STATE_START_X : RUN_STATE_START_Z), "Chase with a running Z axis");

        npc.modeldata.runupdown = 0;
        check(common_try_chase(&npc, &target, true, true) == 1 && npc.running == RUN_STATE_START_X &&
              npc.velocity.z == -2.f, "Chase walking in Z preserves the X run");
        run.range.x.min = 200;
        run.range.x.max = 300;
        attack_choice = ANI_RUN;
        target.position.x = -230;
        check(common_try_chase(&npc, &target, true, false) == 1 && npc.destx == -151.f && npc.velocity.x == -10.f,
              "Chase attack midpoint is limited by screen width and reverses the X speed");
        attack_choice = -1;
        if (profiles[i] < 7447)
        {
            npc.modeldata.legacy_static_move_flags = MOVE_CONFIG_NO_MOVE;
        }
        else
        {
            npc.modeldata.move_config_flags = MOVE_CONFIG_NO_MOVE;
        }
        const int previous_attacks = attack_count;
        check(common_try_chase(&npc, &target, true, true) == 0 && npc.running == RUN_STATE_NONE &&
              attack_count == previous_attacks, "Immobile chase clears running and skips attack selection");
        npc.running = RUN_STATE_START_X;
        check(common_try_follow(&npc, &target, true, true) == 0 && npc.running == RUN_STATE_START_X,
              "Immobile follow preserves the last running state");

        initialize(&npc, animations, count);
        target.position.x = 59;
        target.position.z = 29;
        check(common_try_follow(&npc, &target, true, true) == legacy, "Follow configuration boundary");
        if (legacy)
        {
            check(npc.velocity.x == 0.f && npc.velocity.z == 0.f && npc.destx == 11.f &&
                  npc.destz == 12.f && npc.running == RUN_STATE_START_X, "Close target preserves destinations and run state");
            target.position.x = 60;
            target.position.z = -30;
            check(common_try_follow(&npc, &target, true, true) == 1 && npc.velocity.x == 4.f &&
                  npc.velocity.z == -2.f && npc.destx == 60.f && npc.destz == -30.f &&
                  npc.running == RUN_STATE_NONE, "Follow walks at the exact idle range boundary");

            target.position.x = 201;
            target.position.z = 31;
            check(common_try_follow(&npc, &target, true, true) == 1 && npc.velocity.x == 10.f &&
                  npc.velocity.z == 2.f && npc.running == RUN_STATE_NONE, "Follow Z walk clears the earlier X run");
            npc.modeldata.runupdown = -2;
            check(common_try_follow(&npc, &target, true, true) == 1 && npc.velocity.x == 10.f &&
                  npc.velocity.z == 5.f && npc.running == RUN_STATE_START_X, "Follow runs in Z based on X distance");
            target.position.x = 200;
            target.position.z = 300;
            check(common_try_follow(&npc, &target, false, true) == 1 && npc.velocity.x == 10.f &&
                  npc.destx == 201.f && npc.velocity.z == 2.f && npc.running == RUN_STATE_NONE,
                  "Long Z distance alone cannot start a run");
            target.position.x = -201;
            target.position.z = -300;
            check(common_try_follow(&npc, &target, true, true) == 1 && npc.velocity.x == -4.f &&
                  npc.velocity.z == -2.f && npc.running == RUN_STATE_NONE, "Facing away selects signed walking speed");
            idle.range.x.min = 0;
            target.position.x = 99;
            target.position.z = -49;
            check(common_try_follow(&npc, &target, true, true) == 1 && npc.velocity.x == 0.f &&
                  npc.velocity.z == 0.f, "Nonpositive idle range uses the original fallback");
            idle.range.x.min = 60;
        }
        else
        {
            s_child_follow follow = {.follow_offset.x = 25.f, .follow_range.x = {.min = -50, .max = 50},
                                     .follow_run_range.x = {.min = -100, .max = 100}};
            npc.modeldata.child_follow = &follow;
            npc.modeldata.run_config_flags = RUN_CONFIG_X_RIGHT_ENABLED | RUN_CONFIG_X_RIGHT_INITIAL;
            target.position.x = 201;
            target.position.z = 0;
            target.direction = DIRECTION_RIGHT;
            check(common_try_follow(&npc, &target, true, false) == 1 && npc.velocity.x == 10.f &&
                  npc.destx == 226.f && npc.running == RUN_STATE_START_X, "Typed follow honors target offset");
        }
    }
    return 0;
}
'''
        code = code.replace('@ROUTINES@', '\n'.join(function(source, name) for name in routines))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_legacy_model_changes_preserve_movement_flags(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text(encoding='latin1')
        basic = braced_statement(function(source, 'set_model_ex'),
                                 'if(!(newmodel->model_flag & MODEL_COPY_FLAG_NO_BASIC))')
        movement = basic[:basic.index('if(!newmodel->speed.x)')].rstrip() + '\n}'
        assign = function(source, 'ent_set_model')
        self.assertLess(assign.index('ent->modeldata = *m;'), assign.index('ent_copy_uninit(ent, &oldmodel);'))
        copy = function(source, 'ent_copy_uninit')
        actor_movement, = re.findall(r'(?m)^\s*(ent->modeldata\.move_config_flags = oldmodel->move_config_flags;)', copy)
        actor_attack = braced_statement(copy, 'if (ent->modeldata.aiattack == -1)')
        code = r'''
#include <stdint.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "openbor.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
static void inherit_movement(s_model *newmodel, const s_model *model)
{
    @MOVEMENT@
}

static void copy_actor_defaults(entity *ent, s_model *oldmodel)
{
    @ACTOR_MOVEMENT@
    @ACTOR_ATTACK@
}

int main(void)
{
    static const struct { uint32_t build; int inherits; } cases[] = {
        {7369, 0}, {7391, 0}, {7420, 0}, {7497, 0}, {7498, 1}, {7533, 1},
    };
    const e_move_config_flags old_flags = MOVE_CONFIG_SUBJECT_TO_WALL | MOVE_CONFIG_SUBJECT_TO_PLATFORM;
    const e_move_config_flags new_flags = MOVE_CONFIG_SUBJECT_TO_HOLE;
    s_model model = {.move_config_flags = old_flags, .aiattack = AIATTACK1_NOATTACK};
    static entity actor;
    for (size_t i = 0; i < sizeof(cases) / sizeof(*cases); ++i)
    {
        obor_profile_build = cases[i].build;
        s_model next = {.move_config_flags = new_flags, .aiattack = -1};
        inherit_movement(&next, &model);
        assert(next.move_config_flags == (cases[i].inherits ? old_flags : new_flags));
        actor.modeldata = next;
        copy_actor_defaults(&actor, &model);
        assert(actor.modeldata.move_config_flags == old_flags);
        assert(actor.modeldata.aiattack == AIATTACK1_NOATTACK);
        actor.modeldata.aiattack = AIATTACK1_ALWAYS;
        copy_actor_defaults(&actor, &model);
        assert(actor.modeldata.aiattack == AIATTACK1_ALWAYS);
        assert(next.move_config_flags == (cases[i].inherits ? old_flags : new_flags));
        next.move_config_flags = new_flags;
        next.model_flag = MODEL_COPY_FLAG_NO_BASIC;
        inherit_movement(&next, &model);
        assert(next.move_config_flags == new_flags && model.move_config_flags == old_flags);
    }
    puts("PASS");
}
'''
        code = (code.replace('@MOVEMENT@', movement).replace('@ACTOR_MOVEMENT@', actor_movement)
                .replace('@ACTOR_ATTACK@', actor_attack))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), 'PASS\n')

    def test_legacy_running_controls_and_landing(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        player = function(source, 'player_think')
        self.assertLess(player.index('    const e_run_state previous_run ='),
                        player.index('if(acting_player->playkeys & FLAG_MOVEUP)'))
        self.assertTrue('obor_stop_legacy_player_run(acting_entity, acting_player, previous_run);' in player)
        self.assertIn('run_try_runstop_player(acting_entity, acting_player);', player)
        up = player[player.index('if(acting_player->playkeys & FLAG_MOVEUP)'):]
        up = up[:up.index('else if(t && validanim(acting_entity, ANI_ATTACKUP))')]
        down = player[player.index('if(acting_player->playkeys & FLAG_MOVEDOWN)'):]
        down = down[:down.index('else if(t && validanim(acting_entity, ANI_ATTACKDOWN))')]
        horizontal = player[player.index('if((acting_player->playkeys & (FLAG_MOVELEFT | FLAG_MOVERIGHT)))'):]
        horizontal = horizontal[:horizontal.index('else if(t && validanim(acting_entity, ANI_ATTACKFORWARD))')]
        commands = '}\n'.join((up, down, horizontal)) + '}'
        landing = braced_statement(function(source, 'common_jump'),
                                   'if (obor_profile_build < 7529u ? !self->modeldata.legacy_runhold')
        inherited = braced_statement(function(source, 'set_model_ex'), 'if(!newmodel->runspeed)')
        modern_steer = function(source, 'common_move')
        steer = braced_statement(modern_steer, 'if (obor_uses_legacy_run_config())').rstrip()
        self.assertTrue(steer + '\n        else if (acting_entity->running & RUN_STATE_START_X)' in modern_steer)
        vertical = braced_statement(player, 'if(PLAYER_MIN_Z != PLAYER_MAX_Z && acting_entity->ducking == DUCK_NONE)')
        actions = re.search(r'typedef enum e_local_action_flags\s*\{[^}]+\} e_local_action_flags;', player)[0]
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"

uint32_t obor_profile_build;
@STOP@

static int match_combo(const e_key_def *sequence, s_player *player, size_t count)
{
    return count == 2 && sequence[0] == sequence[1] && (player->playkeys & sequence[0]);
}

static int available_animation;
#undef validanim
#define validanim(entity, animation) ((animation) == available_animation)
#undef PLAYER_MIN_Z
#undef PLAYER_MAX_Z
#define PLAYER_MIN_Z 0
#define PLAYER_MAX_Z 1
@ACTIONS@

static void start_run(entity *acting_entity, s_player *acting_player)
{
    const int notinair = 1;
    const int legacy_run = obor_uses_legacy_run_config();
    static const e_key_def sequence_up_up[] = {FLAG_MOVEUP, FLAG_MOVEUP};
    static const e_key_def sequence_down_down[] = {FLAG_MOVEDOWN, FLAG_MOVEDOWN};
    static const e_key_def sequence_left_left[] = {FLAG_MOVELEFT, FLAG_MOVELEFT};
    static const e_key_def sequence_right_right[] = {FLAG_MOVERIGHT, FLAG_MOVERIGHT};
    int t;
    @START@
}

static void land(entity *self)
{
    @LAND@
}

static e_local_action_flags apply_vertical_input(entity *acting_entity, s_player *acting_player)
{
    const int legacy_run = obor_uses_legacy_run_config();
    e_local_action_flags action = ACTION_NONE;
    @VERTICAL@
    return action;
}

static void inherit_running(s_model *newmodel, const s_model *model)
{
    @INHERIT@
}

static void apply_running_path(entity *acting_entity)
{
    @STEER@
}

static void check(int pass, const char *message)
{
    if (!pass)
    {
        fprintf(stderr, "%u: %s\n", obor_profile_build, message);
        abort();
    }
}

int main(void)
{
    static const unsigned revisions[] = {7369, 7391, 7420, 7502, 7503, 7511, 7512, 7528, 7529, 7533};
    for (size_t i = 0; i < sizeof(revisions) / sizeof(*revisions); ++i)
    {
        obor_profile_build = revisions[i];
        const int legacy = revisions[i] < 7512;
        static entity ent;
        ent = (entity){.direction = DIRECTION_RIGHT};
        s_player player = {.playkeys = FLAG_MOVERIGHT, .combostep = 2};
        available_animation = ANI_RUN;
        start_run(&ent, &player);
        check(ent.running == (legacy ? RUN_STATE_START_X : RUN_STATE_NONE), "Forward double tap without run flags");
        check(player.combostep == (legacy ? 1 : 2), "Forward double tap consumes the input");
        ent.running = RUN_STATE_NONE;
        ent.modeldata.facing = 1;
        player.playkeys = FLAG_MOVELEFT;
        available_animation = ANI_BACKRUN;
        start_run(&ent, &player);
        check(ent.running == RUN_STATE_START_X && player.playkeys == 0, "Backward double tap when facing is fixed");
        available_animation = ANI_RUN;
        for (int z = 0; z <= 7; ++z)
        {
            ent.modeldata.runupdown = z;
            player.playkeys = FLAG_MOVEDOWN;
            ent.running = RUN_STATE_NONE;
            start_run(&ent, &player);
            check(ent.running == (legacy && (z & 2) ? RUN_STATE_START_X : RUN_STATE_NONE),
                  "Original vertical double-tap bit");
        }
        if (legacy)
        {
            const int earlier_stop = revisions[i] < 7503;
            ent.modeldata.runupdown = 0;
            ent.velocity.x = 2.f;
            ent.running = RUN_STATE_START_X;
            player.keys = FLAG_MOVELEFT;
            obor_stop_legacy_player_run(&ent, &player, RUN_STATE_START_X);
            check(ent.running == (earlier_stop ? RUN_STATE_START_X : RUN_STATE_NONE),
                  "Horizontal-only reversal before sustained-run rewrite");
            ent.modeldata.runupdown = 6;
            ent.running = RUN_STATE_START_X;
            player.keys = FLAG_MOVEDOWN;
            obor_stop_legacy_player_run(&ent, &player, RUN_STATE_NONE);
            check(ent.running == (earlier_stop ? RUN_STATE_START_X : RUN_STATE_NONE),
                  "Solely vertical initiation before sustained-run rewrite");
            ent.running = RUN_STATE_START_X;
            ent.velocity.z = 2.f;
            player.keys = FLAG_MOVELEFT | FLAG_MOVERIGHT | FLAG_MOVEUP | FLAG_MOVEDOWN;
            obor_stop_legacy_player_run(&ent, &player, RUN_STATE_START_X);
            check(ent.running == RUN_STATE_NONE, "Opposing commands cancel on both axes");
            ent.running = RUN_STATE_START_X;
            player.keys = FLAG_MOVELEFT | FLAG_MOVEUP;
            obor_stop_legacy_player_run(&ent, &player, RUN_STATE_START_X);
            check(ent.running == RUN_STATE_NONE, "Reversed diagonal stops");
        }

        ent.running = RUN_STATE_START_X;
        ent.modeldata.runspeed = 4.f;
        ent.modeldata.run_config_flags = RUN_CONFIG_X_RIGHT_DASH_FIXED;
        player.keys = FLAG_MOVEUP;
        check(apply_vertical_input(&ent, &player) == ACTION_RUN && ent.velocity.z == (legacy ? -2.f : 0.f),
              "Original upward running velocity");
        player.keys = FLAG_MOVEDOWN;
        check(apply_vertical_input(&ent, &player) == ACTION_RUN && ent.velocity.z == (legacy ? 2.f : 0.f),
              "Original downward running velocity");

        ent.running = RUN_STATE_START_X;
        ent.modeldata.legacy_runhold = -2;
        land(&ent);
        check(ent.running == (revisions[i] < 7529 ? RUN_STATE_START_X : RUN_STATE_NONE),
              "Raw landing value and typed landing value are independent");
        ent.running = RUN_STATE_START_X;
        ent.modeldata.legacy_runhold = 0;
        ent.modeldata.run_config_flags = RUN_CONFIG_LAND;
        land(&ent);
        check(ent.running == (revisions[i] < 7529 ? RUN_STATE_NONE : RUN_STATE_START_X), "Typed landing control");

        s_model model = {.runspeed = 2.5f, .runupdown = -6, .legacy_runhold = -2}, inherited = {0};
        inherit_running(&inherited, &model);
        check(inherited.runspeed == model.runspeed && inherited.runupdown == (legacy ? -6 : 0)
              && inherited.legacy_runhold == (legacy ? -2 : 0), "Original model inheritance");
        ent.running = RUN_STATE_START_X;
        ent.modeldata.runupdown = 0;
        ent.position.z = 10.f;
        ent.velocity.z = 3.f;
        ent.destz = 22.f;
        apply_running_path(&ent);
        check(ent.velocity.z == (legacy ? 0.f : 3.f) && ent.destz == (legacy ? 10.f : 22.f),
              "Original horizontal running path when vertical movement is disabled");
    }
    return 0;
}
'''
        parts = {'STOP': function(source, 'obor_stop_legacy_player_run'), 'START': commands,
                 'LAND': landing, 'INHERIT': inherited, 'STEER': steer, 'VERTICAL': vertical, 'ACTIONS': actions}
        for key, value in parts.items():
            code = code.replace('@' + key + '@', value)
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_guarded_damage_at_7435_and_7442(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        records = re.findall(r'(?ms)^(?:static )?const s_defense (?:legacy_)?default_defense\s*=.*?^};', source)
        self.assertEqual(len(records), 2)
        methods = ('obor_profile_default_defense', 'defense_allocate_object', 'defense_find_current_object',
                   'defense_result_damage', 'obor_apply_guarded_hit')
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"
#undef calloc
#undef free

uint32_t obor_profile_build;
int max_attack_types = 1, nochipdeath;
s_global_config global_config;
entity *self;
@DEFENSE_RECORDS@
@METHODS@

static entity *callback_target;
static int calls;

static void check(int pass, const char *name)
{
    if (!pass)
    {
        fprintf(stderr, "%s for profile %u\n", name, obor_profile_build);
        abort();
    }
}

static int receive_damage(entity *source, s_attack *attack, int falling, s_defense *defense)
{
    check(self == callback_target && source != self && attack && !falling && defense, "Guarded hit callback context");
    ++calls;
    self->energy_state.health_current = 0;
    return 1;
}

struct result { int force, health, energy, callbacks; };

static void check_block(s_defense defense, int force, int hp, int mp, struct result expected, const char *name)
{
    entity source = {0}, target = {.takedamage = receive_damage};
    s_attack attack = {.attack_force = force, .attack_type = ATK_NORMAL};
    self = &source;
    callback_target = &target;
    calls = 0;
    target.energy_state.health_current = hp;
    target.energy_state.mp_current = mp;
    int applied = obor_apply_guarded_hit(&target, &source, &attack, &defense, force);
    check(applied == expected.force && target.energy_state.health_current == expected.health &&
          target.energy_state.mp_current == expected.energy && calls == expected.callbacks && self == &source, name);
}

int main(void)
{
    static const uint32_t profiles[] = {7369, 7391, 7420, 7434, 7435, 7441, 7442, 7533};
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        const int original = obor_profile_build < 7435;
        const int native_order = obor_profile_build < 7442;
        entity unused = {0};
        const s_defense *fallback = defense_find_current_object(&unused, NULL, ATK_NORMAL);
        s_defense *allocated = defense_allocate_object();
        check(fallback && allocated, "Native defense defaults");
        check(fallback->blockratio == (native_order ? 0.f : DEFENSE_BLOCKRATIO_COMPATABILITY_DEFAULT) &&
              fallback->blocktype == (native_order ? BLOCK_TYPE_MP_FIRST : BLOCK_TYPE_GLOBAL) &&
              allocated->blockratio == fallback->blockratio && allocated->blocktype == fallback->blocktype,
              "Fallback and allocated defense use the same profile values");
        free(allocated);

        global_config.block_ratio = 0;
        global_config.block_type = BLOCK_TYPE_GLOBAL;
        nochipdeath = 0;
        check_block(*fallback, 20, 30, 3,
                    original ? (struct result){20, 30, 3, 0}
                             : native_order ? (struct result){17, 13, 0, 0} : (struct result){0, 30, 3, 0},
                    "Guard with native defaults");
        s_defense defense = *fallback;
        defense.blockratio = 0.5f;
        defense.blocktype = 2;
        check_block(defense, 20, 30, 3,
                    original ? (struct result){10, 20, 0, 0}
                             : native_order ? (struct result){20, 10, 0, 0} : (struct result){0, 30, 0, 0},
                    "Native block mode two");
        defense.blocktype = 3;
        check_block(defense, 20, 30, 3,
                    native_order ? (struct result){0, 30, 0, 0} : (struct result){10, 20, 0, 0},
                    "Native block mode three");

        defense = *fallback;
        defense.blocktype = BLOCK_TYPE_HP;
        global_config.block_ratio = 1;
        global_config.block_type = BLOCK_TYPE_MP_FIRST;
        check_block(defense, 20, 30, 3,
                    original ? (struct result){2, 28, 0, 0}
                             : native_order ? (struct result){17, 13, 0, 0} : (struct result){5, 25, 3, 0},
                    "Global MP mode with a local health mode");
        global_config.block_ratio = 0;
        global_config.block_type = BLOCK_TYPE_GLOBAL;

        defense.blockratio = 1.f;
        defense.block_damage_adjust = 5;
        defense.block_damage_min = 2;
        defense.block_damage_max = 12;
        check_block(defense, 20, 30, 3,
                    original ? (struct result){20, 10, 3, 0}
                             : native_order ? (struct result){2, 28, 3, 0} : (struct result){12, 18, 3, 0},
                    "Guarded adjustment and ceiling policy");

        defense = *fallback;
        defense.blocktype = BLOCK_TYPE_HP;
        defense.blockratio = 1.f;
        nochipdeath = 1;
        check_block(defense, 8, 3, 0, (struct result){8, 1, 0, 0}, "Preserve one health point");
        nochipdeath = 0;
        check_block(defense, 8, 3, 0, (struct result){8, 0, 0, 1}, "Call damage when the guard is exhausted");
    }
    return 0;
}
'''
        code = code.replace('@DEFENSE_RECORDS@', '\n'.join(records))
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in methods))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_hit_factors_at_7435_boundary(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        defaults = re.search(r'(?ms)^const s_defense default_defense\s*=.*?^};', source)[0]
        methods = ('offense_result_damage', 'defense_result_damage', 'calculate_force_damage')
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"

uint32_t obor_profile_build;
int max_attack_types = 1;
s_global_config global_config;
@DEFAULT_DEFENSE@
@METHODS@

static void check(int actual, int expected, const char *case_name)
{
    if (actual != expected)
    {
        fprintf(stderr, "%s for profile %u gave %d, expected %d\n",
                case_name, obor_profile_build, actual, expected);
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
        s_offense offense = {.factor = 0.5f, .damage_adjust = 5, .damage_min = 0, .damage_max = 50};
        s_defense defense = {.factor = 2.0f, .damage_adjust = 3, .damage_min = 0, .damage_max = 50};
        s_defense fallback = {.factor = 3.0f, .damage_adjust = 1, .damage_min = 0, .damage_max = 50};
        s_attack attack = {.attack_force = 3, .attack_type = ATK_NORMAL};
        entity target = {.defense = &fallback};
        entity attacker = {.offense = &offense};
        global_config.cheats = 0;

        check(calculate_force_damage(&target, &attacker, &attack, &defense),
              earlier ? 2 : 15, "Apply each configured factor in sequence");
        check(calculate_force_damage(&target, &attacker, &attack, NULL),
              earlier ? 3 : 19, "Hit with the supplied defense omitted");
        attacker.offense = NULL;
        check(calculate_force_damage(&target, &attacker, &attack, &defense),
              earlier ? 6 : 9, "Hit with neutral offense");
        attacker.offense = &offense;
        attack.attack_type = max_attack_types;
        check(calculate_force_damage(&target, &attacker, &attack, &defense),
              earlier ? 6 : 9, "Defense factor at the final type boundary");
        attack.attack_type = max_attack_types + 1;
        check(calculate_force_damage(&target, &attacker, &attack, &defense),
              earlier ? 3 : 9, "No legacy defense factor above the type boundary");
        attack.attack_type = ATK_NORMAL;
        defense.damage_max = 9;
        check(calculate_force_damage(&target, &attacker, &attack, &defense),
              earlier ? 2 : 9, "Newer defense ceiling");
        defense.damage_max = 50;
        defense.damage_min = 18;
        check(calculate_force_damage(&target, &attacker, &attack, &defense),
              earlier ? 2 : 18, "Newer defense floor");
        defense.damage_min = 0;

        global_config.cheats = obor_profile_cheat_mask(CHEAT_OPTIONS_TOD_ACTIVE);
        attacker.modeldata.type = TYPE_PLAYER;
        target.energy_state.health_current = 9;
        check(calculate_force_damage(&target, &attacker, &attack, &defense),
              earlier ? 8 : 21, "Use the native cheat mask before applying factors");
        target.modeldata.guardpoints.max = 1;
        target.modeldata.guardpoints.current = 0;
        check(calculate_force_damage(&target, &attacker, &attack, &defense),
              0, "Guard point exhaustion");
    }
    return 0;
}
'''
        code = code.replace('@DEFAULT_DEFENSE@', defaults)
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in methods))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_wall_selection_at_7390_boundary(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"

uint32_t obor_profile_build;
s_level *level;
static unsigned lookups;
static int wall_index;

int checkwall_index(float x, float z)
{
    if(x != 11 || z != 7) abort();
    ++lookups;
    return wall_index;
}

@CHECK_BLOCK_WALL@

static void check(entity *actor, int expected, unsigned expected_lookups)
{
    lookups = 0;
    if(check_block_wall(actor) != expected || lookups != expected_lookups)
    {
        fprintf(stderr, "Unexpected wall selection for profile %u at height %.0f\n",
                obor_profile_build, (double)actor->position.y);
        abort();
    }
}

int main(void)
{
    static const uint32_t profiles[] = {7369, 7389, 7390, 7391, 7420, 7530, 7533};
    s_terrain walls[] = {{.height = 14}, {.height = 20}};
    s_level floor = {.walls = walls};
    entity actor = {.position = {.x = 11, .z = 7}};
    level = &floor;
    for(size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        wall_index = 1;
        actor.modeldata.move_config_flags = 0;
        check(&actor, WALL_INDEX_NONE, 0);
        actor.modeldata.move_config_flags = MOVE_CONFIG_SUBJECT_TO_WALL;
        actor.position.y = 19;
        check(&actor, 1, 1);
        const int at_or_above = obor_profile_build < 7390 ? 1 : WALL_INDEX_NONE;
        actor.position.y = 20;
        check(&actor, at_or_above, 1);
        actor.position.y = 21;
        check(&actor, at_or_above, 1);
        wall_index = WALL_INDEX_NONE;
        check(&actor, WALL_INDEX_NONE, 1);
    }
    return 0;
}
'''
        code = code.replace('@CHECK_BLOCK_WALL@', function(source, 'check_block_wall'))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_block_continuation_and_direction_at_7493(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        core = (engine / 'openbor.c').read_text()
        routines = ('common_block', 'check_blocking_eligible', 'check_blocking_decision', 'check_blocking_master')
        player = function(core, 'player_think')
        gate = re.search(r'(?ms)^        if\((validanim\(acting_entity, ANI_BLOCK\) && notinair.*?)\n        \{',
                         player)[1]
        self.assertTrue(gate.endswith(')'))
        code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#pragma GCC diagnostic ignored "-Wignored-qualifiers"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wdeprecated-non-prototype"
#endif
#include "scriptcommon.h"

uint32_t obor_profile_build;
entity *self;
s_player player[MAX_PLAYERS];
static entity actor, opponent;
static s_defense defense;
static int block_animations, idle_transitions;
static int random_calls;
static unsigned int random_bits;

static void check(int condition, const char *description)
{
    if (!condition)
    {
        fprintf(stderr, "%u: %s\n", obor_profile_build, description);
        abort();
    }
}

#undef validanim
#define validanim(ent, number) ((ent) == &actor && (number) == ANI_BLOCK)

void ent_set_anim(entity *ent, int number, int reset)
{
    check(ent == &actor && number == ANI_BLOCK && reset == 0, "Block animation parameters");
    ++block_animations;
    ent->animnum = number;
    ent->animating = ANIMATING_FORWARD;
}

int set_idle(entity *ent)
{
    check(ent == &actor, "Idle actor");
    ++idle_transitions;
    return 1;
}

s_defense *defense_find_current_object(entity *ent, s_body *body, e_attack_types type)
{
    check(ent == &actor && !body && type == ATK_NORMAL, "Attack defense arguments");
    return &defense;
}

int check_blocking_rules(entity *ent) { check(ent == &actor, "Block rules actor"); return 1; }
unsigned int rand32(void) { ++random_calls; return random_bits; }

@METHODS@

static int can_start_player_block(entity *acting_entity, int notinair)
{
    return @PLAYER_GATE@;
}

static void reset_actor(void)
{
    memset(&actor, 0, sizeof(actor));
    memset(&opponent, 0, sizeof(opponent));
    memset(&defense, 0, sizeof(defense));
    memset(player, 0, sizeof(player));
    actor.modeldata.type = TYPE_PLAYER;
    actor.blocking = 1;
    actor.animnum = ANI_BLOCK;
    actor.takeaction = common_block;
    self = &actor;
    block_animations = idle_transitions = 0;
}

static void check_continuation(int legacy)
{
    for (int value = -2; value <= 4; ++value)
    for (int pain = 0; pain <= 1; ++pain)
    for (int key = 0; key <= 1; ++key)
    {
        reset_actor();
        actor.modeldata.legacy_holdblock = value;
        actor.modeldata.block_config_flags = value == 2 ? BLOCK_CONFIG_HOLD_IMPACT | BLOCK_CONFIG_HOLD_INFINITE
            : (value == 1 ? BLOCK_CONFIG_HOLD_IMPACT : BLOCK_CONFIG_NONE);
        actor.inpain = pain ? IN_PAIN_BLOCK : IN_PAIN_NONE;
        player[0].keys = key ? FLAG_SPECIAL : 0;
        const int resume = pain && (legacy ? (value & 2) != 0 : value == 2);
        const int continued = !pain && key && (legacy ? value != 0 : value == 1 || value == 2);
        common_block();
        check(block_animations == resume, "Resume after block impact");
        check(idle_transitions == !(resume || continued), "Block release or continuation");
        check(!!actor.blocking == (resume || continued), "Retained blocking state");
        if (resume) check(actor.inpain == IN_PAIN_NONE, "Impact recovery state");
    }
}

static void check_direction_and_admission(int legacy)
{
    for (int value = -3; value <= 3; ++value)
    {
        reset_actor();
        s_attack attack = {.attack_type = ATK_NORMAL};
        actor.direction = opponent.direction = DIRECTION_LEFT;
        actor.modeldata.legacy_blockback = value;
        actor.modeldata.block_config_flags = value ? BLOCK_CONFIG_BACK : BLOCK_CONFIG_NONE;
        check(check_blocking_eligible(&actor, &opponent, &attack, NULL) == (value != 0), "Back-block decision");
        opponent.direction = DIRECTION_RIGHT;
        check(check_blocking_eligible(&actor, &opponent, &attack, NULL), "Front-block decision");
        actor.modeldata.block_config_flags |= BLOCK_CONFIG_DISABLED;
        check(check_blocking_master(&actor, &opponent, &attack, NULL) == legacy, "Disabled flag admission");
        check(can_start_player_block(&actor, 1) == legacy && !can_start_player_block(&actor, 0),
              "Player block key admission");
    }
}

static void check_active_blocking(void)
{
    for (int active = 0; active <= 1; ++active)
    for (int already_blocking = 0; already_blocking <= 1; ++already_blocking)
    {
        reset_actor();
        actor.modeldata.block_config_flags = active ? BLOCK_CONFIG_ACTIVE : BLOCK_CONFIG_NONE;
        actor.modeldata.blockodds = 1;
        actor.blocking = already_blocking;
        const int bypass = active && already_blocking;
        random_calls = 0;
        random_bits = 1;
        check(check_blocking_decision(&actor) == bypass && random_calls == !bypass, "Active block decision");
        random_calls = 0;
        random_bits = 0;
        check(check_blocking_decision(&actor) && random_calls == !bypass, "Random block decision");
    }
}

static void check_block_thresholds(int legacy)
{
    const struct { int model; int defense; int force; int earlier; int later; } cases[] = {
        { 10, 2, 2, 1, 0 },
        { 10, 2, 12, 0, 1 },
        { 10, 0, 9, 1, 0 },
        { 10, 0, 10, 0, 1 },
        { 0, 4, 3, 0, 0 },
        { 0, 4, 4, 1, 1 },
        { 4, -4, 4, 0, 1 },
    };
    for (size_t i = 0; i < sizeof(cases) / sizeof(*cases); ++i)
    {
        reset_actor();
        actor.direction = DIRECTION_LEFT;
        opponent.direction = DIRECTION_RIGHT;
        actor.modeldata.thold = cases[i].model;
        defense.blockthreshold = cases[i].defense;
        s_attack attack = {.attack_type = ATK_NORMAL, .attack_force = cases[i].force};
        const int eligible = legacy ? cases[i].earlier : cases[i].later;
        check(check_blocking_eligible(&actor, &opponent, &attack, NULL) == eligible,
              "Model and defense blocking thresholds");
    }
}

int main(void)
{
    static const unsigned profiles[] = {7369, 7391, 7420, 7442, 7443, 7492, 7493, 7530, 7533};
    for (size_t i = 0; i < sizeof(profiles) / sizeof(*profiles); ++i)
    {
        obor_profile_build = profiles[i];
        const int legacy = profiles[i] < 7493;
        check_continuation(legacy);
        check_direction_and_admission(legacy);
        check_active_blocking();
        check_block_thresholds(profiles[i] < 7443u);
    }
    return 0;
}
'''
        code = (code.replace('@METHODS@', '\n'.join(function(core, name) for name in routines))
                .replace('@PLAYER_GATE@', gate[:-1]))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_blockpain_animation_at_7497_boundary(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        core = (engine / 'openbor.c').read_text()
        code = r'''
#include <stdint.h>
#include <stdlib.h>
#include "openbor.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
static entity defender, current;
entity *self = &current;
static int reaction;

int set_blockpain(entity *actor, int type, int reset)
{
    assert(actor == &current && type == ATK_NORMAL && reset == 1);
    reaction = 1;
    return 1;
}

void ent_set_anim(entity *actor, int animation, int reset)
{
    assert(actor == &defender && animation == ANI_BLOCK && reset == 0);
    reaction = 0;
}

@BLOCKING@

int main(void)
{
    static const unsigned builds[] = {7369, 7391, 7420, 7496, 7497, 7533, 7575, 7576};
    static const struct
    {
        int threshold, force, early, middle, later;
    } hits[] = {
        {10, 9, 0, 1, 0}, {10, 10, 1, 0, 1}, {10, 11, 1, 0, 1},
        {0, -1, 0, 1, 0}, {0, 0, 0, 0, 1}, {0, 1, 0, 0, 1},
        {-5, -6, 0, 1, 0}, {-5, -5, 1, 0, 1}, {-5, -4, 1, 0, 1}
    };
    defender.modeldata.blockpain = 99;
    for (size_t p = 0; p < sizeof(builds) / sizeof(*builds); ++p)
    {
        obor_profile_build = builds[p];
        for (size_t i = 0; i < sizeof(hits) / sizeof(*hits); ++i)
        {
            current.modeldata.blockpain = hits[i].threshold;
            s_attack hit = {.attack_type = ATK_NORMAL, .attack_force = hits[i].force};
            int expected = builds[p] < 7497u ? hits[i].early
                         : builds[p] < 7576u ? hits[i].middle : hits[i].later;
            reaction = -1;
            set_blocking_animation(&defender, &hit);
            assert(reaction == expected);
        }
    }
    return 0;
}
'''
        functions = '\n'.join(function(core, name) for name in
                              ('check_blocking_pain', 'set_blocking_animation'))
        self.assertEqual(native_output(code.replace('@BLOCKING@', functions),
                                       {'engine': '7533'}, engine_source=engine), '')

    def test_blockpain_and_running_callback_order(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(
            revision=row['revision'], **data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)

    def test_7612_landing_damage_health_cheat_scope(self):
        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        gravity = function(source, 'check_gravity')
        gate = re.search(r'\bif\((obor_profile_build < 7557[^{};]*)\)\s*\{\s*checkdamageonlanding\(self\);',
                         gravity)
        self.assertIsNotNone(gate)
        code = r'''
#include "openbor.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
s_global_config global_config;

static int landing_takes_damage(entity *self)
{
    return @GATE@;
}

int main(void)
{
    static entity actor;
    static const uint32_t profiles[] = {7610, 7611, 7612};
    static const unsigned types[] = {TYPE_PLAYER, TYPE_ENEMY, TYPE_PLAYER | TYPE_ENEMY};
    for (size_t revision = 0; revision < sizeof(profiles) / sizeof(*profiles); ++revision)
    {
        obor_profile_build = profiles[revision];
        for (size_t type = 0; type < sizeof(types) / sizeof(*types); ++type)
        {
            actor.modeldata.type = types[type];
            global_config.cheats = 0;
            assert(landing_takes_damage(&actor));
            global_config.cheats = CHEAT_OPTIONS_HEALTH_ACTIVE;
            const int expected = profiles[revision] >= 7611 && !(types[type] & TYPE_PLAYER);
            assert(landing_takes_damage(&actor) == expected);
        }
    }
    return 0;
}
'''
        self.assertEqual(native_output(code.replace('@GATE@', gate[1]), data, engine_source=engine), '')


if __name__ == '__main__':
    unittest.main()
