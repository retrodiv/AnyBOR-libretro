/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
/* Shared state adapter. Included after the OBS3 writer so the ordinary state
 * reader remains the authority for engine/profile/stack/resource validation.
 * Engine-declared resources may replace exactly proven reconstructible body
 * bytes with zeros. An explicit OBS5 manifest retains their complete recipes;
 * everything else is represented losslessly. */
#include "obor_block_state.h"
#include "obor_block_worker_policy.h"
#include "obor_state_config.h"
#include "obor_state_copy.h"
#include "obor_state_stream.h"

extern void *__real_calloc(size_t, size_t);
extern void *__real_realloc(void *, size_t);
extern void __real_free(void *);
int obor_dirty_reset(void);
typedef void (*coded_dirty_callback)(size_t, size_t, void *);
int obor_dirty_scan(size_t, size_t, coded_dirty_callback, void *);

typedef obor_state_part coded_part;
typedef struct {
    coded_part part[MAX_SEGS + 16];
    uint32_t count, length;
    int tracking;
    obor_resource_catalog *catalog;
    uint64_t resource_generation;
} coded_source;

static obor_block_state *coded_cache OBOR_RUNTIME;
static uint32_t coded_image_capacity OBOR_RUNTIME;
static obor_block_worker_policy coded_worker_policy OBOR_RUNTIME;
static uint64_t coded_epoch OBOR_RUNTIME;
static coded_part coded_previous_parts[MAX_SEGS + 16] OBOR_RUNTIME;
static uint32_t coded_previous_count OBOR_RUNTIME;
static uint64_t coded_resource_generation OBOR_RUNTIME;
static obor_resource_mask_range *coded_previous_mask OBOR_RUNTIME;
static uint32_t coded_previous_mask_count OBOR_RUNTIME;
static uint32_t coded_previous_mask_capacity OBOR_RUNTIME;
#if defined(_WIN32)
static unsigned char coded_dirty_pages[(OBOR_ARENA_MAX_SZ / 4096 + 7) / 8] OBOR_RUNTIME;
static int coded_windows_tracking OBOR_RUNTIME;
#endif

static int coded_requested(void)
{
    return obor_state_coded_enabled();
}

static uint32_t coded_capacity(void)
{
    if (!coded_image_capacity) {
        /* Diagnostic only: compare the stock frontend's capacity reservation
         * with identical code/input. Latch once, never shrink/grow mid-session,
         * and never increase the format's existing maximum. */
        coded_image_capacity = obor_block_state_requested_capacity(getenv("OBOR_TEST_CODED_CAPACITY_MIB"));
    }
    return coded_image_capacity;
}

void obor_state_coded_forget(void)
{
    obor_block_worker_policy_reset(&coded_worker_policy);
    coded_epoch = 0;
    coded_previous_count = 0;
    coded_resource_generation = 0;
    coded_previous_mask_count = 0;
#if defined(_WIN32)
    coded_windows_tracking = 0;
#endif
}

void obor_state_coded_discard(void)
{
    obor_state_coded_forget();
    obor_block_state_destroy(coded_cache);
    coded_cache = NULL;
    coded_image_capacity = 0;
    __real_free(coded_previous_mask);
    coded_previous_mask = NULL;
    coded_previous_mask_capacity = 0;
}

#if defined(_WIN32)
#include "obor_state_cache_win.h"
#endif

static int coded_create(void)
{
    if (!coded_cache) {
        const obor_block_allocator allocator = {
            .calloc = __real_calloc, .realloc = __real_realloc, .free = __real_free,
#if defined(_WIN32)
            /* Windows CRT realloc can copy the entire current decoded image
             * for tiny heap growth on each capture. Reserve only virtual
             * address space; commit current bytes incrementally in place. */
            .raw_reserve = coded_raw_reserve, .raw_grow = coded_raw_grow,
            .raw_release = coded_raw_release
#endif
        };
        coded_cache = obor_block_state_create_sized(&allocator, coded_capacity());
    }
    return coded_cache != NULL;
}

