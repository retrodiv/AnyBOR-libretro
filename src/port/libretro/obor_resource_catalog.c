/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_resource_catalog.h"
#include "obor_framebuffer_state.h"
#include <stdlib.h>
#include <string.h>

#define CATALOG_BUCKETS (OBOR_RESOURCE_CATALOG_LIMIT * 2U)
#define CATALOG_EMPTY UINT32_MAX
#define CATALOG_ACTIVE 1U
#define CATALOG_OMITTED 2U
typedef struct {
    uint32_t owner, allocation, body, flags, next_free;
    int checked;
    uint64_t manifest_changed;
    obor_resource_recipe recipe;
} catalog_entry;
typedef struct { uint32_t offset, length, slot; } catalog_range;
struct obor_resource_catalog {
    obor_resource_materializer *materializer;
    obor_resource_image_allocator allocator;
    unsigned char *arena, *manifest;
    catalog_entry *entries;
    uint32_t *buckets;
    catalog_range *ranges;
    uint32_t arena_size, capacity, slots, free_slot, active, tombstones;
    uint32_t range_count, manifest_size, manifest_capacity, framebuffer_slot;
    uint64_t generation;
    uint32_t proof_begin, proof_end;
    int proofs_checked;
};
struct obor_resource_restore {
    obor_resource_catalog *target;
    obor_resource_image_allocator allocator;
    unsigned char *staging;
    uint32_t *staged_offsets;
    size_t staged_size;
};

static uint32_t catalog_u32(const unsigned char *p)
{ return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24; }
static void catalog_put(unsigned char *p, uint32_t value)
{ for (unsigned i = 0; i < 4; ++i) p[i] = (unsigned char)(value >> (i * 8)); }
static uint32_t catalog_hash(uint32_t owner)
{
    owner ^= owner >> 16; owner *= UINT32_C(0x7feb352d);
    owner ^= owner >> 15; owner *= UINT32_C(0x846ca68b);
    return (owner ^ (owner >> 16)) % CATALOG_BUCKETS;
}

static int catalog_bounds(const obor_resource_catalog *c, const catalog_entry *e, uint32_t used)
{
    if (!(used <= c->arena_size && e->allocation && e->owner < used &&
        e->allocation <= used - e->owner && e->body >= e->owner &&
        e->body - e->owner < e->allocation && e->recipe.length <= e->allocation - (e->body - e->owner))) return 0;
    if (e->recipe.kind == OBOR_RESOURCE_ABGR32_FRAME) {
        obor_framebuffer_source s;
        if (!obor_resource_recipe_framebuffer_source(&e->recipe, &s) || s.owner == e->owner ||
            s.owner >= used || s.allocation > used - s.owner || s.offset < s.owner ||
            s.offset - s.owner > s.allocation || e->recipe.length > s.allocation - (s.offset - s.owner) ||
            (s.offset < e->body + e->recipe.length && e->body < s.offset + e->recipe.length)) return 0;
    }
    return 1;
}

/* A frame can derive only from ordinary saved bytes. No resource dependency
 * graph, mutable-body cache or reconstruction cycle is introduced. */
static int catalog_frame_source_raw(const obor_resource_catalog *c, const catalog_entry *frame)
{
    obor_framebuffer_source source;
    if (!obor_resource_recipe_framebuffer_source(&frame->recipe, &source)) return 0;
    for (uint32_t i = 0; i < c->slots; ++i) {
        const catalog_entry *e = c->entries + i;
        if ((e->flags & CATALOG_OMITTED) && source.offset < e->body + e->recipe.length &&
            e->body < source.offset + frame->recipe.length) return 0;
    }
    return 1;
}

static uint32_t catalog_find(const obor_resource_catalog *c, uint32_t owner, uint32_t *bucket)
{
    uint32_t at = catalog_hash(owner), tombstone = CATALOG_EMPTY;
    for (uint32_t count = 0; count < CATALOG_BUCKETS; ++count, at = (at + 1) % CATALOG_BUCKETS) {
        uint32_t value = c->buckets[at];
        if (!value) { *bucket = tombstone != CATALOG_EMPTY ? tombstone : at; return CATALOG_EMPTY; }
        if (value == CATALOG_EMPTY) { if (tombstone == CATALOG_EMPTY) tombstone = at; continue; }
        if (c->entries[value - 1].owner == owner) { *bucket = at; return value - 1; }
    }
    *bucket = tombstone;
    return CATALOG_EMPTY;
}

