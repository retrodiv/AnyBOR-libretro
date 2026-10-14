/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_resource_catalog.h"
#include "obor_framebuffer_state.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if defined(__SANITIZE_ADDRESS__)
#include <sanitizer/asan_interface.h>
#endif

void image_test_reset(size_t);
void *image_test_allocate(size_t);
void image_test_release(void *);
size_t image_test_live(void);
size_t image_test_peak(void);
size_t image_test_attempts(void);
static const obor_resource_image_allocator allocator = {image_test_allocate, image_test_release};
typedef struct { unsigned char *bytes; size_t length; int fail; } input_data;
static int read_input(void *opaque, uint64_t offset, void *out, size_t length)
{
    input_data *in = opaque;
    assert(offset <= in->length && length <= in->length - offset);
    if (in->fail) return 0;
    memcpy(out, in->bytes + offset, length); return 1;
}
static obor_resource_source *open_source(input_data *input)
{
    const obor_resource_reader reader = {input, input->length, read_input};
    return obor_resource_source_create(&reader, &allocator);
}
static const unsigned char expected[] = {
    12,0,0,0, 16,0,0,0, 20,0,0,0,
    1,2,5,6,1,1,7,255, 1,2,5,6,1,1,7,255, 1,2,5,6,1,1,7,255
};
static int unchanged(void *context, uint32_t offset, uint32_t length)
{ return !context || *(uint32_t *)context < offset ||
    *(uint32_t *)context - offset >= length; }
static unsigned char *save_manifest(obor_resource_catalog *c, uint32_t *size)
{
    const void *data = obor_resource_catalog_manifest(c, size); assert(data && *size);
    unsigned char *copy = malloc(*size); assert(copy); memcpy(copy, data, *size); return copy;
}

static void test_unprepared_read(obor_resource_catalog *c)
{
    unsigned char output[32]; memset(output, 0xa5, sizeof(output));
    assert(!obor_resource_catalog_read(c, 0, output, sizeof(output)));
    assert(!obor_resource_catalog_read(c, 0, NULL, 0));
    for (size_t i = 0; i < sizeof(output); ++i) assert(output[i] == 0xa5);
}

static void test_logical_read(obor_resource_catalog *c, const unsigned char *expected_image)
{
    static const uint32_t offsets[] = {0,63,64,79,80,81,95,115,116,120,271,272,307,308,4095,4096};
    unsigned char output[4096+16];
    for (unsigned i=0; i<sizeof(offsets)/sizeof(offsets[0]); ++i) {
        uint32_t offset=offsets[i], lengths[]={0,1,5,36,64,256,4096-offset};
        for (unsigned j=0; j<sizeof(lengths)/sizeof(lengths[0]); ++j) {
            uint32_t length=lengths[j];
            if (length>4096-offset) continue;
            memset(output,0xa5,sizeof(output));
            assert(obor_resource_catalog_read(c,offset,output+8,length));
            assert(!memcmp(output+8,expected_image+offset,length));
            for (unsigned k=0;k<8;++k) assert(output[k]==0xa5);
            for (size_t k=8+length;k<sizeof(output);++k) assert(output[k]==0xa5);
        }
    }
    memset(output,0xa5,sizeof(output));
    assert(!obor_resource_catalog_read(c,UINT32_MAX,output+8,1));
    assert(!obor_resource_catalog_read(c,4095,output+8,2));
    assert(!obor_resource_catalog_read(c,0,output+8,UINT32_MAX));
    assert(!obor_resource_catalog_read(c,0,NULL,1));
    assert(obor_resource_catalog_read(c,4096,NULL,0));
    for (size_t k=0;k<sizeof(output);++k) assert(output[k]==0xa5);
}

