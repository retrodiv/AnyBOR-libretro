/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/* AnyBOR glue: the libretro scaffolding of the single-file core.
 *
 * Contains NO engine code. Pinned engine revisions are linked in as partial
 * objects whose only visible symbols are their suffixed obor_* ABI (see
 * anybor_engines.h, generated from pin.json). At retro_load_game — and again
 * at retro_reset — the glue detects which OpenBOR build the pak needs
 * (core option -> external override -> verified engine executable -> explicit special profile -> legacy API -> filename tag
 * -> sidecar exe -> content scan -> fallback),
 * points g_vtbl at that engine and shuttles video/audio/input.
 */
#include "anybor_file_io.h"
#include <ctype.h>
#include <limits.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <stdlib.h>
#include <string.h>
#if !defined(_WIN32)
#include <unistd.h>
#include <dlfcn.h>
#endif

#include "libretro.h"
#include "anybor_abi.h"
#include "anybor_build_identity.h"
#include "anybor_runtime.h"
#include "anybor_engine_resources.h"
#include "anybor_notices.h"
#include "anybor_crt.h"
#include "anybor_error_screen.h"
#include "anybor_loading_screen.h"
#include "anybor_video_config.h"
#include "anybor_prepare_co.h"
#include "anybor_prepare_progress.h"
#include "anybor_state_padding.h"
#include "../port/libretro/anybor_block_state.h"
#include "../port/libretro/anybor_state_config.h"
#include "anybor_latency_boundaries.h"
#include "anybor_profile.h"
#include "anybor_rewind.h"
#if defined(__APPLE__)
/* Mach-O image introspection: writable snapshot ranges (pristine capture)
 * and the per-engine state sections of this same image. */
#include "anybor_macho.h"
#endif

static void mkdir_p(const char *path);
#include "anybor_storage.h"

static bool g_arena_owned;
#include "anybor_engines.h"
#include "anybor_capture_cadence.h"
#include "anybor_debug.h"
#include "anybor_padmap.h"

#if defined(_WIN32)
#define PATH_SEP '\\'
#else
#define PATH_SEP '/'
#endif

/* ---------------------------------------------------------------- state */

static retro_environment_t env_cb;
static retro_video_refresh_t video_cb;
static retro_audio_sample_batch_t audio_batch_cb;
static retro_input_poll_t input_poll_cb;
static retro_input_state_t input_state_cb;
static retro_log_printf_t log_cb;

obor_state_settings obor_state_session_settings OBOR_RUNTIME;

static void fallback_log(enum retro_log_level level, const char *fmt, ...)
{
    (void)level;
    va_list va;
    va_start(va, fmt);
    vfprintf(stderr, fmt, va);
    va_end(va);
}

static const obor_vtbl *g_vtbl;
static bool g_booted;
static bool g_startup_reported;
static bool g_error_active;
static bool g_fault_pending;
static char g_error_reason[512];
static bool g_engine_error_context, g_engine_log_fresh;
static char g_error_engine[48];
static char g_error_path[4096];
static uint32_t g_error_pixels[OBOR_ERROR_WIDTH * OBOR_ERROR_HEIGHT];
static uint32_t g_state_capacity;
static bool g_variable_state_size;
static bool g_loading, g_loading_done, g_loading_ok, g_loading_cancel;
static bool g_loading_first, g_loading_retry;
static void *g_loading_stack, *g_loading_context, *g_loading_frontend;
static uint64_t g_loading_yield;
static uint32_t *g_loading_pixels; /* ephemeral presentation, never an engine state */
static int g_loading_width, g_loading_height;
static unsigned g_startup_model_percent OBOR_RUNTIME;
static int g_width = 320, g_height = 240;
static int g_source_width = 320, g_source_height = 240;
static float g_aspect = 4.0f / 3.0f;
static unsigned g_max_width = 1920, g_max_height = 1080;
static bool g_av_announced;
static constexpr unsigned kNativeRefresh = 60;
struct presentation_timing {
    unsigned fps, requested, phase;
};
static presentation_timing g_presentation_timing = {kNativeRefresh, kNativeRefresh, 0};
static void output_geometry(int width, int height, bool notify,
                            unsigned required_width = 0, unsigned required_height = 0,
                            float aspect = 0.0f);
/* Outside engine states. Keep both buffers when composition and rotation are needed. */
struct video_buffer {
    uint32_t *pixels;
    size_t capacity;
};
static video_buffer g_window_buffer, g_crt_buffer, g_shift_buffer, g_rotation_buffer;
static int g_content_level = -1;

static char g_engine[48];           /* physical engine actually loaded */
static char g_logical_engine[48];   /* selected logical compatibility profile */
static char g_selection_error[160];
static char g_save_dir[1024];
static char g_game_dir[1600];
static char g_pak_path[4096];
/* Preserve the adjacent-engine location across packed-content preparation. */
static char g_engine_source_path[4096];
static bool g_raw; /* content is an unpacked mod dir, not a .pak */

/* frame counter + rewind/trace bookkeeping (used across sections) */
static FILE *g_trace;
static long g_frame_no;
static long g_last_unser = -99;
static bool g_fault_quarantined;
static obor_capture_cadence g_capture_cadence OBOR_RUNTIME;
/* Current frontend playback direction, never part of the restored world. */
static bool g_reverse_has_snapshot OBOR_RUNTIME;
/* Diagnostic input clocks belong to the current frontend process. */
static bool g_input_after_load OBOR_RUNTIME;
static bool g_input_has_origin OBOR_RUNTIME;
static long g_input_origin OBOR_RUNTIME;

#define p_abi_version (g_vtbl->abi_version)
#define p_boot (g_vtbl->boot)
#define p_run_frame (g_vtbl->run_frame)
#define p_startup_complete (g_vtbl->startup_complete)
#define p_get_exit_status (g_vtbl->get_exit_status)
#define p_get_fault_message (g_vtbl->get_fault_message)
#define p_abandon (g_vtbl->abandon)
#define p_get_video (g_vtbl->get_video)
#define p_set_button (g_vtbl->set_button)
#define p_get_audio (g_vtbl->get_audio)
#define p_serialize_size (g_vtbl->serialize_size)
#define p_serialize (g_vtbl->serialize)
#define p_unserialize (g_vtbl->unserialize)
#define p_shutdown (g_vtbl->shutdown)
#define p_get_rumble (g_vtbl->get_rumble)
#define p_get_arena (g_vtbl->get_arena)
#define p_get_player_state (g_vtbl->get_player_state)
#define p_owned_begin (g_vtbl->owned_begin)
#define p_owned_serialize (g_vtbl->owned_serialize)
#define p_owned_end (g_vtbl->owned_end)
#define p_prepare_state (g_vtbl->prepare_state)

static void decide_engine(void);
static void glue_collect_segments(void);
static void pristine_capture(void);
static void pristine_restore(void);
static bool select_engine_vtbl(const char *engine, char *err, int err_len);
static bool obor_load_retry(const struct retro_game_info *info);
static void stop_faulted_engine(void);
static void loading_dispose(void);
static bool loading_begin(const struct retro_game_info *info, bool retry);
static void loading_run(void);
static bool loading_image(const char *path, bool notify, bool raw = false);
static bool loading_image_size(int width, int height, bool notify);
static void glue_dump_maybe(const uint32_t *px, int w, int h, int pitch_px);

/* ------------------------------------------------- version detection --- */

/* Sparse (commit date -> build) milestones, generated from upstream git
 * history (build number == upstream commit count). Used to translate
 * a sidecar exe's "Compile Date" into a build when no Build label exists.
 * A Build label with a missing number is inconclusive, regardless of date. */
struct date_build { int yyyymm; int build; };
static const struct date_build kDateMap[] = {
    { 200607, 1 },    { 200701, 451 },  { 200801, 1279 }, { 200901, 2200 },
    { 200906, 2310 }, { 201001, 2618 }, { 201101, 2955 }, { 201201, 3654 },
    { 201207, 3711 }, { 201301, 3747 }, { 201401, 4055 }, { 201501, 4099 },
    { 201601, 4165 }, { 201701, 4425 }, { 201705, 4520 }, { 201801, 4600 },
    { 201805, 6119 }, { 201808, 6390 }, { 201809, 6448 }, { 201901, 6700 },
    { 201912, 7142 }, { 202101, 7300 }, { 202401, 7533 }, { 202601, 7800 },
};

static int date_to_build(int year, int month)
{
    int ym = year * 100 + month;
    int best = OBOR_FALLBACK_BUILD;
    for (size_t i = 0; i < sizeof(kDateMap) / sizeof(kDateMap[0]); i++) {
        if (kDateMap[i].yyyymm <= ym)
            best = kDateMap[i].build;
        else
            break;
    }
    return best;
}

struct filename_build_interval { int lower, upper; bool lower_known, upper_known; };

static bool profile_is_revision(const obor_profile_def *profile)
{
    char revision[12];
    snprintf(revision, sizeof(revision), "%d", profile->build);
    return !strcmp(profile->name, revision);
}

static bool build_variant_separator(char c)
{
    return c == ' ' || c == '-' || c == '_';
}

/* A word following a separator may name a table-defined variant. Unknown
 * words retain ordinary numeric routing; numeric ranges stay ranges. */
static bool build_variant_suffix(const char *p)
{
    if (!build_variant_separator(*p)) return false;
    while (build_variant_separator(*p)) ++p;
    return isalpha((unsigned char)*p) != 0;
}

static bool build_interval_endpoint(const char **cursor, int unknown, int *value)
{
    const char *p = *cursor;
    if (strncasecmp(p, "XXXX", 4) == 0) {
        *value = unknown;
        *cursor = p + 4;
        return true;
    }
    if (!isdigit((unsigned char)*p))
        return false;
    int n = 0, digits = 0;
    while (isdigit((unsigned char)*p)) {
        int digit = *p++ - '0';
        if (n > (INT_MAX - digit) / 10)
            return false;
        n = n * 10 + digit;
        ++digits;
    }
    bool partial = false;
    while (*p == 'X' || *p == 'x') {
        if (++digits > 5 || n > (INT_MAX - 9) / 10) return false;
        n = n * 10 + (unknown == INT_MAX ? 9 : 0);
        partial = true;
        ++p;
    }
    if (partial && (digits < 4 || n < 1000)) return false;
    if (n < 1)
        return false;
    *value = n;
    *cursor = p;
    return true;
}

/* Only a version directly attached to this Build tag constrains it. A title's
 * release version or a version in another bracket is not engine evidence. */
static int build_tag_generation(const char *base, const char *build)
{
    for (const char *p = base; p < build; ++p) {
        if (*p != 'v' && *p != 'V') continue;
        const char *q = p + 1;
        if (q < build && *q == '.') ++q;
        if (build - q < 3 || (q[0] != '3' && q[0] != '4') ||
            q[1] != '.' || q[2] != '0') continue;
        int generation = q[0] - '0';
        q += 3;
        while (q < build && (*q == ' ' || *q == '_' || *q == '.' || *q == '-')) ++q;
        if (q == build) return generation;
    }
    return 0;
}

/* Only an explicit whole variant word can select a nonautomatic variant.
 * Variant vocabulary and behavior come from kProfiles, never content or a
 * fixed list of suffixes. Partial/range tags intersect the same table. */
static const obor_profile_def *profile_variant_from_filename(const char *path)
{
    const char *base = strrchr(path, PATH_SEP);
    base = base ? base + 1 : path;
    for (const char *p = base; *p; ++p) {
        if ((p != base && (isalnum((unsigned char)p[-1]) || p[-1] == '_')) ||
            strncasecmp(p, "build ", 6)) continue;
        const char *first = p + 6;
        while (*first == ' ') ++first;
        const char *q = first, *high_end = first;
        int lower, upper;
        if (!build_interval_endpoint(&q, 0, &lower) ||
            !build_interval_endpoint(&high_end, INT_MAX, &upper)) continue;
        bool ranged = false, partial = false;
        for (const char *digit = first; digit < q; ++digit)
            if (*digit == 'X' || *digit == 'x') partial = true;
        if (*q == '-' && (isdigit((unsigned char)q[1]) || q[1] == 'X' || q[1] == 'x')) {
            const char *end = q + 1;
            if (!build_interval_endpoint(&end, INT_MAX, &upper)) continue;
            q = end;
            ranged = true;
        } else if (!isdigit((unsigned char)*first)) continue;
        if (!ranged && (lower < 1000 || upper > 99999)) continue;
        if (!ranged && !partial && (*q == '-' || *q == '_') && !build_variant_suffix(q)) continue;
        if (lower > upper || isalnum((unsigned char)*q)) continue;
        if (!build_variant_suffix(q)) return NULL;
        while (build_variant_separator(*q)) ++q;
        int generation = build_tag_generation(base, p);
        const obor_profile_def *best = NULL;
        for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); ++i) {
            const obor_profile_def *profile = &kProfiles[i];
            size_t length = strlen(profile->variant);
            if (!length || !profile->tagged || profile->build < lower || profile->build > upper ||
                strncasecmp(q, profile->variant, length) || isalnum((unsigned char)q[length]) ||
                q[length] == '-' || q[length] == '_') continue;
            if ((generation == 3 && strncmp(profile->disp, "v3.0 ", 5)) ||
                (generation == 4 && strncmp(profile->disp, "v4.0 ", 5))) continue;
            if (!best || profile->build > best->build) best = profile;
        }
        return best;
    }
    return NULL;
}

static int pick_anchor(int build);

/* Automatic logical revisions refine an existing physical engine era. */
static bool profile_has_automatic_variants(int engine_build)
{
    for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); ++i)
        if (kProfiles[i].automatic && kProfiles[i].engine_build == engine_build &&
            kProfiles[i].build != engine_build) return true;
    return false;
}

static bool declared_build_has_variants(int build)
{
    int anchor = pick_anchor(build);
    for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); ++i)
        if (kProfiles[i].build == anchor)
            return profile_has_automatic_variants(kProfiles[i].engine_build);
    return false;
}

static int profile_in_range(int lower, int upper, bool automatic_only)
{
    int best = 0;
    for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); ++i) {
        const obor_profile_def *p = &kProfiles[i];
        if (p->automatic && (automatic_only || p->tagged) && p->build >= lower && p->build <= upper &&
            ((p->engine_build >= lower && p->engine_build <= upper) ||
             (p->automatic && p->build != p->engine_build)) && p->build > best)
            best = p->build;
    }
    return best;
}

/* An uncovered range uses the first automatic revision beyond its upper bound.
 * Explicit-only aliases never masquerade as a newer physical engine. */
static int profile_for_range(int lower, int upper, bool automatic_only)
{
    int best = profile_in_range(lower, upper, automatic_only);
    if (best) return best;
    int next_build = INT_MAX;
    for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); ++i) {
        const obor_profile_def *p = &kProfiles[i];
        if (p->automatic && (automatic_only || p->tagged) &&
            p->build > upper && p->build >= lower &&
            p->build < next_build) {
            best = p->build;
            next_build = p->build;
        }
    }
    return best;
}

/* Inclusive evidence bounds, independent of the engines currently linked.
 * XXXX denotes an unknown endpoint, not an asserted build number. */
static bool build_interval_from_filename(const char *path,
                                         filename_build_interval *interval)
{
    const char *base = strrchr(path, PATH_SEP);
    base = base ? base + 1 : path;
    for (const char *p = base; *p; ++p) {
        if ((p != base && (isalnum((unsigned char)p[-1]) || p[-1] == '_')) ||
            strncasecmp(p, "build ", 6) != 0)
            continue;
        const char *q = p + 6;
        while (*q == ' ') ++q;
        int lower, upper;
        bool lower_known = isdigit((unsigned char)*q) != 0;
        if (!build_interval_endpoint(&q, 0, &lower) || *q++ != '-')
            continue;
        bool upper_known = isdigit((unsigned char)*q) != 0;
        if (!build_interval_endpoint(&q, INT_MAX, &upper) ||
            isalnum((unsigned char)*q) || *q == '_' || *q == '-' || lower > upper)
            continue;
        int generation = build_tag_generation(base, p);
        if (generation == 3 && upper > 7532) { upper = 7532; upper_known = true; }
        if (generation == 4 && lower < 7142) { lower = 7142; lower_known = true; }
        interval->lower = lower;
        interval->upper = upper;
        interval->lower_known = lower_known;
        interval->upper_known = upper_known;
        return true;
    }
    return false;
}

static void format_build_interval(const filename_build_interval *interval,
                                  char *out, size_t size)
{
    char lower[12] = "XXXX", upper[12] = "XXXX";
    if (interval->lower_known) snprintf(lower, sizeof(lower), "%d", interval->lower);
    if (interval->upper_known) snprintf(upper, sizeof(upper), "%d", interval->upper);
    snprintf(out, size, "%s-%s", lower, upper);
}

/* Parse complete builds or a numeric prefix followed by trailing X digits.
 * A partial tag selects the highest available profile in its interval,
 * using automatic profiles. With no match, its upper endpoint goes
 * through normal automatic routing. profile is zero for that fallback and
 * for complete tags, whose existing special-profile handling stays below. */
static int build_from_filename(const char *path, int *profile)
{
    *profile = 0;
    filename_build_interval interval;
    if (build_interval_from_filename(path, &interval)) {
        int best = profile_for_range(interval.lower, interval.upper, false);
        *profile = best ? best : -1;
        return best;
    }
    const char *base = strrchr(path, PATH_SEP);
    base = base ? base + 1 : path;
    const char *p = base;
    while (*p) {
        if ((p == base || (!isalnum((unsigned char)p[-1]) && p[-1] != '_')) &&
            strncasecmp(p, "build ", 6) == 0) {
            const char *q = p + 6;
            while (*q == ' ') ++q;
            if (isdigit((unsigned char)*q)) {
                int lower = 0, upper = 0, digits = 0;
                while (isdigit((unsigned char)*q)) {
                    if (digits < 5)
                        lower = lower * 10 + (*q - '0');
                    ++digits;
                    ++q;
                }
                /* Keep complete-tag parsing, including leading zeroes. */
                if ((!isalnum((unsigned char)*q) && *q != '_' && *q != '-') ||
                    build_variant_suffix(q)) {
                    const char *start = q - digits;
                    while (start < q && *start == '0') ++start;
                    if (q - start <= 5) {
                        int v = atoi(start);
                        if (v >= 1000 && v <= 99999)
                            return v;
                    }
                } else if (*q == 'X' || *q == 'x') {
                    upper = lower;
                    while (*q == 'X' || *q == 'x') {
                        if (digits < 5) {
                            lower *= 10;
                            upper = upper * 10 + 9;
                        }
                        ++digits;
                        ++q;
                    }
                    if (digits <= 5 && lower >= 1000 &&
                        !isalnum((unsigned char)*q)) {
                        int best = 0;
                        for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); ++i)
                            if (kProfiles[i].automatic && kProfiles[i].tagged && kProfiles[i].build >= lower &&
                                kProfiles[i].build <= upper &&
                                kProfiles[i].build > best)
                                best = kProfiles[i].build;
                        *profile = best;
                        return best ? best : upper;
                    }
                }
            }
        }
        /* v2 era tag: "v.2.1933" or "v2.1933" (no "Build" word) */
        if ((p[0] == 'v' || p[0] == 'V') &&
            (p[1] == '.' || isdigit((unsigned char)p[1]))) {
            const char *q = p + 1;
            if (*q == '.')
                q++;
            if (*q == '2' && q[1] == '.' && isdigit((unsigned char)q[2])) {
                int v = atoi(q + 2);
                if (v >= 1000 && v <= 3020)
                    return v;
            }
        }
        p++;
    }
    return 0;
}

/* Scan a sidecar OpenBOR exe for its build/version strings.
 * Returns a build number or 0. */
static int build_from_exe(const char *exe_path)
{
    FILE *fp = obor_fopen(exe_path, "rb");
    if (!fp)
        return 0;
    /* Version strings live in .rdata; scanning the whole exe (~5-15 MB) once
     * at load time is fine. */
    fseek(fp, 0, SEEK_END);
    long sz = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    if (sz <= 0 || sz > 64 * 1024 * 1024) {
        fclose(fp);
        return 0;
    }
    char *buf = (char *)malloc((size_t)sz + 1);
    if (!buf) {
        fclose(fp);
        return 0;
    }
    size_t got = fread(buf, 1, (size_t)sz, fp);
    fclose(fp);
    buf[got] = '\0';

    int build = 0, year = 0, month = 0;
    bool build_banner_seen = false;
    for (size_t i = 0; i + 6 <= got; ++i) {
        if (memcmp(buf + i, "Build ", 6)) continue;
        build_banner_seen = true;
        const unsigned char *q = (const unsigned char *)buf + i + 6;
        unsigned value = 0;
        while (isdigit(*q) && value <= 99999) value = value * 10 + (*q++ - '0');
        if (!build && value >= 1000 && value <= 99999) build = (int)value;
    }
    static const char *months = "JanFebMarAprMayJunJulAugSepOctNovDec";
    for (size_t i = 0; i + 16 < got; i++) {
        if (year == 0 && memcmp(buf + i, "Compile Date: ", 14) == 0) {
            const char *d = buf + i + 14;              /* "Aug 29 2018" */
            for (int m = 0; m < 12; m++) {
                if (memcmp(d, months + m * 3, 3) == 0) {
                    month = m + 1;
                    break;
                }
            }
            const char *y = d + 3;
            while (*y && !isdigit((unsigned char)*y))
                y++;
            while (*y && isdigit((unsigned char)*y))
                y++; /* skip day */
            while (*y && !isdigit((unsigned char)*y))
                y++;
            if (buf + got - y >= 4 && isdigit((unsigned char)y[0]) &&
                isdigit((unsigned char)y[1]) && isdigit((unsigned char)y[2]) &&
                isdigit((unsigned char)y[3]) && !isdigit((unsigned char)y[4]))
                year = (y[0]-'0')*1000 + (y[1]-'0')*100 + (y[2]-'0')*10 + y[3]-'0';
        }
        if (build && year)
            break;
    }
    free(buf);
    if (build)
        return build;
    if (!build_banner_seen && year >= 2006 && year <= 2099 && month >= 1 && month <= 12)
        return date_to_build(year, month);
    return 0;
}

