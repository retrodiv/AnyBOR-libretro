/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_CRT_H
#define OBOR_CRT_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define OBOR_CRT_MAX_EXTENT 4096

/* Quarter turns counterclockwise, as in RETRO_ENVIRONMENT_SET_ROTATION. */
enum obor_image_rotation {
    OBOR_ROTATION_NONE, OBOR_ROTATION_LEFT, OBOR_ROTATION_INVERTED, OBOR_ROTATION_RIGHT
};

enum obor_crt_oversize {
    OBOR_CRT_640_480, OBOR_CRT_KEEP_480, OBOR_CRT_320_240, OBOR_CRT_KEEP_240
};

typedef struct obor_crt_frame {
    int width, height;             /* Canvas before rotation. */
    int image_width, image_height; /* Centered image inside the canvas. */
    int prescale;                  /* Sharp bilinear integer prescale. */
    int area_filter;
    float aspect;                 /* Display aspect before rotation. */
} obor_crt_frame;

static void obor_crt_fit(obor_crt_frame *frame, int width, int height)
{
    if (width * frame->height >= height * frame->width) {
        frame->image_width = frame->width;
        frame->image_height = height * frame->width / width;
        frame->prescale = (frame->width + width - 1) / width;
    } else {
        frame->image_width = width * frame->height / height;
        frame->image_height = frame->height;
        frame->prescale = (frame->height + height - 1) / height;
    }
    if (frame->image_width < 1) frame->image_width = 1;
    if (frame->image_height < 1) frame->image_height = 1;
}

/* Calculate fitting in game coordinates. Padding rounds up to whole pixels,
 * then both axes are checked again against the inclusive CRT limits. */
static obor_crt_frame obor_crt_layout(int width, int height, int vertical,
                                     enum obor_crt_oversize mode)
{
    obor_crt_frame frame = { width, height, width, height, 1, 0, 0.0f };
    if (width <= 0 || height <= 0 || width > OBOR_CRT_MAX_EXTENT || height > OBOR_CRT_MAX_EXTENT)
        return frame;
    int limit_w = vertical ? 244 : 364, limit_h = vertical ? 364 : 244;
    int shape_w = vertical ? 3 : 4, shape_h = vertical ? 4 : 3;
    if (width <= limit_w && height <= limit_h) {
        int horizontal = width * shape_h, vertical_extent = height * shape_w;
        if (horizontal * 10 < vertical_extent * 9 || horizontal * 10 > vertical_extent * 11) {
            if (horizontal > vertical_extent)
                frame.height = (horizontal + shape_w - 1) / shape_w;
            else
                frame.width = (vertical_extent + shape_h - 1) / shape_h;
        }
        if (frame.width <= limit_w && frame.height <= limit_h)
            return frame;
    }

