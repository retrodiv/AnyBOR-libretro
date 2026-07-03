/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/*
 * AnyBOR platform layer — port entry + the obor_* ABI.
 *
 * The engine owns its main loop (openborMain never returns until quit), so
 * it runs inside a libco coroutine. The frame contract:
 *   - obor_run_frame() switches into the engine coroutine
 *   - the engine renders; video_copy_screen() submits the frame and yields
 *   - sleeps past a frame's worth also yield (liveness for input polling)
 * Time is fully emulated: obor_clock_us advances 16667 us per yielded frame
 * plus whatever the engine explicitly sleeps — deterministic by construction.
 */
#include "libretroport.h"
#include "obor_abi.h"
#include "packfile.h"
#include "utils.h"
#include "libco/libco.h"

#include <stdio.h>
#include <stdlib.h>
#ifdef _WIN32
#include <direct.h> /* chdir */
#include <windows.h> /* NT_TIB stack-range fixup around co_switch */
#else
#include <unistd.h>
#endif

#define FRAME_US 16667ULL

/* Boot breadcrumbs to stderr, env-gated (the glue's obor_debug.log covers
 * everything OUTSIDE p_boot; these cover the inside). */
static void boot_dbg(const char *msg)
{
    static int on = -1;
    if (on < 0)
        on = getenv("OBOR_DEBUG") != NULL;
    if (on) {
        fprintf(stderr, "[OpenBOR:%d] %s\n", (int)OBOR_ENGINE_BUILD, msg);
        fflush(stderr);
    }
}

/* Engine-global path state (the SDL port defines these in sdlport.c). */
char packfile[MAX_FILENAME_LEN] = { "bor.pak" };
char paksDir[MAX_FILENAME_LEN] = { "Paks" };
char savesDir[MAX_FILENAME_LEN] = { "Saves" };
char logsDir[MAX_FILENAME_LEN] = { "Logs" };
char screenShotsDir[MAX_FILENAME_LEN] = { "ScreenShots" };

/* ------------------------------------------------------------- state --- */

unsigned long long obor_clock_us;
unsigned char obor_pad[4][16];
int obor_snd_bits = 16, obor_snd_rate = 44100, obor_snd_started;

static cothread_t co_frontend;
static cothread_t co_engine;
static int engine_alive;
static int frame_ready;
static unsigned long long us_since_yield; /* sleep accumulator */

static const unsigned int *fb_px;
static int fb_w, fb_h, fb_pitch;

static char boot_pak[MAX_FILENAME_LEN];
static char content_alias_name[MAX_FILENAME_LEN];
static char engine_cwd[4096];
void obor_arena_release(void);
void obor_arena_authorize(int owned);

/* co_frontend points into the current frontend thread's TLS. Its address is
 * process-local even though the engine arena is fixed, so a cross-process
 * snapshot must retain the live session's value instead of restoring the
 * saved one from the module data segment. */
void *obor_frontend_context(void) { return co_frontend; }
void obor_frontend_context_restore(void *context)
{
    co_frontend = (cothread_t)context;
}

static char *obor_getcwd(char *buf, size_t cap)
{
#ifdef _WIN32
    return _getcwd(buf, (int)cap);
#else
    return getcwd(buf, cap);
#endif
}

static int obor_ascii_equal(char a, char b)
{
    if (a >= 'A' && a <= 'Z')
        a = (char)(a - 'A' + 'a');
    if (b >= 'A' && b <= 'Z')
        b = (char)(b - 'A' + 'a');
    return a == b;
}

static int obor_is_self_pak_probe(const char *requested)
{
    static const char prefix[] = "paks/";
    const char *name, *end;
    size_t i;
    if (!requested)
        return 0;
    while (requested[0] == '.' &&
           (requested[1] == '/' || requested[1] == '\\'))
        requested += 2;
    for (i = 0; i < sizeof(prefix) - 1; ++i) {
        char c = requested[i] == '\\' ? '/' : requested[i];
        if (!c || !obor_ascii_equal(c, prefix[i]))
            return 0;
    }
    name = requested + sizeof(prefix) - 1;
    if (!name[0] || strchr(name, '/') || strchr(name, '\\'))
        return 0;
    end = name + strlen(name);
    return end - name > 4 && end[-4] == '.' &&
           obor_ascii_equal(end[-3], 'p') &&
           obor_ascii_equal(end[-2], 'a') &&
           obor_ascii_equal(end[-1], 'k');
}

