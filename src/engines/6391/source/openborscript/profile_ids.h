/* AnyBOR modification record: 2026-10-05.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Map native logical-profile animation, attack, subtype and spawn IDs to the
 * shared engine selectors. Preserve the 5134 and 6119 animation ID sequence
 * and first dynamic IDs. Preserve their animation property numbering before
 * the entity collision selector. Translate the original time-over and custom
 * attack numbers for those profiles. Restore their native subtype numbering
 * around boomerang. Translate their original projectile request flag order.
 * Translate their original typed level property indices.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/6391.md
 * at the source repository root. Original notices follow below.
 */

/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */
/* Shared internal selectors, native logical-profile script IDs. */
#ifndef OBOR_PROFILE_IDS_H
#define OBOR_PROFILE_IDS_H
#include <limits.h>

/* Before the back-block animations, the original fixed table placed the
 * two boomerang animations between the back-rise and edge families. */
static inline int obor_mid_classic_animation_count(void)
{
    if(obor_profile_build < 6283 || obor_profile_build >= 6303) return 0;
    if(obor_profile_build < 6292) return 2;
    if(obor_profile_build < 6295) return 4;
    if(obor_profile_build < 6301) return 6;
    return 8;
}

static inline int obor_mid_classic_animation_from_native(int id, int tail_count)
{
    const int first_catch = ANI_BACKBLOCKPAINB - 2;
    const int first_dynamic = first_catch + tail_count;
    const int dynamic_offset = MAX_ANIS - first_dynamic;
    if(id < ANI_BACKBURNDIE) return id;
    if(id < first_catch) return id + 2;
    if(id < first_catch + 2) return ANI_GETBOOMERANG + id - first_catch;
    if(id >= first_dynamic) return id <= INT_MAX - dynamic_offset ? id + dynamic_offset : -1;

    const int animation = ANI_EDGE + id - first_catch - 2;
    return animation == ANI_FALLLOSE ? ANI_LOSE : animation;
}

static inline int obor_mid_classic_animation_to_native(int id, int tail_count)
{
    const int first_catch = ANI_BACKBLOCKPAINB - 2;
    const int first_dynamic = first_catch + tail_count;
    if(id < ANI_BACKBURNDIE) return id;
    if(id >= ANI_BACKRISEB && id <= ANI_BACKRISEATTACK10) return id - 2;
    if(id >= ANI_GETBOOMERANG && id <= ANI_GETBOOMERANGINAIR) return first_catch + id - ANI_GETBOOMERANG;
    if(id >= MAX_ANIS) return id - (MAX_ANIS - first_dynamic);
    if(id == ANI_LOSE && tail_count == 8) return first_dynamic - 1;
    if(id >= ANI_EDGE && id <= ANI_VICTORY && id - ANI_EDGE < tail_count - 2)
        return first_catch + 2 + id - ANI_EDGE;
    return -1;
}

static inline int obor_animation_from_native(int id)
{
    int original_max = ANI_GETBOOMERANG;
    if(id < 0) return id;
    const int middle_tail = obor_mid_classic_animation_count();
    if(middle_tail) return obor_mid_classic_animation_from_native(id, middle_tail);
    if(obor_profile_build >= 6303 && obor_profile_build < 6345)
    {
        if(id == ANI_EDGE) return ANI_GETBOOMERANG;
        if(id == ANI_EDGE + 1) return ANI_GETBOOMERANGINAIR;
        if(obor_profile_build < 6306 && id >= ANI_FALLLOSE + 2)
        {
            if(id == ANI_FALLLOSE + 2) return ANI_LOSE;
            return id < INT_MAX ? id + 1 : -1;
        }
        if(id >= ANI_EDGE + 2 && id < MAX_ANIS) return id - 2;
        return id;
    }
    if(obor_profile_build == 5134 || (obor_profile_build >= 6119 && obor_profile_build < 6283))
    {
        const int offset = ANI_GETBOOMERANG - ANI_BACKRUN - 1;
        if(id <= ANI_BACKRUN) return id;
        return id <= INT_MAX - offset ? id + offset : -1;
    }
    if(obor_profile_build == 6510)
    {
        if(id == 0) return ANI_NONE;
        return id < original_max + 1 ? id - 1 : id < INT_MAX ? id + 1 : -1;
    }
    return id < original_max ? id : id <= INT_MAX - 2 ? id + 2 : -1;
}
static inline int obor_animation_to_native(int id)
{
    int original_max = ANI_GETBOOMERANG;
    const int middle_tail = obor_mid_classic_animation_count();
    if(middle_tail) return obor_mid_classic_animation_to_native(id, middle_tail);
    if(obor_profile_build >= 6303 && obor_profile_build < 6345)
    {
        if(id == ANI_GETBOOMERANG) return ANI_EDGE;
        if(id == ANI_GETBOOMERANGINAIR) return ANI_EDGE + 1;
        if(obor_profile_build < 6306)
        {
            if(id == ANI_FALLLOSE) return -1;
            if(id == ANI_LOSE) return id + 1;
            if(id >= MAX_ANIS) return id - 1;
        }
        if(id >= ANI_EDGE && id < original_max) return id + 2;
        return id;
    }
    if(obor_profile_build == 5134 || (obor_profile_build >= 6119 && obor_profile_build < 6283))
    {
        const int offset = ANI_GETBOOMERANG - ANI_BACKRUN - 1;
        if(id <= ANI_BACKRUN) return id;
        return id >= ANI_GETBOOMERANG ? id - offset : -1;
    }
    if(obor_profile_build == 6510)
    {
        if(id == ANI_NONE) return 0;
        return id < original_max ? id + 1 : id - 1;
    }
    return id < original_max ? id : id - 2;
}
enum
{
    PLAYER_NO_STATUS,
    PLAYER_LOOSING,
    PLAYER_WINNING
};

