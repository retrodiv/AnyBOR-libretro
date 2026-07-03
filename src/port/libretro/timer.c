/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/*
 * AnyBOR timer backend — fully emulated clock.
 *
 * Implements source/gamelib/timer.h against obor_clock_us, which advances
 * 16667 us per yielded frame plus explicit engine sleeps (libretroport.c).
 * No wall-clock reads: same input sequence -> same timing, always. This is
 * what makes save states / rewind deterministic.
 */
#include "libretroport.h"
#include "timer.h"
#include "types.h"

#define GETTIME_FREQ 1000

static unsigned lastinterval;
static unsigned newticks;

void borTimerInit(void) {}
void borTimerExit(void) {}

unsigned timer_gettick(void)
{
    /* A hair of forward motion per read breaks engine busy-waits that poll
     * the clock without sleeping or rendering (e.g. Ghosts'n Demons' loader)
     * — the emulated clock otherwise only advances on frame yields. Still
     * deterministic: time is a pure function of the call sequence. */
    obor_clock_us += 1;
    return (unsigned)(obor_clock_us / 1000ULL);
}

u64 timer_uticks(void)
{
    obor_clock_us += 1;
    return obor_clock_us;
}

unsigned timer_getinterval(unsigned freq)
{
    unsigned tickspassed, ebx, blocksize, now;
    now = timer_gettick() - newticks;
    ebx = now - lastinterval;
    blocksize = GETTIME_FREQ / freq;
    ebx += GETTIME_FREQ % freq;
    tickspassed = ebx / blocksize;
    ebx -= ebx % blocksize;
    lastinterval += ebx;
    return tickspassed;
}

unsigned get_last_interval(void)
{
    return lastinterval;
}

void set_last_interval(unsigned value)
{
    lastinterval = value;
}

void set_ticks(unsigned value)
{
    newticks = value;
}
