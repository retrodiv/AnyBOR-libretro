/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/*
 * AnyBOR video backend.
 *
 * The engine renders into an s_screen (8-bit paletted, 16-bit 565 or 32-bit)
 * and pushes it through video_copy_screen. We convert to XRGB8888 into our
 * own buffer, hand it to the port layer, and yield the frame. vga_vwait only
 * advances the emulated clock to the next 60 Hz boundary — video_copy_screen
 * is the only frame-yield point in the render path.
 */
#include "libretroport.h"
#include "types.h"
#include "video.h"
#include "vga.h"
#include "screen.h"

#include <stdlib.h>
#include <string.h>

u8 pDeltaBuffer[480 * 2592];
int opengl; /* always 0; some engine code tests it */

static s_videomodes mode;
static unsigned *fb;
static int fb_w, fb_h, fb_cap;
static unsigned pal32[256];

#ifdef OBOR_HAS_YUV
static yuv_video_mode yuv_mode_info;
static s_screen *yuv_rgb; /* PIXEL_16 conversion target for webm frames */
#endif
static int yuv_mode;

static int ensure_fb(int w, int h)
{
    size_t pixels;
    if (w <= 0 || h <= 0 || w > 4096 || h > 4096)
        return 0;
    pixels = (size_t)w * (size_t)h;
    if (pixels > (size_t)fb_cap ||
        (yuv_mode && pixels < (size_t)fb_cap)) {
        unsigned *next = (unsigned *)realloc(fb, pixels * sizeof(*fb));
        if (!next && pixels > (size_t)fb_cap)
            return 0;
        if (next) {
            fb = next;
            fb_cap = (int)pixels;
        }
    }
    fb_w = w;
    fb_h = h;
    return 1;
}

void vga_setpalette(unsigned char *palette)
{
    for (int i = 0; i < 256; i++) {
        pal32[i] = ((unsigned)palette[0] << 16) | ((unsigned)palette[1] << 8) |
                   (unsigned)palette[2];
        palette += 3;
    }
}

void vga_vwait(void)
{
    /* Pace to the next 60 Hz boundary on the emulated clock. */
    unsigned long long next = ((obor_clock_us / 16667ULL) + 1ULL) * 16667ULL;
    obor_clock_us = next;
}

int video_set_mode(s_videomodes videomodes)
{
    mode = videomodes;
    if (videomodes.hRes == 0 && videomodes.vRes == 0)
        return 0;
    if (!ensure_fb(videomodes.hRes, videomodes.vRes))
        return 0;
#ifdef OBOR_HAS_YUV
    /* A movie overlay can be much larger than the game's native output.
     * Once the engine returns to its ordinary video mode, retaining that
     * conversion surface makes every later save and rewind copy dead movie
     * pixels. */
    if (yuv_rgb)
        freescreen(&yuv_rgb);
#endif
    yuv_mode = 0;
    return 1;
}

int video_restore_mode(void) { return video_set_mode(mode); }

static int convert_screen(s_screen *src)
{
    if (!src)
        return 0;
    int w = src->width, h = src->height;
    if (!ensure_fb(w, h))
        return 0;
    if (src->pixelformat == PIXEL_32) {
        /* engine 32bpp is ABGR (R in low byte); libretro wants XRGB */
        const unsigned *s = (const unsigned *)src->data;
        unsigned *d = fb;
        for (int i = 0; i < w * h; i++) {
            unsigned v = s[i];
            d[i] = ((v & 0xFF) << 16) | (v & 0xFF00) | ((v >> 16) & 0xFF);
        }
    } else if (src->pixelformat == PIXEL_16) {
        /* engine 16bpp is BGR565 (B high) -> XRGB8888 */
        const unsigned short *s = (const unsigned short *)src->data;
        unsigned *d = fb;
        for (int i = 0; i < w * h; i++) {
            unsigned v = s[i];
            unsigned b = (v >> 11) & 0x1F, g = (v >> 5) & 0x3F, r = v & 0x1F;
            d[i] = ((r << 3 | r >> 2) << 16) | ((g << 2 | g >> 4) << 8) |
                   (b << 3 | b >> 2);
        }
    } else {
        /* 8-bit paletted; prefer the screen's own palette when present */
        unsigned lut[256];
        const unsigned *l = pal32;
        if (src->palette) {
            unsigned char *p = src->palette;
            for (int i = 0; i < 256; i++, p += 3)
                lut[i] = ((unsigned)p[0] << 16) | ((unsigned)p[1] << 8) | p[2];
            l = lut;
        }
        const unsigned char *s = src->data;
        unsigned *d = fb;
        for (int i = 0; i < w * h; i++)
            d[i] = l[s[i]];
    }
    return 1;
}

int video_copy_screen(s_screen *src)
{
    if (!convert_screen(src))
        return 0;
    obor_port_submit_frame(fb, fb_w, fb_h, fb_w);
    obor_yield_frame();
    return 1;
}

void video_clearscreen(void)
{
    if (fb)
        memset(fb, 0, (size_t)fb_w * fb_h * 4);
}

void video_fullscreen_flip(void) {}
void video_stretch(int enable) { (void)enable; }
void video_set_color_correction(int gm, int br) { (void)gm; (void)br; }

/* ---- YUV path (webm cutscenes): convert to RGB and present ---- */

#ifdef OBOR_HAS_YUV
int video_setup_yuv_overlay(const yuv_video_mode *m)
{
    if (!m || !ensure_fb(m->width, m->height))
        return 0;
    yuv_mode_info = *m;
    yuv_mode = 1;
#ifdef OBOR_HAS_MOVIE_PLAYBACK
    yuv_init(4);
#else
    yuv_init(2);
#endif
    if (yuv_rgb)
        freescreen(&yuv_rgb);
#ifdef OBOR_HAS_MOVIE_PLAYBACK
    yuv_rgb = allocscreen(m->width, m->height, PIXEL_32);
#else
    yuv_rgb = allocscreen(m->width, m->height, PIXEL_16);
#endif
    return yuv_rgb != NULL;
}

int video_prepare_yuv_frame(yuv_frame *src)
{
    if (yuv_rgb)
        yuv_to_rgb(src, yuv_rgb);
    return 1;
}

int video_display_yuv_frame(void)
{
    if (yuv_rgb) {
        if (!convert_screen(yuv_rgb))
            return 0;
        obor_port_submit_frame(fb, fb_w, fb_h, fb_w);
        obor_yield_frame();
    }
    return 1;
}
#endif /* OBOR_HAS_YUV */
