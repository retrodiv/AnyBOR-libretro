/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
/*
 * Minimal headless libretro host for AnyBOR (Linux, macOS and Windows).
 *
 * Usage: libretro_host <core.so> <game.pak> <system_dir> <nframes> [ppm_prefix]
 *
 * Env:
 *   OBOR_INPUT="F-T:BTN[:pulse|hold],..."  scripted input timeline
 *   OBOR_INPUT_P1 .. OBOR_INPUT_P4   independent player timelines
 *       BTN: up down left right attack attack2 attack3 attack4 jump special
 *            start esc  (RetroPad ids resolved per the glue's mapping)
 *            analog_left analog_right analog_up analog_down (full stick)
 *   OBOR_ENGINE=<build>   force the obor_engine core option
 *   OBOR_DUMP_EVERY=N     dump a PPM every N frames (needs ppm_prefix)
 *   OBOR_SAVE_AT=N / OBOR_SAVE_STATE=file   serialize at frame N
 *   OBOR_LOAD_AT=N / OBOR_LOAD_STATE=file   unserialize at frame N
 *   OBOR_GAMELOG=On|Off   set the Forward game log core option
 *   OBOR_CRT_TV=On|Off / OBOR_CRT_TOGGLE_AT=N   CRT option and live toggle
 *   OBOR_VIDEO_TRACE=1 / OBOR_OPTIONS_VERSION=0|2   video/option diagnostics
 *   OBOR_STOP_WIDTH=N / OBOR_RESET_WIDTH=N / OBOR_LOAD_WIDTH=N
 *       act on the first frame of width N (synthetic WebM regression)
 *   OBOR_POST_UNLOAD_MS=N   keep the frontend alive after content unload
 *   OBOR_RESET_EVERY=N / OBOR_LOAD_EVERY=N   repeat lifecycle operations
 *   OBOR_CHECK_FDS=1   require the POSIX descriptor count to return to baseline
 *   OBOR_FD_PADDING=N  keep N host files open to shift core descriptor numbers
 *
 * Prints: frames=N last=WxH nonblack_max=N audio_energy=N
 */
#ifdef _WIN32
#include "dlfcn_win.h"
#include <direct.h>
#define host_getcwd _getcwd
#else
#include <dlfcn.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <unistd.h>
#define host_getcwd getcwd
#endif
#include <time.h>
#ifndef _WIN32
#include <execinfo.h>
#include <signal.h>
#include <sys/mman.h>
#include "obor_abi.h"
#endif
#include <stdint.h>
#include <stdio.h>
#include <sys/stat.h>
#include <stdlib.h>
#include <string.h>

#include "libretro.h"

#ifndef _WIN32
static int count_open_fds(void)
{
#if defined(__APPLE__)
    /* Darwin has no procfs. F_GETFD also sees descriptors above the small
     * set of device nodes that may be listed under /dev/fd. */
    long limit = sysconf(_SC_OPEN_MAX);
    if (limit < 0 || limit > INT_MAX)
        return -1;
    int count = 0;
    for (int fd = 0; fd < limit; ++fd) {
        int result;
        do {
            result = fcntl(fd, F_GETFD);
        } while (result < 0 && errno == EINTR);
        if (result >= 0)
            ++count;
        else if (errno != EBADF)
            return -1;
    }
    return count;
#else
    DIR *dir = opendir("/proc/self/fd");
    if (!dir)
        return -1;
    int count = -1; /* exclude the descriptor opened for this measurement */
    struct dirent *entry;
    while ((entry = readdir(dir)))
        if (entry->d_name[0] != '.')
            count++;
    closedir(dir);
    return count;
#endif
}

static void *reserve_host_range(void *address, size_t bytes, int protection)
{
    int flags = MAP_PRIVATE | MAP_ANONYMOUS;
#if defined(MAP_FIXED_NOREPLACE) && !defined(__APPLE__)
    flags |= MAP_FIXED_NOREPLACE;
#endif
    /* On systems without NOREPLACE, use a hint and reject a different
     * address. Never replace an existing frontend mapping with MAP_FIXED. */
    void *mapped = mmap(address, bytes, protection, flags, -1, 0);
    if (mapped != address) {
        if (mapped != MAP_FAILED)
            munmap(mapped, bytes);
        return MAP_FAILED;
    }
    return mapped;
}

static void crash_handler(int sig, siginfo_t *si, void *uc)
{
    (void)uc;
    void *frames[24];
    int n = backtrace(frames, 24);
    fprintf(stderr, "\n*** signal %d at addr %p ***\n", sig, si->si_addr);
    backtrace_symbols_fd(frames, n, 2);
    signal(sig, SIG_DFL);
    raise(sig);
}

static void install_crash_handler(void)
{
    static char altstack[64 * 1024];
    stack_t ss = { altstack, 0, sizeof(altstack) };
    sigaltstack(&ss, NULL);
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_sigaction = crash_handler;
    sa.sa_flags = SA_SIGINFO | SA_ONSTACK;
    sigaction(SIGSEGV, &sa, NULL);
    sigaction(SIGFPE, &sa, NULL);
    sigaction(SIGBUS, &sa, NULL);
    sigaction(SIGILL, &sa, NULL);
}
#else
static void install_crash_handler(void) {}
#endif


static retro_environment_t unused_env;
static char g_sysdir[1024];
static char g_savedir[1024];
static char g_engine_opt[32] = "auto";
static int g_var_dirty = 1;
static const char *g_crt_opt;

static const uint32_t *g_fb;
static unsigned g_fw, g_fh;
static size_t g_fpitch;
static long g_nonblack_max;
static unsigned long long g_audio_energy;
static int g_shutdown;
static int g_variable_states;

