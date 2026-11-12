/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 *
 * Android's ordinary dlopen always chooses an ASLR address. Engine snapshots
 * contain code/static-data pointers as well as opaque game bytes; guessing
 * which words need relocation corrupts data. Keep the engine ELF in this
 * same installed file, at a page-aligned file offset, and let Android's own
 * linker load it into an exclusively reserved, stable address. No extraction,
 * executable anonymous memory, frontend extension or custom linker is needed.
 */
#include "libretro.h"
#include <android/dlext.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <link.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

static void *engine;
static void *reservation;
static size_t reservation_size;
static bool attempted;
static retro_environment_t environment;
static const uintptr_t image_address = 0x2900000000ULL;
extern "C" const unsigned char obor_android_engine_begin[], obor_android_engine_end[];
static const size_t engine_span = OBOR_ANDROID_ENGINE_SPAN;
struct engine_location { uint64_t offset, length; bool found; };

static int locate_engine(struct dl_phdr_info *info, size_t, void *opaque)
{
    engine_location *where = (engine_location *)opaque;
    uintptr_t begin = (uintptr_t)obor_android_engine_begin;
    uintptr_t end = (uintptr_t)obor_android_engine_end;
    for (unsigned i = 0; i < info->dlpi_phnum; ++i) {
        const ElfW(Phdr) *p = &info->dlpi_phdr[i];
        uintptr_t lo = info->dlpi_addr + p->p_vaddr;
        if (p->p_type == PT_LOAD && begin >= lo && end > begin &&
            begin - lo <= p->p_filesz && end - lo <= p->p_filesz) {
            where->offset = p->p_offset + begin - lo;
            where->length = end - begin;
            where->found = true;
            return 1;
        }
    }
    return 0;
}

static void load_error(const char *detail)
{
    fprintf(stderr, "[AnyBOR] Android engine load failed: %s\n", detail);
    if (environment) {
        struct retro_log_callback log = {};
        if (environment(RETRO_ENVIRONMENT_GET_LOG_INTERFACE, &log) && log.log)
            log.log(RETRO_LOG_ERROR, "[AnyBOR] Android engine load failed: %s\n", detail);
    }
}

