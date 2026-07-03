/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "obor_circle.h"
#include "adpcm.h"
#include "obor_endian.h"
#include "obor_zip_path.h"
#include "obor_crt.h"
#include "obor_state_padding.h"

static void test_state_padding(void)
{
    unsigned char actual[2080], expected[2080];
    size_t offset, length, pattern, i;
    for (offset = 0; offset < 16; ++offset)
        for (length = 0; length <= 2048; ++length)
            for (pattern = 0; pattern < 3; ++pattern) {
                memset(actual, 0xa5, sizeof(actual));
                for (i = 0; i < length; ++i)
                    actual[offset + i] = pattern == 0 ? 0 : pattern == 1 ? 0xff :
                                         (i % 509 == 0 ? (unsigned char)(i + 1) : 0);
                memcpy(expected, actual, sizeof(actual));
                memset(expected + offset, 0, length);
                obor_state_clear_padding(actual + offset, length);
                assert(!memcmp(actual, expected, sizeof(actual)));
            }
}

/* Literal floating-point sharp-bilinear coordinate equation, independent
 * of the rational/Q16 implementation. Clamp-to-edge precedes interpolation. */
static double crt_reference_coordinate(int pixel, int source, int dest, int scale)
{
    double texel = (pixel + 0.5) * source / dest;
    int whole = (int)texel;
    double distance = texel - whole - 0.5;
    double region = 0.5 - 0.5 / scale;
    double clamped = distance < -region ? -region : distance > region ? region : distance;
    double coord = whole + (distance - clamped) * scale;
    return coord < 0 ? 0 : coord > source - 1 ? source - 1 : coord;
}

static uint32_t crt_reference_pixel(const uint32_t *src, int w, int h, int pitch,
                                    int x, int y, int dw, int dh, int scale)
{
    double u = crt_reference_coordinate(x, w, dw, scale);
    double v = crt_reference_coordinate(y, h, dh, scale);
    int xa = (int)u, ya = (int)v, xb = xa + 1 < w ? xa + 1 : xa;
    int yb = ya + 1 < h ? ya + 1 : ya, shift;
    double wx = u - xa, wy = v - ya;
    uint32_t result = 0;
    for (shift = 0; shift <= 16; shift += 8) {
        double a = (src[ya * pitch + xa] >> shift) & 255u;
        double b = (src[ya * pitch + xb] >> shift) & 255u;
        double c = (src[yb * pitch + xa] >> shift) & 255u;
        double d = (src[yb * pitch + xb] >> shift) & 255u;
        double value = (a * (1 - wx) + b * wx) * (1 - wy) +
                       (c * (1 - wx) + d * wx) * wy;
        result |= (uint32_t)(value + 0.5) << shift;
    }
    return result;
}