/* Bounded, syntax-scoped content range inference. */
#include "anybor_content_scan.h"

/* Look for an OpenBOR exe next to the pak or one directory up
 * (the common "<Game>/<Game>.exe + <Game>/Paks/<game>.pak" layout). */
static int build_from_sidecar_dir(const char *dir)
{
    obor_path_directory *d = obor_opendir(dir);
    if (!d)
        return 0;
    int build = 0;
    obor_path_entry *e;
    while (!build && (e = obor_readdir(d))) {
        size_t n = strlen(e->d_name);
        if (n < 5 || strcasecmp(e->d_name + n - 4, ".exe") != 0)
            continue;
        if (strncasecmp(e->d_name, "borpak", 6) == 0)
            continue;
        char full[1400];
        if (snprintf(full, sizeof(full), "%s/%s", dir, e->d_name) >= (int)sizeof(full))
            continue;
        build = build_from_exe(full);
    }
    obor_closedir(d);
    return build;
}
static int build_from_sidecar(const char *pak_path)
{
    char dir[1024];
    size_t length = strlen(pak_path);
    if (length >= sizeof(dir)) return 0;
    memcpy(dir, pak_path, length + 1);
    char *slash = strrchr(dir, PATH_SEP);
    if (!slash)
        return 0;
    *slash = '\0';
    int build = build_from_sidecar_dir(dir);
    if (build)
        return build;
    slash = strrchr(dir, PATH_SEP);
    if (slash) {
        *slash = '\0';
        build = build_from_sidecar_dir(dir);
    }
    return build;
}

#include "anybor_engine_identity.h"
static obor_engine_identity g_zip_engine_identity;
static bool g_zip_engine_scanned;
#include "anybor_content_override.h"
/* Descriptor policy and content routing belong to the loaded session. */
static obor_content_choice g_content_choice OBOR_RUNTIME;

/* Choose the first automatic profile whose covered range reaches the
 * detected build. Explicit-only profiles never win a heuristic. */
static int pick_anchor(int build)
{
    const obor_profile_def *best = NULL;
    for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); i++) {
        const obor_profile_def *p = &kProfiles[i];
        if (p->automatic && p->auto_until >= build &&
            (!best || p->auto_until < best->auto_until))
            best = p;
    }
    if (!best) {
        for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); i++)
            if (kProfiles[i].automatic &&
                (!best || kProfiles[i].auto_until > best->auto_until))
                best = &kProfiles[i];
    }
    return best ? best->build : 0;
}

#include "anybor_profile_triage.h"

/* ------------------------------------------------------- core options --- */

struct engine_option_group {
    const char *key, *title;
    int first, last;
};
static const engine_option_group kEngineOptionGroups[] = {
    { "anybor_engine_3000_3499", "Engine Build 3000 -> 3499", 3000, 3499 },
    { "anybor_engine_3500_3749", "Engine Build 3500 -> 3749", 3500, 3749 },
    { "anybor_engine_3750_3999", "Engine Build 3750 -> 3999", 3750, 3999 },
    { "anybor_engine_4000_4999", "Engine Build 4000 -> 4999", 4000, 4999 },
    { "anybor_engine_5000_plus", "Engine Build > 5000", 5001, INT_MAX },
};
static const size_t n_engine_groups = sizeof(kEngineOptionGroups) / sizeof(kEngineOptionGroups[0]);

static bool engine_options_manual(void)
{
    struct retro_variable var = { "anybor_engine", NULL };
    return env_cb && env_cb(RETRO_ENVIRONMENT_GET_VARIABLE, &var) &&
           var.value && (!strcmp(var.value, "Off") || !strcmp(var.value, "More") || !strcmp(var.value, "More..."));
}

static int g_engine_options_visible = -1;
static int g_crt_options_visible = -1;

static const char *const kCrtCanvasWidths[] = { "Keep Game Width", "320px", "512px", "640px" };
static const char *const kCrtCanvasHeights[] = {
    "Keep Game Height", "240px", "384px", "480px"
};

static bool update_engine_option_visibility(void)
{
    if (!env_cb) return false;
    bool visible = engine_options_manual();
    if (g_engine_options_visible == (int)visible) return false;
    g_engine_options_visible = (int)visible;
    bool changed = false;
    for (size_t group = 0; group < n_engine_groups; ++group) {
        struct retro_core_option_display display = { kEngineOptionGroups[group].key, visible };
        changed = env_cb(RETRO_ENVIRONMENT_SET_CORE_OPTIONS_DISPLAY, &display) || changed;
    }
    return changed;
}

static void get_engine_option(char *out, size_t out_len)
{
    if (!out_len) return;
    snprintf(out, out_len, "Auto");
    if (!engine_options_manual()) return;
    for (size_t group = 0; group < n_engine_groups; ++group) {
        struct retro_variable var = { kEngineOptionGroups[group].key, NULL };
        if (!env_cb(RETRO_ENVIRONMENT_GET_VARIABLE, &var) || !var.value) continue;
        for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); ++i) {
            if (kProfiles[i].build >= kEngineOptionGroups[group].first &&
                kProfiles[i].build <= kEngineOptionGroups[group].last &&
                (!strcmp(var.value, kProfiles[i].disp) || !strcmp(var.value, kProfiles[i].name))) {
                snprintf(out, out_len, "%s", kProfiles[i].disp);
                break;
            }
        }
    }
}

static bool g_analog = true;  /* left stick doubles as D-pad */
static bool g_rumble_on = true;
static bool g_macros_on = true;
static bool g_gamelog_on = false;
struct video_options {
    bool crt, vertical, content_overrides;
    int canvas_width, canvas_height;
    unsigned rotation;
};
static video_options g_video_options;
static unsigned g_requested_rotation, g_frontend_rotation;

static unsigned presentation_scopes(const video_options &options)
{
    if (!options.content_overrides) return 0;
    unsigned scopes = 1u << OBOR_SCOPE_GAMERES;
    if (options.crt) {
        bool vertical = options.vertical != ((options.rotation & 1u) != 0);
        scopes |= (1u << OBOR_SCOPE_CRT) |
                  (1u << (vertical ? OBOR_SCOPE_CRT_VERTICAL : OBOR_SCOPE_CRT_HORIZONTAL));
    }
    return scopes;
}

static const char *option_value(const char *key)
{
    struct retro_variable var = { key, NULL };
    return env_cb && env_cb(RETRO_ENVIRONMENT_GET_VARIABLE, &var) && var.value ? var.value : "";
}

template<size_t N>
static int crt_canvas_extent(const char *key, const char *const (&values)[N], int fallback)
{
    const char *value = option_value(key);
    for (const char *choice : values)
        if (!strcmp(value, choice)) return atoi(choice);
    return fallback;
}

static bool opt_is_on(const char *key, bool defval)
{
    struct retro_variable var = { key, NULL };
    if (env_cb && env_cb(RETRO_ENVIRONMENT_GET_VARIABLE, &var) && var.value)
        return strcmp(var.value, "On") == 0;
    return defval;
}

static bool update_option_visibility(void)
{
    bool changed = update_engine_option_visibility();
    if (!env_cb) return changed;
    bool visible = opt_is_on("anybor_crt_tv", false);
    if (g_crt_options_visible != (int)visible) {
        bool delivered = true;
        const char *const keys[] = { "anybor_crt_oversize_canvas_width", "anybor_crt_oversize_canvas_height",
                                     "anybor_os_screen_orientation" };
        for (const char *key : keys) {
            struct retro_core_option_display display = { key, visible };
            bool accepted = env_cb(RETRO_ENVIRONMENT_SET_CORE_OPTIONS_DISPLAY, &display);
            delivered = accepted && delivered;
            changed = changed || accepted;
        }
        if (delivered) g_crt_options_visible = (int)visible;
    }
    return changed;
}

static void request_frontend_rotation(unsigned rotation)
{
    if (rotation == g_requested_rotation) return;
    g_requested_rotation = rotation;
    g_frontend_rotation = OBOR_ROTATION_NONE;
    if (!env_cb) return;
    if (env_cb(RETRO_ENVIRONMENT_SET_ROTATION, &rotation)) {
        g_frontend_rotation = rotation;
    } else if (rotation) {
        /* Some frontends record the request before checking support. */
        unsigned reset = OBOR_ROTATION_NONE;
        env_cb(RETRO_ENVIRONMENT_SET_ROTATION, &reset);
    }
}

static int state_option(const char *key, const char *on, const char *off)
{
    struct retro_variable var = { key, NULL };
    if (env_cb && env_cb(RETRO_ENVIRONMENT_GET_VARIABLE, &var) && var.value) {
        if (!strcmp(var.value, on)) return OBOR_STATE_SETTING_ON;
        if (!strcmp(var.value, off)) return OBOR_STATE_SETTING_OFF;
    }
    return OBOR_STATE_SETTING_DEFAULT;
}

static void load_state_options(void)
{
    obor_state_session_settings.content = state_option("anybor_state_content", "Smart", "Full");
    obor_state_session_settings.compression = state_option("anybor_state_compression", "On", "Off");
}

/* Re-read the live-effect options (the engine option is only sampled at
 * load/reset by decide_engine). */
static void refresh_options(void)
{
    update_option_visibility();
    g_analog = opt_is_on("anybor_analog", true);
    g_rumble_on = opt_is_on("anybor_rumble", true);
    g_macros_on = opt_is_on("anybor_macros", true);
    g_gamelog_on = opt_is_on("anybor_gamelog", false);
    g_video_options.crt = opt_is_on("anybor_crt_tv", false);
    g_video_options.content_overrides = opt_is_on("anybor_content_overrides", true);
    g_video_options.vertical = !strcmp(option_value("anybor_os_screen_orientation"), "Vertical");
    g_video_options.canvas_width = crt_canvas_extent("anybor_crt_oversize_canvas_width",
                                                     kCrtCanvasWidths, OBOR_CRT_DEFAULT_WIDTH);
    g_video_options.canvas_height = crt_canvas_extent("anybor_crt_oversize_canvas_height",
                                                      kCrtCanvasHeights, OBOR_CRT_DEFAULT_HEIGHT);
    const char *value = option_value("anybor_image_rotation");
    g_video_options.rotation = !strcmp(value, "Left") ? OBOR_ROTATION_LEFT :
                               !strcmp(value, "Right") ? OBOR_ROTATION_RIGHT :
                               !strcmp(value, "Upside Down") ? OBOR_ROTATION_INVERTED : OBOR_ROTATION_NONE;
    g_storage.clear_on_unload = opt_is_on("anybor_clear_game_cache", true);
}

/* ---------------------------------------------- frame-loop accessories --- */

/* rumble: engine hit events -> frontend rumble interface */
static struct retro_rumble_interface g_rumble_if;
static bool g_rumble_have;
static uint64_t g_rumble_off_at[OBOR_MAX_PLAYERS];

static void rumble_stop(void)
{
    for (unsigned pl = 0; pl < OBOR_MAX_PLAYERS; pl++) {
        if (g_rumble_have && g_rumble_if.set_rumble_state) {
            g_rumble_if.set_rumble_state(pl, RETRO_RUMBLE_STRONG, 0);
            g_rumble_if.set_rumble_state(pl, RETRO_RUMBLE_WEAK, 0);
        }
        g_rumble_off_at[pl] = 0;
    }
}

static void rumble_frame(void)
{
    if (!g_rumble_have)
        return;
    for (int pl = 0; pl < OBOR_MAX_PLAYERS; pl++) {
        int32_t ratio = 0, ms = 0;
        p_get_rumble(pl, &ratio, &ms);
        if (ratio > 0 && ms > 0 && g_rumble_on) {
            uint16_t s = (uint16_t)(ratio * 65535 / 100);
            g_rumble_if.set_rumble_state((unsigned)pl, RETRO_RUMBLE_STRONG, s);
            g_rumble_if.set_rumble_state((unsigned)pl, RETRO_RUMBLE_WEAK, s);
            uint64_t frames = ((uint64_t)ms * 60 + 999) / 1000;
            g_rumble_off_at[pl] = (uint64_t)g_frame_no + frames;
        } else if (g_rumble_off_at[pl] && (!g_rumble_on || (uint64_t)g_frame_no >= g_rumble_off_at[pl])) {
            g_rumble_if.set_rumble_state((unsigned)pl, RETRO_RUMBLE_STRONG, 0);
            g_rumble_if.set_rumble_state((unsigned)pl, RETRO_RUMBLE_WEAK, 0);
            g_rumble_off_at[pl] = 0;
        }
    }
}

/* memory map: expose the arena so the frontend's cheat search works */
static uint32_t g_map_sent;

static void memmap_maybe_send(void)
{
    void *base = NULL;
    uint32_t used = 0;
    p_get_arena(&base, &used);
    if (!base || !used)
        return;
    if (g_map_sent && used <= g_map_sent + (8u << 20))
        return;
    static struct retro_memory_descriptor md;
    memset(&md, 0, sizeof(md));
    md.flags = RETRO_MEMDESC_SYSTEM_RAM;
    md.ptr = base;
    md.start = 0;
    md.len = (used + 0xFFFu) & ~0xFFFu;
    static struct retro_memory_map mm = { &md, 1 };
    env_cb(RETRO_ENVIRONMENT_SET_MEMORY_MAPS, &mm);
    g_map_sent = used;
}

/* game log tail: mirror OpenBorLog.txt into the frontend log */
static FILE *g_glog_fp;
static char g_glog_path[2048];

static void gamelog_frame(void)
{
    if (!g_gamelog_on || !g_save_dir[0])
        return;
    if (!g_glog_fp) {
        snprintf(g_glog_path, sizeof(g_glog_path),
                 "%s/%s/Logs/OpenBorLog.txt", g_game_dir, g_logical_engine);
        g_glog_fp = obor_fopen(g_glog_path, "rb");
        if (!g_glog_fp)
            return;
    }
    char line[512];
    int guard = 20; /* chunks per frame cap, including long lines */
    long pos = ftell(g_glog_fp);
    while (guard-- > 0 && fgets(line, sizeof(line), g_glog_fp)) {
        size_t n = strlen(line);
        if (n && n < sizeof(line) - 1 && line[n - 1] != '\n') {
            /* partial line still being written — rewind and retry later */
            fseek(g_glog_fp, pos, SEEK_SET);
            break;
        }
        /* A full buffer without a newline is a bounded chunk of a long
         * line, not an unfinished write. Consume it so subsequent records
         * cannot be permanently hidden behind a long content path. */
        while (n && (line[n - 1] == '\n' || line[n - 1] == '\r'))
            line[--n] = '\0';
        if (n)
            log_cb(RETRO_LOG_INFO, "[game] %s\n", line);
        pos = ftell(g_glog_fp);
    }
    clearerr(g_glog_fp); /* keep tailing past EOF */
}

static void gamelog_close(void)
{
    if (g_glog_fp) {
        fclose(g_glog_fp);
        g_glog_fp = NULL;
    }
}

/* special-move macros: L2/R2/L3/R3 replay the active character's own com
 * sequences (parsed from the pak by anybor_padmap.h) */
typedef struct {
    uint16_t steps[OBOR_PM_MAXSTEP]; /* resolved: F/B already absolute */
    int nsteps;
    int step;    /* current step, -1 idle */
    int phase;   /* frames left in current step (press then gap) */
} macro_state;
static macro_state g_macro[OBOR_MAX_PLAYERS];
static unsigned char g_macro_prev[OBOR_MAX_PLAYERS][4];

static const unsigned kMacroPad[4] = {
    RETRO_DEVICE_ID_JOYPAD_L2, RETRO_DEVICE_ID_JOYPAD_R2,
    RETRO_DEVICE_ID_JOYPAD_L3, RETRO_DEVICE_ID_JOYPAD_R3,
};

/* token bitmask -> OBOR button bitmask, resolving F/B with facing */
static uint16_t macro_resolve(uint16_t tk, int facing)
{
    uint16_t b = 0;
    if (tk & OBOR_PM_TK_U) b |= 1 << OBOR_BTN_UP;
    if (tk & OBOR_PM_TK_D) b |= 1 << OBOR_BTN_DOWN;
    if (tk & OBOR_PM_TK_F) b |= 1 << (facing ? OBOR_BTN_RIGHT : OBOR_BTN_LEFT);
    if (tk & OBOR_PM_TK_B) b |= 1 << (facing ? OBOR_BTN_LEFT : OBOR_BTN_RIGHT);
    if (tk & OBOR_PM_TK_A) b |= 1 << OBOR_BTN_ATTACK;
    if (tk & OBOR_PM_TK_A2) b |= 1 << OBOR_BTN_ATTACK2;
    if (tk & OBOR_PM_TK_A3) b |= 1 << OBOR_BTN_ATTACK3;
    if (tk & OBOR_PM_TK_A4) b |= 1 << OBOR_BTN_ATTACK4;
    if (tk & OBOR_PM_TK_J) b |= 1 << OBOR_BTN_JUMP;
    if (tk & OBOR_PM_TK_S) b |= 1 << OBOR_BTN_SPECIAL;
    return b;
}

#define MACRO_PRESS_FRAMES 2
#define MACRO_GAP_FRAMES 1

/* returns 1 if it drove this player's pad (live input must be skipped) */
static int macro_frame(int pl)
{
    macro_state *m = &g_macro[pl];

    /* fire detection on the free pad buttons */
    for (int k = 0; k < 4; k++) {
        int16_t v = input_state_cb((unsigned)pl, RETRO_DEVICE_JOYPAD, 0,
                                   kMacroPad[k]);
        int was = g_macro_prev[pl][k];
        g_macro_prev[pl][k] = v ? 1 : 0;
        if (!g_macros_on || !v || was || m->step >= 0)
            continue;
        char cname[32];
        int32_t facing = 1;
        if (!p_get_player_state(pl, cname, sizeof(cname), &facing))
            continue;
        for (int c = 0; c < g_pm_nchars; c++) {
            if (strcasecmp(g_pm_chars[c].name, cname) != 0)
                continue;
            if (k >= g_pm_chars[c].nseq)
                break;
            m->nsteps = g_pm_chars[c].slen[k];
            for (int s = 0; s < m->nsteps; s++)
                m->steps[s] =
                    macro_resolve(g_pm_chars[c].seq[k][s], facing);
            m->step = 0;
            m->phase = MACRO_PRESS_FRAMES + MACRO_GAP_FRAMES;
            obor_dbg("macro: pl%d slot%d char=%s steps=%d facing=%d", pl, k,
                     cname, m->nsteps, facing);
            break;
        }
    }

    if (m->step < 0)
        return 0;

    /* drive the sequence: press for a couple frames, then a release gap */
    uint16_t mask = (m->phase > MACRO_GAP_FRAMES) ? m->steps[m->step] : 0;
    for (int btn = 0; btn < OBOR_BTN_COUNT; btn++)
        p_set_button(pl, btn, (mask >> btn) & 1);
    if (--m->phase <= 0) {
        m->step++;
        m->phase = MACRO_PRESS_FRAMES + MACRO_GAP_FRAMES;
        if (m->step >= m->nsteps)
            m->step = -1;
    }
    return 1;
}

static void macro_reset_all(void)
{
    for (int pl = 0; pl < OBOR_MAX_PLAYERS; pl++) {
        g_macro[pl].step = -1;
        memset(g_macro_prev[pl], 0, sizeof(g_macro_prev[pl]));
    }
}

static void trace_close(void)
{
    if (g_trace) {
        fclose(g_trace);
        g_trace = NULL;
    }
}

static void content_stop(bool preserve_geometry = false)
{
    g_reverse_has_snapshot = false;
    loading_dispose();
    free(g_loading_pixels);
    g_loading_pixels = NULL;
    g_loading_width = g_loading_height = 0;
    if (g_fault_pending) {
        g_fault_pending = false;
        stop_faulted_engine();
    }
    obor_profile_close();
    if (!obor_latency_close())
        log_cb(RETRO_LOG_WARN, "[OpenBOR] latency diagnostic output incomplete\n");
    obor_capture_cadence_reset(&g_capture_cadence);
    g_input_has_origin = false;
    g_state_capacity = 0;
    rumble_stop();
    g_pm_nchars = 0;
    if (g_booted && g_vtbl)
        p_shutdown();
    if (!g_fault_quarantined) engine_resources_close();
    g_booted = false;
    gamelog_close();
    if (!obor_storage_finish() && log_cb)
        log_cb(RETRO_LOG_WARN, "[OpenBOR] Could not remove all current game cache files.\n");
    macro_reset_all();
    trace_close();
    obor_dbg_uninstall();
    g_vtbl = NULL;
    g_rumble_have = false;
    g_map_sent = 0;
    g_raw = false;
    g_engine[0] = '\0';
    g_logical_engine[0] = '\0';
    g_engine_error_context = g_engine_log_fresh = false;
    g_pak_path[0] = '\0';
    g_engine_source_path[0] = '\0';
    g_zip_engine_scanned = false;
    g_content_choice = obor_content_choice();
    g_content_level = -1;
    memset(&g_zip_engine_identity, 0, sizeof(g_zip_engine_identity));
    free(g_window_buffer.pixels);
    free(g_crt_buffer.pixels);
    free(g_shift_buffer.pixels);
    free(g_rotation_buffer.pixels);
    g_window_buffer = {};
    g_crt_buffer = {};
    g_shift_buffer = {};
    g_rotation_buffer = {};
    if (!preserve_geometry) {
        g_width = g_source_width = 320;
        g_height = g_source_height = 240;
        g_aspect = 4.0f / 3.0f;
        g_max_width = 1920;
        g_max_height = 1080;
        g_av_announced = false;
        g_presentation_timing = {kNativeRefresh, kNativeRefresh, 0};
    } else {
        g_presentation_timing.requested = 0;
    }
}

