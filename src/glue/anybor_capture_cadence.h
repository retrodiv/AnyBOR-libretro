/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_CAPTURE_CADENCE_H
#define OBOR_CAPTURE_CADENCE_H
#include <stdint.h>
#include <string.h>

/* Prediction schedules optional work, never the frontend's actual captures.
 * One missed prediction does not schedule more work until a capture arrives. */
typedef struct {
    uint64_t last, next;
    unsigned period, agreement, seen;
} obor_capture_cadence;

static inline void obor_capture_cadence_reset(obor_capture_cadence *c)
{ memset(c, 0, sizeof(*c)); }

static inline void obor_capture_cadence_observe(obor_capture_cadence *c, uint64_t frame)
{
    if (c->seen && frame == c->last) return;
    uint64_t delta = c->seen && frame > c->last ? frame - c->last : 0;
    if (delta && delta <= 120) {
        c->agreement = delta == c->period ? 2 : 1;
        c->period = (unsigned)delta;
    } else c->agreement = c->period = 0;
    c->last = frame;
    c->seen = 1;
    c->next = c->agreement == 2 && frame <= UINT64_MAX - c->period ?
              frame + c->period : 0;
}

static inline int obor_capture_cadence_due(obor_capture_cadence *c, uint64_t frame)
{
    if (!c->next || frame < c->next) return 0;
    int due = frame == c->next;
    c->next = 0;
    return due;
}
#endif