static void test_current_mask(obor_resource_materializer *m, const obor_resource_recipe *recipe)
{
    unsigned char arena[4096]; memset(arena, 0, sizeof(arena));
    memcpy(arena + 80, expected, sizeof(expected));
    memcpy(arena + 272, expected, sizeof(expected));
    obor_resource_catalog *c = obor_resource_catalog_create(m, &allocator, arena, sizeof(arena));
    assert(c && obor_resource_catalog_add(c, 64, 128, 80, recipe));
    assert(obor_resource_catalog_prepare(c, sizeof(arena), NULL, NULL));
    uint32_t first = OBOR_RESOURCE_MANIFEST_HEADER, record = OBOR_RESOURCE_MANIFEST_RECORD;
    uint64_t generation = obor_resource_catalog_generation(c);
    assert(obor_resource_catalog_manifest_unchanged(c, generation, first, record));
    assert(!obor_resource_catalog_manifest_unchanged(c, 0, first, record));
    assert(!obor_resource_catalog_manifest_unchanged(c, generation+1, first, record));
    assert(!obor_resource_catalog_manifest_unchanged(c, generation, 0, 1));
    assert(!obor_resource_catalog_manifest_unchanged(c, generation, first-1, 2));
    assert(!obor_resource_catalog_manifest_unchanged(c, generation, UINT32_MAX, 1));
    assert(!obor_resource_catalog_manifest_unchanged(c, generation, first, UINT32_MAX));
    assert(!obor_resource_catalog_manifest_unchanged(c, generation, first, 0));
    obor_resource_mask_range old[2];
    assert(obor_resource_catalog_mask_count(c)==1);
    assert(!obor_resource_catalog_copy_mask(c, old, 0));
    assert(obor_resource_catalog_copy_mask(c, old, 2));
    assert(obor_resource_catalog_mask_unchanged(c, old, 1, 90, 4));
    assert(!obor_resource_catalog_mask_unchanged(c, old, 1, UINT32_MAX, 2));
    assert(obor_resource_catalog_add(c, 256, 128, 272, recipe));
    assert(!obor_resource_catalog_manifest_unchanged(c, generation, first, record));
    assert(obor_resource_catalog_prepare(c, sizeof(arena), NULL, NULL));
    assert(obor_resource_catalog_manifest_unchanged(c, generation, first, record));
    assert(!obor_resource_catalog_manifest_unchanged(c, generation, first+record, 1));
    assert(!obor_resource_catalog_manifest_unchanged(c, generation, first+record-1, 2));
    generation = obor_resource_catalog_generation(c);
    /* Creating an unrelated resource must not invalidate every heap block. */
    assert(obor_resource_catalog_mask_unchanged(c, old, 1, 0, 192));
    assert(obor_resource_catalog_mask_unchanged(c, old, 1, 1024, 2048));
    assert(!obor_resource_catalog_mask_unchanged(c, old, 1, 0, sizeof(arena)));
    assert(!obor_resource_catalog_mask_unchanged(c, old, 1, 272, sizeof(expected)));
    assert(obor_resource_catalog_copy_mask(c, old, 2));
    obor_resource_catalog_remove(c, 64);
    assert(obor_resource_catalog_prepare(c, sizeof(arena), NULL, NULL));
    assert(!obor_resource_catalog_manifest_unchanged(c, generation, first, record));
    assert(obor_resource_catalog_manifest_unchanged(c, generation, first+record, record));
    generation = obor_resource_catalog_generation(c);
    assert(obor_resource_catalog_mask_unchanged(c, old, 2, 272, sizeof(expected)));
    assert(!obor_resource_catalog_mask_unchanged(c, old, 2, 80, sizeof(expected)));
    assert(obor_resource_catalog_copy_mask(c, old, 2));
    arena[280]^=1; /* Script writes promote this body back into mutable bytes. */
    assert(obor_resource_catalog_prepare(c, sizeof(arena), NULL, NULL));
    assert(obor_resource_catalog_manifest_unchanged(c, generation, first, record));
    assert(!obor_resource_catalog_manifest_unchanged(c, generation, first+record, record));
    generation = obor_resource_catalog_generation(c);
    /* More script mutation while already raw does not change the recipe;
     * those changed body bytes remain the ordinary heap writer's job. */
    arena[281]^=1;
    assert(obor_resource_catalog_prepare(c, sizeof(arena)-1, NULL, NULL));
    assert(obor_resource_catalog_manifest_unchanged(c, generation, first, record*2));
    assert(!obor_resource_catalog_manifest_unchanged(c, generation, 16, 4));
    arena[281]^=1;
    assert(!obor_resource_catalog_mask_unchanged(c, old, 1, 280, 1));
    assert(obor_resource_catalog_mask_unchanged(c, old, 1, 0, 272));
    assert(!obor_resource_catalog_mask_count(c));
    assert(obor_resource_catalog_copy_mask(c, NULL, 0));
    arena[280]^=1;
    assert(obor_resource_catalog_prepare(c, sizeof(arena), NULL, NULL));
    assert(!obor_resource_catalog_manifest_unchanged(c, generation, first+record, record));
    assert(!obor_resource_catalog_mask_unchanged(c, NULL, 0, 272, sizeof(expected)));
    assert(obor_resource_catalog_mask_unchanged(c, NULL, 0, 308, 100));
    generation = obor_resource_catalog_generation(c);
    memcpy(arena + 528, expected, sizeof(expected));
    assert(obor_resource_catalog_add(c, 512, 128, 528, recipe)); /* reuse empty slot0 */
    assert(obor_resource_catalog_prepare(c, sizeof(arena), NULL, NULL));
    assert(!obor_resource_catalog_manifest_unchanged(c, generation, first, record));
    assert(obor_resource_catalog_manifest_unchanged(c, generation, first+record, record));
    obor_resource_catalog_destroy(c);
}
static unsigned proof_calls;
static int counted_unchanged(void *context, uint32_t offset, uint32_t length)
{ ++proof_calls; return unchanged(context, offset, length); }

