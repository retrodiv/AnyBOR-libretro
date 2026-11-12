/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PREPARE_PROGRESS_H
#define OBOR_PREPARE_PROGRESS_H
#include <stdint.h>

/* Content helpers also run in standalone tools. A frontend may install a
 * cooperative checkpoint; false requests normal cleanup and cancellation. */
static int (*obor_prepare_progress)(void);

/* Preparation has optional passes whose costs cannot be predicted (ZIP,
 * external programs, repairs, cached results). Allocate explicit phase ranges
 * and measure bytes within each pass, never elapsed time or repaint count.
 * This is a monotonic estimate of total preparation work, not a time estimate.
 * Helpers remain usable without a frontend and add no reads or allocations. */
typedef struct { unsigned first, last; } obor_prepare_range;
static obor_prepare_range obor_prepare_phase;
static uint64_t obor_prepare_done, obor_prepare_total;
static unsigned obor_prepare_position; /* thousandths; 1000 only on success */

static inline unsigned obor_prepare_value(void)
{
    if (obor_prepare_total) {
        unsigned value = obor_prepare_phase.first + (unsigned)(
            (double)obor_prepare_done / (double)obor_prepare_total *
            (obor_prepare_phase.last - obor_prepare_phase.first));
        if (value > obor_prepare_position) obor_prepare_position = value;
    }
    return obor_prepare_position;
}

static inline void obor_prepare_reset(void)
{
    obor_prepare_phase.first = obor_prepare_phase.last = 0;
    obor_prepare_done = obor_prepare_total = 0;
    obor_prepare_position = 0;
}

static inline void obor_prepare_stage(obor_prepare_range parent,
                                      unsigned first, unsigned last, uint64_t total)
{
    if (!obor_prepare_progress) return;
    obor_prepare_value();
    unsigned span = parent.last - parent.first;
    obor_prepare_phase.first = parent.first + span * first / 1000;
    obor_prepare_phase.last = parent.first + span * last / 1000;
    obor_prepare_done = 0;
    obor_prepare_total = total;
    if (obor_prepare_phase.first > obor_prepare_position)
        obor_prepare_position = obor_prepare_phase.first;
}

static inline void obor_prepare_advance(uint64_t bytes)
{
    if (!obor_prepare_progress) return;
    uint64_t remaining = obor_prepare_total - obor_prepare_done;
    obor_prepare_done += bytes < remaining ? bytes : remaining;
}

static inline int obor_prepare_checkpoint(void)
{
    return !obor_prepare_progress || obor_prepare_progress();
}
#endif