static void *load_engine()
{
    if (attempted) return engine;
    attempted = true;
    Dl_info own = {};
    if (!dladdr((void *)&load_engine, &own) || !own.dli_fname) {
        load_error("cannot locate the installed core");
        return NULL;
    }
    int fd = open(own.dli_fname, O_RDONLY | O_CLOEXEC);
    struct stat st = {};
    engine_location payload = {};
    dl_iterate_phdr(locate_engine, &payload);
    bool valid = fd >= 0 && !fstat(fd, &st) && S_ISREG(st.st_mode) &&
        st.st_size > 0 && payload.found && !(payload.offset % 16384) &&
        payload.length >= 64 && payload.offset <= (uint64_t)st.st_size &&
        payload.length <= (uint64_t)st.st_size - payload.offset &&
        engine_span && engine_span <= (64ULL << 20) && !(engine_span % 16384);
    if (!valid) {
        if (fd >= 0) close(fd);
        load_error("invalid embedded engine descriptor");
        return NULL;
    }
    /* A hint may choose another address, but can never replace an existing
     * mapping. Reject a collision without touching the other owner's pages. */
    void *wanted = (void *)image_address;
    void *mapped = mmap(wanted, engine_span, PROT_NONE,
                        MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (mapped != wanted) {
        if (mapped != MAP_FAILED) munmap(mapped, engine_span);
        close(fd);
        load_error("stable engine address is already occupied");
        return NULL;
    }
    android_dlextinfo ext = {};
    ext.flags = ANDROID_DLEXT_RESERVED_ADDRESS | ANDROID_DLEXT_USE_LIBRARY_FD |
                ANDROID_DLEXT_USE_LIBRARY_FD_OFFSET;
    ext.reserved_addr = mapped;
    ext.reserved_size = engine_span;
    ext.library_fd = fd;
    ext.library_fd_offset = (off64_t)payload.offset;
    engine = android_dlopen_ext("anybor-embedded-engine.so", RTLD_NOW | RTLD_LOCAL, &ext);
    if (!engine) {
        load_error(dlerror());
        munmap(mapped, engine_span);
    } else {
        reservation = mapped;
        reservation_size = engine_span;
    }
    close(fd);
    return engine;
}

static void *resolve(const char *name)
{
    void *handle = load_engine();
    return handle ? dlsym(handle, name) : NULL;
}

/* RetroArch also loads/unloads a core solely to read its metadata. Release
 * the engine and its arena on dlclose, even when retro_deinit was not called. */
__attribute__((destructor)) static void unload_engine()
{
    if (engine) dlclose(engine);
    if (reservation) munmap(reservation, reservation_size);
}

#define FORWARD(ret, name, args, call) \
    extern "C" RETRO_API ret name args { \
        static auto fn = (decltype(&name))resolve(#name); \
        if (fn) return fn call; \
        return (ret)0; \
    }

extern "C" RETRO_API void retro_set_environment(retro_environment_t cb)
{
    environment = cb;
    auto fn = (decltype(&retro_set_environment))resolve("retro_set_environment");
    if (fn) fn(cb);
}
extern "C" RETRO_API void retro_get_system_info(struct retro_system_info *info)
{
    auto fn = (decltype(&retro_get_system_info))resolve("retro_get_system_info");
    if (fn) fn(info);
    else {
        memset(info, 0, sizeof(*info));
        info->library_name = "AnyBOR";
        info->library_version = "unavailable";
        info->valid_extensions = "pak";
        info->need_fullpath = true;
    }
}
extern "C" RETRO_API void retro_get_system_av_info(struct retro_system_av_info *info)
{
    auto fn = (decltype(&retro_get_system_av_info))resolve("retro_get_system_av_info");
    memset(info, 0, sizeof(*info));
    if (fn) fn(info);
}
extern "C" RETRO_API unsigned retro_api_version(void) { return RETRO_API_VERSION; }
FORWARD(void, retro_set_video_refresh, (retro_video_refresh_t cb), (cb))
FORWARD(void, retro_set_audio_sample, (retro_audio_sample_t cb), (cb))
FORWARD(void, retro_set_audio_sample_batch, (retro_audio_sample_batch_t cb), (cb))
FORWARD(void, retro_set_input_poll, (retro_input_poll_t cb), (cb))
FORWARD(void, retro_set_input_state, (retro_input_state_t cb), (cb))
FORWARD(void, retro_init, (void), ())
FORWARD(void, retro_deinit, (void), ())
FORWARD(void, retro_set_controller_port_device, (unsigned port, unsigned device), (port, device))
FORWARD(void, retro_reset, (void), ())
FORWARD(void, retro_run, (void), ())
FORWARD(size_t, retro_serialize_size, (void), ())
FORWARD(bool, retro_serialize, (void *data, size_t size), (data, size))
FORWARD(bool, retro_unserialize, (const void *data, size_t size), (data, size))
FORWARD(void, retro_cheat_reset, (void), ())
FORWARD(void, retro_cheat_set, (unsigned index, bool enabled, const char *code), (index, enabled, code))
FORWARD(bool, retro_load_game, (const struct retro_game_info *info), (info))
FORWARD(bool, retro_load_game_special, (unsigned type, const struct retro_game_info *info, size_t n), (type, info, n))
FORWARD(void, retro_unload_game, (void), ())
FORWARD(unsigned, retro_get_region, (void), ())
FORWARD(void *, retro_get_memory_data, (unsigned id), (id))
FORWARD(size_t, retro_get_memory_size, (unsigned id), (id))
/* Optional extension retains its ABI; stock frontends do not call it. */
FORWARD(const void *, retro_anybor_rewind_interface, (uint32_t version, uint32_t size), (version, size))