static int catalog_grow(obor_resource_catalog *c, uint32_t needed)
{
    if (needed > OBOR_RESOURCE_CATALOG_LIMIT) return 0;
    if (needed <= c->capacity) return 1;
    uint32_t capacity = c->capacity ? c->capacity : 64;
    while (capacity < needed) capacity *= 2;
    catalog_entry *entries = c->allocator.allocate((size_t)capacity * sizeof(*entries));
    catalog_range *ranges = c->allocator.allocate((size_t)capacity * sizeof(*ranges));
    if (!entries || !ranges) { c->allocator.release(entries); c->allocator.release(ranges); return 0; }
    memset(entries, 0, (size_t)capacity * sizeof(*entries));
    if (c->slots) memcpy(entries, c->entries, (size_t)c->slots * sizeof(*entries));
    if (c->range_count) memcpy(ranges, c->ranges, (size_t)c->range_count * sizeof(*ranges));
    c->allocator.release(c->entries); c->allocator.release(c->ranges);
    c->entries = entries; c->ranges = ranges; c->capacity = capacity;
    return 1;
}

static int catalog_manifest_reserve(obor_resource_catalog *c)
{
    /* Match the bounded geometric slot reserve, including after a load.
     * Only manifest_size bytes are initialized and published. New owners must
     * not allocate/free the complete manifest at every subsequent capture. */
    if (c->slots > c->capacity || c->capacity > OBOR_RESOURCE_CATALOG_LIMIT ||
        c->capacity > (UINT32_MAX - OBOR_RESOURCE_MANIFEST_HEADER) / OBOR_RESOURCE_MANIFEST_RECORD) return 0;
    uint32_t bytes = OBOR_RESOURCE_MANIFEST_HEADER + c->capacity * OBOR_RESOURCE_MANIFEST_RECORD;
    if (bytes <= c->manifest_capacity) return 1;
    unsigned char *manifest = c->allocator.allocate(bytes);
    if (!manifest) return 0;
    c->allocator.release(c->manifest);
    c->manifest = manifest; c->manifest_capacity = bytes;
    return 1;
}

obor_resource_catalog *obor_resource_catalog_create(obor_resource_materializer *m,
        const obor_resource_image_allocator *allocator, void *arena, uint32_t arena_size)
{
    if (!m || !allocator || !allocator->allocate || !allocator->release || !arena || !arena_size) return NULL;
    obor_resource_catalog *c = allocator->allocate(sizeof(*c));
    if (!c) return NULL;
    memset(c, 0, sizeof(*c));
    c->allocator = *allocator; c->materializer = m; c->arena = arena; c->arena_size = arena_size;
    c->free_slot = c->framebuffer_slot = CATALOG_EMPTY; c->generation = 1;
    c->buckets = allocator->allocate((size_t)CATALOG_BUCKETS * sizeof(*c->buckets));
    if (!c->buckets) { allocator->release(c); return NULL; }
    memset(c->buckets, 0, (size_t)CATALOG_BUCKETS * sizeof(*c->buckets));
    return c;
}

void obor_resource_catalog_destroy(obor_resource_catalog *c)
{
    if (!c) return;
    c->allocator.release(c->manifest); c->allocator.release(c->entries);
    c->allocator.release(c->ranges); c->allocator.release(c->buckets); c->allocator.release(c);
}

static void catalog_reindex(obor_resource_catalog *c)
{
    memset(c->buckets, 0, (size_t)CATALOG_BUCKETS * sizeof(*c->buckets));
    c->tombstones = 0;
    for (uint32_t slot = 0; slot < c->slots; ++slot) if (c->entries[slot].flags & CATALOG_ACTIVE) {
        uint32_t at;
        (void)catalog_find(c, c->entries[slot].owner, &at);
        if (at != CATALOG_EMPTY) c->buckets[at] = slot + 1;
    }
}

