/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_CRT_H
#define OBOR_CRT_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define OBOR_CRT_WIDTH 640
#define OBOR_CRT_HEIGHT 480

/* Small images outside inclusive 4:3 +/-10% gain native-pixel padding on
 * one axis. Round fractional extents up, then recheck both size limits.
 * Return whether composition is needed; invalid sizes remain unchanged. */
static int obor_crt_output_size(int width, int height, int *out_w, int *out_h)
{
    *out_w = width;
    *out_h = height;
    if (width <= 0 || height <= 0 || width > 4096 || height > 4096)
        return 0;
    if (width <= 364 && height <= 244 &&
        (width * 30 < height * 36 || width * 30 > height * 44)) {
        if (width * 3 > height * 4)
            *out_h = (width * 3 + 3) / 4;
        else
            *out_w = (height * 4 + 2) / 3;
    }
    if (*out_w > 364 || *out_h > 244) {
        *out_w = OBOR_CRT_WIDTH;
        *out_h = OBOR_CRT_HEIGHT;
        return 1;
    }
    return *out_w != width || *out_h != height;
}

typedef struct obor_crt_tap {
    unsigned first, second, weight; /* Q16 weight of the second texel. */
} obor_crt_tap;

/* Sharp-bilinear texture sampling at destination pixel centres. For a
 * fractional source texel coordinate t and integer prescale s, the texture
 * coordinate stays at the texel centre except within 1/(2*s) of an edge.
 * Those edge regions interpolate with the neighbouring texel. This is the
 * software equivalent of integer nearest prescaling followed by bilinear
 * filtering, without allocating the intermediate image.
 *
 * Keep coordinate calculations rational until the Q16 weight is rounded.
 * In particular, an exact integer enlargement must not soften any pixels. */
static obor_crt_tap obor_crt_sample(int pixel, int source, int dest, int scale)
{
    unsigned denominator = (unsigned)(2 * dest);
    unsigned numerator = (unsigned)((2 * pixel + 1) * source);
    unsigned remainder = numerator % denominator;
    int first = (int)(numerator / denominator), second;
    unsigned weight = 0;
    obor_crt_tap tap;
    if (2 * remainder * (unsigned)scale < denominator) {
        --first;
        weight = 32768u + (unsigned)(((uint64_t)remainder * scale * 65536u +
                                     denominator / 2) / denominator);
    } else if (2 * (denominator - remainder) * (unsigned)scale < denominator) {
        weight = 32768u - (unsigned)(((uint64_t)(denominator - remainder) *
                                     scale * 65536u + denominator / 2) / denominator);
    }
    second = first + 1;
    tap.first = (unsigned)(first < 0 ? 0 : first >= source ? source - 1 : first);
    tap.second = (unsigned)(second < 0 ? 0 : second >= source ? source - 1 : second);
    tap.weight = weight;
    return tap;
}

static uint32_t obor_crt_lerp(uint32_t a, uint32_t b, unsigned weight)
{
    unsigned inverse = 65536u - weight;
    uint64_t rb;
    uint32_t g;
    if (!weight || a == b)
        return a & 0x00ffffffu;
    if (weight == 65536u)
        return b & 0x00ffffffu;
    /* Leave 32 bits between R and B so Q16 products cannot overlap. */
    rb = (((((uint64_t)(a & 0x00ff0000u) << 16) | (a & 255u)) * inverse +
           (((uint64_t)(b & 0x00ff0000u) << 16) | (b & 255u)) * weight +
           UINT64_C(0x0000800000008000)) >> 16);
    g = (((a & 0x0000ff00u) * inverse + (b & 0x0000ff00u) * weight +
          0x00800000u) >> 16) & 0x0000ff00u;
    return (uint32_t)((rb >> 16) & 0x00ff0000u) | (uint32_t)(rb & 255u) | g;
}

/* Fit the complete square-pixel game image inside a 4:3 TV raster.
 * The frontend owns the physical display mode, refresh and interlacing.
 * Source pitch is in pixels; destination is a packed XRGB8888 raster.
 * Sharp bilinear uses ceil(min(viewport_width/source_width,
 * viewport_height/source_height)) as the shared integer prescale. */
static void obor_crt_compose(uint32_t *dst, const uint32_t *src,
                             int width, int height, int pitch)
{
    int dw = OBOR_CRT_WIDTH, dh = OBOR_CRT_HEIGHT;
    int x, y, left, top, scale;
    obor_crt_tap columns[OBOR_CRT_WIDTH];
    memset(dst, 0, OBOR_CRT_WIDTH * OBOR_CRT_HEIGHT * sizeof(*dst));
    if (!src || width <= 0 || height <= 0 || width > 4096 ||
        height > 4096 || pitch < width)
        return;

    if (width * OBOR_CRT_HEIGHT >= height * OBOR_CRT_WIDTH) {
        dh = height * OBOR_CRT_WIDTH / width;
        scale = (OBOR_CRT_WIDTH + width - 1) / width;
    } else {
        dw = width * OBOR_CRT_HEIGHT / height;
        scale = (OBOR_CRT_HEIGHT + height - 1) / height;
    }
    if (dw < 1) dw = 1;
    if (dh < 1) dh = 1;
    left = (OBOR_CRT_WIDTH - dw) / 2;
    top = (OBOR_CRT_HEIGHT - dh) / 2;

    for (x = 0; x < dw; ++x)
        columns[x] = obor_crt_sample(x, width, dw, scale);
    for (y = 0; y < dh; ++y) {
        obor_crt_tap vertical = obor_crt_sample(y, height, dh, scale);
        const uint32_t *row0 = src + (size_t)vertical.first * pitch;
        const uint32_t *row1 = src + (size_t)vertical.second * pitch;
        uint32_t *out = dst + (top + y) * OBOR_CRT_WIDTH + left;
        for (x = 0; x < dw; ++x) {
            obor_crt_tap horizontal = columns[x];
            uint32_t a = obor_crt_lerp(row0[horizontal.first],
                                     row0[horizontal.second], horizontal.weight);
            if (!vertical.weight) {
                out[x] = a;
            } else {
                uint32_t b = obor_crt_lerp(row1[horizontal.first],
                                         row1[horizontal.second], horizontal.weight);
                out[x] = obor_crt_lerp(a, b, vertical.weight);
            }
        }
    }
}

/* Present using the selected output size. Small padded images are copied
 * without filtering; odd margins put the extra pixel at the right/bottom.
 * The caller supplies space for the maximum 640x480 output. */
static void obor_crt_present(uint32_t *dst, const uint32_t *src,
                             int width, int height, int pitch)
{
    int out_w, out_h, left, top, y;
    obor_crt_output_size(width, height, &out_w, &out_h);
    if (width <= 0 || height <= 0 || width > 4096 || height > 4096 ||
        (out_w == OBOR_CRT_WIDTH && out_h == OBOR_CRT_HEIGHT)) {
        obor_crt_compose(dst, src, width, height, pitch);
        return;
    }
    memset(dst, 0, (size_t)out_w * out_h * sizeof(*dst));
    if (!src || pitch < width)
        return;
    left = (out_w - width) / 2;
    top = (out_h - height) / 2;
    for (y = 0; y < height; ++y)
        memcpy(dst + (size_t)(top + y) * out_w + left,
               src + (size_t)y * pitch, (size_t)width * sizeof(*dst));
}

#endif