static void test_range_proofs(obor_resource_materializer *m, const obor_resource_recipe *recipe)
{
    unsigned char arena[4096]; memset(arena, 0, sizeof(arena));
    memcpy(arena + 80, expected, sizeof(expected));
    memcpy(arena + 272, expected, sizeof(expected));
    obor_resource_catalog *c = obor_resource_catalog_create(m, &allocator, arena, sizeof(arena));
    assert(c && obor_resource_catalog_add(c, 64, 128, 80, recipe));
    assert(obor_resource_catalog_add(c, 256, 128, 272, recipe));
    assert(obor_resource_catalog_prepare(c, sizeof(arena), NULL, NULL));
    uint32_t size, repeat_size;
    unsigned char *original = save_manifest(c, &size);
    proof_calls = 0;
    assert(obor_resource_catalog_prepare(c, sizeof(arena), counted_unchanged, NULL));
    assert(proof_calls == 1); /* one actual range proof, never blind manifest reuse */
    const void *repeat = obor_resource_catalog_manifest(c, &repeat_size);
    assert(size == repeat_size && !memcmp(original, repeat, size));
    assert(obor_resource_catalog_mask_count(c) == 2);

    /* A byte within the far resource must invalidate an envelope whose start
     * points at the other resource. Compare the result to the actual body. */
    uint32_t dirty = 280;
    arena[dirty] ^= 1;
    assert(obor_resource_catalog_prepare(c, sizeof(arena), counted_unchanged, &dirty));
    assert(obor_resource_catalog_mask_count(c) == 1);
    unsigned char snapshot[4096]; memcpy(snapshot, arena, sizeof(snapshot));
    obor_resource_catalog_zero(c, 0, snapshot, sizeof(snapshot));
    assert(!memcmp(snapshot + 272, arena + 272, sizeof(expected)));
    proof_calls = 0;
    assert(obor_resource_catalog_prepare(c, sizeof(arena), counted_unchanged, NULL));
    assert(proof_calls == 1 && obor_resource_catalog_mask_count(c) == 1);

    /* Raw bodies belong to the envelope too: restoring the original bytes
     * must make the resource reconstructible again. */
    arena[dirty] ^= 1;
    assert(obor_resource_catalog_prepare(c, sizeof(arena), counted_unchanged, &dirty));
    assert(obor_resource_catalog_mask_count(c) == 2);
    arena[90] ^= 1;
    obor_resource_catalog_forget_proofs(c);
    proof_calls = 0;
    assert(obor_resource_catalog_prepare(c, sizeof(arena), counted_unchanged, NULL));
    assert(proof_calls == 0 && obor_resource_catalog_mask_count(c) == 1);
    arena[90] ^= 1;
    assert(obor_resource_catalog_prepare(c, sizeof(arena), NULL, NULL));
    assert(obor_resource_catalog_mask_count(c) == 2);

    /* Extent and lifetime changes must validate before reusing any envelope. */
    assert(!obor_resource_catalog_prepare(c, 300, counted_unchanged, NULL));
    test_unprepared_read(c);
    assert(obor_resource_catalog_prepare(c, sizeof(arena), counted_unchanged, NULL));
    obor_resource_catalog_remove(c, 256);
    assert(obor_resource_catalog_prepare(c, sizeof(arena), counted_unchanged, NULL));
    assert(obor_resource_catalog_mask_count(c) == 1);
    memset(arena + 272, 0xdd, sizeof(expected));
    assert(!obor_resource_catalog_add(c, 256, 128, 272, recipe)); /* registration proves bytes */
    memcpy(arena + 272, expected, sizeof(expected));
    assert(obor_resource_catalog_add(c, 256, 128, 272, recipe));
    arena[280] ^= 1; /* script mutation after successful registration */
    assert(obor_resource_catalog_prepare(c, sizeof(arena), counted_unchanged, &dirty));
    assert(obor_resource_catalog_mask_count(c) == 1);
    obor_resource_catalog_remove(c, 64);
    obor_resource_catalog_remove(c, 256);
    assert(obor_resource_catalog_prepare(c, sizeof(arena), counted_unchanged, NULL));
    assert(obor_resource_catalog_prepare(c, sizeof(arena), counted_unchanged, NULL));
    assert(obor_resource_catalog_mask_count(c) == 0);
    free(original); obor_resource_catalog_destroy(c);
    puts("range_proofs_mutation_forget_lifetime=1");
}

