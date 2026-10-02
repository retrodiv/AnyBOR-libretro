/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/* AnyBOR glue: the libretro scaffolding of the single-file core.
 *
 * Contains NO engine code. The seven engine eras are linked in as partial
 * objects whose only visible symbols are their suffixed obor_* ABI (see
 * obor_engines.h, generated from pin.json). At retro_load_game — and again
 * at retro_reset — the glue detects which OpenBOR build the pak needs
 * (core option -> explicit special profile -> legacy API -> filename tag
 * -> sidecar exe -> content scan -> fallback),
 * points g_vtbl at that engine and shuttles video/audio/input.
 */
#include <ctype.h>
#include <limits.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if !defined(_WIN32)
#include <unistd.h>
#include <dlfcn.h>
#endif

#include "libretro.h"
#include "obor_abi.h"
#include "obor_runtime.h"
#include "obor_engine_resources.h"
#include "obor_notices.h"
#include "obor_crt.h"
#include "obor_error_screen.h"
#include "obor_state_padding.h"
#include "obor_profile.h"
#if defined(__APPLE__)
/* Mach-O image introspection: writable snapshot ranges (pristine capture)
 * and the per-engine state sections of this same image. */
#include "obor_macho.h"
#endif

static void mkdir_p(const char *path);
#include "obor_storage.h"

static bool g_arena_owned;
#include "obor_engines.h"
#include "obor_debug.h"
#include "obor_padmap.h"

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
static bool g_error_active;
static bool g_fault_pending;
static char g_error_reason[512];
static char g_error_engine[48];
static char g_error_path[4096];
static uint32_t g_error_pixels[OBOR_ERROR_WIDTH * OBOR_ERROR_HEIGHT];
static uint32_t g_state_capacity;
static bool g_variable_state_size;
static int g_width = 320, g_height = 240;
static uint32_t *g_crt_pixels; /* presentation scratch, outside engine states */
static char g_engine[48];           /* physical engine actually loaded */
static char g_logical_engine[48];   /* selected logical compatibility profile */
static char g_selection_error[160];
static char g_save_dir[1024];
static char g_game_dir[1600];
static char g_pak_path[4096];
static bool g_raw; /* content is an unpacked mod dir, not a .pak */

/* frame counter + rewind/trace bookkeeping (used across sections) */
static FILE *g_trace;
static long g_frame_no;
static long g_last_unser = -99;
static bool g_fault_quarantined;

#define p_abi_version (g_vtbl->abi_version)
#define p_boot (g_vtbl->boot)
#define p_run_frame (g_vtbl->run_frame)
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

static void decide_engine(void);
static void glue_collect_segments(void);
static void pristine_capture(void);
static void pristine_restore(void);
static bool select_engine_vtbl(const char *engine, char *err, int err_len);
static bool obor_load_retry(const struct retro_game_info *info);
static void stop_faulted_engine(void);

/* ------------------------------------------------- version detection --- */

/* Sparse (commit date -> build) milestones, generated from upstream git
 * history (build number == upstream commit count). Used to translate
 * a sidecar exe's "Compile Date" into a build when the exe's own build
 * string is empty (builds compiled without SVN/git metadata print none). */
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

static int profile_in_range(int lower, int upper, bool automatic_only)
{
    int best = 0;
    for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); ++i) {
        const obor_profile_def *p = &kProfiles[i];
        if ((!automatic_only || p->automatic) && p->build >= lower && p->build <= upper &&
            p->engine_build >= lower && p->engine_build <= upper && p->build > best)
            best = p->build;
    }
    return best;
}

/* An uncovered range uses the first physical engine beyond its upper bound.
 * Explicit-only aliases never masquerade as a newer physical engine. */
