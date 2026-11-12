/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_BLOCK_STATE_H
#define OBOR_BLOCK_STATE_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* Complete independent images, with stable slots for frontend delta codecs.
 * The cache owns only the current encoding/decoded base, never rewind history.
 * Allocators MUST live outside the memory being captured. */
#define OBOR_BLOCK_STATE_MAGIC UINT32_C(0x3143424f) /* OBC1 */
#define OBOR_BLOCK_STATE_BLOCK 16384U
#ifndef OBOR_BLOCK_STATE_CAPACITY
#define OBOR_BLOCK_STATE_CAPACITY (120U << 20)
#endif
#define OBOR_BLOCK_STATE_MAX_RAW (2U << 30)
/* A 64 MiB complete image bounds frontend scan/copy costs with a 256 MiB
 * rewind history. Keep the compiled ceiling for explicit diagnostics and
 * smaller synthetic test budgets. Overflow fails; no payload is truncated.
 * The pre-boot frontend query and engine writer share this fixed contract. */
#define OBOR_BLOCK_STATE_DEFAULT_CAPACITY \
    (OBOR_BLOCK_STATE_CAPACITY < (64U << 20) ? OBOR_BLOCK_STATE_CAPACITY : (64U << 20))
static inline uint32_t obor_block_state_requested_capacity(const char *value)
{
    static const struct { const char *text; uint32_t mib; } choices[] = {
        {"64", 64}, {"80", 80}, {"96", 96}, {"120", 120}
    };
    if (value) for (size_t i = 0; i < sizeof(choices) / sizeof(choices[0]); ++i)
        if (!strcmp(value, choices[i].text) && (choices[i].mib << 20) <= OBOR_BLOCK_STATE_CAPACITY)
            return choices[i].mib << 20;
    return OBOR_BLOCK_STATE_DEFAULT_CAPACITY;
}
typedef struct obor_block_state obor_block_state;
typedef struct {
    void *(*calloc)(size_t, size_t);
    void *(*realloc)(void *, size_t);
    void (*free)(void *);
    /* Optional complete set for an address-stable current decoded cache.
     * reserve requests MAX_RAW virtual bytes without committing them; grow
     * makes [old_size,new_size) writable without moving or changing earlier
     * bytes. Failure leaves the reservation releasable and earlier bytes
     * intact. No snapshots/history are retained in this cache. */
    void *(*raw_reserve)(size_t maximum);
    int (*raw_grow)(void *, size_t old_size, size_t new_size);
    void (*raw_release)(void *, size_t maximum);
} obor_block_allocator;
typedef struct {
    void *context;
    /* Return a stable direct view or fill scratch. Called synchronously while
     * the engine is parked; no allocation or mutation of captured memory. */
    const void *(*read)(void *, uint32_t offset, uint32_t length, void *scratch);
    /* Optional proof that the bytes still equal the cache's preceding image.
     * May span multiple blocks: prove every byte, including the interior.
     * Return zero unless mapping, epoch and write coverage are all known. */
    int (*unchanged)(void *, uint32_t offset, uint32_t length);
} obor_block_source;

obor_block_state *obor_block_state_create(const obor_block_allocator *allocator);
/* A smaller fixed image budget may be selected before a content session.
 * It must fit the format index and never exceed the compiled maximum. The
 * encoder's complete-image fallback and decoder both enforce this bound. */
obor_block_state *obor_block_state_create_sized(const obor_block_allocator *, uint32_t capacity);
void obor_block_state_destroy(obor_block_state *state);
void obor_block_state_forget(obor_block_state *state);
/* Owner-only recovery after a protected call left through a nonlocal exit.
 * Drain/join an interrupted helper and invalidate its partial image. Harmless
 * without pending work; never call from a signal handler or another thread. */
