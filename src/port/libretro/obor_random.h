/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_RANDOM_IMPLEMENTATION_H
#define OBOR_RANDOM_IMPLEMENTATION_H
#include <stdint.h>
#include <stdlib.h>

/* libc's global rand state lives outside the core's snapshot regions.
 * Keep the game's generator in engine-owned data instead. The Windows
 * sequence and glibc's default 128-byte sequence match their libc controls;
 * other POSIX hosts use their reentrant generator with an owned seed. */
#if defined(__GLIBC__)
static struct random_data obor_random_context;
static int32_t obor_random_buffer[32];
static int obor_random_initialized;

void obor_srand(unsigned int seed)
{
    if (!obor_random_initialized) {
        if (initstate_r(seed, (char *)obor_random_buffer,
                        sizeof(obor_random_buffer), &obor_random_context) == 0)
            obor_random_initialized = 1;
    } else {
        srandom_r(seed, &obor_random_context);
    }
}

int obor_rand(void)
{
    int32_t result = 0;
    if (!obor_random_initialized) obor_srand(1);
    if (obor_random_initialized) random_r(&obor_random_context, &result);
    return result;
}
#else
static unsigned int obor_random_seed = 1;

void obor_srand(unsigned int seed)
{
    obor_random_seed = seed;
}

int obor_rand(void)
{
#ifdef _WIN32
    obor_random_seed = obor_random_seed * 214013u + 2531011u;
    return (int)((obor_random_seed >> 16) & 32767u);
#else
    return rand_r(&obor_random_seed);
#endif
}
#endif
#endif
