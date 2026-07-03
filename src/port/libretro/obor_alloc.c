/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/*
 * AnyBOR snapshot arena.
 *
 * The runtime links with -Wl,--wrap=malloc/calloc/realloc/free/strdup, so
 * EVERY allocation made by engine code, the static libs (libpng, libvorbis)
 * and libco lands here: a contiguous heap at a fixed virtual address, grown
 * sbrk-style by dlmalloc through obor_morecore(). Save states retain every
 * live chunk plus the allocator metadata needed to recreate free chunks,
 * together with the module's writable segments. Unused bytes inside free
 * chunks are omitted.
 *
 * Foreign pointers (allocated by libc internals before/outside the wrap,
 * e.g. FILE buffers) are recognised by address range and passed through to
 * the real libc functions.
 */
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "obor_abi.h" /* OBOR_ARENA_BASE_VA / OBOR_ARENA_MAX_SZ */
#if defined(__linux__) && defined(__x86_64__) && !defined(__ANDROID__)
#define OBOR_BATCH_SPARSE_SPANS 1
#include "obor_state_copy.h"
#else
#define OBOR_BATCH_SPARSE_SPANS 0
#endif

#if defined(_WIN32)
#include <windows.h>
#else
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#endif

/* ~2.6 TB: far above image bases, libc heaps and mmap regions on both
 * Linux and Windows, but BELOW 8 TB — an x64 Windows process whose exe
 * lacks IMAGE_DLLCHARACTERISTICS_HIGH_ENTROPY_VA (retroarch.exe official
 * builds: DllCharacteristics == 0) gets only 8 TB of user address space,
 * and a fixed reserve above that fails on real Windows (wine doesn't
 * enforce the limit, which masked this).
 * Layout: [base, base+guard) guard page (never committed / PROT_NONE)
 *         [base+guard, base+16M) the engine coroutine stack (co_derive)
 *         [base+16M, ...) dlmalloc heap, grown sbrk-style
 * A level-load stack overflow hits the guard instead of silently mauling
 * heap chunks. Snapshots cover [base+4K, brk). */
/* Base + size come from obor_abi.h so the glue's load-time reservation and
 * this allocator agree on the exact range (see the constructor in
 * libretro.cpp). */
#define OBOR_ARENA_BASE ((char *)OBOR_ARENA_BASE_VA)
#define OBOR_ARENA_MAX OBOR_ARENA_MAX_SZ
#if defined(__aarch64__) || defined(__arm__)
/* Raspberry Pi/Recalbox builds commonly use 16K pages. mprotect rounds to
 * the host page size, so a 4K guard would also protect base+4K..base+16K
 * and make the libco stack fault immediately. */
#define OBOR_GUARD_SZ (16ULL * 1024)
#else
#define OBOR_GUARD_SZ 4096ULL
#endif
#define OBOR_STACK_RESERVE (16ULL * 1024 * 1024)

static char *arena_brk;  /* current break (grows, never shrinks) */
static char *arena_lim;  /* end of the reservation */
/* Sum of complete live dlmalloc chunks.  Maintaining it at the wrapped API
 * avoids a full heap walk merely to decide whether sparse encoding pays. */
static uint64_t arena_live_chunk_bytes;

char *obor_arena_base(void) { return OBOR_ARENA_BASE; }
char *obor_stack_ptr(void) { return OBOR_ARENA_BASE + OBOR_GUARD_SZ; }
size_t obor_stack_size(void) { return OBOR_STACK_RESERVE - OBOR_GUARD_SZ; }
size_t obor_arena_used(void)
{
    return arena_brk ? (size_t)(arena_brk - OBOR_ARENA_BASE) : 0;
}

/* The glue explicitly authorizes adoption of its own reservation. A failed
 * claim must never turn into MAP_FIXED over another module's allocation. */
static int arena_authorized;
void obor_arena_authorize(int owned) { arena_authorized = owned != 0; }
static int arena_init(void)
{
    if (!arena_authorized)
        return 0;
    if (arena_brk)
        return 1;
#if defined(_WIN32)
    /* range is MEM_RESERVE|MEM_WRITE_WATCH'd by the glue; commit the stack
     * region (morecore commits the heap as it grows) */
    if (!VirtualAlloc(OBOR_ARENA_BASE + OBOR_GUARD_SZ,
                      OBOR_STACK_RESERVE - OBOR_GUARD_SZ, MEM_COMMIT,
                      PAGE_READWRITE)) {
        fprintf(stderr, "[OpenBOR] arena stack commit failed (err %lu)\n",
                (unsigned long)GetLastError());
        return 0;
    }
#else
    void *p = mmap(OBOR_ARENA_BASE, OBOR_ARENA_MAX, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE | MAP_FIXED,
                   -1, 0);
    if (p != (void *)OBOR_ARENA_BASE) {
        fprintf(stderr, "[OpenBOR] arena map at %p failed (errno %d, got %p)\n",
                (void *)OBOR_ARENA_BASE, errno, p);
        return 0;
    }
    mprotect(OBOR_ARENA_BASE, OBOR_GUARD_SZ, PROT_NONE);
#endif
    arena_brk = OBOR_ARENA_BASE + OBOR_STACK_RESERVE;
    arena_lim = OBOR_ARENA_BASE + OBOR_ARENA_MAX;
    return 1;
}

