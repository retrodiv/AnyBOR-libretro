/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_block_state.h"
#include "obor_block_crc.h"
#include "lz4.h"
#include <string.h>
#include <zlib.h>
#if defined(__linux__) && !defined(__ANDROID__)
#include <time.h>
#endif

/* Called only at capture/thread boundaries, not once per block. Failure is
 * performance metadata, never a reason to omit or reject captured state. */
static uint64_t block_cpu_now(void)
{
#if defined(__linux__) && !defined(__ANDROID__) && defined(CLOCK_THREAD_CPUTIME_ID)
    struct timespec value;
    if (!clock_gettime(CLOCK_THREAD_CPUTIME_ID, &value))
        return (uint64_t)value.tv_sec * UINT64_C(1000000000) + (uint64_t)value.tv_nsec;
#endif
    return 0;
}

static uint64_t block_cpu_elapsed(uint64_t begin)
{
    uint64_t end = block_cpu_now();
    return begin && end >= begin ? end - begin : 0;
}

#define BS_BLOCK OBOR_BLOCK_STATE_BLOCK
#define BS_MAX_BLOCKS (OBOR_BLOCK_STATE_MAX_RAW / BS_BLOCK)
#define BS_ALIGN 256U
#define BS_VERSION 1U
enum { BS_RAW, BS_LZ4, BS_DEFLATE };
typedef struct {
    uint32_t offset, stored, capacity, raw, codec, crc;
} block_entry;
typedef struct {
    uint32_t magic, version, block, count, raw, used, reserved[2];
} block_header;
typedef struct { uint32_t offset, length; } block_hole;
#define BS_TABLE_END ((uint32_t)((sizeof(block_header) + \
    BS_MAX_BLOCKS * sizeof(block_entry) + BS_ALIGN - 1) / BS_ALIGN * BS_ALIGN))
#define BS_OCCUPIED_BYTES ((OBOR_BLOCK_STATE_CAPACITY / BS_ALIGN + 7) / 8)

struct obor_block_state {
    obor_block_allocator allocator;
    unsigned char *image, *raw;
    uint32_t raw_size, raw_capacity, high, hole_count, capacity;
    int valid, deflater_ready, inflater_ready;
    z_stream deflater, inflater;
    block_hole *holes;
    unsigned char *occupied;
    unsigned char changed[(BS_MAX_BLOCKS + 7) / 8];
    obor_block_changes work;
    uint64_t (*clock)(void);
    obor_block_timing timing;
    uint32_t compact_cursor;
    int compact_enabled;
    int worker_enabled;
    void *worker_workspace;
};

void obor_block_state_set_compaction(obor_block_state *state, int enabled)
{ if (state) state->compact_enabled = enabled != 0; }

void obor_block_state_set_worker(obor_block_state *state, int enabled)
{ if (state) state->worker_enabled = enabled != 0; }

void obor_block_state_set_clock(obor_block_state *state, uint64_t (*clock)(void))
{ if (state) state->clock = clock; }

void obor_block_state_timing(const obor_block_state *state, obor_block_timing *out)
{
    if (!out) return;
    memset(out, 0, sizeof(*out));
    if (state && state->valid) *out = state->timing;
}

static uint64_t block_tick(obor_block_state *state)
{ return state->clock ? state->clock() : 0; }

static void block_elapsed(obor_block_state *state, uint64_t begin, uint64_t *sum)
{
    if (state->clock) {
        uint64_t end = state->clock();
        if (end >= begin) *sum += end - begin;
    }
}

static voidpf block_zalloc(voidpf opaque, uInt count, uInt size)
{
    obor_block_allocator *allocator = opaque;
    if (size && (size_t)count > SIZE_MAX / size) return NULL;
    return allocator->calloc(count, size);
}

static void block_zfree(voidpf opaque, voidpf memory)
{
    obor_block_allocator *allocator = opaque;
    allocator->free(memory);
}

