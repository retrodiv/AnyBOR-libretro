/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_TEXTURE_BOUNDS_H
#define OBOR_TEXTURE_BOUNDS_H
#include <limits.h>
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include "anybor_resources.h"

/* Preserve native clipping without signed coordinate overflow. */
static int obor_texture_clip(int sw, int sh, int bw, int bh,
        int *x, int *y, int *width, int *height)
{
    int64_t left = *x, top = *y, w = *width, h = *height;
    if(sw <= 0 || sh <= 0 || bw <= 0 || bh <= 0 || left >= sw || top >= sh) return 0;
    if(left < 0) { w += left; left = 0; }
    if(top < 0) { h += top; top = 0; }
    if(left + w > sw) w = sw - left;
    if(top + h > sh) h = sh - top;
    if(w <= 0 || h <= 0) return 0;
    *x = (int)left; *y = (int)top; *width = (int)w; *height = (int)h;
    return 1;
}

/* Owned storage retains its actual tail, including native palette bytes.
 * Untracked borrowed records keep the caller's declared pixel extent. */
static int obor_texture_storage(const void *record, const void *data,
        int width, int height, size_t bytes, size_t *available)
{
    size_t pixels, needed, capacity;
    uintptr_t start = (uintptr_t)record, body = (uintptr_t)data;
    if(!record || !data || width <= 0 || height <= 0 || !bytes ||
            (size_t)width > SIZE_MAX / (size_t)height) return 0;
    pixels = (size_t)width * (size_t)height;
    if(pixels > (size_t)PTRDIFF_MAX / bytes) return 0;
    needed = pixels * bytes;
    capacity = obor_allocation_size(record);
    if(capacity || obor_allocation_query(record, NULL, &capacity))
    {
        if(body < start || body - start > capacity || needed > capacity - (body - start)) return 0;
        *available = capacity - (body - start);
    }
    else *available = needed;
    return 1;
}

static int obor_texture_palette(const void *record, const void *palette, size_t bytes)
{
    size_t available, capacity = obor_allocation_size(record);
    uintptr_t start = (uintptr_t)record, address = (uintptr_t)palette;
    if(!palette) return 0;
    if(capacity && address >= start && address - start <= capacity)
        return 256 * bytes <= capacity - (address - start);
    return palette && (!obor_allocation_query(palette, NULL, &available) || available >= 256 * bytes);
}

static void obor_texture_palette_pixel(unsigned char *destination,
        const void *palette, unsigned char index, size_t bytes)
{
    unsigned char value[4];
    if(!destination || !palette || (bytes != 2 && bytes != 4)) return;
    memcpy(value, (const unsigned char *)palette + (size_t)index * bytes, bytes);
    memcpy(destination, value, bytes);
}

/* Native float multiplication precedes the double 0.5 addition. */
static int obor_texture_distortion(float factor, float amplitude, int *result)
{
    double value = (double)(factor * amplitude) + 0.5;
    if(!isfinite(value) || value <= (double)INT_MIN - 1.0 || value >= (double)INT_MAX + 1.0) return 0;
    *result = (int)value;
    return 1;
}
#endif
