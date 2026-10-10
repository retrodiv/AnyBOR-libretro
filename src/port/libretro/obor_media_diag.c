/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_media_diag.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef WEBM
#include "obor_threads.h"
void obor_worker_pause(void);
#endif

int obor_media_diag_enabled(void)
{
    const char *value = getenv("OBOR_DIAG_WEBM_REPRODUCIBLE");
    return value && strcmp(value, "1") == 0;
}

void obor_media_diag_failure(const char *phase)
{
    fprintf(stderr, "[obor-media-diag] schema=%d enabled=1 invalid=1 phase=%s\n",
            OBOR_MEDIA_DIAG_SCHEMA, phase);
}

int obor_media_diag_wait(obor_media_diag_probe probe, void *context,
                         const char *phase)
{
#ifdef WEBM
    uint64_t start = obor_wall_uticks();
    for (;;) {
        int ready = probe(context);
        uint64_t now;
        if (ready > 0) return 1;
        if (ready < 0) { obor_media_diag_failure(phase); return 0; }
        now = obor_wall_uticks();
        if (now < start || now - start >= OBOR_MEDIA_DIAG_WAIT_US) {
            obor_media_diag_failure(phase);
            return 0;
        }
        /* Host-only bounded wait. Never call timer_* or obor_wait_frame. */
        obor_worker_pause();
    }
#else
    (void)probe; (void)context; (void)phase;
    return 0;
#endif
}

int obor_media_diag_dimensions(unsigned width, unsigned height,
                               unsigned retained_frames)
{
    uint64_t pixels = (uint64_t)width * height;
    if (!width || !height || (width & 1) || (height & 1) ||
        !retained_frames || pixels > OBOR_MEDIA_DIAG_BUFFER_BYTES ||
        pixels * 3 / 2 > OBOR_MEDIA_DIAG_BUFFER_BYTES / retained_frames) {
        obor_media_diag_failure("decoded-video-budget");
        return 0;
    }
    return 1;
}

void obor_media_diag_announce(const char *adapter, unsigned video_frames,
                              unsigned audio_bytes)
{
    if (!obor_media_diag_enabled()) return;
    fprintf(stderr, "[obor-media-diag] schema=%d enabled=1 adapter=%s "
            "wait_us=%llu video_frames=%u video_budget_bytes=%llu "
            "audio_ring_bytes=%u packet_limit_bytes=%llu "
            "packet_queue_bytes=%llu guest_clock=unchanged\n",
            OBOR_MEDIA_DIAG_SCHEMA, adapter,
            (unsigned long long)OBOR_MEDIA_DIAG_WAIT_US, video_frames,
            (unsigned long long)OBOR_MEDIA_DIAG_BUFFER_BYTES, audio_bytes,
            (unsigned long long)OBOR_MEDIA_DIAG_PACKET_BYTES,
            (unsigned long long)OBOR_MEDIA_DIAG_QUEUE_BYTES);
}

int obor_media_diag_request(obor_media_diag_gate *gate)
{
    int state = __atomic_load_n(&gate->state, __ATOMIC_ACQUIRE);
    if (state == OBOR_MEDIA_EOF) return 1;
    if (state != OBOR_MEDIA_IDLE && state != OBOR_MEDIA_READY) return 0;
    __atomic_store_n(&gate->state, OBOR_MEDIA_REQUESTED, __ATOMIC_RELEASE);
    return 1;
}

int obor_media_diag_take(obor_media_diag_gate *gate)
{
    int expected = OBOR_MEDIA_REQUESTED;
    return __atomic_compare_exchange_n(&gate->state, &expected,
        OBOR_MEDIA_WRITING, 0, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE);
}

void obor_media_diag_complete(obor_media_diag_gate *gate, int terminal)
{
    __atomic_store_n(&gate->state, terminal ? OBOR_MEDIA_EOF : OBOR_MEDIA_READY,
                     __ATOMIC_RELEASE);
}

int obor_media_diag_gate_probe(void *context)
{
    obor_media_diag_gate *gate = context;
    int state = __atomic_load_n(&gate->state, __ATOMIC_ACQUIRE);
    return state == OBOR_MEDIA_FAILED ? -1 :
        (state == OBOR_MEDIA_READY || state == OBOR_MEDIA_EOF);
}
