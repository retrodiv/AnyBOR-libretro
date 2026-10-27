/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Actual native entity arrays and extracted common_dot implementation.
 * MP-only ticks exercise slot bounds without replacing combat calculations. */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef assert
#undef malloc
#undef calloc
#undef realloc
#undef free
#define assert(condition) do { if (!(condition)) abort(); } while (0)

entity *self;
u32 time;
uint32_t obor_profile_build;
#ifdef DOT_HAS_PROFILE_COMBAT
/* The MP-only contract never exercises these HP providers. Retain the
 * complete native helpers and supply their inactive scalar dependencies. */
const s_defense default_defense = {0};
int max_attack_types;
#endif
#ifndef DOT_ATTACK_TYPE
#define DOT_ATTACK_TYPE s_attack
#endif
const DOT_ATTACK_TYPE emptyattack = {0};
__typeof__(((DOT_ATTACK_TYPE *)0)->dropv) default_model_dropv;
static int damage_scripts;
#ifndef DOT_MP_MODE
#define DOT_MP_MODE 2
#endif

void kill(entity *victim)
{
    (void)victim;
    abort();
}

void execute_takedamage_script(entity *ent, entity *other, int force,
                              int drop, int type, int noblock,
                              int guardcost, int jugglecost, int pauseadd
#ifdef DOT_SCRIPT_HAS_TAG
                              , int tag
#endif
                              )
{
    (void)ent; (void)other; (void)force; (void)drop; (void)type;
    (void)noblock; (void)guardcost; (void)jugglecost; (void)pauseadd;
#ifdef DOT_SCRIPT_HAS_TAG
    (void)tag;
#endif
    ++damage_scripts;
}

#include "common_dot.inc"

int main(int argc, char **argv)
{
    int i, last = MAX_DOTS - 1;
    assert(argc == 2);
    obor_profile_build = (uint32_t)strtoul(argv[1], NULL, 10);
    assert(MAX_DOTS > 1);
    self = calloc(1, sizeof(*self));
    assert(self);
    self->health = 100;
    self->mp = 50;
    time = 2;
    for (i = 0; i < MAX_DOTS; ++i) {
        self->dot_time[i] = 1;
        self->dot[i] = DOT_MP_MODE;
        self->dot_cnt[i] = 0;
        self->dot_rate[i] = 100;
        self->dot_force[i] = 7;
        self->dot_atk[i] = 1;
    }
    self->dot_time[last] = 4;
    common_dot();
    assert(self->health == 100 && self->mp == 43 && !damage_scripts);
    assert(self->dot_time[last] == 4 && self->dot[last] == DOT_MP_MODE);
    assert(self->dot_cnt[last] == 2 + GAME_SPEED);
    for (i = 0; i < last; ++i) {
        assert(!self->dot_time[i] && !self->dot[i] && !self->dot_cnt[i]);
        assert(!self->dot_rate[i] && !self->dot_force[i] && !self->dot_atk[i]);
    }
    common_dot();
    assert(self->mp == 43 && !damage_scripts);
    time = 5;
    common_dot();
    for (i = 0; i < MAX_DOTS; ++i) {
        assert(!self->dot_time[i] && !self->dot[i] && !self->dot_cnt[i]);
        assert(!self->dot_rate[i] && !self->dot_force[i] && !self->dot_atk[i]);
    }
    common_dot();
    assert(self->health == 100 && self->mp == 43 && !damage_scripts);
    free(self);
    puts("{\"status\":\"PASS\",\"contracts\":4}");
    return 0;
}