void obor_resource_catalog_remove(obor_resource_catalog *c, uint32_t owner)
{
    if (!c) return;
    uint32_t at, slot = catalog_find(c, owner, &at);
    if (slot == CATALOG_EMPTY) return;
    if (slot == c->framebuffer_slot) c->framebuffer_slot = CATALOG_EMPTY;
    c->buckets[at] = CATALOG_EMPTY; ++c->tombstones;
    memset(c->entries + slot, 0, sizeof(*c->entries));
    c->entries[slot].next_free = c->free_slot; c->free_slot = slot;
    --c->active;
    c->entries[slot].manifest_changed = ++c->generation;
    c->manifest_size = c->range_count = 0;
    if (c->tombstones > OBOR_RESOURCE_CATALOG_LIMIT / 2) catalog_reindex(c);
}

int obor_resource_catalog_add(obor_resource_catalog *c, uint32_t owner, uint32_t allocation,
        uint32_t body, const obor_resource_recipe *recipe)
{
    if (!c) return 0;
    obor_resource_catalog_remove(c, owner);
    if (!obor_resource_recipe_valid(recipe) || c->active == OBOR_RESOURCE_CATALOG_LIMIT) return 0;
    catalog_entry candidate;
    memset(&candidate, 0, sizeof(candidate));
    candidate.owner = owner; candidate.allocation = allocation; candidate.body = body;
    candidate.flags = CATALOG_ACTIVE; candidate.recipe = *recipe;
    if (!catalog_bounds(c, &candidate, c->arena_size)) return 0;
    if (recipe->kind == OBOR_RESOURCE_ABGR32_FRAME) {
        if (c->framebuffer_slot != CATALOG_EMPTY) return 0;
    } else {
        const void *derived = obor_resource_recipe_body(c->materializer, recipe);
        if (!derived || memcmp(c->arena + body, derived, recipe->length)) return 0;
    }
    uint32_t at, slot = catalog_find(c, owner, &at);
    if (slot != CATALOG_EMPTY || at == CATALOG_EMPTY) return 0;
    if (c->free_slot != CATALOG_EMPTY) {
        slot = c->free_slot; c->free_slot = c->entries[slot].next_free;
    } else {
        if (!catalog_grow(c, c->slots + 1)) return 0;
        slot = c->slots++;
    }
    if (c->buckets[at] == CATALOG_EMPTY) --c->tombstones;
    c->buckets[at] = slot + 1; c->entries[slot] = candidate;
    if (recipe->kind == OBOR_RESOURCE_ABGR32_FRAME) c->framebuffer_slot = slot;
    ++c->active;
    c->entries[slot].manifest_changed = ++c->generation;
    c->manifest_size = c->range_count = 0;
    return 1;
}

int obor_resource_catalog_framebuffer(obor_resource_catalog *c, uint32_t owner,
        uint32_t allocation, uint32_t body, const obor_resource_recipe *recipe)
{
    if (!c) return 0;
    if (c->framebuffer_slot != CATALOG_EMPTY) {
        const catalog_entry *e = c->entries + c->framebuffer_slot;
        if (recipe && e->owner == owner && e->allocation == allocation && e->body == body &&
            obor_resource_recipe_equal(&e->recipe, recipe)) return 1;
        obor_resource_catalog_remove(c, e->owner);
    }
    if (!recipe) return 1;
    if (recipe->kind != OBOR_RESOURCE_ABGR32_FRAME) return 0;
    return obor_resource_catalog_add(c, owner, allocation, body, recipe);
}

uint64_t obor_resource_catalog_generation(const obor_resource_catalog *c)
{ return c ? c->generation : 0; }

int obor_resource_catalog_manifest_unchanged(const obor_resource_catalog *c,
        uint64_t previous_generation, uint32_t offset, uint32_t length)
{
    /* The arena extent in the header may change independently of entries.
     * Never reuse that header through a resource-generation proof. */
    if (!c || !c->manifest_size || !previous_generation ||
        previous_generation > c->generation || !length ||
        offset < OBOR_RESOURCE_MANIFEST_HEADER || offset > c->manifest_size ||
        length > c->manifest_size - offset) return 0;
    uint32_t first = (offset - OBOR_RESOURCE_MANIFEST_HEADER) / OBOR_RESOURCE_MANIFEST_RECORD;
    uint32_t last = (offset + length - 1 - OBOR_RESOURCE_MANIFEST_HEADER) / OBOR_RESOURCE_MANIFEST_RECORD;
    for (uint32_t slot = first; slot <= last; ++slot)
        if (c->entries[slot].manifest_changed > previous_generation) return 0;
    return 1;
}
void obor_resource_catalog_forget_proofs(obor_resource_catalog *c)
{
    if (c) {
        c->proofs_checked = 0;
        for (uint32_t i = 0; i < c->slots; ++i) c->entries[i].checked = 0;
    }
}

