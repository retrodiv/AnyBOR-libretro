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
#include "obor_fault.h"
#include "obor_random.h"

#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/stat.h>
#ifdef _WIN32
#include <direct.h> /* chdir */
#include <windows.h> /* NT_TIB stack-range fixup around co_switch */
#else
#include <unistd.h>
#include <signal.h>
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
uint32_t obor_profile_build;

static cothread_t co_frontend;
static cothread_t co_engine;
static int engine_alive;
static int engine_exit_status = -1;
static obor_fault engine_fault;
static char engine_fault_message[256];
static int test_fault_at = -1, test_fault_frame;
static char test_fault_kind[16];
static volatile uintptr_t test_fault_address;
void (*obor_resource_event)(uint32_t kind, uintptr_t handle);
extern int obor_live_threads;
void obor_co_restore_active(cothread_t frontend);
static int frame_ready;
/* Every supported engine sets this after its fonts, scripts, cached models
 * and object tables have finished loading. Loading-screen and timer yields
 * can occur before that point; they are not a completed boot. */
extern int startup_done;
static unsigned long long us_since_yield; /* sleep accumulator */

static const unsigned int *fb_px;
static int fb_w, fb_h, fb_pitch;

static char boot_pak[MAX_FILENAME_LEN];
static char content_alias_name[MAX_FILENAME_LEN];
static char engine_cwd[4096];

void obor_session_paths_get(obor_session_paths *paths)
{
    memcpy(paths->cwd, engine_cwd, sizeof(engine_cwd));
    memcpy(paths->pak, packfile, sizeof(packfile));
    memcpy(paths->boot_pak, boot_pak, sizeof(boot_pak));
    memcpy(paths->paks, paksDir, sizeof(paksDir));
    memcpy(paths->saves, savesDir, sizeof(savesDir));
    memcpy(paths->logs, logsDir, sizeof(logsDir));
    memcpy(paths->screenshots, screenShotsDir, sizeof(screenShotsDir));
}

void obor_session_paths_restore(const obor_session_paths *paths)
{
    memcpy(engine_cwd, paths->cwd, sizeof(engine_cwd));
    memcpy(packfile, paths->pak, sizeof(packfile));
    memcpy(boot_pak, paths->boot_pak, sizeof(boot_pak));
    memcpy(paksDir, paths->paks, sizeof(paksDir));
    memcpy(savesDir, paths->saves, sizeof(savesDir));
    memcpy(logsDir, paths->logs, sizeof(logsDir));
    memcpy(screenShotsDir, paths->screenshots, sizeof(screenShotsDir));
}
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
static void execute_engine(void *context)
{
    (void)context;
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
}

/* Opt-in test instrumentation: inject real memory faults inside the engine
 * coroutine. Inert unless the host explicitly selects this physical engine.
 * Format: OBOR_TEST_FAULT=<build>:<yield-number>:<read|write|null|context>.
 * Yield 0 faults before openborMain; later yields exercise runtime capture. */
__attribute__((noinline)) static unsigned exhaust_stack(unsigned n)
{
    volatile unsigned char padding[4096];
    padding[n & 4095] = (unsigned char)n;
    return exhaust_stack(n + 1) + padding[n & 4095];
}

static void inject_fault_kind(const char *kind, uintptr_t address)
{
    if (!strcmp(kind, "stack")) { (void)exhaust_stack(0); return; }
    if (!strcmp(kind, "allocator")) {
        /* Corrupt the in-use bit of a real arena chunk. dlmalloc's usage
         * check in realloc must reach the same hook as corpus heap damage. */
        void *(*volatile allocate)(size_t) = malloc;
        void *(*volatile resize)(void *, size_t) = realloc;
        void *block = allocate(64), *following = allocate(64);
        if (!block || !following) return;
        ((volatile size_t *)block)[-1] &= ~(size_t)2;
        void *result = resize(block, 128);
        (void)result;
        return;
    }
    if (!strcmp(kind, "context")) co_frontend = (cothread_t)(uintptr_t)1;
    if (!strcmp(kind, "write")) *(volatile unsigned char *)address = 42;
    else { volatile unsigned char value = *(volatile unsigned char *)address; (void)value; }
}

