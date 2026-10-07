/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_LOADING_SCREEN_H
#define OBOR_LOADING_SCREEN_H
#include <stdlib.h>
#include <math.h>
#include "miniz.h"
#include "obor_crt.h"
#include <obor_loading_background.h>

static uint32_t obor_loading_rgb(const unsigned char *rgb, int width, int x, int y)
{
    const unsigned char *p = rgb + ((size_t)y * width + x) * 3;
    return ((uint32_t)p[0] << 16) | ((uint32_t)p[1] << 8) | p[2];
}

typedef struct { int first, count; size_t offset; } obor_loading_tap;
typedef struct {
    obor_loading_tap *taps;
    int32_t *weights;
} obor_loading_filter;

static void obor_loading_filter_free(obor_loading_filter *filter)
{
    free(filter->taps); free(filter->weights);
}

/* Widen Lanczos3 by the reduction factor: all source pixels in its footprint
 * contribute, rather than sampling just the neighbours of a destination
 * centre. Precompute normalized Q14 weights once per axis. */
static int obor_loading_filter_create(obor_loading_filter *filter, int source,
                                      int destination, double start, double span)
{
    double scale = span / destination;
    double footprint = scale > 1.0 ? scale : 1.0;
    int capacity = (int)ceil(6.0 * footprint) + 2;
    if (capacity > source) capacity = source;
    filter->taps = (obor_loading_tap *)malloc((size_t)destination * sizeof(*filter->taps));
    filter->weights = (int32_t *)malloc((size_t)destination * capacity * sizeof(*filter->weights));
    if (!filter->taps || !filter->weights) return 0;
    size_t offset = 0;
    const double pi = 3.14159265358979323846;
    for (int i = 0; i < destination; ++i) {
        double centre = start + (i + 0.5) * scale - 0.5;
        int first = (int)ceil(centre - 3.0 * footprint);
        int last = (int)floor(centre + 3.0 * footprint);
        if (first < 0) first = 0;
        if (last >= source) last = source - 1;
        obor_loading_tap *tap = &filter->taps[i];
        tap->first = first; tap->count = last - first + 1; tap->offset = offset;
        double total = 0.0;
        for (int j = first; j <= last; ++j) {
            double x = (j - centre) / footprint;
            total += fabs(x) < 1e-12 ? 1.0 :
                     fabs(x) >= 3.0 ? 0.0 : 3.0 * sin(pi*x) * sin(pi*x/3.0) / (pi*pi*x*x);
        }
        int sum = 0, peak = 0;
        for (int j = 0; j < tap->count; ++j) {
            double x = (first + j - centre) / footprint;
            double weight = fabs(x) < 1e-12 ? 1.0 :
                            fabs(x) >= 3.0 ? 0.0 : 3.0 * sin(pi*x) * sin(pi*x/3.0) / (pi*pi*x*x);
            int value = (int)floor(weight * 16384.0 / total + 0.5);
            filter->weights[offset + j] = value;
            sum += value;
            if (value > filter->weights[offset + peak]) peak = j;
        }
        filter->weights[offset + peak] += 16384 - sum;
        offset += tap->count;
    }
    return 1;
}

static int obor_loading_channel(int value)
{
    value = (value + 8192) >> 14;
    return value < 0 ? 0 : value > 255 ? 255 : value;
}

/* Centred cover crop followed by separable, antialiased Lanczos3. Retain
 * signed intermediate RGB values so negative lobes are clipped only after
 * both axes. The precomputed native rasters bypass this operation entirely. */
