/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_snapshot_cache.h"
#include <assert.h>
#include <stdio.h>

enum { PAGE = 64, CAPACITY = 1024, PREFIX = 48, PAGES = 12 };
static unsigned char heap[PAGES * PAGE], buffers[2][CAPACITY];
static unsigned char previous[CAPACITY], full[CAPACITY], hinted[CAPACITY];
static uint64_t page_epochs[PAGES];
static uint64_t page_epoch(size_t i) { assert(i < PAGES); return page_epochs[i]; }
typedef struct { size_t end; unsigned count; unsigned char *snapshot; } ranges;
static void emit(void *context, size_t offset, size_t length)
{
    ranges *r = context;
    assert(offset <= CAPACITY && length <= CAPACITY - offset);
    assert(!r->count || offset >= r->end);
    r->end = offset + length;
    ++r->count;
    /* Patch oracle: update only hinted bytes of the preceding full image. */
}
static void apply(void *context, size_t offset, size_t length)
{
    ranges *r = context;
    emit(context, offset, length);
    memcpy(hinted + offset, r->snapshot + offset, length);
}

int main(void)
{
    obor_snapshot_cache cache = {0};
    cache.slot[0].buffer = buffers[0];
    cache.slot[1].buffer = buffers[1];
    memset(buffers, 0xa5, sizeof(buffers));
    memset(previous, 0x7b, sizeof(previous));
    size_t extent = 3 * PAGE + 13;
    unsigned index = 0;
    for (uint64_t epoch = 1; epoch <= 800; ++epoch) {
        if (epoch == 8) extent = 6 * PAGE; /* growth */
        if (epoch == 25) extent += 7; /* growth within an existing page */
        if (epoch == 60) extent = 4 * PAGE; /* shrinking heap */
        /* Growth exposes bytes whose write epoch predates the preceding
         * snapshot, and shrinkage replaces old heap bytes with tail/padding. */
        if (epoch >= 90 && epoch < 260)
            extent = (epoch % PAGES + 1) * PAGE - epoch % 13;
        size_t prefix = PREFIX + (epoch >= 300 && epoch < 350 ? 16 : 0);
        if (epoch == 400) { /* restore invalidates both slots and oracle */
            cache.slot[0].epoch = cache.slot[1].epoch = cache.previous_epoch = 0;
            memset(buffers, 0xb6, sizeof(buffers));
            memset(page_epochs, 0, sizeof(page_epochs));
        }
        size_t page = (epoch * 7) % ((extent + PAGE - 1) / PAGE);
        size_t offset = page * PAGE;
        heap[offset] ^= (unsigned char)(epoch | 1);
        page_epochs[page] = epoch;
        size_t used = prefix + extent + (size_t)(epoch % 17 + 1);
        memset(full, 0, sizeof(full));
        memset(full, (unsigned char)epoch, prefix);
        memcpy(full + prefix, heap, extent);
        memset(full + prefix + extent, (unsigned char)(epoch + 9), used - prefix - extent);
        memcpy(buffers[index], full, prefix);
        memcpy(buffers[index] + prefix + extent, full + prefix + extent,
               used - prefix - extent);
        ranges r = {0, 0, buffers[index]};
        /* Save range events before copy to replay against a complete reference. */
        obor_snapshot_cache prior = cache;
        obor_snapshot_copy(&cache, index, heap, prefix, extent, used, CAPACITY,
                           PAGE, epoch, page_epoch, emit, &r);
        assert(memcmp(buffers[index], full, CAPACITY) == 0);
        /* Changing only the extent must never turn unused state capacity
         * into a full comparison. Offset changes still require fallback. */
        if (prior.previous_epoch && prior.previous_heap_offset == prefix)
            assert(r.end <= (used > prior.previous_used ? used : prior.previous_used));
        memcpy(hinted, previous, sizeof(hinted));
        r.end = r.count = 0;
        obor_snapshot_copy(&prior, index, heap, prefix, extent, used, CAPACITY,
                           PAGE, epoch, page_epoch, apply, &r);
        assert(memcmp(hinted, full, CAPACITY) == 0);
        memcpy(previous, full, CAPACITY);
        /* Sometimes reuse the same destination: no hardcoded alternation. */
        if (epoch % 5) index ^= 1;
    }
    puts("snapshot_cache_passed=1 captures=800 full_images=800 hint_images=800");
    return 0;
}