static void inject_test_fault(int frame)
{
    if (frame != test_fault_at) return;
    inject_fault_kind(test_fault_kind, test_fault_address);
}

void obor_test_fault_phase(const char *phase)
{
    const char *request = getenv("OBOR_TEST_CALL_FAULT");
    int build;
    char requested_phase[24], kind[16];
    if (request && sscanf(request, "%d:%23[^:]:%15s", &build, requested_phase, kind) == 3 &&
        build == OBOR_ENGINE_BUILD && !strcmp(phase, requested_phase) &&
        (!strcmp(kind, "read") || !strcmp(kind, "write") || !strcmp(kind, "null") ||
         !strcmp(kind, "allocator") || !strcmp(kind, "context")))
        inject_fault_kind(kind, !strcmp(kind, "null") ? 0 : OBOR_ARENA_BASE_VA);
}

int obor_protect_call(void (*execute)(void *), void *context, const char *phase)
{
#ifdef _WIN32
    extern uintptr_t __stack_chk_guard;
    uintptr_t frontend_stack_canary = __stack_chk_guard;
#endif
    /* Keep the recovery identity outside engine BSS: the engine may have
     * damaged its co_frontend global before the invalid access surfaced. */
    cothread_t frontend = co_active();
    int returned;
    obor_fault fault;
    returned = obor_fault_run_stack(execute, context, &fault,
                                    obor_stack_ptr(), obor_stack_size());
#ifdef _WIN32
    /* A fault can interrupt snapshot copying before obor_state repairs it. */
    __stack_chk_guard = frontend_stack_canary;
#endif
    if (returned != 1) {
        obor_co_restore_active(frontend);
        engine_alive = 0;
        engine_exit_status = OBOR_EXIT_MEMORY_FAULT;
        if (returned < 0)
            snprintf(engine_fault_message, sizeof(engine_fault_message),
                     "Could not install the engine memory-fault guard.");
        else {
            engine_fault = fault;
            if (fault.kind == OBOR_FAULT_ALLOCATOR)
                snprintf(engine_fault_message, sizeof(engine_fault_message),
                         "Allocator failed: invalid or corrupted memory.\nDuring: %s\nAddress: 0x%llx\nPC: 0x%llx", phase,
                         (unsigned long long)fault.address, (unsigned long long)fault.pc);
            else if (fault.kind == OBOR_FAULT_STACK)
                snprintf(engine_fault_message, sizeof(engine_fault_message),
                         "Engine stack exhausted.\nDuring: %s\nPC: 0x%llx", phase,
                         (unsigned long long)fault.pc);
            else if (fault.kind == OBOR_FAULT_STATE)
                snprintf(engine_fault_message, sizeof(engine_fault_message),
                         "State restore failed after modifying engine memory.\nDuring: %s", phase);
            else
            snprintf(engine_fault_message, sizeof(engine_fault_message),
#ifdef _WIN32
                     "Memory access violation (0x%08x).\nAddress: 0x%llx\nPC: 0x%llx\nDuring: %s",
#else
                     "%s: invalid memory access.\nAddress: 0x%llx\nPC: 0x%llx\nDuring: %s",
                     engine_fault.code == SIGBUS ? "SIGBUS" : "SIGSEGV",
#endif
#ifdef _WIN32
                     (unsigned)engine_fault.code,
#endif
                     (unsigned long long)engine_fault.address,
                     (unsigned long long)engine_fault.pc, phase);
        }
    }
    return returned == 1;
}

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
    obor_protect_call(execute_engine, NULL, "engine execution");
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
    inject_test_fault(++test_fault_frame);
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
    engine_exit_status = reset;
    engine_alive = 0;
    /* Never return into the engine: park forever yielding to the frontend. */
    for (;;)
        co_switch(co_frontend);
}

