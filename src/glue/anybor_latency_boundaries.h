/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Bounded opt-in latency boundaries. No frame/state payloads are retained. */
#ifndef OBOR_LATENCY_BOUNDARIES_H
#define OBOR_LATENCY_BOUNDARIES_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <fcntl.h>
#if defined(_WIN32)
#include <io.h>
#include <sys/stat.h>
#else
#include <unistd.h>
#endif

#define OBOR_LATENCY_MAX_ROWS 65536u
#define OBOR_LATENCY_VIDEO_PREPARE 1u
#define OBOR_LATENCY_VIDEO_CALLBACK 2u
#define OBOR_LATENCY_PROFILE_WRITE 3u
#define OBOR_LATENCY_RETRO_RUN 4u
#define OBOR_LATENCY_AUDIO_CALLBACK 5u

typedef struct {
    uint64_t begin, end;
    int64_t frame;
    uint32_t event, reserved;
} obor_latency_row;
typedef struct {
    FILE *file;
    obor_latency_row *rows;
    uint64_t dropped;
    unsigned count;
    int initialized;
} obor_latency_state;
/* Runtime bookkeeping must survive restore without being part of a state. */
static obor_latency_state g_latency OBOR_RUNTIME;

static uint64_t obor_latency_now(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) return 0;
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static void obor_latency_init(void)
{
    if (g_latency.initialized) return;
    g_latency.initialized = 1;
    const char *path = getenv("OBOR_DIAG_LATENCY_BOUNDARIES");
    if (!path || !*path) return;
#if defined(_WIN32)
    int fd = _open(path, _O_WRONLY | _O_CREAT | _O_EXCL | _O_BINARY,
                   _S_IREAD | _S_IWRITE);
#else
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL, 0600);
#endif
    if (fd < 0) return;
#if defined(_WIN32)
    g_latency.file = _fdopen(fd, "wb");
    if (!g_latency.file) _close(fd);
#else
    g_latency.file = fdopen(fd, "w");
    if (!g_latency.file) close(fd);
#endif
    if (!g_latency.file) return;
    g_latency.rows = (obor_latency_row *)calloc(OBOR_LATENCY_MAX_ROWS,
                                               sizeof(obor_latency_row));
    if (!g_latency.rows) {
        fclose(g_latency.file);
        g_latency.file = NULL;
    }
}

static uint64_t obor_latency_begin(void)
{
    return g_latency.rows ? obor_latency_now() : 0;
}

static void obor_latency_record(unsigned event, long frame, uint64_t begin,
                                 uint64_t end)
{
    if (!g_latency.rows || !begin || end < begin) return;
    if (g_latency.count >= OBOR_LATENCY_MAX_ROWS) {
        if (g_latency.dropped != UINT64_MAX) ++g_latency.dropped;
        return;
    }
    obor_latency_row *row = &g_latency.rows[g_latency.count++];
    row->begin = begin; row->end = end;
    row->frame = frame; row->event = event;
}

static void obor_latency_end(unsigned event, long frame, uint64_t begin)
{
    if (begin) obor_latency_record(event, frame, begin, obor_latency_now());
}

static int obor_latency_close(void)
{
    int ok = 1;
    if (g_latency.file) {
        if (fputs("event,frame,begin_ns,end_ns\n", g_latency.file) < 0) ok = 0;
        for (unsigned i = 0; i < g_latency.count && ok; ++i) {
            const obor_latency_row *r = &g_latency.rows[i];
            if (fprintf(g_latency.file, "%u,%lld,%llu,%llu\n", r->event,
                        (long long)r->frame, (unsigned long long)r->begin,
                        (unsigned long long)r->end) < 0) ok = 0;
        }
        /* Explicit completeness, not an apparent successful truncated trace. */
        if (ok && fprintf(g_latency.file, "summary,%u,%llu,0\n", g_latency.count,
                          (unsigned long long)g_latency.dropped) < 0) ok = 0;
        if (fclose(g_latency.file) != 0) ok = 0;
    }
    free(g_latency.rows);
    memset(&g_latency, 0, sizeof(g_latency));
    return ok;
}

#ifdef __cplusplus
class obor_latency_run_scope {
    uint64_t begin;
    const long *frame;
public:
    explicit obor_latency_run_scope(const long *value)
        : begin(obor_latency_begin()), frame(value) {}
    ~obor_latency_run_scope()
    { obor_latency_end(OBOR_LATENCY_RETRO_RUN, *frame, begin); }
    obor_latency_run_scope(const obor_latency_run_scope&) = delete;
    obor_latency_run_scope& operator=(const obor_latency_run_scope&) = delete;
};
#endif
#endif
