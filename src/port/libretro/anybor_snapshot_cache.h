/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_SNAPSHOT_CACHE_H
#define OBOR_SNAPSHOT_CACHE_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>

/* The caller owns two immutable snapshots. A destination can be two captures
 * old; the comparison oracle is the immediately preceding snapshot instead.
 * Keep those epochs separate. No game data or previous image is retained here. */
typedef struct {
    void *buffer;
    uint64_t epoch;
    size_t used, heap_offset, heap_length;
} obor_snapshot_slot;

typedef struct {
    obor_snapshot_slot slot[2];
    uint64_t previous_epoch;
    size_t previous_used, previous_heap_offset, previous_heap_length;
} obor_snapshot_cache;

typedef uint64_t (*obor_snapshot_page_epoch)(size_t);
typedef void (*obor_snapshot_range)(void *, size_t, size_t);

/* Inputs have been bounded by the state writer. Emit a conservative set of
 * possible changes and copy every page newer than the destination. The first
 * capture initializes the complete advertised buffer, including dirty padding.
 * emit may coalesce/overflow to a single full range without affecting copies. */
static inline void obor_snapshot_copy(obor_snapshot_cache *cache, unsigned index,
    const void *heap, size_t heap_offset, size_t heap_length, size_t used,
    size_t capacity, size_t page_size, uint64_t epoch,
    obor_snapshot_page_epoch changed, obor_snapshot_range emit, void *context)
{
    obor_snapshot_slot *slot = &cache->slot[index];
    unsigned char *output = (unsigned char *)slot->buffer;
    int same_previous = cache->previous_epoch &&
        cache->previous_heap_offset == heap_offset;
    int same_slot = slot->epoch && slot->heap_offset == heap_offset;
    if (!same_previous) emit(context, 0, capacity);
    else {
        emit(context, 0, heap_offset);
    }
    for (size_t offset = 0; offset < heap_length; offset += page_size) {
        size_t length = heap_length - offset;
        if (length > page_size) length = page_size;
        uint64_t written = changed(offset / page_size);
        if (!same_slot || offset + length > slot->heap_length || written > slot->epoch)
            memcpy(output + heap_offset + offset,
                   (const unsigned char *)heap + offset, length);
        /* A growing heap exposes bytes previously occupied by the stack or
         * padding, even if that page has an old write epoch. Its base offset
         * still matches: compare only changed/added pages, not the entire
         * advertised state. Shrinkage is covered by the tail range below. */
        if (same_previous && (written > cache->previous_epoch ||
                              offset + length > cache->previous_heap_length))
            emit(context, heap_offset + offset, length);
    }
    if (same_previous) {
        size_t tail = used > cache->previous_used ? used : cache->previous_used;
        emit(context, heap_offset + heap_length, tail - heap_offset - heap_length);
    }
    size_t clear_end = slot->epoch ? slot->used : capacity;
    if (clear_end > used) memset(output + used, 0, clear_end - used);
    slot->epoch = epoch;
    slot->used = used;
    slot->heap_offset = heap_offset;
    slot->heap_length = heap_length;
    cache->previous_epoch = epoch;
    cache->previous_used = used;
    cache->previous_heap_offset = heap_offset;
    cache->previous_heap_length = heap_length;
}
#endif