static int obor_alias_name_equal(const char *left, const char *right)
{
    while (*left && *right) {
        if (!obor_ascii_equal(*left++, *right++))
            return 0;
    }
    return *left == *right;
}

int obor_buffer_content_alias(const char *requested, char **buffer,
                              size_t *size)
{
    FILE *source;
    long length;
    char *result;
    const char *name = requested;
    if (!buffer || !size || !boot_pak[0] ||
        !obor_is_self_pak_probe(requested))
        return 0;
    while (name[0] == '.' && (name[1] == '/' || name[1] == '\\'))
        name += 2;
    name += 5; /* Paks/ */
    /* One loaded core has one active archive. Some games probe several
     * platform-specific names in the same expression; binding every missing
     * name would load the complete archive repeatedly and can leave an
     * unselected probe alive. Keep the first successful alias as the sole
     * name for this content run. */
    if (content_alias_name[0] &&
        !obor_alias_name_equal(content_alias_name, name))
        return 0;
    source = fopen(boot_pak, "rb");
    if (!source)
        return 0;
    if (fseek(source, 0, SEEK_END) != 0 ||
        (length = ftell(source)) < 0 ||
        fseek(source, 0, SEEK_SET) != 0) {
        fclose(source);
        return 0;
    }
    result = (char *)malloc((size_t)length + 1);
    if (!result || fread(result, 1, (size_t)length, source) !=
                       (size_t)length) {
        free(result);
        fclose(source);
        return 0;
    }
    fclose(source);
    result[length] = 0;
    strncpy(content_alias_name, name, sizeof(content_alias_name) - 1);
    content_alias_name[sizeof(content_alias_name) - 1] = 0;
    *buffer = result;
    *size = (size_t)length;
    return 1;
}

/* Windows can only dispatch an SEH exception if RSP lies inside the TIB's
 * [StackLimit, StackBase) — and libco does not maintain the TIB. Without
 * this fixup, ANY exception raised while the engine runs on the arena
 * stack (CRT internals raise recoverable ones even in healthy runs) kills
 * the process before reaching a single handler: real Windows dies
 * silently, wine logs "Exception frame is not in stack limits". Point the
 * TIB at the arena stack for exactly the span the engine executes. */
static void switch_to_engine(void)
{
    char frontend_cwd[4096];
    int restore_cwd = engine_cwd[0] != '\0';
    if (restore_cwd &&
        (!obor_getcwd(frontend_cwd, sizeof(frontend_cwd)) ||
         chdir(engine_cwd) != 0)) {
        engine_alive = 0;
        return;
    }
#if defined(_WIN32)
    NT_TIB *tib = (NT_TIB *)NtCurrentTeb();
    void *save_base = tib->StackBase;
    void *save_limit = tib->StackLimit;
    tib->StackBase = (char *)obor_stack_ptr() + obor_stack_size();
    tib->StackLimit = obor_stack_ptr();
    co_switch(co_engine);
    tib->StackBase = save_base;
    tib->StackLimit = save_limit;
#else
    co_switch(co_engine);
#endif
    if (restore_cwd)
        chdir(frontend_cwd);
}

/* --------------------------------------------------------- port glue --- */

void obor_port_submit_frame(const unsigned int *px, int w, int h, int pitch_px)
{
    fb_px = px;
    fb_w = w;
    fb_h = h;
    fb_pitch = pitch_px;
    frame_ready = 1;
}

static unsigned polls_since_yield;

void obor_yield_frame(void)
{
    us_since_yield = 0;
    polls_since_yield = 0;
    co_switch(co_frontend);
}

void obor_wait_frame(void)
{
    frame_ready = 1;
    obor_yield_frame();
}

void obor_poll_tick(void)
{
    if (++polls_since_yield >= 240) {
        /* also nudge the clock so time-AND-input waits make progress */
        obor_clock_us += FRAME_US;
        frame_ready = 1;
        obor_yield_frame();
    }
}