obor_block_state *obor_block_state_create_sized(const obor_block_allocator *allocator, uint32_t capacity)
{
    if (!allocator || !allocator->calloc || !allocator->realloc ||
        !allocator->free || BS_TABLE_END >= capacity || capacity % BS_ALIGN ||
        capacity > OBOR_BLOCK_STATE_CAPACITY)
        return NULL;
    if ((allocator->raw_reserve || allocator->raw_grow || allocator->raw_release) &&
        (!allocator->raw_reserve || !allocator->raw_grow || !allocator->raw_release))
        return NULL;
    obor_block_state *state = allocator->calloc(1, sizeof(*state));
    if (!state) return NULL;
    state->allocator = *allocator;
    state->capacity = capacity;
    state->image = allocator->calloc(1, capacity);
    state->holes = allocator->calloc(BS_MAX_BLOCKS + 1, sizeof(block_hole));
    state->occupied = allocator->calloc(1, BS_OCCUPIED_BYTES);
    state->deflater.zalloc = state->inflater.zalloc = block_zalloc;
    state->deflater.zfree = state->inflater.zfree = block_zfree;
    state->deflater.opaque = state->inflater.opaque = &state->allocator;
    if (!state->image || !state->holes || !state->occupied) goto fail;
    if (deflateInit(&state->deflater, 1) != Z_OK) goto fail;
    state->deflater_ready = 1;
    if (inflateInit(&state->inflater) != Z_OK) goto fail;
    state->inflater_ready = 1;
    state->high = BS_TABLE_END;
    return state;
fail:
    obor_block_state_destroy(state);
    return NULL;
}

obor_block_state *obor_block_state_create(const obor_block_allocator *allocator)
{ return obor_block_state_create_sized(allocator, OBOR_BLOCK_STATE_CAPACITY); }

void obor_block_state_destroy(obor_block_state *state)
{
    if (!state) return;
    obor_block_allocator allocator = state->allocator;
    if (state->deflater_ready) deflateEnd(&state->deflater);
    if (state->inflater_ready) inflateEnd(&state->inflater);
    allocator.free(state->image);
    if (state->raw && allocator.raw_release)
        allocator.raw_release(state->raw, OBOR_BLOCK_STATE_MAX_RAW);
    else allocator.free(state->raw);
    allocator.free(state->holes);
    allocator.free(state->occupied);
    allocator.free(state->worker_workspace);
    allocator.free(state);
}

void obor_block_state_forget(obor_block_state *state)
{
    if (!state) return;
    state->valid = 0;
    state->raw_size = state->hole_count = 0;
    state->compact_cursor = 0;
    state->high = BS_TABLE_END;
    memset(state->image, 0, BS_TABLE_END);
    memset(state->changed, 0xff, sizeof(state->changed));
    /* Bytes past high are not published. Future slots are initialized before
     * high advances, including their padding; discarded states do not leak. */
}

static int block_reserve_raw(obor_block_state *state, uint32_t size)
{
    if (!size || size > OBOR_BLOCK_STATE_MAX_RAW) return 0;
    if (size <= state->raw_capacity) return 1;
    if (state->allocator.raw_reserve) {
        if (!state->raw)
            state->raw = state->allocator.raw_reserve(OBOR_BLOCK_STATE_MAX_RAW);
        if (!state->raw || !state->allocator.raw_grow(state->raw, state->raw_capacity, size))
            return 0;
        state->raw_capacity = size;
        return 1;
    }
    void *raw = state->allocator.realloc(state->raw, size);
    if (!raw) return 0;
    state->raw = raw;
    state->raw_capacity = size;
    return 1;
}

static void block_mark_changed(obor_block_state *state, uint32_t block)
{
    state->changed[block / 8] |= (unsigned char)(1U << (block % 8));
}

int obor_block_state_changed(const obor_block_state *state, uint32_t block)
{
    return !state || !state->valid || block >= BS_MAX_BLOCKS ||
           (state->changed[block / 8] & (1U << (block % 8))) != 0;
}

