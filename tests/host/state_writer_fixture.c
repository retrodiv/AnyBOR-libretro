/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
/* The test driver extracts the production writers into state_writers.inc.
 * This fixture supplies identical memory and metadata to both revisions.
 * It does not run a game or weaken the real core's build-identity guard. */
#define _GNU_SOURCE 1
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "obor_state_copy.h"
#include "obor_state_padding.h"
#include "obor_resources.h"
#include "obor_state_layout.h"
#define OBOR_SHA256_STREAM_ONLY
#include "obor_sha256.h"
#if defined(_WIN32)
#include <windows.h>
#else
#include <sys/mman.h>
#endif
/* Exercise the other platform policy without pretending to run its ABI. */
#if defined(OBOR_FIXTURE_OTHER_POLICY)
#if defined(__linux__)
#define OBOR_FIXTURE_WAS_LINUX 1
#undef __linux__
#endif
#if defined(_WIN32)
#define OBOR_FIXTURE_WAS_WINDOWS 1
#undef _WIN32
#endif
#endif
#include "obor_state_config.h"
#ifdef OBOR_FIXTURE_WAS_LINUX
#define __linux__ 1
#endif
#ifdef OBOR_FIXTURE_WAS_WINDOWS
#define _WIN32 1
#endif
#ifdef OBOR_STATE_CONTENT_DEFAULT
obor_state_settings obor_state_session_settings;
#endif
#define OBOR_RUNTIME
#define OBOR_WRITE_WATCH_ENABLED 0
#define OBOR_ENGINE_BUILD 4432
#define OBOR_ARENA_MAX_SZ (1536U << 20)
#define OBOR_ARENA_BASE_VA UINT64_C(0x600000000)
#define MAX_SEGS 16
#define OBS_MAGIC UINT32_C(0x3153424f)
#define OBS_VERSION 7U
#define OBS_RESOURCE_VERSION 8U
#define OBS_STABLE_RESOURCE_VERSION 9U
#define OBS_ALIGNED_RESOURCE_VERSION 10U
#define OBOR_STACK_BUDGET OBOR_STATE_STACK_WINDOW
#if defined(__aarch64__) || defined(__arm__)
#define OBOR_STACK_HEAD 16384U
#else
#define OBOR_STACK_HEAD 4096U
#endif
#define __real_calloc calloc
#define __real_realloc realloc
#define __real_free free
typedef struct { uint32_t count; } obor_state_ranges;
typedef struct { uint64_t vaddr, size; } seg_t;
static seg_t g_segs[MAX_SEGS];
static int g_nsegs = 1, obor_live_threads;
static uint64_t g_image_lo, g_image_hi, g_boot_id = UINT64_C(0x123456789abcdef0);
static uint32_t g_profile_build = 4432;
static uint8_t g_state_build_identity[32];
static unsigned char *arena;
enum { STACK_BYTES = 32768, HEAP_BYTES = 262144, ARENA_BYTES = STACK_BYTES + HEAP_BYTES + 1024 };
static int collect_segments(void) { return 1; }
static void ensure_boot_id(void) {}
static uint64_t state_timing_now(void) { return 0; }
static void *obor_stack_ptr(void) { return arena; }
static size_t obor_stack_size(void) { return STACK_BYTES; }
static void *obor_engine_sp(void) { return arena + STACK_BYTES - 256; }
static void *obor_arena_base(void) { return arena; }
static size_t obor_arena_used(void) { return STACK_BYTES + HEAP_BYTES; }
static uint64_t heap_lo(void) { return (uintptr_t)(arena + STACK_BYTES); }
static uint64_t heap_used(void) { return HEAP_BYTES; }
static uint64_t segs_bytes(void) { return 1024; }
static void obor_arena_stats(size_t *a, size_t *b, size_t *c) { *a = HEAP_BYTES; *b = *c = 0; }
static void peak_update(uint64_t bytes) { (void)bytes; }
static void obor_test_fault_phase(const char *phase) { (void)phase; }
static int owned_stop_images(void) { return 1; }
static void owned_full_range(obor_state_ranges *r, uint32_t size) { (void)r; (void)size; }
#define OBOR_FAULT_MEMORY 1
static void obor_fault_abort(int why, int value) { (void)why; (void)value; abort(); }
static uint64_t obor_heap_sparse_size(void) { return 48 + HEAP_BYTES; }
static int obor_heap_owned_layout(uint64_t *a, uint64_t *b, uint64_t *c)
{ *a = *b = HEAP_BYTES; *c = 0; return 1; }
static uint64_t obor_heap_sparse_write(void *out, uint64_t capacity)
{
    uint32_t words[4] = {0x3153484f, 2, 1, 0};
    uint64_t fields[4] = {STACK_BYTES + HEAP_BYTES, HEAP_BYTES, 0, HEAP_BYTES};
    assert(capacity >= obor_heap_sparse_size());
    memcpy(out, words, sizeof(words)); memcpy((char *)out + 16, fields, sizeof(fields));
    obor_state_copy_heap((char *)out + 48, arena + STACK_BYTES, HEAP_BYTES);
    return obor_heap_sparse_size();
}
#if defined(_WIN32)
static uint64_t obor_heap_sparse_write_padded(void *out, uint64_t capacity,
        void *padding, size_t size, int *done)
{
    uint64_t used = obor_heap_sparse_write(out, capacity);
    obor_state_clear_padding(padding, size); *done = 1; return used;
}
int obor_dirty_reset(void) { return 0; }
int obor_dirty_scan(size_t offset, size_t length,
        void (*callback)(size_t, size_t, void *), void *context)
{ (void)offset; (void)length; (void)callback; (void)context; return 0; }
#endif
/* A fixed empty catalog exercises the actual Smart stream layout. Catalog
 * proof/reconstruction and real-game resource bodies are tested separately. */
