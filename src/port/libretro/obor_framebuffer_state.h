/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_FRAMEBUFFER_STATE_H
#define OBOR_FRAMEBUFFER_STATE_H
#include <stdint.h>
#include <string.h>

/* Same packed ABGR -> XRGB conversion as video.c. No pixels are changed while
 * proving eligibility. Include the unused X byte in exact equality, and use
 * memcpy so serialized source views need not have uint32_t alignment. */
static inline int obor_framebuffer_matches(const void *source, const void *frame, uint32_t bytes)
{
    if (!source || !frame || !bytes || (bytes & 3)) return 0;
    const unsigned char *s = (const unsigned char *)source;
    const unsigned char *f = (const unsigned char *)frame;
    uint32_t difference = 0;
    for (uint32_t i = 0; i < bytes; i += 4) {
        uint32_t value, pixel;
        memcpy(&value, s + i, 4); memcpy(&pixel, f + i, 4);
        difference |= (((value & 0xffU) << 16) | (value & 0xff00U) |
                       ((value >> 16) & 0xffU)) ^ pixel;
    }
    return difference == 0;
}

static inline void obor_framebuffer_reconstruct(const void *source, void *frame, uint32_t bytes)
{
    const unsigned char *s = (const unsigned char *)source;
    unsigned char *f = (unsigned char *)frame;
    for (uint32_t i = 0; i < bytes; i += 4) {
        uint32_t value, pixel;
        memcpy(&value, s + i, 4);
        pixel = ((value & 0xffU) << 16) | (value & 0xff00U) | ((value >> 16) & 0xffU);
        memcpy(f + i, &pixel, 4);
    }
}
#endif