static int block_free_range(obor_block_state *state, uint32_t offset, uint32_t length)
{
    if (!length || offset < BS_TABLE_END || offset > state->high ||
        length > state->high - offset || offset % BS_ALIGN || length % BS_ALIGN) return 0;
    uint32_t left = 0, right = state->hole_count;
    while (left < right) {
        uint32_t middle = left + (right - left) / 2;
        if (state->holes[middle].offset < offset) left = middle + 1;
        else right = middle;
    }
    uint32_t i = left, end = offset + length;
    if ((i && state->holes[i - 1].offset + state->holes[i - 1].length > offset) ||
        (i < state->hole_count && state->holes[i].offset < end)) return 0;
    int before = i && state->holes[i - 1].offset + state->holes[i - 1].length == offset;
    int after = i < state->hole_count && state->holes[i].offset == end;
    if (!before && !after && state->hole_count >= BS_MAX_BLOCKS + 1) return 0;
    memset(state->image + offset, 0, length);
    if (before) {
        state->holes[i - 1].length += length;
        if (after) {
            state->holes[i - 1].length += state->holes[i].length;
            memmove(state->holes + i, state->holes + i + 1,
                    (state->hole_count - i - 1) * sizeof(block_hole));
            --state->hole_count;
        }
    } else if (after) {
        state->holes[i].offset = offset;
        state->holes[i].length += length;
    } else {
        memmove(state->holes + i + 1, state->holes + i,
                (state->hole_count - i) * sizeof(block_hole));
        state->holes[i] = (block_hole){offset, length};
        ++state->hole_count;
    }
    /* Only unoccupied suffixes can leave the published image. All occupied
     * slots keep their addresses, including states already held by a frontend. */
    if (state->hole_count) {
        block_hole *last = state->holes + state->hole_count - 1;
        if (last->offset + last->length == state->high) {
            state->high = last->offset;
            --state->hole_count;
        }
    }
    return 1;
}

static int block_release_slot(obor_block_state *state, block_entry *entry)
{
    if (!entry->capacity) return 1;
    if (!block_free_range(state, entry->offset, entry->capacity)) return 0;
    memset(entry, 0, sizeof(*entry));
    return 1;
}

static int block_compact(obor_block_state *state, uint32_t count)
{
    if (!state->compact_enabled || !count) return 1;
    block_entry *entries = (block_entry *)(state->image + sizeof(block_header));
    uint32_t budget = 512U << 10, examined = 0, candidates = 0;
    while (examined < count && examined < 512 && candidates < 4096 && budget) {
        if (state->compact_cursor >= count) state->compact_cursor = 0;
        block_entry *entry = entries + state->compact_cursor++;
        ++examined;
        uint32_t needed = (entry->stored + BS_ALIGN - 1) / BS_ALIGN * BS_ALIGN;
        uint32_t excess = entry->capacity - needed;
        /* Hysteresis avoids splitting a slot for minor codec fluctuations. */
        if (excess >= 1024 && excess >= entry->capacity / 4 && excess <= budget) {
            if (!block_free_range(state, entry->offset + needed, excess)) return 0;
            entry->capacity = needed;
            budget -= excess;
            state->work.compact_reclaimed += excess;
        }
        if (entry->capacity > budget / 2) continue;
        for (uint32_t i = 0; i < state->hole_count && candidates < 4096; ++i) {
            block_hole *hole = state->holes + i;
            ++candidates;
            if (hole->offset >= entry->offset) break;
            if (hole->length < entry->capacity) continue;
            uint32_t old = entry->offset, destination = hole->offset;
            hole->offset += entry->capacity;
            hole->length -= entry->capacity;
            if (!hole->length) {
                memmove(hole, hole + 1, (state->hole_count - i - 1) * sizeof(*hole));
                --state->hole_count;
            }
            memcpy(state->image + destination, state->image + old, entry->stored);
            memset(state->image + destination + entry->stored, 0, entry->capacity - entry->stored);
            if (!block_free_range(state, old, entry->capacity)) return 0;
            entry->offset = destination;
            budget -= 2 * entry->capacity;
            ++state->work.compact_moved;
            break;
        }
    }
    state->work.compact_examined += examined;
    state->work.compact_holes += candidates;
    state->work.compact_written += (512U << 10) - budget;
    return 1;
}

