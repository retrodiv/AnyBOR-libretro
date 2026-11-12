/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_RANDOM_ADDITIVE_H
#define OBOR_RANDOM_ADDITIVE_H
#include <stdint.h>

/* Owned implementation of the target libc's 31-word additive sequence.
 * Expand a seed with the Park-Miller recurrence, then discard ten cycles.
 * Indices replace host pointers so the complete state belongs to the engine.
 * Explicit unsigned sums preserve the native 32-bit output without overflow.
 */
typedef struct {
    uint32_t words[31];
    unsigned rear;
    int ready;
} obor_additive_random_state;
static obor_additive_random_state obor_additive_random;

static int obor_additive_next(void)
{
    unsigned front = (obor_additive_random.rear + 3u) % 31u;
    uint32_t value = obor_additive_random.words[front] +
                     obor_additive_random.words[obor_additive_random.rear];
    obor_additive_random.words[front] = value;
    obor_additive_random.rear = (obor_additive_random.rear + 1u) % 31u;
    return (int)(value >> 1);
}

void obor_srand(unsigned int value)
{
    int64_t previous = value <= INT32_MAX ? (int64_t)value :
                       (int64_t)value - INT64_C(4294967296);
    obor_additive_random.words[0] = (uint32_t)value;
    for (unsigned i = 1; i < 31; ++i) {
        previous = INT64_C(16807) * (previous % 127773) -
                   INT64_C(2836) * (previous / 127773);
        if (previous <= 0) previous += INT64_C(2147483647);
        obor_additive_random.words[i] = (uint32_t)previous;
    }
    obor_additive_random.rear = 0;
    obor_additive_random.ready = 1;
    for (unsigned i = 0; i < 310; ++i) (void)obor_additive_next();
}

int obor_rand(void)
{
    if (!obor_additive_random.ready) obor_srand(1);
    return obor_additive_next();
}
#endif
