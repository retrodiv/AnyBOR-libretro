/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_STATE_STREAM_H
#define OBOR_STATE_STREAM_H
#include <stdint.h>
#include <string.h>

enum { OBOR_STATE_BYTES, OBOR_STATE_HEAP, OBOR_STATE_ZERO, OBOR_STATE_MANIFEST };
typedef struct {
    uint32_t offset, length;
    const unsigned char *address;
    int kind;
} obor_state_part;
/* A heap reader fills the entire requested output span or reports failure.
 * It may materialize verified zero ranges without reading their live bodies. */
typedef int (*obor_state_heap_reader)(void *, const unsigned char *, void *, uint32_t);

static int obor_state_part_add(obor_state_part *parts, uint32_t capacity,
        uint32_t *count, uint32_t *total, const void *address, uint64_t length, int kind)
{
    if (!length) return 1;
    if (kind < OBOR_STATE_BYTES || kind > OBOR_STATE_MANIFEST ||
        (kind != OBOR_STATE_ZERO && !address) ||
        length > UINT32_MAX - *total || *count >= capacity) return 0;
    parts[(*count)++] = (obor_state_part){*total, (uint32_t)length,
        kind == OBOR_STATE_ZERO ? NULL : address, kind};
    *total += (uint32_t)length;
    return 1;
}

static const void *obor_state_part_read(const obor_state_part *parts, uint32_t count,
        uint32_t total, uint32_t offset, uint32_t length, void *scratch,
        obor_state_heap_reader heap_reader, void *context)
{
    if (offset > total || length > total - offset || (!scratch && length)) return NULL;
    uint32_t done = 0;
    for (uint32_t i = 0; i < count && done < length; ++i) {
        const obor_state_part *part = parts + i;
        if (offset >= part->offset + part->length) continue;
        if (offset < part->offset) return NULL;
        uint32_t inside = offset - part->offset, n = part->length - inside;
        if (n >= length && !done && part->kind != OBOR_STATE_ZERO &&
            !(part->kind == OBOR_STATE_HEAP && heap_reader)) return part->address + inside;
        if (n > length - done) n = length - done;
        unsigned char *out = (unsigned char *)scratch + done;
        if (part->kind == OBOR_STATE_ZERO) memset(out, 0, n);
        else if (part->kind == OBOR_STATE_HEAP && heap_reader) {
            if (!heap_reader(context, part->address + inside, out, n)) return NULL;
        } else memcpy(out, part->address + inside, n);
        done += n; offset += n;
    }
    return done == length ? scratch : NULL;
}

/* A dirty-page proof can only be reused for the same physical bytes at the
 * same logical offsets. Zero windows have no physical owner; their overlap
 * remains unchanged even when a neighbouring stack/manifest slice grows. */
static int obor_state_part_mapped(const obor_state_part *part,
        const obor_state_part *previous, uint32_t count, uint32_t offset, uint32_t length)
{
    if (!length || offset < part->offset || offset - part->offset > part->length ||
        length > part->length - (offset - part->offset)) return 0;
    for (uint32_t j = 0; j < count; ++j) {
        const obor_state_part *old = previous + j;
        if (old->kind != part->kind || offset < old->offset ||
            offset - old->offset > old->length || length > old->length - (offset - old->offset)) continue;
        if (part->kind == OBOR_STATE_ZERO ||
            old->address + (offset - old->offset) == part->address + (offset - part->offset)) return 1;
    }
    return 0;
}
#endif
