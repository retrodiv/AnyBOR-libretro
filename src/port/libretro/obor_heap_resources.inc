/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
/* Included after the ordinary sparse-heap reader in obor_alloc.c. OBS4 uses
 * the block writer's at-most-two dense live-heap spans, excluding only the
 * unused top chunk interior. The manifest must describe real live allocations
 * and zero-filled body ranges wholly represented by that logical heap. */
static const unsigned char *heap_resource_bytes(const void *source, uint64_t offset, uint64_t length)
{
    obor_heap_sparse_header header;
    memcpy(&header, source, sizeof(header));
    const unsigned char *cursor = (const unsigned char *)source + sizeof(header);
    for (uint32_t i = 0; i < header.count; ++i) {
        obor_heap_sparse_span span;
        memcpy(&span, cursor, sizeof(span)); cursor += sizeof(span);
        if (offset >= span.offset && offset - span.offset <= span.length &&
            length <= span.length - (offset - span.offset)) return cursor + offset - span.offset;
        cursor += span.length;
    }
    return NULL;
}

/* Read only from the incoming snapshot, never from the current mutable arena.
 * Check the allocator metadata as well as the sparse span before exposing a
 * source for deterministic output reconstruction. */
const void *obor_heap_resource_snapshot_read(const void *source, uint64_t length,
        uint64_t arena_used, uint32_t owner, uint32_t allocation,
        uint32_t body, uint32_t bytes)
{
    if (!source || !bytes || owner < OBOR_STACK_RESERVE + 2 * sizeof(size_t) ||
        (owner & CHUNK_ALIGN_MASK) || owner > arena_used ||
        allocation > arena_used - owner || body < owner ||
        body - owner > allocation || bytes > allocation - (body - owner) ||
        !obor_heap_sparse_validate(source, length, arena_used)) return NULL;
    uint64_t offset = owner - OBOR_STACK_RESERVE;
    const unsigned char *head = heap_resource_bytes(source, offset - sizeof(size_t), sizeof(size_t));
    if (!head || !heap_resource_bytes(source, offset, allocation)) return NULL;
    size_t bits; memcpy(&bits, head, sizeof(bits));
    size_t chunk_size = bits & ~FLAG_BITS;
    if (!(bits & CINUSE_BIT) || chunk_size < MIN_CHUNK_SIZE ||
        (chunk_size & CHUNK_ALIGN_MASK) || chunk_size - SIZE_T_SIZE != allocation) return NULL;
    const unsigned char *next = heap_resource_bytes(source, offset + allocation, sizeof(size_t));
    if (!next) return NULL;
    memcpy(&bits, next, sizeof(bits));
    if (!(bits & PINUSE_BIT)) return NULL;
    return heap_resource_bytes(source, body - OBOR_STACK_RESERVE, bytes);
}

int obor_heap_resources_validate(const void *source, uint64_t length,
        uint64_t arena_used, const obor_resource_restore *plan)
{
    if (!plan || !obor_heap_sparse_validate(source, length, arena_used)) return 0;
    obor_heap_sparse_header header;
    memcpy(&header, source, sizeof(header));
    if (header.reserved || !header.count || header.count > 2) return 0;
    const unsigned char *cursor = (const unsigned char *)source + sizeof(header);
    uint64_t previous = 0;
    for (uint32_t i = 0; i < header.count; ++i) {
        obor_heap_sparse_span span;
        memcpy(&span, cursor, sizeof(span)); cursor += sizeof(span);
        if (span.offset < previous || (!i && span.offset)) return 0;
        previous = span.offset + span.length; cursor += span.length;
    }
    for (uint32_t i = 0; i < obor_resource_restore_slots(plan); ++i) {
        uint32_t owner, allocation;
        if (!obor_resource_restore_allocation(plan, i, &owner, &allocation)) continue;
        if (owner < OBOR_STACK_RESERVE + 2 * sizeof(size_t) || (owner & CHUNK_ALIGN_MASK)) return 0;
        uint64_t offset = owner - OBOR_STACK_RESERVE;
        const unsigned char *head = heap_resource_bytes(source, offset - sizeof(size_t), sizeof(size_t));
        if (!head || !heap_resource_bytes(source, offset, allocation)) return 0;
        size_t bits; memcpy(&bits, head, sizeof(bits));
        size_t chunk_size = bits & ~FLAG_BITS;
        if (!(bits & CINUSE_BIT) || chunk_size < MIN_CHUNK_SIZE ||
            (chunk_size & CHUNK_ALIGN_MASK) || chunk_size - SIZE_T_SIZE != allocation) return 0;
        const unsigned char *next = heap_resource_bytes(source, offset + allocation, sizeof(size_t));
        if (!next) return 0;
        memcpy(&bits, next, sizeof(bits));
        if (!(bits & PINUSE_BIT)) return 0;
    }
    for (uint32_t i = 0; i < obor_resource_restore_count(plan); ++i) {
        uint32_t offset, bytes;
        if (!obor_resource_restore_range(plan, i, &offset, &bytes) || offset < OBOR_STACK_RESERVE) return 0;
        const unsigned char *body = heap_resource_bytes(source, offset - OBOR_STACK_RESERVE, bytes);
        if (!body) return 0;
        while (bytes >= sizeof(uint64_t)) {
            uint64_t value; memcpy(&value, body, sizeof(value));
            if (value) return 0;
            body += sizeof(value); bytes -= sizeof(value);
        }
        while (bytes--) if (*body++) return 0;
    }
    return 1;
}

int obor_heap_resources_restore(const void *source, uint64_t length,
        uint64_t arena_used, const obor_resource_restore *plan)
{
    /* Preflight already validated resource ownership/zeros before any live
     * state was touched. This inexpensive structural check guards the copy. */
    if (!plan || !obor_heap_sparse_validate(source, length, arena_used)) return 0;
    obor_heap_sparse_header header;
    memcpy(&header, source, sizeof(header));
    const unsigned char *cursor = (const unsigned char *)source + sizeof(header);
    for (uint32_t i = 0; i < header.count; ++i) {
        obor_heap_sparse_span span;
        memcpy(&span, cursor, sizeof(span)); cursor += sizeof(span);
        obor_resource_restore_copy(plan, (uint32_t)(OBOR_STACK_RESERVE + span.offset),
            cursor, (uint32_t)span.length);
        cursor += span.length;
    }
    return 1;
}