static int profile_for_range(int lower, int upper, bool automatic_only)
{
    int best = profile_in_range(lower, upper, automatic_only);
    if (best) return best;
    int next_engine = INT_MAX;
    for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); ++i) {
        const obor_profile_def *p = &kProfiles[i];
        if (p->automatic && p->engine_build > upper && p->engine_build >= lower &&
            p->engine_build < next_engine) {
            best = p->build;
            next_engine = p->engine_build;
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
        if (generation == 4 && lower < 7533) { lower = 7533; lower_known = true; }
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
 * including explicit-only profiles. With no match, its upper endpoint goes
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
                if (!isalnum((unsigned char)*q) && *q != '_' && *q != '-') {
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
                            if (kProfiles[i].build >= lower &&
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
    FILE *fp = fopen(exe_path, "rb");
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
    static const char *months = "JanFebMarAprMayJunJulAugSepOctNovDec";
    for (size_t i = 0; i + 16 < got; i++) {
        if (build == 0 && memcmp(buf + i, "Build ", 6) == 0 &&
            isdigit((unsigned char)buf[i + 6])) {
            int v = atoi(buf + i + 6);
            if (v >= 1000 && v <= 99999)
                build = v;
        }
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
            year = atoi(y);
        }
        if (build && year)
            break;
    }
    free(buf);
    if (build)
        return build;
    if (year >= 2006 && year <= 2099 && month >= 1 && month <= 12)
        return date_to_build(year, month);
    return 0;
}

/* Bounded, syntax-scoped content range inference. */
#include "obor_content_scan.h"

/* Look for an OpenBOR exe next to the pak or one directory up
 * (the common "<Game>/<Game>.exe + <Game>/Paks/<game>.pak" layout). */
#if defined(_WIN32)
#include <windows.h>
#include <direct.h> /* _mkdir */
static int build_from_sidecar_dir(const char *dir)
{
    char pat[1200];
    snprintf(pat, sizeof(pat), "%s\\*.exe", dir);
    WIN32_FIND_DATAA fd;
    HANDLE h = FindFirstFileA(pat, &fd);
    if (h == INVALID_HANDLE_VALUE)
        return 0;
    int build = 0;
    do {
        if (strncasecmp(fd.cFileName, "borpak", 6) == 0)
            continue;
        char full[1400];
        snprintf(full, sizeof(full), "%s\\%s", dir, fd.cFileName);
        build = build_from_exe(full);
    } while (!build && FindNextFileA(h, &fd));
    FindClose(h);
    return build;
}
#else
#include <dirent.h>
#include <sys/stat.h> /* mkdir */
static int build_from_sidecar_dir(const char *dir)
{
    DIR *d = opendir(dir);
    if (!d)
        return 0;
    int build = 0;
    struct dirent *e;
    while (!build && (e = readdir(d))) {
        size_t n = strlen(e->d_name);
        if (n < 5 || strcasecmp(e->d_name + n - 4, ".exe") != 0)
            continue;
        if (strncasecmp(e->d_name, "borpak", 6) == 0)
            continue;
        char full[1400];
        snprintf(full, sizeof(full), "%s/%s", dir, e->d_name);
        build = build_from_exe(full);
    }
    closedir(d);
    return build;
}
#endif

static int build_from_sidecar(const char *pak_path)
{
    char dir[1024];
    strncpy(dir, pak_path, sizeof(dir) - 1);
    dir[sizeof(dir) - 1] = '\0';
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

/* ------------------------------------------------------- core options --- */

static void get_engine_option(char *out, size_t out_len)
{
    struct retro_variable var = { "obor_engine", NULL };
    strncpy(out, "Auto", out_len);
    if (env_cb && env_cb(RETRO_ENVIRONMENT_GET_VARIABLE, &var) && var.value)
        strncpy(out, var.value, out_len - 1);
    out[out_len - 1] = '\0';
}

static bool g_analog = true;  /* left stick doubles as D-pad */
static bool g_rumble_on = true;
static bool g_macros_on = true;
static bool g_gamelog_on = false;
static bool g_crt_on = false;

static bool opt_is_on(const char *key, bool defval)
{
    struct retro_variable var = { key, NULL };
    if (env_cb && env_cb(RETRO_ENVIRONMENT_GET_VARIABLE, &var) && var.value)
        return strcmp(var.value, "On") == 0;
    return defval;
}

/* Re-read the live-effect options (the engine option is only sampled at
 * load/reset by decide_engine). */
static void refresh_options(void)
{
    g_analog = opt_is_on("obor_analog", true);
    g_rumble_on = opt_is_on("obor_rumble", true);
    g_macros_on = opt_is_on("obor_macros", true);
    g_gamelog_on = opt_is_on("obor_gamelog", false);
    g_crt_on = opt_is_on("obor_crt_tv", false);
    g_storage.clear_on_unload = opt_is_on("obor_clear_game_cache", true);
}

/* ---------------------------------------------- frame-loop accessories --- */

/* rumble: engine hit events -> frontend rumble interface */
static struct retro_rumble_interface g_rumble_if;
static bool g_rumble_have;
static long g_rumble_off_at[OBOR_MAX_PLAYERS];

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
            long frames = ms * 60 / 1000;
            g_rumble_off_at[pl] = g_frame_no + (frames > 0 ? frames : 1);
        } else if (g_rumble_off_at[pl] && g_frame_no >= g_rumble_off_at[pl]) {
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
        g_glog_fp = fopen(g_glog_path, "rb");
        if (!g_glog_fp)
            return;
    }
    char line[512];
    int guard = 20; /* lines per frame cap */
    long pos = ftell(g_glog_fp);
    while (guard-- > 0 && fgets(line, sizeof(line), g_glog_fp)) {
        size_t n = strlen(line);
        if (n && line[n - 1] != '\n') {
            /* partial line still being written — rewind and retry later */
            fseek(g_glog_fp, pos, SEEK_SET);
            break;
        }
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
 * sequences (parsed from the pak by obor_padmap.h) */
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

static void content_stop(void)
{
    if (g_fault_pending) {
        g_fault_pending = false;
        stop_faulted_engine();
    }
    obor_profile_close();
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
    g_pak_path[0] = '\0';
    free(g_crt_pixels);
    g_crt_pixels = NULL;
    g_width = 320;
    g_height = 240;
}

static void error_reason(const char *reason)
{
    snprintf(g_error_reason, sizeof(g_error_reason), "%s",
             reason && reason[0] ? reason : "The game could not be loaded.");
}

/* borShutdown writes the reason just after this marker. Ignore the later
 * teardown chatter and any log from a different engine profile. */
static bool engine_log_error(char *out, size_t cap)
{
    if (g_vtbl && p_get_fault_message(out, (uint32_t)cap)) return true;
    if (!g_game_dir[0] || !g_logical_engine[0]) return false;
    char path[2048];
    int n = snprintf(path, sizeof(path), "%s/%s/Logs/OpenBorLog.txt",
                     g_game_dir, g_logical_engine);
    if (n < 0 || (size_t)n >= sizeof(path)) return false;
    FILE *fp = fopen(path, "rb");
    if (!fp) return false;
    char line[512];
    bool marker = false, found = false;
    while (fgets(line, sizeof(line), fp)) {
        if (strstr(line, "An Error Occurred")) {
            marker = true;
            found = false;
            continue;
        }
        if (!marker) continue;
        size_t len = strlen(line);
        while (len && (line[len - 1] == '\n' || line[len - 1] == '\r'))
            line[--len] = '\0';
        if (!len || line[0] == '*') continue;
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
        const char *suffix = "\nWorkers could not be stopped safely. Restart RetroArch.";
        size_t used = strlen(g_error_reason);
        snprintf(g_error_reason + used, sizeof(g_error_reason) - used, "%s", suffix);
    }
    if (deferred) {
        /* State callbacks return outside retro_run. Keep the last submitted
         * pixels alive until the next video callback or explicit unload/reset. */
        g_fault_pending = true;
        g_booted = false;
    } else content_stop();
    snprintf(g_error_engine, sizeof(g_error_engine), "%s", engine);
    g_error_active = true;
    obor_error_render(g_error_pixels, g_error_path, g_error_engine,
                      g_error_reason);
    struct retro_system_av_info av;
    retro_get_system_av_info(&av);
    if (!deferred) env_cb(RETRO_ENVIRONMENT_SET_GEOMETRY, &av.geometry);
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
    video_cb(g_error_pixels, OBOR_ERROR_WIDTH, OBOR_ERROR_HEIGHT,
             OBOR_ERROR_WIDTH * sizeof(uint32_t));
}

/* ------------------------------------------------------------ libretro --- */

#define ENGINE_OPT_INFO \
    "Which OpenBOR engine runs the game. Auto detects it from the pak " \
    "(filename build range or tag, sidecar exe, bounded content scan). A manual choice is " \
    "applied on Restart."

void retro_set_environment(retro_environment_t cb)
{
    env_cb = cb;
    size_t n_profiles = sizeof(kProfiles) / sizeof(kProfiles[0]);

    unsigned cov = 0;
    if (!cb(RETRO_ENVIRONMENT_GET_CORE_OPTIONS_VERSION, &cov))
        cov = 0;
    if (cov >= 2) {
        static struct retro_core_option_v2_category cats[] = {
            { "video", "Video", "Video output." },
            { "input", "Input", "Controller behaviour." },
            { "system", "System", "Engine selection." },
            { "development", "Development", "Tools for exercising content." },
            { NULL, NULL, NULL },
        };
        static struct retro_core_option_v2_definition defs[] = {
            { "obor_crt_tv", "Adjust for 4:3 CRT TV", "Adjust for 4:3 CRT TV",
              "When the game is wider than 364 pixels or taller than 244 "
              "pixels, fit it inside a 640x480 (4:3) frame with sharp bilinear "
              "filtering, preserving its aspect ratio without cropping. "
              "Wider-than-4:3 images have centred black borders above and "
              "below; narrower images have borders on the left and right. "
              "Images within both limits but outside 4:3 +/-10% receive "
              "native-pixel black padding to 4:3, then the size limits "
              "are checked again. "
              "Applies immediately. "
              "The frontend controls the TV's video mode and interlacing.",
              NULL, "video",
              { { "Off", NULL }, { "On", NULL }, { NULL, NULL } }, "Off" },
            { "obor_analog", "Left analog stick as D-pad",
              "Left analog stick as D-pad",
              "Move with the left stick in addition to the D-pad.",
              NULL, "input",
              { { "On", NULL }, { "Off", NULL }, { NULL, NULL } }, "On" },
            { "obor_rumble", "Rumble",
              "Rumble",
              "Forward the game's hit vibration to the controller.",
              NULL, "input",
              { { "On", NULL }, { "Off", NULL }, { NULL, NULL } }, "On" },
            { "obor_macros", "Special move macros (L2/R2/L3/R3)",
              "Special move macros (L2/R2/L3/R3)",
              "Bind the active character's special-move sequences (from the "
              "game's own movelist) to the free shoulder/stick buttons. "
              "Pressing one performs the full input sequence.",
              NULL, "input",
              { { "On", NULL }, { "Off", NULL }, { NULL, NULL } }, "On" },
            { "obor_engine", "Engine build", "Engine build",
              ENGINE_OPT_INFO, NULL, "system",
              { { "Auto", "Auto (detect from pak)" }, { NULL, NULL } },
              "Auto" },
            { "obor_gamelog", "Forward game log",
              "Forward game log",
              "Mirror the game's OpenBorLog into the frontend log "
              "(useful to debug mods).",
              NULL, "system",
              { { "Off", NULL }, { "On", NULL }, { NULL, NULL } }, "Off" },
            { "obor_clear_local_data", "Clear current game saved data on load", NULL,
              "Deletes everything in this game's folder under AnyBOR before it loads, "
              "so the next run behaves like the first on this machine. Includes saved "
              "data from all engine builds. Other games and frontend save states are unaffected.", NULL, "development",
              { { "Off", NULL }, { "On", NULL }, { NULL, NULL } }, "Off" },
            { "obor_clear_game_cache", "Clear current game cache on unload", NULL,
              "Deletes the cache directories used by the current game after unloading it "
              "or closing the core. The next load rebuilds them. Saved game data is unaffected.",
              NULL, "development",
              { { "On", NULL }, { "Off", NULL }, { NULL, NULL } }, "On" },
            { "obor_clear_all_caches", "Clear all game caches on load", NULL,
              "Deletes all contents of AnyBOR-cache before loading a game or generating its "
              "cache. Every load starts with an empty cache while this is On. Saved game "
              "data is unaffected.", NULL, "development",
              { { "On", NULL }, { "Off", NULL }, { NULL, NULL } }, "On" },
            { NULL, NULL, NULL, NULL, NULL, NULL, { { NULL, NULL } }, NULL },
        };
        for (struct retro_core_option_v2_definition *def = defs; def->key; ++def) {
            if (strcmp(def->key, "obor_engine"))
                continue;
            for (size_t i = 0; i < n_profiles && i + 2 < 128; i++) {
                def->values[i + 1].value = kProfiles[i].disp;
                def->values[i + 1].label = NULL;
            }
            def->values[n_profiles + 1].value = NULL;
            def->values[n_profiles + 1].label = NULL;
            break;
        }
        static struct retro_core_options_v2 opts = { cats, defs };
        cb(RETRO_ENVIRONMENT_SET_CORE_OPTIONS_V2, &opts);
        return;
    }

    /* legacy fallback: flat v0 variables */
    static char values[320];
    if (!values[0]) {
        strcpy(values, "Engine build (needs restart); Auto");
        for (size_t i = 0; i < n_profiles; i++) {
            size_t used = strlen(values);
            if (strlen(kProfiles[i].disp) + 2 > sizeof(values) - used)
                break;
            snprintf(values + used, sizeof(values) - used, "|%s", kProfiles[i].disp);
        }
    }
    static const struct retro_variable vars[] = {
        { "obor_crt_tv", "Adjust for 4:3 CRT TV; Off|On" },
        { "obor_analog", "Left analog stick as D-pad; On|Off" },
        { "obor_rumble", "Rumble; On|Off" },
        { "obor_macros", "Special move macros (L2/R2/L3/R3); On|Off" },
        { "obor_engine", values },
        { "obor_gamelog", "Forward game log; Off|On" },
        { "obor_clear_local_data", "Clear current game saved data on load; Off|On" },
        { "obor_clear_game_cache", "Clear current game cache on unload; On|Off" },
        { "obor_clear_all_caches", "Clear all game caches on load; On|Off" },
        { NULL, NULL },
    };
    cb(RETRO_ENVIRONMENT_SET_VARIABLES, (void *)vars);
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

    uint64_t quirks = RETRO_SERIALIZATION_QUIRK_CORE_VARIABLE_SIZE;
    g_variable_state_size = env_cb &&
        env_cb(RETRO_ENVIRONMENT_SET_SERIALIZATION_QUIRKS, &quirks) &&
        (quirks & RETRO_SERIALIZATION_QUIRK_FRONT_VARIABLE_SIZE);
}

void retro_deinit(void) {
    if (g_storage.root[0]) refresh_options();
    content_stop();
}

unsigned retro_api_version(void) { return RETRO_API_VERSION; }

void retro_get_system_info(struct retro_system_info *info)
{
    memset(info, 0, sizeof(*info));
    info->library_name = "AnyBOR";
    info->library_version = OBOR_CORE_VERSION;
    /* .pak, or the models.txt of an unpacked mod (…/<mod>/data/models.txt) */
    info->valid_extensions = "pak|spk|txt|zip";
    info->need_fullpath = true;
    info->block_extract = true;
}

void retro_get_system_av_info(struct retro_system_av_info *info)
{
    memset(info, 0, sizeof(*info));
    info->geometry.base_width = (unsigned)g_width;
    info->geometry.base_height = (unsigned)g_height;
    info->geometry.max_width = 4096;
    info->geometry.max_height = 4096;
    info->geometry.aspect_ratio = (float)g_width / (float)g_height;
    info->timing.fps = 60.0;
    info->timing.sample_rate = 44100.0;
}

void retro_set_controller_port_device(unsigned port, unsigned device)
{
    (void)port;
    (void)device;
}

static bool boot_engine(void)
{
    obor_dbg("boot: pristine capture");
    pristine_capture();  /* first boot: engines still virgin — snapshot */
    obor_dbg("boot: pristine restore");
    pristine_restore();  /* every boot starts from virgin engine statics */
    obor_boot_info boot;
    memset(&boot, 0, sizeof(boot));
    boot.abi_version = OBOR_ABI_VERSION;
    boot.pak_path = g_pak_path;
    boot.save_dir = g_game_dir[0] ? g_game_dir : NULL;
    boot.log_dir = NULL;
    boot.arena_reserved = g_arena_owned ? 1 : 0;
    boot.sample_rate = 44100;
    boot.raw_dir = g_raw ? 1 : 0;
    boot.profile_build = (uint32_t)atoi(g_logical_engine);
    boot.resource_event = engine_resource_event;
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
    int r = p_boot(&boot);
    if (!r && p_get_exit_status() == OBOR_EXIT_MEMORY_FAULT)
        stop_faulted_engine();
    obor_dbg("boot: p_boot -> %d", r);
    return r != 0;
}

void retro_reset(void)
{
    /* True restart: shut the engine down (fds, logs, the whole arena),
     * restore pristine statics and boot again — re-running the version
     * decision so a changed obor_engine core option takes effect NOW. */
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
#if !defined(OBOR_NO_PADMAP)
    if (!g_raw)
        obor_padmap_apply(env_cb, g_pak_path);
#endif
}

/* ---- test-only instrumentation, env-gated, inert in normal use ----
 * OBOR_GLUE_INPUT="F-T:btn,..." synthesizes pad input inside the glue (so a
 * real frontend can be driven to gameplay unattended); btn = up down left
 * right attack jump special start esc. Optional :period:held suffix pulses
 * any button (e.g. 1800-6000:attack:20:4). OBOR_TRACE=/path logs every
 * run/serialize/unserialize call with the frame counter, to compare a real
 * frontend's rewind sequence against the reference harness.
 * (g_trace/g_frame_no/g_last_unser are declared with the top statics.) */

/* OBOR_GLUE_DUMP=prefix: write a PPM of every frame presented within 2
 * frames of an unserialize — captures exactly what a real frontend shows
 * while rewinding. OBOR_GLUE_DUMP_AT=N instead captures exact core frame N;
 * OBOR_GLUE_DUMP_FROM=N with optional OBOR_GLUE_DUMP_TO=M captures a range. */
static void glue_dump_maybe(const uint32_t *px, int w, int h, int pitch_px)
{
    static const char *pfx;
    static long exact_frame = -1;
    static long first_frame = -1;
    static long last_frame = -1;
    static int checked;
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
    static int dumped;
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
    FILE *f = fopen(path, "wb");
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
    static int done;
    if (done)
        return;
    done = 1;
    const char *p = getenv("OBOR_TRACE");
    if (p)
        g_trace = fopen(p, "wt");
}

struct gseg { int from, to; unsigned id; int period, held; };
static gseg g_gsegs[16];
static int g_ngsegs = -1;

static void ginput_init(void)
{
    if (g_ngsegs >= 0)
        return;
    g_ngsegs = 0;
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
    for (int i = 0; i < g_ngsegs; i++) {
        if (g_frame_no >= g_gsegs[i].from && g_frame_no <= g_gsegs[i].to &&
            g_gsegs[i].id == id) {
            if (g_gsegs[i].period)
                return ((g_frame_no - g_gsegs[i].from) % g_gsegs[i].period) < g_gsegs[i].held;
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

void retro_run(void)
{
    if (g_error_active) {
        if (g_fault_pending) {
            char reason[sizeof(g_error_reason)];
            snprintf(reason, sizeof(reason), "%s", g_error_reason);
            g_fault_pending = false;
            stop_faulted_engine();
            error_screen(reason);
        }
        bool upd = false;
        if (env_cb(RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE, &upd) && upd)
            refresh_options();
        if (input_poll_cb) input_poll_cb();
        present_error_frame();
        return;
    }
    if (!g_booted)
        return;

    obor_profile_init();
    uint64_t profile_begin = obor_profile_now();

    bool upd = false;
    if (env_cb(RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE, &upd) && upd)
        refresh_options();

    ginput_init();
    trace_init();
    g_frame_no++;
    if (g_trace) {
        fprintf(g_trace, "f=%ld run\n", g_frame_no);
        fflush(g_trace);
    }

    input_poll_cb();

    /* Rewind replay: each displayed frame is a restored state advanced one
     * engine frame. OpenBOR derives the PLAYER's animation from the pad
     * EVERY tick, so live (neutral) input would snap the character to the
     * idle pose on every step — a frozen sprite sliding backwards. The
     * restored snapshot already carries the pad state of that moment, so
     * while unserializes are streaming in (frontend rewinding), keep hands
     * off and let the historical input drive the replay. */
    bool rewind_replay = (g_last_unser >= g_frame_no - 1);
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
                p_set_button(pl, kPadMap[i].obor, v ? 1 : 0);
            }
        }
    }

    bool debug_restored_frame = getenv("OBOR_DEBUG") &&
                                g_last_unser >= g_frame_no - 1;
    if (debug_restored_frame)
        fprintf(stderr, "[obor] entering first engine frame after restore frame=%ld\n",
                g_frame_no);
    int engine_running = p_run_frame();
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
        return;
    }
    uint64_t profile_core_end = obor_profile_now();

    rumble_frame();
    gamelog_frame();
    if ((g_frame_no & 63) == 0)
        memmap_maybe_send();

    const uint32_t *px = NULL;
    int32_t w = 0, h = 0, pitch = 0;
    p_get_video(&px, &w, &h, &pitch);
    if (px && w > 0 && h > 0) {
        int out_w, out_h;
        if (g_crt_on && obor_crt_output_size(w, h, &out_w, &out_h)) {
            if (!g_crt_pixels)
                g_crt_pixels = (uint32_t *)malloc(
                    OBOR_CRT_WIDTH * OBOR_CRT_HEIGHT * sizeof(uint32_t));
            if (!g_crt_pixels) {
                log_cb(RETRO_LOG_ERROR, "[OpenBOR] CRT framebuffer allocation failed\n");
                error_screen("Could not allocate the CRT framebuffer.");
                present_error_frame();
                return;
            }
            obor_crt_present(g_crt_pixels, px, w, h, pitch);
            px = g_crt_pixels;
            w = out_w;
            h = out_h;
            pitch = out_w;
        }
        if (w != g_width || h != g_height) {
            g_width = w;
            g_height = h;
            struct retro_system_av_info av;
            retro_get_system_av_info(&av);
            env_cb(RETRO_ENVIRONMENT_SET_GEOMETRY, &av.geometry);
        }
        glue_dump_maybe(px, w, h, pitch);
        video_cb(px, (unsigned)w, (unsigned)h, (size_t)pitch * sizeof(uint32_t));
    } else {
        video_cb(NULL, (unsigned)g_width, (unsigned)g_height, 0);
    }

    static int16_t abuf[2048 * 2];
    int32_t frames = p_get_audio(abuf, 2048);
    if (p_get_exit_status() == OBOR_EXIT_MEMORY_FAULT) {
        char reason[sizeof(g_error_reason)];
        p_get_fault_message(reason, sizeof(reason));
        stop_faulted_engine();
        error_screen(reason);
        present_error_frame();
        return;
    }
    if (frames > 0)
        audio_batch_cb(abuf, (size_t)frames);
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
}

/* ---- single-file core machinery -------------------------------------
 * The seven engines live in this same module as partial-linked objects with
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
    bool fault_quarantined;
    bool fault_pending;
    uint32_t state_capacity;
    int width, height;
    uint32_t *crt_pixels;
    char engine[48];
    char logical_engine[48];
    char saved[1024], pak[4096];
    char error_path[sizeof(g_error_path)];
    FILE *trace, *glog;
    obor_profile_state profile;
    gseg input_segments[16];
    int input_segment_count;
    long frame_no, last_unser;
    bool analog, rumble, macros, gamelog, crt, raw, arena_owned;
    retro_rumble_interface rumble_if;
    bool rumble_have;
    long rumble_off_at[OBOR_MAX_PLAYERS];
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
    r->fault_quarantined = g_fault_quarantined;
    r->fault_pending = g_fault_pending;
    r->state_capacity = g_state_capacity;
    r->width = g_width; r->height = g_height;
    r->crt_pixels = g_crt_pixels;
    r->crt = g_crt_on;
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
    g_fault_quarantined = r->fault_quarantined;
    g_fault_pending = r->fault_pending;
    g_state_capacity = r->state_capacity;
    g_width = r->width; g_height = r->height;
    g_crt_pixels = r->crt_pixels;
    g_crt_on = r->crt;
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
        if (memcmp(sec[i].Name, ".idata", 6) == 0)
            continue;
        uintptr_t start = (uintptr_t)mod + sec[i].VirtualAddress;
        size_t bytes = sec[i].Misc.VirtualSize;
        if (memcmp(sec[i].Name, ".bss", 4) == 0) {
            /* MinGW's dllcrt2.o is linked first in .bss. Its first 32 bytes
             * hold the DLL on-exit table and attachment flag, which belong to
             * the current process, not to a game's savestate. Restoring that
             * table from another process leaves an invalid callback pointer
             * and crashes in _execute_onexit_table when RetroArch unloads us.
             * Keep the game/glue statics following the CRT prefix. */
            if (bytes <= 32)
                continue;
            start += 32;
            bytes -= 32;
        }
        glue_add_segment(start, start + bytes);
    }
}
#elif defined(__APPLE__)
#include "obor_macho.h"

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
    if (header)
        obor_macho_writable_segments(header, glue_macho_seg_cb, NULL);
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
 * Restart must honour a live change of the obor_engine core option) */