/* Explicit engine reasons survive cleanup; log fallback is session-scoped. */

static void error_reason(const char *reason)
{
    snprintf(g_error_reason, sizeof(g_error_reason), "%s",
             reason && reason[0] ? reason : "The game could not be loaded.");
}

static void engine_log_begin(void)
{
    char path[2048];
    g_engine_error_context = true;
    g_engine_log_fresh = false;
    int n = snprintf(path, sizeof(path), "%s/%s/Logs/OpenBorLog.txt",
                     g_game_dir, g_logical_engine);
    if (n < 0 || (size_t)n >= sizeof(path)) return;
    /* The engine truncates this per-session log itself. Remove the old entry
     * first so a boot failure before its logger opens cannot reuse old text. */
    g_engine_log_fresh = !obor_remove(path) || errno == ENOENT;
}

/* Read only the active profile's log. Some engines append the reason after
 * shutdown accounting; that accounting is not the game loading error. */
static bool engine_log_error(char *out, size_t cap)
{
    if (!out || !cap) return false;
    if (g_engine_error_context && g_vtbl && p_get_fault_message(out, (uint32_t)cap)) return true;
    if (!g_engine_error_context || !g_engine_log_fresh || !g_game_dir[0] || !g_logical_engine[0]) return false;
    char path[2048];
    int n = snprintf(path, sizeof(path), "%s/%s/Logs/OpenBorLog.txt",
                     g_game_dir, g_logical_engine);
    if (n < 0 || (size_t)n >= sizeof(path)) return false;
#if defined(_WIN32)
    DWORD attributes = obor_win_attributes(path);
    if (attributes == INVALID_FILE_ATTRIBUTES ||
        (attributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DEVICE))) return false;
    FILE *fp = obor_fopen(path, "rb");
#else
    int fd = obor_open(path, O_RDONLY | O_NONBLOCK | O_NOFOLLOW);
    if (fd < 0) return false;
    struct stat st;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode)) { close(fd); return false; }
    FILE *fp = fdopen(fd, "rb");
    if (!fp) close(fd);
#endif
    if (!fp) return false;
    /* A log is a diagnostic fallback, with bounded work even if replaced by
     * an unexpectedly large file. Do not interpret a leading partial line. */
    if (fseek(fp, 0, SEEK_END)) { fclose(fp); return false; }
    long bytes = ftell(fp);
    if (bytes < 0) { fclose(fp); return false; }
    long start = bytes > 65536 ? bytes - 65536 : 0;
    if (fseek(fp, start, SEEK_SET)) { fclose(fp); return false; }
    char line[512];
    size_t remaining = 65536;
    long position = start;
    bool discard = start != 0;
    bool marker = false, found = false, shutdown_summary = false;
    while (remaining && fgets(line, (int)(remaining < sizeof(line)-1 ? remaining+1 : sizeof(line)), fp)) {
        long next = ftell(fp);
        if (next <= position || (uint64_t)(next-position) > remaining) break;
        remaining -= (size_t)(next-position);
        position = next;
        if (discard) {
            if (strchr(line, '\n')) discard = false;
            continue;
        }
        if (strstr(line, "An Error Occurred")) {
            marker = true;
            found = false;
            shutdown_summary = false;
            continue;
        }
        if (!marker) continue;
        size_t len = strlen(line);
        while (len && (line[len - 1] == '\n' || line[len - 1] == '\r'))
            line[--len] = '\0';
        if (line[0] == '*' && strstr(line, "Shutting Down")) {
            shutdown_summary = true;
            continue;
        }
        if (shutdown_summary) {
            if (line[0] == '*' && strstr(line, " Done "))
                shutdown_summary = false;
            continue;
        }
        if (!len || line[0] == '*') continue;
        const char *text = line;
        while (*text == ' ' || *text == '\t') ++text;
        if (!*text) continue;
        const char *amount = NULL;
        if (!strncmp(text, "Total Ram:", 10)) amount = text + 10;
        else if (!strncmp(text, "Free Ram:", 9)) amount = text + 9;
        else if (!strncmp(text, "Used Ram:", 9)) amount = text + 9;
        if (amount) {
            while (*amount == ' ' || *amount == '\t') ++amount;
            const char *digits = amount;
            while (*amount >= '0' && *amount <= '9') ++amount;
            if (amount != digits && !strcmp(amount, " Bytes")) {
                shutdown_summary = true;
                continue;
            }
        }
        snprintf(out, cap, "%s", line);
        found = true;
        break;
    }
    fclose(fp);
    return found;
}

static void stop_faulted_engine(void)
{
    g_booted = false;
    if (p_abandon()) {
        engine_resources_close();
        return;
    }
    /* A second fault while stopping workers can leave a decoder alive.
     * Retain its code, statics, resources and arena; do not let dlclose or a
     * subsequent pristine restore turn that worker into a use-after-free. */
    g_fault_quarantined = true;
#ifdef _WIN32
    HMODULE retained;
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                      GET_MODULE_HANDLE_EX_FLAG_PIN,
                      (LPCSTR)&stop_faulted_engine, &retained);
#else
    Dl_info module;
    if (dladdr((const void *)&stop_faulted_engine, &module))
        (void)dlopen(module.dli_fname, RTLD_NOW); /* Deliberately retain. */
#endif
}

static void error_screen(const char *reason, bool deferred = false)
{
    char engine[sizeof(g_error_engine)];
    snprintf(engine, sizeof(engine), "%s", g_logical_engine[0] ?
             g_logical_engine : (g_engine[0] ? g_engine : "not selected"));
    if (reason) error_reason(reason);
    if (g_fault_quarantined) {
        const char *suffix = "\nWorkers could not be stopped safely. Restart the frontend.";
        size_t used = strlen(g_error_reason);
        snprintf(g_error_reason + used, sizeof(g_error_reason) - used, "%s", suffix);
    }
    if (deferred) {
        /* State callbacks return outside retro_run. Keep the last submitted
         * pixels alive until the next video callback or explicit unload/reset. */
        g_fault_pending = true;
        g_booted = false;
    } else content_stop(true);
    snprintf(g_error_engine, sizeof(g_error_engine), "%s", engine);
    g_error_active = true;
    obor_error_render(g_error_pixels, g_error_path, g_error_engine,
                      g_error_reason);
    if (!deferred) {
        request_frontend_rotation(OBOR_ROTATION_NONE);
        output_geometry(OBOR_ERROR_WIDTH, OBOR_ERROR_HEIGHT, true);
    }
    if (log_cb) log_cb(RETRO_LOG_ERROR, "[OpenBOR] %s\n", g_error_reason);
}

static bool queue_state_fault(void)
{
    if (!g_vtbl || p_get_exit_status() != OBOR_EXIT_MEMORY_FAULT) return false;
    char reason[sizeof(g_error_reason)];
    if (!p_get_fault_message(reason, sizeof(reason)))
        snprintf(reason, sizeof(reason), "Engine failed during a state operation.");
    error_screen(reason, true);
    return true;
}

static void present_error_frame(void)
{
    output_geometry(OBOR_ERROR_WIDTH, OBOR_ERROR_HEIGHT, true);
    video_cb(g_error_pixels, OBOR_ERROR_WIDTH, OBOR_ERROR_HEIGHT,
             OBOR_ERROR_WIDTH * sizeof(uint32_t));
}

/* ------------------------------------------------------------ libretro --- */

#define ENGINE_OPT_INFO \
    "Automatic Engine Selection detects the engine from the file when On " \
    "(verified engine executable, filename build range or tag, sidecar exe, bounded content scan). " \
    "Off shows the manual build ranges. On ignores all range selections. " \
    "A dash in every range uses automatic detection. If several ranges have a selection, " \
    "the last range with a selection in the menu wins. Changes apply on Restart."

void retro_set_environment(retro_environment_t cb)
{
    env_cb = cb;
    g_engine_options_visible = -1;
    g_crt_options_visible = -1;
    size_t n_profiles = sizeof(kProfiles) / sizeof(kProfiles[0]);

    unsigned cov = 0;
    if (!cb(RETRO_ENVIRONMENT_GET_CORE_OPTIONS_VERSION, &cov))
        cov = 0;
    /* Each build range has its own bounded ABI value list. */
    if (cov >= 2) {
        static struct retro_core_option_v2_category cats[] = {
            { "video", "Video", "Video output." },
            { "input", "Input", "Controller behaviour." },
            { "system", "System", "Engine and save state settings." },
            { "development", "Development", "Tools for exercising content." },
            { NULL, NULL, NULL },
        };
        static struct retro_core_option_v2_definition defs[] = {
            { "anybor_crt_tv", "Adjust for 4:3 CRT TV", "Adjust for 4:3 CRT TV",
              "Fits images that need more than 244 scanlines after native-pixel padding. "
              "Centers oversized images in the selected CRT canvas. The frontend controls the TV video mode.",
              NULL, "video",
              { { "Off", NULL }, { "On", NULL }, { NULL, NULL } }, "Off" },
            { "anybor_crt_oversize_canvas_width", "CRT Oversize Canvas Width", "CRT Oversize Canvas Width",
              "Sets the horizontal canvas extent for oversized images. Keep Game Width preserves native "
              "samples along that axis and allows black margins. The axes follow CRT orientation.",
              NULL, "video",
              { { kCrtCanvasWidths[0], NULL }, { kCrtCanvasWidths[1], NULL },
                { kCrtCanvasWidths[2], NULL }, { kCrtCanvasWidths[3], NULL }, { NULL, NULL } },
              kCrtCanvasWidths[0] },
            { "anybor_crt_oversize_canvas_height", "CRT Oversize Canvas Height", "CRT Oversize Canvas Height",
              "Sets the vertical canvas extent for oversized images. Keep Game Height preserves native "
              "samples along that axis and allows black margins. The axes follow CRT orientation.",
              NULL, "video",
              { { kCrtCanvasHeights[0], NULL }, { kCrtCanvasHeights[1], NULL },
                { kCrtCanvasHeights[2], NULL }, { kCrtCanvasHeights[3], NULL }, { NULL, NULL } },
              kCrtCanvasHeights[3] },
            { "anybor_os_screen_orientation", "OS Screen Orientation", "OS Screen Orientation",
              "Match the screen orientation already set in the operating system. This option only selects "
              "the axes for CRT fitting. The operating system controls its own rotation. Vertical swaps "
              "the scanline and canvas axes. Left or Right Image Rotation swaps them again.",
              NULL, "video",
              { { "Horizontal", NULL }, { "Vertical", NULL }, { NULL, NULL } }, "Horizontal" },
            { "anybor_image_rotation", "Image Rotation", "Image Rotation",
              "Turns the complete game image left, right or upside down. Left and Right also swap the CRT canvas axes.",
              NULL, "video",
              { { "None", NULL }, { "Left", NULL }, { "Right", NULL }, { "Upside Down", NULL },
                { NULL, NULL } }, "None" },
            { "anybor_content_overrides", "Content Override Directives", "Content Override Directives",
              "Applies CRT and game-resolution presentation directives declared by this content.",
              NULL, "video",
              { { "On", NULL }, { "Off", NULL }, { NULL, NULL } }, "On" },
            { "anybor_analog", "Left Analog Stick as D-Pad",
              "Left Analog Stick as D-Pad",
              "Move with the left stick in addition to the D-pad.",
              NULL, "input",
              { { "On", NULL }, { "Off", NULL }, { NULL, NULL } }, "On" },
            { "anybor_rumble", "Rumble",
              "Rumble",
              "Enable controller vibration for game effects.",
              NULL, "input",
              { { "On", NULL }, { "Off", NULL }, { NULL, NULL } }, "On" },
            { "anybor_macros", "Special Move Macros (L2/R2/L3/R3)",
              "Special Move Macros (L2/R2/L3/R3)",
              "Bind the active character's special-move sequences (from the "
              "game's own movelist) to the free shoulder/stick buttons. "
              "Pressing one performs the full input sequence.",
              NULL, "input",
              { { "On", NULL }, { "Off", NULL }, { NULL, NULL } }, "On" },
            { "anybor_engine", "Automatic Engine Selection", "Automatic Engine Selection",
              ENGINE_OPT_INFO, NULL, "system",
              { { "On", NULL }, { "Off", NULL }, { NULL, NULL } },
              "On" },
            { "anybor_state_content", "Save State Content", "Save State Content",
              "Smart reconstructs resources whose bytes can be reproduced exactly. "
              "Full stores complete engine memory. Changes apply when content is loaded. "
              "Smart is the default on every platform. Full with compression Off may "
              "exceed the rewind buffer in large games.",
              NULL, "system",
              { { "Smart", NULL }, { "Full", NULL }, { NULL, NULL } },
              OBOR_STATE_CONTENT_DEFAULT },
            { "anybor_state_compression", "Save State Compression", "Save State Compression",
              "On reduces state size. Off avoids compression work and can require "
              "more rewind memory; unchanged blocks remain reusable. Changes apply "
              "when content is loaded. On is the default on every platform. Full "
              "content with compression Off may exceed the rewind buffer in large games.",
              NULL, "system",
              { { "On", NULL }, { "Off", NULL }, { NULL, NULL } },
              OBOR_STATE_COMPRESSION_DEFAULT },
            { "anybor_gamelog", "Forward Game Log",
              "Forward Game Log",
              "Mirror the game's OpenBorLog into the frontend log "
              "(useful to debug mods).",
              NULL, "system",
              { { "Off", NULL }, { "On", NULL }, { NULL, NULL } }, "Off" },
            { "anybor_clear_local_data", "Clear Current Game Saved Data on Load", NULL,
              "Deletes everything in this game's folder under AnyBOR before it loads, "
              "so the next run behaves like the first on this machine. Includes saved "
              "data from all engine builds. Other games and frontend save states are unaffected.", NULL, "development",
              { { "Off", NULL }, { "On", NULL }, { NULL, NULL } }, "Off" },
            { "anybor_clear_game_cache", "Clear Current Game Cache on Unload", NULL,
              "Deletes the cache directories used by the current game after unloading it "
              "or closing the core. The next load rebuilds them. Saved game data is unaffected.",
              NULL, "development",
              { { "On", NULL }, { "Off", NULL }, { NULL, NULL } }, "On" },
            { "anybor_clear_all_caches", "Clear All Game Caches on Load", NULL,
              "Deletes all contents of AnyBOR-cache before loading a game or generating its "
              "cache. Every load starts with an empty cache while this is On. Saved game "
              "data is unaffected.", NULL, "development",
              { { "On", NULL }, { "Off", NULL }, { NULL, NULL } }, "On" },
            { NULL, NULL, NULL, NULL, NULL, NULL, { { NULL, NULL } }, NULL },
        };
        static struct retro_core_option_v2_definition expanded[
            sizeof(defs) / sizeof(defs[0]) + n_engine_groups];
        size_t output = 0;
        for (const auto &def : defs) {
            if (!def.key) break;
            expanded[output++] = def;
            if (strcmp(def.key, "anybor_engine")) continue;
            for (size_t group = 0; group < n_engine_groups; ++group) {
                const auto &range = kEngineOptionGroups[group];
                auto &entry = expanded[output++];
                entry = {};
                entry.key = range.key;
                entry.desc = entry.desc_categorized = range.title;
                entry.info = ENGINE_OPT_INFO;
                entry.category_key = "system";
                entry.default_value = "None";
                entry.values[0] = { "None", "-" };
                size_t value = 1;
                for (size_t i = 0; i < n_profiles; ++i) {
                    if (kProfiles[i].build >= range.first && kProfiles[i].build <= range.last &&
                        value + 1 < RETRO_NUM_CORE_OPTION_VALUES_MAX)
                        entry.values[value++] = { kProfiles[i].disp, NULL };
                }
                entry.values[value] = { NULL, NULL };
            }
        }
        expanded[output] = {};
        static struct retro_core_options_v2 opts = { cats, expanded };
        cb(RETRO_ENVIRONMENT_SET_CORE_OPTIONS_V2, &opts);
        struct retro_core_options_update_display_callback display = { update_option_visibility };
        cb(RETRO_ENVIRONMENT_SET_CORE_OPTIONS_UPDATE_DISPLAY_CALLBACK, &display);
        update_option_visibility();
        return;
    }

    /* legacy fallback: grouped v0 variables (no separate value labels). */
    static char values[n_engine_groups][64 + 48 * (sizeof(kProfiles) / sizeof(kProfiles[0]))];
    for (size_t group = 0; group < n_engine_groups; ++group) {
        const auto &range = kEngineOptionGroups[group];
        snprintf(values[group], sizeof(values[group]), "%s; -", range.title);
        for (size_t i = 0; i < n_profiles; ++i) {
            if (kProfiles[i].build < range.first || kProfiles[i].build > range.last) continue;
            size_t used = strlen(values[group]);
            snprintf(values[group] + used, sizeof(values[group]) - used, "|%s", kProfiles[i].disp);
        }
    }
    static const struct retro_variable vars[] = {
        { "anybor_crt_tv", "Adjust for 4:3 CRT TV; Off|On" },
        { "anybor_crt_oversize_canvas_width", "CRT Oversize Canvas Width; Keep Game Width|320px|512px|640px" },
        { "anybor_crt_oversize_canvas_height", "CRT Oversize Canvas Height; 480px|Keep Game Height|240px|384px" },
        { "anybor_os_screen_orientation", "OS Screen Orientation; Horizontal|Vertical" },
        { "anybor_image_rotation", "Image Rotation; None|Left|Right|Upside Down" },
        { "anybor_content_overrides", "Content Override Directives; On|Off" },
        { "anybor_analog", "Left Analog Stick as D-Pad; On|Off" },
        { "anybor_rumble", "Rumble; On|Off" },
        { "anybor_macros", "Special Move Macros (L2/R2/L3/R3); On|Off" },
        { "anybor_engine", "Automatic Engine Selection; On|Off" },
        { kEngineOptionGroups[0].key, values[0] },
        { kEngineOptionGroups[1].key, values[1] },
        { kEngineOptionGroups[2].key, values[2] },
        { kEngineOptionGroups[3].key, values[3] },
        { kEngineOptionGroups[4].key, values[4] },
        { "anybor_state_content", "Save State Content; " OBOR_STATE_CONTENT_VALUES },
        { "anybor_state_compression", "Save State Compression; " OBOR_STATE_COMPRESSION_VALUES },
        { "anybor_gamelog", "Forward Game Log; Off|On" },
        { "anybor_clear_local_data", "Clear Current Game Saved Data on Load; Off|On" },
        { "anybor_clear_game_cache", "Clear Current Game Cache on Unload; On|Off" },
        { "anybor_clear_all_caches", "Clear All Game Caches on Load; On|Off" },
        { NULL, NULL },
    };
    cb(RETRO_ENVIRONMENT_SET_VARIABLES, (void *)vars);
    struct retro_core_options_update_display_callback display = { update_option_visibility };
    cb(RETRO_ENVIRONMENT_SET_CORE_OPTIONS_UPDATE_DISPLAY_CALLBACK, &display);
    update_option_visibility();
}

void retro_set_video_refresh(retro_video_refresh_t cb) { video_cb = cb; }
void retro_set_audio_sample(retro_audio_sample_t cb) { (void)cb; }
void retro_set_audio_sample_batch(retro_audio_sample_batch_t cb) { audio_batch_cb = cb; }
void retro_set_input_poll(retro_input_poll_t cb) { input_poll_cb = cb; }
void retro_set_input_state(retro_input_state_t cb) { input_state_cb = cb; }

void retro_init(void)
{
    struct retro_log_callback logging;
    if (env_cb && env_cb(RETRO_ENVIRONMENT_GET_LOG_INTERFACE, &logging))
        log_cb = logging.log;
    else
        log_cb = fallback_log;

    uint64_t quirks = RETRO_SERIALIZATION_QUIRK_CORE_VARIABLE_SIZE |
                      RETRO_SERIALIZATION_QUIRK_MUST_INITIALIZE;
    g_variable_state_size = env_cb &&
        env_cb(RETRO_ENVIRONMENT_SET_SERIALIZATION_QUIRKS, &quirks) &&
        (quirks & RETRO_SERIALIZATION_QUIRK_FRONT_VARIABLE_SIZE);
}

void retro_deinit(void) {
    if (g_storage.root[0]) refresh_options();
    content_stop();
    request_frontend_rotation(OBOR_ROTATION_NONE);
}

unsigned retro_api_version(void) { return RETRO_API_VERSION; }

void retro_get_system_info(struct retro_system_info *info)
{
    memset(info, 0, sizeof(*info));
    info->library_name = "AnyBOR";
    info->library_version = OBOR_CORE_VERSION;
    /* .pak, or the models.txt of an unpacked mod (…/<mod>/data/models.txt) */
    info->valid_extensions = "pak|spk|txt|zip|anybor";
    info->need_fullpath = true;
    info->block_extract = true;
}

