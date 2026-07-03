/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/* AnyBOR glue: the libretro scaffolding of the single-file core.
 *
 * Contains NO engine code. The six engine eras are linked in as partial
 * objects whose only visible symbols are their suffixed obor_* ABI (see
 * obor_engines.h, generated from pin.json). At retro_load_game — and again
 * at retro_reset — the glue detects which OpenBOR build the pak needs
 * (filename tag -> sidecar exe -> content scan -> core option -> fallback),
 * points g_vtbl at that engine and shuttles video/audio/input.
 */
#include <ctype.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if !defined(_WIN32)
#include <unistd.h>
#endif

#include "libretro.h"
#include "obor_abi.h"
#include "obor_notices.h"
#include "obor_crt.h"
#include "obor_state_padding.h"
#include "obor_profile.h"

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
static uint32_t g_state_capacity;
static bool g_variable_state_size;
static int g_width = 320, g_height = 240;
static uint32_t *g_crt_pixels; /* presentation scratch, outside engine states */
static char g_engine[48];           /* engine actually loaded, e.g. "6412" */
static char g_save_dir[1024];
static char g_pak_path[4096];
static bool g_raw; /* content is an unpacked mod dir, not a .pak */

/* frame counter + rewind/trace bookkeeping (used across sections) */
static FILE *g_trace;
static long g_frame_no;
static long g_last_unser = -99;

#define p_abi_version (g_vtbl->abi_version)
#define p_boot (g_vtbl->boot)
#define p_run_frame (g_vtbl->run_frame)
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