void obor_port_sleep_us(unsigned long long us)
{
    obor_clock_us += us;
    us_since_yield += us;
    if (us_since_yield >= FRAME_US) {
        /* Engine is pacing without rendering (menu waits, intro delays):
         * re-present the previous frame so the frontend keeps polling
         * input and playing audio. */
        frame_ready = 1;
        obor_yield_frame();
    }
}

void borExit(int reset)
{
    (void)reset;
    engine_alive = 0;
    /* Never return into the engine: park forever yielding to the frontend. */
    for (;;)
        co_switch(co_frontend);
}

static void engine_entry(void)
{
    /* openborMain reads the pak from the `packfile` global (set in
     * obor_boot); its argv only carries debug switches we don't use. */
    static char arg0[] = "openbor";
    static char *argv[2];
    argv[0] = arg0;
    argv[1] = NULL;
    openborMain(1, argv);
    borExit(0);
}

/* ------------------------------------------------------------- ABI ----- */

uint32_t obor_abi_version(void)
{
    return OBOR_ABI_VERSION;
}

int32_t obor_boot(const obor_boot_info *info)
{
    if (!info || info->abi_version != OBOR_ABI_VERSION || !info->arena_reserved)
        return 0;
    obor_arena_authorize(info->arena_reserved);
    char frontend_cwd[4096];
    if (!obor_getcwd(frontend_cwd, sizeof(frontend_cwd)))
        return 0;
    engine_cwd[0] = '\0';
    content_alias_name[0] = '\0';

    if (!obor_state_set_save_dir(info->save_dir) || !obor_state_set_regions(info))
        return 0;

    if (info->raw_dir) {
        /* Unpacked mod: cwd is the mod root only while the engine coroutine
         * runs, so isRawData() can see data/. All mutable output is routed
         * to the frontend save directory, never into the content tree. */
        if (chdir(info->pak_path) != 0)
            goto fail;
        boot_dbg("boot: raw dir mode");
        const char *tail = strrchr(info->pak_path, '/');
#ifdef _WIN32
        const char *bs = strrchr(info->pak_path, '\\');
        if (!tail || (bs && bs > tail))
            tail = bs;
#endif
        snprintf(packfile, MAX_FILENAME_LEN, "%s.pak",
                 tail && tail[1] ? tail + 1 : "rawgame");
        size_t copied = strnlen(packfile, sizeof(boot_pak) - 1);
        memcpy(boot_pak, packfile, copied);
        boot_pak[copied] = 0;
        strcpy(paksDir, ".");
        if (!info->save_dir || !info->save_dir[0])
            goto fail;
        char base[MAX_FILENAME_LEN], root[MAX_FILENAME_LEN];
        int bn = snprintf(base, sizeof(base), "%s/AnyBOR", info->save_dir);
        int rn = snprintf(root, sizeof(root), "%s/AnyBOR/%d",
                          info->save_dir, (int)OBOR_ENGINE_BUILD);
        if (bn < 0 || (size_t)bn >= sizeof(base) ||
            rn < 0 || (size_t)rn >= sizeof(root))
            goto fail;
        dirExists(base, 1);
        dirExists(root, 1);
        if (snprintf(savesDir, sizeof(savesDir), "%s/Saves", root) >=
                (int)sizeof(savesDir) ||
            snprintf(logsDir, sizeof(logsDir), "%s/Logs", root) >=
                (int)sizeof(logsDir) ||
            snprintf(screenShotsDir, sizeof(screenShotsDir),
                     "%s/ScreenShots", root) >= (int)sizeof(screenShotsDir))
            goto fail;
        dirExists(savesDir, 1);
        dirExists(logsDir, 1);
        dirExists(screenShotsDir, 1);
        if (info->sample_rate > 0)
            obor_snd_rate = info->sample_rate;
        packfile_mode(0);
        goto capture_cwd;
    }

    /* Split the pak path into paksDir + packfile (engine convention). */
    strncpy(boot_pak, info->pak_path, sizeof(boot_pak) - 1);
    strncpy(packfile, info->pak_path, sizeof(packfile) - 1);
    {
        const char *slash = strrchr(info->pak_path, '/');
#ifdef _WIN32
        const char *bslash = strrchr(info->pak_path, '\\');
        if (!slash || (bslash && bslash > slash))
            slash = bslash;
#endif
        if (slash) {
            size_t n = (size_t)(slash - info->pak_path);
            if (n >= sizeof(paksDir))
                n = sizeof(paksDir) - 1;
            memcpy(paksDir, info->pak_path, n);
            paksDir[n] = '\0';
        }
    }
    /* Old eras hardcode "./Logs", "./Saves", ... relative to the CWD, and
     * newer ones default their *Dir globals to the same names — so chdir to
     * a writable root and let every era use its native layout. The root is
     * per engine build: a settings .cfg written by one build read by another
     * (different savedata layout) yields garbage — e.g. soundrate 0 and a
     * division-by-zero crash at game start. */
    if (info->save_dir && info->save_dir[0]) {
        char root[MAX_FILENAME_LEN];
        snprintf(root, sizeof(root), "%s/AnyBOR", info->save_dir);
        dirExists(root, 1);
        snprintf(root, sizeof(root), "%s/AnyBOR/%d", info->save_dir,
                 (int)OBOR_ENGINE_BUILD);
        dirExists(root, 1);
        if (chdir(root) != 0)
            goto fail;
    }
    strcpy(savesDir, "Saves");
    strcpy(logsDir, "Logs");
    strcpy(screenShotsDir, "ScreenShots");
    dirExists("Saves", 1);
    dirExists("Logs", 1);
    dirExists("ScreenShots", 1);
    dirExists("Paks", 1);

    if (info->sample_rate > 0)
        obor_snd_rate = info->sample_rate;

    packfile_mode(0);

    boot_dbg("boot: dirs ok");
capture_cwd:
    if (!obor_getcwd(engine_cwd, sizeof(engine_cwd)) ||
        chdir(frontend_cwd) != 0)
        goto fail;

    /* The engine runs on a dedicated ~16 MB stack inside the snapshot arena
     * (fixed VA, guard page below) — see obor_alloc.c. */
    if (!obor_arena_init())
        goto fail;
    boot_dbg("boot: arena ok");
    co_frontend = co_active();
    co_engine = co_derive(obor_stack_ptr(), (unsigned)obor_stack_size(),
                          engine_entry);
    if (!co_engine)
        goto fail;
    engine_alive = 1;
    obor_clock_us = 0;
    boot_dbg("boot: entering engine");

    /* Run the engine up to its first frame so boot failures surface here. */
    frame_ready = 0;
    switch_to_engine();
    boot_dbg("boot: first frame reached");
    if (engine_alive || frame_ready)
        return 1;
    obor_shutdown();
    return 0;

fail:
    chdir(frontend_cwd);
    engine_alive = 0;
    co_engine = NULL;
    obor_arena_release();
    engine_cwd[0] = '\0';
    return 0;
}

