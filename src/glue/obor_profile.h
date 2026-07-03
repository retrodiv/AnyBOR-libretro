/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Opt-in measurement of the real frontend. No game-specific routes or data.
 */
#ifndef OBOR_PROFILE_H
#define OBOR_PROFILE_H

#include <time.h>
#include <fcntl.h>
#if defined(_WIN32)
#include <io.h>
#include <sys/stat.h>
#else
#include <unistd.h>
#endif

typedef struct {
    FILE *file;
    unsigned rows;
    int initialized;
} obor_profile_state;

static obor_profile_state g_profile;

static uint64_t obor_profile_now(void)
{
    if (!g_profile.file)
        return 0;
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0)
        return 0;
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static void obor_profile_init(void)
{
    if (g_profile.initialized)
        return;
    g_profile.initialized = 1;
    const char *path = getenv("OBOR_PROFILE");
    if (!path || !*path)
        return;
    /* Never truncate an earlier receipt or another process's profile. */
#if defined(_WIN32)
    int fd = _open(path, _O_WRONLY | _O_CREAT | _O_EXCL | _O_BINARY,
                   _S_IREAD | _S_IWRITE);
    if (fd >= 0) {
        g_profile.file = _fdopen(fd, "wb");
        if (!g_profile.file)
            _close(fd);
    }
#else
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL, 0600);
    if (fd >= 0) {
        g_profile.file = fdopen(fd, "w");
        if (!g_profile.file)
            close(fd);
    }
#endif
    if (g_profile.file)
        fputs("event,frame,begin_ns,core_end_ns,end_ns,capacity,written,heap,ok,context\n",
              g_profile.file);
}

static void obor_profile_record(const char *event, long frame, uint64_t begin,
                                uint64_t core_end, size_t capacity,
                                size_t written, uint64_t heap, int ok,
                                int context)
{
    if (!g_profile.file)
        return;
    uint64_t end = obor_profile_now();
    /* At most 200000 short CSV rows (under 32 MiB). Never retain states. */
    if (g_profile.rows < 200000) {
        fprintf(g_profile.file, "%s,%ld,%llu,%llu,%llu,%zu,%zu,%llu,%d,%d\n",
                event, frame, (unsigned long long)begin,
                (unsigned long long)core_end, (unsigned long long)end,
                capacity, written, (unsigned long long)heap, ok, context);
        ++g_profile.rows;
        if (!(g_profile.rows % 60))
            fflush(g_profile.file);
    } else {
        fputs("limit,0,0,0,0,0,0,0,0,-1\n", g_profile.file);
        fclose(g_profile.file);
        g_profile.file = NULL;
    }
}

static void obor_profile_close(void)
{
    if (g_profile.file)
        fclose(g_profile.file);
    memset(&g_profile, 0, sizeof(g_profile));
}

#endif