/* input timeline */
struct seg { int from, to, pad_id, port, device, value; int pulse; };
static struct seg g_segs[320];
static int g_nsegs;
static int g_frame;

/* OBS v2 contract, independent of the core's range collector. Test-only:
 * call with a deliberately dirty destination and verify the whole transport
 * buffer, including guard bytes and deterministic capacity padding. */
static int check_state_blob(const unsigned char *data, size_t size, int report)
{
    uint32_t head[4];
    uint64_t fields[7];
    if (size < 72) return 0;
    memcpy(head, data, sizeof(head));
    memcpy(fields, data + 16, sizeof(fields));
    if (head[0] != 0x3153424f || head[1] != 2 || !head[3] || head[3] > 16)
        return 0;
    size_t table = 72 + head[3] * 16, segments = 0;
    if (table > size) return 0;
    for (unsigned i = 0; i < head[3]; ++i) {
        uint64_t bytes;
        memcpy(&bytes, data + 72 + i * 16 + 8, 8);
        if (bytes > size - segments) return 0;
        segments += (size_t)bytes;
    }
#if defined(__aarch64__) || defined(__arm__)
    size_t context = 16384;
#else
    size_t context = 4096;
#endif
    if (table > size - segments || context > size - table - segments ||
        fields[6] < 32 || fields[6] > size - table - segments - context)
        return 0;

    const unsigned char *heap = data + table + segments + context;
    uint32_t sparse_head[4];
    uint64_t sparse_fields[2];
    memcpy(sparse_head, heap, sizeof(sparse_head));
    memcpy(sparse_fields, heap + 16, sizeof(sparse_fields));
    if (sparse_head[0] != 0x3153484f || sparse_head[1] != 2 ||
        sparse_head[3] != 0 || sparse_fields[0] != fields[3] ||
        sparse_fields[0] < (16u << 20))
        return 0;

    uint64_t extent = sparse_fields[0] - (16u << 20), payload = 0;
    size_t cursor = 32;
    for (uint32_t i = 0; i < sparse_head[2]; ++i) {
        uint64_t span[2];
        if (cursor > fields[6] || sizeof(span) > fields[6] - cursor)
            return 0;
        memcpy(span, heap + cursor, sizeof(span));
        cursor += sizeof(span);
        if (!span[1] || span[0] > extent || span[1] > extent - span[0] ||
            span[1] > sparse_fields[1] || payload > sparse_fields[1] - span[1] ||
            cursor > fields[6] || span[1] > fields[6] - cursor)
            return 0;
        cursor += (size_t)span[1];
        payload += span[1];
    }
    if (cursor != fields[6] || payload != sparse_fields[1])
        return 0;

    uint64_t used = table + segments + context + fields[6] + fields[5];
    if (used > size || segments >= (4u << 20)) return 0;
    for (size_t i = (size_t)used; i < size; ++i)
        if (data[i]) return 0;
    if (report)
        printf("state_contract version=%u capacity=%zu logical=%llu segments=%zu heap=%llu stack=%llu tail_zero=1\n",
               head[1], size, (unsigned long long)used, segments,
               (unsigned long long)fields[6], (unsigned long long)fields[5]);
    return 1;
}

static bool host_rumble(unsigned port, enum retro_rumble_effect effect,
                        uint16_t strength)
{
    if (getenv("OBOR_DEBUG") && effect == RETRO_RUMBLE_STRONG)
        printf("rumble: port=%u strength=%u\n", port, strength);
    return true;
}

static int btn_to_id(const char *name)
{
    static const struct { const char *n; int id; } map[] = {
        { "up", RETRO_DEVICE_ID_JOYPAD_UP },
        { "down", RETRO_DEVICE_ID_JOYPAD_DOWN },
        { "left", RETRO_DEVICE_ID_JOYPAD_LEFT },
        { "right", RETRO_DEVICE_ID_JOYPAD_RIGHT },
        { "attack", RETRO_DEVICE_ID_JOYPAD_Y },
        { "attack2", RETRO_DEVICE_ID_JOYPAD_X },
        { "attack3", RETRO_DEVICE_ID_JOYPAD_L },
        { "attack4", RETRO_DEVICE_ID_JOYPAD_R },
        { "jump", RETRO_DEVICE_ID_JOYPAD_B },
        { "special", RETRO_DEVICE_ID_JOYPAD_A },
        { "start", RETRO_DEVICE_ID_JOYPAD_START },
        { "esc", RETRO_DEVICE_ID_JOYPAD_SELECT },
        { "l2", RETRO_DEVICE_ID_JOYPAD_L2 },
        { "r2", RETRO_DEVICE_ID_JOYPAD_R2 },
        { "l3", RETRO_DEVICE_ID_JOYPAD_L3 },
        { "r3", RETRO_DEVICE_ID_JOYPAD_R3 },
    };
    for (size_t i = 0; i < sizeof(map) / sizeof(map[0]); i++)
        if (!strcmp(map[i].n, name))
            return map[i].id;
    return -1;
}

static void parse_input_timeline(const char *s, int port)
{
    if (!s)
        return;
    char *dup = strdup(s);
    for (char *tok = strtok(dup, ","); tok && g_nsegs < 320;
         tok = strtok(NULL, ",")) {
        int from, to;
        char btn[24], mode[16];
        mode[0] = 0;
        if (sscanf(tok, "%d-%d:%23[^:]:%15s", &from, &to, btn, mode) >= 3) {
            int id = btn_to_id(btn);
            int device = RETRO_DEVICE_JOYPAD, value = 1;
            if (!strncmp(btn, "analog_", 7)) {
                device = RETRO_DEVICE_ANALOG;
                if (!strcmp(btn, "analog_left") || !strcmp(btn, "analog_right"))
                    id = RETRO_DEVICE_ID_ANALOG_X;
                else if (!strcmp(btn, "analog_up") || !strcmp(btn, "analog_down"))
                    id = RETRO_DEVICE_ID_ANALOG_Y;
                value = (!strcmp(btn, "analog_left") || !strcmp(btn, "analog_up")) ? -32767 : 32767;
            }
            if (id >= 0) {
                g_segs[g_nsegs].from = from;
                g_segs[g_nsegs].to = to;
                g_segs[g_nsegs].pad_id = id;
                g_segs[g_nsegs].port = port;
                g_segs[g_nsegs].device = device;
                g_segs[g_nsegs].value = value;
                g_segs[g_nsegs].pulse = strcmp(mode, "hold") != 0;
                g_nsegs++;
            }
        }
    }
    free(dup);
}