static inline int obor_profile_has_player_status(void)
{
    return obor_profile_build >= 6301 && obor_profile_build < 6305;
}

static inline int obor_profile_has_player_status_property(void)
{
    return obor_profile_build >= 6302 && obor_profile_has_player_status();
}

static inline int obor_profile_uses_5134_script_ids(void)
{
    return obor_profile_build == 5134 || obor_profile_build == 6119;
}

static inline int obor_profile_uses_legacy_path_sizes(void)
{
    return obor_profile_build && obor_profile_build < 6205;
}

static inline int obor_profile_uses_early_summon_damage_type(void)
{
    return obor_profile_build && obor_profile_build < 6304;
}

static inline int obor_profile_has_checkbase(void)
{
    return !obor_profile_build || obor_profile_build >= 6316;
}

static inline int obor_profile_has_boss_counters(void)
{
    return !obor_profile_build || obor_profile_build >= 6318;
}

static inline int obor_profile_has_obstacle_plane(void)
{
    return !obor_profile_build || obor_profile_build >= 6272;
}

static inline int obor_profile_has_lose_attack(void)
{
    return !obor_profile_uses_5134_script_ids() &&
           (obor_profile_build < 6175 || obor_profile_build >= 6310);
}

static inline int obor_profile_has_lose_attack_slot(void)
{
    return !obor_profile_uses_5134_script_ids() &&
           (obor_profile_build < 6175 || obor_profile_build >= 6303);
}

static inline int obor_profile_uses_loose_attack_name(void)
{
    return obor_profile_build >= 6303 && obor_profile_build < 6310;
}

static inline int obor_profile_has_back_rise_animations(void)
{
    return !obor_profile_uses_5134_script_ids() &&
           (obor_profile_build < 6175 || obor_profile_build >= 6283);
}

static inline int obor_profile_has_back_block_animations(void)
{
    return !obor_profile_uses_5134_script_ids() &&
           (obor_profile_build < 6175 || obor_profile_build >= 6303);
}

static inline int obor_profile_has_edge_animations(void)
{
    return !obor_profile_build || obor_profile_build >= 6292;
}

static inline int obor_profile_has_edge_range(void)
{
    return !obor_profile_build || obor_profile_build >= 6312;
}

static inline void obor_clear_classic_edge(entity *ent)
{
    if(obor_profile_has_edge_animations() && !obor_profile_has_edge_range()) ent->edge = EDGE_NO;
}

static inline void obor_clear_recovery_state(entity *ent)
{
    if(!obor_profile_build || obor_profile_build >= 6281) ent->rising = 0;
    if(!obor_profile_build || obor_profile_build >= 6282) ent->riseattacking = 0;
}

static inline void obor_clear_death_state(entity *ent)
{
    if(!obor_profile_build || obor_profile_build >= 6284)
    {
        ent->inpain = 0;
        ent->falling = 0;
        obor_clear_recovery_state(ent);
    }
    if(obor_profile_build >= 6292 && obor_profile_build < 6303) ent->edge = EDGE_NO;
    if(!obor_profile_build || obor_profile_build >= 6293) ent->ducking = DUCK_INACTIVE;
}

static inline int obor_profile_has_animation_entity_collision(void)
{
    return obor_profile_build == 0 || obor_profile_build >= 6332;
}

static inline int obor_profile_has_entity_collision_collection(void)
{
    return !obor_profile_build || obor_profile_build >= 6340;
}

