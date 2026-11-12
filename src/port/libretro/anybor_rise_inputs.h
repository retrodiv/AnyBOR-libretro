/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_RISE_INPUTS_H
#define OBOR_RISE_INPUTS_H

#include <stdint.h>

/* The caller evaluates its native unsigned timer expression before passing
 * the span. A supplied sample keeps one RNG call at the native gate. */
static inline int obor_rise_random(unsigned int sample, uint64_t span)
{
    return span && (uint64_t)sample % span < UINT64_C(3);
}

#endif