static int coded_add(coded_source *source, const void *address, uint64_t length, int kind)
{
    return obor_state_part_add(source->part, sizeof(source->part) / sizeof(source->part[0]),
        &source->count, &source->length, address, length, kind);
}

static int coded_read_resources(void *opaque, const unsigned char *address, void *out, uint32_t length)
{
    coded_source *source = opaque;
    uintptr_t base = (uintptr_t)obor_arena_base(), begin = (uintptr_t)address;
    if (begin < base || begin - base > UINT32_MAX) return 0;
    return obor_resource_catalog_read(source->catalog, (uint32_t)(begin - base), out, length);
}

static const void *coded_read(void *opaque, uint32_t offset, uint32_t length, void *scratch)
{
    coded_source *source = opaque;
    return obor_state_part_read(source->part, source->count, source->length, offset, length,
        scratch, source->catalog ? coded_read_resources : NULL, source);
}

#if defined(_WIN32)
static void coded_mark_dirty(size_t offset, size_t length, void *unused)
{
    (void)unused;
    if (offset > OBOR_ARENA_MAX_SZ || length > OBOR_ARENA_MAX_SZ - offset) return;
    size_t end = (offset + length + 4095) / 4096;
    for (size_t page = offset / 4096; page < end; ++page)
        coded_dirty_pages[page / 8] |= (unsigned char)(1U << (page % 8));
}
#endif

static int coded_resource_unchanged(void *opaque, uint32_t offset, uint32_t length)
{
    const coded_source *source = opaque;
    uintptr_t begin = (uintptr_t)obor_arena_base() + offset;
    if (!source->tracking || !length || begin < heap_lo() ||
        offset > OBOR_ARENA_MAX_SZ || length > OBOR_ARENA_MAX_SZ - offset) return 0;
#if defined(_WIN32)
    size_t first = offset / 4096, last = (offset + length - 1) / 4096;
    for (size_t page = first; page <= last; ++page)
        if (coded_dirty_pages[page / 8] & (1U << (page % 8))) return 0;
    return 1;
#elif OBOR_WRITE_WATCH_ENABLED
    return obor_write_watch_range_unchanged(begin, length, coded_epoch);
#else
    return 0;
#endif
}

/* Obtain the current proof before a restore stops write tracking. Windows'
 * scan resets the queried pages, so invalidate its global epoch immediately;
 * even a rejected load must not later reuse a proof that lost those writes. */
static void coded_restore_tracking(coded_source *source)
{
    memset(source, 0, sizeof(*source));
#if defined(_WIN32)
    memset(coded_dirty_pages, 0, sizeof(coded_dirty_pages));
    source->tracking = coded_windows_tracking && obor_dirty_scan(
        (size_t)(heap_lo() - OBOR_ARENA_BASE_VA), (size_t)heap_used(), coded_mark_dirty, NULL);
    coded_windows_tracking = 0;
#elif OBOR_WRITE_WATCH_ENABLED
    source->tracking = coded_epoch && obor_write_watch_epoch();
#endif
}

static void coded_watch_restored_resources(void)
{
    obor_block_worker_policy_reset(&coded_worker_policy);
    if (!obor_resources_catalog() || __atomic_load_n(&obor_live_threads, __ATOMIC_SEQ_CST)) return;
#if defined(_WIN32)
    coded_windows_tracking = obor_dirty_reset();
#elif OBOR_WRITE_WATCH_ENABLED
    long native_page = sysconf(_SC_PAGESIZE);
    uint64_t extent = heap_used(), page = native_page > 0 ? (uint64_t)native_page : 0;
    uint64_t rounded = page ? (extent + page - 1) / page * page : 0;
    uint64_t maximum = OBOR_ARENA_MAX_SZ - (heap_lo() - OBOR_ARENA_BASE_VA);
    if (!rounded || rounded > maximum ||
        !obor_write_watch_start((void *)(uintptr_t)heap_lo(), (size_t)rounded, (size_t)maximum)) return;
    coded_epoch = obor_write_watch_epoch();
    int armed = obor_write_watch_arm((size_t)rounded);
    if (armed < 0) obor_fault_abort(OBOR_FAULT_MEMORY, 0);
    if (!armed && !owned_stop_images()) obor_fault_abort(OBOR_FAULT_MEMORY, 0);
#endif
}