static void system_av_info(struct retro_system_av_info *info)
{
    memset(info, 0, sizeof(*info));
    info->geometry.base_width = (unsigned)g_width;
    info->geometry.base_height = (unsigned)g_height;
    info->geometry.max_width = g_max_width;
    info->geometry.max_height = g_max_height;
    info->geometry.aspect_ratio = g_aspect;
    info->timing.fps = g_presentation_timing.fps;
    info->timing.sample_rate = 44100.0;
}

void retro_get_system_av_info(struct retro_system_av_info *info)
{
    system_av_info(info);
    g_av_announced = true;
}

/* A frontend can decline a new refresh. Continue pacing at its last accepted
 * rate and retry only when the requested rate changes or the content resets. */
static void update_presentation_timing(unsigned fps)
{
    auto &timing = g_presentation_timing;
    if (fps == timing.requested) return;
    timing.requested = fps;
    if (fps == timing.fps) return;

    struct retro_system_av_info av;
    system_av_info(&av);
    av.timing.fps = fps;
    if (g_av_announced && !env_cb(RETRO_ENVIRONMENT_SET_SYSTEM_AV_INFO, &av)) return;
    timing.fps = fps;
    timing.phase = fps > kNativeRefresh ? fps - kNativeRefresh : 0;
}

/* Keep simulation and mixing on their original deterministic 60 Hz clock. */
static unsigned presentation_ticks(bool rewinding)
{
    auto &timing = g_presentation_timing;
    if (rewinding) return 1;
    timing.phase += kNativeRefresh;
    unsigned ticks = timing.phase / timing.fps;
    timing.phase %= timing.fps;
    return ticks;
}

/* Allocation bounds belong to the current frontend, not to a saved frame.
 * Once announced they only grow, including while loading an older state. */
static void output_geometry(int width, int height, bool notify,
                            unsigned required_width, unsigned required_height, float aspect)
{
    if (width <= 0 || height <= 0) return;
    if ((unsigned)width > required_width) required_width = (unsigned)width;
    if ((unsigned)height > required_height) required_height = (unsigned)height;
    if (aspect <= 0.0f) aspect = (float)width / height;
    bool changed = width != g_width || height != g_height || aspect != g_aspect;
    bool grow = required_width > g_max_width || required_height > g_max_height;
    g_width = width; g_height = height;
    g_aspect = aspect;
    if (!g_av_announced) {
        g_max_width = required_width;
        g_max_height = required_height;
    } else {
        if (required_width > g_max_width) g_max_width = required_width;
        if (required_height > g_max_height) g_max_height = required_height;
    }
    if (notify && (changed || grow)) {
        struct retro_system_av_info av;
        system_av_info(&av);
        if (!grow || !env_cb(RETRO_ENVIRONMENT_SET_SYSTEM_AV_INFO, &av))
            env_cb(RETRO_ENVIRONMENT_SET_GEOMETRY, &av.geometry);
    }
    if (notify) g_av_announced = true;
}

struct video_presentation {
    obor_crt_frame raster, canvas;
    int crop_x, crop_y, crop_width, crop_height;
    int shift_x, shift_y;
    unsigned software_rotation;
};

static int32_t read_presentation_global(const char *name, double *value)
{
    return g_booted && g_vtbl->get_content_number(name, value);
}

static void content_video_fields(int (&fields)[OBOR_TARGET_COUNT])
{
    const auto &policy = g_content_choice.presentation;
    unsigned scopes = presentation_scopes(g_video_options);
    if (!scopes) return;
    for (unsigned i = 0; i < policy.number_count; ++i) {
        const auto &rule = policy.numbers[i];
        if (rule.target < OBOR_TARGET_WINDOW_W || !(scopes & (1u << rule.scope))) continue;
        double condition;
        if (rule.condition[0] &&
            (!read_presentation_global(rule.condition, &condition) || condition == 0)) continue;
        double value;
        if (!obor_presentation_number(rule.expression, read_presentation_global, &value))
            continue;
        if (value >= INT_MIN && value <= INT_MAX) fields[rule.target] = (int)value;
    }
}

/* Use the same layout to negotiate and render loading screens and game frames. */
static video_presentation video_geometry(int width, int height, bool notify)
{
    g_source_width = width;
    g_source_height = height;
    const auto &options = g_video_options;
    unsigned rotation = options.rotation;
    unsigned paired_rotation = OBOR_ROTATION_NONE;
    if (options.crt && options.vertical)
        paired_rotation = rotation & 1u ? rotation : (unsigned)OBOR_ROTATION_LEFT;
    request_frontend_rotation(paired_rotation);

    bool vertical = options.vertical != ((rotation & 1u) != 0);
    const auto &policy = g_content_choice.presentation;
    auto window = (options.crt && options.content_overrides) ?
        policy.crt_rasters[vertical] : obor_window_raster{};
    obor_crt_mode mode = options.content_overrides ? policy.crt_mode : obor_crt_mode{};
    int fields[OBOR_TARGET_COUNT] = {};
    content_video_fields(fields);
    int target_width = window.width ? window.width : width;
    int target_height = window.height ? window.height : height;
    if (!window.width) {
        if (fields[OBOR_TARGET_WINDOW_W] > 0 && fields[OBOR_TARGET_WINDOW_W] <= 3840)
            target_width = fields[OBOR_TARGET_WINDOW_W];
        if (fields[OBOR_TARGET_WINDOW_H] > 0 && fields[OBOR_TARGET_WINDOW_H] <= 2160)
            target_height = fields[OBOR_TARGET_WINDOW_H];
    }
    obor_crt_frame raster = {width, height, width, height, 1, 0, 0.0f};
    if (width <= OBOR_CRT_MAX_EXTENT && height <= OBOR_CRT_MAX_EXTENT &&
        (target_width != width || target_height != height)) {
        raster.width = raster.image_width = target_width;
        raster.height = raster.image_height = target_height;
        obor_crt_fit(&raster, width, height, target_width, target_height);
        raster.prescale = obor_crt_prescale(&raster, width, height);
    }

    int left = fields[OBOR_TARGET_CROP_LEFT], top = fields[OBOR_TARGET_CROP_TOP];
    int right = fields[OBOR_TARGET_CROP_RIGHT], bottom = fields[OBOR_TARGET_CROP_BOTTOM];
    if (left < 0 || top < 0 || right < 0 || bottom < 0 ||
        (int64_t)left + right >= raster.width || (int64_t)top + bottom >= raster.height)
        left = top = right = bottom = 0;
    int crop_width = raster.width - left - right, crop_height = raster.height - top - bottom;
    obor_crt_frame canvas = options.crt ?
        obor_crt_layout(crop_width, crop_height, vertical, options.canvas_width,
                        options.canvas_height, mode) :
        obor_crt_frame{crop_width, crop_height, crop_width, crop_height, 1, 0, 0.0f};
    unsigned software_rotation = (rotation + 4u - g_frontend_rotation) & 3u;
    bool swap_axes = (software_rotation & 1u) != 0;
    int out_w = swap_axes ? canvas.height : canvas.width;
    int out_h = swap_axes ? canvas.width : canvas.height;
    float aspect = canvas.aspect > 0.0f ? canvas.aspect : (float)canvas.width / canvas.height;
    /* The extent is the submitted framebuffer. The aspect includes both turns. */
    if (rotation & 1u) aspect = 1.0f / aspect;

    /* With CRT enabled only the composed raster reaches the frontend. A
     * larger internal movie surface must not restart its video driver while
     * that raster stays unchanged. Keep the default CRT fit in the native
     * path's reservation so enabling it can reuse the existing buffer. */
    unsigned reserve_width = 0, reserve_height = 0;
    if (!options.crt) {
        obor_crt_frame fallback = obor_crt_layout(width, height, vertical,
            options.canvas_width, options.canvas_height, mode);
        reserve_width = (unsigned)(swap_axes ? fallback.height : fallback.width);
        reserve_height = (unsigned)(swap_axes ? fallback.width : fallback.height);
    }
    output_geometry(out_w, out_h, notify, reserve_width, reserve_height, aspect);
    return { raster, canvas, left, top, crop_width, crop_height,
             fields[OBOR_TARGET_SHIFT_X], fields[OBOR_TARGET_SHIFT_Y], software_rotation };
}

static bool reserve_video_buffer(video_buffer &buffer, int width, int height)
{
    if ((size_t)width > SIZE_MAX / sizeof(uint32_t) / (size_t)height) return false;
    size_t count = (size_t)width * height;
    if (count <= buffer.capacity) return true;
    uint32_t *pixels = (uint32_t *)realloc(buffer.pixels, count * sizeof(*pixels));
    if (!pixels) return false;
    buffer = { pixels, count };
    return true;
}

static void shift_video(uint32_t *dst, const uint32_t *src, int width, int height, int pitch,
                        int dx, int dy)
{
    memset(dst, 0, (size_t)width * height * sizeof(*dst));
    if (dx <= -width || dx >= width || dy <= -height || dy >= height) return;
    int dst_x = dx > 0 ? dx : 0, dst_y = dy > 0 ? dy : 0;
    int src_x = dx < 0 ? -dx : 0, src_y = dy < 0 ? -dy : 0;
    int columns = width - dst_x - src_x, rows = height - dst_y - src_y;
    for (int y = 0; y < rows; ++y)
        memcpy(dst + (size_t)(dst_y + y) * width + dst_x,
               src + (size_t)(src_y + y) * pitch + src_x, (size_t)columns * sizeof(*dst));
}

static bool present_video(const uint32_t *px, int width, int height, int pitch)
{
    uint64_t preparation_begin = obor_latency_begin();
    if (!px || width <= 0 || height <= 0) {
        obor_latency_end(OBOR_LATENCY_VIDEO_PREPARE, g_frame_no, preparation_begin);
        uint64_t callback_begin = obor_latency_begin();
        video_cb(NULL, (unsigned)g_width, (unsigned)g_height, 0);
        obor_latency_end(OBOR_LATENCY_VIDEO_CALLBACK, g_frame_no, callback_begin);
        return true;
    }
    video_presentation presentation = video_geometry(width, height, true);
    const auto &raster = presentation.raster;
    const auto &canvas = presentation.canvas;
    bool make_window = raster.width != width || raster.height != height;
    int crop_width = presentation.crop_width, crop_height = presentation.crop_height;
    bool compose = crop_width != raster.width || crop_height != raster.height ||
                   canvas.width != crop_width || canvas.height != crop_height ||
                   canvas.image_width != crop_width || canvas.image_height != crop_height;
    bool shift = presentation.shift_x || presentation.shift_y;
    if ((make_window && !reserve_video_buffer(g_window_buffer, raster.width, raster.height)) ||
        (compose && !reserve_video_buffer(g_crt_buffer, canvas.width, canvas.height)) ||
        (shift && !reserve_video_buffer(g_shift_buffer, canvas.width, canvas.height)) ||
        (presentation.software_rotation && !reserve_video_buffer(g_rotation_buffer, g_width, g_height))) {
        error_screen("Could not allocate the video presentation framebuffer.");
        present_error_frame();
        return false;
    }
    if (make_window) {
        obor_crt_present(g_window_buffer.pixels, &raster, px, width, height, pitch);
        px = g_window_buffer.pixels;
        width = pitch = raster.width;
        height = raster.height;
    }
    px += (size_t)presentation.crop_y * pitch + presentation.crop_x;
    width = crop_width;
    height = crop_height;
    if (compose) {
        obor_crt_present(g_crt_buffer.pixels, &canvas, px, width, height, pitch);
        px = g_crt_buffer.pixels;
        width = pitch = canvas.width;
        height = canvas.height;
    }
    if (shift) {
        shift_video(g_shift_buffer.pixels, px, width, height, pitch,
                    presentation.shift_x, presentation.shift_y);
        px = g_shift_buffer.pixels;
        pitch = width;
    }
    if (presentation.software_rotation) {
        obor_rotate_frame(g_rotation_buffer.pixels, px, width, height, pitch,
                          presentation.software_rotation);
        px = g_rotation_buffer.pixels;
        width = pitch = g_width;
        height = g_height;
    }
    glue_dump_maybe(px, width, height, pitch);
    obor_latency_end(OBOR_LATENCY_VIDEO_PREPARE, g_frame_no, preparation_begin);
    uint64_t callback_begin = obor_latency_begin();
    video_cb(px, (unsigned)width, (unsigned)height, (size_t)pitch * sizeof(uint32_t));
    obor_latency_end(OBOR_LATENCY_VIDEO_CALLBACK, g_frame_no, callback_begin);
    return true;
}

void retro_set_controller_port_device(unsigned port, unsigned device)
{
    (void)port;
    (void)device;
}

static void startup_model_progress(int completed, int total)
{
    if (completed <= 0 || total <= 0) return;
    unsigned percent = completed >= total ? 100u :
        (unsigned)((uint64_t)completed * 100 / total);
    if (percent > g_startup_model_percent) g_startup_model_percent = percent;
}

static unsigned content_level_rate(int level)
{
    g_content_level = level;
    if (!g_video_options.crt || !g_video_options.content_overrides ||
        level < 0 || level >= OBOR_PRESENTATION_LEVELS) return 0;
    return g_content_choice.presentation.level_rates[level];
}

static unsigned content_numeric_overrides(const obor_numeric_override **rules, unsigned *scopes)
{
    const auto &policy = g_content_choice.presentation;
    *rules = policy.numbers;
    *scopes = presentation_scopes(g_video_options);
    return policy.number_count;
}

static bool boot_engine(void)
{
    g_startup_reported = false;
    g_startup_model_percent = 0;
    obor_dbg("boot: pristine capture");
    pristine_capture();  /* first boot: engines still virgin — snapshot */
    obor_dbg("boot: pristine restore");
    pristine_restore();  /* every boot starts from virgin engine statics */
    obor_boot_info boot;
    memset(&boot, 0, sizeof(boot));
    boot.abi_version = OBOR_ABI_VERSION;
    if (!obor_build_identity_read(boot.state_build_identity)) {
        fprintf(stderr, "[AnyBOR] missing linked state identity; core build is incomplete\n");
        return false;
    }
    boot.pak_path = g_pak_path;
    boot.save_dir = g_game_dir[0] ? g_game_dir : NULL;
    boot.log_dir = NULL;
    boot.arena_reserved = g_arena_owned ? 1 : 0;
    boot.sample_rate = 44100;
    boot.raw_dir = g_raw ? 1 : 0;
    const obor_profile_def *selected_profile = NULL;
    for (const auto &profile : kProfiles)
        if (!strcmp(profile.name, g_logical_engine)) selected_profile = &profile;
    if (!selected_profile) return false;
    boot.profile_build = (uint32_t)selected_profile->build;
    boot.profile_key = selected_profile->name;
    boot.profile_features = selected_profile->features;
    boot.resource_event = engine_resource_event;
    boot.state_content = obor_state_session_settings.content;
    boot.state_compression = obor_state_session_settings.compression;
    boot.startup_progress = startup_model_progress;
    boot.content_level_rate = content_level_rate;
    boot.content_numeric_overrides = content_numeric_overrides;
    g_content_level = -1;
    obor_engine_region regions[OBOR_MAX_ENGINE_REGIONS];
    const size_t n_eng = sizeof(kEngineDefs) / sizeof(kEngineDefs[0]);
    static_assert(sizeof(kEngineDefs) / sizeof(kEngineDefs[0]) <= OBOR_MAX_ENGINE_REGIONS,
                  "Too many engine state regions");
    for (size_t i = 0; i < n_eng; ++i) {
        regions[i].begin = (uintptr_t)kEngineDefs[i].bss_begin;
        regions[i].end = (uintptr_t)kEngineDefs[i].bss_end;
        regions[i].engine_build = kEngineDefs[i].build;
    }
    boot.engine_regions = regions;
    boot.engine_region_count = (uint32_t)n_eng;
    obor_dbg("boot: p_boot enter (engine %s)", g_engine);
    engine_log_begin();
    int r = p_boot(&boot);
    /* Loose data has no packed-resource reserve hint. Finish its initial
     * resource load before the frontend fixes the state allocation. */
    if (r && g_raw) {
        while (!p_startup_complete()) {
            if (!p_run_frame()) { r = 0; break; }
        }
    }
    if (!r && p_get_exit_status() == OBOR_EXIT_MEMORY_FAULT)
        stop_faulted_engine();
    obor_dbg("boot: p_boot -> %d", r);
    return r != 0;
}

void retro_reset(void)
{
    g_reverse_has_snapshot = false;
    if (g_loading) {
        struct retro_game_info info = {};
        char path[sizeof(g_error_path)];
        snprintf(path, sizeof(path), "%s", g_error_path);
        info.path = path;
        uint32_t capacity = g_state_capacity;
        if (!loading_begin(&info, true)) error_screen(NULL);
        if (g_state_capacity < capacity) g_state_capacity = capacity;
        return;
    }
    /* True restart: shut the engine down (fds, logs, the whole arena),
     * restore pristine statics and boot again — re-running the version
     * decision so a changed anybor_engine core option takes effect NOW. */
    if (g_error_active) {
        struct retro_game_info info = {};
        char path[sizeof(g_error_path)];
        snprintf(path, sizeof(path), "%s", g_error_path);
        info.path = path;
        g_error_active = false;
        /* Retry from the original content path, with the new core option.
         * The normal load path is used, without clearing game saves. */
        obor_load_retry(&info);
        return;
    }
    if (!g_booted)
        return;
    /* Archive descriptors are read from the ZIP, not from an extracted cache.
     * A descriptor may also change its payload between restarts. */
    bool reroute = g_zip_engine_scanned || g_content_choice.descriptor[0];
    if (!reroute && g_content_choice.source[0]) {
        char target[4096];
        obor_content_choice refreshed;
        reroute = !obor_content_loose(g_content_choice.source, target, sizeof(target), refreshed) ||
                  refreshed.descriptor[0];
        if (!reroute) g_content_choice = refreshed;
    }
    if (reroute) {
        struct retro_game_info info = {};
        char path[sizeof(g_error_path)];
        snprintf(path, sizeof(path), "%s", g_error_path);
        info.path = path;
        uint32_t capacity = g_state_capacity;
        obor_load_retry(&info);
        if (g_state_capacity < capacity) g_state_capacity = capacity;
        return;
    }
    g_booted = false;
    obor_dbg("reset: shutdown engine %s", g_engine);
    rumble_stop();
    macro_reset_all();
    gamelog_close();
    g_map_sent = 0;
    p_shutdown();
    engine_resources_close();

    decide_engine(); /* may pick a different engine than last time */
    log_cb(RETRO_LOG_INFO, "[OpenBOR] reset: booting engine %s\n", g_engine);

    char err[256] = "";
    if (!select_engine_vtbl(g_engine, err, sizeof(err))) {
        error_screen(err);
        return;
    }
    if (!boot_engine()) {
        char reason[sizeof(g_error_reason)];
        if (!engine_log_error(reason, sizeof(reason)))
            snprintf(reason, sizeof(reason), "Engine %s failed to start this game.", g_engine);
        error_screen(reason);
        return;
    }
    g_booted = true;
    if (!g_raw)
        obor_padmap_apply(env_cb, g_pak_path, &g_content_choice.controls);
}

/* ---- test-only instrumentation, env-gated, inert in normal use ----
 * OBOR_GLUE_INPUT="F-T:btn,..." synthesizes pad input inside the glue (so a
 * real frontend can be driven to gameplay unattended); btn = up down left
 * right attack jump special start esc. Optional :period:held suffix pulses
 * any button (e.g. 1800-6000:attack:20:4). OBOR_TRACE=/path logs every
 * run/serialize/unserialize call with the frame counter, to compare a real
 * frontend's rewind sequence against the reference harness.
 * OBOR_GLUE_INPUT_AFTER_LOAD=1 makes these input frames relative to the last
 * successful load (first subsequent run is frame1). It sends no synthetic
 * input before that load. This makes checkpoint comparisons independent of
 * asynchronous frontend load-command latency; ordinary test routes are unchanged.
 * (g_trace/g_frame_no/g_last_unser are declared with the top statics.) */

/* OBOR_GLUE_DUMP=prefix: write a PPM of every frame presented within 2
 * frames of an unserialize — captures exactly what a real frontend shows
 * while rewinding. OBOR_GLUE_DUMP_AT=N instead captures exact core frame N;
 * OBOR_GLUE_DUMP_FROM=N with optional OBOR_GLUE_DUMP_TO=M captures a range. */
static void glue_dump_maybe(const uint32_t *px, int w, int h, int pitch_px)
{
    /* Diagnostic environment and counters belong to this process. Loading a
     * state must neither recover another process's getenv pointer nor replace
     * the current capture range with the saved process's disabled settings. */
    static const char *pfx OBOR_RUNTIME;
    static long exact_frame OBOR_RUNTIME = -1;
    static long first_frame OBOR_RUNTIME = -1;
    static long last_frame OBOR_RUNTIME = -1;
    static int checked OBOR_RUNTIME;
    if (!checked) {
        checked = 1;
        pfx = getenv("OBOR_GLUE_DUMP");
        const char *value = getenv("OBOR_GLUE_DUMP_AT");
        if (value)
            exact_frame = strtol(value, NULL, 10);
        value = getenv("OBOR_GLUE_DUMP_FROM");
        if (value)
            first_frame = strtol(value, NULL, 10);
        value = getenv("OBOR_GLUE_DUMP_TO");
        if (value)
            last_frame = strtol(value, NULL, 10);
    }
    static int dumped OBOR_RUNTIME;
    if (!pfx || !px || dumped >= 400)
        return;
    if (exact_frame >= 0 ? g_frame_no != exact_frame :
        first_frame >= 0 ? (g_frame_no < first_frame ||
                            (last_frame >= 0 && g_frame_no > last_frame)) :
                           g_frame_no - g_last_unser > 2)
        return;
    dumped++;
    char path[1100];
    snprintf(path, sizeof(path), "%s%06ld.ppm", pfx, g_frame_no);
    FILE *f = obor_fopen(path, "wb");
    if (!f)
        return;
    fprintf(f, "P6\n%d %d\n255\n", w, h);
    for (int y = 0; y < h; y++) {
        const uint32_t *row = px + (size_t)y * pitch_px;
        for (int x = 0; x < w; x++) {
            unsigned char rgb[3] = { (unsigned char)(row[x] >> 16),
                                     (unsigned char)(row[x] >> 8),
                                     (unsigned char)row[x] };
            fwrite(rgb, 1, 3, f);
        }
    }
    fclose(f);
}