#include "obor_legacy_api.h"

static void decide_engine(void)
{
    g_selection_error[0] = '\0';
    char opt[48];
    get_engine_option(opt, sizeof(opt));

    int n_avail = (int)(sizeof(kProfiles) / sizeof(kProfiles[0]));

    int build = 0;
    const char *how = "fallback";
    if (strcasecmp(opt, "auto") != 0) {
        /* match the display value ("v3 4086") or the bare build ("4086",
         * used by the test harness via OBOR_ENGINE) */
        for (int i = 0; i < n_avail; i++)
            if (strcmp(opt, kProfiles[i].disp) == 0 ||
                strcmp(opt, kProfiles[i].name) == 0)
                build = kProfiles[i].build;
        if (build)
            how = "core option";
    }
    int filename_profile = 0;
    int filename_build = build_from_filename(g_pak_path, &filename_profile);
    filename_build_interval interval;
    bool has_interval = build_interval_from_filename(g_pak_path, &interval);
    char interval_text[28] = "";
    if (has_interval) format_build_interval(&interval, interval_text, sizeof(interval_text));
    if (!build && has_interval) {
        if (filename_profile < 0) {
            g_engine[0] = '\0';
            g_logical_engine[0] = '\0';
            snprintf(g_selection_error, sizeof(g_selection_error),
                     "No available engine lies in or above the filename build interval. Select an engine manually to override it.");
            log_cb(RETRO_LOG_ERROR, "[OpenBOR] %s Bounds: %s\n",
                   g_selection_error, interval_text);
            return;
        }
        build = filename_build;
        how = "filename interval";
    }
    if (filename_build == 4453 || filename_build == 6412 || filename_build == 7533) {
        filename_profile = filename_build;
        if (!build) {
            build = filename_build;
            how = "filename tag";
        }
    }
    if (!build && !g_raw && (build = obor_legacy_api_build(g_pak_path)) != 0)
        how = "legacy script API";
    if (!build && (build = filename_build) != 0)
        how = "filename tag";
    if (!build && g_raw && (build = build_from_sidecar_dir(g_pak_path)) != 0)
        how = "exe in mod dir";
    if (!build && (build = build_from_sidecar(g_pak_path)) != 0)
        how = "sidecar exe";
    int content_profile = 0;
    if (!build && !g_raw) { /* the content scan reads the pak's file table */
        int cb = build_from_content(g_pak_path);
        if (!g_content_scan_complete)
            log_cb(RETRO_LOG_INFO, "[OpenBOR] content scan budget or input limit reached; using fallback.\n");
        if (g_content_range_seen) {
            content_profile = profile_for_range(g_content_lower, g_content_upper, true);
            log_cb(RETRO_LOG_INFO, "[OpenBOR] content build bounds %d-%d -> profile %d\n",
                   g_content_lower, g_content_upper, content_profile);
            if (!content_profile) {
                g_engine[0] = g_logical_engine[0] = '\0';
                snprintf(g_selection_error, sizeof(g_selection_error),
                         "No available engine lies in or above the content build range. Select an engine manually.");
                return;
            }
        } else log_cb(RETRO_LOG_INFO, "[OpenBOR] content scan verdict: %d\n", cb);
        if (cb > 0) {
            build = cb;
            how = "content scan";
        }
    }
    if (!build)
        build = OBOR_FALLBACK_BUILD;

    int anchor = content_profile ? content_profile : strcmp(how, "core option") == 0 ? build :
                 ((strcmp(how, "filename tag") == 0 ||
                   strcmp(how, "filename interval") == 0) && filename_profile) ?
                     filename_profile : pick_anchor(build);
    const obor_profile_def *selected = NULL;
    for (int i = 0; i < n_avail; i++)
        if (kProfiles[i].build == anchor)
            selected = &kProfiles[i];
    if (!selected) {
        g_engine[0] = '\0';
        g_logical_engine[0] = '\0';
        return;
    }
    snprintf(g_logical_engine, sizeof(g_logical_engine), "%d", anchor);
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
#if defined(OBOR_NO_OSD_MESSAGES)
    (void)msg;
#else
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
#endif
}