/* exported so the port can force init before deriving the stack */
int obor_arena_init(void) { return arena_init(); }

/* retro_reset / netplay reinit: drop the arena's PHYSICAL pages but KEEP the
 * glue's VA claim (single-file core — the module is not reloaded). Never
 * munmap/MEM_RELEASE: that would free the range and let the frontend's ASLR
 * grab it before the next boot. The next arena_init re-maps fresh + zeroed. */
void obor_arena_release(void)
{
    if (!arena_brk)
        return;
#if defined(_WIN32)
    VirtualFree(OBOR_ARENA_BASE, OBOR_ARENA_MAX, MEM_DECOMMIT);
#else
    /* PROT_NONE keeps the mapping (claim) but returns the pages to the OS */
    mmap(OBOR_ARENA_BASE, OBOR_ARENA_MAX, PROT_NONE,
         MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE | MAP_FIXED, -1, 0);
#endif
    arena_brk = NULL;
    arena_lim = NULL;
    arena_live_chunk_bytes = 0;
}

/* Grow the arena to at least `used` bytes (state restore needs the saved
 * break re-established before copying the heap image back). */
int obor_arena_grow_to(size_t used)
{
    if (!arena_init())
        return 0;
    if (used > OBOR_ARENA_MAX)
        return 0;
    char *want = OBOR_ARENA_BASE + used;
    if (want > arena_brk) {
#if defined(_WIN32)
        if (!VirtualAlloc(arena_brk, (size_t)(want - arena_brk), MEM_COMMIT,
                          PAGE_READWRITE))
            return 0;
#endif
        arena_brk = want;
    }
    return 1;
}

/* ---- dirty-page tracking for the incremental serialize fast path ------- */
/* obor_dirty_reset(): forget all history (next scan sees everything clean).
 * obor_dirty_scan(off, len, cb, ctx): report pages of [base+off, base+off+
 * len) written since the previous reset/scan as (offset, length) runs, then
 * re-arm. Returns 1 on success, 0 if untrackable (caller falls back to a
 * full copy). Single-threaded by construction: the engine coroutine is
 * parked while the glue serializes. */
typedef void (*obor_dirty_cb)(size_t off, size_t len, void *ctx);

#if defined(_WIN32)
int obor_dirty_reset(void)
{
    return ResetWriteWatch(OBOR_ARENA_BASE, OBOR_ARENA_MAX) == 0;
}

int obor_dirty_scan(size_t off, size_t len, obor_dirty_cb cb, void *ctx)
{
    static void *addrs[16384];
    char *lo = OBOR_ARENA_BASE + off;
    char *hi = lo + len;
    while (lo < hi) {
        size_t chunk = (size_t)(hi - lo);
        if (chunk > (sizeof(addrs) / sizeof(addrs[0])) * 4096ULL)
            chunk = (sizeof(addrs) / sizeof(addrs[0])) * 4096ULL;
        ULONG_PTR n = sizeof(addrs) / sizeof(addrs[0]);
        ULONG gran = 0;
        if (GetWriteWatch(WRITE_WATCH_FLAG_RESET, lo, chunk, addrs, &n,
                          &gran) != 0)
            return 0;
        size_t run_off = 0, run_len = 0;
        for (ULONG_PTR i = 0; i < n; i++) {
            size_t po = (size_t)((char *)addrs[i] - OBOR_ARENA_BASE);
            if (run_len && po == run_off + run_len) {
                run_len += 4096;
            } else {
                if (run_len)
                    cb(run_off, run_len, ctx);
                run_off = po;
                run_len = 4096;
            }
        }
        if (run_len)
            cb(run_off, run_len, ctx);
        lo += chunk;
    }
    return 1;
}
#else
/* Linux: DISABLED. soft-dirty (/proc/self/clear_refs "4") technically
 * works, but re-arming write-protects EVERY writable page of the process;
 * the following frame then pays thousands of micro-faults (measured:
 * +3.3 ms just re-writing the destination buffer, plus hidden cost inside
 * the engine frame). A full 40 MB copy costs ~1.4 ms — cheaper than the
 * "optimization". Windows' GetWriteWatch has no such churn, so the fast
 * path stays on there. (Future: userfaultfd-wp is range-scoped and could
 * bring this back for Linux.) */
int obor_dirty_reset(void)
{
    return 0;
}

int obor_dirty_reset_linux_disabled(void)
{
    int fd = open("/proc/self/clear_refs", O_WRONLY);
    if (fd < 0)
        return 0;
    int ok = write(fd, "4", 1) == 1;
    close(fd);
    return ok;
}

