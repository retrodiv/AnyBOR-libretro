/* AnyBOR modification record: 2026-10-05.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Map native logical-profile animation, attack, subtype and spawn IDs to the
 * shared engine selectors.
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
static inline int obor_animation_from_native(int id)
{
    int original_max = ANI_GETBOOMERANG;
    if(id < 0) return id;
    if(obor_profile_build == 6330)
    {
        if(id == ANI_EDGE) return ANI_GETBOOMERANG;
        if(id == ANI_EDGE + 1) return ANI_GETBOOMERANGINAIR;
        if(id >= ANI_EDGE + 2 && id < MAX_ANIS) return id - 2;
        return id;
    }
    if(obor_profile_build == 6510)
    {
        if(id == 0) return ANI_NONE;
        return id < original_max + 1 ? id - 1 : id + 1;
    }
    return id < original_max ? id : id + 2;
}
static inline int obor_animation_to_native(int id)
{
    int original_max = ANI_GETBOOMERANG;
    if(obor_profile_build == 6330)
    {
        if(id == ANI_GETBOOMERANG) return ANI_EDGE;
        if(id == ANI_GETBOOMERANGINAIR) return ANI_EDGE + 1;
        if(id >= ANI_EDGE && id < original_max) return id + 2;
        return id;
    }
    if(obor_profile_build == 6510)
    {
        if(id == ANI_NONE) return 0;
        return id < original_max ? id + 1 : id - 1;
    }
    return id < original_max ? id : id - 2;
}
static inline int obor_animation_property_from_native(int id)
{
    return obor_profile_build == 6330 && id >= ANI_PROP_ENTITY_COLLISION ? id + 1 : id;
}
static inline int obor_animation_property_to_native(int id)
{
    return obor_profile_build == 6330 && id > ANI_PROP_ENTITY_COLLISION ? id - 1 : id;
}
static inline int obor_subtype_from_native(int id)
{
    if(obor_profile_build != 6330) return id;
    if(id == SUBTYPE_TOUCH) return SUBTYPE_BOOMERANG;
    return id > SUBTYPE_TOUCH && id <= SUBTYPE_CHASE + 1 ? id - 1 : id;
}
static inline int obor_subtype_to_native(int id)
{
    if(obor_profile_build != 6330) return id;
    if(id == SUBTYPE_BOOMERANG) return SUBTYPE_TOUCH;
    return id >= SUBTYPE_TOUCH && id <= SUBTYPE_CHASE ? id + 1 : id;
}
static inline int obor_spawn_type_from_native(int id)
{
    if(obor_profile_build != 6330) return id;
    if(id == SPAWN_TYPE_STEAM) return SPAWN_TYPE_PROJECTILE_BOOMERANG;
    return id > SPAWN_TYPE_STEAM && id <= SPAWN_TYPE_WEAPON + 1 ? id - 1 : id;
}
static inline int obor_spawn_type_to_native(int id)
{
    if(obor_profile_build != 6330) return id;
    if(id == SPAWN_TYPE_PROJECTILE_BOOMERANG) return SPAWN_TYPE_STEAM;
    return id >= SPAWN_TYPE_STEAM && id <= SPAWN_TYPE_WEAPON ? id + 1 : id;
}
static inline int obor_attack_from_native(int id)
{
    if(id < 0) return id;
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
    return id >= ATK_BOSS_DEATH ? id + 1 : id;
}
static inline int obor_attack_to_native(int id)
{
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