static uint32_t block_reserve_slot(obor_block_state *state, uint32_t size)
{
    for (uint32_t i = 0; i < state->hole_count; ++i) {
        block_hole *hole = state->holes + i;
        if (hole->length < size) continue;
        uint32_t offset = hole->offset;
        hole->offset += size;
        hole->length -= size;
        if (!hole->length) {
            memmove(hole, hole + 1, (state->hole_count - i - 1) * sizeof(*hole));
            --state->hole_count;
        }
        return offset;
    }
    if (size > state->capacity - state->high) return 0;
    uint32_t offset = state->high;
    state->high += size;
    return offset;
}

static int block_deflate(obor_block_state *state, const void *raw, uint32_t size,
                          void *output, uint32_t capacity)
{
    z_stream *stream = &state->deflater;
    if (deflateReset(stream) != Z_OK) return 0;
    stream->next_in = (Bytef *)raw;
    stream->avail_in = size;
    stream->next_out = output;
    stream->avail_out = capacity;
    if (deflate(stream, Z_FINISH) != Z_STREAM_END || stream->avail_in) return 0;
    return (int)(capacity - stream->avail_out);
}

/* Amortize mapping/epoch queries for a complete aligned group. The callback
 * must prove the entire span, including its interior. Any missing proof or
 * partial/grown/shrunk block retains the existing per-block path. No encoded
 * bytes, slot positions, ownership or state capacity change. */
#define BS_PROOF_GROUP 64U
static uint32_t block_proven_group(obor_block_state *state,
    const obor_block_source *source, uint32_t index, uint32_t raw_size)
{
    const uint32_t span = BS_PROOF_GROUP * BS_BLOCK;
    uint32_t offset = index * BS_BLOCK;
    if (!state->valid || !source->unchanged || index % BS_PROOF_GROUP ||
        offset > raw_size || span > raw_size - offset ||
        offset > state->raw_size || span > state->raw_size - offset) return 0;
    const block_entry *entries = (const block_entry *)(state->image + sizeof(block_header));
    for (uint32_t i = 0; i < BS_PROOF_GROUP; ++i)
        if (entries[index+i].raw != BS_BLOCK) return 0;
    uint64_t tick = block_tick(state);
    int proven = source->unchanged(source->context, offset, span);
    block_elapsed(state, tick, &state->timing.proof_ns);
    if (!proven) return 0;
    state->work.proven_blocks += BS_PROOF_GROUP;
    return BS_PROOF_GROUP;
}

static int block_encode(obor_block_state *, const obor_block_source *,
                        uint32_t, int, int, int);
#include "obor_block_worker.inc"