static obor_resource_catalog *restore(obor_resource_catalog *c, const void *manifest, uint32_t size,
        const unsigned char *snapshot, obor_resource_unchanged proof, void *ctx, size_t expected_staging)
{
    obor_resource_restore *plan = obor_resource_restore_prepare(c, manifest, size, 4096, proof, ctx);
    assert(plan && obor_resource_restore_staged(plan) == expected_staging);
    /* Span boundaries deliberately split both omitted bodies. */
    const uint32_t boundary[] = {0, 85, 105, 280, 300, 4096};
    for (unsigned i = 1; i < sizeof(boundary) / sizeof(boundary[0]); ++i)
        obor_resource_restore_copy(plan, boundary[i - 1], snapshot + boundary[i - 1], boundary[i] - boundary[i - 1]);
    obor_resource_catalog *target = obor_resource_restore_commit(plan); assert(target);
    obor_resource_restore_destroy(plan); obor_resource_catalog_destroy(c);
    return target;
}

typedef struct { const unsigned char *bytes; uint32_t size; int fail; } frame_snapshot;
static const void *read_frame_snapshot(void *context, uint32_t owner, uint32_t allocation,
        uint32_t offset, uint32_t length)
{
    frame_snapshot *s = context;
    if (s->fail || owner != 64 || allocation != 128 || offset != 80 || length != 32 ||
        offset > s->size || length > s->size-offset) return NULL;
    return s->bytes + offset;
}
static void test_framebuffer(obor_resource_materializer *m, const obor_resource_recipe *sprite)
{
    unsigned char arena[4096], snapshot[4096], before[4096];
    memset(arena, 0x72, sizeof(arena));
    const uint32_t pixels[8] = {0,0xff0000ff,0x12345678,0xffffffff,0x01ab3421,7,0xff00,0x830000};
    memcpy(arena+80, pixels, sizeof(pixels));
    obor_framebuffer_reconstruct(arena+80, arena+528, sizeof(pixels));
    assert(obor_framebuffer_matches(arena+80, arena+528, sizeof(pixels)));
    assert(!obor_framebuffer_matches(NULL, arena+528, 32));
    assert(!obor_framebuffer_matches(arena+80, arena+528, 31));
    unsigned char unaligned[33]; memcpy(unaligned+1,arena+80,32);
    assert(obor_framebuffer_matches(unaligned+1,arena+528,32));
    for (unsigned i=0;i<32;++i) {
        arena[528+i]^=1; assert(!obor_framebuffer_matches(arena+80,arena+528,32)); arena[528+i]^=1;
    }
    obor_framebuffer_source origin = {64,128,80,16}, decoded;
    obor_resource_recipe recipe, loaded, bad;
    assert(obor_resource_recipe_framebuffer(&recipe,&origin,4,2));
    unsigned char wire[OBOR_RESOURCE_RECIPE_SIZE];
    assert(obor_resource_recipe_write(&recipe,wire,sizeof(wire)));
    assert(wire[0]==3 && wire[32]==OBOR_RESOURCE_ABGR32_FRAME && wire[40]==64 && wire[48]==80);
    assert(obor_resource_recipe_read(&loaded,wire,sizeof(wire)));
    assert(obor_resource_recipe_equal(&loaded,&recipe));
    assert(obor_resource_recipe_framebuffer_source(&loaded,&decoded));
    assert(!memcmp(&origin,&decoded,sizeof(origin)));
    for(unsigned i=56;i<sizeof(wire);++i) {
        wire[i]=1; assert(!obor_resource_recipe_read(&loaded,wire,sizeof(wire)));wire[i]=0;
    }
    bad=recipe;bad.version=2;assert(!obor_resource_recipe_valid(&bad));
    bad=recipe;bad.width=0;assert(!obor_resource_recipe_valid(&bad));
    bad=recipe;bad.length--;assert(!obor_resource_recipe_valid(&bad));
    origin.stride=17;assert(!obor_resource_recipe_framebuffer(&loaded,&origin,4,2));origin.stride=16;
    origin.allocation=32;assert(!obor_resource_recipe_framebuffer(&loaded,&origin,4,2));origin.allocation=128;
    assert(!obor_resource_recipe_framebuffer(&loaded,&origin,UINT32_MAX,2));
    assert(!obor_resource_recipe_body(m,&recipe)); /* no mutable source-body cache */
    obor_resource_catalog *c=obor_resource_catalog_create(m,&allocator,arena,sizeof(arena)); assert(c);
    assert(obor_resource_catalog_framebuffer(c,512,128,528,&recipe));
    assert(obor_resource_catalog_prepare(c,sizeof(arena),NULL,NULL));
    assert(obor_resource_catalog_mask_count(c)==1);
    uint64_t generation=obor_resource_catalog_generation(c);
    assert(obor_resource_catalog_framebuffer(c,512,128,528,&recipe));
    assert(obor_resource_catalog_generation(c)==generation); /* no per-capture churn */
    assert(obor_resource_catalog_prepare(c,sizeof(arena),unchanged,NULL));
    assert(obor_resource_catalog_generation(c)==generation);
    uint32_t dirty=81; arena[dirty]^=1; /* source changes, destination does not */
    assert(obor_resource_catalog_prepare(c,sizeof(arena),unchanged,&dirty));
    assert(!obor_resource_catalog_mask_count(c));
    arena[dirty]^=1;
    assert(obor_resource_catalog_prepare(c,sizeof(arena),unchanged,&dirty));
    assert(obor_resource_catalog_mask_count(c)==1);
    dirty=531;arena[dirty]^=1;
    assert(obor_resource_catalog_prepare(c,sizeof(arena),unchanged,&dirty));
    assert(!obor_resource_catalog_mask_count(c));arena[dirty]^=1;
    assert(obor_resource_catalog_prepare(c,sizeof(arena),unchanged,&dirty));
    assert(obor_resource_catalog_mask_count(c)==1);
    uint32_t size;unsigned char *manifest=save_manifest(c,&size);
    assert(obor_resource_catalog_read(c,0,snapshot,sizeof(snapshot)));
    for(unsigned i=528;i<560;++i) assert(snapshot[i]==0);
    frame_snapshot incoming={snapshot,sizeof(snapshot),0};
    memcpy(before,arena,sizeof(arena));
    assert(!obor_resource_restore_prepare(c,manifest,size,sizeof(arena),unchanged,NULL));
    incoming.fail=1;
    assert(!obor_resource_restore_prepare_snapshot(c,manifest,size,sizeof(arena),unchanged,NULL,read_frame_snapshot,&incoming));
    assert(!memcmp(before,arena,sizeof(arena)));incoming.fail=0;
    /* Same recipe, different current pixels, even a current unchanged proof:
     * restoration MUST stage from incoming bytes, never reuse current output. */
    arena[80]^=0x31;obor_framebuffer_reconstruct(arena+80,arena+528,32);
    assert(obor_resource_catalog_prepare(c,sizeof(arena),NULL,NULL));
    obor_resource_restore *plan=obor_resource_restore_prepare_snapshot(c,manifest,size,sizeof(arena),unchanged,NULL,read_frame_snapshot,&incoming);
    assert(plan && obor_resource_restore_staged(plan)==32);
    obor_resource_restore_copy(plan,0,snapshot,sizeof(snapshot));
    obor_resource_catalog *restored=obor_resource_restore_commit(plan);assert(restored);
    assert(!memcmp(before,arena,sizeof(arena)));
    obor_resource_restore_destroy(plan);obor_resource_catalog_destroy(restored);free(manifest);
    assert(obor_resource_catalog_framebuffer(c,0,0,0,NULL));
    assert(obor_resource_catalog_prepare(c,sizeof(arena),NULL,NULL));
    assert(!obor_resource_catalog_mask_count(c));
    /* A source covered by a different resource must remain raw: there is no
     * dependency graph. Once that omission is removed eligibility recovers. */
    memcpy(arena+80,expected,sizeof(expected));
    obor_framebuffer_reconstruct(arena+80,arena+528,32);
    assert(obor_resource_catalog_add(c,64,128,80,sprite));
    assert(obor_resource_catalog_framebuffer(c,512,128,528,&recipe));
    assert(obor_resource_catalog_prepare(c,sizeof(arena),NULL,NULL));
    assert(obor_resource_catalog_mask_count(c)==1);
    obor_resource_mask_range range;
    assert(obor_resource_catalog_copy_mask(c,&range,1) && range.offset==80);
    obor_resource_catalog_remove(c,64);
    assert(obor_resource_catalog_prepare(c,sizeof(arena),unchanged,NULL));
    assert(obor_resource_catalog_mask_count(c)==1);
    assert(obor_resource_catalog_copy_mask(c,&range,1) && range.offset==528);
    obor_resource_catalog_remove(c,512);
    assert(obor_resource_catalog_prepare(c,sizeof(arena),NULL,NULL));
    assert(!obor_resource_catalog_mask_count(c));
    obor_resource_catalog_destroy(c);
    puts("frame_exact_fallback=1 source_dirty_proof=1 incoming_snapshot_only=1 no_resource_cycles=1");
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    FILE *file = fopen(argv[1], "rb"); assert(file);
    assert(!fseek(file, 0, SEEK_END)); long length = ftell(file); assert(length > 0 && length < (1 << 20));
    rewind(file);
    input_data input = {malloc((size_t)length), (size_t)length, 0}; assert(input.bytes);
    assert(fread(input.bytes, 1, input.length, file) == input.length); fclose(file);
    unsigned char arena[4096], original[4096], snapshot[4096], changed[4096], snapshot_changed[4096];
    memset(arena, 0xab, sizeof(arena));
    memcpy(arena + 80, expected, sizeof(expected)); memcpy(arena + 272, expected, sizeof(expected));
    memcpy(original, arena, sizeof(arena));
    image_test_reset(0);
    obor_resource_source *source = open_source(&input); assert(source);
    obor_resource_materializer *m = obor_resource_materializer_create(source, &allocator, 2048); assert(m);
    obor_resource_recipe r;
    assert(obor_resource_recipe_prove(m, &r, "data/image.png", 14, 5,3,0,0,5,3,expected,sizeof(expected)));
    test_current_mask(m, &r);
    test_range_proofs(m, &r);
    test_framebuffer(m, &r);
    obor_resource_catalog *c = obor_resource_catalog_create(m, &allocator, arena, sizeof(arena)); assert(c);
    test_unprepared_read(NULL);
    test_unprepared_read(c);
    /* Register in reverse address order: catalog sorting must not move wire slots. */
    assert(obor_resource_catalog_add(c, 256, 128, 272, &r));
    assert(obor_resource_catalog_add(c, 64, 128, 80, &r));
    assert(obor_resource_catalog_prepare(c, sizeof(arena), NULL, NULL));
    uint32_t menu_size, modified_size;
    unsigned char *menu = save_manifest(c, &menu_size);
    /* A failed preparation cannot expose ranges from an earlier snapshot. */
    assert(!obor_resource_catalog_prepare(c, 64, NULL, NULL));
    test_unprepared_read(c);
    assert(obor_resource_catalog_prepare(c, sizeof(arena), NULL, NULL));
    /* Stable bodies/owners retain the exact manifest and omission ranges even
     * when a snapshot's arena extent changes independently of resources. */
    assert(obor_resource_catalog_prepare(c, sizeof(arena) - 1, unchanged, NULL));
    uint32_t stable_size; unsigned char *stable = save_manifest(c, &stable_size);
    assert(stable_size == menu_size && !memcmp(stable, menu, 16) &&
        !memcmp(stable + 20, menu + 20, menu_size - 20));
    assert(stable[16] == 255 && stable[17] == 15); free(stable);
    assert(obor_resource_catalog_prepare(c, sizeof(arena), unchanged, NULL));
    const void *current_manifest = obor_resource_catalog_manifest(c, &stable_size);
    assert(stable_size == menu_size && !memcmp(current_manifest, menu, menu_size));
    memcpy(snapshot, arena, sizeof(arena)); obor_resource_catalog_zero(c, 0, snapshot, sizeof(snapshot));
    for (size_t i = 0; i < sizeof(arena); ++i) {
        int body = (i >= 80 && i < 80 + sizeof(expected)) || (i >= 272 && i < 272 + sizeof(expected));
        assert(snapshot[i] == (body ? 0 : arena[i]));
    }
#if defined(__SANITIZE_ADDRESS__)
    /* Proof/materialization finished before poisoning. Serializing the logical
     * image must never read either omitted source body, even in a mixed span. */
    __asan_poison_memory_region(arena+80,sizeof(expected));
    __asan_poison_memory_region(arena+272,sizeof(expected));
#endif
    test_logical_read(c,snapshot);
#if defined(__SANITIZE_ADDRESS__)
    __asan_unpoison_memory_region(arena+80,sizeof(expected));
    __asan_unpoison_memory_region(arena+272,sizeof(expected));
#endif
    /* Exact unchanged proof permits retaining identical live resources, with no
     * decoded historical bodies retained in another buffer. */
    c = restore(c, menu, menu_size, snapshot, unchanged, NULL, 0);
    assert(!memcmp(arena, original, sizeof(arena)));
    uint32_t dirty = 80;
    arena[95] ^= 0x40; arena[65] ^= 1; arena[120] ^= 2;
    assert(obor_resource_catalog_prepare(c, sizeof(arena), unchanged, &dirty));
    unsigned char *modified = save_manifest(c, &modified_size);
    assert(menu_size == modified_size);
    assert(!memcmp(menu + OBOR_RESOURCE_MANIFEST_HEADER,
        modified + OBOR_RESOURCE_MANIFEST_HEADER, OBOR_RESOURCE_MANIFEST_RECORD));
    memcpy(changed, arena, sizeof(arena)); memcpy(snapshot_changed, arena, sizeof(arena));
    obor_resource_catalog_zero(c, 0, snapshot_changed, sizeof(snapshot_changed));
    assert(!memcmp(snapshot_changed + 80, arena + 80, sizeof(expected)));
    test_logical_read(c,snapshot_changed);
    c = restore(c, menu, menu_size, snapshot, unchanged, &dirty, sizeof(expected));
    assert(!memcmp(arena, original, sizeof(arena)));

    /* Both original owners are freed and reused by unrelated allocations.
     * A new session reconstructs solely from manifest and content. */
    obor_resource_catalog_remove(c, 64);
    test_unprepared_read(c);
    obor_resource_catalog_remove(c, 256);
    memset(arena, 0xee, sizeof(arena));
    assert(obor_resource_catalog_prepare(c, sizeof(arena), unchanged, NULL));
    unsigned char raw[4096]; memcpy(raw, arena, sizeof(raw));
    obor_resource_catalog_zero(c, 0, raw, sizeof(raw)); assert(!memcmp(raw, arena, sizeof(raw)));
    test_logical_read(c,raw);
    obor_resource_catalog_destroy(c); obor_resource_materializer_destroy(m); obor_resource_source_destroy(source);
    assert(!image_test_live());
    source = open_source(&input); assert(source);
    m = obor_resource_materializer_create(source, &allocator, 0); assert(m);
    c = obor_resource_catalog_create(m, &allocator, arena, sizeof(arena)); assert(c);
    c = restore(c, menu, menu_size, snapshot, NULL, NULL, 2 * sizeof(expected));
    assert(!memcmp(arena, original, sizeof(arena)) && !obor_resource_materializer_cached(m));
    c = restore(c, modified, modified_size, snapshot_changed, NULL, NULL, sizeof(expected));
    assert(!memcmp(arena, changed, sizeof(arena)));

    /* Malformed recipes, unavailable content and overlapping ownership fail
     * before the existing world changes. Full target resource set is staged. */
    unsigned char *bad = malloc(menu_size); assert(bad);
    memcpy(bad, menu, menu_size); bad[OBOR_RESOURCE_MANIFEST_HEADER + 16 + 32] ^= 1;
    assert(!obor_resource_restore_prepare(c, bad, menu_size, 4096, NULL, NULL));
    assert(!memcmp(arena, changed, sizeof(arena)));
    input.fail = 1;
    assert(!obor_resource_restore_prepare(c, menu, menu_size, 4096, NULL, NULL)); input.fail = 0;
    assert(!memcmp(arena, changed, sizeof(arena)));
    memcpy(bad, menu, menu_size);
    memcpy(bad + OBOR_RESOURCE_MANIFEST_HEADER + OBOR_RESOURCE_MANIFEST_RECORD,
        bad + OBOR_RESOURCE_MANIFEST_HEADER, OBOR_RESOURCE_MANIFEST_RECORD);
    assert(!obor_resource_restore_prepare(c, bad, menu_size, 4096, NULL, NULL));
    assert(!obor_resource_restore_prepare(c, menu, menu_size - 1, 4096, NULL, NULL));
    assert(!obor_resource_restore_prepare(c, menu, menu_size, 64, NULL, NULL));
    for (uint32_t i = 0; i < menu_size; ++i) {
        memcpy(bad, menu, menu_size); bad[i] ^= 0xff;
        obor_resource_restore *plan = obor_resource_restore_prepare(c, bad, menu_size, 4096, NULL, NULL);
        obor_resource_restore_destroy(plan);
        assert(!memcmp(arena, changed, sizeof(arena)));
    }
    obor_resource_catalog_destroy(c); obor_resource_materializer_destroy(m); obor_resource_source_destroy(source);
    assert(!image_test_live());

    size_t attempts = 0;
    for (size_t failure = 0; !failure || failure <= attempts; ++failure) {
        image_test_reset(failure); memset(arena, 0xee, sizeof(arena));
        source = open_source(&input);
        if (source) {
            m = obor_resource_materializer_create(source, &allocator, 0);
            if (m) {
                c = obor_resource_catalog_create(m, &allocator, arena, sizeof(arena));
                if (c) {
                    obor_resource_restore *plan = obor_resource_restore_prepare(c, menu, menu_size, 4096, NULL, NULL);
                    for (unsigned i = 0; i < sizeof(arena); ++i) assert(arena[i] == 0xee);
                    if (plan) {
                        obor_resource_restore_copy(plan, 0, snapshot, sizeof(snapshot));
                        obor_resource_catalog *target = obor_resource_restore_commit(plan); assert(target);
                        assert(!memcmp(arena, original, sizeof(arena)));
                        obor_resource_catalog_destroy(target);
                    }
                    obor_resource_restore_destroy(plan); obor_resource_catalog_destroy(c);
                }
                obor_resource_materializer_destroy(m);
            }
            obor_resource_source_destroy(source);
        }
        if (!failure) attempts = image_test_attempts();
        assert(!image_test_live() && image_test_peak() < (32U << 20));
    }
    free(bad); free(menu); free(modified); free(input.bytes);
    puts("cold_menu_resources=1 mutable_body=1 free_reuse=1 stable_slots=1 preflight_failures_atomic=1");
    return 0;
}