int obor_dirty_scan(size_t off, size_t len, obor_dirty_cb cb, void *ctx)
{
    int fd = open("/proc/self/pagemap", O_RDONLY);
    if (fd < 0)
        return 0;
    static uint64_t ents[16384];
    size_t page0 = ((size_t)OBOR_ARENA_BASE + off) / 4096;
    size_t pages = (len + 4095) / 4096;
    size_t done = 0;
    size_t run_off = 0, run_len = 0;
    while (done < pages) {
        size_t n = pages - done;
        if (n > sizeof(ents) / sizeof(ents[0]))
            n = sizeof(ents) / sizeof(ents[0]);
        ssize_t got = pread(fd, ents, n * 8,
                            (off_t)((page0 + done) * 8));
        if (got != (ssize_t)(n * 8)) {
            close(fd);
            return 0;
        }
        for (size_t i = 0; i < n; i++) {
            if (!(ents[i] & (1ULL << 55)))
                continue;
            size_t po = off + (done + i) * 4096;
            if (run_len && po == run_off + run_len) {
                run_len += 4096;
            } else {
                if (run_len)
                    cb(run_off, run_len, ctx);
                run_off = po;
                run_len = 4096;
            }
        }
        done += n;
    }
    close(fd);
    if (run_len)
        cb(run_off, run_len, ctx);
    return obor_dirty_reset(); /* re-arm for the next interval */
}
#endif

/* sbrk-style MORECORE for dlmalloc */
static void *obor_morecore(intptr_t incr)
{
    if (!arena_init())
        return (void *)-1; /* MFAIL */
    if (incr <= 0)
        return arena_brk; /* no trim support; report current break */
    if (arena_brk + incr > arena_lim)
        return (void *)-1;
#if defined(_WIN32)
    if (!VirtualAlloc(arena_brk, (size_t)incr, MEM_COMMIT, PAGE_READWRITE))
        return (void *)-1;
#endif
    void *old = arena_brk;
    arena_brk += incr;
    return old;
}

/* ---- dlmalloc, configured as the arena allocator ---- */
#if defined(_WIN32)
/* Keep dlmalloc off its WIN32 branch (it would force HAVE_MORECORE=0 and
 * VirtualAlloc-mmap, bypassing the arena). It re-derives WIN32 from _WIN32,
 * so both go — but mingw system headers refuse to parse without _WIN32, so
 * pre-include every header dlmalloc's unix path wants while the macros are
 * still up. Locks come from winpthreads. */
#include <sys/types.h>
#include <errno.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <time.h>
#include <unistd.h>
#include <pthread.h>
#undef WIN32
#undef _WIN32
#define LACKS_SYS_MMAN_H 1
#define LACKS_SCHED_H 1
#define LACKS_SYS_PARAM_H 1
#endif
#define USE_DL_PREFIX 1
#define USE_LOCKS 1
#define HAVE_MMAP 0
#define HAVE_MREMAP 0
#define HAVE_MORECORE 1
#define MORECORE obor_morecore
#define MORECORE_CONTIGUOUS 1
#define MORECORE_CANNOT_TRIM 1
#define NO_MALLOC_STATS 1
#define ABORT_ON_ASSERT_FAILURE 0
#include "dlmalloc.inc"

extern void *__real_malloc(size_t);
extern void *__real_realloc(void *, size_t);
extern void __real_free(void *);

/* Test-only allocation ownership census. Keep the pointer table outside the
 * snapshotted arena so diagnostics cannot alter the state being measured. */
typedef struct {
    void *pointer;
    void *caller;
    size_t requested;
} profile_live_slot;

/* Some games can transiently create several million allocations while loading.
 * Keep the diagnostic table below 200 MiB and below 50% occupancy in the
 * largest observed case so linear probing remains bounded. */
enum { PROFILE_LIVE_CAPACITY = 1 << 23 };
static profile_live_slot *profile_live_slots;
static int profile_live_enabled = -1;

static int profile_live_is_enabled(void)
{
    if (profile_live_enabled < 0) {
        const char *value = getenv("OBOR_PROFILE_LIVE_SITES");
        profile_live_enabled = value && value[0];
        if (profile_live_enabled) {
            profile_live_slots = __real_malloc(sizeof(*profile_live_slots) *
                                               PROFILE_LIVE_CAPACITY);
            if (profile_live_slots)
                memset(profile_live_slots, 0, sizeof(*profile_live_slots) *
                                              PROFILE_LIVE_CAPACITY);
            else
                profile_live_enabled = 0;
        }
    }
    return profile_live_enabled;
}

static size_t profile_live_hash(const void *pointer)
{
    uintptr_t value = (uintptr_t)pointer >> 4;
    value ^= value >> 23;
    value *= (uintptr_t)0x9e3779b1U;
    return (size_t)value & (PROFILE_LIVE_CAPACITY - 1);
}

