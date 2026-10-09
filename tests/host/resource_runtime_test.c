/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#define _POSIX_C_SOURCE 200809L
#include "obor_resources.h"
#include "obor_state_config.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
void image_test_reset(size_t);
void *image_test_allocate(size_t);
void image_test_release(void *);
size_t image_test_live(void);
size_t image_test_attempts(void);
void *__real_malloc(size_t size) { return image_test_allocate(size); }
void __real_free(void *p) { image_test_release(p); }
FILE *__real_fopen(const char *p, const char *mode) { return fopen(p, mode); }
int __real_fclose(FILE *file) { return fclose(file); }
size_t __real_fread(void *p, size_t n, size_t size, FILE *file) { return fread(p, n, size, file); }
static unsigned char arena[32768];
char *obor_arena_base(void) { return (char *)arena; }
size_t obor_allocation_size(const void *owner)
{
    uintptr_t p = (uintptr_t)owner, start = (uintptr_t)arena + 256;
    return p >= start && p + 128 <= (uintptr_t)arena + sizeof(arena) && !((p - start) % 128) ? 128 : 0;
}
static const unsigned char body[] = {
    12,0,0,0,16,0,0,0,20,0,0,0,
    1,2,5,6,1,1,7,255,1,2,5,6,1,1,7,255,1,2,5,6,1,1,7,255
};
static uint32_t u32(const unsigned char *p)
{ return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24; }
static void expect_catalog(unsigned active, unsigned omitted)
{
    obor_resource_catalog *c = obor_resources_catalog(); assert(c);
    assert(obor_resource_catalog_prepare(c, sizeof(arena), NULL, NULL));
    uint32_t length; const unsigned char *m = obor_resource_catalog_manifest(c, &length);
    assert(m && length >= OBOR_RESOURCE_MANIFEST_HEADER);
    assert(u32(m + 24) == active && u32(m + 20) == omitted);
}
static void bind_bitmap(void)
{
    obor_resources_image_begin(); obor_resources_image_opened("data/image.png");
    obor_resources_bitmap_loaded(arena + 32, 5, 3);
}
static void encode(void)
{
    obor_resources_sprite_encoded(arena + 32, arena + 256, arena + 280, sizeof(body), 0,0,5,3);
}
static void *unrelated_worker_frees(void *unused)
{
    (void)unused;
    for (unsigned i = 0; i < 50000; ++i)
        obor_resources_forget_owner(arena + 257 + (i % 128) * 128);
    return NULL;
}
static void concurrent_registry_growth(void)
{
    pthread_t worker; assert(!pthread_create(&worker, NULL, unrelated_worker_frees, NULL));
    for (unsigned i = 1; i < 128; ++i) {
        unsigned char *owner = arena + 256 + i * 128;
        memcpy(owner + 24, body, sizeof(body));
        obor_resources_sprite_encoded(arena + 32, owner, owner + 24, sizeof(body), 0,0,5,3);
    }
    assert(!pthread_join(worker, NULL)); expect_catalog(128, 128 * sizeof(body));
    for (unsigned i = 1; i < 128; ++i) obor_resources_forget_owner(arena + 256 + i * 128);
    expect_catalog(1, sizeof(body));
}
static void cropped_bitmap_provenance(void)
{
    const unsigned char cropped[] = {8,0,0,0,9,0,0,0,0,2,5,6,255,0,2,5,6,255};
    /* Two physical compactions must compose without changing source geometry. */
    bind_bitmap();
    obor_resources_bitmap_cropped(arena+32,1,1,4,2);
    obor_resources_bitmap_cropped(arena+32,0,0,2,2);
    memcpy(arena+280,cropped,sizeof(cropped));
    obor_resources_sprite_encoded(arena+32,arena+256,arena+280,sizeof(cropped),0,0,2,2);
    expect_catalog(1,sizeof(cropped));
    obor_resources_clear_cache(); expect_catalog(1,sizeof(cropped));
    /* A crop outside the current rectangle cannot retain a stale binding. */
    obor_resources_bitmap_cropped(arena+32,UINT32_MAX,0,2,2);
    obor_resources_sprite_encoded(arena+32,arena+256,arena+280,sizeof(cropped),0,0,2,2);
    expect_catalog(0,0);
    bind_bitmap(); memcpy(arena+280,body,sizeof(body)); encode(); expect_catalog(1,sizeof(body));
}
static void member_byte_provenance(void)
{
    for (unsigned i=0;i<64;++i) arena[512+i]=arena[640+i]=(unsigned char)(44+i);
    arena[576]=0x80; arena[704]=0x80; /* Mutable allocation tails. */
    obor_resources_member_bytes_loaded("data/sample.bin",44,arena+512,arena+512,64);
    obor_resources_member_bytes_loaded("data/sample.bin",44,arena+640,arena+640,64);
    expect_catalog(3,sizeof(body)+128);
    arena[527]^=1; expect_catalog(3,sizeof(body)+64);
    arena[527]^=1; expect_catalog(3,sizeof(body)+128);
    /* Tail writes do not alter the body or become reconstructed data. */
    arena[576]=0xe3; expect_catalog(3,sizeof(body)+128);
    obor_resources_forget_owner(arena+512); expect_catalog(2,sizeof(body)+64);
    obor_resources_member_bytes_loaded("data/sample.bin",UINT32_MAX,arena+512,arena+512,64);
    expect_catalog(2,sizeof(body)+64);
    obor_resources_member_bytes_loaded("data/sample.bin",44,arena+512,arena+512,64);
    expect_catalog(3,sizeof(body)+128);
    /* Reuse at the same address with a different member slice. */
    for (unsigned i=0;i<32;++i) arena[512+i]=(unsigned char)(144+i);
    obor_resources_member_bytes_loaded("data/sample.bin",144,arena+512,arena+512,32);
    expect_catalog(3,sizeof(body)+96);
    for (unsigned i=0;i<64;++i) arena[512+i]=(unsigned char)(44+i);
    obor_resources_member_bytes_loaded("data/sample.bin",44,arena+512,arena+512,64);
    obor_resources_clear_cache(); expect_catalog(3,sizeof(body)+128);
}
static void exercise(const char *path)
{
    obor_resources_open(path, 0); assert(obor_resources_catalog());
    memset(arena, 0x92, sizeof(arena)); memcpy(arena + 280, body, sizeof(body));
    bind_bitmap(); encode(); expect_catalog(1, sizeof(body));
    obor_resources_clear_cache(); expect_catalog(1, sizeof(body));
    concurrent_registry_growth();
    cropped_bitmap_provenance();
    /* A script's changed body must be stored raw despite its source binding. */
    arena[291] ^= 1; expect_catalog(1, 0);
    memcpy(arena + 280, body, sizeof(body)); expect_catalog(1, sizeof(body));
    obor_resources_forget_owner(arena + 256); expect_catalog(0, 0);
    encode(); expect_catalog(1, sizeof(body));
    /* Free/realloc of a bitmap prevents stale provenance at its reused address. */
    obor_resources_forget_owner(arena + 32); encode(); expect_catalog(0, 0);
    bind_bitmap(); encode(); expect_catalog(1, sizeof(body));
    obor_resources_image_begin(); obor_resources_bitmap_loaded(arena + 32, 5,3);
    encode(); expect_catalog(0, 0);
    bind_bitmap(); encode(); expect_catalog(1, sizeof(body));
    uint32_t length; const void *manifest = obor_resource_catalog_manifest(obor_resources_catalog(), &length);
    member_byte_provenance();
    manifest = obor_resource_catalog_manifest(obor_resources_catalog(), &length);
    unsigned char *copy = malloc(length); assert(copy); memcpy(copy, manifest, length);
    /* Native preflight can run while current workers free unrelated owners.
     * It holds no engine lock and neither a bad target nor a successful staged
     * target may alter the current arena before those workers are joined. */
    unsigned char before[sizeof(arena)]; memcpy(before,arena,sizeof(arena));
    pthread_t worker; assert(!pthread_create(&worker,NULL,unrelated_worker_frees,NULL));
    copy[0]^=1;
    assert(!obor_resources_prepare_restore(copy,length,sizeof(arena),NULL,NULL,1));
    copy[0]^=1;
    obor_resource_restore *staged=obor_resources_prepare_restore(copy,length,sizeof(arena),NULL,NULL,1);
    assert(staged && obor_resource_restore_staged(staged)==sizeof(body)+128);
    assert(!memcmp(before,arena,sizeof(arena)));
    assert(!pthread_join(worker,NULL));
    obor_resource_restore_destroy(staged);
    /* Process teardown loses every catalog, origin and source-derived cache. */
    obor_resources_close(); assert(!image_test_live());
    memset(arena, 0x35, sizeof(arena));
    obor_resources_open(path, 0); assert(obor_resources_catalog());
    obor_resource_restore *plan = obor_resources_prepare_restore(copy,
        length, sizeof(arena), NULL, NULL, 1); assert(plan);
    obor_resources_adopt(obor_resource_restore_commit(plan));
    obor_resource_restore_destroy(plan); free(copy);
    assert(!memcmp(arena + 280, body, sizeof(body))); expect_catalog(3, sizeof(body)+128);
    for (unsigned i=0;i<64;++i) assert(arena[512+i]==44+i && arena[640+i]==44+i);
    assert(arena[576]==0x35 && arena[704]==0x35); /* Outside the resource body. */
    obor_resources_forget_owner(arena+512); obor_resources_forget_owner(arena+640);
    expect_catalog(1,sizeof(body));
    /* Origins from a later session must not survive a restore or reset. */
    encode(); expect_catalog(0, 0);
    bind_bitmap(); encode(); expect_catalog(1, sizeof(body));
    obor_resources_adopt(NULL); expect_catalog(0, 0);
    encode(); expect_catalog(0, 0);
    obor_resources_close(); assert(!image_test_live());
}
int main(int argc, char **argv)
{
    assert(argc == 2); image_test_reset(0);
    unsetenv("OBOR_RESOURCE_STATES"); unsetenv("OBOR_COMPRESSED_STATES");
    obor_resources_open(argv[1], 0);
    assert(!!obor_resources_catalog() == OBOR_STATE_DEFAULT_ENABLED);
    obor_resources_close(); assert(!image_test_live());
    assert(!setenv("OBOR_RESOURCE_STATES", "0", 1));
    obor_resources_open(argv[1], 0); assert(!obor_resources_catalog());
    assert(!setenv("OBOR_RESOURCE_STATES", "1", 1));
    assert(!setenv("OBOR_COMPRESSED_STATES", "0", 1));
    obor_resources_open(argv[1], 0); assert(!obor_resources_catalog());
    assert(!setenv("OBOR_COMPRESSED_STATES", "1", 1));
    obor_resources_open(argv[1], 1); assert(!obor_resources_catalog());
    obor_resources_open("/nonexistent/anybor-resource-test", 0);
    assert(!obor_resources_catalog() && !image_test_live());
    exercise(argv[1]); exercise(argv[1]);
    image_test_reset(0); obor_resources_open(argv[1], 0);
    size_t attempts = image_test_attempts(); obor_resources_close(); assert(!image_test_live());
    for (size_t failure = 1; failure <= attempts; ++failure) {
        image_test_reset(failure); obor_resources_open(argv[1], 0);
        obor_resources_close(); assert(!image_test_live());
    }
    puts("engine_provenance=1 free_realloc_reuse=1 cold_source_restore=1 reset=1 allocation_failures=1");
    return 0;
}