static void engine_entry(void)
{
    inject_test_fault(0);
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

/* The old dirExists helper truncates absolute paths to 128 bytes. Per-game
 * namespaces can exceed that even when the frontend root itself is short. */
static int obor_make_dir(const char *path)
{
#if defined(_WIN32)
    if (_mkdir(path) == 0) return 1;
    /* Attributes instead of stat(): an engine header can set
     * _FILE_OFFSET_BITS=64 (the 8023 tree does) after <sys/stat.h> was already
     * read here, and mingw then maps the stat() CALL to the 88-byte stat64
     * while this file keeps the 48-byte struct stat. The call then writes 40
     * bytes past its slot, over the caller's saved frame, and kills the boot
     * of exactly the engines that expose that define. Asking for the
     * attributes answers the same question with no struct to size wrong. */
    DWORD attrs = GetFileAttributesA(path);
    return attrs != INVALID_FILE_ATTRIBUTES &&
           (attrs & FILE_ATTRIBUTE_DIRECTORY) != 0;
#else
    if (mkdir(path, 0755) == 0) return 1;
    struct stat st;
    return errno == EEXIST && stat(path, &st) == 0 && S_ISDIR(st.st_mode);
#endif
}

uint32_t obor_abi_version(void)
{
    return OBOR_ABI_VERSION;
}

int32_t obor_boot(const obor_boot_info *info)
{
    if (!info || info->abi_version != OBOR_ABI_VERSION ||
        !info->arena_reserved || !info->profile_build)
        return 0;
    obor_profile_build = info->profile_build;
    obor_arena_authorize(info->arena_reserved);
    char frontend_cwd[4096];
    if (!obor_getcwd(frontend_cwd, sizeof(frontend_cwd)))
        return 0;
    engine_cwd[0] = '\0';
    content_alias_name[0] = '\0';

    if (!obor_state_set_save_dir(info->save_dir, obor_profile_build) ||
        !obor_state_set_regions(info))
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
        int bn = snprintf(base, sizeof(base), "%s", info->save_dir);
        int rn = snprintf(root, sizeof(root), "%s/%d",
                          info->save_dir, (int)obor_profile_build);
        if (bn < 0 || (size_t)bn >= sizeof(base) ||
            rn < 0 || (size_t)rn >= sizeof(root))
            goto fail;
        if (!obor_make_dir(base)) goto fail;
        if (!obor_make_dir(root)) goto fail;
        if (snprintf(savesDir, sizeof(savesDir), "%s/Saves", root) >=
                (int)sizeof(savesDir) ||
            snprintf(logsDir, sizeof(logsDir), "%s/Logs", root) >=
                (int)sizeof(logsDir) ||
            snprintf(screenShotsDir, sizeof(screenShotsDir),
                     "%s/ScreenShots", root) >= (int)sizeof(screenShotsDir))
            goto fail;
        if (!obor_make_dir(savesDir)) goto fail;
        if (!obor_make_dir(logsDir)) goto fail;
        if (!obor_make_dir(screenShotsDir)) goto fail;
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
     * a writable root and let every era use its native layout. The frontend supplies a per-game root. Its subdirectory is
     * per engine build: a settings .cfg written by one build read by another
     * (different savedata layout) yields garbage — e.g. soundrate 0 and a
     * division-by-zero crash at game start. */
    if (info->save_dir && info->save_dir[0]) {
        char root[4096];
        snprintf(root, sizeof(root), "%s", info->save_dir);
        if (!obor_make_dir(root)) goto fail;
        snprintf(root, sizeof(root), "%s/%d", info->save_dir,
                 (int)obor_profile_build);
        if (!obor_make_dir(root)) goto fail;
        if (chdir(root) != 0)
            goto fail;
    }
    strcpy(savesDir, "Saves");
    strcpy(logsDir, "Logs");
    strcpy(screenShotsDir, "ScreenShots");
    if (!obor_make_dir("Saves")) goto fail;
    if (!obor_make_dir("Logs")) goto fail;
    if (!obor_make_dir("ScreenShots")) goto fail;
    if (!obor_make_dir("Paks")) goto fail;

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
    if (!obor_fault_stack_prepare(obor_stack_ptr(), obor_stack_size())) goto fail;
    co_engine = co_derive(obor_stack_ptr(), (unsigned)obor_stack_size(),
                          engine_entry);
    if (!co_engine)
        goto fail;
    engine_alive = 1;
    engine_exit_status = -1;
    memset(&engine_fault, 0, sizeof(engine_fault));
    engine_fault_message[0] = '\0';
    obor_resource_event = info->resource_event;
    test_fault_at = -1;
    test_fault_frame = 0;
    {
        const char *request = getenv("OBOR_TEST_FAULT");
        int build, at;
        char kind[16];
        if (request && sscanf(request, "%d:%d:%15s", &build, &at, kind) == 3 &&
            build == OBOR_ENGINE_BUILD && at >= 0 &&
            (!strcmp(kind, "read") || !strcmp(kind, "write") || !strcmp(kind, "null") ||
             !strcmp(kind, "context") || !strcmp(kind, "allocator") || !strcmp(kind, "stack"))) {
            test_fault_at = at;
            snprintf(test_fault_kind, sizeof(test_fault_kind), "%s", kind);
            test_fault_address = !strcmp(kind, "null") ? 0 : OBOR_ARENA_BASE_VA;
        }
    }
    obor_clock_us = 0;
    boot_dbg("boot: entering engine");

    /* Finish resource initialization before the frontend fixes its rewind
     * allocation. A loading-screen/timer yield can otherwise leave only a
     * tiny bootstrap heap in that first snapshot. Keep the existing yields
     * and fault boundaries while completing boot, then stop at the first
     * ordinary frame; menus and intros still run through retro_run. */
    frame_ready = 0;
    switch_to_engine();
    while (engine_alive && !startup_done) {
        obor_clock_us += FRAME_US;
        frame_ready = 0;
        switch_to_engine();
    }
    boot_dbg("boot: first frame reached");
    if (engine_alive || (frame_ready && engine_exit_status == 0))
        return 1;
    if (engine_exit_status != OBOR_EXIT_MEMORY_FAULT) obor_shutdown();
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

int32_t obor_get_exit_status(void)
{
    return engine_exit_status;
}

int32_t obor_get_fault_message(char *out, uint32_t capacity)
{
    if (engine_exit_status != OBOR_EXIT_MEMORY_FAULT) return 0;
    if (out && capacity) snprintf(out, capacity, "%s", engine_fault_message);
    return 1;
}

#ifdef WEBM
static void stop_workers(void *unused)
{
    extern void obor_webm_stop(void);
    (void)unused;
    obor_webm_stop();
}
#endif

int32_t obor_abandon(void)
{
    extern void obor_audio_fault_unlock(void);
    engine_alive = 0;
    co_engine = NULL;
    /* dlmalloc can fail while holding its lock. Workers must not enter a
     * corrupted allocator, and joining them here could wait on that lock. */
    if (__atomic_load_n(&obor_live_threads, __ATOMIC_SEQ_CST) &&
        engine_fault.kind == OBOR_FAULT_ALLOCATOR) return 0;
    obor_audio_fault_unlock();
#ifdef WEBM
    if (__atomic_load_n(&obor_live_threads, __ATOMIC_SEQ_CST)) {
        obor_fault cleanup_fault;
        if (obor_fault_run(stop_workers, NULL, &cleanup_fault) != 1 ||
            __atomic_load_n(&obor_live_threads, __ATOMIC_SEQ_CST)) return 0;
    }
#endif
    obor_arena_release();
    engine_cwd[0] = '\0';
    obor_resource_event = NULL;
    return 1;
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
    /* Resource teardown may free arena-backed names outside a frame guard.
     * End owned protection while the fault guard still owns this thread. */
    if (!obor_owned_end()) {
        (void)obor_abandon();
        return;
    }
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
