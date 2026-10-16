/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#define main capacity_fixture_main
#include "resource_catalog_capacity_test.c"
#undef main
#ifndef EXPECT_RANGE_MERGE
#define EXPECT_RANGE_MERGE 1
#endif
#ifndef OBOR_CATALOG_IMPLEMENTATION
#define OBOR_CATALOG_IMPLEMENTATION "obor_resource_catalog.c"
#endif
static size_t sorted_elements, sort_calls, recipe_calls, refuse_recipe, observed_refusal;
void range_test_sort(void *,size_t,size_t,int (*)(const void *,const void *));
int range_test_recipe(const obor_resource_recipe *,void *,size_t);
#define qsort range_test_sort
#define obor_resource_recipe_write range_test_recipe
#include OBOR_CATALOG_IMPLEMENTATION
#undef qsort
#undef obor_resource_recipe_write
void range_test_sort(void *base,size_t count,size_t width,int (*compare)(const void *,const void *))
{
    assert(width==sizeof(catalog_range)); sorted_elements+=count; ++sort_calls;
    qsort(base,count,width,compare);
}
int range_test_recipe(const obor_resource_recipe *recipe,void *out,size_t size)
{
    ++recipe_calls; int result=obor_resource_recipe_write(recipe,out,size);
    if(result && recipe_calls==refuse_recipe) { ++observed_refusal; return 0; }
    return result;
}
static int dirty_range(void *unused,uint32_t offset,uint32_t length)
{ (void)unused;(void)offset;assert(length);return 0; }
static void prepare_ranges(obor_resource_catalog *c,uint32_t used,size_t merge,size_t full)
{
    size_t before=sorted_elements;
    assert(obor_resource_catalog_prepare(c,used,dirty_range,NULL));
    size_t expected=EXPECT_RANGE_MERGE?merge:full;
    if(sorted_elements-before!=expected)
        fprintf(stderr,"sorted allocations: got=%zu expected=%zu merge=%d\n",sorted_elements-before,expected,EXPECT_RANGE_MERGE);
    assert(sorted_elements-before==expected);
    assert(c->ordered_generation==c->generation && c->ordered_count==c->active);
}
typedef struct { uint32_t owner,allocation; int active; } expected_range;
static void register_range(obor_resource_catalog *c,unsigned char *arena,
        expected_range *expected,uint32_t slot,uint32_t owner,uint32_t allocation,const obor_resource_recipe *recipe)
{
    memcpy(arena+owner+8,body,sizeof(body));
    assert(obor_resource_catalog_add(c,owner,allocation,owner+8,recipe));
    expected[slot]=(expected_range){owner,allocation,1};
}
static int expected_order(const void *a,const void *b)
{
    const obor_resource_mask_range *x=a,*y=b;
    return (x->offset>y->offset)-(x->offset<y->offset);
}
static void canonical_ranges(obor_resource_catalog *c,const unsigned char *arena,uint32_t used,
        const expected_range *expected,uint32_t slots,const obor_resource_recipe *recipe,FILE *output)
{
    uint32_t size;const unsigned char *manifest=obor_resource_catalog_manifest(c,&size);
    assert(manifest && size==manifest_bytes(slots));
    unsigned char *wire=calloc(1,size),*logical=malloc(used),*actual=malloc(used);
    obor_resource_mask_range mask[132],observed[132];uint32_t active=0,omitted=0;
    assert(wire && logical && actual);memcpy(logical,arena,used);
    for(uint32_t i=0;i<slots;++i) {
        if(!expected[i].active)continue;
        uint32_t owner=expected[i].owner;int matches=!memcmp(arena+owner+8,body,sizeof(body));
        ++active;
        unsigned char *record=wire+OBOR_RESOURCE_MANIFEST_HEADER+i*OBOR_RESOURCE_MANIFEST_RECORD;
        put(record,owner);put(record+4,expected[i].allocation);put(record+8,owner+8);put(record+12,matches?3:1);
        assert(obor_resource_recipe_write(recipe,record+16,OBOR_RESOURCE_RECIPE_SIZE));
        if(matches) { mask[omitted++]=(obor_resource_mask_range){owner+8,sizeof(body)};memset(logical+owner+8,0,sizeof(body)); }
    }
    const uint32_t header[8]={OBOR_RESOURCE_MANIFEST_MAGIC,1,slots,OBOR_RESOURCE_MANIFEST_RECORD,used,omitted*sizeof(body),active,0};
    for(unsigned i=0;i<8;++i)put(wire+i*4,header[i]);
    assert(!memcmp(wire,manifest,size));free(wire);
    assert(obor_resource_catalog_read(c,0,actual,used));assert(!memcmp(logical,actual,used));
    qsort(mask,omitted,sizeof(*mask),expected_order);
    assert(obor_resource_catalog_mask_count(c)==omitted);
    assert(obor_resource_catalog_copy_mask(c,observed,132));assert(!memcmp(mask,observed,omitted*sizeof(*mask)));
    ++canonical_states;append_u32(output,size);append(output,manifest,size);
    append_u32(output,used);append(output,actual,used);append_u32(output,omitted);append(output,mask,omitted*sizeof(*mask));
    free(logical);free(actual);
}
static void refused_ranges(obor_resource_catalog *c)
{
    uint32_t size=UINT32_MAX;assert(!obor_resource_catalog_manifest(c,&size) && !size);
    assert(!obor_resource_catalog_mask_count(c) && !c->ordered_generation);
}
static void cases(obor_resource_materializer *materializer,const obor_resource_recipe *recipe,FILE *output)
{
    unsigned char arena[8192];memset(arena,0x71,sizeof(arena));
    expected_range expected[132];memset(expected,0,sizeof(expected));
    obor_resource_catalog *c=obor_resource_catalog_create(materializer,&allocator,arena,sizeof(arena));assert(c);
    register_range(c,arena,expected,0,512,32,recipe);register_range(c,arena,expected,1,64,32,recipe);
    register_range(c,arena,expected,2,1024,32,recipe);
    prepare_ranges(c,sizeof(arena),3,3);canonical_ranges(c,arena,sizeof(arena),expected,3,recipe,output);
    register_range(c,arena,expected,3,256,32,recipe);
    prepare_ranges(c,sizeof(arena),1,4);canonical_ranges(c,arena,sizeof(arena),expected,4,recipe,output);
    register_range(c,arena,expected,4,1792,32,recipe);register_range(c,arena,expected,5,1920,32,recipe);
    register_range(c,arena,expected,6,2048,32,recipe);register_range(c,arena,expected,7,384,32,recipe);
    register_range(c,arena,expected,8,768,32,recipe);
    prepare_ranges(c,sizeof(arena),5,9);canonical_ranges(c,arena,sizeof(arena),expected,9,recipe,output);
    obor_resource_catalog_remove(c,64);expected[1].active=0;obor_resource_catalog_remove(c,2048);expected[6].active=0;
    prepare_ranges(c,sizeof(arena),0,7);canonical_ranges(c,arena,sizeof(arena),expected,9,recipe,output);
    obor_resource_catalog_remove(c,512);expected[0].active=0;
    register_range(c,arena,expected,0,96,64,recipe); /* owner replacement in reused stable slot */
    register_range(c,arena,expected,2,1024,96,recipe); /* same owner, changed allocation */
    register_range(c,arena,expected,6,1280,32,recipe); /* earlier free slot reused */
    prepare_ranges(c,sizeof(arena),3,8);canonical_ranges(c,arena,sizeof(arena),expected,9,recipe,output);
    arena[96+9]^=1;
    prepare_ranges(c,sizeof(arena),1,8);canonical_ranges(c,arena,sizeof(arena),expected,9,recipe,output);
    arena[96+10]^=1;
    prepare_ranges(c,sizeof(arena),0,0);canonical_ranges(c,arena,sizeof(arena),expected,9,recipe,output);
    memcpy(arena+104,body,sizeof(body));
    prepare_ranges(c,sizeof(arena),1,8);canonical_ranges(c,arena,sizeof(arena),expected,9,recipe,output);

    register_range(c,arena,expected,2,1024,300,recipe); /* changed size crosses unchanged owner1280 */
    assert(!obor_resource_catalog_prepare(c,sizeof(arena),dirty_range,NULL));refused_ranges(c);
    register_range(c,arena,expected,2,1024,96,recipe);
    prepare_ranges(c,sizeof(arena),8,8);canonical_ranges(c,arena,sizeof(arena),expected,9,recipe,output);

    register_range(c,arena,expected,1,1808,32,recipe); /* changed against unchanged owner1792 */
    assert(!obor_resource_catalog_prepare(c,sizeof(arena),dirty_range,NULL));refused_ranges(c);
    obor_resource_catalog_remove(c,1808);expected[1].active=0;
    prepare_ranges(c,sizeof(arena),8,8);canonical_ranges(c,arena,sizeof(arena),expected,9,recipe,output);
    register_range(c,arena,expected,1,2304,64,recipe);
    register_range(c,arena,expected,9,2336,64,recipe); /* two changed allocations overlap */
    assert(!obor_resource_catalog_prepare(c,sizeof(arena),dirty_range,NULL));refused_ranges(c);
    obor_resource_catalog_remove(c,2304);expected[1].active=0;obor_resource_catalog_remove(c,2336);expected[9].active=0;
    prepare_ranges(c,sizeof(arena),8,8);canonical_ranges(c,arena,sizeof(arena),expected,10,recipe,output);

    /* Raw entries are still part of the complete allocation index. */
    arena[1792+9]^=1;prepare_ranges(c,sizeof(arena),1,8);
    register_range(c,arena,expected,9,1808,32,recipe);
    assert(!obor_resource_catalog_prepare(c,sizeof(arena),dirty_range,NULL));refused_ranges(c);
    obor_resource_catalog_remove(c,1808);expected[9].active=0;
    prepare_ranges(c,sizeof(arena),8,8);canonical_ranges(c,arena,sizeof(arena),expected,10,recipe,output);
    memcpy(arena+1800,body,sizeof(body));prepare_ranges(c,sizeof(arena),1,8);

    /* Even counter-incoherent metadata cannot hide unchanged/unchanged overlap. */
    uint32_t bucket,slot=catalog_find(c,1280,&bucket);assert(slot!=CATALOG_EMPTY);
    c->entries[slot].owner=1808;c->entries[slot].body=1816;
    memcpy(arena+1816,body,sizeof(body));c->manifest_size=0;
    assert(!obor_resource_catalog_prepare(c,sizeof(arena),dirty_range,NULL));refused_ranges(c);
    c->entries[slot].owner=1280;c->entries[slot].body=1288;
    prepare_ranges(c,sizeof(arena),8,8);canonical_ranges(c,arena,sizeof(arena),expected,10,recipe,output);

    /* Fail after real recipe stores, after the allocation index was merged. */
    register_range(c,arena,expected,9,3008,32,recipe);arena[96+9]^=1;
    uint32_t bytes;const void *old=obor_resource_catalog_manifest(c,&bytes);assert(!old); /* add invalidates view */
    unsigned char before_arena[sizeof(arena)];memcpy(before_arena,arena,sizeof(arena));
    unsigned char before_manifest[32+10*600];memcpy(before_manifest,c->manifest,sizeof(before_manifest));
    refuse_recipe=recipe_calls+2;
    assert(!obor_resource_catalog_prepare(c,sizeof(arena),dirty_range,NULL));
    assert(observed_refusal==1);refuse_recipe=0;refused_ranges(c);
    assert(!memcmp(before_arena,arena,sizeof(arena)) && memcmp(before_manifest,c->manifest,sizeof(before_manifest)));
    prepare_ranges(c,sizeof(arena),9,9);canonical_ranges(c,arena,sizeof(arena),expected,10,recipe,output);
    obor_resource_catalog_forget_proofs(c);memcpy(arena+104,body,sizeof(body));
    prepare_ranges(c,sizeof(arena),1,9);canonical_ranges(c,arena,sizeof(arena),expected,10,recipe,output);
    assert(!obor_resource_catalog_prepare(c,3039,dirty_range,NULL));refused_ranges(c);
    prepare_ranges(c,sizeof(arena),9,9);canonical_ranges(c,arena,sizeof(arena),expected,10,recipe,output);

    register_range(c,arena,expected,1,4000,32,recipe);
    for(uint32_t i=10;i<64;++i)register_range(c,arena,expected,i,4032+(i-10)*32,32,recipe);
    prepare_ranges(c,sizeof(arena),55,64);canonical_ranges(c,arena,sizeof(arena),expected,64,recipe,output);
    size_t old_live=live;uint64_t old_generation=c->ordered_generation;catalog_range *old_order=c->ordered;
    memcpy(arena+6008,body,sizeof(body));fail_at=attempts+3;
    assert(!obor_resource_catalog_add(c,6000,32,6008,recipe));fail_at=0;
    assert(live==old_live && c->ordered==old_order && c->ordered_generation==old_generation && c->capacity==64);
    register_range(c,arena,expected,64,6000,32,recipe);
    assert(!c->ordered_generation); /* Fresh A5 backing has no cached order. */
    fail_at=attempts+1;
    assert(!obor_resource_catalog_prepare(c,sizeof(arena),dirty_range,NULL));fail_at=0;refused_ranges(c);
    prepare_ranges(c,sizeof(arena),65,65);canonical_ranges(c,arena,sizeof(arena),expected,65,recipe,output);
    assert(!obor_resource_catalog_prepare(c,sizeof(arena)+1,dirty_range,NULL));refused_ranges(c);
    prepare_ranges(c,sizeof(arena),65,65);

    const void *manifest=obor_resource_catalog_manifest(c,&bytes);unsigned char *copy=malloc(bytes);assert(copy);memcpy(copy,manifest,bytes);
    arena[96+9]^=1;
    obor_resource_restore *plan=obor_resource_restore_prepare(c,copy,bytes,sizeof(arena),NULL,NULL);assert(plan);
    obor_resource_catalog *loaded=obor_resource_restore_commit(plan);assert(loaded);
    obor_resource_restore_destroy(plan);obor_resource_catalog_destroy(c);c=loaded;free(copy);
    assert(!c->ordered_generation);
    prepare_ranges(c,sizeof(arena),65,65);canonical_ranges(c,arena,sizeof(arena),expected,65,recipe,output);
    c->ordered_count=UINT32_MAX;
    prepare_ranges(c,sizeof(arena),65,65);
    c->ordered_generation=c->generation+1;
    prepare_ranges(c,sizeof(arena),65,65);canonical_ranges(c,arena,sizeof(arena),expected,65,recipe,output);
    c->generation=UINT64_MAX;arena[96+9]^=1;
    prepare_ranges(c,sizeof(arena),65,65);assert(!c->generation && !c->ordered_generation);
    canonical_ranges(c,arena,sizeof(arena),expected,65,recipe,output);
    obor_resource_catalog_destroy(c);
}
int main(int argc,char **argv)
{
    assert(argc==2 || argc==3);FILE *file=fopen(argv[1],"rb");assert(file);
    assert(!fseek(file,0,SEEK_END));long length=ftell(file);assert(length>0);rewind(file);
    input_data input={malloc((size_t)length),(size_t)length};assert(input.bytes);
    assert(fread(input.bytes,1,input.size,file)==input.size);assert(!fclose(file));
    const obor_resource_reader reader={&input,input.size,read_input};
    obor_resource_source *source=obor_resource_source_create(&reader,&allocator);assert(source);
    obor_resource_materializer *materializer=obor_resource_materializer_create(source,&allocator,1024*1024);assert(materializer);
    obor_resource_recipe recipe;
    assert(obor_resource_recipe_prove_bytes(materializer,&recipe,"data/sample.bin",15,44,body,sizeof(body)));
    FILE *output=argc==3?fopen(argv[2],"wb"):NULL;assert(argc!=3 || output);
    cases(materializer,&recipe,output);
    if(output)assert(!fclose(output));
    obor_resource_materializer_destroy(materializer);obor_resource_source_destroy(source);free(input.bytes);
    assert(!live && !allocations);
    printf("range_merge=%d all_bounds=1 global_nonoverlap=1 raw_included=1 retire_reuse=1 owner_size_changed=1 arbitrary_order=1 fallback_failure_load_realloc_wrap=1 canonical_states=%u sorted_elements=%zu sort_calls=%zu\n",
            EXPECT_RANGE_MERGE,canonical_states,sorted_elements,sort_calls);
    return 0;
}