static void test_crt_filter(void)
{
    const struct { int w, h; } cases[] = {
        {365, 244}, {364, 245}, {320, 245}, {368, 240}, {368, 245},
        {480, 272}, {320, 180}, {640, 360}, {960, 540}, {1280, 720},
        {641, 480}, {640, 481}, {800, 600}, {800, 601}, {800, 800},
        {241, 320}, {511, 317}, {1, 600}, {960, 1}, {4096, 1}, {1, 4096}, {1, 1}
    };
    static uint32_t guarded[640 * 480 + 2];
    uint32_t *frame = guarded + 1;
    size_t n;
    int phase, x, y;
    guarded[0] = guarded[640 * 480 + 1] = 0xdeadbeefu;
    for (n = 0; n < sizeof(cases) / sizeof(cases[0]); ++n) {
        int w = cases[n].w, h = cases[n].h, pitch = w + 3, dw = 640, dh = 480;
        int left, top, scale;
        uint32_t *source = (uint32_t *)malloc((size_t)pitch * h * sizeof(*source));
        assert(source);
        memset(source, 0xa5, (size_t)pitch * h * sizeof(*source));
        if (w * 480 >= h * 640) {
            dh = h * 640 / w;
            scale = (640 + w - 1) / w;
        } else {
            dw = w * 480 / h;
            scale = (480 + h - 1) / h;
        }
        if (!dw) dw = 1;
        if (!dh) dh = 1;
        left = (640 - dw) / 2;
        top = (480 - dh) / 2;
        for (y = 0; y < h; ++y)
            for (x = 0; x < w; ++x)
                source[y * pitch + x] = (uint32_t)(x * 12347u + y * 97813u) & 0xffffffu;
        obor_crt_compose(frame, source, w, h, pitch);
        for (y = 0; y < 480; ++y)
            for (x = 0; x < 640; ++x) {
                uint32_t actual = frame[y * 640 + x], expected;
                int shift;
                if (x < left || x >= left + dw || y < top || y >= top + dh) {
                    assert(actual == 0);
                    continue;
                }
                expected = crt_reference_pixel(source, w, h, pitch,
                                                x - left, y - top, dw, dh, scale);
                for (shift = 0; shift <= 16; shift += 8)
                    assert(abs((int)((actual >> shift) & 255) -
                               (int)((expected >> shift) & 255)) <= 1);
            }
        free(source);
        assert(guarded[0] == 0xdeadbeefu && guarded[640 * 480 + 1] == 0xdeadbeefu);
    }
    /* One-pixel vertical strokes scrolling through every 480->640 phase.
     * The old nearest scaler returned 255 at columns 1 and 2 in phase zero;
     * sharp bilinear instead blends those edges to 191. Integer enlargement
     * remains exact (covered by test_crt below). */
    for (phase = 0; phase < 6; ++phase) {
        uint32_t *source = (uint32_t *)malloc(480 * 272 * sizeof(*source));
        assert(source);
        for (y = 0; y < 272; ++y)
            for (x = 0; x < 480; ++x)
                source[y * 480 + x] = (x + phase) % 3 == 1 ? 0xffffffu : 0;
        obor_crt_compose(frame, source, 480, 272, 480);
        for (x = 0; x < 640; ++x)
            assert(frame[180 * 640 + x] ==
                   crt_reference_pixel(source, 480, 272, 480, x, 121, 640, 362, 2));
        if (!phase)
            assert(frame[180 * 640 + 1] == 0xbfbfbfu &&
                   frame[180 * 640 + 2] == 0xbfbfbfu);
        free(source);
    }
}

static void test_crt(void)
{
    static uint32_t source[960 * 800], frame[640 * 480];
    const struct { int w, h, left, top, right, bottom; } cases[] = {
        {320, 240, 0, 0, 640, 480},
        {365, 244, 0, 26, 640, 453},
        {364, 245, 0, 25, 640, 455},
        {320, 245, 7, 0, 633, 480},
        {368, 240, 0, 31, 640, 448},
        {368, 245, 0, 27, 640, 453},
        {640, 480, 0, 0, 640, 480},
        {641, 480, 0, 0, 640, 479},
        {640, 481, 1, 0, 639, 480},
        {800, 600, 0, 0, 640, 480},
        {800, 601, 1, 0, 639, 480},
        {800, 800, 80, 0, 560, 480},
        {960, 540, 0, 60, 640, 420},
        {480, 272, 0, 59, 640, 421},
        {320, 256, 20, 0, 620, 480},
        {240, 320, 140, 0, 500, 480},
        {1, 600, 319, 0, 320, 480},
        {960, 1, 0, 239, 640, 240},
    };
    size_t n;
    int x, y;
    for (n = 0; n < sizeof(source) / sizeof(source[0]); ++n)
        source[n] = 0x123456;
    for (n = 0; n < sizeof(cases) / sizeof(cases[0]); ++n) {
        obor_crt_compose(frame, source, cases[n].w, cases[n].h, 960);
        for (y = 0; y < 480; ++y)
            for (x = 0; x < 640; ++x)
                assert(frame[y * 640 + x] ==
                    ((x >= cases[n].left && x < cases[n].right &&
                      y >= cases[n].top && y < cases[n].bottom) ? 0x123456u : 0));
    }
    /* Padded source rows must not leak into the image. Check pixel centres
     * and orientation using an independently specified 2x enlargement. */
    for (y = 0; y < 240; ++y)
        for (x = 0; x < 320; ++x)
            source[y * 960 + x] = (uint32_t)(y * 320 + x + 1);
    obor_crt_compose(frame, source, 320, 240, 960);
    for (y = 0; y < 480; ++y)
        for (x = 0; x < 640; ++x)
            assert(frame[y * 640 + x] == (uint32_t)((y / 2) * 320 + x / 2 + 1));
    obor_crt_compose(frame, source, 4097, 1, 4097);
    for (n = 0; n < sizeof(frame) / sizeof(frame[0]); ++n)
        assert(frame[n] == 0);
}