static int block_encode(obor_block_state *state, const obor_block_source *source,
                         uint32_t raw_size, int allow_repack, int initial_codec, int update_codec)
{
    if (!state || !source || !source->read) return 0;
#if defined(__linux__) && !defined(__ANDROID__)
    if (allow_repack && state->worker_enabled && state->valid && !state->clock &&
        raw_size >= BW_BATCH * BS_BLOCK) {
        int result = block_encode_worker(state, source, raw_size, initial_codec, update_codec);
        if (result >= 0) return result;
    }
#endif
    if (allow_repack) {
        memset(&state->work, 0, sizeof(state->work));
        memset(&state->timing, 0, sizeof(state->timing));
    }
    if (!block_reserve_raw(state, raw_size)) goto fail;
    uint32_t count = (raw_size + BS_BLOCK - 1) / BS_BLOCK;
    uint32_t old_count = (state->raw_size + BS_BLOCK - 1) / BS_BLOCK;
    block_entry *entries = (block_entry *)(state->image + sizeof(block_header));
    unsigned char scratch[BS_BLOCK], compressed[BS_BLOCK + 1024];
    memset(state->changed, 0, sizeof(state->changed));
    for (uint32_t i = count; i < old_count; ++i) {
        if (!block_release_slot(state, entries + i)) goto fail;
        block_mark_changed(state, i);
    }
    for (uint32_t i = 0; i < count; ++i) {
        uint32_t proven_group = block_proven_group(state, source, i, raw_size);
        if (proven_group) { i += proven_group - 1; continue; }
        uint32_t offset = i * BS_BLOCK, length = raw_size - offset;
        if (length > BS_BLOCK) length = BS_BLOCK;
        block_entry *entry = entries + i;
        int existing = state->valid && entry->raw == length &&
                       offset + length <= state->raw_size;
        uint64_t tick = block_tick(state);
        int proven = existing && source->unchanged &&
            source->unchanged(source->context, offset, length);
        block_elapsed(state, tick, &state->timing.proof_ns);
        if (proven) {
            ++state->work.proven_blocks;
            continue;
        }
        tick = block_tick(state);
        const void *raw = source->read(source->context, offset, length, scratch);
        block_elapsed(state, tick, &state->timing.read_ns);
        if (!raw) goto fail;
        ++state->work.read_blocks;
        state->work.read_bytes += length;
        tick = block_tick(state);
        int equal = existing && !memcmp(raw, state->raw + offset, length);
        block_elapsed(state, tick, &state->timing.compare_ns);
        if (equal) {
            ++state->work.equal_blocks;
            continue;
        }
        tick = block_tick(state);
        int codec = existing ? update_codec : initial_codec;
        int stored = codec == BS_RAW ? (int)length :
            codec == BS_LZ4 ? LZ4_compress_default(raw, (char *)compressed, (int)length, sizeof(compressed)) :
            block_deflate(state, raw, length, compressed, sizeof(compressed));
        block_elapsed(state, tick, &state->timing.compress_ns);
        if (stored <= 0) goto fail;
        tick = block_tick(state);
        if ((uint32_t)stored >= length) {
            codec = BS_RAW;
            stored = (int)length;
            memcpy(compressed, raw, length);
        }
        uint32_t capacity = ((uint32_t)stored + BS_ALIGN - 1) / BS_ALIGN * BS_ALIGN;
        if (entry->capacity < capacity) {
            if (!block_release_slot(state, entry)) goto fail;
            entry->offset = block_reserve_slot(state, capacity);
            if (!entry->offset) {
                /* Slot fragmentation and promotion of formerly cold blocks
                 * to the fast codec can exhaust the pool even when a complete
                 * compact image fits. Rebuild once from the current source,
                 * without dropping bytes or changing the frontend capacity.
                 * No output is published until the complete retry succeeds. */
                if (allow_repack) {
                    ++state->work.repacks;
                    obor_block_state_forget(state);
                    return block_encode(state, source, raw_size, 0, BS_DEFLATE, update_codec);
                }
                goto fail;
            }
            entry->capacity = capacity;
        }
        memcpy(state->image + entry->offset, compressed, (size_t)stored);
        memset(state->image + entry->offset + stored, 0, entry->capacity - (uint32_t)stored);
        entry->stored = (uint32_t)stored;
        entry->raw = length;
        entry->codec = (uint32_t)codec;
        block_elapsed(state, tick, &state->timing.slot_ns);
        tick = block_tick(state);
        entry->crc = obor_block_crc32(0, raw, length);
        block_elapsed(state, tick, &state->timing.crc_ns);
        tick = block_tick(state);
        memcpy(state->raw + offset, raw, length);
        block_mark_changed(state, i);
        block_elapsed(state, tick, &state->timing.cache_ns);
    }
    if (!block_compact(state, count)) goto fail;
    block_header header = {OBOR_BLOCK_STATE_MAGIC, BS_VERSION, BS_BLOCK,
                           count, raw_size, state->high, {0, 0}};
    memcpy(state->image, &header, sizeof(header));
    state->raw_size = raw_size;
    state->valid = 1;
    return 1;
fail:
    obor_block_state_forget(state);
    return 0;
}

static int block_encode_measured(obor_block_state *state, const obor_block_source *source,
                                  uint32_t raw_size, int initial_codec, int update_codec)
{
    uint64_t begin = block_cpu_now();
    /* Bounded repacks recurse below this wrapper. Their CPU work and any
     * joined helper belong to this one complete capture, without double count. */
    int result = block_encode(state, source, raw_size, 1, initial_codec, update_codec);
    if (state) state->work.owner_cpu_ns = result ? block_cpu_elapsed(begin) : 0;
    return result;
}

int obor_block_state_encode(obor_block_state *state, const obor_block_source *source,
                            uint32_t raw_size)
{ return block_encode_measured(state, source, raw_size, BS_DEFLATE, BS_LZ4); }