static void profile_live_remove(void *pointer)
{
    size_t slot, hole;
    if (!pointer || !profile_live_is_enabled())
        return;
    slot = profile_live_hash(pointer);
    for (size_t n = 0; n < PROFILE_LIVE_CAPACITY; ++n) {
        profile_live_slot *entry = &profile_live_slots[slot];
        if (!entry->pointer)
            return;
        if (entry->pointer == pointer) {
            /* Back-shift the following probe cluster. Tombstones eventually
             * made allocation-heavy games scan the entire table. */
            hole = slot;
            slot = hole;
            for (;;) {
                slot = (slot + 1) & (PROFILE_LIVE_CAPACITY - 1);
                profile_live_slot candidate = profile_live_slots[slot];
                if (!candidate.pointer) {
                    memset(&profile_live_slots[hole], 0,
                           sizeof(profile_live_slots[hole]));
                    return;
                }
                size_t home = profile_live_hash(candidate.pointer);
                if (((slot - home) & (PROFILE_LIVE_CAPACITY - 1)) >=
                    ((slot - hole) & (PROFILE_LIVE_CAPACITY - 1))) {
                    profile_live_slots[hole] = candidate;
                    hole = slot;
                }
            }
        }
        slot = (slot + 1) & (PROFILE_LIVE_CAPACITY - 1);
    }
}

static void profile_live_add(void *pointer, size_t requested, void *caller)
{
    size_t slot;
    if (!pointer || !profile_live_is_enabled())
        return;
    slot = profile_live_hash(pointer);
    for (size_t n = 0; n < PROFILE_LIVE_CAPACITY; ++n) {
        profile_live_slot *entry = &profile_live_slots[slot];
        if (!entry->pointer) {
            entry->pointer = pointer;
            entry->caller = caller;
            entry->requested = requested;
            return;
        } else if (entry->pointer == pointer) {
            entry->caller = caller;
            entry->requested = requested;
            return;
        }
        slot = (slot + 1) & (PROFILE_LIVE_CAPACITY - 1);
    }
}

static void profile_live_dump(void)
{
    typedef struct {
        void *caller;
        size_t requested;
        uint64_t count, chunk_bytes;
    } aggregate;
    enum { AGGREGATE_CAPACITY = 16384 };
    static int dumped;
    aggregate *groups;
    if (dumped || !profile_live_is_enabled())
        return;
    dumped = 1;
    groups = __real_malloc(sizeof(*groups) * AGGREGATE_CAPACITY);
    if (!groups)
        return;
    memset(groups, 0, sizeof(*groups) * AGGREGATE_CAPACITY);
    for (size_t i = 0; i < PROFILE_LIVE_CAPACITY; ++i) {
        profile_live_slot *live = &profile_live_slots[i];
        if (!live->pointer)
            continue;
        size_t slot = (((uintptr_t)live->caller >> 4) ^ live->requested) &
                      (AGGREGATE_CAPACITY - 1);
        for (size_t n = 0; n < AGGREGATE_CAPACITY; ++n) {
            aggregate *group = &groups[slot];
            if (!group->count || (group->caller == live->caller &&
                                  group->requested == live->requested)) {
                group->caller = live->caller;
                group->requested = live->requested;
                group->count++;
                group->chunk_bytes += chunksize(mem2chunk(live->pointer));
                break;
            }
            slot = (slot + 1) & (AGGREGATE_CAPACITY - 1);
        }
    }
    for (size_t i = 0; i < AGGREGATE_CAPACITY; ++i)
        if (groups[i].count)
            fprintf(stderr, "[obor-live-site] caller=%p requested=%llu count=%llu chunks=%llu\n",
                    groups[i].caller, (unsigned long long)groups[i].requested,
                    (unsigned long long)groups[i].count,
                    (unsigned long long)groups[i].chunk_bytes);
    __real_free(groups);
}

/* Test-only live allocation census.  Exact dlmalloc chunk sizes through
 * 64 KiB identify compact engine structures without retaining a pointer
 * table in the snapshot arena; larger chunks are grouped by power of two.
 * The external buffers and output are created only when explicitly asked. */