obor_resource_catalog *obor_resources_catalog(void)
{ return obor_state_resources_enabled() ? (obor_resource_catalog *)arena : NULL; }
static void obor_video_prepare_state(void) {}
int obor_resource_catalog_prepare(obor_resource_catalog *c, uint32_t used,
        obor_resource_unchanged f, void *context)
{ (void)c; (void)used; (void)f; (void)context; return 1; }
const void *obor_resource_catalog_manifest(const obor_resource_catalog *c, uint32_t *size)
{
    static const uint32_t manifest[8] = {OBOR_RESOURCE_MANIFEST_MAGIC, 1, 0, 0, 32, 0, 0, 0};
    (void)c; *size = sizeof(manifest); return manifest;
}
uint64_t obor_resource_catalog_generation(const obor_resource_catalog *c) { (void)c; return 1; }
int obor_resource_catalog_read(const obor_resource_catalog *c, uint32_t offset, void *out, uint32_t n)
{ (void)c; assert(offset <= ARENA_BYTES && n <= ARENA_BYTES-offset); memcpy(out, arena+offset, n); return 1; }
int obor_resource_catalog_manifest_unchanged(const obor_resource_catalog *c, uint64_t g, uint32_t o, uint32_t n)
{ (void)c; (void)g; (void)o; (void)n; return 0; }
int obor_resource_catalog_mask_unchanged(const obor_resource_catalog *c, const obor_resource_mask_range *p,
        uint32_t count, uint32_t o, uint32_t n)
{ (void)c; (void)p; (void)count; (void)o; (void)n; return 0; }
uint32_t obor_resource_catalog_mask_count(const obor_resource_catalog *c) { (void)c; return 0; }
int obor_resource_catalog_copy_mask(const obor_resource_catalog *c, obor_resource_mask_range *p, uint32_t n)
{ (void)c; (void)p; (void)n; return 1; }

#include "state_writers.inc"

int main(int argc, char **argv)
{
    assert(argc == 2);
#if defined(_WIN32)
    arena = VirtualAlloc((void *)(uintptr_t)OBOR_ARENA_BASE_VA, ARENA_BYTES,
                         MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
#else
    arena = mmap((void *)(uintptr_t)OBOR_ARENA_BASE_VA, ARENA_BYTES,
                 PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
#endif
    assert((uintptr_t)arena == OBOR_ARENA_BASE_VA);
    for (size_t i=0; i<ARENA_BYTES; ++i) arena[i] = (unsigned char)((i/31 + i/8192) % 17);
    for (size_t i=0; i<32; ++i) g_state_build_identity[i] = (uint8_t)(i+1);
    g_segs[0] = (seg_t){(uintptr_t)(arena + STACK_BYTES + HEAP_BYTES), 1024};
    g_image_lo = OBOR_ARENA_BASE_VA; g_image_hi = g_image_lo + ARENA_BYTES;
#ifdef OBOR_STATE_CONTENT_DEFAULT
    if (!strcmp(argv[1], "explicit")) {
        obor_state_session_settings.content = obor_state_session_settings.compression =
            OBOR_STATE_SETTING_ON;
    } else if (!strcmp(argv[1], "legacy")) {
        /* Preserve the independent legacy writer oracle after the intentional
         * default change. Optional encoder policies still use this old flag. */
        obor_state_session_settings.content = obor_state_session_settings.compression =
            OBOR_STATE_DEFAULT_ENABLED ? OBOR_STATE_SETTING_ON : OBOR_STATE_SETTING_OFF;
    } else assert(!strcmp(argv[1], "default"));
#else
    assert(!strcmp(argv[1], "default"));
#endif
    size_t capacity = 64U << 20;
    unsigned char *output = malloc(capacity); assert(output);
    for (unsigned capture=0; capture<4; ++capture) {
        if (capture == 1 || capture == 3) arena[STACK_BYTES + 17321] ^= 0x31;
        memset(output, 0xa5, capacity);
        int padding_done = 0;
        uint32_t used = coded_requested() ? serialize_coded(output, (uint32_t)capacity) :
            serialize_impl(output, (uint32_t)capacity, NULL, &padding_done);
        assert(used && used <= capacity);
        if (!padding_done) obor_state_clear_padding(output + used, capacity - used);
        obor_sha256_ctx hash; uint8_t digest[32];
        obor_sha256_init(&hash); obor_sha256_update(&hash, output, capacity); obor_sha256_final(&hash, digest);
        printf("capture=%u coded=%d resources=%d used=%u sha256=", capture,
               coded_requested(), obor_state_resources_enabled(), used);
        for (unsigned n=0; n<32; ++n) printf("%02x", digest[n]);
        puts("");
    }
    obor_state_coded_discard(); free(output);
    return 0;
}
