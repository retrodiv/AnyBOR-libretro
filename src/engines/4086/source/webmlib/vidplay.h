/* AnyBOR modification record: 2026-10-19.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Import the native 4153 media component, retaining its upstream authorship
 * and license notices.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/4086.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2015 OpenBOR Team
 */

#ifndef VIDPLAY_H
#define VIDPLAY_H

#include "yuv.h"

struct webm_context;
typedef struct webm_context webm_context;

webm_context *webm_start_playback(const char *path, int volume);
void webm_get_video_info(webm_context *ctx, yuv_video_mode *dims);
void webm_close(webm_context *ctx);
yuv_frame *webm_get_next_frame(webm_context *ctx);

#endif

