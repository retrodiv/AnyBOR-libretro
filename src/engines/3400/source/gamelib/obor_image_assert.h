/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Preserve source-owned image failure diagnostics and controlled core
 * termination for historical profiles.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/3400.md
 * at the source repository root. Original notices follow below.
 */

/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_EARLY_IMAGE_ASSERT_H
#define OBOR_EARLY_IMAGE_ASSERT_H
#include <stdint.h>
extern uint32_t obor_profile_build;
void obor_port_assert(int value, const char *assertion, const char *func,
                      const char *file, int line);
typedef struct obor_image_assert_location {
    uint32_t revision;
    int screen_allocation, screen_decode, panel;
} obor_image_assert_location;
static const obor_image_assert_location obor_image_assert_locations[] = {
    {3020, 0, 0, 0},
    {3038, 0, 0, 0},
    {3039, 0, 0, 8727},
    {3051, 0, 0, 8735},
    {3052, 907, 917, 8732},
    {3057, 907, 917, 8732},
    {3062, 907, 917, 8732},
    {3073, 910, 920, 8747},
    {3081, 910, 920, 8747},
    {3109, 910, 920, 8923},
    {3117, 910, 920, 8928},
    {3137, 930, 940, 8877},
    {3138, 930, 940, 0},
    {3143, 916, 926, 0},
    {3160, 916, 926, 0},
    {3173, 916, 926, 0},
    {3192, 916, 926, 0},
    {3208, 916, 926, 0},
    {3273, 890, 900, 0},
    {3288, 890, 900, 0},
    {3303, 890, 900, 0},
    {3307, 890, 900, 0},
    {3310, 890, 900, 0},
    {3311, 890, 900, 0},
    {3316, 890, 900, 0},
    {3317, 890, 900, 0},
    {3318, 890, 900, 0},
    {3327, 890, 900, 0},
    {3328, 890, 900, 0},
    {3330, 890, 900, 0},
    {3332, 890, 900, 0},
    {3335, 890, 900, 0},
    {3337, 890, 900, 0},
    {3340, 890, 900, 0},
    {3341, 890, 900, 0},
    {3342, 890, 900, 0},
    {3350, 890, 900, 0},
    {3351, 890, 900, 0},
    {3352, 890, 900, 0},
    {3353, 890, 900, 0},
    {3354, 890, 900, 0},
    {3355, 890, 900, 0},
    {3356, 890, 900, 0},
    {3357, 890, 900, 0},
    {3360, 890, 900, 0},
    {3361, 890, 900, 0},
    {3362, 890, 900, 0},
    {3365, 890, 900, 0},
    {3366, 890, 900, 0},
    {3367, 890, 900, 0},
    {3371, 890, 900, 0},
    {3372, 890, 900, 0},
    {3373, 890, 900, 0},
    {3375, 890, 900, 0},
    {3379, 890, 900, 0},
    {3380, 890, 900, 0},
    {3381, 890, 900, 0},
    {3383, 890, 900, 0},
    {3385, 890, 900, 0},
    {3388, 890, 900, 0},
    {3391, 890, 900, 0},
    {3394, 890, 900, 0},
    {3397, 890, 900, 0},
    {3400, 890, 900, 0},
};
static void obor_early_image_assert(unsigned site)
{
#ifndef NDEBUG
    const obor_image_assert_location *location =
        &obor_image_assert_locations[sizeof(obor_image_assert_locations) /
                                     sizeof(obor_image_assert_locations[0]) - 1];
    unsigned i;
    int line;
    for(i = 0; i < sizeof(obor_image_assert_locations) /
                    sizeof(obor_image_assert_locations[0]); ++i)
        if(obor_image_assert_locations[i].revision == obor_profile_build) {
            location = &obor_image_assert_locations[i];
            break;
        }
    line = site == 0 ? location->screen_allocation :
           site == 1 ? location->screen_decode : location->panel;
    if(line)
        obor_port_assert(0, "0", site == 2 ? "load_level" : "loadscreen",
                         site == 2 ? "openbor.c" : "source/gamelib/loadimg.c", line);
#else
    (void)site;
#endif
}
#endif