static int catalog_order(const void *a, const void *b)
{
    uint32_t left = ((const catalog_range *)a)->offset, right = ((const catalog_range *)b)->offset;
    return (left > right) - (left < right);
}

static int catalog_ranges(obor_resource_catalog *c, uint32_t used)
{
    uint32_t count = 0;
    for (uint32_t i = 0; i < c->slots; ++i) {
        const catalog_entry *e = c->entries + i;
        if (!(e->flags & CATALOG_ACTIVE)) continue;
        if (!catalog_bounds(c, e, used)) return 0;
        c->ranges[count++] = (catalog_range){e->owner, e->allocation, i};
    }
    if (count) qsort(c->ranges, count, sizeof(*c->ranges), catalog_order);
    for (uint32_t i = 1; i < count; ++i)
        if (c->ranges[i].offset < c->ranges[i - 1].offset + c->ranges[i - 1].length) return 0;
    uint32_t retained = 0;
    for (uint32_t i = 0; i < count; ++i) {
        const catalog_entry *e = c->entries + c->ranges[i].slot;
        if (e->flags & CATALOG_OMITTED)
            c->ranges[retained++] = (catalog_range){e->body, e->recipe.length, c->ranges[i].slot};
    }
    c->range_count = retained;
    return 1;
}

int obor_resource_catalog_prepare(obor_resource_catalog *c, uint32_t used,
        obor_resource_unchanged unchanged, void *context)
{
    if (!c || used > c->arena_size) return 0;
    /* Add/remove invalidate the manifest. Forget/reset invalidate checked
     * proofs. With identical bounds and a write-tracking proof covering every
     * active body, eligibility and the complete preceding manifest still
     * hold. A dirty byte, absent proof or changed extent uses the full path. */
    if (c->manifest_size && c->proofs_checked &&
        used == catalog_u32(c->manifest + 16) &&
        (!c->active || (unchanged && c->proof_end > c->proof_begin &&
         unchanged(context, c->proof_begin, c->proof_end - c->proof_begin))))
        return 1;
    c->proofs_checked = 0;
    uint32_t proof_begin = UINT32_MAX, proof_end = 0;
    uint64_t previous_generation = c->generation;
    uint32_t previous_manifest = c->manifest_size, previous_ranges = c->range_count;
    c->manifest_size = c->range_count = 0;
    uint32_t omitted = 0;
    for (uint32_t i = 0; i < c->slots; ++i) {
        catalog_entry *e = c->entries + i;
        if (!(e->flags & CATALOG_ACTIVE)) continue;
        if (!catalog_bounds(c, e, used)) return 0;
        if (e->body < proof_begin) proof_begin = e->body;
        if (e->body + e->recipe.length > proof_end) proof_end = e->body + e->recipe.length;
        obor_framebuffer_source frame_source;
        int frame = e->recipe.kind == OBOR_RESOURCE_ABGR32_FRAME;
        if (frame) {
            if (!obor_resource_recipe_framebuffer_source(&e->recipe, &frame_source)) return 0;
            if (frame_source.offset < proof_begin) proof_begin = frame_source.offset;
            if (frame_source.offset + e->recipe.length > proof_end) proof_end = frame_source.offset + e->recipe.length;
        }
        uint32_t old = e->flags;
        int eligible = (old & CATALOG_OMITTED) != 0;
        if (!e->checked || !unchanged || !unchanged(context, e->body, e->recipe.length) ||
            (frame && !unchanged(context, frame_source.offset, e->recipe.length))) {
            if (frame) eligible = obor_framebuffer_matches(c->arena + frame_source.offset,
                                                         c->arena + e->body, e->recipe.length);
            else {
                const void *candidate = obor_resource_recipe_body(c->materializer, &e->recipe);
                eligible = candidate && !memcmp(candidate, c->arena + e->body, e->recipe.length);
            }
        }
        if (eligible && e->recipe.length <= OBOR_RESOURCE_STAGE_LIMIT - omitted) {
            e->flags |= CATALOG_OMITTED; omitted += e->recipe.length;
        } else e->flags &= ~CATALOG_OMITTED;
        e->checked = 1;
        if (old != e->flags) e->manifest_changed = ++c->generation;
    }
    if (c->framebuffer_slot != CATALOG_EMPTY) {
        catalog_entry *e = c->entries + c->framebuffer_slot;
        if ((e->flags & CATALOG_OMITTED) && !catalog_frame_source_raw(c, e)) {
            e->flags &= ~CATALOG_OMITTED; omitted -= e->recipe.length;
            e->checked = 0;
            e->manifest_changed = ++c->generation;
        }
    }
    c->proof_begin = proof_begin; c->proof_end = proof_end; c->proofs_checked = 1;
    /* A valid preceding manifest already proved ordering, nonoverlap, path
     * encoding and stable-slot contents. Dirty proofs above still examine
     * every body; if neither ownership nor eligibility changed, only the
     * current arena extent can differ. Avoid sorting and rewriting every
     * recipe on each capture merely to produce the identical bytes. */
    if (previous_manifest && previous_generation == c->generation) {
        catalog_put(c->manifest + 16, used);
        c->manifest_size = previous_manifest; c->range_count = previous_ranges;
        return 1;
    }
    if (!catalog_ranges(c, used)) return 0;
    if (!catalog_manifest_reserve(c)) { c->range_count = 0; return 0; }
    uint32_t bytes = OBOR_RESOURCE_MANIFEST_HEADER + c->slots * OBOR_RESOURCE_MANIFEST_RECORD;
    uint32_t header[8] = {OBOR_RESOURCE_MANIFEST_MAGIC, 1, c->slots,
        OBOR_RESOURCE_MANIFEST_RECORD, used, omitted, c->active, 0};
    for (unsigned i = 0; i < 8; ++i) catalog_put(c->manifest + i * 4, header[i]);
    for (uint32_t i = 0; i < c->slots; ++i) {
        const catalog_entry *e = c->entries + i;
        unsigned char *out = c->manifest + OBOR_RESOURCE_MANIFEST_HEADER + i * OBOR_RESOURCE_MANIFEST_RECORD;
        if (!(e->flags & CATALOG_ACTIVE)) {
            memset(out, 0, OBOR_RESOURCE_MANIFEST_RECORD);
            continue;
        }
        catalog_put(out, e->owner); catalog_put(out + 4, e->allocation);
        catalog_put(out + 8, e->body); catalog_put(out + 12, e->flags);
        if (!obor_resource_recipe_write(&e->recipe, out + 16, OBOR_RESOURCE_RECIPE_SIZE)) return 0;
    }
    c->manifest_size = bytes;
    return 1;
}