static void profile_heap_histogram(void)
{
    enum { EXACT_GRANULARITY = 8, EXACT_LIMIT = 65536,
           EXACT_BINS = EXACT_LIMIT / EXACT_GRANULARITY + 1,
           LARGE_BINS = 64 };
    static int checked;
    const char *destination;
    typedef struct {
        uint64_t hash, count;
        const unsigned char *sample;
    } duplicate_slot;
    enum { DUPLICATE_SLOTS = 131072, DUPLICATE_CHUNK = 160,
           DUPLICATE_COMPARE_BYTES = 144 };
    uint64_t *counts, *bytes, *large_counts, *large_bytes;
    duplicate_slot *duplicates = NULL;
    uint64_t duplicate_unique = 0, duplicate_instances = 0;

    if (checked)
        return;
    checked = 1;
    destination = getenv("OBOR_PROFILE_HEAP_HIST");
    if (!destination || !destination[0])
        return;
    counts = (uint64_t *)__real_malloc(EXACT_BINS * sizeof(*counts));
    bytes = (uint64_t *)__real_malloc(EXACT_BINS * sizeof(*bytes));
    large_counts = (uint64_t *)__real_malloc(LARGE_BINS * sizeof(*large_counts));
    large_bytes = (uint64_t *)__real_malloc(LARGE_BINS * sizeof(*large_bytes));
    if (!counts || !bytes || !large_counts || !large_bytes) {
        __real_free(counts);
        __real_free(bytes);
        __real_free(large_counts);
        __real_free(large_bytes);
        return;
    }
    memset(counts, 0, EXACT_BINS * sizeof(*counts));
    memset(bytes, 0, EXACT_BINS * sizeof(*bytes));
    memset(large_counts, 0, LARGE_BINS * sizeof(*large_counts));
    memset(large_bytes, 0, LARGE_BINS * sizeof(*large_bytes));
    duplicates = (duplicate_slot *)__real_malloc(DUPLICATE_SLOTS * sizeof(*duplicates));
    if (duplicates)
        memset(duplicates, 0, DUPLICATE_SLOTS * sizeof(*duplicates));

    ensure_initialization();
    mstate m = gm;
    if (!PREACTION(m)) {
        if (is_initialized(m)) {
            for (msegmentptr segment = &m->seg; segment; segment = segment->next) {
                mchunkptr q = align_as_chunk(segment->base);
                while (segment_holds(segment, q) && q != m->top &&
                       q->head != FENCEPOST_HEAD) {
                    size_t chunk = chunksize(q);
                    if (!chunk || (char *)q + chunk > segment->base + segment->size)
                        break;
                    if (is_inuse(q)) {
                        if (chunk <= EXACT_LIMIT) {
                            size_t bin = chunk / EXACT_GRANULARITY;
                            counts[bin]++;
                            bytes[bin] += chunk;
                        } else {
                            unsigned bin = 0;
                            size_t value = chunk;
                            while (value >>= 1)
                                bin++;
                            if (bin >= LARGE_BINS)
                                bin = LARGE_BINS - 1;
                            large_counts[bin]++;
                            large_bytes[bin] += chunk;
                        }
                        if (duplicates && chunk == DUPLICATE_CHUNK) {
                            const unsigned char *data = (const unsigned char *)chunk2mem(q);
                            uint64_t hash = UINT64_C(1469598103934665603);
                            for (size_t j = 0; j < DUPLICATE_COMPARE_BYTES; ++j) {
                                hash ^= data[j];
                                hash *= UINT64_C(1099511628211);
                            }
                            if (!hash)
                                hash = 1;
                            size_t slot = (size_t)hash & (DUPLICATE_SLOTS - 1);
                            for (size_t probe = 0; probe < DUPLICATE_SLOTS; ++probe) {
                                duplicate_slot *entry = &duplicates[slot];
                                if (!entry->hash) {
                                    entry->hash = hash;
                                    entry->count = 1;
                                    entry->sample = data;
                                    duplicate_unique++;
                                    duplicate_instances++;
                                    break;
                                }
                                if (entry->hash == hash &&
                                    !memcmp(entry->sample, data, DUPLICATE_COMPARE_BYTES)) {
                                    entry->count++;
                                    duplicate_instances++;
                                    break;
                                }
                                slot = (slot + 1) & (DUPLICATE_SLOTS - 1);
                            }
                        }
                    }
                    q = next_chunk(q);
                }
            }
        }
        POSTACTION(m);
    }

    FILE *out = (!strcmp(destination, "1") || !strcmp(destination, "stderr")) ?
                stderr : fopen(destination, "w");
    if (out) {
        for (size_t i = 1; i < EXACT_BINS; ++i)
            if (counts[i])
                fprintf(out, "[obor-heap-hist] chunk=%llu count=%llu bytes=%llu\n",
                        (unsigned long long)(i * EXACT_GRANULARITY),
                        (unsigned long long)counts[i],
                        (unsigned long long)bytes[i]);
        for (unsigned i = 0; i < LARGE_BINS; ++i)
            if (large_counts[i])
                fprintf(out, "[obor-heap-hist] range=%llu-%llu count=%llu bytes=%llu\n",
                        (unsigned long long)(1ULL << i),
                        (unsigned long long)(i == 63 ? UINT64_MAX : (1ULL << (i + 1)) - 1),
                        (unsigned long long)large_counts[i],
                        (unsigned long long)large_bytes[i]);
        if (duplicates)
            fprintf(out, "[obor-heap-duplicates] chunk=%u compared=%u instances=%llu unique=%llu\n",
                    DUPLICATE_CHUNK, DUPLICATE_COMPARE_BYTES,
                    (unsigned long long)duplicate_instances,
                    (unsigned long long)duplicate_unique);
        if (out != stderr)
            fclose(out);
    }
    __real_free(counts);
    __real_free(bytes);
    __real_free(large_counts);
    __real_free(large_bytes);
    __real_free(duplicates);
}

