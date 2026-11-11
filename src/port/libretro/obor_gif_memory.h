/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_GIF_MEMORY_H
#define OBOR_GIF_MEMORY_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>

/* Keep short-read behavior without constructing a pointer before the block. */
static inline unsigned char *obor_gif_read_block(int handle,
                                                unsigned char *buffer, int count)
{
    int received = readpackfile(handle, buffer, count);
    return buffer + (received > 0 && received <= count ? received : 0);
}

/* The native image descriptor stores signed 16-bit offsets. Preserve that
 * wrap after adding a caller offset, without overflowing the promoted sum. */
static inline short obor_gif_offset(short value, int adjustment)
{
    uint16_t bits = (uint16_t)((int64_t)value + adjustment);
    return (short)(bits <= INT16_MAX ? (int32_t)bits : (int32_t)bits - 65536);
}

/* Palette and pixel storage can be byte aligned. Keep the native pixel bytes
 * and skip a direct-color store when its palette is absent. */
static inline void obor_gif_store_pixel(s_screen *screen,
                                       const unsigned char *palette,
                                       size_t position, unsigned char index)
{
    switch(screen->pixelformat)
    {
    case PIXEL_8:
        screen->data[position] = index;
        break;
    case PIXEL_16:
        if(palette) memcpy(screen->data + position * 2, palette + (size_t)index * 2, 2);
        break;
    case PIXEL_32:
        if(palette) memcpy(screen->data + position * 4, palette + (size_t)index * 4, 4);
        break;
    }
}

#endif
