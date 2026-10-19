/* AnyBOR modification record: 2026-10-06.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Map native logical-profile animation, attack, subtype and spawn IDs to the
 * shared engine selectors. Preserve divergent 7086 and 2021 7123 animation,
 * combat, model, script-selector and menu contracts by logical profile,
 * retaining safe storage and additive APIs.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/7142.md
 * at the source repository root. Original notices follow below.
 */

/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */
#ifndef OBOR_BRANCH_PROFILE_IDS_H
#define OBOR_BRANCH_PROFILE_IDS_H
#include <limits.h>
/* Named properties added after the divergent revisions must not collide with
 * their pre-existing numeric selectors. Only newly accepted names use this tag. */
#define OBOR_ANIMATION_NAMED_BASE 65536
static inline const char *obor_profile_version_string(void)
{
    if(obor_profile_build == 7086) return "v3.0 Build 7086 (commit hash: 7a45a22)";
    if(obor_profile_build == 7123) return "v3.0 Build 7123 (commit hash: f5261e7)";
    return VERSION;
}
static inline const char *obor_profile_shutdown_message(void)
{
    if(obor_profile_build == 7086) return OBOR_SHUTDOWN_MESSAGE_VERSION("v3.0 Build 7086 (commit hash: 7a45a22)");
    if(obor_profile_build == 7123) return OBOR_SHUTDOWN_MESSAGE_VERSION("v3.0 Build 7123 (commit hash: f5261e7)");
    return DEFAULT_SHUTDOWN_MESSAGE;
}

extern int max_attack_types;
/* Internal tables keep the current capacity. Script IDs retain their original
 * revision's domain, including dynamic normal attacks after the built-in set. */
/* New named internal types use formerly invalid negative selectors. This
 * leaves every original nonnegative custom attack ID unchanged. */
static inline int obor_attack_from_native(int id)
{
    if(obor_profile_legacy_branch())
    {
        if(id == -2) return ATK_SUB_ENTITY_PARENT_KILL;
        if(id == -3) return ATK_SUB_ENTITY_UNSUMMON;
    }
    if(obor_profile_legacy_branch() && id >= 21)
        return id > INT_MAX - 2 ? -1 : id + 2;
    return id;
}
static inline int obor_attack_to_native(int id)
{
    if(!obor_profile_legacy_branch() || id < 21) return id;
    if(id == ATK_SUB_ENTITY_PARENT_KILL) return -2;
    if(id == ATK_SUB_ENTITY_UNSUMMON) return -3;
    return id - 2;
}
static inline int obor_attack_valid(int id)
{
    return id >= 0 && id < max_attack_types;
}
static inline int obor_spawn_type_from_native(int id)
{
    if(obor_profile_legacy_branch() && id >= SPAWN_TYPE_DUST_DROP)
        return id == INT_MAX ? -1 : id + 1;
    return id;
}
static inline int obor_spawn_type_to_native(int id)
{
    if(!obor_profile_legacy_branch() || id < SPAWN_TYPE_DUST_DROP) return id;
    return id == SPAWN_TYPE_DUST_DROP ? -1 : id - 1;
}
#endif