const void *obor_resource_catalog_manifest(const obor_resource_catalog *c, uint32_t *size)
{
    if (size) *size = c ? c->manifest_size : 0;
    return c && c->manifest_size ? c->manifest : NULL;
}

static uint32_t catalog_first_range(const obor_resource_catalog *c, uint32_t offset)
{
    uint32_t lo = 0, hi = c->range_count;
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2;
        if (c->ranges[mid].offset + c->ranges[mid].length <= offset) lo = mid + 1; else hi = mid;
    }
    return lo;
}

void obor_resource_catalog_zero(const obor_resource_catalog *c, uint32_t offset, void *output, uint32_t length)
{
    if (!c || !c->manifest_size || !output || offset > c->arena_size || length > c->arena_size - offset) return;
    uint32_t end = offset + length;
    for (uint32_t i = catalog_first_range(c, offset); i < c->range_count && c->ranges[i].offset < end; ++i) {
        uint32_t begin = c->ranges[i].offset, stop = begin + c->ranges[i].length;
        if (begin < offset) begin = offset;
        if (stop > end) stop = end;
        memset((unsigned char *)output + begin - offset, 0, stop - begin);
    }
}

int obor_resource_catalog_read(const obor_resource_catalog *c, uint32_t offset,
        void *output, uint32_t length)
{
    if (!c || !c->manifest_size || (!output && length) ||
        offset > c->arena_size || length > c->arena_size - offset) return 0;
    if (!length) return 1;
    unsigned char *out = output;
    uint32_t cursor = offset, end = offset + length;
    for (uint32_t i = catalog_first_range(c, offset);
         i < c->range_count && c->ranges[i].offset < end; ++i) {
        uint32_t begin = c->ranges[i].offset, stop = begin + c->ranges[i].length;
        if (begin < offset) begin = offset;
        if (stop > end) stop = end;
        if (cursor < begin)
            memcpy(out + cursor - offset, c->arena + cursor, begin - cursor);
        memset(out + begin - offset, 0, stop - begin);
        cursor = stop;
    }
    if (cursor < end)
        memcpy(out + cursor - offset, c->arena + cursor, end - cursor);
    return 1;
}

