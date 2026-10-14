/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_resource_catalog.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
const void *obor_heap_resource_snapshot_read(const void *, uint64_t, uint64_t, uint32_t, uint32_t, uint32_t, uint32_t);
int obor_heap_resources_validate(const void *, uint64_t, uint64_t, const obor_resource_restore *);
int obor_heap_resources_restore(const void *, uint64_t, uint64_t, const obor_resource_restore *);
void image_test_reset(size_t);
void *image_test_allocate(size_t);
void image_test_release(void *);
size_t image_test_live(void);
static const obor_resource_image_allocator allocator = {image_test_allocate, image_test_release};
static int read_file(void *file, uint64_t offset, void *output, size_t length)
{ return !fseek(file, (long)offset, SEEK_SET) && fread(output, 1, length, file) == length; }
static const unsigned char body[] = {
    12,0,0,0,16,0,0,0,20,0,0,0,
    1,2,5,6,1,1,7,255,1,2,5,6,1,1,7,255,1,2,5,6,1,1,7,255
};
static void put64(void *out, uint64_t value) { memcpy(out, &value, sizeof(value)); }
int main(int argc, char **argv)
{
    assert(argc == 2); image_test_reset(0);
    FILE *file = fopen(argv[1], "rb"); assert(file);
    assert(!fseek(file, 0, SEEK_END)); long bytes = ftell(file); assert(bytes > 0);
    const obor_resource_reader reader = {file, (uint64_t)bytes, read_file};
    obor_resource_source *source = obor_resource_source_create(&reader, &allocator); assert(source);
    obor_resource_materializer *m = obor_resource_materializer_create(source, &allocator, 0); assert(m);
    obor_resource_recipe recipe;
    assert(obor_resource_recipe_prove(m, &recipe, "data/image.png", 14, 5,3,0,0,5,3,body,sizeof(body)));
    const uint32_t base = 16U << 20, used = base + 4096;
    unsigned char *arena = calloc(1, used); assert(arena);
    unsigned char expected[4096]; memset(expected, 0x72, sizeof(expected));
    /* Ordinary aligned live dlmalloc chunk: 144-byte chunk /136 usable bytes.
     * The next chunk's PINUSE marks this owner live. Body starts after its
     * engine header; palette and padding stay ordinary snapshot bytes. */
    put64(expected + 248, 144 | 3); put64(expected + 392, 64 | 1);
    memcpy(expected + 280, body, sizeof(body)); memcpy(arena + base, expected, sizeof(expected));
    obor_resource_catalog *c = obor_resource_catalog_create(m, &allocator, arena, used); assert(c);
    assert(obor_resource_catalog_add(c, base + 256, 136, base + 280, &recipe));
    assert(obor_resource_catalog_prepare(c, used, NULL, NULL));
    uint32_t manifest_size; const void *manifest = obor_resource_catalog_manifest(c, &manifest_size);
    unsigned char snapshot[32 + 16 + 4096];
    const uint32_t fields[] = {UINT32_C(0x3153484f), 2, 1, 0};
    memcpy(snapshot, fields, sizeof(fields)); put64(snapshot + 16, used); put64(snapshot + 24, 4096);
    put64(snapshot + 32, 0); put64(snapshot + 40, 4096); memcpy(snapshot + 48, expected, 4096);
    obor_resource_catalog_zero(c, base, snapshot + 48, 4096);
    obor_resource_restore *plan = obor_resource_restore_prepare(c, manifest, manifest_size, used, NULL, NULL);
    assert(plan && obor_heap_resources_validate(snapshot, sizeof(snapshot), used, plan));
    unsigned char saved[sizeof(snapshot)]; memcpy(saved, snapshot, sizeof(saved));
    /* Incoming source view is independently bounded and must describe a real
     * live allocation. This reader never consults the current arena. */
    const unsigned char *view = obor_heap_resource_snapshot_read(snapshot,sizeof(snapshot),used,
        base+256,136,base+272,16);
    assert(view == snapshot+48+272);
    assert(!obor_heap_resource_snapshot_read(snapshot,sizeof(snapshot),used,base+257,136,base+272,16));
    assert(!obor_heap_resource_snapshot_read(snapshot,sizeof(snapshot),used,base+256,135,base+272,16));
    assert(!obor_heap_resource_snapshot_read(snapshot,sizeof(snapshot),used,base+256,136,base+255,16));
    assert(!obor_heap_resource_snapshot_read(snapshot,sizeof(snapshot),used,base+256,136,base+390,3));
    assert(!obor_heap_resource_snapshot_read(snapshot,sizeof(snapshot),used,base+256,136,base+272,0));
    assert(!obor_heap_resource_snapshot_read(snapshot,sizeof(snapshot),used,base+256,UINT32_MAX,base+272,16));
    for (size_t length=0;length<sizeof(snapshot);length+=13)
        assert(!obor_heap_resource_snapshot_read(snapshot,length,used,base+256,136,base+272,16));
    put64(snapshot+48+248,144|1);
    assert(!obor_heap_resource_snapshot_read(snapshot,sizeof(snapshot),used,base+256,136,base+272,16));
    memcpy(snapshot,saved,sizeof(saved));
    put64(snapshot+48+392,64);
    assert(!obor_heap_resource_snapshot_read(snapshot,sizeof(snapshot),used,base+256,136,base+272,16));
    memcpy(snapshot,saved,sizeof(saved));

    snapshot[48 + 280] = 3; assert(!obor_heap_resources_validate(snapshot, sizeof(snapshot), used, plan));
    memcpy(snapshot, saved, sizeof(saved));
    put64(snapshot + 48 + 248, 144 | 1); assert(!obor_heap_resources_validate(snapshot, sizeof(snapshot), used, plan));
    memcpy(snapshot, saved, sizeof(saved));
    put64(snapshot + 48 + 248, 160 | 3); assert(!obor_heap_resources_validate(snapshot, sizeof(snapshot), used, plan));
    memcpy(snapshot, saved, sizeof(saved));
    put64(snapshot + 48 + 392, 64); assert(!obor_heap_resources_validate(snapshot, sizeof(snapshot), used, plan));
    memcpy(snapshot, saved, sizeof(saved));
    snapshot[12] = 1; assert(!obor_heap_resources_validate(snapshot, sizeof(snapshot), used, plan));
    memcpy(snapshot, saved, sizeof(saved));
    for (size_t length = 0; length < sizeof(snapshot); length += 13)
        assert(!obor_heap_resources_validate(snapshot, length, used, plan));
    memset(arena + base, 0x35, 4096);
    assert(obor_heap_resources_restore(snapshot, sizeof(snapshot), used, plan));
    obor_resource_catalog *target = obor_resource_restore_commit(plan); assert(target);
    assert(!memcmp(arena + base, expected, sizeof(expected)));
    obor_resource_restore_destroy(plan); obor_resource_catalog_destroy(target);
    obor_resource_catalog_destroy(c); obor_resource_materializer_destroy(m);
    obor_resource_source_destroy(source); fclose(file); free(arena); assert(!image_test_live());
    puts("real_heap_reader=1 allocation_ownership=1 logical_zero_validation=1 exact_restore=1");
    return 0;
}
