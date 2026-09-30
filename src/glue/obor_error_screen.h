/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_ERROR_SCREEN_H
#define OBOR_ERROR_SCREEN_H

#include <stdint.h>
#include <string.h>
#include "obor_hankaku.h"

#define OBOR_ERROR_WIDTH 320
#define OBOR_ERROR_HEIGHT 240

/* The OpenBOR SDL menu's 5x10 ASCII glyphs, drawn independently of an engine.
 * This must work after an engine has torn down its framebuffer and allocator. */
static void obor_error_glyph(uint32_t *pixels, int x, int y, unsigned char ch)
{
    if (ch < 0x20 || ch > 0x7e)
        ch = '?';
    const unsigned char *glyph = hankaku_font10 + (ch - 0x20) * 10;
    for (int row = 0; row < 10; ++row) {
        unsigned bits = glyph[row];
        for (int col = 0; col < 5; ++col)
            if ((bits & (1u << col)) && x + col < OBOR_ERROR_WIDTH &&
                y + row < OBOR_ERROR_HEIGHT)
                pixels[(y + row) * OBOR_ERROR_WIDTH + x + col] = 0x00ffffffu;
    }
}

static void obor_error_line(uint32_t *pixels, int x, int y, const char *s)
{
    if (!s)
        return;
    for (; *s && x <= OBOR_ERROR_WIDTH - 5; ++s, x += 5)
        obor_error_glyph(pixels, x, y, (unsigned char)*s);
}

/* Wrap untrusted paths and engine messages without formatting them as printf
 * strings. Non-ASCII bytes become '?' so a malformed log cannot index past
 * the upstream font table. */
static int obor_error_wrapped(uint32_t *pixels, int y, const char *s, int last_y)
{
    char line[61];
    if (!s)
        return y;
    while (*s && y <= last_y) {
        int n = 0;
        while (*s == ' ' || *s == '\n' || *s == '\r' || *s == '\t')
            ++s;
        while (*s && *s != '\n' && *s != '\r' && n < 60) {
            unsigned char c = (unsigned char)*s++;
            line[n++] = (c >= 0x20 && c <= 0x7e) ? (char)c : '?';
        }
        while (n && line[n - 1] == ' ')
            --n;
        line[n] = 0;
        obor_error_line(pixels, 10, y, line);
        y += 12;
    }
    return y;
}

static void obor_error_render(uint32_t *pixels, const char *game,
                              const char *engine, const char *reason)
{
    const char *filename = game;
    for (const char *p = game; p && *p; ++p)
        if (*p == '/' || *p == '\\')
            filename = p + 1;
    memset(pixels, 0, OBOR_ERROR_WIDTH * OBOR_ERROR_HEIGHT * sizeof(*pixels));
    obor_error_line(pixels, 10, 10, "ANYBOR - ERROR LOADING GAME");
    obor_error_line(pixels, 10, 34, "GAME:");
    obor_error_wrapped(pixels, 46, filename, 58);
    obor_error_line(pixels, 10, 70, "ENGINE:");
    obor_error_wrapped(pixels, 82, engine, 82);
    obor_error_line(pixels, 10, 106, "PROBLEM:");
    obor_error_wrapped(pixels, 118, reason, 190);
    obor_error_line(pixels, 10, 207, "Change Engine build in Core Options,");
    obor_error_line(pixels, 10, 219, "then select Restart to try again.");
}

#endif
