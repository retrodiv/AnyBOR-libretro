/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_DETECTION_CLOCK_H
#define OBOR_DETECTION_CLOCK_H
#include <stdint.h>
#include <time.h>

/* System clock only: the glue must not depend on the C++ standard library. */
static uint64_t obor_detection_now(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) return UINT64_MAX;
    return (uint64_t)ts.tv_sec * 1000ULL + (uint64_t)ts.tv_nsec / 1000000ULL;
}

static bool obor_detection_expired(uint64_t started)
{
    uint64_t now = obor_detection_now();
    return started == UINT64_MAX || now == UINT64_MAX || now < started || now - started >= 750;
}
#endif