static void test_crt_presentation(void)
{
    const struct { int w, h, out_w, out_h, left, top; } cases[] = {
        {320, 240, 320, 240, 0, 0},
        {320, 180, 320, 240, 0, 30},
        {360, 180, 640, 480, 0, 80},
        {320, 200, 320, 240, 0, 20},
        {240, 240, 320, 240, 40, 0},
        {240, 244, 326, 244, 43, 0},
        {241, 241, 322, 241, 40, 0},
        {321, 180, 321, 241, 0, 30},
        {320, 181, 320, 240, 0, 29},
        {324, 180, 324, 243, 0, 31},
        {325, 180, 325, 244, 0, 32},
        {326, 180, 640, 480, 0, 63},
        /* Inclusive tolerance endpoints and adjacent pixels. */
        {239, 200, 267, 200, 14, 0},
        {240, 200, 240, 200, 0, 0},
        {241, 200, 241, 200, 0, 0},
        {219, 150, 219, 150, 0, 0},
        {220, 150, 220, 150, 0, 0},
        {221, 150, 221, 166, 0, 8},
        {364, 244, 640, 480, 0, 25},
        {364, 240, 640, 480, 0, 29},
        {365, 244, 640, 480, 0, 26},
        {364, 245, 640, 480, 0, 25},
        {320, 245, 640, 480, 7, 0},
        {365, 245, 640, 480, 0, 25},
        {640, 480, 640, 480, 0, 0},
        {800, 800, 640, 480, 80, 0},
        {1, 1, 2, 1, 0, 0},
    };
    static uint32_t source[803 * 800], guarded[640 * 480 + 2];
    static uint32_t scaled[640 * 480];
    uint32_t *frame = guarded + 1;
    size_t n, p;
    int x, y, out_w, out_h;
    assert(!obor_crt_output_size(0, 240, &out_w, &out_h));
    assert(out_w == 0 && out_h == 240);
    assert(!obor_crt_output_size(4097, 1, &out_w, &out_h));
    assert(!obor_crt_output_size(1, -1, &out_w, &out_h));
    for (n = 0; n < sizeof(cases) / sizeof(cases[0]); ++n) {
        int w = cases[n].w, h = cases[n].h, pitch = w + 3;
        int adapted = obor_crt_output_size(w, h, &out_w, &out_h);
        int fitted = out_w == 640 && out_h == 480;
        assert(out_w == cases[n].out_w && out_h == cases[n].out_h);
        assert(adapted == (fitted || out_w != w || out_h != h));
        for (p = 0; p < sizeof(guarded) / sizeof(guarded[0]); ++p)
            guarded[p] = 0xdeadbeefu;
        memset(source, 0xa5, sizeof(source));
        for (y = 0; y < h; ++y)
            for (x = 0; x < w; ++x)
                source[y * pitch + x] = (uint32_t)(1 + x * 73 + y * 251);
        obor_crt_present(frame, source, w, h, pitch);
        if (fitted) {
            obor_crt_compose(scaled, source, w, h, pitch);
            assert(!memcmp(frame, scaled, sizeof(scaled)));
        } else {
            for (y = 0; y < out_h; ++y)
                for (x = 0; x < out_w; ++x) {
                    int sx = x - cases[n].left, sy = y - cases[n].top;
                    uint32_t expected = sx >= 0 && sx < w && sy >= 0 && sy < h
                        ? source[sy * pitch + sx] : 0;
                    assert(frame[y * out_w + x] == expected);
                }
        }
        assert(guarded[0] == 0xdeadbeefu);
        for (p = (size_t)out_w * out_h + 1;
             p < sizeof(guarded) / sizeof(guarded[0]); ++p)
            assert(guarded[p] == 0xdeadbeefu);
    }
}