/* Snapshot profiling needs to distinguish live allocations from the arena's
 * high-water mark.  Keep this allocator-specific detail here: callers only
 * receive aggregate byte counts, and normal builds do no extra heap walk
 * unless the test-only OBOR_PROFILE path asks for them. */
void obor_arena_stats(size_t *live, size_t *free_bytes, size_t *top_free)
{
    struct mallinfo info = dlmallinfo();
    if (live)
        *live = info.uordblks > 0 ? (size_t)info.uordblks : 0;
    if (free_bytes)
        *free_bytes = info.fordblks > 0 ? (size_t)info.fordblks : 0;
    if (top_free)
        *top_free = info.keepcost > 0 ? (size_t)info.keepcost : 0;
    profile_heap_histogram();
    profile_live_dump();
}

/* Save allocated chunks verbatim, but retain only allocator bookkeeping for
 * free chunks.  User bytes in a free chunk have no defined value and are not
 * read by dlmalloc; its header/list/tree links and the segment tail are the
 * complete state needed to allocate from that chunk after a restore. */
#define OBOR_HEAP_SPARSE_MAGIC 0x3153484fU /* "OHS1" */
#define OBOR_HEAP_SPARSE_VERSION 2U

typedef struct {
    uint32_t magic, version, count, reserved;
    uint64_t arena_used, payload_bytes;
} obor_heap_sparse_header;

typedef struct {
    uint64_t offset, length;
} obor_heap_sparse_span;

typedef struct {
    unsigned char *cursor, *limit, *last_header;
#if OBOR_BATCH_SPARSE_SPANS
    const unsigned char *pending_address;
    uint64_t pending_length;
#endif
    uint64_t count, payload, previous_end;
    int have_previous, writing, failed;
} obor_sparse_scan;

/* Walking every dlmalloc chunk is counterproductive for script-heavy games:
 * a compiled instruction graph can contain well over a million adjacent live
 * allocations with only a few KiB of holes.  In that case one dense span is
 * both almost the same size and much cheaper to capture.  Keep sparse spans
 * when they actually omit a material part of the heap. */
static int sparse_use_dense(uint64_t *extent_out)
{
    const char *origin = OBOR_ARENA_BASE + OBOR_STACK_RESERVE;
    uint64_t extent, not_live;

    ensure_initialization();
    if (!arena_brk || arena_brk < origin)
        return 0;
    extent = (uint64_t)(arena_brk - origin);
    if (extent_out)
        *extent_out = extent;
    if (!extent)
        return 0;
    not_live = extent > arena_live_chunk_bytes ?
               extent - arena_live_chunk_bytes : 0;
    return not_live <= extent / 64;
}

#if OBOR_BATCH_SPARSE_SPANS
static void sparse_flush(obor_sparse_scan *scan)
{
    if (!scan->writing || !scan->pending_length || scan->failed)
        return;
    obor_heap_sparse_span span = {
        (uint64_t)((const char *)scan->pending_address -
                   (OBOR_ARENA_BASE + OBOR_STACK_RESERVE)),
        scan->pending_length
    };
    if ((size_t)(scan->limit - scan->cursor) < sizeof(span) ||
        span.length > (uint64_t)(scan->limit - scan->cursor - sizeof(span))) {
        scan->failed = 1;
        return;
    }
    scan->last_header = scan->cursor;
    memcpy(scan->cursor, &span, sizeof(span));
    scan->cursor += sizeof(span);
    obor_state_copy_heap(scan->cursor, scan->pending_address,
                         (size_t)span.length);
    scan->cursor += span.length;
    scan->pending_address = NULL;
    scan->pending_length = 0;
}
#endif

static void sparse_emit(obor_sparse_scan *scan, const void *address,
                        size_t length)
{
    const char *origin = OBOR_ARENA_BASE + OBOR_STACK_RESERVE;
    const char *at = (const char *)address;
    if (!length || at < origin || at > arena_brk ||
        length > (size_t)(arena_brk - at)) {
        scan->failed = 1;
        return;
    }
    uint64_t offset = (uint64_t)(at - origin);
    if (scan->have_previous && offset == scan->previous_end) {
        if (scan->writing) {
#if OBOR_BATCH_SPARSE_SPANS
            scan->pending_length += length;
#else
            obor_heap_sparse_span previous;
            if (length > (size_t)(scan->limit - scan->cursor)) {
                scan->failed = 1;
                return;
            }
            memcpy(&previous, scan->last_header, sizeof(previous));
            previous.length += length;
            memcpy(scan->last_header, &previous, sizeof(previous));
#endif
        }
    } else {
        if (scan->count == UINT32_MAX) {
            scan->failed = 1;
            return;
        }
        if (scan->writing) {
#if OBOR_BATCH_SPARSE_SPANS
            sparse_flush(scan);
            if (scan->failed)
                return;
            scan->pending_address = (const unsigned char *)address;
            scan->pending_length = length;
#else
            obor_heap_sparse_span span = {offset, length};
            if ((size_t)(scan->limit - scan->cursor) < sizeof(span) ||
                length > (size_t)(scan->limit - scan->cursor - sizeof(span))) {
                scan->failed = 1;
                return;
            }
            scan->last_header = scan->cursor;
            memcpy(scan->cursor, &span, sizeof(span));
            scan->cursor += sizeof(span);
#endif
        }
        scan->count++;
    }
#if !OBOR_BATCH_SPARSE_SPANS
    if (scan->writing) {
        memcpy(scan->cursor, address, length);
        scan->cursor += length;
    }
#endif
    scan->payload += length;
    scan->previous_end = offset + length;
    scan->have_previous = 1;
}