/* Parse "[v.3.0_Build_4086]" / "Build 4086" / "[v.2.1933]" out of a filename. */
static int build_from_filename(const char *path)
{
    const char *base = strrchr(path, PATH_SEP);
    base = base ? base + 1 : path;
    const char *p = base;
    while (*p) {
        if ((p[0] == 'B' || p[0] == 'b') && strncasecmp(p, "build", 5) == 0) {
            const char *q = p + 5;
            while (*q == '_' || *q == ' ' || *q == '.' || *q == '-')
                q++;
            if (isdigit((unsigned char)*q)) {
                int v = atoi(q);
                if (v >= 1000 && v <= 99999)
                    return v;
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

/* ---- content-based lower bound: which engine vocabulary does the pak
 * actually USE? Tokens (models.txt commands at line starts, script calls
 * name-followed-by-paren) are matched against obor_markers.h — each marker
 * maps to the engine build that introduced it, tuned so prose
 * never fires. Gives a reliable LOWER bound; only bounds >= 6412 reroute
 * (below that the proven 6412 fallback stays). */
#include "obor_markers.h"

static int marker_cmp(const void *k, const void *m)
{
    return strcmp((const char *)k, ((const obor_marker *)m)->tok);
}

static int marker_lookup(const char *tok)
{
    const obor_marker *m = (const obor_marker *)bsearch(
        tok, kMarkers, sizeof(kMarkers) / sizeof(kMarkers[0]),
        sizeof(kMarkers[0]), marker_cmp);
    return m ? m->build : 0;
}

static int removed_lookup(const char *tok)
{
    const obor_marker *m = (const obor_marker *)bsearch(
        tok, kRemovedMarkers,
        sizeof(kRemovedMarkers) / sizeof(kRemovedMarkers[0]),
        sizeof(kRemovedMarkers[0]), marker_cmp);
    return m ? m->build : 0;
}

static int g_content_ub; /* min "last build" among removed tokens seen */

static int content_token(int *lb, const char *tok)
{
    int b = marker_lookup(tok);
    if (b > *lb) {
        *lb = b;
        if (getenv("OBOR_CONTENT_DEBUG"))
            fprintf(stderr, "[content] lb -> %d from '%s'\n", b, tok);
    }
    int r = removed_lookup(tok);
    if (r && (!g_content_ub || r < g_content_ub)) {
        g_content_ub = r;
        if (getenv("OBOR_CONTENT_DEBUG"))
            fprintf(stderr, "[content] ub -> %d from '%s' (removed)\n", r, tok);
    }
    return b;
}

/* scan one text buffer; is_script selects call-site vs line-start rules */
static void content_scan_buf(int *lb, char *data, size_t n, int is_script)
{
    char tok[32];
    if (is_script) {
        /* strip // and C comments in place */
        size_t w = 0;
        for (size_t i = 0; i < n;) {
            if (data[i] == '/' && i + 1 < n && data[i + 1] == '/') {
                while (i < n && data[i] != '\n')
                    i++;
            } else if (data[i] == '/' && i + 1 < n && data[i + 1] == '*') {
                i += 2;
                while (i + 1 < n && !(data[i] == '*' && data[i + 1] == '/'))
                    i++;
                i = i + 2 < n ? i + 2 : n;
            } else {
                data[w++] = data[i++];
            }
        }
        n = w;
        for (size_t i = 0; i < n;) {
            if ((data[i] >= 'a' && data[i] <= 'z')) {
                size_t j = i, k = 0;
                while (j < n && k < 31 &&
                       ((data[j] >= 'a' && data[j] <= 'z') ||
                        (data[j] >= '0' && data[j] <= '9') || data[j] == '_'))
                    tok[k++] = data[j++];
                tok[k] = '\0';
                size_t sp = j;
                while (sp < n && (data[sp] == ' ' || data[sp] == '\t'))
                    sp++;
                if (sp < n && data[sp] == '(' && k >= 3)
                    content_token(lb, tok);
                i = j;
            } else {
                i++;
            }
        }
    } else {
        for (size_t i = 0; i < n;) {
            while (i < n && (data[i] == ' ' || data[i] == '\t' ||
                             data[i] == '\r'))
                i++;
            size_t k = 0;
            while (i < n && data[i] != '\n' && data[i] > ' ' && k < 31) {
                char c = data[i];
                if (c >= 'A' && c <= 'Z')
                    c += 32;
                tok[k++] = c;
                i++;
            }
            tok[k] = '\0';
            if (k >= 3)
                content_token(lb, tok);
            while (i < n && data[i] != '\n')
                i++;
            if (i < n)
                i++;
        }
    }
}

static int build_from_content(const char *pak_path)
{
    FILE *fp = fopen(pak_path, "rb");
    if (!fp)
        return 0;
    unsigned char tail[4];
    if (fseek(fp, -4, SEEK_END) != 0 || fread(tail, 1, 4, fp) != 4) {
        fclose(fp);
        return 0;
    }
    long end = ftell(fp) - 4;
    unsigned int dir = (unsigned)tail[0] | ((unsigned)tail[1] << 8) |
                       ((unsigned)tail[2] << 16) | ((unsigned)tail[3] << 24);
    if (fseek(fp, (long)dir, SEEK_SET) != 0) {
        fclose(fp);
        return 0;
    }
    /* collect .txt/.c/.h entries first (bounded) */
    enum { MAXE = 800 };
    static struct { unsigned start, size; char script; } ent[MAXE];
    int ne = 0;
    long long budget = 16LL << 20;
    while (ftell(fp) < end && ne < MAXE) {
        unsigned char e[12];
        if (fread(e, 1, 12, fp) != 12)
            break;
        unsigned pns = (unsigned)e[0] | ((unsigned)e[1] << 8) |
                       ((unsigned)e[2] << 16) | ((unsigned)e[3] << 24);
        unsigned st = (unsigned)e[4] | ((unsigned)e[5] << 8) |
                      ((unsigned)e[6] << 16) | ((unsigned)e[7] << 24);
        unsigned sz = (unsigned)e[8] | ((unsigned)e[9] << 8) |
                      ((unsigned)e[10] << 16) | ((unsigned)e[11] << 24);
        if (pns < 13 || pns > 1000)
            break;
        char name[1024];
        unsigned nlen = pns - 12;
        if (nlen >= sizeof(name) || fread(name, 1, nlen, fp) != nlen)
            break;
        name[nlen] = '\0';
        size_t L = strlen(name);
        int script = 0, text = 0;
        if (L > 4 && !strcasecmp(name + L - 4, ".txt"))
            text = 1;
        else if (L > 2 && (!strcasecmp(name + L - 2, ".c") ||
                           !strcasecmp(name + L - 2, ".h")))
            script = 1;
        if ((text || script) && sz <= (2u << 20) && budget - sz > 0) {
            ent[ne].start = st;
            ent[ne].size = sz;
            ent[ne].script = (char)script;
            ne++;
            budget -= sz;
        }
    }
    int lb = 0;
    g_content_ub = 0;
    char *buf = (char *)malloc(2u << 20);
    if (buf) {
        for (int i = 0; i < ne; i++) {
            if (fseek(fp, (long)ent[i].start, SEEK_SET) != 0)
                continue;
            size_t got = fread(buf, 1, ent[i].size, fp);
            content_scan_buf(&lb, buf, got, ent[i].script);
        }
    }

    free(buf);
    fclose(fp);
    if (getenv("OBOR_CONTENT_DEBUG"))
        fprintf(stderr, "[content] lb=%d ub=%d\n", lb, g_content_ub);

    /* Removed vocabulary provides an upper bound; newer required vocabulary
     * provides a lower bound. Otherwise leave the decision to the caller. */
    if (g_content_ub && g_content_ub < 6412 && lb <= g_content_ub)
        return g_content_ub;
    if (lb >= 6412)
        return lb;
    return 0;
}

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

/* Choose the anchor engine for a required build: smallest anchor >= build,
 * else the newest. Restricted to engines actually present in the container
 * when we have that list. */
static int pick_anchor(int build, const int *avail, int n_avail)
{
    int best = 0;
    for (int i = 0; i < n_avail; i++) {
        if (avail[i] >= build && (best == 0 || avail[i] < best))
            best = avail[i];
    }
    if (!best) {
        for (int i = 0; i < n_avail; i++)
            if (avail[i] > best)
                best = avail[i];
    }
    return best;
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
static char g_glog_path[1200];

static void gamelog_frame(void)
{
    if (!g_gamelog_on || !g_save_dir[0])
        return;
    if (!g_glog_fp) {
        snprintf(g_glog_path, sizeof(g_glog_path),
                 "%s/AnyBOR/%s/Logs/OpenBorLog.txt", g_save_dir, g_engine);
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
    obor_profile_close();
    g_state_capacity = 0;
    rumble_stop();
    g_pm_nchars = 0;
    if (g_booted && g_vtbl)
        p_shutdown();
    g_booted = false;
    gamelog_close();
    macro_reset_all();
    trace_close();
    obor_dbg_uninstall();
    g_vtbl = NULL;
    g_rumble_have = false;
    g_map_sent = 0;
    g_raw = false;
    g_engine[0] = '\0';
    g_pak_path[0] = '\0';
    free(g_crt_pixels);
    g_crt_pixels = NULL;
    g_width = 320;
    g_height = 240;
}

/* ------------------------------------------------------------ libretro --- */

#define ENGINE_OPT_INFO \
    "Which OpenBOR engine runs the game. Auto detects it from the pak " \
    "(filename tag, sidecar exe, content scan). A manual choice is " \
    "applied on Restart."

void retro_set_environment(retro_environment_t cb)
{
    env_cb = cb;
    size_t n_eng = sizeof(kEngineDefs) / sizeof(kEngineDefs[0]);

    unsigned cov = 0;
    if (!cb(RETRO_ENVIRONMENT_GET_CORE_OPTIONS_VERSION, &cov))
        cov = 0;
    if (cov >= 2) {
        static struct retro_core_option_v2_category cats[] = {
            { "video", "Video", "Video output." },
            { "input", "Input", "Controller behaviour." },
            { "system", "System", "Engine selection." },
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
            { NULL, NULL, NULL, NULL, NULL, NULL, { { NULL, NULL } }, NULL },
        };
        for (struct retro_core_option_v2_definition *def = defs; def->key; ++def) {
            if (strcmp(def->key, "obor_engine"))
                continue;
            for (size_t i = 0; i < n_eng && i + 2 < 128; i++) {
                def->values[i + 1].value = kEngineDefs[i].disp;
                def->values[i + 1].label = NULL;
            }
            def->values[n_eng + 1].value = NULL;
            def->values[n_eng + 1].label = NULL;
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
        for (size_t i = 0; i < n_eng; i++) {
            size_t used = strlen(values);
            if (strlen(kEngineDefs[i].disp) + 2 > sizeof(values) - used)
                break;
            snprintf(values + used, sizeof(values) - used, "|%s", kEngineDefs[i].disp);
        }
    }
    static const struct retro_variable vars[] = {
        { "obor_crt_tv", "Adjust for 4:3 CRT TV; Off|On" },
        { "obor_analog", "Left analog stick as D-pad; On|Off" },
        { "obor_rumble", "Rumble; On|Off" },
        { "obor_macros", "Special move macros (L2/R2/L3/R3); On|Off" },
        { "obor_engine", values },
        { "obor_gamelog", "Forward game log; Off|On" },
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

void retro_deinit(void) { content_stop(); }

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
    boot.save_dir = g_save_dir[0] ? g_save_dir : NULL;
    boot.log_dir = NULL;
    boot.arena_reserved = g_arena_owned ? 1 : 0;
    boot.sample_rate = 44100;
    boot.raw_dir = g_raw ? 1 : 0;
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
    obor_dbg("boot: p_boot -> %d", r);
    return r != 0;
}

void retro_reset(void)
{
    /* True restart: shut the engine down (fds, logs, the whole arena),
     * restore pristine statics and boot again — re-running the version
     * decision so a changed obor_engine core option takes effect NOW. */
    if (!g_booted)
        return;
    g_booted = false;
    obor_dbg("reset: shutdown engine %s", g_engine);
    rumble_stop();
    macro_reset_all();
    gamelog_close();
    g_map_sent = 0;
    p_shutdown();

    decide_engine(); /* may pick a different engine than last time */
    log_cb(RETRO_LOG_INFO, "[OpenBOR] reset: booting engine %s\n", g_engine);

    char err[256] = "";
    if (!select_engine_vtbl(g_engine, err, sizeof(err)) || !boot_engine()) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] reset failed: %s\n", err);
        env_cb(RETRO_ENVIRONMENT_SHUTDOWN, NULL);
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
        env_cb(RETRO_ENVIRONMENT_SHUTDOWN, NULL);
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
                env_cb(RETRO_ENVIRONMENT_SHUTDOWN, NULL);
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
 * The six engines live in this same module as partial-linked objects with
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
    uint32_t state_capacity;
    int width, height;
    uint32_t *crt_pixels;
    char engine[48];
    char saved[1024], pak[4096];
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
    uint8_t *pristine;
    gseg_t segments[16];
    int nsegments;
} glue_regs;

static void glue_save(glue_regs *r)
{
    r->env = env_cb; r->video = video_cb; r->audio = audio_batch_cb;
    r->poll = input_poll_cb; r->input = input_state_cb; r->log = log_cb;
    r->vtbl = g_vtbl; r->booted = g_booted;
    r->state_capacity = g_state_capacity;
    r->width = g_width; r->height = g_height;
    r->crt_pixels = g_crt_pixels;
    r->crt = g_crt_on;
    memcpy(r->engine, g_engine, sizeof(g_engine));
    memcpy(r->saved, g_save_dir, sizeof(g_save_dir));
    memcpy(r->pak, g_pak_path, sizeof(g_pak_path));
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
    r->pristine = g_pristine;
    r->nsegments = g_ngsegs2;
    memcpy(r->segments, g_gsegs2, sizeof(g_gsegs2));
}

static void glue_load(const glue_regs *r)
{
    env_cb = r->env; video_cb = r->video; audio_batch_cb = r->audio;
    input_poll_cb = r->poll; input_state_cb = r->input; log_cb = r->log;
    g_vtbl = r->vtbl; g_booted = r->booted;
    g_state_capacity = r->state_capacity;
    g_width = r->width; g_height = r->height;
    g_crt_pixels = r->crt_pixels;
    g_crt_on = r->crt;
    memcpy(g_engine, r->engine, sizeof(g_engine));
    memcpy(g_save_dir, r->saved, sizeof(g_save_dir));
    memcpy(g_pak_path, r->pak, sizeof(g_pak_path));
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
    g_pristine = r->pristine;
    g_ngsegs2 = r->nsegments;
    memcpy(g_gsegs2, r->segments, sizeof(g_gsegs2));
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
        g_gsegs2[g_ngsegs2].vaddr = start;
        g_gsegs2[g_ngsegs2].size = bytes;
        g_ngsegs2++;
    }
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
                g_gsegs2[g_ngsegs2].vaddr = lo;
                g_gsegs2[g_ngsegs2].size = (size_t)(rl - lo);
                g_ngsegs2++;
            }
            if (rh < hi && g_ngsegs2 < 16) {
                g_gsegs2[g_ngsegs2].vaddr = (uintptr_t)rh;
                g_gsegs2[g_ngsegs2].size = (size_t)(hi - rh);
                g_ngsegs2++;
            }
        } else if (g_ngsegs2 < 16) {
            g_gsegs2[g_ngsegs2].vaddr = lo;
            g_gsegs2[g_ngsegs2].size = (size_t)(hi - lo);
            g_ngsegs2++;
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
    char opt[48];
    get_engine_option(opt, sizeof(opt));

    int avail[16];
    int n_avail = (int)(sizeof(kEngineDefs) / sizeof(kEngineDefs[0]));
    for (int i = 0; i < n_avail; i++)
        avail[i] = kEngineDefs[i].build;

    int build = 0;
    const char *how = "fallback";
    if (strcasecmp(opt, "auto") != 0) {
        /* match the display value ("v3 4086") or the bare build ("4086",
         * used by the test harness via OBOR_ENGINE) */
        for (int i = 0; i < n_avail; i++)
            if (strcmp(opt, kEngineDefs[i].disp) == 0 ||
                strcmp(opt, kEngineDefs[i].name) == 0)
                build = kEngineDefs[i].build;
        if (build)
            how = "core option";
    }
    if (!build && !g_raw && (build = obor_legacy_api_build(g_pak_path)) != 0)
        how = "legacy script API";
    if (!build && (build = build_from_filename(g_pak_path)) != 0)
        how = "filename tag";
    if (!build && g_raw && (build = build_from_sidecar_dir(g_pak_path)) != 0)
        how = "exe in mod dir";
    if (!build && (build = build_from_sidecar(g_pak_path)) != 0)
        how = "sidecar exe";
    if (!build && !g_raw) { /* the content scan reads the pak's file table */
        int cb = build_from_content(g_pak_path);
        log_cb(RETRO_LOG_INFO, "[OpenBOR] content scan verdict: %d\n", cb);
        if (cb > 0) {
            build = cb;
            how = "content scan";
        }
    }
    if (!build)
        build = OBOR_FALLBACK_BUILD;

    int anchor = pick_anchor(build, avail, n_avail);
    snprintf(g_engine, sizeof(g_engine), "%d", anchor);
    log_cb(RETRO_LOG_INFO,
           "[OpenBOR] pak needs build %d (%s) -> engine %s\n", build, how,
           g_engine);

    /* surface the decision in the frontend UI (OSD notification) */
    const char *disp = g_engine;
    for (size_t i = 0; i < sizeof(kEngineDefs) / sizeof(kEngineDefs[0]); i++)
        if (strcmp(kEngineDefs[i].name, g_engine) == 0)
            disp = kEngineDefs[i].disp;
    char msg[160];
    if (strcmp(how, "core option") == 0)
        snprintf(msg, sizeof(msg), "AnyBOR %s (core option)", disp);
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
    char tmp[1200];
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
__attribute__((constructor)) static void obor_arena_claim(void)
{
#if defined(_WIN32)
    void *p = VirtualAlloc((void *)OBOR_ARENA_BASE_VA, OBOR_ARENA_MAX_SZ,
                           MEM_RESERVE | MEM_WRITE_WATCH, PAGE_READWRITE);
    g_arena_owned = p == (void *)OBOR_ARENA_BASE_VA;
    if (p && !g_arena_owned)
        VirtualFree(p, 0, MEM_RELEASE);
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

bool retro_load_game(const struct retro_game_info *info)
{
    if (!info || !info->path) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] no content path (need_fullpath)\n");
        return false;
    }

    /* some frontend paths (netplay content reinit) load again without an
     * unload in between — shut the running engine down first */
    if (g_booted || g_vtbl)
        content_stop();

    /* The engine chdir()s into the save root (old engine eras hardcode
     * relative Logs/Saves); relative paths captured here would die there. */
    abspath(info->path, g_pak_path, sizeof(g_pak_path));

    enum retro_pixel_format fmt = RETRO_PIXEL_FORMAT_XRGB8888;
    if (!env_cb(RETRO_ENVIRONMENT_SET_PIXEL_FORMAT, &fmt)) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] XRGB8888 not supported\n");
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
                                  sizeof(newpath)))
                return false;
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
                return false;
            }
            *s = '\0';
            s1 = strrchr(root, '/');
            s2 = strrchr(root, '\\');
            s = (s2 && (!s1 || s2 > s1)) ? s2 : s1;
            if (!s || strcasecmp(s + 1, "data") != 0) {
                log_cb(RETRO_LOG_ERROR,
                       "[OpenBOR] unpacked content must be data/models.txt\n");
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
            return false;
        }
        const char *error = obor_pak_validate(g_pak_path);
        if (error) {
            log_cb(RETRO_LOG_ERROR, "[OpenBOR] %s: %s\n", error, g_pak_path);
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

    char err[256] = "";
    if (!select_engine_vtbl(g_engine, err, sizeof(err))) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] engine selection failed: %s\n", err);
        return false;
    }

    if (!boot_engine()) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] engine boot failed\n");
        obor_dbg("load_game: boot FAILED");
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
    content_stop();
}

unsigned retro_get_region(void) { return RETRO_REGION_NTSC; }

size_t retro_serialize_size(void)
{
    if (!g_booted)
        return 0;
    if (g_variable_state_size)
        return p_serialize_size();
    /* The frontend can keep its first rewind allocation across Reset.
     * A learned heap peak must not silently change that session contract. */
    if (!g_state_capacity)
        g_state_capacity = p_serialize_size();
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
    /* The frontend copies/diffs the entire advertised capacity, not only
     * our payload. Never feed it uninitialized or stale tail bytes. */
    if (ok && written < size)
        obor_state_clear_padding((uint8_t *)data + written, size - written);
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
        ok = g_booted && p_unserialize(data, (uint32_t)size) == 1;
        if (getenv("OBOR_DEBUG"))
            fprintf(stderr, "[obor] engine unserialize returned ok=%d\n", ok);
        glue_load(&r);
        if (getenv("OBOR_DEBUG"))
            fprintf(stderr, "[obor] glue state restored after unserialize\n");
    }
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
