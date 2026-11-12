/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_STATE_CONFIG_H
#define OBOR_STATE_CONFIG_H
#include <stdlib.h>
#include <string.h>

/* Runtime policies select their supported platform scope. This flag
 * controls preparation, encoder maintenance and helper policy, not which
 * writer is selected by the frontend or the engine's default settings. */
#if (defined(_WIN32) && (defined(__x86_64__) || defined(_M_X64))) || \
    ((defined(__linux__) || defined(__APPLE__)) && \
     (defined(__x86_64__) || defined(__aarch64__) || (defined(__riscv) && __riscv_xlen == 64)))
#define OBOR_STATE_DEFAULT_ENABLED 1
#else
#define OBOR_STATE_DEFAULT_ENABLED 0
#endif

/* Share writer defaults between the pre-boot size query and every engine.
 * Core options may select another writer when content is loaded. */
#define OBOR_STATE_WRITER_DEFAULT_ENABLED 1
#define OBOR_STATE_CONTENT_DEFAULT "Smart"
#define OBOR_STATE_COMPRESSION_DEFAULT "On"
#define OBOR_STATE_CONTENT_VALUES "Smart|Full"
#define OBOR_STATE_COMPRESSION_VALUES "On|Off"

/* Zero preserves the writer default for callers that do not provide core
 * options. Each localized engine and the glue own a separate runtime copy;
 * loading a state must never change the current session's writer selection. */
enum { OBOR_STATE_SETTING_DEFAULT, OBOR_STATE_SETTING_ON, OBOR_STATE_SETTING_OFF };
typedef struct { int content, compression; } obor_state_settings;
extern obor_state_settings obor_state_session_settings;

static inline int obor_state_setting_enabled(int setting)
{
    if (setting == OBOR_STATE_SETTING_ON) return 1;
    if (setting == OBOR_STATE_SETTING_OFF) return 0;
    return OBOR_STATE_WRITER_DEFAULT_ENABLED;
}

/* Overrides are for diagnosis, not game selection. Invalid values retain the
 * selected policy. Explicit 0 permits unchanged-code ON/OFF comparisons. */
static inline int obor_state_option(const char *name, int fallback)
{
    const char *value = getenv(name);
    if (value && !strcmp(value, "0")) return 0;
    if (value && !strcmp(value, "1")) return 1;
    return fallback;
}

static inline int obor_state_coded_enabled(void)
{
    int content = obor_state_setting_enabled(obor_state_session_settings.content);
    int compression = obor_state_setting_enabled(obor_state_session_settings.compression);
    return obor_state_option("OBOR_COMPRESSED_STATES", content || compression);
}

static inline int obor_state_resources_enabled(void)
{
    return obor_state_coded_enabled() &&
        obor_state_option("OBOR_RESOURCE_STATES",
            obor_state_setting_enabled(obor_state_session_settings.content));
}

static inline int obor_state_raw_mutable_enabled(void)
{
    return obor_state_option("OBOR_STATE_RAW_MUTABLE",
        !obor_state_setting_enabled(obor_state_session_settings.compression));
}

static inline int obor_state_worker_watch_enabled(void)
{
    /* The classic movie adapter publishes and joins every decoder worker on
     * the engine owner. The asynchronous movie layer has nested/third-party
     * workers outside that contract and must invalidate its page proofs. */
#if (defined(__linux__) || defined(__APPLE__) || defined(_WIN32)) && \
    (defined(__x86_64__) || defined(__aarch64__) || defined(_M_X64) || \
     (defined(__riscv) && __riscv_xlen == 64)) && !defined(OBOR_HAS_MOVIE_PLAYBACK)
    return obor_state_option("OBOR_STATE_WORKER_WATCH", 1);
#else
    return 0;
#endif
}

static inline int obor_state_audio_first(void)
{
    /* Stock Windows frontend tests show less capture-correlated presentation
     * delay when its audio wait precedes video delivery. This benefit was not
     * reproduced on ARM64 Linux; retain the original order on other targets. */
#if defined(_WIN32) && (defined(__x86_64__) || defined(_M_X64))
    return obor_state_option("OBOR_AUDIO_BEFORE_VIDEO", 1);
#else
    return obor_state_option("OBOR_AUDIO_BEFORE_VIDEO", 0);
#endif
}
#endif