static inline int obor_animation_property_from_native(int id)
{
    return !obor_profile_has_animation_entity_collision() && id >= ANI_PROP_ENTITY_COLLISION ? (id < INT_MAX ? id + 1 : -1) : id;
}
static inline int obor_animation_property_to_native(int id)
{
    return !obor_profile_has_animation_entity_collision() && id > ANI_PROP_ENTITY_COLLISION ? id - 1 : id;
}
static inline int obor_level_property_from_native(int id)
{
    if(obor_profile_has_boss_counters() || id < LEVEL_PROP_NUM_BOSSES) return id;
    return id < LEVEL_PROP_WEAPON ? id + 1 : -1;
}
static inline int obor_level_property_to_native(int id)
{
    return !obor_profile_has_boss_counters() && id > LEVEL_PROP_NUM_BOSSES ? id - 1 : id;
}
static inline int obor_subtype_from_native(int id)
{
    if(!obor_profile_has_classic_boomerang()) return id;
    if(id == SUBTYPE_TOUCH) return SUBTYPE_BOOMERANG;
    return id > SUBTYPE_TOUCH && id <= SUBTYPE_CHASE + 1 ? id - 1 : id;
}
static inline int obor_subtype_to_native(int id)
{
    if(!obor_profile_has_classic_boomerang()) return id;
    if(id == SUBTYPE_BOOMERANG) return SUBTYPE_TOUCH;
    return id >= SUBTYPE_TOUCH && id <= SUBTYPE_CHASE ? id + 1 : id;
}
static inline int obor_spawn_type_from_native(int id)
{
    if(!obor_profile_has_custom_boomerang()) return id;
    if(id == SPAWN_TYPE_STEAM) return SPAWN_TYPE_PROJECTILE_BOOMERANG;
    return id > SPAWN_TYPE_STEAM && id <= SPAWN_TYPE_WEAPON + 1 ? id - 1 : id;
}
static inline int obor_spawn_type_to_native(int id)
{
    if(!obor_profile_has_custom_boomerang()) return id;
    if(id == SPAWN_TYPE_PROJECTILE_BOOMERANG) return SPAWN_TYPE_STEAM;
    return id >= SPAWN_TYPE_STEAM && id <= SPAWN_TYPE_WEAPON ? id + 1 : id;
}
/* The request flags are a six-bit group. 6391 moves the custom request to the end. */
static inline unsigned obor_projectile_prime_from_native(unsigned flags)
{
    if(!obor_profile_uses_5134_script_ids()) return flags;
    return (flags & ~0x3f0u) | ((flags & 0x010u) << 5) | ((flags & 0x3e0u) >> 1);
}

static inline unsigned obor_projectile_prime_to_native(unsigned flags)
{
    if(!obor_profile_uses_5134_script_ids()) return flags;
    return (flags & ~0x3f0u) | ((flags & 0x200u) >> 5) | ((flags & 0x1f0u) << 1);
}

static inline int obor_attack_from_native(int id)
{
    if(id < 0) return id;
    if(!obor_profile_has_lose_attack_slot() && id >= ATK_LOSE)
    {
        if(id == ATK_LOSE) return ATK_TIMEOVER;
        /* Both the lose and boss-death slots precede the physical custom range. */
        return id <= INT_MAX - 2 ? id + 2 : -1;
    }
    if(obor_profile_build == 6510)
    {
        switch(id)
        {
            case 15: return ATK_BOSS_DEATH;
            case 16: return ATK_ITEM;
            case 17: return ATK_LAND;
            case 18: return ATK_LIFESPAN;
            case 19: return ATK_LOSE;
            case 20: return ATK_PIT;
            case 21: return ATK_TIMEOVER;
            default: return id;
        }
    }
    return id >= ATK_BOSS_DEATH ? (id < INT_MAX ? id + 1 : -1) : id;
}
static inline int obor_attack_to_native(int id)
{
    if(!obor_profile_has_lose_attack_slot() && id >= ATK_LOSE)
    {
        if(id == ATK_TIMEOVER) return id - 1;
        if(id >= MAX_ATKS) return id - 2;
        return ATK_NONE;
    }
    if(obor_profile_build == 6510)
    {
        switch(id)
        {
            case ATK_BOSS_DEATH: return 15;
            case ATK_ITEM: return 16;
            case ATK_LAND: return 17;
            case ATK_LIFESPAN: return 18;
            case ATK_LOSE: return 19;
            case ATK_PIT: return 20;
            case ATK_TIMEOVER: return 21;
            default: return id;
        }
    }
    return id >= MAX_ATKS ? id - 1 : id;
}
#endif