static void trace_init(void)
{
    static int done OBOR_RUNTIME;
    if (done)
        return;
    done = 1;
    const char *p = getenv("OBOR_TRACE");
    if (p)
        g_trace = obor_fopen(p, "wt");
}

struct gseg { int from, to; unsigned id; int period, held; };
static gseg g_gsegs[16];
static int g_ngsegs = -1;

static void ginput_init(void)
{
    if (g_ngsegs >= 0)
        return;
    g_ngsegs = 0;
    const char *relative = getenv("OBOR_GLUE_INPUT_AFTER_LOAD");
    g_input_after_load = relative && !strcmp(relative, "1");
    const char *s = getenv("OBOR_GLUE_INPUT");
    if (!s)
        return;
    char *dup = strdup(s);
    for (char *tok = strtok(dup, ","); tok && g_ngsegs < 16;
         tok = strtok(NULL, ",")) {
        int from, to, period = 0, held = 0;
        char btn[24];
        int fields = sscanf(tok, "%d-%d:%23[^:]:%d:%d", &from, &to, btn,
                            &period, &held);
        if ((fields == 3 || (fields == 5 && period > 0 && held > 0 && held <= period)) &&
            from >= 0 && to >= from) {
            unsigned id = 999;
            if (!strcmp(btn, "up")) id = RETRO_DEVICE_ID_JOYPAD_UP;
            else if (!strcmp(btn, "down")) id = RETRO_DEVICE_ID_JOYPAD_DOWN;
            else if (!strcmp(btn, "left")) id = RETRO_DEVICE_ID_JOYPAD_LEFT;
            else if (!strcmp(btn, "right")) id = RETRO_DEVICE_ID_JOYPAD_RIGHT;
            else if (!strcmp(btn, "attack")) id = RETRO_DEVICE_ID_JOYPAD_Y;
            else if (!strcmp(btn, "jump")) id = RETRO_DEVICE_ID_JOYPAD_B;
            else if (!strcmp(btn, "special")) id = RETRO_DEVICE_ID_JOYPAD_A;
            else if (!strcmp(btn, "start")) id = RETRO_DEVICE_ID_JOYPAD_START;
            else if (!strcmp(btn, "esc")) id = RETRO_DEVICE_ID_JOYPAD_SELECT;
            if (id != 999) {
                g_gsegs[g_ngsegs].from = from;
                g_gsegs[g_ngsegs].to = to;
                g_gsegs[g_ngsegs].id = id;
                g_gsegs[g_ngsegs].period = fields == 5 ? period :
                    id == RETRO_DEVICE_ID_JOYPAD_START ? 30 : 0;
                g_gsegs[g_ngsegs].held = fields == 5 ? held : 4;
                g_ngsegs++;
            }
        }
    }
    free(dup);
}

static int ginput_state(unsigned id)
{
    if (g_input_after_load && !g_input_has_origin) return 0;
    const long frame = g_input_after_load ? g_frame_no - g_input_origin : g_frame_no;
    for (int i = 0; i < g_ngsegs; i++) {
        if (frame >= g_gsegs[i].from && frame <= g_gsegs[i].to &&
            g_gsegs[i].id == id) {
            if (g_gsegs[i].period)
                return ((frame - g_gsegs[i].from) % g_gsegs[i].period) < g_gsegs[i].held;
            return 1;
        }
    }
    return 0;
}

/* RetroPad -> OpenBOR mapping (per player). */
static const struct { unsigned retro; int obor; } kPadMap[] = {
    { RETRO_DEVICE_ID_JOYPAD_UP, OBOR_BTN_UP },
    { RETRO_DEVICE_ID_JOYPAD_DOWN, OBOR_BTN_DOWN },
    { RETRO_DEVICE_ID_JOYPAD_LEFT, OBOR_BTN_LEFT },
    { RETRO_DEVICE_ID_JOYPAD_RIGHT, OBOR_BTN_RIGHT },
    { RETRO_DEVICE_ID_JOYPAD_Y, OBOR_BTN_ATTACK },
    { RETRO_DEVICE_ID_JOYPAD_B, OBOR_BTN_JUMP },
    { RETRO_DEVICE_ID_JOYPAD_A, OBOR_BTN_SPECIAL },
    { RETRO_DEVICE_ID_JOYPAD_X, OBOR_BTN_ATTACK2 },
    { RETRO_DEVICE_ID_JOYPAD_L, OBOR_BTN_ATTACK3 },
    { RETRO_DEVICE_ID_JOYPAD_R, OBOR_BTN_ATTACK4 },
    { RETRO_DEVICE_ID_JOYPAD_START, OBOR_BTN_START },
    { RETRO_DEVICE_ID_JOYPAD_SELECT, OBOR_BTN_ESC },
};

static bool present_audio_frame(const int16_t *samples, int32_t frames,
                                bool profile_callbacks)
{
    if (p_get_exit_status() == OBOR_EXIT_MEMORY_FAULT) {
        char reason[sizeof(g_error_reason)];
        p_get_fault_message(reason, sizeof(reason));
        stop_faulted_engine();
        error_screen(reason);
        present_error_frame();
        return false;
    }
    if (frames > 0) {
        uint64_t begin = profile_callbacks ? obor_profile_now() : 0;
        uint64_t callback_begin = obor_latency_begin();
        audio_batch_cb(samples, (size_t)frames);
        obor_latency_end(OBOR_LATENCY_AUDIO_CALLBACK, g_frame_no, callback_begin);
        if (profile_callbacks)
            obor_profile_record("audio", g_frame_no, begin, obor_profile_now(),
                                0, 0, 0, 1, 0);
    }
    return true;
}

static bool run_game_tick(bool frontend_rewind, bool deliver_video)
{
    /* Current delivered audio is captured with the ordinary module globals
     * so reverse presentation can replay it without advancing the mixer. */
    static struct { int16_t samples[2048 * 2]; int32_t frames; } audio_frame;
    obor_latency_run_scope latency_scope(&g_frame_no);
    uint64_t profile_begin = obor_profile_now();

    ginput_init();
    trace_init();
    if (p_startup_complete()) g_frame_no++;
    if (g_trace) {
        fprintf(g_trace, "f=%ld run\n", g_frame_no);
        fflush(g_trace);
    }

    input_poll_cb();

    /* After the first successful restore, an explicit rewind throttle
     * presents the saved frame without advancing the engine. A forward tick
     * could enter model preparation or restart a
     * movie and then prevent the next otherwise valid restore. Hold the last
     * complete frame across refused history entries too: the frontend may
     * retain such entries after a failed capture. Ordinary state loads and
     * frontends without throttle reporting keep the normal forward path.
     * Before that first restore, allow an already active preload to finish:
     * its safety guard may temporarily defer every restore callback. */
    if (!frontend_rewind) g_reverse_has_snapshot = false;
    bool rewind_replay = frontend_rewind && g_reverse_has_snapshot;
    bool present_restored = rewind_replay &&
                           audio_frame.frames >= 0 && audio_frame.frames <= 2048;
    if (!rewind_replay) {
        for (int pl = 0; pl < OBOR_MAX_PLAYERS; pl++) {
            /* an in-flight special-move macro owns this player's pad */
            if (macro_frame(pl))
                continue;
            /* left analog stick doubles as the D-pad (threshold at half
             * deflection) — beat'em'up movement is 8-way digital anyway */
            int16_t ax = 0, ay = 0;
            if (g_analog) {
                ax = input_state_cb((unsigned)pl, RETRO_DEVICE_ANALOG,
                                    RETRO_DEVICE_INDEX_ANALOG_LEFT,
                                    RETRO_DEVICE_ID_ANALOG_X);
                ay = input_state_cb((unsigned)pl, RETRO_DEVICE_ANALOG,
                                    RETRO_DEVICE_INDEX_ANALOG_LEFT,
                                    RETRO_DEVICE_ID_ANALOG_Y);
            }
            unsigned pressed = 0;
            for (size_t i = 0; i < sizeof(kPadMap) / sizeof(kPadMap[0]); i++) {
                int16_t v = input_state_cb((unsigned)pl, RETRO_DEVICE_JOYPAD, 0,
                                           kPadMap[i].retro);
                if (!v) {
                    switch (kPadMap[i].retro) {
                    case RETRO_DEVICE_ID_JOYPAD_UP: v = ay < -16384; break;
                    case RETRO_DEVICE_ID_JOYPAD_DOWN: v = ay > 16384; break;
                    case RETRO_DEVICE_ID_JOYPAD_LEFT: v = ax < -16384; break;
                    case RETRO_DEVICE_ID_JOYPAD_RIGHT: v = ax > 16384; break;
                    }
                }
                if (pl == 0 && g_ngsegs > 0 && !v)
                    v = (int16_t)ginput_state(kPadMap[i].retro);
                if (v) pressed |= 1u<<kPadMap[i].obor;
            }
            pressed = obor_content_buttons(g_content_choice.controls, pressed);
            for (int button=0;button<OBOR_BTN_COUNT;++button)
                p_set_button(pl, button, (pressed>>button)&1u);
        }
    }

    bool debug_restored_frame = getenv("OBOR_DEBUG") &&
                                g_last_unser >= g_frame_no - 1;
    if (debug_restored_frame)
        fprintf(stderr, "[obor] entering first engine frame after restore frame=%ld\n",
                g_frame_no);
    /* A restored state already has its exact framebuffer. Running one forward
     * tick while explicitly rewinding can close a restored menu or start a
     * movie worker again. Ordinary loads and unsupported frontends retain the
     * existing forward path; reverse mode must be reported by the frontend. */
    int engine_running = present_restored ? 1 : p_run_frame();
    if (debug_restored_frame)
        fprintf(stderr, "[obor] first engine frame after restore returned ok=%d\n",
                engine_running);
    if (!engine_running) {
        obor_profile_record("run", g_frame_no, profile_begin,
                            obor_profile_now(), 0, 0, 0, 0, -1);
        int32_t status = p_get_exit_status();
        if (status != 0) {
            char reason[sizeof(g_error_reason)];
            /* Closing the engine log flushes borShutdown's final message. */
            if (status == OBOR_EXIT_MEMORY_FAULT) stop_faulted_engine();
            else { p_shutdown(); engine_resources_close(); }
            g_booted = false;
            if (!engine_log_error(reason, sizeof(reason)))
                snprintf(reason, sizeof(reason), "Engine %s stopped with error %d.",
                         g_engine, (int)status);
            error_screen(reason);
            present_error_frame();
        } else {
            env_cb(RETRO_ENVIRONMENT_SHUTDOWN, NULL);
        }
        return false;
    }
    uint64_t profile_core_end = obor_profile_now();

    if (!g_startup_reported && p_startup_complete()) {
        g_startup_reported = true;
        log_cb(RETRO_LOG_INFO, "[OpenBOR] resource initialization complete\n");
    }

    rumble_frame();
    gamelog_frame();
    if ((g_frame_no & 63) == 0)
        memmap_maybe_send();

    const uint32_t *px = NULL;
    int32_t w = 0, h = 0, pitch = 0;
    if (deliver_video) p_get_video(&px, &w, &h, &pitch);
    const char *callback_profile = getenv("OBOR_PROFILE_CALLBACKS");
    bool profile_callbacks = g_profile.file && callback_profile &&
                             !strcmp(callback_profile, "1");
    /* Keep both complete payloads from this engine tick. The platform policy
     * chooses which frontend callback may wait first. */
    bool audio_first = obor_state_audio_first();
    bool prepare = !rewind_replay && p_startup_complete() &&
        obor_state_coded_enabled() &&
        obor_state_option("OBOR_STATE_PREPARE", OBOR_STATE_DEFAULT_ENABLED) &&
        obor_capture_cadence_due(&g_capture_cadence, (uint64_t)g_frame_no);
    if (!present_restored && (prepare || audio_first))
        audio_frame.frames = p_get_audio(audio_frame.samples, 2048);
    if (prepare) {
        /* Audio advances authoritative mixer state. Finish it before preparing
         * the current image, then spend codec work before presentation waits.
         * The requested serialize still revalidates every changed byte. */
        if (p_get_exit_status() != OBOR_EXIT_MEMORY_FAULT) {
            uint64_t begin = obor_profile_now();
            uint32_t prepared = p_prepare_state();
            obor_profile_record("prepare", g_frame_no, begin, obor_profile_now(),
                                g_state_capacity, prepared, 0, prepared != 0, 0);
            if (!prepared) obor_capture_cadence_reset(&g_capture_cadence);
        }
    }
    if (audio_first && !present_audio_frame(audio_frame.samples, audio_frame.frames,
                                           profile_callbacks)) return false;
    if (deliver_video) {
        uint64_t video_begin = profile_callbacks ? obor_profile_now() : 0;
        bool presented = present_video(px, w, h, pitch);
        if (profile_callbacks)
            obor_profile_record("video", g_frame_no, video_begin, obor_profile_now(),
                                0, 0, 0, presented, 0);
        if (!presented) return false;
    }
    if (px && w > 0 && h > 0) {
        free(g_loading_pixels);
        g_loading_pixels = NULL;
    }

    if (!present_restored && !prepare && !audio_first)
        audio_frame.frames = p_get_audio(audio_frame.samples, 2048);
    int32_t frames = audio_frame.frames;
    if (!audio_first && !present_audio_frame(audio_frame.samples, frames,
                                            profile_callbacks)) return false;
    if (present_restored && getenv("OBOR_STATE_TIMING"))
        fprintf(stderr, "[obor-reverse] frame=%ld present_snapshot=1 audio_frames=%d\n",
                g_frame_no, frames);
    /* For run rows the final profile column is an active-player bitmask.
     * State rows continue to use it for RETRO_ENVIRONMENT_GET_SAVESTATE_CONTEXT.
     * This opt-in signal records whether a route reached a live player entity
     * rather than measuring a title/menu screen. */
    int active_players = 0;
    if (g_profile.file) {
        for (int pl = 0; pl < OBOR_MAX_PLAYERS; ++pl) {
            if (p_get_player_state(pl, NULL, 0, NULL))
                active_players |= 1 << pl;
        }
    }
    obor_profile_record("run", g_frame_no, profile_begin, profile_core_end,
                        0, 0, 0, 1, active_players);
    return true;
}

void retro_run(void)
{
    if (g_loading) {
        loading_run();
        return;
    }

    bool upd = false;
    if ((g_booted || g_error_active) && env_cb(RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE, &upd) && upd)
        refresh_options();
    if (g_error_active) {
        if (g_fault_pending) {
            char reason[sizeof(g_error_reason)];
            snprintf(reason, sizeof(reason), "%s", g_error_reason);
            g_fault_pending = false;
            stop_faulted_engine();
            error_screen(reason);
        }
        update_presentation_timing(kNativeRefresh);
        if (input_poll_cb) input_poll_cb();
        present_error_frame();
        return;
    }
    if (!g_booted) return;

    obor_profile_init();
    const auto &mode = g_content_choice.presentation.crt_mode;
    unsigned refresh = kNativeRefresh;
    if (g_video_options.crt && g_video_options.content_overrides) {
        unsigned level_rate = content_level_rate(g_content_level);
        refresh = obor_crt_refresh(level_rate ? level_rate : refresh, mode);
    }
    update_presentation_timing(refresh);

    struct retro_throttle_state throttle = {};
    bool frontend_rewind = p_startup_complete() &&
                         env_cb(RETRO_ENVIRONMENT_GET_THROTTLE_STATE, &throttle) &&
                         throttle.mode == RETRO_THROTTLE_REWINDING;
    unsigned ticks = presentation_ticks(frontend_rewind);
    if (!ticks) {
        input_poll_cb();
        bool can_dupe = false;
        if (env_cb(RETRO_ENVIRONMENT_GET_CAN_DUPE, &can_dupe) && can_dupe) {
            video_cb(NULL, (unsigned)g_width, (unsigned)g_height, 0);
        } else {
            const uint32_t *pixels;
            int32_t width, height, pitch;
            p_get_video(&pixels, &width, &height, &pitch);
            present_video(pixels, width, height, pitch);
        }
        return;
    }
    for (unsigned tick = 0; tick < ticks; ++tick)
        if (!run_game_tick(frontend_rewind, tick + 1 == ticks)) break;
}

/* ---- single-file core machinery -------------------------------------
 * The engine builds live in this same module as partial-linked objects with
 * only their suffixed ABI exported (see Makefile.libretro `partial`). Two
 * consequences handled here:
 *  - a fresh boot needs pristine engine statics: capture the module's
 *    writable segments once, restore per boot;
 *  - those segments include the glue's own statics, so every bulk restore
 *    (pristine or savestate) is bracketed by a save/load of glue state. */

/* writable, non-RELRO segments of this module (glue + all engines) */
typedef struct { uintptr_t vaddr; size_t size; } gseg_t;
static gseg_t g_gsegs2[16];
static int g_ngsegs2;
static uint8_t *g_pristine;

typedef struct {
    retro_environment_t env;
    retro_video_refresh_t video;
    retro_audio_sample_batch_t audio;
    retro_input_poll_t poll;
    retro_input_state_t input;
    retro_log_printf_t log;
    const obor_vtbl *vtbl;
    bool booted;
    bool startup_reported;
    bool fault_quarantined;
    bool fault_pending;
    uint32_t state_capacity;
    int width, height;
    int source_width, source_height;
    float aspect;
    unsigned max_width, max_height;
    bool av_announced;
    presentation_timing timing;
    video_buffer window_buffer, crt_buffer, shift_buffer, rotation_buffer;
    video_options presentation_options;
    unsigned requested_rotation, frontend_rotation;
    uint32_t *loading_pixels;
    int loading_width, loading_height;
    char engine[48];
    char logical_engine[48];
    char saved[1024], pak[4096];
    char error_path[sizeof(g_error_path)];
    FILE *trace, *glog;
    obor_profile_state profile;
    gseg input_segments[16];
    int input_segment_count;
    long frame_no, last_unser;
    bool analog, rumble, macros, gamelog, raw, arena_owned;
    retro_rumble_interface rumble_if;
    bool rumble_have;
    uint64_t rumble_off_at[OBOR_MAX_PLAYERS];
    obor_pm_char pm_chars[OBOR_PM_MAXCH];
    int pm_nchars;
    obor_diagnostics_state diagnostics;
    char game_dir[sizeof(g_game_dir)];
    obor_storage_session storage;
    uint8_t *pristine;
    gseg_t segments[16];
    int nsegments;
} glue_regs;

static void glue_save(glue_regs *r)
{
    r->env = env_cb; r->video = video_cb; r->audio = audio_batch_cb;
    r->poll = input_poll_cb; r->input = input_state_cb; r->log = log_cb;
    r->vtbl = g_vtbl; r->booted = g_booted;
    r->startup_reported = g_startup_reported;
    r->fault_quarantined = g_fault_quarantined;
    r->fault_pending = g_fault_pending;
    r->state_capacity = g_state_capacity;
    r->width = g_width; r->height = g_height;
    r->source_width = g_source_width; r->source_height = g_source_height;
    r->aspect = g_aspect;
    r->max_width = g_max_width; r->max_height = g_max_height;
    r->av_announced = g_av_announced;
    r->timing = g_presentation_timing;
    r->window_buffer = g_window_buffer;
    r->crt_buffer = g_crt_buffer;
    r->shift_buffer = g_shift_buffer; r->rotation_buffer = g_rotation_buffer;
    r->presentation_options = g_video_options;
    r->requested_rotation = g_requested_rotation; r->frontend_rotation = g_frontend_rotation;
    r->loading_pixels = g_loading_pixels;
    r->loading_width = g_loading_width; r->loading_height = g_loading_height;
    memcpy(r->engine, g_engine, sizeof(g_engine));
    memcpy(r->logical_engine, g_logical_engine, sizeof(g_logical_engine));
    memcpy(r->saved, g_save_dir, sizeof(g_save_dir));
    memcpy(r->pak, g_pak_path, sizeof(g_pak_path));
    memcpy(r->error_path, g_error_path, sizeof(g_error_path));
    r->trace = g_trace; r->glog = g_glog_fp;
    r->profile = g_profile;
    memcpy(r->input_segments, g_gsegs, sizeof(g_gsegs));
    r->input_segment_count = g_ngsegs;
    r->frame_no = g_frame_no; r->last_unser = g_last_unser;
    r->analog = g_analog; r->rumble = g_rumble_on;
    r->macros = g_macros_on; r->gamelog = g_gamelog_on;
    r->raw = g_raw; r->arena_owned = g_arena_owned;
    r->rumble_if = g_rumble_if; r->rumble_have = g_rumble_have;
    memcpy(r->rumble_off_at, g_rumble_off_at, sizeof(g_rumble_off_at));
    memcpy(r->pm_chars, g_pm_chars, sizeof(g_pm_chars));
    r->pm_nchars = g_pm_nchars;
    r->diagnostics = g_diagnostics;
    r->storage = g_storage;
    memcpy(r->game_dir, g_game_dir, sizeof(g_game_dir));
    r->pristine = g_pristine;
    r->nsegments = g_ngsegs2;
    memcpy(r->segments, g_gsegs2, sizeof(g_gsegs2));
}