static int coded_unchanged(void *opaque, uint32_t offset, uint32_t length)
{
    coded_source *source = opaque;
    if (!length) return 0;
    for (uint32_t i = 0; i < source->count; ++i) {
        const coded_part *part = source->part + i;
        if (part->kind == OBOR_STATE_BYTES ||
            !obor_state_part_mapped(part, coded_previous_parts, coded_previous_count, offset, length)) continue;
        if (part->kind == OBOR_STATE_ZERO) return 1;
        if (part->kind == OBOR_STATE_MANIFEST)
            return obor_resource_catalog_manifest_unchanged(source->catalog,
                coded_resource_generation, offset - part->offset, length);
        if (!source->tracking) return 0;
        uint32_t arena_offset = (uint32_t)((uintptr_t)part->address + offset -
            part->offset - (uintptr_t)obor_arena_base());
        if (source->resource_generation != coded_resource_generation &&
            (!source->catalog || !obor_resource_catalog_mask_unchanged(source->catalog,
                coded_previous_mask, coded_previous_mask_count, arena_offset, length))) return 0;
        return coded_resource_unchanged(source, arena_offset, length);
    }
    return 0;
}

static uint32_t update_coded(void *buffer, uint32_t size, int preparation)
{
    if ((!preparation && !buffer) || size < coded_capacity() || !collect_segments() ||
        __atomic_load_n(&obor_live_threads, __ATOMIC_SEQ_CST) > 0 || !coded_create())
        return 0;
    ensure_boot_id();
    unsigned char *stack = (unsigned char *)obor_stack_ptr();
    unsigned char *top = stack + obor_stack_size();
    unsigned char *sp = (unsigned char *)obor_engine_sp(), *slice = stack;
    if (sp > stack + OBOR_STACK_HEAD + 128 && sp < top) slice = sp - 128;
    uint64_t stack_length = (uint64_t)(top - slice);
    if (stack_length > OBOR_STACK_BUDGET) return 0;
    uint64_t extent = heap_used(), prefix = extent, suffix = 0, suffix_length = 0;
    if (!extent) return 0;
    /* Avoid serializing a large unused top allocation. Interior free bytes
     * remain losslessly represented so the logical block addresses stay stable. */
    uint64_t candidate_prefix, candidate_suffix, candidate_length;
    if (obor_heap_owned_layout(&candidate_prefix, &candidate_suffix, &candidate_length) &&
        candidate_prefix <= extent && candidate_suffix >= candidate_prefix &&
        candidate_suffix <= extent && candidate_length == extent - candidate_suffix &&
        extent - candidate_prefix - candidate_length >= (1U << 20)) {
        prefix = candidate_prefix; suffix = candidate_suffix; suffix_length = candidate_length;
    }
    uint32_t count = suffix_length ? 2 : 1;
    struct {
        uint32_t magic, version, count, reserved;
        uint64_t arena_used, payload;
    } heap_header = {UINT32_C(0x3153484f), 2, count, 0,
                     obor_arena_used(), prefix + suffix_length};
    struct { uint64_t offset, length; } spans[2] = {{0, prefix}, {suffix, suffix_length}};
    obs_header header;
    memset(&header, 0, sizeof(header));
    header.magic = OBS_MAGIC;
    header.version = OBS_VERSION;
    memcpy(header.build_identity, g_state_build_identity, sizeof(header.build_identity));
    header.profile_build = g_profile_build;
    header.physical_build = OBOR_ENGINE_BUILD;
    header.nsegs = (uint32_t)g_nsegs;
    header.image_lo = g_image_lo;
    header.image_hi = g_image_hi;
    header.boot_id = g_boot_id;
    header.arena_used = obor_arena_used();
    header.stack_off = (uint64_t)(slice - stack);
    header.stack_len = stack_length;
    header.heap_len = sizeof(heap_header) + count * sizeof(spans[0]) + prefix + suffix_length;
    coded_source source;
    memset(&source, 0, sizeof(source));
    if (!coded_add(&source, &header, sizeof(header), 0) ||
        !coded_add(&source, g_segs, (uint64_t)g_nsegs * sizeof(seg_t), 0)) return 0;
    for (int i = 0; i < g_nsegs; ++i)
        if (!coded_add(&source, (const void *)(uintptr_t)g_segs[i].vaddr, g_segs[i].size, 0)) return 0;
    if (!coded_add(&source, stack, OBOR_STACK_HEAD, OBOR_STATE_BYTES)) return 0;

#if defined(_WIN32)
    memset(coded_dirty_pages, 0, sizeof(coded_dirty_pages));
    source.tracking = coded_windows_tracking && obor_dirty_scan(
        (size_t)(heap_lo() - OBOR_ARENA_BASE_VA), (size_t)extent, coded_mark_dirty, NULL);
#elif OBOR_WRITE_WATCH_ENABLED
    size_t page = obor_write_watch_page_size();
    if (!page) { long native_page = sysconf(_SC_PAGESIZE); if (native_page > 0) page = (size_t)native_page; }
    uint64_t rounded = page ? (extent + page - 1) / page * page : 0;
    uint64_t maximum = OBOR_ARENA_MAX_SZ - (heap_lo() - OBOR_ARENA_BASE_VA);
    if (rounded && rounded <= maximum &&
        (obor_write_watch_epoch() || obor_write_watch_start((void *)(uintptr_t)heap_lo(),
                                                            (size_t)rounded, (size_t)maximum)) &&
        obor_write_watch_extend((size_t)rounded)) source.tracking = coded_epoch != 0;
#endif
    uint64_t resource_begin = getenv("OBOR_STATE_TIMING") ? state_timing_now() : 0;
    source.catalog = obor_resources_catalog();
    if (source.catalog) {
        obor_video_prepare_state();
        uint32_t manifest_size;
        if (!obor_resource_catalog_prepare(source.catalog, (uint32_t)obor_arena_used(),
            coded_resource_unchanged, &source)) {
            obor_state_coded_forget();
            return 0;
        }
        const void *manifest = obor_resource_catalog_manifest(source.catalog, &manifest_size);
        if (!manifest || manifest_size > OBOR_STATE_MANIFEST_WINDOW ||
            !coded_add(&source, NULL, OBOR_STATE_STACK_WINDOW - stack_length, OBOR_STATE_ZERO) ||
            !coded_add(&source, slice, stack_length, OBOR_STATE_BYTES) ||
            !coded_add(&source, manifest, manifest_size, OBOR_STATE_MANIFEST) ||
            !coded_add(&source, NULL, OBOR_STATE_MANIFEST_WINDOW - manifest_size, OBOR_STATE_ZERO)) {
            obor_state_coded_forget();
            return 0;
        }
        header.version = OBS_STABLE_RESOURCE_VERSION;
        const char *aligned_heap = getenv("OBOR_STATE_ALIGNED_HEAP");
        if (aligned_heap && !strcmp(aligned_heap, "1")) {
            if (sizeof(heap_header) + sizeof(spans[0]) != OBOR_STATE_SPARSE_PREFIX ||
                heap_lo() % OBOR_STATE_HEAP_ALIGNMENT ||
                !coded_add(&source, NULL, obor_state_resource_heap_padding(source.length),
                           OBOR_STATE_ZERO)) {
                obor_state_coded_forget();
                return 0;
            }
            header.version = OBS_ALIGNED_RESOURCE_VERSION;
        }
        source.resource_generation = obor_resource_catalog_generation(source.catalog);
    }
    if (!coded_add(&source, &heap_header, sizeof(heap_header), OBOR_STATE_BYTES) ||
        !coded_add(&source, spans, sizeof(spans[0]), OBOR_STATE_BYTES) ||
        !coded_add(&source, (const void *)(uintptr_t)heap_lo(), prefix, OBOR_STATE_HEAP)) return 0;
    if (suffix_length &&
        (!coded_add(&source, spans + 1, sizeof(spans[0]), OBOR_STATE_BYTES) ||
         !coded_add(&source, (const void *)(uintptr_t)(heap_lo() + suffix), suffix_length, OBOR_STATE_HEAP))) return 0;
    if (!source.catalog && !coded_add(&source, slice, stack_length, OBOR_STATE_BYTES)) return 0;
    uint64_t resource_end = resource_begin ? state_timing_now() : 0;
    const obor_block_source input = {&source, coded_read, coded_unchanged};
    const char *raw_mutable = getenv("OBOR_STATE_RAW_MUTABLE");
    int initial_deflate = obor_state_option("OBOR_STATE_INITIAL_DEFLATE", OBOR_STATE_DEFAULT_ENABLED);
    const char *block_profile = getenv("OBOR_BLOCK_PROFILE");
    int pool_compact = obor_state_option("OBOR_STATE_POOL_COMPACT", OBOR_STATE_DEFAULT_ENABLED);
    int block_profile_enabled = !preparation && block_profile && !strcmp(block_profile, "1");
    obor_block_state_set_clock(coded_cache, block_profile_enabled ? state_timing_now : NULL);
    obor_block_state_set_compaction(coded_cache, !preparation && pool_compact);
#if defined(__linux__) && !defined(__ANDROID__)
    /* Keep explicit serial/helper overrides for attribution. The platform
     * default uses work measured in the preceding call of the same phase;
     * at most one helper joins before this call returns. */
    obor_block_state_set_worker(coded_cache,
        obor_state_option("OBOR_STATE_COMPRESSION_WORKER",
            OBOR_STATE_DEFAULT_ENABLED &&
            obor_block_worker_policy_due(&coded_worker_policy, preparation)));
#endif
    /* Compact newly encountered blocks once, then use the fast codec for
     * mutable updates. Both choices preserve the complete engine bytes. */
    int encoded = source.catalog ?
        (raw_mutable && !strcmp(raw_mutable, "1") ?
            obor_block_state_encode_mutable(coded_cache, &input, source.length) :
            initial_deflate ?
                obor_block_state_encode(coded_cache, &input, source.length) :
                obor_block_state_encode_fast(coded_cache, &input, source.length)) :
        obor_block_state_encode(coded_cache, &input, source.length);
    if (!encoded) {
        obor_state_coded_forget();
        fprintf(stderr, "[obor] complete compressed state exceeds its format budget or cannot be allocated\n");
        return 0;
    }
    obor_block_worker_policy_observe(&coded_worker_policy, preparation,
        obor_block_state_workload(coded_cache), obor_block_state_cpu_cost(coded_cache));
    uint32_t used = 0;
    const void *image = obor_block_state_image(coded_cache, &used);
    if (!image || used > size) return 0;
    uint64_t codec_end = resource_begin ? state_timing_now() : 0;
    if (!preparation) obor_state_copy_heap(buffer, image, used);
    uint64_t copy_end = resource_begin ? state_timing_now() : 0;
    if (block_profile_enabled) {
        obor_block_timing timing;
        obor_block_state_timing(coded_cache, &timing);
        fprintf(stderr, "[obor-block-profile] proof_ms=%.3f read_ms=%.3f compare_ms=%.3f compress_ms=%.3f slot_ms=%.3f crc_ms=%.3f cache_ms=%.3f\n",
            timing.proof_ns / 1e6, timing.read_ns / 1e6, timing.compare_ns / 1e6,
            timing.compress_ns / 1e6, timing.slot_ns / 1e6, timing.crc_ns / 1e6,
            timing.cache_ns / 1e6);
    }
    if (resource_begin) {
        obor_block_changes changed;
        obor_block_state_changes(coded_cache, &changed);
        fprintf(stderr, "[obor-codec-cpu%s] owner_ms=%.3f helper_ms=%.3f total_ms=%.3f\n",
            preparation ? "-prepare" : "", changed.owner_cpu_ns / 1e6,
            changed.helper_cpu_ns / 1e6, obor_block_state_cpu_cost(coded_cache) / 1e6);
        fprintf(stderr, "[obor-resources%s] prepare_ms=%.3f codec_ms=%.3f copy_ms=%.3f used=%u changed_blocks=%u changed_raw=%llu changed_slots=%llu read_blocks=%u read_bytes=%llu proven_blocks=%u equal_blocks=%u repacks=%u tracking=%d generation=%llu previous_generation=%llu logical_bytes=%u stored_bytes=%llu slot_bytes=%llu hole_bytes=%llu\n",
            preparation ? "-prepare" : "",
            (resource_end - resource_begin) / 1e6, (codec_end - resource_end) / 1e6,
            (copy_end - codec_end) / 1e6, used, changed.blocks,
            (unsigned long long)changed.raw_bytes, (unsigned long long)changed.slot_bytes,
            changed.read_blocks, (unsigned long long)changed.read_bytes,
            changed.proven_blocks, changed.equal_blocks, changed.repacks, source.tracking,
            (unsigned long long)source.resource_generation,
            (unsigned long long)coded_resource_generation, source.length,
            (unsigned long long)changed.total_stored_bytes,
            (unsigned long long)changed.total_slot_bytes,
            (unsigned long long)changed.pool_hole_bytes);
        if (changed.worker_threads)
            fprintf(stderr, "[obor-block-worker%s] threads=%u blocks=%u\n",
                preparation ? "-prepare" : "", changed.worker_threads, changed.worker_blocks);
        if (pool_compact)
            fprintf(stderr, "[obor-pool-maintenance] examined=%u holes=%u moved=%u written=%llu reclaimed=%llu\n",
                changed.compact_examined, changed.compact_holes, changed.compact_moved,
                (unsigned long long)changed.compact_written,
                (unsigned long long)changed.compact_reclaimed);
    }
    coded_previous_count = source.count;
    coded_resource_generation = source.resource_generation;
    memcpy(coded_previous_parts, source.part, source.count * sizeof(coded_part));
    if (source.catalog) {
        uint32_t count = obor_resource_catalog_mask_count(source.catalog);
        if (count > coded_previous_mask_capacity) {
            void *mask = __real_realloc(coded_previous_mask, (size_t)count * sizeof(*coded_previous_mask));
            if (mask) {
                coded_previous_mask = mask;
                coded_previous_mask_capacity = count;
            }
        }
        if (!obor_resource_catalog_copy_mask(source.catalog, coded_previous_mask,
                                             coded_previous_mask_capacity)) {
            /* The complete output is already valid. Losing this optional
             * proof only forces a complete comparison on the next capture. */
            coded_previous_count = coded_previous_mask_count = 0;
        } else coded_previous_mask_count = count;
    } else coded_previous_mask_count = 0;
#if defined(_WIN32)
    coded_windows_tracking = obor_dirty_reset();
#elif OBOR_WRITE_WATCH_ENABLED
    coded_epoch = obor_write_watch_epoch();
    if (coded_epoch) {
        int armed = obor_write_watch_arm((size_t)rounded);
        if (armed < 0) obor_fault_abort(OBOR_FAULT_MEMORY, 0);
        if (!armed && !owned_stop_images()) obor_fault_abort(OBOR_FAULT_MEMORY, 0);
    }
#endif
    return used;
}

static uint32_t serialize_coded(void *buffer, uint32_t size)
{ return update_coded(buffer, size, 0); }
