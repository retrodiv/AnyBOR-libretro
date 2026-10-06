/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_LOADING_SCREEN_H
#define OBOR_LOADING_SCREEN_H
#include "obor_error_screen.h"
#include "obor_loading_background.h"

/* An indeterminate indicator: preparation has several passes, so a guessed
 * percentage would misrepresent progress. Native loading follows this phase. */
static void obor_loading_render(uint32_t *pixels, unsigned tick)
{
    for (unsigned i = 0; i < OBOR_ERROR_WIDTH * OBOR_ERROR_HEIGHT; ++i) {
        const unsigned char *rgb = obor_loading_background + i * 3;
        pixels[i] = ((uint32_t)rgb[0] << 16) | ((uint32_t)rgb[1] << 8) | rgb[2];
    }
    unsigned phase = tick % 100;
    int offset = (int)(phase <= 50 ? phase : 100 - phase) * 4;
    for (int y = 220; y < 226; ++y)
        for (int x = 40; x < 280; ++x)
            pixels[y * OBOR_ERROR_WIDTH + x] =
                x >= 40 + offset && x < 80 + offset ? 0x00407ac0u : 0x00303030u;
}
#endif
