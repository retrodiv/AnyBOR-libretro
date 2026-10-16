/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#define _GNU_SOURCE
#include "obor_fault.h"
#include "obor_write_watch.h"
#include "obor_snapshot_cache.h"
#include "obor_block_state.h"
#include <assert.h>
#include <errno.h>
#include <signal.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

static unsigned char *memory;
static size_t page, extent, maximum;
static size_t first_write, write_count;
static unsigned protect_calls, fail_protect, fail_restore;
static unsigned synthetic_page;
extern int __real_mprotect(void *, size_t, int);
extern long __real_sysconf(int);
long __wrap_sysconf(int name)
{ return name == _SC_PAGESIZE && synthetic_page ? (long)synthetic_page : __real_sysconf(name); }
int __wrap_mprotect(void *p, size_t n, int protection)
{
    ++protect_calls;
    if (protect_calls == fail_protect || protect_calls == fail_restore) {
        /* Model the documented possibility of partially changed permissions. */
        if (n) assert(!__real_mprotect(p, (size_t)__real_sysconf(_SC_PAGESIZE), protection));
        errno = ENOMEM; return -1;
    }
    return __real_mprotect(p, n, protection);
}
static void writes(void *unused)
{
    (void)unused;
    for (size_t i = first_write; i < first_write + write_count; ++i)
        ((volatile unsigned char *)memory)[i * page + 13] ^= 1;
}
static void cpu(size_t first, size_t count)
{
    first_write = first; write_count = count;
    obor_fault fault;
    assert(obor_fault_run(writes, NULL, &fault) == 1);
}
static int clean(size_t offset, size_t length, uint64_t epoch)
{ return obor_write_watch_range_unchanged((uintptr_t)memory + offset, length, epoch); }
static void begin(size_t pages, size_t max_pages)
{
    page = (size_t)__wrap_sysconf(_SC_PAGESIZE);
    extent = pages * page; maximum = max_pages * page;
    /* Also align to synthetic 16/64 KiB pages on a 4 KiB test host. */
    void *whole = mmap(NULL, maximum + page, PROT_READ | PROT_WRITE,
                       MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(whole != MAP_FAILED);
    uintptr_t aligned = ((uintptr_t)whole + page - 1) / page * page;
    size_t head = aligned - (uintptr_t)whole;
    if (head) assert(!munmap(whole, head));
    size_t tail = maximum + page - head - maximum;
    if (tail) assert(!munmap((void *)(aligned + maximum), tail));
    memory = (void *)aligned; memset(memory, 0x37, maximum);
    assert(obor_write_watch_start(memory, extent, maximum));
    assert(obor_write_watch_arm(extent) == 1);
}
static void finish(void)
{
    fail_protect = fail_restore = 0;
    assert(obor_write_watch_stop());
    memset(memory, 0x42, maximum); /* all pages, including former hot, writable */
    assert(!munmap(memory, maximum));
}
static void learn(size_t first, size_t count, int empty_between)
{
    for (unsigned epoch = 0; epoch < 16; ++epoch) {
        cpu(first, count);
        assert(obor_write_watch_arm(extent) == 1);
        if (empty_between) assert(obor_write_watch_arm(extent) == 1);
        if (epoch != 15)
            assert(obor_write_watch_page_epoch(first) != UINT64_MAX);
    }
    assert(obor_write_watch_page_epoch(first) == UINT64_MAX);
    puts("learn_active_epochs=16");
}
static void nothing(void *context, size_t offset, size_t length)
{ (void)context; (void)offset; (void)length; }
typedef struct { unsigned char *out; const unsigned char *source; } patch_context;
static void apply_hint(void *context, size_t offset, size_t length)
{
    patch_context *p = context; assert(offset <= extent && length <= extent - offset);
    memcpy(p->out + offset, p->source + offset, length);
}
static void capture(obor_snapshot_cache *cache, unsigned index,
                    unsigned char *expected, unsigned char *previous)
{
    obor_snapshot_cache prior = *cache;
    obor_snapshot_copy(cache, index, memory, 0, extent, extent, extent, page,
                      obor_write_watch_epoch(), obor_write_watch_page_epoch,
                      nothing, NULL);
    assert(!memcmp(cache->slot[index].buffer, expected, extent));
    patch_context patch = {previous, cache->slot[index].buffer};
    /* As in snapshot_cache_test, replay the emitted ranges against the prior
     * complete state, after this destination has been initialized. */
    obor_snapshot_copy(&prior, index, memory, 0, extent, extent, extent, page,
                      obor_write_watch_epoch(), obor_write_watch_page_epoch,
                      apply_hint, &patch);
    assert(!memcmp(previous, expected, extent));
}
static void same_epoch(void)
{
    begin(4, 8); learn(1, 1, 1);
    obor_snapshot_cache cache = {0};
    cache.slot[0].buffer = calloc(1, extent); cache.slot[1].buffer = calloc(1, extent);
    assert(cache.slot[0].buffer && cache.slot[1].buffer);
    unsigned char *previous = malloc(extent); assert(previous); memset(previous, 0xa5, extent);
    for (unsigned cycle = 0; cycle < 5; ++cycle) {
        uint64_t prior = obor_write_watch_epoch();
        assert(obor_write_watch_arm(extent) == 1);
        assert(!clean(page, page, prior)); /* global last_change shortcut */
        assert(!clean(page - 1, 2, prior));
        assert(!clean(0, extent, prior));
        assert(clean(0, page, prior) && clean(page * 2, page, prior));
        uint64_t same = obor_write_watch_epoch();
        capture(&cache, 0, memory, previous);
        unsigned before_protect = protect_calls;
        cpu(1, 1); /* RW: no fault and no new epoch */
        assert(protect_calls == before_protect);
        assert(obor_write_watch_prepare_io(memory + page + 9, 32));
        assert(protect_calls == before_protect); /* internal hot stamp avoids IO reprotection */
        assert(obor_write_watch_page_epoch(1) == UINT64_MAX);
        capture(&cache, 0, memory, previous); /* same destination AND same epoch */
        cpu(1, 1); capture(&cache, 1, memory, previous);
        cpu(1, 1); capture(&cache, 0, memory, previous);
        assert(obor_write_watch_epoch() == same);
    }
    free(cache.slot[0].buffer); free(cache.slot[1].buffer); free(previous);
    assert(obor_write_watch_stop());
    assert(obor_write_watch_start(memory, extent, maximum));
    assert(obor_write_watch_arm(extent) == 1);
    assert(obor_write_watch_page_epoch(1) != UINT64_MAX); /* session reset */
    finish(); puts("hot_same_epoch_snapshot=1 hot_ranges_never_proven=1 lifetime_reset=1");
}
static void false_learning(void)
{
    begin(4, 8);
    for (unsigned i = 0; i < 40; ++i) {
        assert(obor_write_watch_prepare_io(memory, page));
        memory[13] ^= 1; /* IO-prepared page produces no CPU fault */
        cpu(1 + i % 2, 1); /* alternating CPU pages break each other's streak */
        assert(obor_write_watch_arm(extent) == 1);
        for (unsigned p = 0; p < 4; ++p)
            assert(obor_write_watch_page_epoch(p) != UINT64_MAX);
    }
    assert(obor_write_watch_extend(maximum)); extent = maximum;
    assert(obor_write_watch_arm(extent) == 1); /* new pages were RW until now */
    for (unsigned i = 0; i < 15; ++i) {
        cpu(7, 1); assert(obor_write_watch_arm(extent) == 1);
        assert(obor_write_watch_page_epoch(7) != UINT64_MAX);
    }
    cpu(7, 1); assert(obor_write_watch_arm(extent) == 1);
    assert(obor_write_watch_page_epoch(7) == UINT64_MAX);
    finish(); puts("io_extension_empty_not_learning=1 real_streak_required=1");
}
static void budget(void)
{
    begin(600, 600);
    for (unsigned i = 0; i < 16; ++i) {
        cpu(0, 600); assert(obor_write_watch_arm(extent) == 1);
    }
    size_t hot = 0;
    for (size_t i = 0; i < 600; ++i)
        hot += obor_write_watch_page_epoch(i) == UINT64_MAX;
    size_t expected = (2U << 20) / page;
    if (expected > 512) expected = 512;
    assert(hot == expected && hot * page <= (2U << 20));
    finish(); printf("hot_budget_pages=%zu bytes=%zu page=%zu\n", hot, hot * page, page);
}
static void broken_arm(int fatal)
{
    begin(6, 6); learn(2, 1, 0);
    protect_calls = 0; fail_protect = 2; fail_restore = fatal ? 3 : 0;
    errno = EDOM;
    assert(obor_write_watch_arm(extent) == (fatal ? -1 : 0));
    assert(errno == EDOM);
    assert(!clean(0, extent, 1));
    fail_protect = fail_restore = 0;
    assert(obor_write_watch_stop()); /* restores even failed partial mapping */
    memset(memory, 0x42, maximum);
    assert(obor_write_watch_start(memory, extent, maximum));
    assert(obor_write_watch_arm(extent) == 1);
    assert(obor_write_watch_page_epoch(2) != UINT64_MAX);
    finish(); puts("partial_rearm_fail_closed=1 errno_preserved=1");
}
static const void *source_read(void *ctx, uint32_t offset, uint32_t length, void *scratch)
{ (void)ctx; (void)scratch; assert(offset <= extent && length <= extent - offset); return memory + offset; }
static uint64_t source_epoch;
static int source_clean(void *ctx, uint32_t offset, uint32_t length)
{ (void)ctx; return clean(offset, length, source_epoch); }
static void blocks(int helper)
{
    begin(768, 768); /* 3 MiB on 4K: middle of a 64-block proof group. */
    size_t hot = (OBOR_BLOCK_STATE_BLOCK * 31 + 4096) / page;
    learn(hot, 1, 1);
    obor_block_allocator allocator = {.calloc=calloc, .realloc=realloc, .free=free};
    obor_block_state *encoder = obor_block_state_create(&allocator);
    obor_block_state *decoder = obor_block_state_create(&allocator);
    assert(encoder && decoder);
    obor_block_state_set_worker(encoder, helper);
    obor_block_source source = {NULL, source_read, source_clean};
    unsigned char *saved[4], *expected[4]; uint32_t sizes[4];
    obor_block_state *serial = obor_block_state_create(&allocator); assert(serial);
    unsigned actual_helpers = 0;
    for (unsigned i = 0; i < 4; ++i) {
        if (i == 2) assert(obor_write_watch_arm(extent) == 1);
        cpu(hot, 1);
        if (i == 1 || i == 3) cpu(0, 256); /* >32 changed blocks: a real helper batch */
        expected[i] = malloc(extent); assert(expected[i]); memcpy(expected[i], memory, extent);
        assert(obor_block_state_encode_fast(encoder, &source, (uint32_t)extent));
        obor_block_changes changes; obor_block_state_changes(encoder, &changes);
        actual_helpers += changes.worker_threads;
        assert(obor_block_state_encode_fast(serial, &source, (uint32_t)extent));
        uint32_t serial_size;
        const void *serial_image = obor_block_state_image(serial, &serial_size);
        const void *image = obor_block_state_image(encoder, &sizes[i]);
        assert(serial_size == sizes[i] && !memcmp(serial_image, image, sizes[i]));
        assert(image && (saved[i] = malloc(sizes[i]))); memcpy(saved[i], image, sizes[i]);
        assert(obor_block_state_decode(decoder, saved[i], sizes[i]));
        uint32_t length; const void *raw = obor_block_state_raw(decoder, &length);
        assert(length == extent && !memcmp(raw, memory, length));
        source_epoch = obor_write_watch_epoch();
    }
    if (helper) assert(actual_helpers > 0);
    for (unsigned at = 4; at > 0; --at) {
        unsigned i = at - 1;
        obor_block_state_forget(decoder);
        assert(obor_block_state_decode(decoder, saved[i], sizes[i]));
        uint32_t length; const void *raw = obor_block_state_raw(decoder, &length);
        assert(length == extent && !memcmp(raw, expected[i], length));
        free(saved[i]); free(expected[i]);
    }
    obor_block_state_destroy(serial);
    obor_block_state_destroy(encoder); obor_block_state_destroy(decoder);
    finish(); printf("hot_group64_middle=1 cold_independent=4 same_epoch_encoder=1 actual_helpers=%u\n", actual_helpers);
}
static void disabled(void)
{
    assert(!setenv("OBOR_STATE_HOT_PAGES", "0", 1));
    begin(4, 4);
    for (unsigned i = 0; i < 40; ++i) {
        cpu(1, 1); assert(obor_write_watch_arm(extent) == 1);
        assert(obor_write_watch_page_epoch(1) != UINT64_MAX);
    }
    finish(); puts("hot_disabled_keeps_signal_tracking=1");
}
static void *worker_write(void *arg)
{
    obor_fault_worker_enter();
    size_t index = (size_t)(uintptr_t)arg;
    ((volatile unsigned char *)memory)[index * page + 13] ^= 1;
    obor_fault_worker_leave(); return NULL;
}
static void leased_writes(void *unused)
{
    (void)unused; pthread_t threads[2];
    for (size_t i = 0; i < 2; ++i) {
        assert(obor_fault_worker_acquire());
        assert(!pthread_create(&threads[i], NULL, worker_write, (void *)(uintptr_t)(i + 1)));
    }
    assert(!obor_write_watch_arm(extent));
    assert(!obor_write_watch_extend(maximum));
    assert(!obor_write_watch_stop());
    assert(!clean(0, extent, 1));
    for (unsigned i = 0; i < 2; ++i) {
        assert(!pthread_join(threads[i], NULL)); obor_fault_worker_release();
    }
}
static void workers(void)
{
    begin(4, 8);
    for (unsigned i = 0; i < 20; ++i) {
        obor_fault fault;
        assert(obor_fault_run(leased_writes, NULL, &fault) == 1);
        assert(obor_write_watch_arm(extent) == 1);
        if (i < 15) assert(obor_write_watch_page_epoch(1) != UINT64_MAX);
        else assert(obor_write_watch_page_epoch(1) == UINT64_MAX &&
                    obor_write_watch_page_epoch(2) == UINT64_MAX);
    }
    assert(!obor_fault_worker_leases()); finish();
    puts("real_worker_cpu_learning=1 lease_blocks_rearm_extend_stop=1 joined=40");
}
static void abandoned(void)
{
    begin(4, 4); learn(1, 1, 1);
    assert(!munmap(memory, maximum));
    unsigned before = protect_calls;
    obor_write_watch_abandon(); assert(protect_calls == before);
    assert(!obor_write_watch_epoch() && obor_write_watch_page_epoch(1) == UINT64_MAX);
    begin(4, 4); assert(obor_write_watch_page_epoch(1) != UINT64_MAX);
    finish(); puts("abandon_discards_selection_without_accessing_old_arena=1");
}
int main(int argc, char **argv)
{
    assert(argc == 2); assert(!setenv("OBOR_STATE_HOT_PAGES", "1", 1));
    if (!strcmp(argv[1], "same-epoch")) same_epoch();
    else if (!strcmp(argv[1], "false-learning")) false_learning();
    else if (!strcmp(argv[1], "budget4")) { synthetic_page = 4096; budget(); }
    else if (!strcmp(argv[1], "budget16")) { synthetic_page = 16384; budget(); }
    else if (!strcmp(argv[1], "budget64")) { synthetic_page = 65536; budget(); }
    else if (!strcmp(argv[1], "partial")) broken_arm(0);
    else if (!strcmp(argv[1], "fatal")) broken_arm(1);
    else if (!strcmp(argv[1], "blocks")) blocks(0);
    else if (!strcmp(argv[1], "helper")) blocks(1);
    else if (!strcmp(argv[1], "disabled")) disabled();
    else if (!strcmp(argv[1], "workers")) workers();
    else if (!strcmp(argv[1], "abandon")) abandoned();
    else return 2;
    return 0;
}