/* mkdir -p: frontends hand out save dirs they haven't created yet (e.g.
 * RetroArch's per-session .netplay/ redirection) and the engine's own
 * dirExists only creates one level. */
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
#if defined(_WIN32)
        _mkdir(tmp);
#else
        mkdir(tmp, 0755);
#endif
        *c = sep;
    }
#if defined(_WIN32)
    _mkdir(tmp);
#else
    mkdir(tmp, 0755);
#endif
}

#include "obor_zip.h"
#include "obor_pak_validate.h"
#include "obor_packed_prepare.h"

static void abspath(const char *in, char *out, size_t out_len)
{
    char tmp[4096]; /* realpath demands PATH_MAX; callers' buffers vary */
#if defined(_WIN32)
    if (GetFullPathNameA(in, sizeof(tmp), tmp, NULL))
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
            fprintf(stderr, "[OpenBOR] arena mach 0x%llx -> 0x%llx (kr=%d)\n",
                    candidates[index], (unsigned long long)where, (int)kr);
            if (kr != KERN_SUCCESS) {
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
                fprintf(stderr, "[OpenBOR] arena mmap 0x%llx -> %p\n",
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
        if (index == sizeof(candidates) / sizeof(candidates[0]))
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
    FILE *fp = fopen(path, "wb");
    if (!fp)
        return;
    size_t size = sizeof(obor_license_text) - 1;
    bool ok = fwrite(obor_license_text, 1, size, fp) == size;
    if (fclose(fp) != 0)
        ok = false;
    if (!ok && log_cb)
        log_cb(RETRO_LOG_WARN, "[OpenBOR] Could not finish writing the license documentation.\n");
}

static bool load_game(const struct retro_game_info *info, bool retry)
{
    if (g_fault_quarantined) {
        error_reason("The previous engine still has live workers. Restart RetroArch.");
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
    if (!env_cb(RETRO_ENVIRONMENT_SET_PIXEL_FORMAT, &fmt)) {
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

    if (!obor_storage_game_directory(g_save_dir, g_pak_path, g_game_dir, sizeof(g_game_dir))) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] Could not resolve a safe game save directory.\n");
        error_reason("Could not resolve a safe game save directory.");
        return false;
    }
    refresh_options();
    if (!obor_storage_begin(g_save_dir, !retry && opt_is_on("obor_clear_all_caches", true),
                            opt_is_on("obor_clear_game_cache", true))) {
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
            if (!obor_zip_prepare(g_pak_path, g_save_dir, newpath,
                                  sizeof(newpath))) {
                error_reason("Could not extract a single OpenBOR game from the ZIP.");
                return false;
            }
            strncpy(g_pak_path, newpath, sizeof(g_pak_path) - 1);
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
    if (!g_raw) {
        size_t n = strlen(g_pak_path);
        if (n <= 4 || (strcasecmp(g_pak_path + n - 4, ".pak") != 0 &&
                       strcasecmp(g_pak_path + n - 4, ".spk") != 0)) {
            log_cb(RETRO_LOG_ERROR, "[OpenBOR] unsupported content path\n");
            error_reason("Unsupported content path; expected PAK, SPK, ZIP or data/models.txt.");
            return false;
        }
        char prepared[4096];
        const char *system = NULL;
        env_cb(RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY, &system);
        if (!obor_packed_prepare(g_pak_path, g_save_dir, system, prepared, sizeof(prepared))) {
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

    /* opt-in diagnostics (env OBOR_DEBUG or obor_debug.enable by the pak) */
    obor_dbg_set_dir(g_pak_path);
    obor_dbg_install();
    obor_dbg("load_game: pak=%s", g_pak_path);

    refresh_options();
    decide_engine();
    obor_dbg("load_game: engine %s (save_dir=%s)", g_engine, g_save_dir);

    if (!retry && opt_is_on("obor_clear_local_data", false) &&
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

    /* per-game button labels for the frontend's Port Controls menu,
     * parsed from the pak's playable characters (obor_padmap.h).
     * Unpacked mods keep the generic labels for now. */
#if !defined(OBOR_NO_PADMAP)
    if (!g_raw)
        obor_padmap_apply(env_cb, g_pak_path);
#endif

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

bool retro_load_game(const struct retro_game_info *info)
{
    g_error_active = false;
    g_error_reason[0] = '\0';
    g_error_path[0] = '\0';
    if (info && info->path)
        abspath(info->path, g_error_path, sizeof(g_error_path));
    bool ok = load_game(info, false);
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
    bool ok = load_game(info, true);
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
    g_error_active = false;
    g_error_path[0] = '\0';
}

unsigned retro_get_region(void) { return RETRO_REGION_NTSC; }

size_t retro_serialize_size(void)
{
    if (!g_booted)
        return 0;
    if (g_variable_state_size)
    {
        uint32_t size = p_serialize_size();
        return queue_state_fault() ? 0 : size;
    }
    /* The frontend can keep its first rewind allocation across Reset.
     * A learned heap peak must not silently change that session contract. */
    if (!g_state_capacity)
        g_state_capacity = p_serialize_size();
    if (queue_state_fault()) return 0;
    return g_state_capacity;
}

bool retro_serialize(void *data, size_t size)
{
    obor_profile_init();
    uint64_t profile_begin = obor_profile_now();
    uint32_t written = g_booted && data && size <= UINT32_MAX ?
                       p_serialize(data, (uint32_t)size) : 0;
    uint64_t profile_core_end = obor_profile_now();
    bool ok = written > 0 && written <= size;
    if (!written && g_booted && queue_state_fault()) ok = false;
    if (g_profile.file) {
        uint64_t heap = 0;
        uint32_t magic = 0;
        int context = -1;
        env_cb(RETRO_ENVIRONMENT_GET_SAVESTATE_CONTEXT, &context);
        if (ok && written >= 72) {
            memcpy(&magic, data, sizeof(magic));
            if (magic == 0x3153424fU)
                memcpy(&heap, (const uint8_t *)data + 64, sizeof(heap));
        }
        obor_profile_record("serialize", g_frame_no, profile_begin,
                            profile_core_end, size, written, heap, ok, context);
    }
    if (g_trace) {
        fprintf(g_trace, "f=%ld ser ok=%d sz=%zu\n", g_frame_no, (int)ok, size);
        fflush(g_trace);
    }
    return ok;
}

bool retro_unserialize(const void *data, size_t size)
{
    obor_profile_init();
    uint64_t profile_begin = obor_profile_now();
    bool ok;
    {
        /* the snapshot spans this whole module's writable segments — the
         * glue's own registers must survive the bulk restore */
        glue_regs r;
        glue_save(&r);
        /* A fixed-capacity frontend can pass an older, larger manual state
         * after the core has selected a smaller rewind-safe allocation.
         * Reject it before restoring pointers from an incompatible module
         * image. The frontend retains its current game on failure. */
        ok = g_booted && size <= UINT32_MAX &&
             (g_variable_state_size || !g_state_capacity ||
              size <= g_state_capacity) &&
             p_unserialize(data, (uint32_t)size) == 1;
        if (getenv("OBOR_DEBUG"))
            fprintf(stderr, "[obor] engine unserialize returned ok=%d\n", ok);
        glue_load(&r);
        if (getenv("OBOR_DEBUG"))
            fprintf(stderr, "[obor] glue state restored after unserialize\n");
    }
    if (!ok && g_booted) queue_state_fault();
    if (ok)
        g_last_unser = g_frame_no;
    obor_profile_record("unserialize", g_frame_no, profile_begin,
                        obor_profile_now(), size, 0, 0, ok, -1);
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
