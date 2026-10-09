/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_STATE_CONFIG_H
#define OBOR_STATE_CONFIG_H
#include <stdlib.h>
#include <string.h>

/* Share policy between the frontend's pre-boot size query and every engine.
 * Other targets retain their existing writer until equivalent reconstruction
 * and presentation checks have been completed there. */
#if (defined(_WIN32) && (defined(__x86_64__) || defined(_M_X64))) || \
    (defined(__linux__) && !defined(__ANDROID__) && \
     (defined(__x86_64__) || defined(__aarch64__)))
#define OBOR_STATE_DEFAULT_ENABLED 1
#else
#define OBOR_STATE_DEFAULT_ENABLED 0
#endif

/* Overrides are for diagnosis, not game selection. Invalid values retain the
 * platform policy. Explicit 0 permits unchanged-code ON/OFF comparisons. */
static inline int obor_state_option(const char *name, int fallback)
{
    const char *value = getenv(name);
    if (value && !strcmp(value, "0")) return 0;
    if (value && !strcmp(value, "1")) return 1;
    return fallback;
}

static inline int obor_state_coded_enabled(void)
{
    return obor_state_option("OBOR_COMPRESSED_STATES", OBOR_STATE_DEFAULT_ENABLED);
}

static inline int obor_state_resources_enabled(void)
{
    return obor_state_coded_enabled() &&
        obor_state_option("OBOR_RESOURCE_STATES", OBOR_STATE_DEFAULT_ENABLED);
}

static inline int obor_state_worker_watch_enabled(void)
{
    /* The classic movie adapter publishes and joins every decoder worker on
     * the engine owner. The asynchronous movie layer has nested/third-party
     * workers outside that contract and must invalidate its page proofs. */
#if defined(__linux__) && !defined(__ANDROID__) && \
    (defined(__x86_64__) || defined(__aarch64__)) && !defined(OBOR_HAS_MOVIE_PLAYBACK)
    return obor_state_option("OBOR_STATE_WORKER_WATCH", 1);
#else
    return 0;
#endif
}

static inline int obor_state_audio_first(void)
{
    /* Stock Windows frontend tests show less capture-correlated presentation
     * delay when its audio wait precedes video delivery. This benefit was not
     * reproduced on Recalbox; retain the original order on other targets. */
#if defined(_WIN32) && (defined(__x86_64__) || defined(_M_X64))
    return obor_state_option("OBOR_AUDIO_BEFORE_VIDEO", 1);
#else
    return obor_state_option("OBOR_AUDIO_BEFORE_VIDEO", 0);
#endif
}
#endif