static void glue_load(const glue_regs *r)
{
    env_cb = r->env; video_cb = r->video; audio_batch_cb = r->audio;
    input_poll_cb = r->poll; input_state_cb = r->input; log_cb = r->log;
    g_vtbl = r->vtbl; g_booted = r->booted;
    g_startup_reported = r->startup_reported;
    g_fault_quarantined = r->fault_quarantined;
    g_fault_pending = r->fault_pending;
    g_state_capacity = r->state_capacity;
    g_width = r->width; g_height = r->height;
    g_source_width = r->source_width; g_source_height = r->source_height;
    g_aspect = r->aspect;
    g_max_width = r->max_width; g_max_height = r->max_height;
    g_av_announced = r->av_announced;
    g_presentation_timing = r->timing;
    g_window_buffer = r->window_buffer;
    g_crt_buffer = r->crt_buffer;
    g_shift_buffer = r->shift_buffer; g_rotation_buffer = r->rotation_buffer;
    g_video_options = r->presentation_options;
    g_requested_rotation = r->requested_rotation; g_frontend_rotation = r->frontend_rotation;
    g_loading_pixels = r->loading_pixels;
    g_loading_width = r->loading_width; g_loading_height = r->loading_height;
    memcpy(g_engine, r->engine, sizeof(g_engine));
    memcpy(g_logical_engine, r->logical_engine, sizeof(g_logical_engine));
    memcpy(g_save_dir, r->saved, sizeof(g_save_dir));
    memcpy(g_pak_path, r->pak, sizeof(g_pak_path));
    memcpy(g_error_path, r->error_path, sizeof(g_error_path));
    /* FILE objects belong to this frontend process, never to a snapshot. */
    g_trace = r->trace; g_glog_fp = r->glog;
    g_profile = r->profile;
    memcpy(g_gsegs, r->input_segments, sizeof(g_gsegs));
    g_ngsegs = r->input_segment_count;
    g_frame_no = r->frame_no; g_last_unser = r->last_unser;
    g_analog = r->analog; g_rumble_on = r->rumble;
    g_macros_on = r->macros; g_gamelog_on = r->gamelog;
    g_raw = r->raw; g_arena_owned = r->arena_owned;
    g_rumble_if = r->rumble_if; g_rumble_have = r->rumble_have;
    memcpy(g_rumble_off_at, r->rumble_off_at, sizeof(g_rumble_off_at));
    memcpy(g_pm_chars, r->pm_chars, sizeof(g_pm_chars));
    g_pm_nchars = r->pm_nchars;
    g_diagnostics = r->diagnostics;
    g_storage = r->storage;
    memcpy(g_game_dir, r->game_dir, sizeof(g_game_dir));
    g_pristine = r->pristine;
    g_ngsegs2 = r->nsegments;
    memcpy(g_gsegs2, r->segments, sizeof(g_gsegs2));
}


static void glue_add_segment(uintptr_t begin, uintptr_t end)
{
    uintptr_t runtime_lo, runtime_hi;
    obor_runtime_bounds(&runtime_lo, &runtime_hi);
    if (end <= begin) return;
    if (runtime_hi > runtime_lo && runtime_lo < end && runtime_hi > begin) {
        if (runtime_lo > begin) glue_add_segment(begin, runtime_lo);
        if (runtime_hi < end) glue_add_segment(runtime_hi, end);
        return;
    }
    if (g_ngsegs2 < 16) {
        g_gsegs2[g_ngsegs2].vaddr = begin;
        g_gsegs2[g_ngsegs2++].size = end - begin;
    }
}

#if defined(_WIN32)
static void glue_collect_segments(void)
{
    if (g_ngsegs2)
        return;
    HMODULE mod = NULL;
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                           GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                       (LPCSTR)&glue_collect_segments, &mod);
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)mod;
    const IMAGE_NT_HEADERS *nt =
        (const IMAGE_NT_HEADERS *)((const char *)mod + dos->e_lfanew);
    const IMAGE_SECTION_HEADER *sec = IMAGE_FIRST_SECTION(nt);
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections &&
                         g_ngsegs2 < 16; i++) {
        if (!(sec[i].Characteristics & IMAGE_SCN_MEM_WRITE))
            continue;
        if (memcmp(sec[i].Name, ".idata", 6) == 0 ||
            memcmp(sec[i].Name, ".tls", 4) == 0 ||
            memcmp(sec[i].Name, ".CRT", 4) == 0)
            continue;
        uintptr_t start = (uintptr_t)mod + sec[i].VirtualAddress;
        size_t bytes = sec[i].Misc.VirtualSize;
        glue_add_segment(start, start + bytes);
    }
}
#elif defined(__APPLE__)
#include "anybor_macho.h"

static void glue_macho_seg_cb(uint64_t lo, uint64_t hi, void *context)
{
    (void)context;
    if (g_ngsegs2 >= 16 || hi <= lo)
        return;
    glue_add_segment((uintptr_t)lo, (uintptr_t)hi);
}

/* Darwin: dyld has already slid the image by the time a core is loaded, so
 * the writable ranges of this module come from its own load commands. */
static void glue_collect_segments(void)
{
    if (g_ngsegs2)
        return;
    const struct mach_header_64 *header =
        obor_macho_own_header((const void *)&glue_collect_segments);
    if (!header || !obor_macho_writable_segments(header, glue_macho_seg_cb, NULL))
        g_ngsegs2 = 0;
}
#else
#include <link.h>
static int glue_phdr_cb(struct dl_phdr_info *info, size_t size, void *data)
{
    (void)size; (void)data;
    uintptr_t self = (uintptr_t)&glue_collect_segments;
    int mine = 0;
    for (int i = 0; i < info->dlpi_phnum; i++) {
        const ElfW(Phdr) *ph = &info->dlpi_phdr[i];
        if (ph->p_type != PT_LOAD)
            continue;
        uintptr_t lo = info->dlpi_addr + ph->p_vaddr;
        if (self >= lo && self < lo + ph->p_memsz) { mine = 1; break; }
    }
    if (!mine)
        return 0;
    long host_page = sysconf(_SC_PAGESIZE);
    uint64_t page_mask = (host_page > 0 ? (uint64_t)host_page : 4096) - 1;
    uint64_t rl = 0, rh = 0;
    for (int i = 0; i < info->dlpi_phnum; i++) {
        const ElfW(Phdr) *ph = &info->dlpi_phdr[i];
        if (ph->p_type == PT_GNU_RELRO) {
            rl = (info->dlpi_addr + ph->p_vaddr) & ~page_mask;
            rh = (info->dlpi_addr + ph->p_vaddr + ph->p_memsz + page_mask) & ~page_mask;
        }
    }
    for (int i = 0; i < info->dlpi_phnum; i++) {
        const ElfW(Phdr) *ph = &info->dlpi_phdr[i];
        if (ph->p_type != PT_LOAD || !(ph->p_flags & PF_W))
            continue;
        uint64_t lo = info->dlpi_addr + ph->p_vaddr;
        uint64_t hi = lo + ph->p_memsz;
        if (rh > rl && rl < hi && rh > lo) {
            if (rl > lo && g_ngsegs2 < 16) {
                glue_add_segment((uintptr_t)lo, (uintptr_t)rl);
            }
            if (rh < hi && g_ngsegs2 < 16) {
                glue_add_segment((uintptr_t)rh, (uintptr_t)hi);
            }
        } else if (g_ngsegs2 < 16) {
            glue_add_segment((uintptr_t)lo, (uintptr_t)hi);
        }
    }
    return 1;
}

static void glue_collect_segments(void)
{
    if (!g_ngsegs2)
        dl_iterate_phdr(glue_phdr_cb, NULL);
}
#endif

static void pristine_capture(void)
{
    if (g_pristine)
        return;
    glue_collect_segments();
    size_t total = 0;
    for (int i = 0; i < g_ngsegs2; i++) {
        obor_dbg("pristine: seg %d vaddr=%p size=%zu", i,
                 (void *)g_gsegs2[i].vaddr, (size_t)g_gsegs2[i].size);
        total += g_gsegs2[i].size;
    }
    g_pristine = (uint8_t *)malloc(total);
    obor_dbg("pristine: %d segs, %zu bytes, buf=%p", g_ngsegs2, total,
             (void *)g_pristine);
    if (!g_pristine)
        return;
    uint8_t *p = g_pristine;
    for (int i = 0; i < g_ngsegs2; i++) {
        obor_dbg("pristine: copying seg %d", i);
        memcpy(p, (void *)g_gsegs2[i].vaddr, g_gsegs2[i].size);
        p += g_gsegs2[i].size;
    }
    obor_dbg("pristine: capture done");
}

static void pristine_restore(void)
{
    if (!g_pristine)
        return;
    glue_regs r;
    glue_save(&r);
    const uint8_t *p = r.pristine;
    for (int i = 0; i < r.nsegments; i++) {
        obor_dbg("pristine: restoring seg %d", i);
        memcpy((void *)r.segments[i].vaddr, p, r.segments[i].size);
        p += r.segments[i].size;
    }
    glue_load(&r);
    obor_dbg("pristine: restore done");
}

static bool select_engine_vtbl(const char *engine, char *err, int err_len)
{
    obor_capture_cadence_reset(&g_capture_cadence);
    g_input_has_origin = false;
    g_vtbl = NULL;
    if (!*engine && *g_selection_error) {
        snprintf(err, (size_t)err_len, "%s", g_selection_error);
        return false;
    }
    for (size_t i = 0; i < sizeof(kEngineDefs) / sizeof(kEngineDefs[0]); i++) {
        if (strcmp(kEngineDefs[i].name, engine) == 0) {
            g_vtbl = &kEngineDefs[i].v;
            break;
        }
    }
    if (!g_vtbl) {
        snprintf(err, (size_t)err_len, "engine %s not linked in", engine);
        return false;
    }
    if (p_abi_version() != OBOR_ABI_VERSION) {
        snprintf(err, (size_t)err_len, "engine ABI %u != glue ABI %u",
                 p_abi_version(), OBOR_ABI_VERSION);
        return false;
    }
    return true;
}

/* full detection cascade; used by retro_load_game AND retro_reset (a
 * Restart must honour a live change of the anybor_engine core option) */
#include "anybor_legacy_api.h"

static void decide_engine(void)
{
    g_content_triage = false;
    g_selection_error[0] = '\0';
    char opt[48];
    get_engine_option(opt, sizeof(opt));

    int n_avail = (int)(sizeof(kProfiles) / sizeof(kProfiles[0]));

    int build = 0;
    const obor_profile_def *explicit_profile = NULL;
    const char *how = "fallback";
    if (strcasecmp(opt, "auto") != 0) {
        /* Preserve saved options using the old v3/v4 display strings. */
        for (int i = 0; i < n_avail; i++) {
            char previous[48];
            snprintf(previous, sizeof(previous), "%.2s %s", kProfiles[i].disp, kProfiles[i].name);
            if (strcmp(opt, kProfiles[i].disp) == 0 ||
                strcmp(opt, kProfiles[i].name) == 0 || strcmp(opt, previous) == 0) {
                build = kProfiles[i].build;
                explicit_profile = &kProfiles[i];
            }
        }
        if (build)
            how = "core option";
    }
    if (!build) {
        const char *system = NULL;
        char value[48], evidence[4608];
        env_cb(RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY, &system);
        if (!obor_content_override(system, g_content_choice, value, evidence, sizeof(evidence))) {
            g_engine[0] = g_logical_engine[0] = 0;
            snprintf(g_selection_error, sizeof(g_selection_error), "Invalid or unreadable AnyBOR.ini engine override.");
            return;
        }
        if (value[0]) {
            for (int i = 0; i < n_avail; ++i) {
                const char *bare = strchr(kProfiles[i].disp, ' ');
                if (!strcasecmp(value, kProfiles[i].name) || !strcasecmp(value, kProfiles[i].disp) ||
                    (bare && !strcasecmp(value, bare + 1))) explicit_profile = &kProfiles[i];
            }
            if (!explicit_profile) {
                g_engine[0] = g_logical_engine[0] = 0;
                snprintf(g_selection_error, sizeof(g_selection_error), "Engine override profile '%s' is unavailable.", value);
                return;
            }
            build = explicit_profile->build;
            how = "external engine override";
            log_cb(RETRO_LOG_INFO, "[OpenBOR] %s -> profile %s\n", evidence, explicit_profile->name);
        }
    }
    obor_engine_identity identity = {};
    if (!build) {
        identity = g_zip_engine_scanned ? g_zip_engine_identity :
            obor_engine_for_content(g_engine_source_path[0] ? g_engine_source_path : g_pak_path, g_raw);
        if (identity.status == OBOR_ENGINE_IDENTIFIED) {
            build = identity.engine->build;
            how = "engine executable SHA-256";
            for (int i = 0; i < n_avail; ++i)
                if (kProfiles[i].build == build &&
                    (identity.engine->variant[0] ?
                     !strcmp(kProfiles[i].variant, identity.engine->variant) :
                     profile_is_revision(&kProfiles[i]))) explicit_profile = &kProfiles[i];
            log_cb(RETRO_LOG_INFO,
                "[OpenBOR] engine executable %s SHA-256 %s -> build %d%s%s%s\n",
                identity.evidence, identity.engine->sha256, build,
                identity.engine->variant[0] ? "-" : "", identity.engine->variant,
                explicit_profile ? " (exact profile available)" : " (using available-profile rules)");
        } else if (identity.status == OBOR_ENGINE_AMBIGUOUS) {
            log_cb(RETRO_LOG_INFO,
                "[OpenBOR] engine executable identification ambiguous: build %d%s%s (%s) versus %d%s%s (%s); using existing detection.\n",
                identity.engine ? identity.engine->build : 0,
                identity.engine && identity.engine->variant[0] ? "-" : "",
                identity.engine ? identity.engine->variant : "", identity.evidence,
                identity.conflict ? identity.conflict->build : 0,
                identity.conflict && identity.conflict->variant[0] ? "-" : "",
                identity.conflict ? identity.conflict->variant : "", identity.conflicting_evidence);
        } else if (identity.status == OBOR_ENGINE_SCAN_INCOMPLETE) {
            log_cb(RETRO_LOG_INFO, "[OpenBOR] engine executable identification incomplete within scan limits; using existing detection.\n");
        }
    }
    int filename_profile = 0;
    int filename_build = build_from_filename(g_pak_path, &filename_profile);
    if (!build) {
        explicit_profile = profile_variant_from_filename(g_pak_path);
        if (explicit_profile) {
            build = explicit_profile->build;
            how = "filename variant tag";
        }
    }
    filename_build_interval interval;
    bool has_interval = build_interval_from_filename(g_pak_path, &interval);
    char interval_text[28] = "";
    if (has_interval) format_build_interval(&interval, interval_text, sizeof(interval_text));
    filename_build_interval triage_interval;
    bool has_triage_interval = filename_triage_bounds(g_pak_path, &triage_interval);
    int triage_profile = 0;
    int legacy_build = 0;
    bool legacy_probed = false;
    if (identity.status == OBOR_ENGINE_IDENTIFIED && !explicit_profile && !g_raw) {
        g_content_triage = true;
        build_from_content(g_pak_path);
        legacy_build = obor_legacy_api_build(g_pak_path);
        legacy_probed = true;
        triage_profile = profile_triage_exact_select(build, legacy_build);
        g_content_triage = false;
    }
    if (!build && has_triage_interval && !g_raw && filename_profile >= 0) {
        g_content_triage = true;
        build_from_content(g_pak_path);
        legacy_build = obor_legacy_api_build(g_pak_path);
        legacy_probed = true;
        triage_profile = profile_triage_select(&triage_interval, legacy_build);
        g_content_triage = false;
        if (triage_profile) {
            build = triage_profile;
            how = "filename content triage";
        }
        if (!g_content_scan_complete)
            log_cb(RETRO_LOG_INFO, "[OpenBOR] content scan incomplete; retaining proved model facts only; script bindings inconclusive.\n");
    }
    if (!build && has_interval) {
        if (filename_profile < 0) {
            g_engine[0] = '\0';
            g_logical_engine[0] = '\0';
    g_engine_error_context = g_engine_log_fresh = false;
            snprintf(g_selection_error, sizeof(g_selection_error),
                     "No available engine lies in or above the filename build interval. Select an engine manually to override it.");
            log_cb(RETRO_LOG_ERROR, "[OpenBOR] %s Bounds: %s\n",
                   g_selection_error, interval_text);
            return;
        }
        build = filename_build;
        how = "filename interval";
    }
    if (!build && !g_raw && !has_interval && !has_triage_interval &&
        filename_missing_exact_profile(g_pak_path, filename_build)) {
        g_content_triage = true;
        build_from_content(g_pak_path);
        legacy_build = obor_legacy_api_build(g_pak_path);
        legacy_probed = true;
        triage_profile = profile_triage_exact_select(filename_build, legacy_build);
        g_content_triage = false;
        if (triage_profile) {
            build = filename_build;
            how = "filename exact triage";
        }
        if (!g_content_scan_complete)
            log_cb(RETRO_LOG_INFO, "[OpenBOR] content scan incomplete; retaining proved model facts only; script bindings inconclusive.\n");
    }
    int declared_anchor = filename_build > 0 && declared_build_has_variants(filename_build)
        ? pick_anchor(filename_build) : 0;
    /* Early aliases retain the legacy API through its original upper bound.
     * A later candidate must still pass the existing preflight priority. */
    bool filename_profile_enabled = declared_anchor != 0 &&
        filename_build <= 4166 && declared_anchor <= 4166;
    int exact_tagged_profile = 0;
    for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); ++i)
        if (kProfiles[i].build == filename_build && profile_is_revision(&kProfiles[i]) && kProfiles[i].tagged &&
            (!kProfiles[i].automatic || kProfiles[i].build != kProfiles[i].engine_build || filename_build == 7123 ||
             filename_build == 7142 || filename_build == 7533 || filename_build == 8023))
        {
            filename_profile_enabled = true;
            exact_tagged_profile = filename_build;
        }
    if (filename_profile_enabled) {
        filename_profile = exact_tagged_profile ? exact_tagged_profile : declared_anchor;
        if (!build) {
            build = filename_build;
            how = "filename tag";
        }
    }
    if (!build && !g_raw) {
        if (!legacy_probed) legacy_build = obor_legacy_api_build(g_pak_path);
        if ((build = legacy_build) != 0) how = "legacy script API";
    }
    if (!build && (build = filename_build) != 0)
        how = "filename tag";
    if (!build && g_raw && (build = build_from_sidecar_dir(g_pak_path)) != 0)
        how = "exe in mod dir";
    if (!build && (build = build_from_sidecar(g_pak_path)) != 0)
        how = "sidecar exe";
    int content_profile = 0;
    if (!build && !g_raw && (obor_native_metadata_features(g_pak_path) & OBOR_PROFILE_LNS_6330)) {
        for (int i = 0; i < n_avail; ++i) {
            if (!(kProfiles[i].features & OBOR_PROFILE_LNS_6330)) continue;
            explicit_profile = &kProfiles[i];
            build = explicit_profile->build;
            how = "bound native content capability";
            break;
        }
    }
    bool refine_legacy = !filename_build && legacy_build && !strcmp(how, "legacy script API");
    if ((!build || refine_legacy) && !g_raw) { /* the content scan reads the pak's file table */
        g_content_triage = true;
        g_content_infer = true;
        int cb = build_from_content(g_pak_path);
        g_content_infer = false;
        g_content_triage = false;
        bool contradiction;
        content_profile = profile_content_select(refine_legacy,
            refine_legacy ? pick_anchor(legacy_build) : OBOR_FALLBACK_BUILD, contradiction);
        if (!g_content_scan_complete)
            log_cb(RETRO_LOG_INFO, "[OpenBOR] content scan incomplete; retaining proved model and dependency facts.\n");
        if (!refine_legacy) {
            if (contradiction) {
                build = OBOR_FALLBACK_BUILD;
            } else if (g_content_range_seen) {
                if (!content_profile)
                    content_profile = OBOR_FALLBACK_BUILD;
                log_cb(RETRO_LOG_INFO, "[OpenBOR] content build bounds %d-%d -> profile %d\n",
                       g_content_lower, g_content_upper, content_profile);
            } else {
                log_cb(RETRO_LOG_INFO, "[OpenBOR] content scan verdict: %d\n", cb);
            }
            if (!contradiction && (content_profile || cb > 0)) {
                build = cb > 0 ? cb : content_profile;
                how = "content scan";
            }
        }
    }
    if (!build)
        build = OBOR_FALLBACK_BUILD;

    int anchor = triage_profile ? triage_profile : content_profile ? content_profile : strcmp(how, "core option") == 0 ? build :
                 ((strcmp(how, "filename tag") == 0 ||
                   strcmp(how, "filename interval") == 0) && filename_profile) ?
                     filename_profile : pick_anchor(build);
    const obor_profile_def *selected = explicit_profile;
    for (int i = 0; i < n_avail; i++)
        if (!selected && kProfiles[i].build == anchor && profile_is_revision(&kProfiles[i]))
            selected = &kProfiles[i];
    if (!selected) {
        g_engine[0] = '\0';
        g_logical_engine[0] = '\0';
    g_engine_error_context = g_engine_log_fresh = false;
        return;
    }
    snprintf(g_logical_engine, sizeof(g_logical_engine), "%s", selected->name);
    snprintf(g_engine, sizeof(g_engine), "%d", selected->engine_build);
    if (strcmp(how, "filename interval") == 0)
        log_cb(RETRO_LOG_INFO,
               "[OpenBOR] pak build bounds %s (filename interval) -> profile %s -> engine %s\n",
               interval_text, g_logical_engine, g_engine);
    else log_cb(RETRO_LOG_INFO,
           "[OpenBOR] pak needs build %d (%s) -> profile %s -> engine %s\n",
           build, how, g_logical_engine, g_engine);

    /* surface the decision in the frontend UI (OSD notification) */
    const char *disp = selected->disp;
    char msg[160];
    if (strcmp(how, "core option") == 0)
        snprintf(msg, sizeof(msg), "AnyBOR %s (core option)", disp);
    else if (strcmp(how, "filename interval") == 0)
        snprintf(msg, sizeof(msg), "AnyBOR %s (auto: build interval %s)", disp, interval_text);
    else
        snprintf(msg, sizeof(msg), "AnyBOR %s (auto: %s, build %d)", disp,
                 how, build);
    unsigned mv = 0;
    if (env_cb(RETRO_ENVIRONMENT_GET_MESSAGE_INTERFACE_VERSION, &mv) &&
        mv >= 1) {
        struct retro_message_ext m;
        memset(&m, 0, sizeof(m));
        m.msg = msg;
        m.duration = 3500;
        m.priority = 1;
        m.level = RETRO_LOG_INFO;
        m.target = RETRO_MESSAGE_TARGET_OSD;
        m.type = RETRO_MESSAGE_TYPE_NOTIFICATION;
        m.progress = -1;
        env_cb(RETRO_ENVIRONMENT_SET_MESSAGE_EXT, &m);
    } else {
        struct retro_message m = { msg, 210 }; /* ~3.5 s at 60 fps */
        env_cb(RETRO_ENVIRONMENT_SET_MESSAGE, &m);
    }
}

