/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include "obor_write_watch.h"
#include "obor_fault.h"

#if OBOR_WRITE_WATCH_ENABLED
#include "obor_abi.h"
#include "obor_runtime.h"
#include "obor_state_config.h"
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <sys/mman.h>
#include <unistd.h>

/* Learning is a cost policy only. Always-writable pages remain unconditionally
 * dirty to every proof consumer. No snapshot format or engine data changes. */
#ifndef OBOR_WRITE_WATCH_HOT_DEFAULT
#define OBOR_WRITE_WATCH_HOT_DEFAULT 1
#endif
#define HOT_ACTIVE_EPOCHS 16U
#define HOT_MAX_PAGES 512U
#define HOT_MAX_BYTES (2U << 20)

typedef struct {
    uintptr_t base;
    size_t extent, protected_length, maximum, page_size, mapping_size;
    uint64_t epoch, last_change;
    uint64_t *cpu_writes;
    unsigned char *streak, *hot;
    size_t cpu_words, hot_count, hot_limit;
    int hot_enabled;
    volatile sig_atomic_t armed;
    uint64_t changed[];
} write_watch;

/* Neither this pointer nor its anonymous metadata mapping is a part of a
 * savestate. The allocator never places bookkeeping in the snapshot arena. */
static write_watch *watch OBOR_RUNTIME;

