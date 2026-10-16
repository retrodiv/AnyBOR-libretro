/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_resource_catalog.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef EXPECT_GEOMETRIC
#define EXPECT_GEOMETRIC 1
#endif

typedef union allocation_header allocation_header;
union allocation_header {
    struct { allocation_header *previous, *next; size_t size; } data;
    long double alignment;
    void *pointer;
};
static allocation_header *allocations;
static size_t attempts, releases, fail_at, live, peak, requested;
static unsigned canonical_states;
static void *allocate(size_t size)
{
    ++attempts; requested += size;
    if (attempts == fail_at) return NULL;
    assert(size <= SIZE_MAX - sizeof(allocation_header));
    allocation_header *p = malloc(sizeof(*p) + size);
    assert(p);
    p->data.previous = NULL; p->data.next = allocations; p->data.size = size;
    if (allocations) allocations->data.previous = p;
    allocations = p; live += size; if (live > peak) peak = live;
    memset(p + 1, 0xa5, size);
    return p + 1;
}
static void release(void *memory)
{
    if (!memory) return;
    allocation_header *p = (allocation_header *)memory - 1;
    if (p->data.previous) p->data.previous->data.next = p->data.next;
    else { assert(allocations == p); allocations = p->data.next; }
    if (p->data.next) p->data.next->data.previous = p->data.previous;
    assert(live >= p->data.size); live -= p->data.size; ++releases; free(p);
}
static size_t reserved(const void *memory)
{
    for (allocation_header *p = allocations; p; p = p->data.next)
        if ((const void *)(p + 1) == memory) return p->data.size;
    return 0;
}
static const obor_resource_image_allocator allocator = {allocate, release};
typedef struct { unsigned char *bytes; size_t size; } input_data;
static int read_input(void *context, uint64_t offset, void *out, size_t length)
{
    const input_data *input = context;
    assert(offset <= input->size && length <= input->size - offset);
    memcpy(out, input->bytes + offset, length); return 1;
}
static void put(unsigned char *out, uint32_t value)
{ for (unsigned i = 0; i < 4; ++i) out[i] = (unsigned char)(value >> (i * 8)); }
static uint32_t get(const unsigned char *p)
{ return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24; }
#ifdef OBOR_CATALOG_ZERO_TRACK
#ifndef EXPECT_SELECTIVE_ZERO
#define EXPECT_SELECTIVE_ZERO 1
#endif
/* Only catalog.c is compiled with memset renamed to this real forwarding
 * function. Observe requested clear traffic without changing any writes. */
static int track_clears;
static size_t clear_bytes, clear_calls, all_clear_bytes, checked_prepares;
static uintptr_t clear_begin, clear_end;
void *obor_catalog_test_memset(void *memory, int value, size_t size)
{
    if (track_clears && size) {
        uintptr_t begin = (uintptr_t)memory;
        assert((unsigned char)value == 0 && begin <= UINTPTR_MAX - size);
        assert(clear_bytes <= SIZE_MAX - size);
        clear_bytes += size; ++clear_calls;
        if (begin < clear_begin) clear_begin = begin;
        if (begin + size > clear_end) clear_end = begin + size;
    }
    return memset(memory,value,size);
}
static int checked_prepare(obor_resource_catalog *catalog, uint32_t used,
        obor_resource_unchanged unchanged, void *context)
{
    uint32_t previous_size;
    int previous = obor_resource_catalog_manifest(catalog,&previous_size) != NULL;
    uint64_t generation = obor_resource_catalog_generation(catalog);
    assert(!track_clears);
    clear_bytes = clear_calls = 0; clear_begin = UINTPTR_MAX; clear_end = 0;
    track_clears = 1;
    int result = obor_resource_catalog_prepare(catalog,used,unchanged,context);
    track_clears = 0;
    if (result) {
        uint32_t size;
        const unsigned char *manifest = obor_resource_catalog_manifest(catalog,&size);
        assert(manifest && size >= OBOR_RESOURCE_MANIFEST_HEADER);
        uint32_t slots = get(manifest + 8), active = get(manifest + 24);
        assert(active <= slots);
        int rebuild = !previous || generation != obor_resource_catalog_generation(catalog);
        size_t expected = !rebuild ? 0 : EXPECT_SELECTIVE_ZERO ?
            (size_t)(slots - active) * OBOR_RESOURCE_MANIFEST_RECORD : size;
        if (clear_bytes != expected)
            fprintf(stderr,"manifest clear traffic: got=%zu expected=%zu slots=%u active=%u rebuild=%d\n",
                    clear_bytes,expected,slots,active,rebuild);
        assert(clear_bytes == expected);
        if (clear_calls) {
            assert(clear_begin >= (uintptr_t)manifest &&
                   clear_end <= (uintptr_t)manifest + size);
        }
        all_clear_bytes += clear_bytes; ++checked_prepares;
    }
    return result;
}
#define obor_resource_catalog_prepare checked_prepare
#endif
static uint32_t capacity_for(uint32_t slots)
{
    if (!slots) return 0;
    uint32_t capacity = 64;
    while (capacity < slots) capacity *= 2;
    assert(capacity <= OBOR_RESOURCE_CATALOG_LIMIT); return capacity;
}
static uint32_t manifest_bytes(uint32_t slots)
{ return OBOR_RESOURCE_MANIFEST_HEADER + slots * OBOR_RESOURCE_MANIFEST_RECORD; }
static size_t expected_reservation(uint32_t slots)
{ return manifest_bytes(EXPECT_GEOMETRIC ? capacity_for(slots) : slots); }
static void append(FILE *file, const void *data, size_t size)
{ if (file) assert(fwrite(data, 1, size, file) == size); }
static void append_u32(FILE *file, uint32_t value)
{ unsigned char out[4]; put(out, value); append(file, out, sizeof(out)); }