/* mkdir -p: the frontend may supply a save directory that has yet to be created. */
static void mkdir_p(const char *path)
{
    char tmp[4096];
    strncpy(tmp, path, sizeof(tmp) - 1);
    tmp[sizeof(tmp) - 1] = '\0';
    for (char *c = tmp + 1; *c; c++) {
        if (*c != '/' && *c != '\\')
            continue;
        char sep = *c;
        *c = '\0';
        obor_mkdir(tmp, 0755);
        *c = sep;
    }
    obor_mkdir(tmp, 0755);
}

#include "anybor_zip.h"
#include "anybor_pak_validate.h"
#include "anybor_packed_prepare.h"

static void abspath(const char *in, char *out, size_t out_len)
{
    char tmp[4096]; /* realpath demands PATH_MAX; callers' buffers vary */
#if defined(_WIN32)
    if (obor_win_absolute(in, tmp, sizeof(tmp)))
        in = tmp;
#else
    if (realpath(in, tmp))
        in = tmp;
#endif
    strncpy(out, in, out_len - 1);
    out[out_len - 1] = '\0';
}

/* Reserve the snapshot address without replacing any existing mapping.
 * Ownership lasts exactly as long as this loaded module. */
#if defined(_WIN32)
#include <windows.h>
#else
#include <sys/mman.h>
#include <errno.h>
#endif
#if defined(__APPLE__)
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <libproc.h>
#include <unistd.h>
#endif

#if defined(__APPLE__)
static int obor_arena_range_is_free(unsigned long long base, size_t size)
{
    mach_vm_address_t cursor = (mach_vm_address_t)base;
    mach_vm_address_t limit = (mach_vm_address_t)(base + size);
    while (cursor < limit) {
        mach_vm_size_t region = 0;
        vm_region_basic_info_data_64_t info;
        mach_port_t object = MACH_PORT_NULL;
        mach_msg_type_number_t count = VM_REGION_BASIC_INFO_COUNT_64;
        kern_return_t kr = mach_vm_region(mach_task_self(), &cursor, &region,
                                          VM_REGION_BASIC_INFO_64,
                                          (vm_region_info_t)&info, &count,
                                          &object);
        if (kr == KERN_INVALID_ADDRESS)
            return 1;               /* nothing mapped from base upwards */
        if (kr != KERN_SUCCESS)
            return 0;
        if (cursor <= base)
            return 0;               /* a region covers the base itself */
        cursor += region;
    }
    return 1;
}
#endif /* __APPLE__ */

__attribute__((constructor)) static void obor_arena_claim(void)
{
#if defined(_WIN32)
    void *p = VirtualAlloc((void *)OBOR_ARENA_BASE_VA, OBOR_ARENA_MAX_SZ,
                           MEM_RESERVE | MEM_WRITE_WATCH, PAGE_READWRITE);
    g_arena_owned = p == (void *)OBOR_ARENA_BASE_VA;
    if (p && !g_arena_owned)
        VirtualFree(p, 0, MEM_RELEASE);
#elif defined(__APPLE__)
    {
        const bool debug = getenv("OBOR_DEBUG") != NULL;
        static const unsigned long long candidates[] = {
            (unsigned long long)OBOR_ARENA_BASE_VA, 0x400000000000ULL,
        };
        size_t index;
        for (index = 0; index < sizeof(candidates) / sizeof(candidates[0]);
             index++) {
            mach_vm_address_t where = (mach_vm_address_t)candidates[index];
            kern_return_t kr = mach_vm_allocate(mach_task_self(), &where,
                                                OBOR_ARENA_MAX_SZ,
                                                VM_FLAGS_FIXED);
            if (debug) fprintf(stderr, "[OpenBOR] arena mach 0x%llx -> 0x%llx (kr=%d)\n",
                    candidates[index], (unsigned long long)where, (int)kr);
            if (debug && kr != KERN_SUCCESS) {
                char holder[1024] = "";
                proc_regionfilename(getpid(),
                                    (uint64_t)candidates[index],
                                    holder, sizeof(holder));
                fprintf(stderr, "[OpenBOR] arena held at 0x%llx by '%s'\n",
                        candidates[index], holder);
            }
            if (kr != KERN_SUCCESS &&
                obor_arena_range_is_free(candidates[index],
                                         OBOR_ARENA_MAX_SZ)) {
                /* The fixed reserve refused a range nothing else maps, so
                 * MAP_FIXED cannot displace anything: the same contract the
                 * Linux path gets from MAP_FIXED_NOREPLACE. */
                void *forced = mmap((void *)candidates[index],
                                    OBOR_ARENA_MAX_SZ, PROT_NONE,
                                    MAP_PRIVATE | MAP_ANONYMOUS |
                                        MAP_NORESERVE | MAP_FIXED, -1, 0);
                if (debug) fprintf(stderr, "[OpenBOR] arena mmap 0x%llx -> %p\n",
                        candidates[index], forced);
                if (forced == (void *)candidates[index]) {
                    kr = KERN_SUCCESS;
                    where = (mach_vm_address_t)candidates[index];
                }
            }
            if (kr == KERN_SUCCESS &&
                where == (mach_vm_address_t)candidates[index]) {
                g_arena_owned = candidates[index] ==
                                (unsigned long long)OBOR_ARENA_BASE_VA;
                if (!g_arena_owned)
                    munmap((void *)candidates[index], OBOR_ARENA_MAX_SZ);
                break;
            }
        }
        if (debug && index == sizeof(candidates) / sizeof(candidates[0]))
            fprintf(stderr, "[OpenBOR] arena refused at every candidate\n");
    }
#else
#ifndef MAP_FIXED_NOREPLACE
#define MAP_FIXED_NOREPLACE 0x100000
#endif
    void *p = mmap((void *)OBOR_ARENA_BASE_VA, OBOR_ARENA_MAX_SZ, PROT_NONE,
                   MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE |
                       MAP_FIXED_NOREPLACE, -1, 0);
    g_arena_owned = p == (void *)OBOR_ARENA_BASE_VA;
    /* Old kernels can ignore NOREPLACE and return a different address. */
    if (p != MAP_FAILED && !g_arena_owned)
        munmap(p, OBOR_ARENA_MAX_SZ);
#endif
    if (!g_arena_owned)
        fprintf(stderr, "[OpenBOR] snapshot address unavailable; content loading disabled.\n");
}

__attribute__((destructor)) static void glue_module_unload(void)
{
    content_stop();
    free(g_pristine);
    g_pristine = NULL;
    if (g_arena_owned) {
#if defined(_WIN32)
        VirtualFree((void *)OBOR_ARENA_BASE_VA, 0, MEM_RELEASE);
#else
        munmap((void *)OBOR_ARENA_BASE_VA, OBOR_ARENA_MAX_SZ);
#endif
        g_arena_owned = false;
    }
}

/* A reference to this documentation keeps it in stripped core binaries. */
static void write_license_documentation(void)
{
    char path[1200];
    int n = snprintf(path, sizeof(path), "%s/anybor-license-notices.txt", g_save_dir);
    if (!g_save_dir[0] || n < 0 || (size_t)n >= sizeof(path))
        return;
    FILE *fp = obor_fopen(path, "wb");
    if (!fp)
        return;
    size_t size = sizeof(obor_license_text) - 1;
    bool ok = fwrite(obor_license_text, 1, size, fp) == size;
    if (fclose(fp) != 0)
        ok = false;
    if (!ok && log_cb)
        log_cb(RETRO_LOG_WARN, "[OpenBOR] Could not finish writing the license documentation.\n");
}

static bool finish_load_game(void);

static bool load_game(const struct retro_game_info *info, bool retry, bool prepare_only = false)
{
    const obor_prepare_range total_progress = {0, 1000};
    unsigned packed_start = 0;
    if (g_fault_quarantined) {
        error_reason("The previous engine still has live workers. Restart the frontend.");
        return false;
    }
    if (!info || !info->path) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] no content path (need_fullpath)\n");
        error_reason("No content path was provided by the frontend.");
        return false;
    }

    /* some frontend paths (netplay content reinit) load again without an
     * unload in between — shut the running engine down first */
    if (g_storage.root[0]) refresh_options();
    if (g_booted || g_vtbl || g_storage.root[0])
        content_stop();

    /* The engine chdir()s into the save root (old engine eras hardcode
     * relative Logs/Saves); relative paths captured here would die there. */
    abspath(info->path, g_pak_path, sizeof(g_pak_path));

    enum retro_pixel_format fmt = RETRO_PIXEL_FORMAT_XRGB8888;
    if (!prepare_only && !env_cb(RETRO_ENVIRONMENT_SET_PIXEL_FORMAT, &fmt)) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] XRGB8888 not supported\n");
        error_reason("The frontend does not support XRGB8888 video.");
        return false;
    }

    /* absolute: the engine chdir()s away and retro_reset re-reads the
     * decision long after that */
    g_save_dir[0] = '\0';
    const char *dir = NULL;
    if (env_cb(RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY, &dir) && dir && dir[0]) {
        mkdir_p(dir); /* netplay hands out a not-yet-created subdir */
        abspath(dir, g_save_dir, sizeof(g_save_dir));
    }
    if (!g_save_dir[0]) {
        log_cb(RETRO_LOG_ERROR,
               "[OpenBOR] frontend did not provide a writable save directory\n");
        error_reason("The frontend did not provide a writable save directory.");
        return false;
    }

    char routed[4096];
    g_content_choice.presentation = {};
    if (!obor_content_loose(g_pak_path, routed, sizeof(routed), g_content_choice)) {
        error_reason("Invalid, ambiguous or unavailable .anybor content descriptor.");
        return false;
    }
    snprintf(g_pak_path, sizeof(g_pak_path), "%s", routed);

    if (!obor_storage_game_directory(g_save_dir, g_pak_path, g_game_dir, sizeof(g_game_dir))) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] Could not resolve a safe game save directory.\n");
        error_reason("Could not resolve a safe game save directory.");
        return false;
    }
    refresh_options();
    if (!obor_storage_begin(g_save_dir, !retry && opt_is_on("anybor_clear_all_caches", true),
                            opt_is_on("anybor_clear_game_cache", true))) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] Could not clear the cache directory.\n");
        error_reason("Could not prepare the game cache directory.");
        return false;
    }

    /* .zip content: exactly ONE game inside (a .pak, or an unpacked mod's
     * data/ tree); extracted once into a persistent cache and the content
     * path rewritten to the extracted file — the rest of the flow is
     * identical to loading it directly. */
    {
        size_t n = strlen(g_pak_path);
        if (n > 4 && strcasecmp(g_pak_path + n - 4, ".zip") == 0) {
            char newpath[4096];
            obor_prepare_stage(total_progress, 0, 400, 0);
            const char *system = NULL;
            env_cb(RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY, &system);
            if (!obor_zip_prepare(g_pak_path, g_save_dir, newpath,
                                  sizeof(newpath), system, &g_zip_engine_identity, &g_content_choice)) {
                error_reason("Could not extract a single OpenBOR game from the ZIP.");
                return false;
            }
            strncpy(g_pak_path, newpath, sizeof(g_pak_path) - 1);
            g_zip_engine_scanned = true;
            packed_start = 400;
            obor_dbg("load_game: zip -> %s", g_pak_path);
        }
    }

    /* Unpacked mod: accept only the canonical …/<mod>/data/models.txt.
     * Treating an arbitrary .txt as a mod used to chdir two directories up
     * and could make the engine read/write an unrelated tree. */
    g_raw = false;
    {
        size_t n = strlen(g_pak_path);
        if (n > 4 && strcasecmp(g_pak_path + n - 4, ".txt") == 0) {
            char root[4096];
            strncpy(root, g_pak_path, sizeof(root) - 1);
            root[sizeof(root) - 1] = '\0';
            char *s1 = strrchr(root, '/');
            char *s2 = strrchr(root, '\\');
            char *s = (s2 && (!s1 || s2 > s1)) ? s2 : s1;
            if (!s || strcasecmp(s + 1, "models.txt") != 0) {
                log_cb(RETRO_LOG_ERROR,
                       "[OpenBOR] unpacked content must be data/models.txt\n");
                error_reason("Unpacked content must be data/models.txt.");
                return false;
            }
            *s = '\0';
            s1 = strrchr(root, '/');
            s2 = strrchr(root, '\\');
            s = (s2 && (!s1 || s2 > s1)) ? s2 : s1;
            if (!s || strcasecmp(s + 1, "data") != 0) {
                log_cb(RETRO_LOG_ERROR,
                       "[OpenBOR] unpacked content must be data/models.txt\n");
                error_reason("Unpacked content must be data/models.txt.");
                return false;
            }
            *s = '\0';
            strncpy(g_pak_path, root, sizeof(g_pak_path) - 1);
            g_raw = true;
            log_cb(RETRO_LOG_INFO, "[OpenBOR] unpacked mod root: %s\n",
                   g_pak_path);
        }
    }
    snprintf(g_engine_source_path, sizeof(g_engine_source_path), "%s", g_pak_path);
    if (!g_raw) {
        size_t n = strlen(g_pak_path);
        if (n <= 4 || (strcasecmp(g_pak_path + n - 4, ".pak") != 0 &&
                       strcasecmp(g_pak_path + n - 4, ".spk") != 0)) {
            log_cb(RETRO_LOG_ERROR, "[OpenBOR] unsupported content path\n");
            error_reason("Unsupported content path; expected PAK, SPK, ZIP, ANYBOR or data/models.txt.");
            return false;
        }
        char prepared[4096];
        snprintf(prepared, sizeof(prepared), "%s", g_pak_path);
        const char *system = NULL;
        env_cb(RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY, &system);
        obor_prepare_stage(total_progress, packed_start, 950, 0);
        if (!g_zip_engine_scanned &&
            !obor_packed_prepare(g_pak_path, g_save_dir, system, prepared, sizeof(prepared), g_content_choice.transform, &g_content_choice.function)) {
            error_reason("Could not read or prepare the packed content.");
            return false;
        }
        snprintf(g_pak_path, sizeof(g_pak_path), "%s", prepared);
        const char *error = obor_pak_validate(g_pak_path);
        if (error) {
            log_cb(RETRO_LOG_ERROR, "[OpenBOR] %s: %s\n", error, g_pak_path);
            error_reason(error);
            /* Load failures remain actionable even on targets that suppress
             * routine engine-selection notifications. No engine has booted. */
            unsigned version = 0;
            if (env_cb(RETRO_ENVIRONMENT_GET_MESSAGE_INTERFACE_VERSION, &version) && version >= 1) {
                struct retro_message_ext message = {};
                message.msg = error;
                message.duration = 10000;
                message.priority = 3;
                message.level = RETRO_LOG_ERROR;
                message.target = RETRO_MESSAGE_TARGET_OSD;
                message.type = RETRO_MESSAGE_TYPE_NOTIFICATION;
                message.progress = -1;
                env_cb(RETRO_ENVIRONMENT_SET_MESSAGE_EXT, &message);
            } else {
                struct retro_message message = { error, 600 };
                env_cb(RETRO_ENVIRONMENT_SET_MESSAGE, &message);
            }
            return false;
        }
    }

    obor_prepare_stage(total_progress, 950, 990, 0);
    /* opt-in diagnostics (env OBOR_DEBUG or obor_debug.enable by the pak) */
    obor_dbg_set_dir(g_pak_path);
    obor_dbg_install();
    obor_dbg("load_game: pak=%s", g_pak_path);

    refresh_options();
    if (prepare_only) loading_image(g_pak_path, true, g_raw);
    decide_engine();
    obor_dbg("load_game: engine %s (save_dir=%s)", g_engine, g_save_dir);

    if (!retry && opt_is_on("anybor_clear_local_data", false) &&
        !obor_storage_remove(g_game_dir)) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] Could not clear current game saved data.\n");
        error_reason("Could not clear current game saved data.");
        return false;
    }
    mkdir_p(g_game_dir);
    if (!obor_storage_directory(g_game_dir)) {
        error_reason("Could not create the game save directory.");
        return false;
    }

    char err[256] = "";
    if (!select_engine_vtbl(g_engine, err, sizeof(err))) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] engine selection failed: %s\n", err);
        error_reason(err);
        return false;
    }

    return prepare_only || finish_load_game();
}

static bool finish_load_game(void)
{
    if (!boot_engine()) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] engine boot failed\n");
        obor_dbg("load_game: boot FAILED");
        if (!engine_log_error(g_error_reason, sizeof(g_error_reason))) {
            char reason[160];
            snprintf(reason, sizeof(reason), "Engine %s failed to start this game.", g_engine);
            error_reason(reason);
        }
        return false;
    }

    if (!g_av_announced) {
        const uint32_t *pixels;
        int32_t width, height, pitch;
        p_get_video(&pixels, &width, &height, &pitch);
        if (pixels && width > 0 && height > 0)
            video_geometry(width, height, false);
    }

    /* per-game button labels for the frontend's Port Controls menu,
     * parsed from the pak's playable characters (anybor_padmap.h).
     * Unpacked mods keep the generic labels for now. */
    if (!g_raw)
        obor_padmap_apply(env_cb, g_pak_path, &g_content_choice.controls);

    write_license_documentation();
    obor_dbg("load_game: booted OK (%dx%d)", g_width, g_height);
    g_booted = true;

    macro_reset_all();
    gamelog_close();
    g_map_sent = 0;
    memmap_maybe_send();
    g_rumble_have =
        env_cb(RETRO_ENVIRONMENT_GET_RUMBLE_INTERFACE, &g_rumble_if) &&
        g_rumble_if.set_rumble_state;
    return true;
}

/* Preparation runs on a disposable stack, with no live engine. Boot occurs
 * back on the frontend stack: engine libco must retain that caller context. */
static void loading_switch(void)
{
#if defined(_WIN32)
    NT_TIB *tib = (NT_TIB *)NtCurrentTeb();
    void *base = tib->StackBase, *limit = tib->StackLimit;
    tib->StackBase = (char *)g_loading_stack + (2u << 20);
    tib->StackLimit = g_loading_stack;
    obor_prepare_co_switch(g_loading_context);
    tib->StackBase = base;
    tib->StackLimit = limit;
#else
    obor_prepare_co_switch(g_loading_context);
#endif
}

static int loading_checkpoint(void)
{
    if (g_loading_cancel) return 0;
    uint64_t now = obor_detection_now();
    if (now == UINT64_MAX || now < g_loading_yield || now - g_loading_yield >= 32) {
        obor_prepare_co_switch(g_loading_frontend);
        g_loading_yield = obor_detection_now();
    }
    return !g_loading_cancel;
}

static void loading_entry(void)
{
    struct retro_game_info info = {};
    info.path = g_error_path;
    g_loading_ok = !g_loading_cancel && load_game(&info, g_loading_retry, true);
    g_loading_done = true;
    for (;;) obor_prepare_co_switch(g_loading_frontend);
}

static void loading_dispose(void)
{
    if (!g_loading_context) return;
    g_loading_cancel = true;
    /* Resume through normal helper cleanup instead of abandoning open FILEs,
     * allocated transform buffers or a partial cache publication. */
    while (!g_loading_done) loading_switch();
    obor_prepare_progress = NULL;
    free(g_loading_stack);
    g_loading_stack = g_loading_context = g_loading_frontend = NULL;
    g_loading = false;
}

static bool loading_finish(void)
{
    bool ok = g_loading_ok;
    loading_dispose();
    if (ok && finish_load_game()) return true;
    error_screen(NULL);
    return false;
}

/* RetroArch reserves rewind before its first run. Advertise the generic PACK
 * growth allowance and all possible active-engine sections before preparation;
 * snapshots themselves remain unavailable until boot (MUST_INITIALIZE).
 * Archive sizes and saved peaks are allocation hints, never engine selectors. */