int obor_write_watch_start(void *base, size_t length, size_t maximum)
{
    if (watch || obor_fault_worker_leases()) return 0;
    _Static_assert(__atomic_always_lock_free(sizeof(uint64_t), 0),
                   "Signal write tracking requires lock-free page epochs");
    long page = sysconf(_SC_PAGESIZE);
    if (page <= 0 || ((size_t)page & ((size_t)page - 1)) || !length ||
        length > maximum || maximum > OBOR_ARENA_MAX_SZ - (16UL << 20) ||
        (uintptr_t)base % (size_t)page || length % (size_t)page ||
        maximum % (size_t)page || (uintptr_t)base > UINTPTR_MAX - maximum)
        return 0;
#ifndef OBOR_WRITE_WATCH_TEST
    if ((uintptr_t)base != OBOR_ARENA_BASE_VA + (16UL << 20)) return 0;
#endif
    size_t pages = maximum / (size_t)page;
    if (pages > (SIZE_MAX - sizeof(write_watch)) / sizeof(uint64_t)) return 0;
    size_t bytes = sizeof(write_watch) + pages * sizeof(uint64_t);
    size_t words = (pages + 63) / 64;
    int hot_enabled = obor_state_option("OBOR_STATE_HOT_PAGES", OBOR_WRITE_WATCH_HOT_DEFAULT);
    if (hot_enabled) {
        if (words > (SIZE_MAX - bytes) / sizeof(uint64_t)) return 0;
        bytes += words * sizeof(uint64_t);
        if (pages > (SIZE_MAX - bytes) / 2) return 0;
        bytes += pages * 2;
    }
    write_watch *created = mmap(NULL, bytes, PROT_READ | PROT_WRITE,
                               MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (created == MAP_FAILED) return 0;
    created->base = (uintptr_t)base;
    created->extent = length;
    created->maximum = maximum;
    created->page_size = (size_t)page;
    created->mapping_size = bytes;
    created->hot_enabled = hot_enabled;
    if (hot_enabled) {
        created->cpu_words = words;
        created->cpu_writes = created->changed + pages;
        created->streak = (unsigned char *)(created->cpu_writes + words);
        created->hot = created->streak + pages;
        created->hot_limit = HOT_MAX_BYTES / (size_t)page;
        if (created->hot_limit > HOT_MAX_PAGES) created->hot_limit = HOT_MAX_PAGES;
    }
    created->epoch = 1;
    created->last_change = 1;
    watch = created;
    return 1;
}

int obor_write_watch_extend(size_t length)
{
    write_watch *w = watch;
    if (!w || obor_fault_worker_leases() || length < w->extent || length > w->maximum ||
        length % w->page_size) return 0;
    /* Newly allocated pages were writable before the next protection pass.
     * Conservatively include all their bytes, even without a CPU fault. */
    for (size_t i = w->extent / w->page_size; i < length / w->page_size; ++i)
        __atomic_store_n(&w->changed[i], w->epoch, __ATOMIC_RELEASE);
    if (length > w->extent)
        __atomic_store_n(&w->last_change, w->epoch, __ATOMIC_RELEASE);
    w->extent = length;
    return 1;
}

/* Called only by the parked owner, without worker leases. Empty protection
 * epochs between preparation and serialization do not invent observations.
 * Extension/IO marks never set cpu_writes and cannot cause promotion. */
static void learn_hot(write_watch *w)
{
    if (!w->hot_enabled) return;
    size_t pages = w->extent / w->page_size;
    int active = 0;
    for (size_t i = 0; i < w->cpu_words; ++i)
        active |= __atomic_load_n(&w->cpu_writes[i], __ATOMIC_ACQUIRE) != 0;
    if (!active) return;
    for (size_t i = 0; i < pages; ++i) {
        if (w->hot[i]) continue;
        uint64_t bits = __atomic_load_n(&w->cpu_writes[i / 64], __ATOMIC_ACQUIRE);
        if (bits & (UINT64_C(1) << (i % 64))) {
            if (w->streak[i] < HOT_ACTIVE_EPOCHS) ++w->streak[i];
            if (w->streak[i] == HOT_ACTIVE_EPOCHS && w->hot_count < w->hot_limit) {
                w->hot[i] = 1;
                ++w->hot_count;
            }
        } else w->streak[i] = 0;
    }
    memset(w->cpu_writes, 0, w->cpu_words * sizeof(uint64_t));
}

/* Leave promoted pages RW; protect only the contiguous cold complements.
 * A partial failure is recovered by the same whole-range RW fallback as the
 * ordinary watcher. The selection has no bearing on saved content. */
static int protect_cold(write_watch *w, size_t length)
{
    if (!w->hot_count) return mprotect((void *)w->base, length, PROT_READ) == 0;
    size_t pages = length / w->page_size;
    for (size_t i = 0; i < pages;) {
        if (w->hot[i]) { ++i; continue; }
        size_t first = i++;
        while (i < pages && !w->hot[i]) ++i;
        if (mprotect((void *)(w->base + first * w->page_size),
                     (i - first) * w->page_size, PROT_READ)) return 0;
    }
    return 1;
}

int obor_write_watch_arm(size_t length)
{
    write_watch *w = watch;
    /* UINT64_MAX is reserved for a page that can never be proven unchanged. */
    if (!w || w->epoch >= UINT64_MAX - 1 || !obor_write_watch_extend(length)) return 0;
    int saved_errno = errno;
    learn_hot(w);
    if (!protect_cold(w, length)) {
        /* mprotect failures can leave a partially modified mapping. Restore
         * write access before allowing an ordinary-serializer fallback. */
        int restored = mprotect((void *)w->base, length, PROT_READ | PROT_WRITE) == 0;
        w->armed = 0;
        w->protected_length = restored ? 0 : length;
        errno = saved_errno;
        return restored ? 0 : -1;
    }
    w->protected_length = length;
    ++w->epoch;
    if (w->hot_count) {
        for (size_t i = 0; i < length / w->page_size; ++i)
            if (w->hot[i]) __atomic_store_n(&w->changed[i], w->epoch, __ATOMIC_RELEASE);
        __atomic_store_n(&w->last_change, w->epoch, __ATOMIC_RELEASE);
    }
    w->armed = 1;
    errno = saved_errno;
    return 1;
}

int obor_write_watch_stop(void)
{
    write_watch *w = watch;
    if (obor_fault_worker_leases()) return 0;
    if (!w) return 1;
    int saved_errno = errno;
    if (w->protected_length &&
        mprotect((void *)w->base, w->protected_length, PROT_READ | PROT_WRITE)) {
        errno = saved_errno;
        return 0; /* keep metadata alive until the caller handles the error */
    }
    w->armed = 0;
    watch = NULL;
    munmap(w, w->mapping_size);
    errno = saved_errno;
    return 1;
}

int obor_write_watch_fault(uintptr_t address)
{
    write_watch *w = watch;
    if (!w || !w->armed || address < w->base ||
        address - w->base >= w->protected_length) return 0;
    size_t index = (address - w->base) / w->page_size;
    /* Two workers can fault on this page before either mprotect completes.
     * Both may retry the write, even if the other already marked it. Calling
     * mprotect again is safe and needs no signal-handler lock or spin loop. */
    int saved_errno = errno;
    int result = mprotect((void *)(w->base + index * w->page_size),
                          w->page_size, PROT_READ | PROT_WRITE);
    if (!result) {
        __atomic_store_n(&w->changed[index], w->epoch, __ATOMIC_RELEASE);
        /* All leased workers share this generation; captures and rearming
         * are refused until they join. No signal-handler lock is needed. */
        __atomic_store_n(&w->last_change, w->epoch, __ATOMIC_RELEASE);
    }
    errno = saved_errno;
    return result == 0;
}

int obor_write_watch_cpu_fault(uintptr_t address)
{
    if (!obor_write_watch_fault(address)) return 0;
    write_watch *w = watch;
    if (w->hot_enabled) {
        size_t page = (address - w->base) / w->page_size;
        __atomic_fetch_or(&w->cpu_writes[page / 64],
                          UINT64_C(1) << (page % 64), __ATOMIC_RELEASE);
    }
    return 1;
}

void obor_write_watch_abandon(void)
{
    if (obor_fault_worker_leases()) obor_fault_abort(OBOR_FAULT_STATE, 0);
    write_watch *w = watch;
    if (!w) return;
    watch = NULL;
    munmap(w, w->mapping_size);
}

int obor_write_watch_prepare_io(void *buffer, size_t length)
{
    write_watch *w = watch;
    if (!w || !w->armed || !length) return 1;
    uintptr_t begin = (uintptr_t)buffer;
    uintptr_t end = length > UINTPTR_MAX - begin ? UINTPTR_MAX : begin + length;
    uintptr_t limit = w->base + w->protected_length;
    if (end <= w->base || begin >= limit) return 1;
    if (begin < w->base) begin = w->base;
    if (end > limit) end = limit;
    size_t first = (begin - w->base) / w->page_size;
    size_t last = (end - 1 - w->base) / w->page_size;
    for (size_t i = first; i <= last; ++i)
        if (__atomic_load_n(&w->changed[i], __ATOMIC_ACQUIRE) != w->epoch &&
            !obor_write_watch_fault(w->base + i * w->page_size)) return 0;
    return 1;
}

uint64_t obor_write_watch_epoch(void) { return watch ? watch->epoch : 0; }
uint64_t obor_write_watch_page_epoch(size_t page)
{
    write_watch *w = watch;
    /* Unlike epoch-only stamps, this also invalidates a snapshot slot reused
     * after an untrapped write in the SAME epoch. */
    if (!w || !w->armed || page >= w->extent / w->page_size ||
        (w->hot_count && w->hot[page])) return UINT64_MAX;
    return __atomic_load_n(&w->changed[page], __ATOMIC_ACQUIRE);
}
int obor_write_watch_range_unchanged(uintptr_t begin, size_t length, uint64_t since)
{
    write_watch *w = watch;
    if (!w || !w->armed || obor_fault_worker_leases() || !since ||
        since >= w->epoch || !length || begin < w->base ||
        begin - w->base >= w->extent || length > w->extent - (begin - w->base))
        return 0;
    if (__atomic_load_n(&w->last_change, __ATOMIC_ACQUIRE) <= since) return 1;
    size_t first = (begin - w->base) / w->page_size;
    size_t last = (begin - w->base + length - 1) / w->page_size;
    for (size_t i = first; i <= last; ++i)
        if (__atomic_load_n(&w->changed[i], __ATOMIC_ACQUIRE) > since) return 0;
    return 1;
}
size_t obor_write_watch_page_size(void) { return watch ? watch->page_size : 0; }
#endif

#if defined(__linux__) || (defined(__APPLE__) && OBOR_WRITE_WATCH_ENABLED)
#include <stdio.h>
#include <unistd.h>
#if defined(__APPLE__)
#include <dlfcn.h>
#include "obor_native_io.h"
/* These interposers are localized with their engine by the Mach-O rewriter.
 * Forward through the actual SDK ABI; cache only process-local addresses. */
ssize_t __real_read(int fd, void *buffer, size_t count)
{
    OBOR_DARWIN_NATIVE(__real_read, OBOR_NATIVE_IO_READ);
    if (!original) { errno = ENOSYS; return -1; }
    return original(fd, buffer, count);
}
size_t __real_fread(void *buffer, size_t size, size_t count, FILE *stream)
{
    OBOR_DARWIN_NATIVE(__real_fread, OBOR_NATIVE_IO_FREAD);
    if (!original) { errno = ENOSYS; return 0; }
    return original(buffer, size, count, stream);
}
#else
extern ssize_t __real_read(int, void *, size_t);
extern size_t __real_fread(void *, size_t, size_t, FILE *);
#endif

/* Kernel writes return EFAULT instead of invoking the CPU signal handler.
 * Pre-mark exactly the intersecting pages; preserve ordinary libc behavior. */
ssize_t __wrap_read(int fd, void *buffer, size_t count)
{
    if (!obor_write_watch_prepare_io(buffer, count))
        obor_fault_abort(OBOR_FAULT_MEMORY, (uintptr_t)buffer);
    return __real_read(fd, buffer, count);
}

size_t __wrap_fread(void *buffer, size_t size, size_t count, FILE *stream)
{
    if (size && count <= SIZE_MAX / size &&
        !obor_write_watch_prepare_io(buffer, size * count))
        obor_fault_abort(OBOR_FAULT_MEMORY, (uintptr_t)buffer);
    return __real_fread(buffer, size, count, stream);
}
#if defined(__APPLE__)
ssize_t read(int fd, void *buffer, size_t count)
{ return __wrap_read(fd, buffer, count); }
size_t fread(void *buffer, size_t size, size_t count, FILE *stream)
{ return __wrap_fread(buffer, size, count, stream); }
#endif
#endif