    frame.area_filter = mode == OBOR_CRT_320_240 || mode == OBOR_CRT_KEEP_240;
    int scale = frame.area_filter ? 80 : 160;
    if (mode == OBOR_CRT_KEEP_480 || mode == OBOR_CRT_KEEP_240) {
        int kept = vertical ? height : width, other = vertical ? width : height;
        int fixed = 3 * scale, fitted = fixed, ideal = (other * 4 + 2) / 3;
        if (kept >= ideal) {
            ideal = kept;
            fitted = 4 * scale * other / kept;
            if (fitted < 1) fitted = 1;
        }
        int extent = ideal > OBOR_CRT_MAX_EXTENT ? OBOR_CRT_MAX_EXTENT : ideal;
        frame.width = vertical ? fixed : extent;
        frame.height = vertical ? extent : fixed;
        frame.image_width = vertical ? fitted : kept;
        frame.image_height = vertical ? kept : fitted;
        /* The frontend supplies the remaining bars if the ideal extent exceeds the cap. */
        float aspect = (4.0f * extent) / (3.0f * ideal);
        frame.aspect = vertical ? 1.0f / aspect : aspect;
    } else {
        frame.width = shape_w * scale;
        frame.height = shape_h * scale;
        obor_crt_fit(&frame, width, height);
    }
    return frame;
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

static void obor_crt_sharp_bilinear(uint32_t *dst, int stride, int dw, int dh,
                                  const uint32_t *src, int width, int height,
                                  int pitch, int scale)
{
    int x, y;
    obor_crt_tap columns[OBOR_CRT_MAX_EXTENT];

    for (x = 0; x < dw; ++x)
        columns[x] = obor_crt_sample(x, width, dw, scale);
    for (y = 0; y < dh; ++y) {
        obor_crt_tap vertical = obor_crt_sample(y, height, dh, scale);
        const uint32_t *row0 = src + (size_t)vertical.first * pitch;
        const uint32_t *row1 = src + (size_t)vertical.second * pitch;
        uint32_t *out = dst + (size_t)y * stride;
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

/* Measure weighted pixel coverage in units of 1/destination_extent. */
static unsigned obor_crt_area_overlap(unsigned texel, unsigned extent,
                                      unsigned first, unsigned end)
{
    unsigned left = texel * extent, right = left + extent;
    return (right < end ? right : end) - (left > first ? left : first);
}

static void obor_crt_area(uint32_t *dst, int stride, unsigned dw, unsigned dh,
                          const uint32_t *src, unsigned width, unsigned height, int pitch)
{
    uint64_t area = (uint64_t)width * height;
    for (unsigned y = 0; y < dh; ++y) {
        unsigned top = y * height, bottom = top + height;
        uint32_t *out = dst + (size_t)y * stride;
        for (unsigned x = 0; x < dw; ++x) {
            unsigned left = x * width, right = left + width;
            uint64_t red = 0, green = 0, blue = 0;
            for (unsigned sy = top / dh; sy * dh < bottom; ++sy) {
                unsigned wy = obor_crt_area_overlap(sy, dh, top, bottom);
                const uint32_t *row = src + (size_t)sy * pitch;
                for (unsigned sx = left / dw; sx * dw < right; ++sx) {
                    unsigned weight = wy * obor_crt_area_overlap(sx, dw, left, right);
                    uint32_t pixel = row[sx];
                    red += ((pixel >> 16) & 255u) * (uint64_t)weight;
                    green += ((pixel >> 8) & 255u) * (uint64_t)weight;
                    blue += (pixel & 255u) * (uint64_t)weight;
                }
            }
            out[x] = (uint32_t)((red + area / 2) / area) << 16 |
                     (uint32_t)((green + area / 2) / area) << 8 |
                     (uint32_t)((blue + area / 2) / area);
        }
    }
}

/* Source pitch is in pixels. The destination is packed XRGB8888. */
static void obor_crt_present(uint32_t *dst, const obor_crt_frame *frame,
                             const uint32_t *src, int width, int height, int pitch)
{
    int stride = frame->width, dw = frame->image_width, dh = frame->image_height;
    uint32_t *image = dst + (size_t)((frame->height - dh) / 2) * stride + (stride - dw) / 2;
    if (dw != stride || dh != frame->height)
        memset(dst, 0, (size_t)stride * frame->height * sizeof(*dst));
    if (dw == width && dh == height) {
        for (int y = 0; y < height; ++y)
            memcpy(image + (size_t)y * stride, src + (size_t)y * pitch,
                   (size_t)width * sizeof(*dst));
    } else if (frame->area_filter) {
        obor_crt_area(image, stride, (unsigned)dw, (unsigned)dh,
                      src, (unsigned)width, (unsigned)height, pitch);
    } else {
        obor_crt_sharp_bilinear(image, stride, dw, dh, src, width, height, pitch, frame->prescale);
    }
}

static inline void obor_rotate_frame(uint32_t *dst, const uint32_t *src,
                                     int width, int height, int pitch, unsigned rotation)
{
    int out_w = rotation & 1u ? height : width;
    int out_h = rotation & 1u ? width : height;
    int step = rotation == OBOR_ROTATION_LEFT ? pitch : rotation == OBOR_ROTATION_RIGHT ? -pitch : -1;
    for (int y = 0; y < out_h; ++y) {
        ptrdiff_t index;
        if (rotation == OBOR_ROTATION_LEFT)
            index = width - 1 - y;
        else if (rotation == OBOR_ROTATION_RIGHT)
            index = (ptrdiff_t)(height - 1) * pitch + y;
        else
            index = (ptrdiff_t)(height - 1 - y) * pitch + width - 1;
        for (int x = 0; x < out_w; ++x, index += step)
            *dst++ = src[index];
    }
}

#endif