int obor_block_state_encode_fast(obor_block_state *state, const obor_block_source *source,
                                 uint32_t raw_size)
{ return block_encode_measured(state, source, raw_size, BS_LZ4, BS_LZ4); }

int obor_block_state_encode_mutable(obor_block_state *state, const obor_block_source *source,
                                    uint32_t raw_size)
{ return block_encode_measured(state, source, raw_size, BS_LZ4, BS_RAW); }

void obor_block_state_changes(const obor_block_state *state, obor_block_changes *out)
{
    if (!out) return;
    memset(out, 0, sizeof(*out));
    if (!state || !state->valid) return;
    *out = state->work;
    uint32_t count = (state->raw_size + BS_BLOCK - 1) / BS_BLOCK;
    const block_entry *entries = (const block_entry *)(state->image + sizeof(block_header));
    for (uint32_t i = 0; i < count; ++i) {
        out->total_stored_bytes += entries[i].stored;
        out->total_slot_bytes += entries[i].capacity;
        if (obor_block_state_changed(state, i)) {
            ++out->blocks; out->raw_bytes += entries[i].raw; out->slot_bytes += entries[i].capacity;
        }
    }
    out->pool_hole_bytes = state->high - BS_TABLE_END - out->total_slot_bytes;
}

uint32_t obor_block_state_workload(const obor_block_state *state)
{
    return state && state->valid ? state->work.read_blocks - state->work.equal_blocks : 0;
}

uint64_t obor_block_state_cpu_cost(const obor_block_state *state)
{
    if (!state || !state->valid || !state->work.owner_cpu_ns ||
        (state->work.worker_threads && !state->work.helper_cpu_ns)) return 0;
    if (state->work.owner_cpu_ns > UINT64_MAX - state->work.helper_cpu_ns) return 0;
    return state->work.owner_cpu_ns + state->work.helper_cpu_ns;
}

const void *obor_block_state_image(const obor_block_state *state, uint32_t *used)
{
    if (used) *used = state && state->valid ? state->high : 0;
    return state && state->valid ? state->image : NULL;
}

const void *obor_block_state_raw(const obor_block_state *state, uint32_t *size)
{
    if (size) *size = state && state->valid ? state->raw_size : 0;
    return state && state->valid ? state->raw : NULL;
}

static int block_read_entry(const unsigned char *image, const block_header *header,
                            uint32_t block, block_entry *entry)
{
    memcpy(entry, image + sizeof(*header) + block * sizeof(*entry), sizeof(*entry));
    uint32_t expected = header->raw - block * BS_BLOCK;
    if (expected > BS_BLOCK) expected = BS_BLOCK;
    return entry->raw == expected && entry->stored && entry->stored <= BS_BLOCK &&
           entry->codec <= BS_DEFLATE && entry->offset >= BS_TABLE_END &&
           entry->offset % BS_ALIGN == 0 && entry->capacity &&
           entry->capacity <= BS_BLOCK && entry->capacity % BS_ALIGN == 0 &&
           entry->stored <= entry->capacity && entry->offset <= header->used &&
           entry->capacity <= header->used - entry->offset &&
           (entry->codec != BS_RAW || entry->stored == entry->raw);
}

static int block_inflate(obor_block_state *state, const void *source, uint32_t size,
                         void *output, uint32_t length)
{
    z_stream *stream = &state->inflater;
    if (inflateReset(stream) != Z_OK) return 0;
    stream->next_in = (Bytef *)source;
    stream->avail_in = size;
    stream->next_out = output;
    stream->avail_out = length;
    return inflate(stream, Z_FINISH) == Z_STREAM_END &&
           !stream->avail_in && !stream->avail_out;
}

