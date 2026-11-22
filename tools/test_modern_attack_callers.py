"""Check default attack payloads in item, enemy and time-over callers.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-attack-caller-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    default = re.search(r'(?ms)^const s_attack emptyattack\s*=\s*\{.*?^\};', core)
    velocity = re.search(r'(?ms)^s_axis_principal_float default_model_dropv\s*=\s*\{.*?^\};', core)
    if default is None or velocity is None:
        raise ValueError('Complete default attack and velocity required')
    parts = dict(DEFAULT=default[0], VELOCITY=velocity[0],
        FUNCTIONS='\n'.join(function(core, name) for name in (
            'do_item_script', 'kill_all_enemies', 'kill_all_players_by_timeover')),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=','.join('{' + ','.join(str(v) for v in row) + '}' for row in data['cases']))
    code = Path(__file__).with_name('modern_attack_callers_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved attack caller input')
    return code


class ModernAttackCallerContracts(unittest.TestCase):
    def test_original_animation_attack_range(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        methods = tuple(f'check_range_target_{axis}' for axis in ('x', 'y', 'z', 'base', 'all'))
        prepare = function(source, 'normal_prepare')
        for attack in ('ANI_THROWATTACK', 'animspecials[i]', 'animattacks[i]'):
            self.assertIn(f'check_range_target_all(self, target, {attack}, 0, 0)', prepare)
        code = r'''
#include "openbor.h"
#undef assert
#include <assert.h>

@METHODS@

int main(void)
{
    static entity actor;
    static entity target;
    static s_anim animation;
    s_anim *animations[] = {&animation};
    actor.modeldata.animation = animations;
    animation.range.x = (s_metric_range){.min = 3, .max = 8};
    animation.range.y = (s_metric_range){.min = 1, .max = 2};
    animation.range.z = (s_metric_range){.min = -2, .max = -1};
    animation.range.base = (s_metric_range){.min = 2, .max = 4};

    actor.position.x = 10.9f;
    actor.position.y = 1.9f;
    actor.position.z = 8.1f;
    actor.base = 3.9f;
    target.position.x = 13.1f;
    target.position.y = 2.1f;
    target.position.z = 7.9f;
    target.base = 5.1f;

    actor.direction = DIRECTION_RIGHT;
    assert(check_range_target_all(&actor, &target, 0, 0, 0));
    target.position.x = 18.9f;
    assert(check_range_target_all(&actor, &target, 0, 0, 0));
    target.position.x = 19.0f;
    assert(!check_range_target_all(&actor, &target, 0, 0, 0));

    actor.direction = DIRECTION_LEFT;
    target.position.x = 2.1f;
    assert(check_range_target_all(&actor, &target, 0, 0, 0));
    target.position.x = 7.9f;
    assert(check_range_target_all(&actor, &target, 0, 0, 0));
    target.position.x = 8.0f;
    assert(!check_range_target_all(&actor, &target, 0, 0, 0));

    target.position.x = 5.0f;
    target.position.y = 1.99f;
    assert(!check_range_target_all(&actor, &target, 0, 0, 0));
    target.position.y = 2.0f;
    target.position.z = 8.0f;
    assert(!check_range_target_all(&actor, &target, 0, 0, 0));
    target.position.z = 7.9f;
    target.base = 8.0f;
    assert(!check_range_target_all(&actor, &target, 0, 0, 0));
    target.base = 7.9f;
    assert(check_range_target_all(&actor, &target, 0, 0, 0));
    assert(!check_range_target_all(&actor, NULL, 0, 0, 0));
    return 0;
}
'''
        code = code.replace('@METHODS@', '\n'.join(function(source, name) for name in methods))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_hit_impact_playback(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        self.assertIn('play_hit_impact_sound(attack, attacking_entity, didblock);', function(source, 'do_attack'))
        code = r'''
#include <stdint.h>
#include "openbor.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
s_global_sample global_sample_list;
s_savedata savedata;
int noslowfx;
static int sound_calls;
static int played_sample;
static unsigned played_speed;

int sound_play_sample(int sample, unsigned priority, int left, int right, unsigned speed)
{
    assert(priority == 0 && left == 37 && right == 37);
    ++sound_calls;
    played_sample = sample;
    played_speed = speed;
    return 0;
}

@IMPACT@

static void check_impact(s_attack *attack, entity *actor, int blocked, int sample, unsigned speed)
{
    sound_calls = 0;
    assert(play_hit_impact_sound(attack, actor, blocked) == sample);
    assert(sound_calls == (speed != 0));
    if (speed != 0)
    {
        assert(played_sample == sample && played_speed == speed);
    }
}

int main(void)
{
    const unsigned builds[] = {7369, 7391, 7420, 7444, 7445, 7533};
    savedata.effectvol = 37;
    static entity actor;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        const int legacy = builds[i] < 7445u;
        const unsigned special_speed = legacy ? 0 : 100;
        s_attack attack = {.blocksound = 4, .hitsound = 11, .attack_force = 12};
        global_sample_list.block = 7;
        global_sample_list.indirect = 8;
        noslowfx = 0;

        actor.projectile = BLAST_NONE;
        check_impact(&attack, &actor, 1, 4, special_speed);
        attack.blocksound = SAMPLE_ID_NONE;
        check_impact(&attack, &actor, 1, 7, special_speed);
        global_sample_list.block = SAMPLE_ID_NONE;
        check_impact(&attack, &actor, 1, SAMPLE_ID_NONE, 0);
        check_impact(&attack, &actor, 0, 11, 93);

        actor.projectile = BLAST_ATTACK;
        check_impact(&attack, &actor, 0, 8, special_speed);
        actor.projectile = BLAST_TOSS;
        check_impact(&attack, &actor, 0, legacy ? 11 : 8, legacy ? 93 : 100);
        global_sample_list.indirect = SAMPLE_ID_NONE;
        check_impact(&attack, &actor, 0, 11, 93);

        attack.attack_force = 100;
        check_impact(&attack, &actor, 0, 11, 60);
        noslowfx = 1;
        check_impact(&attack, &actor, 0, 11, 100);
        attack.hitsound = SAMPLE_ID_NONE;
        check_impact(&attack, &actor, 0, SAMPLE_ID_NONE, 0);
    }
    return 0;
}
'''
        code = code.replace('@IMPACT@', function(source, 'play_hit_impact_sound'))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_original_contact_item_type_selection(self):
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/7533'))
        source = (engine / 'openbor.c').read_text()
        functions = ('diff', 'isItem', 'isSubtypeTouch', 'isSubtypeWeapon', 'isSubtypeProjectile',
                     'faction_check_player_verses', 'faction_check_can_damage', 'obor_item_contact_can_damage',
                     'normal_test_item', 'test_item', 'player_test_touch')
        code = r'''
#include <stdint.h>
#include "openbor.h"
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
s_savedata savedata;
s_level *level;
s_videomodes videomodes = {.hRes = 320};

@FUNCTIONS@

static void check_pickup(entity *collector, entity *item, int expected)
{
    assert(normal_test_item(collector, item) == expected);
    assert(test_item(collector, item) == expected);
    assert(player_test_touch(collector, item) == expected);
}

int main(void)
{
    const unsigned builds[] = {7369, 7391, 7420, 7443, 7444, 7533};
    static entity collector, item;
    static int vulnerable = 1;
    static s_anim item_animation = {.numframes = 1, .vulnerable = &vulnerable};
    static s_anim pickup_animation = {.numframes = 1};
    static s_anim *collector_animations[MAX_ANIS];
    collector.modeldata.animation = collector_animations;
    collector.modeldata.animation_capacity = MAX_ANIS;
    collector.modeldata.health = 5;
    collector.energy_state.health_current = 1;
    item.modeldata.type = TYPE_ITEM;
    item.modeldata.subtype = SUBTYPE_TOUCH;
    item.energy_state.health_current = 1;
    item.animation = &item_animation;
    item.faction.damage_direct = FACTION_GROUP_TYPE_EXCLUSIVE;
    item.faction.damage_indirect = FACTION_GROUP_TYPE_EXCLUSIVE;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        const int legacy = builds[i] < 7444;
        collector_animations[ANI_GET] = NULL;
        collector.modeldata.type = TYPE_PLAYER | TYPE_NPC;
        item.faction.type_damage_direct = TYPE_PLAYER;
        check_pickup(&collector, &item, !legacy);

        item.faction.type_damage_direct = TYPE_PLAYER | TYPE_NPC;
        check_pickup(&collector, &item, 1);

        collector.modeldata.type = TYPE_PLAYER;
        item.projectile = BLAST_ATTACK;
        item.faction.type_damage_direct = TYPE_NPC;
        item.faction.type_damage_indirect = TYPE_PLAYER;
        check_pickup(&collector, &item, 0);

        collector.modeldata.type = TYPE_UNDELCARED;
        item.faction.type_damage_direct = TYPE_UNDELCARED;
        check_pickup(&collector, &item, legacy);

        collector.modeldata.type = TYPE_PLAYER;
        collector_animations[ANI_GET] = &pickup_animation;
        check_pickup(&collector, &item, 1);
    }
    return 0;
}
'''
        code = code.replace('@FUNCTIONS@', '\n'.join(function(source, name) for name in functions))
        self.assertEqual(native_output(code, {'engine': '7533'}, engine_source=engine), '')

    def test_item_enemy_and_timeover_defaults_and_reuse(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