void obor_block_state_quiesce(obor_block_state *state);
/* Optional bounded slot maintenance. Each capture examines at most 512
 * entries and 4096 hole candidates and writes at most 512 KiB of pool bytes.
 * It reclaims excess slot capacity and moves complete encoded blocks into
 * earlier holes. No engine bytes or additional historical images are kept.
 * Disabled by default while cadence and frontend-delta costs are evaluated. */
void obor_block_state_set_compaction(obor_block_state *, int enabled);
/* Optional synchronous pipeline: at most one helper compresses bounded batches
 * while the caller reads/proves other blocks. It joins before return; scratch
 * never supplies restore data. Unsupported/small/single-CPU cases stay serial.
 * Disabled by default. Detailed per-block clocks also retain the serial path. */
void obor_block_state_set_worker(obor_block_state *, int enabled);
/* No caller output is modified on failure. Capacity overflow is a failure,
 * never a truncated or history-dependent image. */
int obor_block_state_encode(obor_block_state *state, const obor_block_source *source,
                            uint32_t raw_size);
/* Prefer LZ4 for new blocks as well as updates. If the complete image cannot
 * fit, retry once with DEFLATE in the same budget; never drop payload bytes. */
int obor_block_state_encode_fast(obor_block_state *state, const obor_block_source *source,
                                 uint32_t raw_size);
/* Diagnostic alternative: preserve directly changing bytes in raw stable
 * slots so compression does not amplify small changes for a frontend delta
 * codec. New blocks use LZ4; the same bounded DEFLATE retry remains available. */
int obor_block_state_encode_mutable(obor_block_state *state, const obor_block_source *source,
                                    uint32_t raw_size);
typedef struct {
    uint32_t blocks;
    uint64_t raw_bytes, slot_bytes;
    uint32_t read_blocks, proven_blocks, equal_blocks, repacks;
    uint64_t read_bytes;
    uint64_t total_stored_bytes, total_slot_bytes, pool_hole_bytes;
    uint32_t compact_examined, compact_holes, compact_moved;
    uint32_t worker_threads, worker_blocks;
    uint64_t owner_cpu_ns, helper_cpu_ns;
    uint64_t compact_written, compact_reclaimed;
} obor_block_changes;
/* Changed blocks exclude released slots; total_* and pool_hole_bytes describe
 * the current complete image. Diagnostic encoding costs, not a measurement of
 * frontend delta-history consumption. */
void obor_block_state_changes(const obor_block_state *, obor_block_changes *);
/* Constant-time count of source blocks actually recompressed by the last
 * successful encode. Unlike image statistics, this does not scan the index.
 * Released slots are excluded; invalid caches report no usable estimate. */
uint32_t obor_block_state_workload(const obor_block_state *);
/* Sum of owner and sole helper CPU costs from the last successful encode.
 * Constant time; zero if a clock is unavailable or the cache is invalid.
 * Unlike elapsed time, scheduler waits do not enable the helper by themselves. */
uint64_t obor_block_state_cpu_cost(const obor_block_state *);
/* Optional diagnostic clock. It must not mutate captured memory. Measurements
 * include clock overhead and are not acceptance timings. NULL disables it. */
typedef struct {
    uint64_t proof_ns, read_ns, compare_ns, compress_ns, slot_ns, crc_ns, cache_ns;
} obor_block_timing;
void obor_block_state_set_clock(obor_block_state *, uint64_t (*clock)(void));
void obor_block_state_timing(const obor_block_state *, obor_block_timing *);
const void *obor_block_state_image(const obor_block_state *state, uint32_t *used);
/* Decode/validate into private cache memory before an engine restore commits.
 * Failure invalidates the cache, and never touches engine memory. */
int obor_block_state_decode(obor_block_state *state, const void *image, uint32_t size);
const void *obor_block_state_raw(const obor_block_state *state, uint32_t *size);
/* Changed decoded blocks relative to the preceding cache image. This alone
 * does NOT describe writes the engine made since that image was captured. */
int obor_block_state_changed(const obor_block_state *state, uint32_t block);
#endif
