/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
/* Exercise the allocator's real dense snapshot branch, including dlmalloc's
 * deliberate undefinition of Windows macros. Testing the helper alone misses
 * a branch which is accidentally compiled out at its call site. */
#include <windows.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned jobs_created;
static unsigned reported_cpus = 4;
static PTP_WORK counted_work(PTP_WORK_CALLBACK callback, void *context,
                            PTP_CALLBACK_ENVIRON environment)
{
    ++jobs_created;
#if defined(OBOR_TEST_POOL_FAILURE)
    (void)callback; (void)context; (void)environment;
    return NULL;
#else
#if defined(OBOR_TEST_POOL_PARTIAL_FAILURE)
    if (jobs_created & 1) return NULL;
#endif
    return CreateThreadpoolWork(callback, context, environment);
#endif
}
static void four_cpus(LPSYSTEM_INFO info)
{
    GetSystemInfo(info);
    info->dwNumberOfProcessors = reported_cpus;
}
#define CreateThreadpoolWork counted_work
#define GetSystemInfo four_cpus
#include "obor_alloc.c"

void obor_state_owned_discard(void) {}
#if OBOR_WRITE_WATCH_ENABLED
int obor_write_watch_stop(void) { return 1; }
void obor_write_watch_abandon(void) {}
#endif
void obor_fault_allocator_activity(int active) { (void)active; }
void obor_fault_abort(uint32_t kind, uintptr_t address)
{ (void)kind; (void)address; abort(); }
void *__real_malloc(size_t n) { return malloc(n); }
void *__real_realloc(void *p, size_t n) { return realloc(p, n); }
void __real_free(void *p) { free(p); }

static void capture(int parallel)
{
    uint64_t extent = 0;
    assert(sparse_use_dense(&extent));
    uint64_t size = obor_heap_sparse_size();
    unsigned char *memory = malloc((size_t)size + 80);
    assert(memory);
    for (unsigned offset = 16; offset < 32; ++offset) {
        memset(memory, 0xa5, (size_t)size + 80);
        unsigned before = jobs_created;
        assert(obor_heap_sparse_write(memory + offset, size) == size);
        if (jobs_created - before != (parallel ? 3u : 0u)) {
            fputs("FAIL dense snapshot did not execute the selected copy route\n", stderr);
            exit(1);
        }
        obor_heap_sparse_header header;
        obor_heap_sparse_span span;
        memcpy(&header, memory + offset, sizeof(header));
        memcpy(&span, memory + offset + sizeof(header), sizeof(span));
        assert(header.count == 1 && header.payload_bytes == extent);
        assert(span.offset == 0 && span.length == extent);
        assert(!memcmp(memory + offset + sizeof(header) + sizeof(span),
                       OBOR_ARENA_BASE + OBOR_STACK_RESERVE, (size_t)extent));
        for (unsigned i = 0; i < offset; ++i) assert(memory[i] == 0xa5);
        for (uint64_t i = size + offset; i < size + 80; ++i)
            assert(memory[i] == 0xa5);
        assert(obor_heap_sparse_validate(memory + offset, size, obor_arena_used()));
    }
    free(memory);
}

static void capture_padded(void)
{
    const size_t gap = 1912, tail = (20u << 20) + 513;
    uint64_t extent = 0;
    assert(sparse_use_dense(&extent));
    size_t size = (size_t)obor_heap_sparse_size();
    unsigned char *memory = malloc(size + gap + tail + 80);
    assert(memory);
    reported_cpus = 8;
    for (unsigned offset = 16; offset < 32; ++offset) {
        memset(memory, 0xa5, size + gap + tail + 80);
        unsigned char *padding = memory + offset + size + gap;
        for (unsigned reuse = 0; reuse < 3; ++reuse) {
            if (reuse) {
                /* Arbitrary caller edits, including the last SIMD/tail byte,
                 * cannot be skipped merely because this buffer was reused. */
                memory[offset + 48 + 511] ^= 0x73;
                memory[offset + size - 1] ^= 0x15;
                padding[tail - 1] = 0x51;
            }
            unsigned before = jobs_created;
            int done = 0;
            assert(obor_heap_sparse_write_padded(memory + offset, size,
                                                 padding, tail, &done) == size);
            assert(done && jobs_created - before == 7);
            assert(!memcmp(memory + offset + 48,
                           OBOR_ARENA_BASE + OBOR_STACK_RESERVE, (size_t)extent));
            for (size_t i = 0; i < tail; ++i) assert(!padding[i]);
            for (size_t i = 0; i < offset; ++i) assert(memory[i] == 0xa5);
            for (size_t i = 0; i < gap; ++i) assert(memory[offset + size + i] == 0xa5);
            for (size_t i = offset + size + gap + tail;
                 i < size + gap + tail + 80; ++i) assert(memory[i] == 0xa5);
            assert(obor_heap_sparse_validate(memory + offset, size, obor_arena_used()));
        }
    }
    /* No writes or jobs may start if the snapshot does not fit. */
    memset(memory, 0xa5, size + gap + tail + 80);
    int done = 0;
    unsigned before = jobs_created;
    assert(!obor_heap_sparse_write_padded(memory + 16, size - 1,
           memory + 16 + size + gap, tail, &done));
    assert(!done && jobs_created == before);
    for (size_t i = 0; i < size + gap + tail + 80; ++i) assert(memory[i] == 0xa5);
    reported_cpus = 4;
    free(memory);
}

static void capture_padded_fallback(void)
{
    const size_t tail = (16u << 20) - 1;
    size_t size = (size_t)obor_heap_sparse_size();
    uint64_t extent = 0;
    assert(sparse_use_dense(&extent));
    unsigned char *memory = malloc(size + tail);
    assert(memory);
    const unsigned cpus[] = {1, 4, 8};
    for (unsigned i = 0; i < sizeof(cpus) / sizeof(cpus[0]); ++i) {
        reported_cpus = cpus[i];
        memset(memory, 0xa5, size + tail);
        unsigned before = jobs_created;
        int done = 0;
        assert(obor_heap_sparse_write_padded(memory, size, memory + size, tail, &done) == size);
        assert(!done && jobs_created - before == (cpus[i] == 1 ? 0u : 3u));
        assert(!memcmp(memory + 48, OBOR_ARENA_BASE + OBOR_STACK_RESERVE, (size_t)extent));
        for (size_t at = 0; at < tail; ++at) assert(memory[size + at] == 0xa5);
    }
    reported_cpus = 4;
    free(memory);
}

int main(void)
{
    void *claim = VirtualAlloc(OBOR_ARENA_BASE, OBOR_ARENA_MAX,
                              MEM_RESERVE | MEM_WRITE_WATCH, PAGE_READWRITE);
    assert(claim == OBOR_ARENA_BASE);
    obor_arena_authorize(1);
    assert(obor_arena_init());
    void *small = __wrap_malloc(1u << 20);
    assert(small);
    memset(small, 0x73, 1u << 20);
    capture(0);
    __wrap_free(small);
    unsigned char *large = __wrap_malloc(40u << 20);
    assert(large);
    uint32_t rng = 43;
    for (size_t i = 0; i < (40u << 20); ++i) {
        rng = rng * 1664525u + 1013904223u;
        large[i] = (unsigned char)(rng >> 24);
    }
    capture(1);
    capture_padded();
    capture_padded_fallback();
    large[17] ^= 0xff;
    capture(1);
    __wrap_free(large);
    obor_arena_release();
    assert(VirtualFree(claim, 0, MEM_RELEASE));
    puts("PASS dense Windows heap: parallel route, exact bytes, dirty reuse, all alignments and guards");
    return 0;
}