static int sparse_scan_heap(obor_sparse_scan *scan)
{
    ensure_initialization();
    mstate m = gm;
    if (PREACTION(m))
        return 0;
    if (!is_initialized(m)) {
        POSTACTION(m);
        return 0;
    }
    for (msegmentptr segment = &m->seg; segment; segment = segment->next) {
        mchunkptr q = align_as_chunk(segment->base);
        if ((char *)q > segment->base)
            sparse_emit(scan, segment->base, (size_t)((char *)q - segment->base));
        while (!scan->failed && segment_holds(segment, q) && q != m->top &&
               q->head != FENCEPOST_HEAD) {
            size_t chunk = chunksize(q);
            if (!chunk || (char *)q + chunk > segment->base + segment->size) {
                scan->failed = 1;
                break;
            }
            size_t kept = is_inuse(q) ? chunk :
                (chunk < sizeof(tchunk) ? chunk : sizeof(tchunk));
            sparse_emit(scan, q, kept);
            q = next_chunk(q);
        }
        if (!scan->failed && segment_holds(segment, m->top)) {
            size_t kept = m->topsize < sizeof(mchunk) ? m->topsize : sizeof(mchunk);
            sparse_emit(scan, m->top, kept);
        }
        if (!scan->failed) {
            if (segment->size < TOP_FOOT_SIZE)
                scan->failed = 1;
            else
                sparse_emit(scan, segment->base + segment->size - TOP_FOOT_SIZE,
                            TOP_FOOT_SIZE);
        }
#if OBOR_BATCH_SPARSE_SPANS
        sparse_flush(scan);
#endif
        scan->have_previous = 0; /* segment list order need not be ascending */
    }
    POSTACTION(m);
    return !scan->failed;
}

uint64_t obor_heap_sparse_size(void)
{
    uint64_t extent = 0;
    if (sparse_use_dense(&extent))
        return sizeof(obor_heap_sparse_header) +
               sizeof(obor_heap_sparse_span) + extent;
    obor_sparse_scan scan = {0};
    if (!sparse_scan_heap(&scan))
        return 0;
    uint64_t table = scan.count * sizeof(obor_heap_sparse_span);
    if (table > UINT64_MAX - sizeof(obor_heap_sparse_header) ||
        scan.payload > UINT64_MAX - sizeof(obor_heap_sparse_header) - table)
        return 0;
    return sizeof(obor_heap_sparse_header) + table + scan.payload;
}

uint64_t obor_heap_sparse_write(void *destination, uint64_t capacity)
{
    if (!destination || capacity < sizeof(obor_heap_sparse_header))
        return 0;
    uint64_t extent = 0;
    if (sparse_use_dense(&extent)) {
        uint64_t needed = sizeof(obor_heap_sparse_header) +
                          sizeof(obor_heap_sparse_span) + extent;
        if (needed > capacity)
            return 0;
        obor_heap_sparse_header header = {
            OBOR_HEAP_SPARSE_MAGIC, OBOR_HEAP_SPARSE_VERSION, 1, 0,
            obor_arena_used(), extent
        };
        obor_heap_sparse_span span = {0, extent};
        unsigned char *cursor = (unsigned char *)destination;
        memcpy(cursor, &header, sizeof(header));
        cursor += sizeof(header);
        memcpy(cursor, &span, sizeof(span));
        cursor += sizeof(span);
        memcpy(cursor, OBOR_ARENA_BASE + OBOR_STACK_RESERVE, (size_t)extent);
        return needed;
    }
    obor_sparse_scan write = {0};
    write.writing = 1;
    write.cursor = (unsigned char *)destination + sizeof(obor_heap_sparse_header);
    write.limit = (unsigned char *)destination + capacity;
    if (!sparse_scan_heap(&write))
        return 0;
    obor_heap_sparse_header header = {
        OBOR_HEAP_SPARSE_MAGIC, OBOR_HEAP_SPARSE_VERSION,
        (uint32_t)write.count, 0, obor_arena_used(), write.payload
    };
    memcpy(destination, &header, sizeof(header));
    return (uint64_t)(write.cursor - (unsigned char *)destination);
}

