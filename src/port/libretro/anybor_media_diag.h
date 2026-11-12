/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_MEDIA_DIAG_H
#define OBOR_MEDIA_DIAG_H

/* Developer-only scheduling policy. Does not read or change guest time/RNG.
 * A failed barrier invalidates the diagnostic run; never yield guest frames
 * or silently fall back to timing-dependent production scheduling. */
#define OBOR_MEDIA_DIAG_SCHEMA 1
#define OBOR_MEDIA_DIAG_WAIT_US 2000000ULL
#define OBOR_MEDIA_DIAG_BUFFER_BYTES (64ULL * 1024 * 1024)
#define OBOR_MEDIA_DIAG_PACKET_BYTES (2ULL * 1024 * 1024)
#define OBOR_MEDIA_DIAG_QUEUE_BYTES (16ULL * 1024 * 1024)
typedef int (*obor_media_diag_probe)(void *context);
int obor_media_diag_enabled(void);
int obor_media_diag_wait(obor_media_diag_probe probe, void *context,
                         const char *phase);
void obor_media_diag_failure(const char *phase);
int obor_media_diag_dimensions(unsigned width, unsigned height,
                               unsigned retained_frames);
void obor_media_diag_announce(const char *adapter, unsigned video_frames,
                              unsigned audio_bytes);

/* Single owner/producer handshake. The owner cannot mix while the producer
 * writes the legacy music ring. EOF is successful terminal readiness. */
typedef struct { int state; } obor_media_diag_gate;
enum { OBOR_MEDIA_IDLE, OBOR_MEDIA_REQUESTED, OBOR_MEDIA_WRITING,
       OBOR_MEDIA_READY, OBOR_MEDIA_EOF, OBOR_MEDIA_FAILED };
int obor_media_diag_request(obor_media_diag_gate *gate);
int obor_media_diag_take(obor_media_diag_gate *gate);
void obor_media_diag_complete(obor_media_diag_gate *gate, int terminal);
int obor_media_diag_gate_probe(void *gate);

#ifdef WEBM
/* Adapter owns decoder-specific readiness; the common mixer calls it before
 * taking the audio lock, so the producer can replenish its bounded reserve. */
int obor_webm_diag_audio_prepare(void);
#endif
#endif