static unsigned hits[65][65];
static void pixel(int x, int y, void *unused)
{
    (void)unused;
    assert(x >= 0 && x < 65 && y >= 0 && y < 65);
    assert(++hits[y][x] == 1); /* Alpha must be applied once per pixel. */
}

int main(void)
{
    int r, x, y;
    test_crt();
    test_crt_filter();
    test_crt_presentation();
    test_state_padding();
    assert(sizeof(UInt64) == 8 && sizeof(SInt64) == 8);
    assert(Swap16(0x1234) == 0x3412);
    assert(Swap32(UINT32_C(0x01234567)) == UINT32_C(0x67452301));
    assert(Swap64(UINT64_C(0x0123456789abcdef)) == UINT64_C(0xefcdab8967452301));
    assert(Swap64(Swap64(UINT64_C(0x89504e470d0a1a0a))) == UINT64_C(0x89504e470d0a1a0a));
    {
        char out[128];
        const char *bad[] = {"../x", "/x", "C:x", "a/./x", "a/NUL.txt",
            "CON", "prn.wav", "x/LPT9.ext", "COM1", "a./x", "a /x",
            "x:stream", "a?b", "a|b", "CON .txt", "COM\xc2\xb9.txt"};
        size_t i;
        for (i = 0; i < sizeof(bad)/sizeof(bad[0]); ++i)
            assert(!obor_zip_safe_name(bad[i], out, sizeof(out)));
        assert(obor_zip_safe_name("Data\\Sprites/hero.png", out, sizeof(out)));
        assert(!strcmp(out, "Data/Sprites/hero.png"));
        assert(obor_zip_safe_name("company/lpt10.png", out, sizeof(out)));
        assert(!obor_zip_safe_name("abcdef", out, 4));
    }
    for (r = 0; r <= 30; ++r) {
        memset(hits, 0, sizeof(hits));
        obor_circle_raster(32, 32, r, 65, 65, pixel, 0);
        assert(hits[32][32 + r] && hits[32 + r][32]);
        for (y = 0; y < 65; ++y)
            for (x = 0; x < 65; ++x) {
                assert(hits[y][x] == hits[64-y][x]);
                assert(hits[y][x] == hits[y][64-x]);
                assert(hits[y][x] == hits[x][y]);
            }
    }
    memset(hits, 0, sizeof(hits));
    obor_circle_raster(0, 0, 3, 65, 65, pixel, 0);
    assert(hits[0][3] && hits[3][0] && hits[2][2]);
    obor_circle_raster(INT_MIN, INT_MAX, 1, 65, 65, pixel, 0);
    obor_circle_raster(0, 0, -1, 65, 65, pixel, 0);
    {
        unsigned char packed[] = {0x77, 0xff, 0x00};
        short pcm[6], zeros[4] = {0, 0, 0, 0};
        unsigned char encoded[2] = {255, 255};
        adpcm_reset();
        assert(adpcm_decode(packed, pcm, 1, 1) == 4);
        assert(pcm[0] == 11 && pcm[1] == 41);
        assert(adpcm_valprev(0) == 41 && adpcm_index(0) == 16);
        adpcm_reset();
        assert(adpcm_decode(packed, pcm, 1, 2) == 4);
        assert(pcm[0] == 11 && pcm[1] == 11);
        assert(adpcm_index(0) == 8 && adpcm_index(1) == 8);
        adpcm_reset();
        assert(adpcm_encode(zeros, encoded, sizeof(zeros), 1) == 2);
        assert(!encoded[0] && !encoded[1]);
        adpcm_loop_reset(0, 32767, 88);
        adpcm_decode(packed, pcm, 1, 1);
        assert(pcm[0] == 32767 && pcm[1] == 32767);
        assert(adpcm_decode(packed, pcm, INT_MAX, 1) == 0);
        assert(adpcm_decode(0, pcm, 1, 1) == 0);
    }
    return 0;
}