static int obor_loading_resize(uint32_t *dst, int width, int height,
                                const unsigned char *rgb, int sw, int sh)
{
    if (!dst || !rgb || width <= 0 || height <= 0 || sw <= 0 || sh <= 0) return 0;
    double cw = sw, ch = sh;
    if ((int64_t)width * sh < (int64_t)height * sw) cw = (double)sh * width / height;
    else ch = (double)sw * height / width;
    obor_loading_filter horizontal = {NULL, NULL}, vertical = {NULL, NULL};
    int16_t *intermediate = NULL;
    int result = 0;
    int first, rows;
    obor_loading_tap *last;
    if (!obor_loading_filter_create(&horizontal, sw, width, (sw-cw)/2.0, cw) ||
        !obor_loading_filter_create(&vertical, sh, height, (sh-ch)/2.0, ch)) goto done;
    first = vertical.taps[0].first;
    last = &vertical.taps[height-1];
    rows = last->first + last->count - first;
    intermediate = (int16_t *)malloc((size_t)rows * width * 3 * sizeof(*intermediate));
    if (!intermediate) goto done;
    for (int y = 0; y < rows; ++y) {
        const unsigned char *line = rgb + (size_t)(first+y) * sw * 3;
        int16_t *out = intermediate + (size_t)y * width * 3;
        for (int x = 0; x < width; ++x) {
            const obor_loading_tap *tap = &horizontal.taps[x];
            const int32_t *weights = horizontal.weights + tap->offset;
            const unsigned char *pixels = line + tap->first * 3;
            int red = 0, green = 0, blue = 0;
            for (int j = 0; j < tap->count; ++j) {
                int weight = weights[j];
                red += pixels[3*j] * weight;
                green += pixels[3*j+1] * weight;
                blue += pixels[3*j+2] * weight;
            }
            out[3*x] = (int16_t)((red + 8192) >> 14);
            out[3*x+1] = (int16_t)((green + 8192) >> 14);
            out[3*x+2] = (int16_t)((blue + 8192) >> 14);
        }
    }
    for (int y = 0; y < height; ++y) {
        const obor_loading_tap *tap = &vertical.taps[y];
        const int32_t *weights = vertical.weights + tap->offset;
        const int16_t *line = intermediate + (size_t)(tap->first-first) * width * 3;
        for (int x = 0; x < width; ++x) {
            const int16_t *pixels = line + 3*x;
            int red = 0, green = 0, blue = 0;
            for (int j = 0; j < tap->count; ++j) {
                int weight = weights[j];
                red += pixels[0] * weight;
                green += pixels[1] * weight;
                blue += pixels[2] * weight;
                pixels += (size_t)width * 3;
            }
            dst[(size_t)y * width + x] = ((uint32_t)obor_loading_channel(red) << 16) |
                                       ((uint32_t)obor_loading_channel(green) << 8) |
                                       (uint32_t)obor_loading_channel(blue);
        }
    }
    result = 1;
done:
    free(intermediate);
    obor_loading_filter_free(&horizontal); obor_loading_filter_free(&vertical);
    return result;
}

/* Decode only the selected asset. Discard the master RGB buffer after the
 * resize; the framebuffer lasts until native video takes over. No resized
 * image or image identity is written to the filesystem. */
static uint32_t *obor_loading_create(int width, int height)
{
    if (width <= 0 || height <= 0 || width > 4096 || height > 4096) return NULL;
    const obor_loading_asset *asset = &obor_loading_assets[3];
    for (unsigned i = 0; i < 3; ++i)
        if (width == obor_loading_assets[i].width && height == obor_loading_assets[i].height)
            asset = &obor_loading_assets[i];
    mz_ulong bytes = (mz_ulong)asset->width * asset->height * 3;
    unsigned char *rgb = (unsigned char *)malloc(bytes);
    uint32_t *pixels = (uint32_t *)malloc((size_t)width * height * sizeof(*pixels));
    if (!rgb || !pixels || mz_uncompress(rgb, &bytes, asset->data, asset->size) != MZ_OK ||
        bytes != (mz_ulong)asset->width * asset->height * 3) {
        free(rgb); free(pixels); return NULL;
    }
    if (width == asset->width && height == asset->height) {
        for (int y = 0; y < height; ++y)
            for (int x = 0; x < width; ++x)
                pixels[(size_t)y * width + x] = obor_loading_rgb(rgb, width, x, y);
    } else {
        if (!obor_loading_resize(pixels, width, height, rgb, asset->width, asset->height)) {
            free(rgb); free(pixels); return NULL;
        }
    }
    free(rgb);
    return pixels;
}

/* Fill from the left with measured preparation progress (thousandths).
 * Retain the approved artwork and track proportions at every native raster. */
static void obor_loading_render(uint32_t *pixels, int width, int height, unsigned progress)
{
    int track = width * 3 / 4;
    if (track < 1) track = 1;
    int left = (width - track) / 2;
    if (progress > 1000) progress = 1000;
    int filled = (int)((uint64_t)track * progress / 1000);
    int top = height * 220 / 240, rows = height * 6 / 240;
    if (rows < 1) rows = 1;
    if (rows > height - top) rows = height - top;
    for (int y = top; y < top + rows; ++y)
        for (int x = 0; x < track; ++x)
            pixels[(size_t)y * width + left + x] =
                x < filled ? 0x00407ac0u : 0x00303030u;
}
#endif
