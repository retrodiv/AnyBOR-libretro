/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
/* Reuse the independent A5 allocator, canonical manifest/arena/mask oracle and
 * PACK reader. Include the actual catalog TU only to force counter boundaries;
 * no test hooks or alternate writer are added to production. */
#define main capacity_fixture_main
#include "resource_catalog_capacity_test.c"
#undef main

#ifndef EXPECT_INCREMENTAL
#define EXPECT_INCREMENTAL 1
#endif
#ifndef OBOR_CATALOG_CACHE_FIELDS
#define OBOR_CATALOG_CACHE_FIELDS 0
#endif
#ifndef OBOR_CATALOG_IMPLEMENTATION
#define OBOR_CATALOG_IMPLEMENTATION "obor_resource_catalog.c"
#endif
static size_t recipe_writes, refused_write, refused_observed, dirty_proofs;
int catalog_test_recipe_write(const obor_resource_recipe *, void *, size_t);
#define obor_resource_recipe_write catalog_test_recipe_write
#include OBOR_CATALOG_IMPLEMENTATION
#undef obor_resource_recipe_write

int catalog_test_recipe_write(const obor_resource_recipe *recipe, void *output, size_t size)
{
    ++recipe_writes;
    int result = obor_resource_recipe_write(recipe,output,size);
    /* A refusal may follow real writes: callers must not trust any part of
     * the previous metadata guarantee after a partially emitted manifest. */
    if (result && recipe_writes == refused_write) { ++refused_observed; return 0; }
    return result;
}
static int always_dirty(void *context, uint32_t offset, uint32_t length)
{
    (void)context; (void)offset; assert(length); ++dirty_proofs;
    return 0; /* RW/hot pages never obtain an immutability proof. */
}
static void prepare_expect(obor_resource_catalog *catalog, uint32_t used,
        size_t incremental, size_t original)
{
    size_t before = recipe_writes;
    assert(obor_resource_catalog_prepare(catalog,used,always_dirty,NULL));
    size_t expected = EXPECT_INCREMENTAL ? incremental : original;
    if (recipe_writes - before != expected)
        fprintf(stderr,"recipe writes: got=%zu expected=%zu incremental=%d\n",
                recipe_writes-before,expected,EXPECT_INCREMENTAL);
    assert(recipe_writes - before == expected);
}
static void rejected_view(obor_resource_catalog *catalog)
{
    uint32_t size = UINT32_MAX;
    assert(!obor_resource_catalog_manifest(catalog,&size) && !size);
    assert(!obor_resource_catalog_mask_count(catalog));
}
static void test_incremental(obor_resource_materializer *materializer,
        const obor_resource_recipe *recipe, FILE *canonical)
{
    unsigned char arena[8192]; memset(arena,0x71,sizeof(arena));
    slot_state slots[132]; memset(slots,0,sizeof(slots));
    obor_resource_catalog *c = obor_resource_catalog_create(materializer,&allocator,arena,sizeof(arena));
    assert(c);
    for (uint32_t i=0;i<3;++i) { slots[i]=(slot_state){64+i*32,1}; add(c,arena,slots[i].owner,recipe); }
    prepare_expect(c,sizeof(arena),3,3);
    check(c,arena,sizeof(arena),slots,3,recipe,canonical);
    slots[3]=(slot_state){64+3*32,1}; add(c,arena,slots[3].owner,recipe);
    prepare_expect(c,sizeof(arena),1,4); /* Existing canonical recipes stay in place. */
    check(c,arena,sizeof(arena),slots,4,recipe,canonical);

    size_t proofs = dirty_proofs;
    arena[slots[1].owner+9]^=1;
    prepare_expect(c,sizeof(arena),1,4);
    assert(dirty_proofs-proofs==5); /* Envelope + all four hot/RW bodies. */
    check(c,arena,sizeof(arena),slots,4,recipe,canonical);
    arena[slots[1].owner+10]^=1;
    prepare_expect(c,sizeof(arena),0,0); /* Already raw: live bytes still change. */
    check(c,arena,sizeof(arena),slots,4,recipe,canonical);
    memcpy(arena+slots[1].owner+8,body,sizeof(body));
    prepare_expect(c,sizeof(arena),1,4);
    check(c,arena,sizeof(arena),slots,4,recipe,canonical);

    obor_resource_catalog_remove(c,slots[0].owner); slots[0].active=0;
    obor_resource_catalog_remove(c,slots[2].owner); slots[2].active=0;
    prepare_expect(c,sizeof(arena),0,2);
    check(c,arena,sizeof(arena),slots,4,recipe,canonical);
    slots[2]=(slot_state){5000,1}; add(c,arena,slots[2].owner,recipe);
    slots[0]=(slot_state){5032,1}; add(c,arena,slots[0].owner,recipe);
    prepare_expect(c,sizeof(arena),2,4);
    check(c,arena,sizeof(arena),slots,4,recipe,canonical);
    for (uint32_t i=4;i<64;++i) { slots[i]=(slot_state){64+i*32,1}; add(c,arena,slots[i].owner,recipe); }
    prepare_expect(c,sizeof(arena),60,64);
    check(c,arena,sizeof(arena),slots,64,recipe,canonical);

    uint32_t previous_size;
    const unsigned char *previous = obor_resource_catalog_manifest(c,&previous_size);
    unsigned char *copy = malloc(previous_size); assert(copy); memcpy(copy,previous,previous_size);
    slots[64]=(slot_state){64+64*32,1}; add(c,arena,slots[64].owner,recipe);
    fail_at=attempts+1;
    assert(!obor_resource_catalog_prepare(c,sizeof(arena),always_dirty,NULL));
    fail_at=0; rejected_view(c);
    assert(!memcmp(previous,copy,previous_size)); free(copy);
    prepare_expect(c,sizeof(arena),65,65); /* Reallocation discards the old bytes. */
    check(c,arena,sizeof(arena),slots,65,recipe,canonical);

    assert(!obor_resource_catalog_prepare(c,sizeof(arena)+1,always_dirty,NULL));
#if EXPECT_INCREMENTAL
    rejected_view(c);
#endif
    prepare_expect(c,sizeof(arena),65,0); /* Even an early refusal loses the guarantee. */
    check(c,arena,sizeof(arena),slots,65,recipe,canonical);

    previous=obor_resource_catalog_manifest(c,&previous_size);
    copy=malloc(previous_size); assert(copy); memcpy(copy,previous,previous_size);
    unsigned char before_arena[sizeof(arena)];
    slots[65]=(slot_state){64+65*32,1}; add(c,arena,slots[65].owner,recipe);
    arena[slots[1].owner+9]^=1;
    memcpy(before_arena,arena,sizeof(arena));
    refused_write=recipe_writes+2;
    assert(!obor_resource_catalog_prepare(c,sizeof(arena),always_dirty,NULL));
    assert(refused_observed==1); refused_write=0; rejected_view(c);
    /* The failed writer really changed the old buffer, but never the arena. */
    assert(!memcmp(arena,before_arena,sizeof(arena)));
    assert(memcmp(previous,copy,previous_size)); free(copy);
    prepare_expect(c,sizeof(arena),66,66);
    check(c,arena,sizeof(arena),slots,66,recipe,canonical);

    obor_resource_catalog_forget_proofs(c);
    memcpy(arena+slots[1].owner+8,body,sizeof(body));
    prepare_expect(c,sizeof(arena),1,66);
    check(c,arena,sizeof(arena),slots,66,recipe,canonical);
    previous=obor_resource_catalog_manifest(c,&previous_size);
    copy=malloc(previous_size); assert(copy); memcpy(copy,previous,previous_size);
    arena[slots[1].owner+9]^=3;
    obor_resource_restore *restore=obor_resource_restore_prepare(c,copy,previous_size,sizeof(arena),NULL,NULL);
    assert(restore);
    obor_resource_catalog *loaded=obor_resource_restore_commit(restore); assert(loaded);
    obor_resource_restore_destroy(restore); obor_resource_catalog_destroy(c); c=loaded; free(copy);
    prepare_expect(c,sizeof(arena),66,0); /* A loaded catalog starts without a local cache proof. */
    check(c,arena,sizeof(arena),slots,66,recipe,canonical);
    slots[66]=(slot_state){64+66*32,1}; add(c,arena,slots[66].owner,recipe);
    prepare_expect(c,sizeof(arena),1,67);
    check(c,arena,sizeof(arena),slots,67,recipe,canonical);

    uint64_t generation=c->generation;
    slots[67]=(slot_state){64+67*32,1}; add(c,arena,slots[67].owner,recipe);
    c->generation=1; /* Incoherent with the known last complete generation. */
    prepare_expect(c,sizeof(arena),68,68);
    check(c,arena,sizeof(arena),slots,68,recipe,canonical);
    c->generation=generation+2; c->manifest_size=0;
    prepare_expect(c,sizeof(arena),68,68);
#if OBOR_CATALOG_CACHE_FIELDS
    c->manifest_slots=UINT32_MAX; /* No out-of-range access to a purported cache. */
    prepare_expect(c,sizeof(arena),68,0);
#endif
    c->generation=UINT64_MAX;
    arena[slots[3].owner+9]^=1; /* Eligibility increments across the generation boundary. */
    prepare_expect(c,sizeof(arena),68,68);
    assert(c->generation==0);
    check(c,arena,sizeof(arena),slots,68,recipe,canonical);
    obor_resource_catalog_destroy(c);
}
static void test_recipe_replacement(obor_resource_materializer *materializer,
        const obor_resource_recipe *recipe, FILE *canonical)
{
    unsigned char arena[4096]; memset(arena,0x71,sizeof(arena));
    slot_state slot={64,1};
    obor_resource_catalog *c=obor_resource_catalog_create(materializer,&allocator,arena,sizeof(arena));
    assert(c); add(c,arena,64,recipe);
    prepare_expect(c,sizeof(arena),1,1);
    check(c,arena,sizeof(arena),&slot,1,recipe,canonical);
    obor_resource_recipe replacement;
    assert(obor_resource_recipe_prove_bytes(materializer,&replacement,"data/sample.bin",15,100,body,sizeof(body)));
    add(c,arena,64,&replacement);
    prepare_expect(c,sizeof(arena),1,1);
    check(c,arena,sizeof(arena),&slot,1,&replacement,canonical);
    obor_resource_catalog_destroy(c);
}
int main(int argc,char **argv)
{
    assert(argc==2 || argc==3);
    FILE *file=fopen(argv[1],"rb"); assert(file);
    assert(!fseek(file,0,SEEK_END)); long length=ftell(file); assert(length>0); rewind(file);
    input_data input={malloc((size_t)length),(size_t)length}; assert(input.bytes);
    assert(fread(input.bytes,1,input.size,file)==input.size); assert(!fclose(file));
    const obor_resource_reader reader={&input,input.size,read_input};
    obor_resource_source *source=obor_resource_source_create(&reader,&allocator); assert(source);
    obor_resource_materializer *materializer=obor_resource_materializer_create(source,&allocator,1024*1024); assert(materializer);
    obor_resource_recipe recipe;
    assert(obor_resource_recipe_prove_bytes(materializer,&recipe,"data/sample.bin",15,44,body,sizeof(body)));
    FILE *canonical=argc==3?fopen(argv[2],"wb"):NULL; assert(argc!=3 || canonical);
    test_incremental(materializer,&recipe,canonical);
    test_recipe_replacement(materializer,&recipe,canonical);
    if (canonical) assert(!fclose(canonical));
    obor_resource_materializer_destroy(materializer); obor_resource_source_destroy(source); free(input.bytes);
    assert(!live && !allocations);
    printf("incremental_metadata=%d a5=1 hot_rw_rechecked=1 retire_reuse=1 growth=1 early_failure=1 partial_recipe_failure=1 load_first_full=1 forget=1 recipe_replaced=1 counters_wrap=1 canonical_states=%u recipe_writes=%zu dirty_proofs=%zu\n",
            EXPECT_INCREMENTAL,canonical_states,recipe_writes,dirty_proofs);
    return 0;
}