int obor_heap_sparse_validate(const void *source, uint64_t length,
                              uint64_t arena_used)
{
    if (!source || length < sizeof(obor_heap_sparse_header) ||
        arena_used < OBOR_STACK_RESERVE || arena_used > OBOR_ARENA_MAX)
        return 0;
    obor_heap_sparse_header header;
    memcpy(&header, source, sizeof(header));
    if (header.magic != OBOR_HEAP_SPARSE_MAGIC ||
        header.version != OBOR_HEAP_SPARSE_VERSION ||
        header.arena_used != arena_used)
        return 0;
    const unsigned char *cursor = (const unsigned char *)source + sizeof(header);
    const unsigned char *limit = (const unsigned char *)source + length;
    uint64_t extent = arena_used - OBOR_STACK_RESERVE, payload = 0;
    for (uint32_t i = 0; i < header.count; ++i) {
        obor_heap_sparse_span span;
        if ((size_t)(limit - cursor) < sizeof(span))
            return 0;
        memcpy(&span, cursor, sizeof(span));
        cursor += sizeof(span);
        if (!span.length || span.offset > extent || span.length > extent - span.offset ||
            span.length > header.payload_bytes ||
            payload > header.payload_bytes - span.length ||
            span.length > (uint64_t)(limit - cursor))
            return 0;
        cursor += span.length;
        payload += span.length;
    }
    return payload == header.payload_bytes && cursor == limit;
}

int obor_heap_sparse_restore(const void *source, uint64_t length,
                             uint64_t arena_used)
{
    if (!obor_heap_sparse_validate(source, length, arena_used))
        return 0;
    obor_heap_sparse_header header;
    memcpy(&header, source, sizeof(header));
    const unsigned char *cursor = (const unsigned char *)source + sizeof(header);
    char *origin = OBOR_ARENA_BASE + OBOR_STACK_RESERVE;
    for (uint32_t i = 0; i < header.count; ++i) {
        obor_heap_sparse_span span;
        memcpy(&span, cursor, sizeof(span));
        cursor += sizeof(span);
        memcpy(origin + span.offset, cursor, (size_t)span.length);
        cursor += span.length;
    }
    return 1;
}

/* ---- the --wrap surface ---- */

static int in_arena(const void *p)
{
    return (const char *)p >= OBOR_ARENA_BASE && (const char *)p < arena_lim;
}

static void profile_large_alloc(const char *kind, size_t bytes, void *result,
                                void *caller)
{
    static size_t threshold;
    static int initialized;
    if (!initialized) {
        const char *value = getenv("OBOR_PROFILE_ALLOC");
        threshold = value ? (size_t)strtoull(value, NULL, 10) : 0;
        initialized = 1;
    }
    if (threshold && bytes >= threshold)
        fprintf(stderr, "[obor-alloc] %s bytes=%llu ptr=%p caller=%p\n",
                kind, (unsigned long long)bytes, result, caller);
}

void *__wrap_malloc(size_t n)
{
    void *result = dlmalloc(n);
    if (result)
        arena_live_chunk_bytes += chunksize(mem2chunk(result));
    profile_large_alloc("malloc", n, result, __builtin_return_address(0));
    profile_live_add(result, n, __builtin_return_address(0));
    return result;
}

void *__wrap_calloc(size_t n, size_t sz)
{
    void *result = dlcalloc(n, sz);
    if (result)
        arena_live_chunk_bytes += chunksize(mem2chunk(result));
    size_t bytes = sz && n > SIZE_MAX / sz ? SIZE_MAX : n * sz;
    profile_large_alloc("calloc", bytes, result, __builtin_return_address(0));
    profile_live_add(result, bytes, __builtin_return_address(0));
    return result;
}

void *__wrap_realloc(void *p, size_t n)
{
    if (!p || in_arena(p)) {
        size_t old_chunk = p ? chunksize(mem2chunk(p)) : 0;
        void *result = dlrealloc(p, n);
        if (result) {
            profile_live_remove(p);
            arena_live_chunk_bytes -= old_chunk;
            arena_live_chunk_bytes += chunksize(mem2chunk(result));
            profile_live_add(result, n, __builtin_return_address(0));
        } else if (p && n == 0)
        {
            profile_live_remove(p);
            arena_live_chunk_bytes -= old_chunk;
        }
        profile_large_alloc("realloc", n, result, __builtin_return_address(0));
        return result;
    }
    return __real_realloc(p, n);
}

void __wrap_free(void *p)
{
    if (!p)
        return;
    if (in_arena(p))
    {
        profile_live_remove(p);
        arena_live_chunk_bytes -= chunksize(mem2chunk(p));
        dlfree(p);
    }
    else
        __real_free(p);
}

char *__wrap_strdup(const char *s)
{
    size_t n = strlen(s) + 1;
    char *d = (char *)dlmalloc(n);
    if (d) {
        arena_live_chunk_bytes += chunksize(mem2chunk(d));
        memcpy(d, s, n);
        profile_live_add(d, n, __builtin_return_address(0));
    }
    return d;
}