uint32_t obor_resource_catalog_mask_count(const obor_resource_catalog *c)
{ return c && c->manifest_size ? c->range_count : 0; }

int obor_resource_catalog_copy_mask(const obor_resource_catalog *c,
        obor_resource_mask_range *output, uint32_t capacity)
{
    if (!c || !c->manifest_size || c->range_count > capacity ||
        (c->range_count && !output)) return 0;
    for (uint32_t i = 0; i < c->range_count; ++i)
        output[i] = (obor_resource_mask_range){c->ranges[i].offset, c->ranges[i].length};
    return 1;
}

int obor_resource_catalog_mask_unchanged(const obor_resource_catalog *c,
        const obor_resource_mask_range *previous, uint32_t previous_count,
        uint32_t offset, uint32_t length)
{
    if (!c || !c->manifest_size || !length || offset > c->arena_size ||
        length > c->arena_size - offset || previous_count > OBOR_RESOURCE_CATALOG_LIMIT ||
        (previous_count && !previous)) return 0;
    uint32_t end = offset + length;
    uint32_t lo = 0, hi = previous_count;
    /* Previous masks come only from copy_mask: sorted, nonoverlapping and
     * bounded by the same arena. Compare clipped intervals exactly; hashes
     * are not sufficient proof for omitting bytes. */
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2;
        if (previous[mid].offset + previous[mid].length <= offset) lo = mid + 1;
        else hi = mid;
    }
    uint32_t now = catalog_first_range(c, offset), old = lo;
    for (;;) {
        int has_now = now < c->range_count && c->ranges[now].offset < end;
        int has_old = old < previous_count && previous[old].offset < end;
        if (!has_now || !has_old) return has_now == has_old;
        uint32_t a = c->ranges[now].offset, b = a + c->ranges[now].length;
        uint32_t x = previous[old].offset, y = x + previous[old].length;
        if (a < offset) a = offset;
        if (x < offset) x = offset;
        if (b > end) b = end;
        if (y > end) y = end;
        if (a != x || b != y) return 0;
        ++now; ++old;
    }
}