static void parse_input_env(void)
{
    parse_input_timeline(getenv("OBOR_INPUT"), 0);
    for (int port = 0; port < 4; ++port) {
        char key[32];
        snprintf(key, sizeof(key), "OBOR_INPUT_P%d", port + 1);
        parse_input_timeline(getenv(key), port);
    }
}

static bool env_cb(unsigned cmd, void *data)
{
    switch (cmd) {
    case RETRO_ENVIRONMENT_GET_CORE_OPTIONS_VERSION:
        *(unsigned *)data = getenv("OBOR_OPTIONS_VERSION") ?
            (unsigned)atoi(getenv("OBOR_OPTIONS_VERSION")) : 0;
        return true;
    case RETRO_ENVIRONMENT_SET_CORE_OPTIONS_V2: {
        const struct retro_core_options_v2 *opts = data;
        if (getenv("OBOR_VIDEO_TRACE")) {
            const struct retro_core_option_v2_category *cat = opts->categories;
            const struct retro_core_option_v2_definition *def = opts->definitions;
            printf("category_order=");
            for (; cat->key; ++cat)
                printf("%s%s", cat == opts->categories ? "" : "|", cat->desc);
            printf("\noption_order=");
            for (; def->key; ++def)
                printf("%s%s", def == opts->definitions ? "" : "|", def->key);
            printf("\n");
            cat = opts->categories;
            def = opts->definitions;
            for (; cat->key; ++cat)
                if (!strcmp(cat->key, "video"))
                    printf("video_category=%s\n", cat->desc);
            for (; def->key; ++def)
                if (!strcmp(def->key, "obor_crt_tv"))
                    printf("crt_option=%s category=%s default=%s\n",
                           def->desc, def->category_key, def->default_value);
        }
        return true;
    }
    case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT:
        return *(enum retro_pixel_format *)data == RETRO_PIXEL_FORMAT_XRGB8888;
    case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY:
        *(const char **)data = g_sysdir;
        return true;
    case RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY:
        if (getenv("OBOR_NO_SAVE_DIR")) {
            *(const char **)data = NULL;
            return false;
        }
        *(const char **)data = g_savedir;
        return true;
    case RETRO_ENVIRONMENT_GET_VARIABLE: {
        struct retro_variable *storage_var = (struct retro_variable *)data;
        const char *storage_env = NULL;
        if (!strcmp(storage_var->key, "obor_clear_local_data")) storage_env = "OBOR_CLEAR_LOCAL_DATA";
        if (!strcmp(storage_var->key, "obor_clear_game_cache")) storage_env = "OBOR_CLEAR_GAME_CACHE";
        if (!strcmp(storage_var->key, "obor_clear_all_caches")) storage_env = "OBOR_CLEAR_ALL_CACHES";
        if (storage_env && getenv(storage_env)) {
            storage_var->value = getenv(storage_env);
            return true;
        }

        struct retro_variable *var = (struct retro_variable *)data;
        if (!strcmp(var->key, "obor_crt_tv") && g_crt_opt) {
            var->value = g_crt_opt;
            return true;
        }
        if (!strcmp(var->key, "obor_gamelog") && getenv("OBOR_GAMELOG")) {
            var->value = getenv("OBOR_GAMELOG");
            return true;
        }
        if (!strcmp(var->key, "obor_engine")) {
            var->value = g_engine_opt;
            return true;
        }
        return false;
    }
    case RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE:
        *(bool *)data = g_var_dirty != 0;
        g_var_dirty = 0;
        return true;
    case RETRO_ENVIRONMENT_SET_MEMORY_MAPS:
        if (getenv("OBOR_DEBUG")) {
            const struct retro_memory_map *mm = data;
            for (unsigned i = 0; i < mm->num_descriptors; i++)
                printf("memmap: ptr=%p len=%zu KB\n",
                       mm->descriptors[i].ptr,
                       mm->descriptors[i].len / 1024);
        }
        return true;
    case RETRO_ENVIRONMENT_SET_SERIALIZATION_QUIRKS: {
        uint64_t *quirks = data;
        if (!getenv("OBOR_FIXED_STATE_FRONTEND")) {
            *quirks |= RETRO_SERIALIZATION_QUIRK_FRONT_VARIABLE_SIZE;
            g_variable_states = 1;
        }
        return true;
    }
    case RETRO_ENVIRONMENT_GET_RUMBLE_INTERFACE: {
        struct retro_rumble_interface *ri = data;
        ri->set_rumble_state = host_rumble;
        return true;
    }
    case RETRO_ENVIRONMENT_GET_MESSAGE_INTERFACE_VERSION:
        *(unsigned *)data = 1;
        return true;
    case RETRO_ENVIRONMENT_SET_MESSAGE_EXT:
        if (((const struct retro_message_ext *)data)->level == RETRO_LOG_ERROR)
            printf("load_error_osd: %s\n", ((const struct retro_message_ext *)data)->msg);
        if (getenv("OBOR_DEBUG"))
            printf("osd: %s\n",
                   ((const struct retro_message_ext *)data)->msg);
        return true;
    case RETRO_ENVIRONMENT_SET_INPUT_DESCRIPTORS:
        if (getenv("OBOR_DEBUG")) {
            const struct retro_input_descriptor *d = data;
            for (; d->description; d++)
                if (d->port == 0)
                    printf("descriptor: id=%u '%s'\n", d->id, d->description);
        }
        return true;
    case RETRO_ENVIRONMENT_SET_VARIABLES:
        if (getenv("OBOR_VIDEO_TRACE")) {
            const struct retro_variable *var = data;
            printf("option_order=");
            for (; var->key; ++var)
                printf("%s%s", var == (const struct retro_variable *)data ? "" : "|", var->key);
            printf("\n");
            var = data;
            for (; var->key; ++var)
                if (!strcmp(var->key, "obor_crt_tv"))
                    printf("crt_legacy=%s\n", var->value);
        }
        return true;
    case RETRO_ENVIRONMENT_GET_LOG_INTERFACE: {
        struct retro_log_callback *cb = (struct retro_log_callback *)data;
        cb->log = (retro_log_printf_t)printf;
        return false; /* let the core fall back; printf signature differs */
    }
    case RETRO_ENVIRONMENT_SHUTDOWN:
        g_shutdown = 1;
        return true;
    case RETRO_ENVIRONMENT_SET_GEOMETRY:
        if (getenv("OBOR_VIDEO_TRACE")) {
            const struct retro_game_geometry *geo = data;
            printf("geometry=%ux%u aspect=%.6f frame=%d\n",
                   geo->base_width, geo->base_height, geo->aspect_ratio, g_frame);
        }
        return true;
    default:
        return false;
    }
}