size_t obor_arena_used(void);

int32_t obor_run_frame(void)
{
    if (!engine_alive)
        return 0;
    obor_clock_us += FRAME_US;
    frame_ready = 0;
    while (!frame_ready && engine_alive)
        switch_to_engine();
    {
        static int dbg = -1, n;
        if (dbg < 0)
            dbg = getenv("OBOR_DEBUG_ARENA") != NULL;
        if (dbg && (++n % 100) == 0)
            fprintf(stderr, "[obor] frame %d arena %zu KB\n", n,
                    obor_arena_used() / 1024);
    }
    return engine_alive;
}

void *obor_engine_sp(void)
{
    /* libco's amd64/aarch64 backends store the cothread's saved stack
     * pointer in the first word of the handle. Valid while parked. */
    return co_engine ? *(void **)co_engine : NULL;
}

void obor_get_arena(void **base, uint32_t *used)
{
    *base = obor_arena_base();
    *used = (uint32_t)obor_arena_used();
}

void obor_get_video(const uint32_t **pixels, int32_t *width, int32_t *height,
                    int32_t *pitch_pixels)
{
    *pixels = fb_px;
    *width = fb_w;
    *height = fb_h;
    *pitch_pixels = fb_pitch;
}

void obor_set_button(int32_t player, int32_t button, int32_t down)
{
    if (player >= 0 && player < 4 && button >= 0 && button < 16)
        obor_pad[player][button] = (unsigned char)(down ? 1 : 0);
}

