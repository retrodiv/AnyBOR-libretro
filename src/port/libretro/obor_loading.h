/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_LOADING_H
#define OBOR_LOADING_H
#include <stdint.h>

/* Loading work does not advance the emulated frame clock until a repaint
 * yields. Let real progress break that cycle, without using wall time or
 * painting once per model in very large model lists. */
static inline int obor_loading_progress_changed(int value, int max, int *last)
{
    if (value < 0 || max <= 0) {
        *last = -1;
        return 0;
    }
    int percent = (int)((int64_t)value * 100 / max);
    if (percent == *last)
        return 0;
    *last = percent;
    return 1;
}
#endif