int obor_block_state_decode(obor_block_state *state, const void *data, uint32_t size)
{
    if (!state || !data) return 0;
    const unsigned char *image = data;
    block_header header;
    if (size < sizeof(header)) goto fail;
    memcpy(&header, image, sizeof(header));
    if (header.magic != OBOR_BLOCK_STATE_MAGIC || header.version != BS_VERSION ||
        header.block != BS_BLOCK || !header.raw || header.raw > OBOR_BLOCK_STATE_MAX_RAW ||
        header.count != (header.raw + BS_BLOCK - 1) / BS_BLOCK ||
        header.used < BS_TABLE_END || header.used > size ||
        header.used > state->capacity || header.used % BS_ALIGN ||
        header.reserved[0] || header.reserved[1]) goto fail;
    /* Reject an input alias which reallocating/writing the decoded cache could
     * invalidate. The immutable encoded cache itself may be read back. */
    uintptr_t input = (uintptr_t)data, raw_address = (uintptr_t)state->raw;
    if (input > UINTPTR_MAX - size || raw_address > UINTPTR_MAX - state->raw_capacity ||
        (state->raw && input < raw_address + state->raw_capacity && raw_address < input + size))
        goto fail;
    memset(state->occupied, 0, BS_OCCUPIED_BYTES);
    for (uint32_t i = 0; i < header.count; ++i) {
        block_entry entry;
        if (!block_read_entry(image, &header, i, &entry)) goto fail;
        for (uint32_t quantum = entry.offset / BS_ALIGN;
             quantum < (entry.offset + entry.capacity) / BS_ALIGN; ++quantum) {
            unsigned char bit = (unsigned char)(1U << (quantum % 8));
            if (state->occupied[quantum / 8] & bit) goto fail;
            state->occupied[quantum / 8] |= bit;
        }
    }
    if (!block_reserve_raw(state, header.raw)) goto fail;
    block_entry *previous = (block_entry *)(state->image + sizeof(block_header));
    unsigned char restored[BS_BLOCK];
    memset(state->changed, 0, sizeof(state->changed));
    for (uint32_t i = 0; i < header.count; ++i) {
        block_entry entry;
        if (!block_read_entry(image, &header, i, &entry)) goto fail;
        uint32_t offset = i * BS_BLOCK;
        int existing = state->valid && offset + entry.raw <= state->raw_size;
        const block_entry *old = previous + i;
        if (existing && old->raw == entry.raw && old->stored == entry.stored &&
            old->codec == entry.codec && old->crc == entry.crc &&
            !memcmp(state->image + old->offset, image + entry.offset, entry.stored))
            continue;
        if (entry.codec == BS_RAW) memcpy(restored, image + entry.offset, entry.raw);
        else if (entry.codec == BS_LZ4) {
            if (LZ4_decompress_safe((const char *)image + entry.offset, (char *)restored,
                                    (int)entry.stored, (int)entry.raw) != (int)entry.raw)
                goto fail;
        } else if (!block_inflate(state, image + entry.offset, entry.stored, restored, entry.raw))
            goto fail;
        if (obor_block_crc32(0, restored, entry.raw) != entry.crc) goto fail;
        if (!existing || memcmp(state->raw + offset, restored, entry.raw)) {
            memcpy(state->raw + offset, restored, entry.raw);
            block_mark_changed(state, i);
        }
    }
    /* The entry table and pool have been validated before they become trusted
     * cache metadata. Unused table entries never influence a subsequent grow. */
    memmove(state->image, image, header.used);
    memset(state->image + sizeof(header) + header.count * sizeof(block_entry), 0,
            BS_TABLE_END - sizeof(header) - header.count * sizeof(block_entry));
    state->raw_size = header.raw;
    state->compact_cursor = 0;
    state->high = header.used;
    state->hole_count = 0;
    uint32_t begin = BS_TABLE_END / BS_ALIGN, limit = header.used / BS_ALIGN;
    while (begin < limit) {
        if (state->occupied[begin / 8] & (1U << (begin % 8))) { ++begin; continue; }
        uint32_t end = begin + 1;
        while (end < limit && !(state->occupied[end / 8] & (1U << (end % 8)))) ++end;
        if (state->hole_count >= BS_MAX_BLOCKS + 1) goto fail;
        state->holes[state->hole_count++] = (block_hole){begin * BS_ALIGN, (end - begin) * BS_ALIGN};
        memset(state->image + begin * BS_ALIGN, 0, (end - begin) * BS_ALIGN);
        begin = end;
    }
    state->valid = 1;
    return 1;
fail:
    obor_block_state_forget(state);
    return 0;
}
