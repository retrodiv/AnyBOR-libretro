/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Preserve source-owned drawing and frame diagnostics with bounded access
 * and controlled engine termination.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/3400.md
 * at the source repository root. Original notices follow below.
 */

/* Source-owned drawing/frame assertion diagnostics.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */
#ifndef OBOR_FRAME_ASSERT_H
#define OBOR_FRAME_ASSERT_H
#include <stdint.h>
#include <string.h>
extern uint32_t obor_profile_build;
void obor_port_assert(int value, const char *assertion, const char *function,
                      const char *file, int line);
#ifndef NDEBUG
typedef struct {
    uint32_t revision;
    unsigned line[8];
    const char *expression[8];
} obor_frame_assert_location;
static const obor_frame_assert_location obor_frame_assert_locations[] = {
    {3020, {0, 0, 0, 0, 0, 0, 0, 0}, {"", "", "", "", "", "", "", ""}},
    {3057, {0, 0, 0, 0, 0, 0, 0, 0}, {"", "", "", "", "", "", "", ""}},
    {3062, {0, 0, 0, 0, 0, 0, 0, 0}, {"", "", "", "", "", "", "", ""}},
    {3073, {0, 0, 0, 0, 0, 0, 0, 0}, {"", "", "", "", "", "", "", ""}},
    {3081, {0, 0, 0, 0, 0, 0, 0, 0}, {"", "", "", "", "", "", "", ""}},
    {3082, {0, 0, 0, 0, 0, 0, 0, 0}, {"", "", "", "", "", "", "", ""}},
    {3083, {556, 557, 558, 559, 564, 565, 566, 10291}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", "f < self->animation->numframes"}},
    {3109, {556, 557, 558, 559, 564, 565, 566, 10434}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", "f < self->animation->numframes"}},
    {3117, {563, 564, 565, 566, 571, 572, 573, 10439}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", "f < self->animation->numframes"}},
    {3143, {572, 573, 574, 575, 580, 581, 582, 10396}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", "f < self->animation->numframes"}},
    {3160, {572, 573, 574, 575, 580, 581, 582, 10396}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", "f < self->animation->numframes"}},
    {3173, {573, 574, 575, 576, 581, 582, 583, 10384}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", "f < self->animation->numframes"}},
    {3192, {572, 573, 574, 575, 580, 581, 582, 10263}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", "f < self->animation->numframes"}},
    {3201, {573, 574, 575, 576, 581, 582, 583, 10249}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", "f < self->animation->numframes"}},
    {3204, {573, 574, 575, 576, 581, 582, 583, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3208, {573, 574, 575, 576, 581, 582, 583, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3273, {569, 570, 571, 572, 577, 578, 579, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3288, {569, 570, 571, 572, 577, 578, 579, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3303, {569, 570, 571, 572, 577, 578, 579, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3307, {569, 570, 571, 572, 577, 578, 579, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3310, {569, 570, 571, 572, 577, 578, 579, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3311, {569, 570, 571, 572, 577, 578, 579, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3316, {569, 570, 571, 572, 577, 578, 579, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3317, {569, 570, 571, 572, 577, 578, 579, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3318, {569, 570, 571, 572, 577, 578, 579, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3327, {569, 570, 571, 572, 577, 578, 579, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3328, {571, 572, 573, 574, 579, 580, 581, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3330, {571, 572, 573, 574, 579, 580, 581, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3332, {571, 572, 573, 574, 579, 580, 581, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3335, {571, 572, 573, 574, 579, 580, 581, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3337, {571, 572, 573, 574, 579, 580, 581, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3340, {571, 572, 573, 574, 579, 580, 581, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3341, {571, 572, 573, 574, 579, 580, 581, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3342, {571, 572, 573, 574, 579, 580, 581, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3350, {571, 572, 573, 574, 579, 580, 581, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3351, {571, 572, 573, 574, 579, 580, 581, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3352, {571, 572, 573, 574, 579, 580, 581, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3353, {571, 572, 573, 574, 579, 580, 581, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3354, {571, 572, 573, 574, 579, 580, 581, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3355, {571, 572, 573, 574, 579, 580, 581, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3356, {571, 572, 573, 574, 579, 580, 581, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3357, {571, 572, 573, 574, 579, 580, 581, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3360, {577, 578, 579, 580, 585, 586, 587, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3361, {577, 578, 579, 580, 585, 586, 587, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3362, {577, 578, 579, 580, 585, 586, 587, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3365, {577, 578, 579, 580, 585, 586, 587, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3366, {585, 586, 587, 588, 593, 594, 595, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3367, {585, 586, 587, 588, 593, 594, 595, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3371, {585, 586, 587, 588, 593, 594, 595, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3372, {585, 586, 587, 588, 593, 594, 595, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3373, {585, 586, 587, 588, 593, 594, 595, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3375, {585, 586, 587, 588, 593, 594, 595, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3379, {585, 586, 587, 588, 593, 594, 595, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3380, {585, 586, 587, 588, 593, 594, 595, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3381, {585, 586, 587, 588, 593, 594, 595, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3383, {585, 586, 587, 588, 593, 594, 595, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3385, {585, 586, 587, 588, 593, 594, 595, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3388, {585, 586, 587, 588, 593, 594, 595, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3391, {585, 586, 587, 588, 593, 594, 595, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3394, {587, 588, 589, 590, 595, 596, 597, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3397, {587, 588, 589, 590, 595, 596, 597, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}},
    {3400, {588, 589, 590, 591, 596, 597, 598, 0}, {"index >= 0", "a != NULL", "m != NULL", "index < a->numframes", "index >= 0", "a != NULL", "index < a->numframes", ""}}
};
#endif
static void obor_frame_assert(int valid, const char *expression, const char *function)
{
    if(valid) return;
#ifndef NDEBUG
    unsigned site = 8;
    if(strcmp(function, "update_frame") == 0) site = 7;
    else if(strcmp(function, "setDrawMethod") == 0) {
        if(strcmp(expression, "index >= 0") == 0) site = 0;
        else if(strcmp(expression, "a != NULL") == 0) site = 1;
        else if(strcmp(expression, "m != NULL") == 0) site = 2;
        else if(strcmp(expression, "index < a->numframes") == 0) site = 3;
    } else if(strcmp(function, "getDrawMethod") == 0) {
        if(strcmp(expression, "index >= 0") == 0) site = 4;
        else if(strcmp(expression, "a != NULL") == 0) site = 5;
        else if(strcmp(expression, "index < a->numframes") == 0) site = 6;
    }
    if(site < 8) {
        const obor_frame_assert_location *location =
            &obor_frame_assert_locations[
                sizeof(obor_frame_assert_locations) / sizeof(*obor_frame_assert_locations) - 1];
        for(unsigned i = 0; i < sizeof(obor_frame_assert_locations) /
                                    sizeof(*obor_frame_assert_locations); ++i)
            if(obor_frame_assert_locations[i].revision == obor_profile_build) {
                location = &obor_frame_assert_locations[i];
                break;
            }
        if(location->line[site])
            obor_port_assert(0, location->expression[site], function,
                             "openbor.c", (int)location->line[site]);
    }
#else
    (void)expression;
    (void)function;
#endif
}
#endif
