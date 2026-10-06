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
#include <errno.h>
#include <signal.h>
#include <sys/mman.h>
#include <unistd.h>

typedef struct {
    uintptr_t base;
    size_t extent, protected_length, maximum, page_size, mapping_size;
    uint64_t epoch;
    volatile sig_atomic_t armed;
    volatile uint64_t changed[];
} write_watch;

/* Neither this pointer nor its anonymous metadata mapping is a part of a
 * savestate. The allocator never places bookkeeping in the snapshot arena. */
static write_watch *watch OBOR_RUNTIME;

int obor_write_watch_start(void *base, size_t length, size_t maximum)
{
    if (watch) return 0;
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
    write_watch *created = mmap(NULL, bytes, PROT_READ | PROT_WRITE,
                               MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (created == MAP_FAILED) return 0;
    created->base = (uintptr_t)base;
    created->extent = length;
    created->maximum = maximum;
    created->page_size = (size_t)page;
    created->mapping_size = bytes;
    created->epoch = 1;
    watch = created;
    return 1;
}

int obor_write_watch_extend(size_t length)
{
    write_watch *w = watch;
    if (!w || length < w->extent || length > w->maximum ||
        length % w->page_size) return 0;
    /* Newly allocated pages were writable before the next protection pass.
     * Conservatively include all their bytes, even without a CPU fault. */
    for (size_t i = w->extent / w->page_size; i < length / w->page_size; ++i)
        w->changed[i] = w->epoch;
    w->extent = length;
    return 1;
}

int obor_write_watch_arm(size_t length)
{
    write_watch *w = watch;
    if (!w || w->epoch == UINT64_MAX || !obor_write_watch_extend(length)) return 0;
    int saved_errno = errno;
    if (mprotect((void *)w->base, length, PROT_READ)) {
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
    w->armed = 1;
    errno = saved_errno;
    return 1;
}

int obor_write_watch_stop(void)
{
    write_watch *w = watch;
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
    if (w->changed[index] == w->epoch) return 0;
    int saved_errno = errno;
    int result = mprotect((void *)(w->base + index * w->page_size),
                          w->page_size, PROT_READ | PROT_WRITE);
    if (!result) w->changed[index] = w->epoch;
    errno = saved_errno;
    return result == 0;
}

void obor_write_watch_abandon(void)
{
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
        if (w->changed[i] != w->epoch &&
            !obor_write_watch_fault(w->base + i * w->page_size)) return 0;
    return 1;
}

uint64_t obor_write_watch_epoch(void) { return watch ? watch->epoch : 0; }
uint64_t obor_write_watch_page_epoch(size_t page)
{
    return watch && page < watch->extent / watch->page_size ?
        watch->changed[page] : UINT64_MAX;
}
size_t obor_write_watch_page_size(void) { return watch ? watch->page_size : 0; }
#endif

#ifdef __linux__
#include <stdio.h>
#include <unistd.h>
extern ssize_t __real_read(int, void *, size_t);
extern size_t __real_fread(void *, size_t, size_t, FILE *);

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
#endif