static uint32_t loading_capacity(const char *path)
{
    /* The frontend freezes its rewind allocation before engine boot. Keep
     * the complete-block transport's contract consistent with
     * the engine writer from that first query, including loading screens. */
    if (obor_state_coded_enabled())
        return obor_block_state_requested_capacity(getenv("OBOR_TEST_CODED_CAPACITY_MIB"));
    uint64_t footprint = 0, peak = 0, full = 0, inactive = 0, largest = 0;
    FILE *fp = obor_fopen(path, "rb");
    if (fp) {
        if (!fseek(fp, 0, SEEK_END)) {
            long size = ftell(fp);
            if (size > 0) footprint = (uint64_t)size;
            unsigned char tail[4];
            if (size >= 12 && !fseek(fp, -4, SEEK_END) && fread(tail, 1, 4, fp) == 4) {
                uint64_t directory = obor_pak_u32(tail);
                if (directory > 8 && directory < (uint64_t)size - 4)
                    footprint = directory - 8;
            }
        }
        fclose(fp);
    }
    size_t length = strlen(path);
    if (length > 4 && !strcasecmp(path + length - 4, ".zip")) {
        obor_zip_reader_scope reader(path);
        if (reader.opened) {
            uint64_t total = 0;
            unsigned count = (unsigned)mz_zip_reader_get_num_files(&reader.archive);
            if (count <= OBOR_ZIP_MAX_ENTRIES) {
                for (unsigned i = 0; i < count; ++i) {
                    mz_zip_archive_file_stat item;
                    if (!mz_zip_reader_file_stat(&reader.archive, i, &item) ||
                        item.m_uncomp_size > OBOR_ZIP_MAX_TOTAL - total) { total = 0; break; }
                    total += item.m_uncomp_size;
                }
                if (total) footprint = total;
            }
        }
    }
    if (footprint > OBOR_ARENA_MAX_SZ) footprint = OBOR_ARENA_MAX_SZ;
    const char *base = path;
    for (const char *p = path; *p; ++p) if (*p == '/' || *p == '\\') base = p + 1;
    for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); ++i) {
        char cache[4096];
        int n = snprintf(cache, sizeof(cache), "%s/%s/Saves/.obor_peak_sparse_v2_%s.txt",
                         g_game_dir, kProfiles[i].name, base);
        if (n < 0 || (size_t)n >= sizeof(cache)) continue;
        FILE *file = obor_fopen(cache, "rt");
        unsigned long long bytes = 0;
        if (file) {
            if (fscanf(file, "%llu", &bytes) == 1 && bytes <= OBOR_ARENA_MAX_SZ && bytes > peak)
                peak = bytes;
            fclose(file);
        }
    }
    glue_collect_segments();
    for (int i = 0; i < g_ngsegs2; ++i) full += g_gsegs2[i].size;
    for (size_t i = 0; i < sizeof(kEngineDefs) / sizeof(kEngineDefs[0]); ++i) {
        uint64_t bytes = (uintptr_t)kEngineDefs[i].bss_end - (uintptr_t)kEngineDefs[i].bss_begin;
        inactive += bytes;
        if (bytes > largest) largest = bytes;
    }
    inactive -= largest;
    uint64_t heap = footprint * 5 / 8;
    uint64_t preload = footprint < (128ULL << 20) ? footprint : (128ULL << 20);
    if (heap < preload) heap = preload;
    /* A small compressed archive is not a bound on decoded resources. Keep
     * the 16 MiB bootstrap minimum plus the engine's 16 MiB cold growth
     * margin before the frontend fixes its allocation. Larger PACK/peak
     * hints already provide this minimum. */
    if (heap < (32ULL << 20)) heap = 32ULL << 20;
    if (heap < peak + peak / 3) heap = peak + peak / 3;
    uint64_t capacity = heap + full + (4ULL << 20) + 16384 + 512;
    capacity = (capacity + (8ULL << 20) - 1) & ~((8ULL << 20) - 1);
    capacity -= inactive;
    capacity = (capacity + (1ULL << 20) - 1) & ~((1ULL << 20) - 1);
    return capacity <= UINT32_MAX ? (uint32_t)capacity : 0;
}

static bool loading_image_size(int width, int height, bool notify)
{
    uint32_t *pixels = obor_loading_create(width, height);
    if (!pixels) return false;
    free(g_loading_pixels);
    g_loading_pixels = pixels;
    g_loading_width = width; g_loading_height = height;
    video_geometry(width, height, notify);
    return true;
}

static bool loading_image(const char *path, bool notify, bool raw)
{
    int width, height;
    if (!(raw ? obor_video_directory_resolution(path, &width, &height) :
                obor_video_resolution(path, &width, &height))) return false;
    if (g_loading_pixels && width == g_loading_width && height == g_loading_height)
        return true;
    return loading_image_size(width, height, notify);
}

static bool loading_begin(const struct retro_game_info *info, bool retry)
{
    if (g_fault_quarantined) {
        error_reason("The previous engine still has live workers. Restart the frontend.");
        return false;
    }
    if (!info || !info->path) { error_reason("No content path was provided by the frontend."); return false; }
    char path[sizeof(g_error_path)];
    abspath(info->path, path, sizeof(path));
    content_stop(retry);
    if (!retry) request_frontend_rotation(OBOR_ROTATION_NONE);
    snprintf(g_error_path, sizeof(g_error_path), "%s", path);
    enum retro_pixel_format format = RETRO_PIXEL_FORMAT_XRGB8888;
    if (!env_cb(RETRO_ENVIRONMENT_SET_PIXEL_FORMAT, &format)) {
        error_reason("The frontend does not support XRGB8888 video.");
        return false;
    }
    if (!g_arena_owned) {
        error_reason("The snapshot address is unavailable. Restart the frontend.");
        return false;
    }
    /* Initial state capacity, loading artwork and saves use the actual PAK or ZIP.
     * Keep g_error_path as the original descriptor for preparation/restart. */
    if (obor_content_suffix(path, ".anybor")) {
        obor_descriptor descriptor = {};
        char target[4096];
        if (!obor_descriptor_read(path, descriptor) ||
            !obor_descriptor_target(path, descriptor.payload, target, sizeof(target))) {
            error_reason("Invalid .anybor descriptor or unavailable payload.");
            return false;
        }
        g_content_choice.presentation = descriptor.presentation;
        snprintf(path, sizeof(path), "%s", target);
    }
    /* Unpacked mods retain their original synchronous setup and namespace;
     * there is no packed-content preparation phase or archive-size hint. */
    size_t n = strlen(path);
    if (n > 4 && !strcasecmp(path + n - 4, ".txt"))
        return load_game(info, retry);
    const char *directory = NULL;
    g_save_dir[0] = '\0';
    if (env_cb(RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY, &directory) && directory && *directory)
        abspath(directory, g_save_dir, sizeof(g_save_dir));
    if (!g_save_dir[0]) { error_reason("The frontend did not provide a writable save directory."); return false; }
    if (!obor_storage_game_directory(g_save_dir, path, g_game_dir, sizeof(g_game_dir))) {
        error_reason("Could not resolve a safe game save directory."); return false;
    }
    refresh_options();
    /* Unknown/protected or outer ZIP content keeps preparation running until
     * its ordinary settings become accessible. Never guess a custom raster. */
    if (!loading_image(path, retry) && n > 4 && !strcasecmp(path + n - 4, ".zip")) {
        /* A duplicate frame has no source before the first real image. ZIP
         * metadata arrives later; start with the negotiated loading raster. */
        unsigned maximum_width = g_max_width, maximum_height = g_max_height;
        if (!loading_image_size(g_source_width, g_source_height, retry)) {
            error_reason("Could not prepare the loading image."); return false;
        }
        if (maximum_width > g_max_width) g_max_width = maximum_width;
        if (maximum_height > g_max_height) g_max_height = maximum_height;
    }
    g_state_capacity = loading_capacity(path);
    if (!g_state_capacity) { error_reason("Could not reserve the initial state capacity."); return false; }
    g_loading_stack = malloc(2u << 20);
    if (!g_loading_stack) { error_reason("Could not allocate the preparation stack."); return false; }
    g_loading_frontend = obor_prepare_co_active();
    g_loading_context = obor_prepare_co_derive(g_loading_stack, 2u << 20, loading_entry);
    if (!g_loading_context) {
        free(g_loading_stack); g_loading_stack = NULL;
        error_reason("Could not initialize content preparation."); return false;
    }
    g_loading = g_loading_first = true;
    g_loading_done = g_loading_ok = g_loading_cancel = false;
    g_loading_retry = retry;
    obor_prepare_reset();
    obor_prepare_progress = loading_checkpoint;
    return true;
}

static void loading_run(void)
{
    if (input_poll_cb) input_poll_cb();
    bool upd = false;
    if (env_cb(RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE, &upd) && upd) refresh_options();
    if (!g_loading_first || !g_loading_pixels) {
        g_loading_yield = obor_detection_now();
        loading_switch();
    }
    g_loading_first = false;
    if (g_loading_done) {
        if (!loading_finish()) {
            present_error_frame();
            return;
        }
        if (!g_loading_pixels) {
            /* Large or unusual settings outside the quick probe's bounds
             * are still valid engine inputs. Its first yielded framebuffer
             * supplies the exact raster before any custom image is shown. */
            const uint32_t *pixels;
            int32_t width, height, pitch;
            p_get_video(&pixels, &width, &height, &pitch);
            if (!loading_image_size(width, height, true)) {
                error_screen("Could not prepare the loading image.");
                present_error_frame();
                return;
            }
        }
    }
    if (g_loading_pixels)
        obor_loading_render(g_loading_pixels, g_loading_width, g_loading_height,
                            g_loading_done ? 1000 : obor_prepare_value());
    present_video(g_loading_pixels, g_loading_width, g_loading_height, g_loading_width);
}

bool retro_load_game(const struct retro_game_info *info)
{
    load_state_options();
    g_error_active = false;
    g_error_reason[0] = '\0';
    g_error_path[0] = '\0';
    if (info && info->path)
        abspath(info->path, g_error_path, sizeof(g_error_path));
    bool ok = loading_begin(info, false);
    if (!ok) {
        /* Without a negotiated pixel format there is no safe frame to send. */
        if (strcmp(g_error_reason, "The frontend does not support XRGB8888 video.") == 0) {
            content_stop();
            return false;
        }
        error_screen(NULL);
        return true;
    }
    return true;
}

static bool obor_load_retry(const struct retro_game_info *info)
{
    g_error_reason[0] = '\0';
    bool ok = loading_begin(info, true);
    if (!ok) error_screen(NULL);
    return ok;
}

bool retro_load_game_special(unsigned type, const struct retro_game_info *info,
                             size_t num)
{
    (void)type;
    (void)info;
    (void)num;
    return false;
}

void retro_unload_game(void)
{
    if (g_storage.root[0]) refresh_options();
    content_stop();
    request_frontend_rotation(OBOR_ROTATION_NONE);
    g_error_active = false;
    g_error_path[0] = '\0';
}

unsigned retro_get_region(void) { return RETRO_REGION_NTSC; }

size_t retro_serialize_size(void)
{
    if (g_loading) return g_state_capacity;
    if (!g_booted)
        return 0;
    if (g_variable_state_size)
    {
        uint32_t size = p_serialize_size();
        if (queue_state_fault()) return 0;
        return size < g_state_capacity ? g_state_capacity : size;
    }
    /* The frontend can keep its first rewind allocation across Reset.
     * A learned heap peak must not silently change that session contract. */
    if (!g_state_capacity)
        g_state_capacity = p_serialize_size();
    if (queue_state_fault()) return 0;
    return g_state_capacity;
}

static constexpr uint32_t kRawStateMagic = 0x3153424fU; /* OBS1 */

static bool present_startup_restore_loading(unsigned progress)
{
    if (!g_av_announced || !video_cb) return true;
    if (!g_loading_pixels &&
        !loading_image_size(g_loading_width ? g_loading_width : g_source_width,
                            g_loading_height ? g_loading_height : g_source_height,
                            false))
        return true;
    obor_loading_render(g_loading_pixels, g_loading_width, g_loading_height, progress);
    return present_video(g_loading_pixels, g_loading_width, g_loading_height,
                         g_loading_width);
}

static bool finish_startup_for_restore(const void *data, size_t size)
{
    /* Stock rewind can retain the zero buffer from a refused startup capture.
     * Only a recognized state header should take the synchronous boot path. */
    uint32_t magic;
    if (!data || size < 2 * sizeof(magic) || size > UINT32_MAX) return false;
    memcpy(&magic, data, sizeof(magic));
    if (magic != kRawStateMagic && magic != OBOR_BLOCK_STATE_MAGIC) return false;

    /* Reserve space for each measured phase. Model counts report completed
     * work and cannot predict how long the remaining models will take. */
    const unsigned preparation_end = 100;
    const unsigned models_end = 950;
    if (g_loading) {
        unsigned shown = obor_prepare_value() * preparation_end / 1000;
        if (!present_startup_restore_loading(shown)) return false;
        /* Resume the existing preparation on its own stack, then boot on
         * this thread. The frontend may release the state as soon as this
         * callback returns, so complete the actual restore in this call. */
        g_loading_yield = obor_detection_now();
        while (!g_loading_done) {
            loading_switch();
            unsigned progress = obor_prepare_value() * preparation_end / 1000;
            if (progress > shown && !g_loading_done) {
                if (!present_startup_restore_loading(progress)) return false;
                shown = progress;
            }
        }
        if (!loading_finish()) return false;
    }
    /* Engine boot returns at its first yield. Finish initial model loading
     * so the ordinary restore runs outside any active preload parser. */
    unsigned shown = 0;
    for (;;) {
        unsigned progress = preparation_end +
            g_startup_model_percent * (models_end - preparation_end) / 100;
        if (progress > shown) {
            if (!present_startup_restore_loading(progress)) return false;
            shown = progress;
        }
        if (p_startup_complete()) break;
        if (!p_run_frame()) return false;
    }
    return shown == models_end || present_startup_restore_loading(models_end);
}

static void profile_state_identity(const char *operation, const void *data, size_t size)
{
    /* Diagnostic correlation only: record the complete block index (including
     * every block's integrity CRC), never payloads or a second rewind history.
     * Disabled for performance acceptance because hashing has its own cost. */
    if (!g_profile.file || g_profile.rows >= 200000 ||
        !getenv("OBOR_PROFILE_STATE_IDENTITIES") || !data || size < 32) return;
    uint32_t header[8];
    memcpy(header, data, sizeof(header));
    if (header[0] != OBOR_BLOCK_STATE_MAGIC || header[1] != 1 ||
        header[2] != OBOR_BLOCK_STATE_BLOCK ||
        header[3] > OBOR_BLOCK_STATE_MAX_RAW / OBOR_BLOCK_STATE_BLOCK ||
        (uint64_t)header[3] * 24 > size - sizeof(header)) return;
    obor_sha256_ctx hash;
    unsigned char digest[32];
    obor_sha256_init(&hash);
    obor_sha256_update(&hash, data, sizeof(header) + (size_t)header[3] * 24);
    obor_sha256_final(&hash, digest);
    char hex[65];
    for (unsigned i = 0; i < sizeof(digest); ++i)
        snprintf(hex + 2 * i, 3, "%02x", digest[i]);
    fprintf(stderr, "[obor-state-id] %s frame=%ld index=%s raw=%u used=%u\n",
            operation, g_frame_no, hex, header[4], header[5]);
    /* A held rewind must observe its target before more states are popped.
     * In particular, redirected Windows stderr can otherwise retain a batch
     * of identities. This diagnostic is disabled in cadence measurements. */
    fflush(stderr);
}

static uint32_t serialize_capture(void *data, size_t size, obor_state_ranges *ranges)
{
    obor_profile_init();
    uint64_t profile_begin = obor_profile_now();
    uint32_t written = g_booted && data && size <= UINT32_MAX ?
                       (ranges ? p_owned_serialize(data, (uint32_t)size, ranges) :
                                 p_serialize(data, (uint32_t)size)) : 0;
    uint64_t profile_core_end = obor_profile_now();
    bool ok = written > 0 && written <= size;
    if (!written && g_booted && queue_state_fault()) ok = false;
    if (!ok && data && size) {
        /* Stock rewind may enqueue this buffer despite the failed callback.
         * Give supported buffers one invalid representation: alternating
         * stale payloads would otherwise produce large deltas during loading.
         * Requests outside the engine's uint32_t API retain header-only
         * invalidation; their full extent cannot be passed to the engine. */
        size_t clear_size = size <= UINT32_MAX ? size : sizeof(uint32_t);
        memset(data, 0, clear_size);
    }
    if (g_profile.file) {
        uint64_t heap = 0;
        uint32_t magic = 0;
        int context = -1;
        env_cb(RETRO_ENVIRONMENT_GET_SAVESTATE_CONTEXT, &context);
        if (ok && written >= 72) {
            memcpy(&magic, data, sizeof(magic));
            if (magic == kRawStateMagic)
                memcpy(&heap, (const uint8_t *)data + 64, sizeof(heap));
        }
        obor_profile_record("serialize", g_frame_no, profile_begin,
                            profile_core_end, size, written, heap, ok, context);
    }
    if (g_trace) {
        fprintf(g_trace, "f=%ld ser ok=%d sz=%zu\n", g_frame_no, (int)ok, size);
        fflush(g_trace);
    }
    if (ok) profile_state_identity("capture", data, written);
    if (ok && !ranges)
        obor_capture_cadence_observe(&g_capture_cadence, (uint64_t)g_frame_no);
    else obor_capture_cadence_reset(&g_capture_cadence);
    return ok ? written : 0;
}

bool retro_serialize(void *data, size_t size)
{
    return serialize_capture(data, size, NULL) != 0;
}

static int32_t rewind_owned_begin(void *first, void *second, uint32_t size, uint32_t flags)
{
    if (!g_booted || flags != OBOR_REWIND_EXCLUSIVE_BUFFERS_AND_MEMORY) return 0;
    int32_t result = p_owned_begin(first, second, size);
    if (!result) queue_state_fault();
    return result;
}

static uint32_t rewind_owned_capture(void *data, uint32_t size, obor_state_ranges *ranges)
{
    if (!ranges) return 0;
    return serialize_capture(data, size, ranges);
}

static int32_t rewind_owned_end(void)
{
    if (!g_booted || !g_vtbl) return 1;
    int32_t result = p_owned_end();
    if (!result) queue_state_fault();
    return result;
}

const obor_rewind_interface *retro_anybor_rewind_interface(uint32_t version, uint32_t size)
{
#if defined(__linux__) && defined(__aarch64__) && !defined(__ANDROID__)
    static const obor_rewind_interface api = {
        rewind_owned_begin, rewind_owned_capture, rewind_owned_end};
    if (version == OBOR_REWIND_INTERFACE_VERSION && size == sizeof(api)) return &api;
#else
    (void)version; (void)size;
#endif
    return NULL;
}

bool retro_unserialize(const void *data, size_t size)
{
    ginput_init();
    obor_capture_cadence_reset(&g_capture_cadence);
    obor_profile_init();
    uint64_t profile_begin = obor_profile_now();
    /* Even a glue-level rejection invalidates caller ownership. A rewind pop
     * modifies a registered buffer before loading it, so the frontend ends the
     * session before the pop; this also covers direct ordinary load callers. */
    if (g_booted && g_vtbl && !p_owned_end()) {
        queue_state_fault();
        return false;
    }
    bool startup_restore = g_loading || (g_booted && !p_startup_complete());
    if (startup_restore && !finish_startup_for_restore(data, size)) return false;
    bool ok;
    {
        /* the snapshot spans this whole module's writable segments — the
         * glue's own registers must survive the bulk restore */
        glue_regs r;
        glue_save(&r);
        /* The current writer's capacity is not a limit on readable states:
         * a Full state can be larger than a Smart session's rewind transport.
         * The engine validates binary identity, layout and every input range
         * before writing live memory, independently of the selected writer. */
        ok = g_booted && size <= UINT32_MAX &&
             p_unserialize(data, (uint32_t)size) == 1;
        if (getenv("OBOR_DEBUG"))
            fprintf(stderr, "[obor] engine unserialize returned ok=%d\n", ok);
        glue_load(&r);
        if (getenv("OBOR_DEBUG"))
            fprintf(stderr, "[obor] glue state restored after unserialize\n");
    }
    if (!ok && g_booted) queue_state_fault();
    if (ok) {
        if (startup_restore && !present_startup_restore_loading(1000)) return false;
        g_last_unser = g_frame_no;
        g_reverse_has_snapshot = true;
        if (g_input_after_load) {
            g_input_origin = g_frame_no;
            g_input_has_origin = true;
            fprintf(stderr, "[obor-input] successful load origin=%ld\n", g_input_origin);
            fflush(stderr);
        }
    }
    obor_profile_record("unserialize", g_frame_no, profile_begin,
                        obor_profile_now(), size, 0, 0, ok, -1);
    if (ok) profile_state_identity("restore", data, size);
    if (getenv("OBOR_DEBUG"))
        fprintf(stderr, "[obor] retro_unserialize returning ok=%d\n", ok);
    if (g_trace) {
        fprintf(g_trace, "f=%ld unser ok=%d sz=%zu\n", g_frame_no, (int)ok, size);
        fflush(g_trace);
    }
    return ok;
}

void *retro_get_memory_data(unsigned id) { (void)id; return NULL; }
size_t retro_get_memory_size(unsigned id) { (void)id; return 0; }
void retro_cheat_reset(void) {}
void retro_cheat_set(unsigned index, bool enabled, const char *code)
{
    (void)index;
    (void)enabled;
    (void)code;
}
