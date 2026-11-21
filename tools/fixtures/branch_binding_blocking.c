/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */

#include "openbor.h"
#include <assert.h>

uint32_t obor_profile_build;

void execute_on_bind_update_other_to_self(entity *ent, entity *other, s_bind *bind)
{
    assert(bind->ent == ent && other != ent);
}

void execute_on_bind_update_self_to_other(entity *ent, entity *other, s_bind *bind)
{
    assert(bind->ent == other && ent != other);
}

void ent_set_anim(entity *ent, int animation, int reset)
{
    (void)ent;
    (void)animation;
    (void)reset;
    assert(0);
}

void update_frame(entity *ent, unsigned frame)
{
    (void)ent;
    (void)frame;
    assert(0);
}

void kill_entity(entity *ent)
{
    (void)ent;
    assert(0);
}

@METHODS@

int main(void)
{
    const unsigned profiles[] = {6997, 7039, 7086, 7091, 7123, 7142};
    const e_direction directions[] = {DIRECTION_LEFT, DIRECTION_RIGHT};
    for(size_t p = 0; p < sizeof(profiles) / sizeof(profiles[0]); ++p)
    {
        obor_profile_build = profiles[p];
        const int early = profiles[p] == 6997 || profiles[p] == 7039;
        entity actor = {0};
        entity target = {0};
        target.position.x = 200;
        actor.binding.ent = &target;
        actor.binding.offset.x = 12;

        for(size_t i = 0; i < sizeof(directions) / sizeof(directions[0]); ++i)
        {
            target.direction = directions[i];
            const int relative_offset = directions[i] == DIRECTION_LEFT ? -12 : 12;
            actor.position.x = 100;
            actor.binding.positioning.x = BIND_MODE_NONE;
            adjust_bind(&actor);
            assert(actor.position.x == 100);
            actor.binding.positioning.x = BIND_MODE_TARGET;
            adjust_bind(&actor);
            assert(actor.position.x == 200 + relative_offset);
            actor.binding.positioning.x = BIND_MODE_LEVEL;
            adjust_bind(&actor);
            assert(actor.position.x == (early ? relative_offset : 12));
        }

        s_defense defenses[1] = {{0}};
        s_collision_attack attack = {0};
        actor.defense = defenses;
        actor.direction = DIRECTION_RIGHT;
        target.direction = DIRECTION_LEFT;
        for(int power = 0; power <= 3; ++power)
        {
            defenses[0].blockpower = power;
            for(int break_power = 0; break_power <= 3; ++break_power)
            {
                attack.no_block = break_power;
                const int checked = power || (!early && break_power);
                assert(check_blocking_eligible(&actor, &target, &attack) ==
                       (!checked || break_power < power));
            }
        }
    }
}
