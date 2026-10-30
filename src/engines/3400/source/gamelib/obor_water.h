/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Calculate bounded historical water spans and phase conversions while
 * preserving native clipping and sampling.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/3400.md
 * at the source repository root. Original notices follow below.
 */

/*
 * Bounded historical water traversal.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */
#ifndef OBOR_WATER_H
#define OBOR_WATER_H
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
extern uint32_t obor_profile_build;
extern float _sinfactors[256];
typedef struct obor_water_rows {
    int sw, sh, dw, dh, sy, dy, rows, x, amplitude, period, origin;
    float phase, step;
} obor_water_rows;

static int obor_water_distortion(float phase, int amplitude, int *value)
{
    int index;
    double raw;
    if(!((double)phase >= INT_MIN && (double)phase <= INT_MAX)) return 0;
    index = (int)phase;
    if(index < 0 || index >= 256) return 0;
    /* Preserve the original float multiplication before adding double 0.5. */
    raw = (double)(_sinfactors[index] * amplitude) + 0.5;
    if(!(raw >= INT_MIN && raw <= INT_MAX)) return 0;
    *value = (int)raw;
    return 1;
}

static int obor_water_begin(obor_water_rows *w, s_screen *dest, s_screen *src,
                           int x, int y, int amplitude, float wavelength, int time, int mode)
{
    int64_t sy, dy, count;
    if(!src || !dest || src->width <= 0 || src->height <= 0 ||
       dest->width <= 0 || dest->height <= 0 || wavelength == 0.0f) return 0;
    w->sw = src->width; w->sh = src->height;
    w->dw = dest->width; w->dh = dest->height;
    if((uint64_t)w->sw * w->sh > SIZE_MAX / 4 ||
       (uint64_t)w->dw * w->dh > SIZE_MAX / 4) return 0;
    if((int64_t)x + (int64_t)amplitude * 2 + w->sw <= 0 ||
       (int64_t)x - (int64_t)amplitude * 2 >= w->dw) return 0;
    sy = y < 0 ? -(int64_t)y : 0;
    dy = y < 0 ? 0 : y;
    count = (int64_t)w->sh - sy;
    if(count > (int64_t)w->dh - dy) count = (int64_t)w->dh - dy;
    if(count <= 0) return 0;
    w->sy = (int)sy; w->dy = (int)dy; w->rows = (int)count;
    w->x = x; w->amplitude = amplitude;
    w->period = obor_profile_build < 3366 ? 255 : 256;
    w->phase = (float)(time % w->period);
    w->origin = amplitude;
    if(mode == 1 && !obor_water_distortion(w->phase, amplitude, &w->origin)) return 0;
    w->step = w->period / wavelength;
    w->phase += w->sy * w->step;
    return 1;
}

static int obor_water_span(obor_water_rows *w, int row, int *sx, int *dx, int *length)
{
    int wave;
    int64_t begin, end, source, count, shift;
    size_t sb, db, stotal = (size_t)w->sw * w->sh, dtotal = (size_t)w->dw * w->dh;
    if(!((double)w->phase >= INT_MIN && (double)w->phase <= INT_MAX)) return 0;
    w->phase = w->phase - (int)w->phase + (int)w->phase % w->period;
    if(!obor_water_distortion(w->phase, w->amplitude, &wave)) return 0;
    w->phase += w->step;
    shift = (int64_t)wave - w->origin;
    begin = (int64_t)w->x + shift; end = begin + w->sw;
    if(obor_profile_build >= 3390) {
        /* The original rejects against source width, not destination width. */
        if(begin >= w->sw || end <= 0) return 0;
        source = begin < 0 ? -begin : 0;
        if(begin < 0) begin = 0;
        if(end > w->dw) end = w->dw;
        count = end - begin;
    } else {
        /* Preserve the old left-first branch, including defined row spill. */
        if(end < 0 || begin > w->dw) return 0;
        source = begin < 0 ? -begin : 0;
        if(begin < 0) {count = end; begin = 0;}
        else count = end > w->dw ? w->dw - begin : w->sw;
    }
    if(count <= 0 || source < 0 || source > w->sw || count > w->sw - source ||
       begin < 0 || begin > w->dw) return 0;
    sb = (size_t)(w->sy + row) * w->sw + (size_t)source;
    db = (size_t)(w->dy + row) * w->dw + (size_t)begin;
    if(sb > stotal || db > dtotal || (size_t)count > stotal - sb) return 0;
    *sx = (int)source; *dx = (int)begin; *length = (int)count;
    return 1;
}
#endif
