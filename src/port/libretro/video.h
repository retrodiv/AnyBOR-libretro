/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/* AnyBOR video backend — API mirror of sdl/video.h, no SDL. */
#ifndef VIDEO_H
#define VIDEO_H

#include "gfxtypes.h"
#include "types.h"

/* yuv.h (webmlib) only exists in webm-era engines */
#if defined(__has_include)
#if __has_include("yuv.h")
#define OBOR_HAS_YUV 1
#endif
#endif
#ifdef OBOR_HAS_YUV
#include "yuv.h"
#endif

extern u8 pDeltaBuffer[480 * 2592];
extern int opengl;

int video_restore_mode(void);
int video_set_mode(s_videomodes);
int video_copy_screen(s_screen *);
void video_clearscreen(void);
void video_fullscreen_flip(void);
void video_stretch(int);
void video_set_color_correction(int, int);
#ifdef OBOR_HAS_YUV
int video_setup_yuv_overlay(const yuv_video_mode *);
int video_prepare_yuv_frame(yuv_frame *);
int video_display_yuv_frame(void);
#endif

#endif