/* obor_get_audio lives in sblaster.c (needs the mixer);
 * obor_serialize/unserialize live in obor_state.c. */

/* Walk the BOR PACK directory (format identical across eras): trailing u32
 * points at the entry table; each entry is {u32 len, u32 start, u32 size,
 * char name[len-12]}. */
int obor_pak_has_prefix(const char *pakpath, const char *prefix)
{
    FILE *fp = fopen(pakpath, "rb");
    if (!fp)
        return 0;
    int found = 0;
    unsigned char tail[4];
    if (fseek(fp, -4, SEEK_END) != 0 || fread(tail, 1, 4, fp) != 4)
        goto out;
    long end;
    {
        long cur = ftell(fp);
        end = cur - 4;
    }
    unsigned int dir = (unsigned)tail[0] | ((unsigned)tail[1] << 8) |
                       ((unsigned)tail[2] << 16) | ((unsigned)tail[3] << 24);
    if (fseek(fp, (long)dir, SEEK_SET) != 0)
        goto out;
    size_t plen = strlen(prefix);
    while (ftell(fp) < end) {
        unsigned char e[12];
        if (fread(e, 1, 12, fp) != 12)
            break;
        unsigned int pns_len = (unsigned)e[0] | ((unsigned)e[1] << 8) |
                               ((unsigned)e[2] << 16) | ((unsigned)e[3] << 24);
        if (pns_len < 13 || pns_len > 1000)
            break;
        char name[1024];
        unsigned int nlen = pns_len - 12;
        if (nlen >= sizeof(name))
            break;
        if (fread(name, 1, nlen, fp) != nlen)
            break;
        name[nlen] = '\0';
        /* normalize slashes and compare case-insensitively */
        int match = 1;
        for (size_t i = 0; i < plen; i++) {
            char a = name[i], b = prefix[i];
            if (a == '\\')
                a = '/';
            if (b == '\\')
                b = '/';
            if (a >= 'A' && a <= 'Z')
                a += 32;
            if (b >= 'A' && b <= 'Z')
                b += 32;
            if (a != b || name[i] == '\0') {
                match = 0;
                break;
            }
        }
        if (match) {
            found = 1;
            break;
        }
    }
out:
    fclose(fp);
    return found;
}

/* patched into packfile.c per era; the log FILEs are utils.c globals.
 * All weak so an unpatched era still links. */
#ifndef _WIN32
void obor_packfile_closeall(void) __attribute__((weak));
extern FILE *openborLog __attribute__((weak));
extern FILE *scriptLog __attribute__((weak));
#else
void obor_packfile_closeall(void);
extern FILE *openborLog;
extern FILE *scriptLog;
#endif

void obor_shutdown(void)
{
    engine_alive = 0;
#ifdef WEBM
    /* Playback workers own arena allocations and pak handles. Join them
     * while those resources still exist, before abandoning the coroutine. */
    extern void obor_webm_stop(void);
    obor_webm_stop();
#endif
    /* co_engine came from co_derive over arena memory — nothing to free */
    co_engine = NULL;

    /* Release every OS resource this instance holds before the glue restores
     * pristine engine state; fds/FILEs would otherwise leak per reset. */
#ifndef _WIN32
    if (obor_packfile_closeall)
        obor_packfile_closeall();
    if (&openborLog && openborLog) {
        fclose(openborLog);
        openborLog = NULL;
    }
    if (&scriptLog && scriptLog) {
        fclose(scriptLog);
        scriptLog = NULL;
    }
#else
    obor_packfile_closeall();
    if (openborLog) {
        fclose(openborLog);
        openborLog = NULL;
    }
    if (scriptLog) {
        fclose(scriptLog);
        scriptLog = NULL;
    }
#endif
    obor_arena_release();
    engine_cwd[0] = '\0';
}
