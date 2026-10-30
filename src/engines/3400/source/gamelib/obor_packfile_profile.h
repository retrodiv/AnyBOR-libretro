/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Retain each profile's native path-assertion diagnostic and use the
 * controlled engine stop.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/3400.md
 * at the source repository root. Original notices follow below.
 */

/* Own source locations for packfile profile diagnostics.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */
#ifndef OBOR_PACKFILE_PROFILE_H
#define OBOR_PACKFILE_PROFILE_H
#include <stdint.h>
extern uint32_t obor_profile_build;
void obor_port_assert(int value, const char *assertion, const char *function,
                      const char *file, int line);
static void obor_profile_casesearch_assert(void)
{
#ifndef NDEBUG
    static const struct { uint32_t revision; int line; const char *expression; } locations[] = {
        {3020, 0, ""},
        {3038, 0, ""},
        {3039, 202, "rest_of_path-filepath > 0"},
        {3057, 202, "rest_of_path-filepath > 0"},
        {3062, 202, "rest_of_path-filepath > 0"},
        {3063, 202, "rest_of_path-filepath > 0"},
        {3073, 205, "rest_of_path-filepath > 0"},
        {3081, 226, "rest_of_path-filepath > 0"},
        {3109, 226, "rest_of_path-filepath > 0"},
        {3117, 226, "rest_of_path-filepath > 0"},
        {3120, 226, "rest_of_path-filepath > 0"},
        {3121, 226, "rest_of_path-filepath > 0"},
        {3143, 226, "rest_of_path-filepath > 0"},
        {3160, 226, "rest_of_path-filepath > 0"},
        {3173, 226, "rest_of_path-filepath > 0"},
        {3185, 226, "rest_of_path-filepath > 0"},
        {3186, 238, "rest_of_path-filepath > 0"},
        {3192, 238, "rest_of_path-filepath > 0"},
        {3208, 238, "rest_of_path-filepath > 0"},
        {3273, 237, "rest_of_path-filepath > 0"},
        {3288, 237, "rest_of_path-filepath > 0"},
        {3303, 237, "rest_of_path-filepath > 0"},
        {3307, 239, "rest_of_path-filepath > 0"},
        {3310, 239, "rest_of_path-filepath > 0"},
        {3311, 239, "rest_of_path-filepath > 0"},
        {3316, 239, "rest_of_path-filepath > 0"},
        {3317, 239, "rest_of_path-filepath > 0"},
        {3318, 239, "rest_of_path-filepath > 0"},
        {3327, 239, "rest_of_path-filepath > 0"},
        {3328, 239, "rest_of_path-filepath > 0"},
        {3330, 239, "rest_of_path-filepath > 0"},
        {3332, 239, "rest_of_path-filepath > 0"},
        {3335, 239, "rest_of_path-filepath > 0"},
        {3337, 239, "rest_of_path-filepath > 0"},
        {3340, 239, "rest_of_path-filepath > 0"},
        {3341, 239, "rest_of_path-filepath > 0"},
        {3342, 239, "rest_of_path-filepath > 0"},
        {3350, 239, "rest_of_path-filepath > 0"},
        {3351, 239, "rest_of_path-filepath > 0"},
        {3352, 239, "rest_of_path-filepath > 0"},
        {3353, 239, "rest_of_path-filepath > 0"},
        {3354, 239, "rest_of_path-filepath > 0"},
        {3355, 239, "rest_of_path-filepath > 0"},
        {3356, 239, "rest_of_path-filepath > 0"},
        {3357, 239, "rest_of_path-filepath > 0"},
        {3360, 239, "rest_of_path-filepath > 0"},
        {3361, 239, "rest_of_path-filepath > 0"},
        {3362, 239, "rest_of_path-filepath > 0"},
        {3365, 239, "rest_of_path-filepath > 0"},
        {3366, 239, "rest_of_path-filepath > 0"},
        {3367, 239, "rest_of_path-filepath > 0"},
        {3371, 239, "rest_of_path-filepath > 0"},
        {3372, 239, "rest_of_path-filepath > 0"},
        {3373, 239, "rest_of_path-filepath > 0"},
        {3375, 239, "rest_of_path-filepath > 0"},
        {3379, 239, "rest_of_path-filepath > 0"},
        {3380, 239, "rest_of_path-filepath > 0"},
        {3381, 239, "rest_of_path-filepath > 0"},
        {3383, 239, "rest_of_path-filepath > 0"},
        {3385, 239, "rest_of_path-filepath > 0"},
        {3388, 239, "rest_of_path-filepath > 0"},
        {3391, 239, "rest_of_path-filepath > 0"},
        {3394, 239, "rest_of_path-filepath > 0"},
        {3397, 239, "rest_of_path-filepath > 0"},
        {3400, 239, "rest_of_path-filepath > 0"},
    };
    unsigned i;
    for(i = 0; i < sizeof(locations) / sizeof(*locations); ++i)
        if(locations[i].revision == obor_profile_build)
        {
            if(locations[i].line)
                obor_port_assert(0, locations[i].expression, "casesearch",
                                 "source/gamelib/packfile.c", locations[i].line);
            return;
        }
#endif
}
#endif
