/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_ATTACK_QUERY_H
#define OBOR_ATTACK_QUERY_H

#include <stdint.h>

/* The public handle comes from an animation's attack-frame table. Keep its
 * actual allocation capacity separate from the script-editable frame count.
 * Aligned aliases into the same table retain their native indexing behavior. */
static int obor_attack_frame_is_valid(const void *table, int frame)
{
    const s_anim_list *node;
    uintptr_t address = (uintptr_t)table;
    if(!table || frame < 0) return 0;
    for(node = anim_list; node; node = node->next)
    {
        const s_anim *animation = node->anim;
        uintptr_t first, displacement;
        size_t slot, capacity, element;
        if(!animation || !animation->collision_attack) continue;
        capacity = animation->obor_attack_frame_capacity;
        element = sizeof(*animation->collision_attack);
        if(!capacity || capacity > SIZE_MAX / element) continue;
        first = (uintptr_t)animation->collision_attack;
        if(address < first) continue;
        displacement = address - first;
        if(displacement % element) continue;
        slot = displacement / element;
        if(slot < capacity && (size_t)frame < capacity - slot) return 1;
    }
    return 0;
}

#endif