static void video_cb(const void *data, unsigned width, unsigned height,
                     size_t pitch)
{
    g_fw = width;
    g_fh = height;
    g_fpitch = pitch;
    g_fb = (const uint32_t *)data;
    if (!data)
        return;
    long nb = 0;
    const uint8_t *rows = (const uint8_t *)data;
    for (unsigned y = 0; y < height; y++) {
        const uint32_t *px = (const uint32_t *)(rows + y * pitch);
        for (unsigned x = 0; x < width; x++)
            if (px[x] & 0xFFFFFF)
                nb++;
    }
    if (nb > g_nonblack_max)
        g_nonblack_max = nb;
}

static void audio_sample_cb(int16_t l, int16_t r)
{
    g_audio_energy += (l > 0 ? l : -l) + (r > 0 ? r : -r);
}

static size_t audio_batch_cb(const int16_t *data, size_t frames)
{
    for (size_t i = 0; i < frames * 2; i++)
        g_audio_energy += (unsigned)(data[i] > 0 ? data[i] : -data[i]);
    return frames;
}

static void input_poll_cb(void) {}

static int16_t input_state_cb(unsigned port, unsigned device, unsigned index,
                              unsigned id)
{
    if (port >= 4 || index != 0)
        return 0;
    for (int i = 0; i < g_nsegs; i++) {
        if (g_frame >= g_segs[i].from && g_frame <= g_segs[i].to &&
            port == (unsigned)g_segs[i].port && device == (unsigned)g_segs[i].device &&
            (unsigned)g_segs[i].pad_id == id) {
            if (!g_segs[i].pulse)
                return (int16_t)g_segs[i].value;
            return ((g_frame - g_segs[i].from) % 30) < 4 ? (int16_t)g_segs[i].value : 0;
        }
    }
    return 0;
}

static void dump_ppm(const char *prefix, int frame)
{
    if (!g_fb)
        return;
    char path[1200];
    snprintf(path, sizeof(path), "%s%06d.ppm", prefix, frame);
    FILE *f = fopen(path, "wb");
    if (!f)
        return;
    fprintf(f, "P6\n%u %u\n255\n", g_fw, g_fh);
    const uint8_t *rows = (const uint8_t *)g_fb;
    for (unsigned y = 0; y < g_fh; y++) {
        const uint32_t *px = (const uint32_t *)(rows + y * g_fpitch);
        for (unsigned x = 0; x < g_fw; x++) {
            uint8_t rgb[3] = { (uint8_t)(px[x] >> 16), (uint8_t)(px[x] >> 8),
                               (uint8_t)px[x] };
            fwrite(rgb, 1, 3, f);
        }
    }
    fclose(f);
}

