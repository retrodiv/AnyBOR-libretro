/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Preserve source-owned command-table allocation diagnostics and controlled
 * engine termination for historical profiles.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/3400.md
 * at the source repository root. Original notices follow below.
 */

/* Source-owned command allocation diagnostics.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */
#ifndef OBOR_COMMAND_ASSERT_H
#define OBOR_COMMAND_ASSERT_H
#include <stdint.h>
extern uint32_t obor_profile_build;
void borExit(int status);
void obor_port_assert(int value, const char *assertion, const char *function,
                      const char *file, int line);
#ifndef NDEBUG
typedef struct {
    uint32_t revision;
    unsigned line[4];
    const char *function[4];
} obor_command_assert_location;
static const obor_command_assert_location obor_command_assert_locations[] = {
    {3020, {0, 0, 0, 0}, {"", "", "", ""}},
    {3057, {0, 0, 0, 0}, {"", "", "", ""}},
    {3062, {0, 0, 0, 0}, {"", "", "", ""}},
    {3073, {0, 0, 0, 0}, {"", "", "", ""}},
    {3081, {0, 0, 0, 0}, {"", "", "", ""}},
    {3109, {0, 0, 0, 0}, {"", "", "", ""}},
    {3113, {0, 0, 0, 0}, {"", "", "", ""}},
    {3114, {0, 0, 0, 0}, {"", "", "", ""}},
    {3115, {13, 0, 0, 0}, {"createCommandList", "", "", ""}},
    {3117, {13, 0, 0, 0}, {"createCommandList", "", "", ""}},
    {3143, {13, 0, 0, 0}, {"createCommandList", "", "", ""}},
    {3160, {13, 0, 0, 0}, {"createCommandList", "", "", ""}},
    {3167, {13, 0, 0, 0}, {"createModelCommandList", "", "", ""}},
    {3168, {13, 0, 310, 0}, {"createModelCommandList", "", "createLevelCommandList", ""}},
    {3173, {13, 0, 310, 0}, {"createModelCommandList", "", "createLevelCommandList", ""}},
    {3181, {17, 0, 318, 0}, {"createModelCommandList", "", "createLevelCommandList", ""}},
    {3182, {17, 0, 318, 435}, {"createModelCommandList", "", "createLevelCommandList", "createLevelOrderCommandList"}},
    {3192, {17, 0, 318, 435}, {"createModelCommandList", "", "createLevelCommandList", "createLevelOrderCommandList"}},
    {3208, {17, 0, 328, 445}, {"createModelCommandList", "", "createLevelCommandList", "createLevelOrderCommandList"}},
    {3243, {17, 0, 328, 441}, {"createModelCommandList", "", "createLevelCommandList", "createLevelOrderCommandList"}},
    {3244, {35, 0, 35, 35}, {"prepareList", "", "prepareList", "prepareList"}},
    {3255, {35, 0, 35, 35}, {"prepareList", "", "prepareList", "prepareList"}},
    {3256, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3273, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3288, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3303, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3307, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3310, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3311, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3316, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3317, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3318, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3327, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3328, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3330, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3332, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3335, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3337, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3340, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3341, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3342, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3350, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3351, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3352, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3353, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3354, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3355, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3356, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3357, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3360, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3361, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3362, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3365, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3366, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3367, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3371, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3372, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3373, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3375, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3379, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3380, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3381, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3383, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3385, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3388, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3391, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3394, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3397, {39, 39, 39, 39}, {"prepareList", "prepareList", "prepareList", "prepareList"}},
    {3400, {40, 40, 40, 40}, {"prepareList", "prepareList", "prepareList", "prepareList"}}
};
#endif
static void obor_command_allocation_assert(int valid, unsigned site)
{
    if(valid) return;
#ifndef NDEBUG
    const obor_command_assert_location *location =
        &obor_command_assert_locations[
            sizeof(obor_command_assert_locations) / sizeof(*obor_command_assert_locations) - 1];
    for(unsigned i = 0; i < sizeof(obor_command_assert_locations) /
                                sizeof(*obor_command_assert_locations); ++i)
        if(obor_command_assert_locations[i].revision == obor_profile_build) {
            location = &obor_command_assert_locations[i];
            break;
        }
    if(site < 4 && location->line[site])
        obor_port_assert(0, "result", location->function[site],
                         "source/gamelib/commands.c", (int)location->line[site]);
#else
    (void)site;
#endif
    /* Additional private tables and disabled assertions still stop safely. */
    borExit(1);
}
#endif
