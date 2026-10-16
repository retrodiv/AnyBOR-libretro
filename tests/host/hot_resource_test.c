/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#define _GNU_SOURCE
#include "obor_fault.h"
#include "obor_write_watch.h"
#include "obor_resource_catalog.h"
#include "obor_framebuffer_state.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

static unsigned char *arena;
static size_t page;
static uint64_t proof_epoch;
static unsigned char *input;
static size_t input_length;
static void *allocate(size_t n) { return malloc(n); }
static const obor_resource_image_allocator allocator = {allocate, free};
static int read_input(void *ctx, uint64_t offset, void *out, size_t length)
{
    (void)ctx; assert(offset <= input_length && length <= input_length - offset);
    memcpy(out, input + offset, length); return 1;
}
static int unchanged(void *ctx, uint32_t offset, uint32_t length)
{ (void)ctx; return obor_write_watch_range_unchanged((uintptr_t)arena + offset, length, proof_epoch); }
static void write_hot(void *unused)
{
    (void)unused;
    for (size_t p = 1; p <= 3; ++p) ((volatile unsigned char *)arena)[p * page + 13] ^= 1;
}
int main(int argc, char **argv)
{
    assert(argc == 2 && !setenv("OBOR_STATE_HOT_PAGES", "1", 1));
    FILE *f = fopen(argv[1], "rb"); assert(f);
    assert(!fseek(f, 0, SEEK_END)); long length = ftell(f); assert(length > 0 && length < (1 << 20));
    rewind(f); input_length = (size_t)length; input = malloc(input_length); assert(input);
    assert(fread(input, 1, input_length, f) == input_length); fclose(f);
    page = (size_t)sysconf(_SC_PAGESIZE);
    arena = mmap(NULL, 4 * page, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(arena != MAP_FAILED); memset(arena, 0, 4 * page);
    static const unsigned char body[] = {1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16};
    const uint32_t source_pixels[] = {0xff112233, 0x80445566, 0x01778899, 0xffabcdef};
    uint32_t body_at = (uint32_t)page + 80, source_at = (uint32_t)page * 2 + 80;
    uint32_t frame_at = (uint32_t)page * 3 + 80;
    memcpy(arena + body_at, body, sizeof(body));
    memcpy(arena + source_at, source_pixels, sizeof(source_pixels));
    obor_framebuffer_reconstruct(arena + source_at, arena + frame_at, sizeof(source_pixels));
    const obor_resource_reader reader = {NULL, input_length, read_input};
    obor_resource_source *source = obor_resource_source_create(&reader, &allocator); assert(source);
    obor_resource_materializer *m = obor_resource_materializer_create(source, &allocator, 2048); assert(m);
    obor_resource_recipe bytes, frame;
    assert(obor_resource_recipe_prove_bytes(m, &bytes, "data/body.bin", 13, 0, body, sizeof(body)));
    obor_framebuffer_source origin = {(uint32_t)page * 2 + 64, 128, source_at, 8};
    assert(obor_resource_recipe_framebuffer(&frame, &origin, 2, 2));
    obor_resource_catalog *c = obor_resource_catalog_create(m, &allocator, arena, (uint32_t)page * 4); assert(c);
    assert(obor_resource_catalog_add(c, (uint32_t)page + 64, 128, body_at, &bytes));
    assert(obor_resource_catalog_framebuffer(c, (uint32_t)page * 3 + 64, 128, frame_at, &frame));
    assert(obor_resource_catalog_prepare(c, (uint32_t)page * 4, NULL, NULL));
    assert(obor_resource_catalog_mask_count(c) == 2);
    assert(obor_write_watch_start(arena, page * 4, page * 4));
    assert(obor_write_watch_arm(page * 4) == 1);
    for (unsigned i = 0; i < 16; ++i) {
        obor_fault fault; assert(obor_fault_run(write_hot, NULL, &fault) == 1);
        assert(obor_write_watch_arm(page * 4) == 1);
        assert(obor_write_watch_arm(page * 4) == 1); /* empty PREPARE/serialize epoch */
    }
    for (unsigned p = 1; p <= 3; ++p) assert(obor_write_watch_page_epoch(p) == UINT64_MAX);
    unsigned char *logical = malloc(page * 4); assert(logical);
    for (unsigned cycle = 0; cycle < 3; ++cycle) {
        proof_epoch = obor_write_watch_epoch();
        assert(obor_write_watch_arm(page * 4) == 1);
        assert(obor_resource_catalog_prepare(c, (uint32_t)page * 4, unchanged, NULL));
        assert(obor_resource_catalog_mask_count(c) == 2);
        /* Mutate the proven body while RW, without a new epoch or CPU fault. */
        arena[body_at + 5] ^= 0x40;
        assert(obor_resource_catalog_prepare(c, (uint32_t)page * 4, unchanged, NULL));
        assert(obor_resource_catalog_mask_count(c) == 1);
        assert(obor_resource_catalog_read(c, 0, logical, (uint32_t)page * 4));
        assert(!memcmp(logical + body_at, arena + body_at, sizeof(body)));
        arena[body_at + 5] ^= 0x40;
        assert(obor_resource_catalog_prepare(c, (uint32_t)page * 4, unchanged, NULL));
        assert(obor_resource_catalog_mask_count(c) == 2);
        /* Changing ONLY the framebuffer source must invalidate its marker. */
        arena[source_at] ^= 0x20;
        assert(obor_resource_catalog_prepare(c, (uint32_t)page * 4, unchanged, NULL));
        assert(obor_resource_catalog_mask_count(c) == 1);
        assert(obor_resource_catalog_read(c, 0, logical, (uint32_t)page * 4));
        assert(!memcmp(logical + frame_at, arena + frame_at, sizeof(source_pixels)));
        arena[source_at] ^= 0x20;
        assert(obor_resource_catalog_prepare(c, (uint32_t)page * 4, unchanged, NULL));
        assert(obor_resource_catalog_mask_count(c) == 2);
        arena[frame_at] ^= 0x10;
        assert(obor_resource_catalog_prepare(c, (uint32_t)page * 4, unchanged, NULL));
        assert(obor_resource_catalog_mask_count(c) == 1);
        arena[frame_at] ^= 0x10;
        assert(obor_resource_catalog_prepare(c, (uint32_t)page * 4, unchanged, NULL));
        assert(obor_resource_catalog_mask_count(c) == 2);
    }
    assert(obor_write_watch_stop());
    obor_resource_catalog_destroy(c); obor_resource_materializer_destroy(m);
    obor_resource_source_destroy(source); free(input); free(logical); assert(!munmap(arena, page * 4));
    puts("hot_resource_mutation_raw=1 hot_frame_source_and_copy_raw=1 same_epoch_catalog_exact=1");
    return 0;
}
