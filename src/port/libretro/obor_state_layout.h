/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_STATE_LAYOUT_H
#define OBOR_STATE_LAYOUT_H
#include "obor_resource_catalog.h"

#define OBOR_STATE_STACK_WINDOW (4U << 20)
#define OBOR_STATE_MANIFEST_WINDOW (OBOR_RESOURCE_MANIFEST_HEADER + \
    OBOR_RESOURCE_CATALOG_LIMIT * OBOR_RESOURCE_MANIFEST_RECORD)
#define OBOR_STATE_HEAP_ALIGNMENT 16384U
#define OBOR_STATE_SPARSE_PREFIX 48U /* OHS2 header and first span descriptor */

typedef struct { uint32_t stack, manifest, heap; } obor_state_resource_offsets;

/* OBS6 keeps the OHS2 heap bytes intact and inserts a zero-only gap before
 * its header. The first live heap byte then has the same16KiB alignment as
 * the fixed arena heap. A codec block no longer straddles two16KiB tracked
 * pages merely because the module/context prefix had an unrelated size. */
static uint32_t obor_state_resource_heap_padding(uint64_t heap)
{
    return (OBOR_STATE_HEAP_ALIGNMENT -
        ((heap % OBOR_STATE_HEAP_ALIGNMENT + OBOR_STATE_SPARSE_PREFIX) %
         OBOR_STATE_HEAP_ALIGNMENT)) % OBOR_STATE_HEAP_ALIGNMENT;
}

/* OBS5 places these windows after the fixed module/context prefix. No arena
 * high-water mark, stack depth or catalog slot count can move another region.
 * All returned offsets are checked before any pointer into input is formed. */
static int obor_state_resource_layout_aligned(uint64_t prefix, uint64_t stack_length,
        uint64_t heap_length, uint32_t size, int aligned, obor_state_resource_offsets *out)
{
    if (!out || stack_length > OBOR_STATE_STACK_WINDOW || prefix > size ||
        OBOR_STATE_STACK_WINDOW > size - prefix) return 0;
    uint64_t manifest = prefix + OBOR_STATE_STACK_WINDOW;
    if (OBOR_STATE_MANIFEST_WINDOW > size - manifest) return 0;
    uint64_t heap = manifest + OBOR_STATE_MANIFEST_WINDOW;
    if (aligned) {
        uint32_t padding = obor_state_resource_heap_padding(heap);
        if (padding > size - heap) return 0;
        heap += padding;
    }
    if (heap_length != size - heap) return 0;
    *out = (obor_state_resource_offsets){(uint32_t)(manifest - stack_length),
        (uint32_t)manifest, (uint32_t)heap};
    return 1;
}

static int obor_state_resource_layout(uint64_t prefix, uint64_t stack_length,
        uint64_t heap_length, uint32_t size, obor_state_resource_offsets *out)
{
    return obor_state_resource_layout_aligned(prefix, stack_length, heap_length,
        size, 0, out);
}

/* The enclosing fixed window is validated first. The catalog parser still
 * validates every header, owner and recipe field in this bounded slice. */
static uint32_t obor_state_manifest_length(const void *input, uint32_t available)
{
    if (!input || available < OBOR_RESOURCE_MANIFEST_HEADER) return 0;
    const unsigned char *p = (const unsigned char *)input + 8;
    uint32_t slots = (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
    if (slots > OBOR_RESOURCE_CATALOG_LIMIT) return 0;
    uint32_t size = OBOR_RESOURCE_MANIFEST_HEADER + slots * OBOR_RESOURCE_MANIFEST_RECORD;
    return size <= available ? size : 0;
}
#endif
