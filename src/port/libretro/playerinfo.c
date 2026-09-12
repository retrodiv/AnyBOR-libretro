/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/*
 * playerinfo.c — obor_get_player_state: active character + facing.
 *
 * Lives in its own translation unit because it needs the full openbor.h
 * (entity/model/player types); that header redefines printf and drags in
 * the whole engine surface, which the rest of the port layer avoids.
 * The field chain player[i].ent->model->name and ent->direction is stable
 * across every pinned era (verified 3400..8020).
 */
#include "openbor.h"
#include "obor_abi.h"

#include <string.h>

extern s_player player[];

int32_t obor_get_player_state(int32_t pl, char *name, int32_t cap,
                              int32_t *facing)
{
    if (facing)
        *facing = 1;
    if (name && cap > 0)
        name[0] = '\0';
    if (pl < 0 || pl >= OBOR_MAX_PLAYERS)
        return 0;
    if (!player[pl].ent || !player[pl].ent->model)
        return 0;
    if (name && cap > 0) {
        strncpy(name, player[pl].ent->model->name, (size_t)cap - 1);
        name[cap - 1] = '\0';
    }
    if (facing)
        *facing = player[pl].ent->direction ? 1 : 0;
    return 1;
}