typedef struct { uint32_t owner; int active; } slot_state;
static const unsigned char body[8] = {44,45,46,47,48,49,50,51};
static void add(obor_resource_catalog *catalog, unsigned char *arena,
        uint32_t owner, const obor_resource_recipe *recipe)
{
    memcpy(arena + owner + 8, body, sizeof(body));
    assert(obor_resource_catalog_add(catalog, owner, 32, owner + 8, recipe));
}
static void check(obor_resource_catalog *catalog, const unsigned char *arena,
        uint32_t used, const slot_state *slots, uint32_t count,
        const obor_resource_recipe *recipe, FILE *canonical)
{
    uint32_t size = 0;
    const unsigned char *manifest = obor_resource_catalog_manifest(catalog, &size);
    assert(manifest && size == manifest_bytes(count));
    ++canonical_states;
    assert(reserved(manifest) == expected_reservation(count));
    unsigned char *expected = calloc(1, size); assert(expected);
    uint32_t active = 0, omitted = 0;
    for (uint32_t i = 0; i < count; ++i) {
        if (!slots[i].active) continue;
        uint32_t owner = slots[i].owner;
        int matches = !memcmp(arena + owner + 8, body, sizeof(body));
        ++active; if (matches) omitted += sizeof(body);
        unsigned char *record = expected + OBOR_RESOURCE_MANIFEST_HEADER + i * OBOR_RESOURCE_MANIFEST_RECORD;
        put(record, owner); put(record + 4, 32); put(record + 8, owner + 8);
        put(record + 12, matches ? 3 : 1);
        assert(obor_resource_recipe_write(recipe, record + 16, OBOR_RESOURCE_RECIPE_SIZE));
    }
    const uint32_t header[8] = {OBOR_RESOURCE_MANIFEST_MAGIC,1,count,
        OBOR_RESOURCE_MANIFEST_RECORD,used,omitted,active,0};
    for (unsigned i = 0; i < 8; ++i) put(expected + 4 * i, header[i]);
    assert(!memcmp(expected, manifest, size)); free(expected);
    append_u32(canonical,size); append(canonical,manifest,size);
    unsigned char *logical = malloc(used); assert(logical);
    assert(obor_resource_catalog_read(catalog,0,logical,used));
    unsigned char *reference = malloc(used); assert(reference); memcpy(reference,arena,used);
    for (uint32_t i = 0; i < count; ++i)
        if (slots[i].active && !memcmp(arena + slots[i].owner + 8,body,sizeof(body)))
            memset(reference + slots[i].owner + 8,0,sizeof(body));
    assert(!memcmp(logical,reference,used)); free(reference);
    append_u32(canonical,used); append(canonical,logical,used); free(logical);
    uint32_t mask_count = obor_resource_catalog_mask_count(catalog);
    assert(mask_count == omitted / sizeof(body));
    obor_resource_mask_range *mask = malloc((size_t)(mask_count + 1) * sizeof(*mask)); assert(mask);
    assert(obor_resource_catalog_copy_mask(catalog,mask,mask_count));
    append_u32(canonical,mask_count);
    for (uint32_t i = 0; i < mask_count; ++i) {
        assert(mask[i].length == sizeof(body));
        if (i) assert(mask[i].offset >= mask[i-1].offset + mask[i-1].length);
        append_u32(canonical,mask[i].offset); append_u32(canonical,mask[i].length);
    }
    free(mask);
}
static void failed_growth(obor_resource_catalog *catalog, unsigned char *arena,
        slot_state *slots, const obor_resource_recipe *recipe)
{
    uint32_t size;
    const unsigned char *old = obor_resource_catalog_manifest(catalog,&size);
    assert(old && size == manifest_bytes(64));
    unsigned char *copy = malloc(size); assert(copy); memcpy(copy,old,size);
    unsigned char arena_before[8192];
    add(catalog,arena,64 + 64 * 32,recipe);
    slots[64] = (slot_state){64 + 64 * 32,1};
    memcpy(arena_before,arena,sizeof(arena_before));
    size_t old_capacity = reserved(old), released_before = releases;
    fail_at = attempts + 1;
    assert(!obor_resource_catalog_prepare(catalog,sizeof(arena_before),NULL,NULL));
    fail_at = 0;
    uint32_t invalid_size = UINT32_MAX;
    assert(!obor_resource_catalog_manifest(catalog,&invalid_size) && !invalid_size);
    assert(!obor_resource_catalog_mask_count(catalog));
    assert(reserved(old) == old_capacity && releases == released_before);
    assert(!memcmp(old,copy,size) && !memcmp(arena,arena_before,sizeof(arena_before)));
    assert(obor_resource_catalog_prepare(catalog,sizeof(arena_before),NULL,NULL));
    assert(!reserved(old)); free(copy);
}
static void lifecycle(obor_resource_materializer *materializer,
        const obor_resource_recipe *recipe, FILE *canonical)
{
    unsigned char arena[8192]; memset(arena,0x71,sizeof(arena));
    slot_state slots[132]; memset(slots,0,sizeof(slots));
    obor_resource_catalog *catalog = obor_resource_catalog_create(materializer,&allocator,arena,sizeof(arena));
    assert(catalog);
    assert(obor_resource_catalog_prepare(catalog,sizeof(arena),NULL,NULL));
    check(catalog,arena,sizeof(arena),slots,0,recipe,canonical);
    for (uint32_t i = 0; i < 64; ++i) {
        uint32_t previous_size; const void *previous = obor_resource_catalog_manifest(catalog,&previous_size);
        add(catalog,arena,64 + i * 32,recipe); slots[i] = (slot_state){64 + i * 32,1};
        size_t after_add = attempts;
        assert(obor_resource_catalog_prepare(catalog,sizeof(arena),NULL,NULL));
        if (EXPECT_GEOMETRIC && i) {
            uint32_t size; assert(obor_resource_catalog_manifest(catalog,&size) == previous);
            assert(attempts == after_add);
        }
        if (i == 0 || i == 1 || i == 62 || i == 63)
            check(catalog,arena,sizeof(arena),slots,i + 1,recipe,canonical);
    }
    failed_growth(catalog,arena,slots,recipe);
    check(catalog,arena,sizeof(arena),slots,65,recipe,canonical);
    for (uint32_t i = 65; i < 129; ++i) {
        uint32_t old_size; const void *old = obor_resource_catalog_manifest(catalog,&old_size);
        add(catalog,arena,64 + i * 32,recipe); slots[i] = (slot_state){64 + i * 32,1};
        size_t before = attempts;
        assert(obor_resource_catalog_prepare(catalog,sizeof(arena),NULL,NULL));
        if (EXPECT_GEOMETRIC && i != 128) {
            uint32_t size; assert(obor_resource_catalog_manifest(catalog,&size) == old);
            assert(attempts == before);
        }
        if (i == 126 || i == 127 || i == 128)
            check(catalog,arena,sizeof(arena),slots,i + 1,recipe,canonical);
    }
    uint32_t size; const unsigned char *manifest = obor_resource_catalog_manifest(catalog,&size);
    unsigned char *copy = malloc(size); assert(copy); memcpy(copy,manifest,size);
    size_t full_capacity = reserved(manifest);
    for (uint32_t i = size; i < full_capacity; ++i) assert(manifest[i] == 0xa5);
    obor_resource_catalog_remove(catalog,slots[5].owner); slots[5].active = 0;
    obor_resource_catalog_remove(catalog,slots[40].owner); slots[40].active = 0;
    size_t before = attempts;
    assert(obor_resource_catalog_prepare(catalog,sizeof(arena),NULL,NULL));
    assert(attempts == before);
    check(catalog,arena,sizeof(arena),slots,129,recipe,canonical);
    add(catalog,arena,64 + 140 * 32,recipe); slots[40] = (slot_state){64 + 140 * 32,1};
    add(catalog,arena,64 + 141 * 32,recipe); slots[5] = (slot_state){64 + 141 * 32,1};
    assert(obor_resource_catalog_prepare(catalog,sizeof(arena),NULL,NULL));
    check(catalog,arena,sizeof(arena),slots,129,recipe,canonical);
    arena[slots[40].owner + 9] ^= 0x3f;
    obor_resource_catalog_forget_proofs(catalog);
    assert(obor_resource_catalog_prepare(catalog,sizeof(arena),NULL,NULL));
    check(catalog,arena,sizeof(arena),slots,129,recipe,canonical);

    /* Loading reserves geometrically too and only commits reconstructed bytes
     * after the whole preflight succeeds. A failed target leaves the current
     * prepared manifest and live arena unchanged. */
    const void *current = obor_resource_catalog_manifest(catalog,&size);
    unsigned char *current_copy = malloc(size); assert(current_copy); memcpy(current_copy,current,size);
    unsigned char before_arena[sizeof(arena)]; memcpy(before_arena,arena,sizeof(arena));
    size_t current_live = live;
    before = attempts;
    obor_resource_restore *probe = obor_resource_restore_prepare(catalog,copy,manifest_bytes(129),sizeof(arena),NULL,NULL);
    assert(probe); size_t load_allocations = attempts - before;
    assert(load_allocations >= 5); /* Includes the target manifest reserve. */
    obor_resource_restore_destroy(probe);
    uint32_t current_size;
    for (size_t fail = 1; fail <= load_allocations; ++fail) {
        fail_at = attempts + fail;
        assert(!obor_resource_restore_prepare(catalog,copy,manifest_bytes(129),sizeof(arena),NULL,NULL));
        fail_at = 0;
        assert(obor_resource_catalog_manifest(catalog,&current_size) == current && current_size == size);
        assert(!memcmp(current,current_copy,size));
        assert(live == current_live && !memcmp(arena,before_arena,sizeof(arena)));
    }
    free(current_copy);
    obor_resource_restore *restore = obor_resource_restore_prepare(catalog,copy,manifest_bytes(129),sizeof(arena),NULL,NULL);
    assert(restore);
    obor_resource_catalog *loaded = obor_resource_restore_commit(restore); assert(loaded);
    obor_resource_restore_destroy(restore); obor_resource_catalog_destroy(catalog); catalog = loaded;
    /* The loaded stream precedes retire/reuse and the mutable-body edit. */
    for (uint32_t i = 0; i < 129; ++i) slots[i] = (slot_state){64 + i * 32,1};
    assert(obor_resource_catalog_prepare(catalog,sizeof(arena),NULL,NULL));
    check(catalog,arena,sizeof(arena),slots,129,recipe,canonical);
    const void *loaded_manifest = obor_resource_catalog_manifest(catalog,&size);
    before = attempts;
    add(catalog,arena,64 + 129 * 32,recipe); slots[129] = (slot_state){64 + 129 * 32,1};
    size_t after_add = attempts;
    assert(obor_resource_catalog_prepare(catalog,sizeof(arena),NULL,NULL));
    if (EXPECT_GEOMETRIC) {
        assert(attempts == after_add && after_add == before);
        assert(obor_resource_catalog_manifest(catalog,&size) == loaded_manifest);
    }
    check(catalog,arena,sizeof(arena),slots,130,recipe,canonical);
    obor_resource_catalog_destroy(catalog); free(copy);
}
static void limit(obor_resource_materializer *materializer,
        const obor_resource_recipe *recipe, FILE *canonical)
{
    const uint32_t count = OBOR_RESOURCE_CATALOG_LIMIT, used = 64 + (count + 1) * 32;
    unsigned char *arena = malloc(used); slot_state *slots = calloc(count,sizeof(*slots));
    assert(arena && slots); memset(arena,0x71,used);
    obor_resource_catalog *catalog = obor_resource_catalog_create(materializer,&allocator,arena,used);
    assert(catalog);
    for (uint32_t i = 0; i < count; ++i) {
        slots[i] = (slot_state){64 + i * 32,1}; add(catalog,arena,slots[i].owner,recipe);
    }
    assert(obor_resource_catalog_prepare(catalog,used,NULL,NULL));
    check(catalog,arena,used,slots,count,recipe,canonical);
    uint32_t size; const unsigned char *manifest = obor_resource_catalog_manifest(catalog,&size);
    assert(size == 39321632U && size == manifest_bytes(count));
    assert(reserved(manifest) == size);
    size_t before = attempts;
    assert(!obor_resource_catalog_add(catalog,64 + count * 32,32,72 + count * 32,recipe));
    assert(attempts == before && obor_resource_catalog_manifest(catalog,&size) == manifest);
    unsigned char *copy = malloc(size); assert(copy); memcpy(copy,manifest,size);
    put(copy + 8,count + 1);
    assert(!obor_resource_restore_prepare(catalog,copy,size,used,NULL,NULL));
    put(copy + 8,UINT32_MAX);
    assert(!obor_resource_restore_prepare(catalog,copy,size,used,NULL,NULL));
    assert(get(manifest + 8) == count);
    free(copy); obor_resource_catalog_destroy(catalog); free(slots); free(arena);
}
int main(int argc, char **argv)
{
    assert(argc == 2 || argc == 3);
    FILE *source_file = fopen(argv[1],"rb"); assert(source_file);
    assert(!fseek(source_file,0,SEEK_END)); long length = ftell(source_file); assert(length > 0);
    rewind(source_file); input_data input = {malloc((size_t)length),(size_t)length}; assert(input.bytes);
    assert(fread(input.bytes,1,input.size,source_file) == input.size); assert(!fclose(source_file));
    const obor_resource_reader reader = {&input,input.size,read_input};
    obor_resource_source *source = obor_resource_source_create(&reader,&allocator); assert(source);
    obor_resource_materializer *materializer = obor_resource_materializer_create(source,&allocator,1024*1024); assert(materializer);
    obor_resource_recipe recipe;
    assert(obor_resource_recipe_prove_bytes(materializer,&recipe,"data/sample.bin",15,44,body,sizeof(body)));
    FILE *canonical = argc == 3 ? fopen(argv[2],"wb") : NULL; assert(argc != 3 || canonical);
    lifecycle(materializer,&recipe,canonical); limit(materializer,&recipe,canonical);
    if (canonical) assert(!fclose(canonical));
    obor_resource_materializer_destroy(materializer); obor_resource_source_destroy(source); free(input.bytes);
    assert(!live && !allocations);
    puts("manifest_capacity_growth=1 a5_allocator=1 retire_reuse=1 load_adopt=1 allocation_failure_atomic=1 limit65536=1 canonical_bytes=1");
    printf("canonical_states=%u allocator_attempts=%zu releases=%zu requested_bytes=%zu peak_live_bytes=%zu\n",
           canonical_states,attempts,releases,requested,peak);
#ifdef OBOR_CATALOG_ZERO_TRACK
    assert(checked_prepares);
    printf("selective_manifest_zeroing=%d checked_prepares=%zu clear_bytes=%zu\n",
           EXPECT_SELECTIVE_ZERO,checked_prepares,all_clear_bytes);
#endif
    return 0;
}