static obor_resource_catalog *catalog_read(obor_resource_catalog *current, const void *input,
        uint32_t size, uint32_t used)
{
    if (!input || size < OBOR_RESOURCE_MANIFEST_HEADER || used > current->arena_size) return NULL;
    const unsigned char *p = input;
    uint32_t slots = catalog_u32(p + 8), omitted = catalog_u32(p + 20), active = catalog_u32(p + 24);
    if (catalog_u32(p) != OBOR_RESOURCE_MANIFEST_MAGIC || catalog_u32(p + 4) != 1 ||
        slots > OBOR_RESOURCE_CATALOG_LIMIT || catalog_u32(p + 12) != OBOR_RESOURCE_MANIFEST_RECORD ||
        catalog_u32(p + 16) != used || omitted > OBOR_RESOURCE_STAGE_LIMIT || active > slots ||
        catalog_u32(p + 28) || size != OBOR_RESOURCE_MANIFEST_HEADER + slots * OBOR_RESOURCE_MANIFEST_RECORD) return NULL;
    obor_resource_catalog *c = obor_resource_catalog_create(current->materializer, &current->allocator,
        current->arena, current->arena_size);
    if (!c || !catalog_grow(c, slots)) { obor_resource_catalog_destroy(c); return NULL; }
    c->slots = slots;
    uint32_t total = 0;
    for (uint32_t i = 0; i < slots; ++i) {
        const unsigned char *record = p + OBOR_RESOURCE_MANIFEST_HEADER + i * OBOR_RESOURCE_MANIFEST_RECORD;
        catalog_entry *e = c->entries + i;
        uint32_t flags = catalog_u32(record + 12);
        if (!flags) {
            for (uint32_t j = 0; j < OBOR_RESOURCE_MANIFEST_RECORD; ++j) if (record[j]) goto fail;
            e->next_free = c->free_slot; c->free_slot = i;
            continue;
        }
        if (!(flags & CATALOG_ACTIVE) || (flags & ~(CATALOG_ACTIVE | CATALOG_OMITTED))) goto fail;
        e->owner = catalog_u32(record); e->allocation = catalog_u32(record + 4);
        e->body = catalog_u32(record + 8); e->flags = flags;
        if (!obor_resource_recipe_read(&e->recipe, record + 16, OBOR_RESOURCE_RECIPE_SIZE) ||
            !catalog_bounds(c, e, used)) goto fail;
        if (e->recipe.kind == OBOR_RESOURCE_ABGR32_FRAME) {
            if (c->framebuffer_slot != CATALOG_EMPTY) goto fail;
            c->framebuffer_slot = i;
        }
        if (flags & CATALOG_OMITTED) {
            if (e->recipe.length > OBOR_RESOURCE_STAGE_LIMIT - total) goto fail;
            total += e->recipe.length;
        }
        uint32_t at;
        if (catalog_find(c, e->owner, &at) != CATALOG_EMPTY || at == CATALOG_EMPTY) goto fail;
        c->buckets[at] = i + 1; ++c->active;
    }
    if (c->active != active || total != omitted || !catalog_ranges(c, used)) goto fail;
    if (!catalog_manifest_reserve(c)) goto fail;
    memcpy(c->manifest, input, size); c->manifest_size = size;
    c->generation = current->generation + 1;
    return c;
fail:
    obor_resource_catalog_destroy(c); return NULL;
}

obor_resource_restore *obor_resource_restore_prepare_snapshot(obor_resource_catalog *current,
        const void *manifest, uint32_t size, uint32_t used, obor_resource_unchanged unchanged,
        void *context, obor_resource_snapshot_read snapshot_read, void *snapshot)
{
    if (!current) return NULL;
    obor_resource_catalog *target = catalog_read(current, manifest, size, used);
    if (!target) return NULL;
    obor_resource_restore *plan = current->allocator.allocate(sizeof(*plan));
    if (!plan) { obor_resource_catalog_destroy(target); return NULL; }
    memset(plan, 0, sizeof(*plan)); plan->target = target; plan->allocator = current->allocator;
    if (target->range_count) {
        plan->staged_offsets = plan->allocator.allocate((size_t)target->range_count * sizeof(*plan->staged_offsets));
        if (!plan->staged_offsets) goto fail;
    }
    for (uint32_t i = 0; i < target->range_count; ++i) {
        const catalog_entry *e = target->entries + target->ranges[i].slot;
        uint32_t at, slot = catalog_find(current, e->owner, &at);
        int reusable = 0;
        /* Mutable source bytes are absent from a frame recipe's identity.
         * Always reconstruct from the INCOMING snapshot, even if its metadata
         * and the current output copy are unchanged. */
        if (e->recipe.kind != OBOR_RESOURCE_ABGR32_FRAME && slot != CATALOG_EMPTY && unchanged) {
            const catalog_entry *live = current->entries + slot;
            reusable = live->checked && (live->flags & CATALOG_OMITTED) && live->body == e->body &&
                live->allocation == e->allocation && obor_resource_recipe_equal(&live->recipe, &e->recipe) &&
                unchanged(context, e->body, e->recipe.length);
        }
        if (reusable) plan->staged_offsets[i] = CATALOG_EMPTY;
        else {
            plan->staged_offsets[i] = (uint32_t)plan->staged_size;
            plan->staged_size += e->recipe.length;
        }
    }
    if (plan->staged_size > OBOR_RESOURCE_STAGE_LIMIT) goto fail;
    if (plan->staged_size) {
        plan->staging = plan->allocator.allocate(plan->staged_size);
        if (!plan->staging) goto fail;
    }
    for (uint32_t i = 0; i < target->range_count; ++i) {
        if (plan->staged_offsets[i] == CATALOG_EMPTY) continue;
        const catalog_entry *e = target->entries + target->ranges[i].slot;
        if (e->recipe.kind == OBOR_RESOURCE_ABGR32_FRAME) {
            obor_framebuffer_source source;
            if (!snapshot_read || !catalog_frame_source_raw(target, e) ||
                !obor_resource_recipe_framebuffer_source(&e->recipe, &source)) goto fail;
            const void *body = snapshot_read(snapshot, source.owner, source.allocation,
                                             source.offset, e->recipe.length);
            if (!body) goto fail;
            obor_framebuffer_reconstruct(body, plan->staging + plan->staged_offsets[i], e->recipe.length);
        } else {
            const void *body = obor_resource_recipe_body(target->materializer, &e->recipe);
            if (!body) goto fail;
            memcpy(plan->staging + plan->staged_offsets[i], body, e->recipe.length);
        }
    }
    return plan;
fail:
    obor_resource_restore_destroy(plan); return NULL;
}