int main(int argc, char **argv)
{
    if (argc < 5) {
        fprintf(stderr,
                "usage: %s <core.so> <game.pak> <sysdir> <nframes> [ppm]\n",
                argv[0]);
        return 2;
    }
    const char *core_path = argv[1], *pak = argv[2];
    char initial_cwd[4096], final_cwd[4096];
    if (!host_getcwd(initial_cwd, sizeof(initial_cwd)))
        return 2;
    snprintf(g_sysdir, sizeof(g_sysdir), "%s", argv[3]);
    #ifdef _WIN32
    snprintf(g_savedir, sizeof(g_savedir), "%s\\saves", argv[3]);
#else
    snprintf(g_savedir, sizeof(g_savedir), "%s/saves", argv[3]);
#endif
    int nframes = atoi(argv[4]);
    const char *ppm = argc > 5 ? argv[5] : NULL;

    install_crash_handler();
#ifndef _WIN32
    const int check_signals[] = {SIGSEGV, SIGBUS, SIGILL, SIGFPE, SIGABRT};
    struct sigaction saved_signals[5];
    for (int i = 0; i < 5; ++i) sigaction(check_signals[i], NULL, &saved_signals[i]);
    unsigned char *occupied = NULL;
    if (getenv("OBOR_OCCUPIED_ARENA")) {
        occupied = reserve_host_range((void *)OBOR_ARENA_BASE_VA, 4096,
                                      PROT_READ | PROT_WRITE);
        if (occupied != (void *)OBOR_ARENA_BASE_VA) return 2;
        memset(occupied, 0xa5, 4096);
    }
#endif
    const char *eng = getenv("OBOR_ENGINE");
    if (eng)
        snprintf(g_engine_opt, sizeof(g_engine_opt), "%s", eng);
    parse_input_env();
    g_crt_opt = getenv("OBOR_CRT_TV");

#ifdef _WIN32
    _mkdir(g_sysdir);
    _mkdir(g_savedir);
#else
    mkdir(g_sysdir, 0700);
    mkdir(g_savedir, 0700);
#endif

    FILE *host_files[16] = {0};
    int padding = getenv("OBOR_FD_PADDING") ? atoi(getenv("OBOR_FD_PADDING")) : 0;
    if (padding < 0 || padding > 16)
        return 2;
    for (int i = 0; i < padding; ++i) {
        host_files[i] = tmpfile();
        if (!host_files[i] || fputs("host resource guard\n", host_files[i]) < 0 ||
            fflush(host_files[i]) != 0)
            return 2;
    }
#ifndef _WIN32
    int fds_before = getenv("OBOR_CHECK_FDS") ? count_open_fds() : -1;
    if (getenv("OBOR_CHECK_FDS") && fds_before < 0) {
        fprintf(stderr, "cannot count open file descriptors\n");
        return 2;
    }
#endif
    void *h = dlopen(core_path, RTLD_NOW | RTLD_LOCAL);
    if (!h) {
        fprintf(stderr, "dlopen: %s\n", dlerror());
        return 1;
    }
#define SYM(name) __typeof__(name) *p_##name = (__typeof__(name) *)dlsym(h, #name)
    SYM(retro_set_environment);
    SYM(retro_set_video_refresh);
    SYM(retro_set_audio_sample);
    SYM(retro_set_audio_sample_batch);
    SYM(retro_set_input_poll);
    SYM(retro_set_input_state);
    SYM(retro_init);
    SYM(retro_get_system_info);
    SYM(retro_get_system_av_info);
    SYM(retro_load_game);
    SYM(retro_run);
    SYM(retro_unload_game);
    SYM(retro_reset);
    SYM(retro_deinit);
    SYM(retro_serialize_size);
    SYM(retro_serialize);
    SYM(retro_unserialize);
#undef SYM
    if (!p_retro_set_environment || !p_retro_get_system_info || !p_retro_load_game || !p_retro_run) {
        fprintf(stderr, "core lacks retro_* symbols\n");
        return 1;
    }
    if (getenv("OBOR_DEBUG"))
        fprintf(stderr, "core retro_run=%p\n", (void *)p_retro_run);

    struct retro_system_info identity = {0};
    p_retro_get_system_info(&identity);
    printf("library_name=%s\n", identity.library_name ? identity.library_name : "");

    p_retro_set_environment(env_cb);
    p_retro_set_video_refresh(video_cb);
    p_retro_set_audio_sample(audio_sample_cb);
    p_retro_set_audio_sample_batch(audio_batch_cb);
    p_retro_set_input_poll(input_poll_cb);
    p_retro_set_input_state(input_state_cb);
    p_retro_init();

    struct retro_game_info info = { pak, NULL, 0, NULL };
    int loaded = p_retro_load_game(&info);
#ifndef _WIN32
    if (occupied) {
        if (loaded) { fprintf(stderr, "occupied arena was accepted\n"); return 1; }
        for (int i = 0; i < 4096; ++i) if (occupied[i] != 0xa5) return 1;
        p_retro_deinit();
        dlclose(h);
        for (int i = 0; i < 4096; ++i) if (occupied[i] != 0xa5) return 1;
        munmap(occupied, 4096);
        puts("occupied_arena_rejected=1 foreign_mapping_preserved=1");
        return 0;
    }
#endif
    if (!loaded) {
        fprintf(stderr, "retro_load_game failed\n");
        p_retro_deinit();
        return 1;
    }
    if (getenv("OBOR_VIDEO_TRACE")) {
        struct retro_system_av_info av;
        p_retro_get_system_av_info(&av);
        printf("initial_geometry=%ux%u aspect=%.6f\n",
               av.geometry.base_width, av.geometry.base_height, av.geometry.aspect_ratio);
    }

    size_t contract_sz = 0;
    unsigned char *contract_buf = NULL;
    if (getenv("OBOR_STATE_CHECK")) {
        contract_sz = p_retro_serialize_size(); /* before the first retro_run */
        if (!contract_sz || contract_sz > UINT32_MAX) return 1;
        contract_buf = malloc(contract_sz + 16);
        if (!contract_buf) return 1;
        memset(contract_buf, 0xa5, contract_sz + 16);
        if (!p_retro_serialize(contract_buf + 8, contract_sz) ||
            !check_state_blob(contract_buf + 8, contract_sz, 1)) {
            fprintf(stderr, "initial state contract failed\n");
            return 1;
        }
        uint32_t invalid_version = 0, current_version = 2;
        memcpy(contract_buf + 12, &invalid_version, 4);
        if (p_retro_unserialize(contract_buf + 8, contract_sz)) return 1;
        memcpy(contract_buf + 12, &current_version, 4);
        if (p_retro_unserialize(contract_buf + 8, 72)) return 1;
        puts("invalid_version_and_truncation_rejected=1");
    }

    int dump_every = 0;
    if (getenv("OBOR_DUMP_EVERY"))
        dump_every = atoi(getenv("OBOR_DUMP_EVERY"));

    /* OBOR_REWIND_AT=N: serialize EVERY frame from N-60 (timing the cost a
     * frontend rewind ring pays), snapshot once at N-60, restore it at N
     * (same-session rewind) and keep running. */
    int rewind_at = getenv("OBOR_REWIND_AT") ? atoi(getenv("OBOR_REWIND_AT")) : -1;
    unsigned char *rw_keep = NULL, *rw_scratch = NULL;
    size_t ring_sz = 0;
    double ser_ms_acc = 0;
    int ser_n = 0;
    int save_at = getenv("OBOR_SAVE_AT") ? atoi(getenv("OBOR_SAVE_AT")) : -1;
    int reset_at = getenv("OBOR_RESET_AT") ? atoi(getenv("OBOR_RESET_AT")) : -1;
    int reset_every = getenv("OBOR_RESET_EVERY") ? atoi(getenv("OBOR_RESET_EVERY")) : 0;
    /* OBOR_SET_ENGINE_AT=frame:build — change the core option mid-run (the
     * glue re-reads it on retro_reset) */
    int setopt_at = -1; char setopt_val[32] = "";
    if (getenv("OBOR_SET_ENGINE_AT"))
        sscanf(getenv("OBOR_SET_ENGINE_AT"), "%d:%31s", &setopt_at, setopt_val);

    /* OBOR_RAREWIND=START,COUNT: mimic RetroArch's rewind exactly — push a
     * state every frame; from START, each iteration pops the previous state,
     * unserializes it and lets the normal retro_run of this iteration render
     * it. Prints per-step frame-hash comparison vs the forward run. */
    int rw_start = -1, rw_count = 0;
    if (getenv("OBOR_RAREWIND"))
        sscanf(getenv("OBOR_RAREWIND"), "%d,%d", &rw_start, &rw_count);
    unsigned char **rw_ring = NULL;
    uint32_t *fwd_hash = NULL;
    size_t rw_sz = 0;
    int rw_step = 0;
    if (rw_start > 0) {
        if (rw_count < 2 || rw_count > 128 || rw_start <= rw_count) return 1;
        rw_ring = calloc(rw_count + 4, sizeof(*rw_ring));
        fwd_hash = calloc(rw_start + 2, sizeof(uint32_t));
        rw_sz = p_retro_serialize_size(); /* frontend's cold fixed capacity */
        if (!rw_ring || !fwd_hash || !rw_sz) return 1;
        printf("rewind_capacity=%zu\n", rw_sz);
    }
    int load_at = getenv("OBOR_LOAD_AT") ? atoi(getenv("OBOR_LOAD_AT")) : -1;
    int load_every = getenv("OBOR_LOAD_EVERY") ? atoi(getenv("OBOR_LOAD_EVERY")) : 0;
    int stop_width = getenv("OBOR_STOP_WIDTH") ? atoi(getenv("OBOR_STOP_WIDTH")) : 0;
    int reset_width = getenv("OBOR_RESET_WIDTH") ? atoi(getenv("OBOR_RESET_WIDTH")) : 0;
    int load_width = getenv("OBOR_LOAD_WIDTH") ? atoi(getenv("OBOR_LOAD_WIDTH")) : 0;

    for (g_frame = 0; g_frame < nframes && !g_shutdown; g_frame++) {
        size_t current_state_size = p_retro_serialize_size();
        if (contract_sz && current_state_size != contract_sz) {
            if (!g_variable_states || !current_state_size ||
                current_state_size > UINT32_MAX)
                return 1;
            unsigned char *grown = realloc(contract_buf, current_state_size + 16);
            if (!grown)
                return 1;
            contract_buf = grown;
            contract_sz = current_state_size;
        }
        if (rw_sz && current_state_size < rw_sz) {
            fprintf(stderr, "frontend rejected changed state capacity at frame %d\n", g_frame);
            return 1;
        }
        if (getenv("OBOR_CRT_TOGGLE_AT") &&
            g_frame == atoi(getenv("OBOR_CRT_TOGGLE_AT"))) {
            g_crt_opt = g_crt_opt && !strcmp(g_crt_opt, "On") ? "Off" : "On";
            g_var_dirty = 1;
        }
        int rw_popped = 0;
        if (rw_start > 0 && g_frame >= rw_start && rw_step < rw_count) {
            int slot = (rw_start - 1 - rw_step) % (rw_count + 4);
            if (!rw_ring[slot] || !p_retro_unserialize(rw_ring[slot], rw_sz)) {
                fprintf(stderr, "rewind restore rejected at frame %d\n", g_frame);
                return 1;
            }
            rw_step++;
            rw_popped = 1;
        }
        p_retro_run();
        if (contract_buf) {
            memset(contract_buf, 0xa5, contract_sz + 16);
            if (!p_retro_serialize(contract_buf + 8, contract_sz) ||
                !check_state_blob(contract_buf + 8, contract_sz, g_frame == nframes - 1)) {
                fprintf(stderr, "state contract failed at frame %d\n", g_frame);
                return 1;
            }
            for (unsigned i = 0; i < 8; ++i)
                if (contract_buf[i] != 0xa5 || contract_buf[8 + contract_sz + i] != 0xa5)
                    return 1;
        }
        if (stop_width && g_fw == (unsigned)stop_width) {
            printf("stop_width=%u at frame %d\n", g_fw, g_frame);
            break;
        }
        if (reset_width && g_fw == (unsigned)reset_width) {
            printf("reset_width=%u at frame %d\n", g_fw, g_frame);
            reset_at = g_frame;
            reset_width = 0;
        }
        if (load_width && g_fw == (unsigned)load_width) {
            printf("load_width=%u at frame %d\n", g_fw, g_frame);
            load_at = g_frame;
            load_width = 0;
        }
        if (rw_start > 0) {
            uint32_t hh = 2166136261u;
            const uint8_t *rows = (const uint8_t *)g_fb;
            for (unsigned y = 0; y < g_fh && g_fb; ++y) {
                const uint32_t *px = (const uint32_t *)(rows + y * g_fpitch);
                for (unsigned x = 0; x < g_fw; ++x)
                    hh = (hh ^ px[x]) * 16777619u;
            }
            if (g_frame < rw_start) {
                fwd_hash[g_frame] = hh;
            } else if (rw_popped) {
                int shown = rw_start - rw_step + 1; /* expected forward frame */
                /* step 1 shows frame rw_start itself, which the forward run
                 * never hashed (rewind replaced it) — no reference exists */
                printf("rewind step %d: shows fwd frame %d %s\n", rw_step,
                       shown,
                       shown >= rw_start ? "NOREF"
                       : (shown >= 0 && fwd_hash[shown] == hh) ? "MATCH"
                                                               : "MISMATCH");
                if (shown < rw_start && (shown < 0 || fwd_hash[shown] != hh)) return 1;
                if (rw_step == rw_count) {
                    int changes = 0;
                    for (int i = rw_start - rw_count + 2; i < rw_start; ++i)
                        changes += fwd_hash[i] != fwd_hash[i - 1];
                    printf("rewind_reference_changes=%d\n", changes);
                }
                if (ppm) {
                    char pfx[1100];
                    snprintf(pfx, sizeof(pfx), "%srwstep", ppm);
                    dump_ppm(pfx, rw_step);
                }
            }
            if (g_frame < rw_start) {
                int slot = g_frame % (rw_count + 4);
                if (!rw_ring[slot])
                    rw_ring[slot] = malloc(rw_sz);
                if (!rw_ring[slot] || !p_retro_serialize(rw_ring[slot], rw_sz)) {
                    fprintf(stderr, "rewind push rejected at frame %d\n", g_frame);
                    return 1;
                }
            }
        }
        if (ppm && dump_every && g_frame % dump_every == 0)
            dump_ppm(ppm, g_frame);

        if (rewind_at > 0 && g_frame >= rewind_at - 60 && g_frame <= rewind_at) {
            struct timespec t0, t1;
            if (!ring_sz) {
                ring_sz = p_retro_serialize_size();
                rw_keep = malloc(ring_sz);
                rw_scratch = malloc(ring_sz);
            }
            clock_gettime(CLOCK_MONOTONIC, &t0);
            if (g_frame == rewind_at - 60) {
                if (!rw_keep || !rw_scratch || !p_retro_serialize(rw_keep, ring_sz)) return 1;
            } else if (g_frame < rewind_at) {
                if (!p_retro_serialize(rw_scratch, ring_sz)) return 1;
                clock_gettime(CLOCK_MONOTONIC, &t1);
                ser_ms_acc += (t1.tv_sec - t0.tv_sec) * 1e3 +
                              (t1.tv_nsec - t0.tv_nsec) / 1e6;
                ser_n++;
            } else {
                int ok = p_retro_unserialize(rw_keep, ring_sz);
                if (!ok) return 1;
                clock_gettime(CLOCK_MONOTONIC, &t1);
                printf("rewind: serialize %.2f ms/frame avg (%d), "
                       "unserialize ok=%d %.2f ms, size=%zu\n",
                       ser_ms_acc / (ser_n ? ser_n : 1), ser_n, ok,
                       (t1.tv_sec - t0.tv_sec) * 1e3 +
                           (t1.tv_nsec - t0.tv_nsec) / 1e6,
                       ring_sz);
            }
        }
        /* OBOR_FASTCHECK=START,COUNT: serialize into the SAME buffer every
         * frame (exercising the core's incremental fast path), then compare
         * the accumulated result against a fresh full serialize. */
        static int fc_start = -2, fc_count = 0;
        static unsigned char *fc_a = NULL;
        if (fc_start == -2) {
            fc_start = -1;
            if (getenv("OBOR_FASTCHECK"))
                sscanf(getenv("OBOR_FASTCHECK"), "%d,%d", &fc_start,
                       &fc_count);
        }
        if (fc_start > 0 && g_frame >= fc_start) {
            size_t sz = p_retro_serialize_size();
            if (!fc_a)
                fc_a = calloc(1, sz); /* zero tails -> comparable */
            p_retro_serialize(fc_a, sz);
            if (g_frame == fc_start + fc_count) {
                unsigned char *fc_b = calloc(1, sz);
                p_retro_serialize(fc_b, sz);
                /* OBS v2 serializes module bookkeeping as well as game data.
                 * The second call changes serializer counters/pointers and old
                 * buffers retain unused tail bytes. Compare the actual heap and
                 * parked stack payload, whose incremental path is under test. */
                uint32_t magic, version, nseg;
                uint64_t heap_len, stack_len;
                memcpy(&magic, fc_a, 4); memcpy(&version, fc_a + 4, 4);
                memcpy(&nseg, fc_a + 12, 4);
                memcpy(&stack_len, fc_a + 56, 8); memcpy(&heap_len, fc_a + 64, 8);
                if (sz < 72 || magic != 0x3153424f || version != 2 || nseg > 16 ||
                    memcmp(fc_a, fc_b, 72)) {
                    fprintf(stderr, "fastcheck: unexpected or inconsistent state header\n");
                    return 1;
                }
                size_t begin = 72 + (size_t)nseg * 16;
                for (uint32_t i = 0; i < nseg; ++i) {
                    uint64_t bytes;
                    memcpy(&bytes, fc_a + 72 + (size_t)i * 16 + 8, 8);
                    if (bytes > sz - begin) return 1;
                    begin += (size_t)bytes;
                }
#if defined(__aarch64__)
                size_t head = 16384;
#else
                size_t head = 4096;
#endif
                if (begin > sz || head > sz - begin || heap_len > sz - begin - head ||
                    stack_len > sz - begin - head - heap_len) return 1;
                size_t length = head + (size_t)heap_len + (size_t)stack_len;
                if (memcmp(fc_a + begin, fc_b + begin, length)) {
                    fprintf(stderr, "fastcheck: heap/stack differs from full snapshot\n");
                    return 1;
                }
                printf("fastcheck after %d incremental frames: HEAP_AND_STACK_IDENTICAL\n", fc_count);
                free(fc_b);
                fc_start = -1;
            }
        }

        if (g_frame == setopt_at && setopt_val[0]) {
            snprintf(g_engine_opt, sizeof(g_engine_opt), "%s", setopt_val);
            g_var_dirty = 1;
            printf("core option obor_engine := %s at frame %d\n", setopt_val,
                   g_frame);
        }
        if (g_frame == reset_at ||
            (reset_every > 0 && g_frame > 0 && g_frame % reset_every == 0)) {
            printf("reset at frame %d\n", g_frame);
            p_retro_reset();
        }
        if (g_frame == save_at && getenv("OBOR_SAVE_STATE")) {
            size_t sz = p_retro_serialize_size();
            void *buf = malloc(sz);
            if (buf && p_retro_serialize(buf, sz)) {
                FILE *f = fopen(getenv("OBOR_SAVE_STATE"), "wb");
                if (f) {
                    fwrite(&sz, sizeof(sz), 1, f);
                    fwrite(buf, 1, sz, f);
                    fclose(f);
                    printf("saved state (%zu bytes) at frame %d\n", sz, g_frame);
                }
            }
            free(buf);
        }
        if ((g_frame == load_at ||
             (load_every > 0 && g_frame >= load_at && g_frame % load_every == 0)) &&
            getenv("OBOR_LOAD_STATE")) {
            FILE *f = fopen(getenv("OBOR_LOAD_STATE"), "rb");
            if (f) {
                size_t sz = 0;
                if (fread(&sz, sizeof(sz), 1, f) == 1) {
                    void *buf = malloc(sz);
                    if (buf && fread(buf, 1, sz, f) == sz) {
                        printf("load state at frame %d: %s\n", g_frame,
                               p_retro_unserialize(buf, sz) ? "ok" : "FAILED");
                    }
                    free(buf);
                }
                fclose(f);
            }
        }
    }
    if (ppm)
        dump_ppm(ppm, g_frame);

    printf("frames=%d last=%ux%u nonblack_max=%ld audio_energy=%llu%s\n",
           g_frame, g_fw, g_fh, g_nonblack_max, g_audio_energy,
           g_shutdown ? " (shutdown)" : "");
    free(contract_buf);
    free(rw_keep);
    free(rw_scratch);
    if (rw_ring) {
        for (int i = 0; i < rw_count + 4; ++i) free(rw_ring[i]);
        free(rw_ring);
    }
    free(fwd_hash);
    p_retro_unload_game();
    if (getenv("OBOR_POST_UNLOAD_MS")) {
        unsigned ms = (unsigned)atoi(getenv("OBOR_POST_UNLOAD_MS"));
#ifdef _WIN32
        Sleep(ms);
#else
        usleep(ms * 1000u);
#endif
    }
    p_retro_deinit();
    if (!host_getcwd(final_cwd, sizeof(final_cwd)) ||
        strcmp(initial_cwd, final_cwd) != 0) {
        fprintf(stderr, "cwd was not restored: '%s' -> '%s'\n", initial_cwd,
                final_cwd);
        return 1;
    }
    printf("cwd_restored=1\n");
    dlclose(h);
    for (int i = 0; i < padding; ++i) {
        char text[64];
        if (fseek(host_files[i], 0, SEEK_SET) != 0 ||
            !fgets(text, sizeof(text), host_files[i]) ||
            strcmp(text, "host resource guard\n") != 0) {
            fprintf(stderr, "core damaged host file %d\n", i);
            return 1;
        }
    }
    if (padding)
        puts("host_files_preserved=1");
#ifndef _WIN32
    if (fds_before >= 0) {
        int fds_after = count_open_fds();
        if (fds_after != fds_before) {
            fprintf(stderr, "file descriptor count changed: %d -> %d\n",
                    fds_before, fds_after);
            return 1;
        }
        puts("file_descriptors_restored=1");
    }
#endif
    for (int i = 0; i < padding; ++i)
        fclose(host_files[i]);
#ifndef _WIN32
    for (int i = 0; i < 5; ++i) {
        struct sigaction now;
        sigaction(check_signals[i], NULL, &now);
        if (now.sa_handler != saved_signals[i].sa_handler ||
            ((now.sa_flags ^ saved_signals[i].sa_flags) & SA_SIGINFO)) {
            fprintf(stderr, "signal handler not restored: %d\n", check_signals[i]);
            return 1;
        }
    }
    void *probe = reserve_host_range((void *)OBOR_ARENA_BASE_VA,
                                    OBOR_ARENA_MAX_SZ, PROT_NONE);
    if (probe != (void *)OBOR_ARENA_BASE_VA) {
        fprintf(stderr, "arena reservation leaked after dlclose\n");
        return 1;
    }
    munmap(probe, OBOR_ARENA_MAX_SZ);
    puts("handlers_restored=1 arena_released=1");
    if (getenv("OBOR_LIFECYCLE")) {
        unsetenv("OBOR_LIFECYCLE");
        g_nonblack_max = 0; g_audio_energy = 0; g_shutdown = 0;
        g_nsegs = 0; g_var_dirty = 1;
        puts("reloading_module=1");
        return main(argc, argv);
    }
#endif
    return 0;
}
