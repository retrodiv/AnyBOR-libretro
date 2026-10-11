/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Standalone component: no frontend, game, or state payload. */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#if defined(_WIN32)
#include <windows.h>
#endif
#define OBOR_RUNTIME
#include "obor_latency_boundaries.h"

static void variable(const char *value)
{
#if defined(_WIN32)
    assert(_putenv_s("OBOR_DIAG_LATENCY_BOUNDARIES", value) == 0);
#else
    assert(setenv("OBOR_DIAG_LATENCY_BOUNDARIES", value, 1) == 0);
#endif
}
static void delay(void)
{
#if defined(_WIN32)
    Sleep(5);
#else
    struct timespec remaining = {0, 5000000};
    while (nanosleep(&remaining, &remaining) && errno == EINTR) { }
#endif
}
static int early_return(long *frame)
{
    obor_latency_run_scope scope(frame);
    uint64_t begin = obor_latency_begin();
    delay();
    obor_latency_end(OBOR_LATENCY_VIDEO_CALLBACK, *frame, begin);
    ++*frame;
    return 7;
}
int main(int argc, char **argv)
{
    assert(argc == 3 && sizeof(obor_latency_row) == 32);
    variable(""); obor_latency_init();
    assert(!g_latency.rows && !g_latency.file && !obor_latency_begin());
    assert(obor_latency_close());

    variable(argv[1]); obor_latency_init();
    assert(g_latency.rows && g_latency.file);
    assert(g_latency.count == 0);
    assert(fflush(g_latency.file) == 0 && ftell(g_latency.file) == 0);
    long frame = 10;
    assert(early_return(&frame) == 7 && frame == 11 && g_latency.count == 2);
    assert(g_latency.rows[0].event == OBOR_LATENCY_VIDEO_CALLBACK);
    assert(g_latency.rows[0].frame == 10);
    assert(g_latency.rows[0].end - g_latency.rows[0].begin >= 1000000);
    assert(g_latency.rows[1].event == OBOR_LATENCY_RETRO_RUN);
    assert(g_latency.rows[1].frame == 11);
    assert(g_latency.rows[1].begin <= g_latency.rows[0].begin);
    assert(g_latency.rows[1].end >= g_latency.rows[0].end);
    /* No data was written while the timing events accumulated. */
    assert(fflush(g_latency.file) == 0 && ftell(g_latency.file) == 0);
    assert(obor_latency_close());
    assert(!g_latency.rows && !g_latency.file && !g_latency.initialized);
    FILE *first = fopen(argv[1], "rb"); assert(first);
    char saved[2048]; size_t bytes = fread(saved, 1, sizeof(saved), first);
    assert(bytes > 0 && bytes < sizeof(saved)); assert(!ferror(first)); fclose(first);
    /* An existing receipt must not be truncated, opened, or appended to. */
    obor_latency_init(); assert(!g_latency.file && !g_latency.rows);
    assert(obor_latency_close());
    first = fopen(argv[1], "rb"); assert(first);
    char again[2048]; assert(fread(again, 1, sizeof(again), first) == bytes);
    assert(!memcmp(saved, again, bytes)); fclose(first);

    variable(argv[2]); obor_latency_init(); assert(g_latency.rows);
    for (unsigned i = 0; i < OBOR_LATENCY_MAX_ROWS + 17; ++i)
        obor_latency_record(OBOR_LATENCY_PROFILE_WRITE, i, 100+i, 101+i);
    assert(g_latency.count == OBOR_LATENCY_MAX_ROWS && g_latency.dropped == 17);
    assert(g_latency.rows[0].frame == 0);
    assert(g_latency.rows[OBOR_LATENCY_MAX_ROWS-1].frame == OBOR_LATENCY_MAX_ROWS-1);
    assert(obor_latency_close());
    first = fopen(argv[2], "rb"); assert(first);
    char line[128]; unsigned lines = 0; int complete = 0;
    while (fgets(line, sizeof(line), first)) {
        ++lines;
        if (!strcmp(line, "summary,65536,17,0\n")) complete = 1;
    }
    assert(!ferror(first) && lines == OBOR_LATENCY_MAX_ROWS+2 && complete);
    fclose(first);
    variable(""); obor_latency_init(); assert(!g_latency.rows);
    assert(obor_latency_close());
    puts("{\"pass\":true,\"max_rows\":65536,\"bounded_bytes\":2097152,\"dropped\":17,\"normal_mode\":\"disabled\",\"game_acceptance\":false}");
}