obor_resource_restore *obor_resource_restore_prepare(obor_resource_catalog *current,
        const void *manifest, uint32_t size, uint32_t used,
        obor_resource_unchanged unchanged, void *context)
{
    return obor_resource_restore_prepare_snapshot(current, manifest, size, used,
                                                  unchanged, context, NULL, NULL);
}

void obor_resource_restore_copy(const obor_resource_restore *plan, uint32_t offset,
        const void *source, uint32_t length)
{
    if (!plan || !source || !plan->target) return;
    const obor_resource_catalog *c = plan->target;
    if (offset > c->arena_size || length > c->arena_size - offset) return;
    uint32_t end = offset + length, cursor = offset;
    for (uint32_t i = catalog_first_range(c, offset); i < c->range_count && c->ranges[i].offset < end; ++i) {
        uint32_t begin = c->ranges[i].offset, stop = begin + c->ranges[i].length;
        if (begin > cursor) memcpy(c->arena + cursor, (const unsigned char *)source + cursor - offset, begin - cursor);
        cursor = stop < end ? stop : end;
    }
    if (cursor < end) memcpy(c->arena + cursor, (const unsigned char *)source + cursor - offset, end - cursor);
}

obor_resource_catalog *obor_resource_restore_commit(obor_resource_restore *plan)
{
    if (!plan || !plan->target) return NULL;
    obor_resource_catalog *c = plan->target;
    for (uint32_t i = 0; i < c->range_count; ++i) {
        catalog_entry *e = c->entries + c->ranges[i].slot;
        if (plan->staged_offsets[i] != CATALOG_EMPTY)
            memcpy(c->arena + e->body, plan->staging + plan->staged_offsets[i], e->recipe.length);
        /* Caller must establish a new full write-tracking epoch after commit
         * before using an unchanged proof; otherwise pass no callback. */
        e->checked = 1;
    }
    plan->target = NULL;
    return c;
}

void obor_resource_restore_destroy(obor_resource_restore *plan)
{
    if (!plan) return;
    obor_resource_catalog_destroy(plan->target);
    plan->allocator.release(plan->staging); plan->allocator.release(plan->staged_offsets);
    plan->allocator.release(plan);
}
size_t obor_resource_restore_staged(const obor_resource_restore *p) { return p ? p->staged_size : 0; }
uint32_t obor_resource_restore_count(const obor_resource_restore *p)
{ return p && p->target ? p->target->range_count : 0; }
int obor_resource_restore_range(const obor_resource_restore *p, uint32_t index, uint32_t *offset, uint32_t *length)
{
    if (!p || !p->target || !offset || !length || index >= p->target->range_count) return 0;
    *offset = p->target->ranges[index].offset; *length = p->target->ranges[index].length;
    return 1;
}

uint32_t obor_resource_restore_slots(const obor_resource_restore *p)
{ return p && p->target ? p->target->slots : 0; }
int obor_resource_restore_allocation(const obor_resource_restore *p, uint32_t slot,
        uint32_t *owner, uint32_t *allocation)
{
    if (!p || !p->target || !owner || !allocation || slot >= p->target->slots ||
        !(p->target->entries[slot].flags & CATALOG_ACTIVE)) return 0;
    *owner = p->target->entries[slot].owner;
    *allocation = p->target->entries[slot].allocation;
    return 1;
}
