/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#define _GNU_SOURCE
#include "obor_block_state.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if defined(_WIN32)
#include "obor_state_cache_win.h"
#else
#include <sys/mman.h>
#include <unistd.h>
#endif

static size_t calls, fail_at;
static uint64_t clock_calls;
static uint64_t test_clock(void) { return ++clock_calls * 100; }
static void *test_calloc(size_t n, size_t s)
{ return ++calls == fail_at ? NULL : calloc(n, s); }
static void *test_realloc(void *p, size_t s)
{ return ++calls == fail_at ? NULL : realloc(p, s); }
static obor_block_allocator allocator = {
    .calloc = test_calloc, .realloc = test_realloc, .free = free
};
static size_t reservations, releases, grows;
static void *test_reserve(size_t maximum)
{
    if (++calls == fail_at) return NULL;
#if defined(_WIN32)
    void *p = coded_raw_reserve(maximum);
#else
    void *p = mmap(NULL, maximum, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED) p = NULL;
#endif
    if (p) ++reservations;
    return p;
}
static int test_grow(void *p, size_t before, size_t after)
{
    if (++calls == fail_at) return 0;
    assert(after > before && after <= OBOR_BLOCK_STATE_MAX_RAW);
    ++grows;
#if defined(_WIN32)
    return coded_raw_grow(p, before, after);
#else
    size_t page = (size_t)sysconf(_SC_PAGESIZE);
    size_t first = (before + page - 1) / page * page;
    size_t last = (after + page - 1) / page * page;
    return first == last || !mprotect((unsigned char *)p + first, last-first, PROT_READ | PROT_WRITE);
#endif
}
static void test_release(void *p, size_t maximum)
{
    ++releases;
#if defined(_WIN32)
    coded_raw_release(p, maximum);
#else
    assert(!munmap(p, maximum));
#endif
}
typedef struct { unsigned char *bytes; uint32_t length; int fail; size_t reads; } source_data;
static const void *read_source(void *opaque, uint32_t offset, uint32_t size, void *scratch)
{
    source_data *source = opaque;
    (void)scratch;
    ++source->reads;
    if (source->fail == 1 || (source->fail == 2 && offset >= OBOR_BLOCK_STATE_BLOCK) ||
        offset > source->length || size > source->length - offset) return NULL;
    return source->bytes + offset;
}
static int unchanged_source(void *opaque, uint32_t offset, uint32_t size)
{ (void)opaque; (void)size; return offset != 3 * OBOR_BLOCK_STATE_BLOCK; }
static uint32_t random_word(uint32_t *state)
{ uint32_t v=*state;v^=v<<13;v^=v>>17;v^=v<<5;return *state=v; }
static unsigned char *copy_image(obor_block_state *cache, uint32_t *size)
{
    const void *image = obor_block_state_image(cache, size);
    assert(image && *size <= OBOR_BLOCK_STATE_CAPACITY);
    unsigned char *copy = malloc(*size);assert(copy);memcpy(copy,image,*size);return copy;
}
static void equal_raw(obor_block_state *cache, const void *expected, uint32_t expected_size)
{
    uint32_t size;const void *raw=obor_block_state_raw(cache,&size);
    assert(raw && size==expected_size && !memcmp(raw,expected,size));
}
static void put32(void *p,uint32_t value) { memcpy(p,&value,sizeof(value)); }
static uint32_t get32(const void *p) {uint32_t value;memcpy(&value,p,sizeof(value));return value;}

static void exercise_compaction(void)
{
    const uint32_t length = 1U << 20;
    unsigned char *bytes = malloc(length), *original = malloc(length);
    assert(bytes && original);
    uint32_t seed = 0x315991;
    for (uint32_t i = 0; i < length; ++i) bytes[i] = (unsigned char)random_word(&seed);
    memcpy(original, bytes, length);
    source_data data = {bytes, length, 0, 0};
    obor_block_source source = {&data, read_source, NULL};
    obor_block_state *cache = obor_block_state_create(&allocator);
    obor_block_state *cold = obor_block_state_create(&allocator);
    assert(cache && cold && obor_block_state_encode_fast(cache, &source, length));
    uint32_t old_size, large_size;
    unsigned char *old = copy_image(cache, &old_size);
    memset(bytes, 0, length);
    assert(obor_block_state_encode_fast(cache, &source, length));
    unsigned char *large = copy_image(cache, &large_size);
    assert(large_size == old_size); /* Slot capacity retained without maintenance. */
    obor_block_state_set_compaction(cache, 1);
    uint32_t previous_size = large_size;
    uint64_t reclaimed = 0, moved = 0;
    for (unsigned i = 0; i < 16; ++i) {
        assert(obor_block_state_encode_fast(cache, &source, length));
        obor_block_changes changes;
        obor_block_state_changes(cache, &changes);
        assert(changes.compact_written <= 512U << 10 && changes.compact_examined <= 512 &&
            changes.compact_holes <= 4096 && changes.blocks == 0);
        reclaimed += changes.compact_reclaimed; moved += changes.compact_moved;
        uint32_t size; const void *image = obor_block_state_image(cache, &size);
        assert(image && size <= previous_size);
        previous_size = size;
        obor_block_state_forget(cold);
        assert(obor_block_state_decode(cold, image, size)); equal_raw(cold, bytes, length);
    }
    assert(reclaimed >= length * 3 / 4 && moved && large_size - previous_size >= length * 3 / 4);
    /* Old images remain complete after later pool contents have moved/reused. */
    assert(obor_block_state_decode(cache, old, old_size)); equal_raw(cache, original, length);
    assert(obor_block_state_decode(cache, large, large_size)); equal_raw(cache, bytes, length);
    assert(obor_block_state_encode_fast(cache, &source, length)); equal_raw(cache, bytes, length);
    obor_block_state_destroy(cache); obor_block_state_destroy(cold);
    free(old); free(large); free(bytes); free(original);
    puts("bounded_compaction=1 old_images_independent=1 cold_compact_decode=16");
}

int main(int argc, char **argv)
{
    int virtual_cache = argc == 2 && !strcmp(argv[1], "--virtual");
    if (virtual_cache) {
        allocator.raw_reserve = test_reserve;
        assert(!obor_block_state_create(&allocator));
        allocator.raw_grow = test_grow;
        assert(!obor_block_state_create(&allocator));
        allocator.raw_release = test_release;
    }
    assert(obor_block_state_requested_capacity(NULL)==OBOR_BLOCK_STATE_CAPACITY);
    assert(obor_block_state_requested_capacity("256")==OBOR_BLOCK_STATE_CAPACITY);
    assert(obor_block_state_requested_capacity("80junk")==OBOR_BLOCK_STATE_CAPACITY);
    assert(obor_block_state_requested_capacity("80")<=OBOR_BLOCK_STATE_CAPACITY);
    /* Allocation failures during construction must be handled by the supplied
     * allocator; zlib allocations must not escape into an engine arena. */
    calls=0;fail_at=0;
    obor_block_state *probe=obor_block_state_create(&allocator);assert(probe);
    size_t construction_calls=calls;obor_block_state_destroy(probe);
    for(size_t i=1;i<=construction_calls;++i){
        calls=0;fail_at=i;probe=obor_block_state_create(&allocator);
        if(probe)obor_block_state_destroy(probe);
    }
    fail_at=0;calls=0;
    exercise_compaction();
    assert(!obor_block_state_create_sized(&allocator, 1U<<20));
    assert(!obor_block_state_create_sized(&allocator, (4U<<20)+1));
    assert(!obor_block_state_create_sized(&allocator, OBOR_BLOCK_STATE_CAPACITY+256));
    obor_block_state *small=obor_block_state_create_sized(&allocator, 4U<<20);assert(small);
    obor_block_state *cache=obor_block_state_create(&allocator);
    obor_block_state *cold=obor_block_state_create(&allocator);assert(cache && cold);
    uint32_t maximum=8U<<20, initial=1U<<20;
    unsigned char *bytes=malloc(maximum),*prior=malloc(maximum);assert(bytes && prior);
    for(uint32_t i=0;i<maximum;++i)bytes[i]=(unsigned char)((i/71+i/4096)%13);
    source_data data={bytes,initial,0,0};
    obor_block_source source={&data,read_source,NULL};
    if (virtual_cache) {
        /* Reserve failure, then commitment failure, then recovery. Failed
         * commitment must keep the same releasable reservation for retry. */
        fail_at=calls+1;
        assert(!obor_block_state_encode_fast(cache,&source,data.length));
        size_t before=reservations;
        fail_at=calls+2;
        assert(!obor_block_state_encode_fast(cache,&source,data.length));
        assert(reservations==before+1);
        fail_at=0;
    }
    assert(obor_block_state_encode_fast(cache,&source,data.length));
    uint32_t fast_size; unsigned char *fast=copy_image(cache,&fast_size);
    for (uint32_t i=0;i<data.length/OBOR_BLOCK_STATE_BLOCK;++i)
        assert(get32(fast+32+i*24+16)==1);
    obor_block_changes changes;
    obor_block_state_changes(cache,&changes);
    assert(changes.blocks==data.length/OBOR_BLOCK_STATE_BLOCK && changes.raw_bytes==data.length && changes.slot_bytes>0);
    assert(changes.total_stored_bytes>0 && changes.total_stored_bytes<=changes.total_slot_bytes &&
        changes.total_slot_bytes==changes.slot_bytes && changes.pool_hole_bytes==0);
    assert(changes.read_bytes==data.length && changes.read_blocks==changes.blocks &&
        !changes.proven_blocks && !changes.equal_blocks && !changes.repacks);
    /* Instrumentation cannot change the complete image or retain costs when
     * disabled. Exercise changed, equal and proven branches independently. */
    obor_block_state_set_clock(cold, test_clock);
    assert(obor_block_state_encode_fast(cold,&source,data.length));
    uint32_t timed_size; const void *timed=obor_block_state_image(cold,&timed_size);
    assert(timed_size==fast_size && !memcmp(timed,fast,fast_size));
    obor_block_timing timing;
    obor_block_state_timing(cold,&timing);
    assert(clock_calls && timing.proof_ns && timing.read_ns && timing.compare_ns &&
        timing.compress_ns && timing.slot_ns && timing.crc_ns && timing.cache_ns);
    assert(obor_block_state_encode_fast(cold,&source,data.length));
    obor_block_state_timing(cold,&timing);
    assert(timing.proof_ns && timing.read_ns && timing.compare_ns && !timing.compress_ns &&
        !timing.slot_ns && !timing.crc_ns && !timing.cache_ns);
    source.unchanged=unchanged_source;
    assert(obor_block_state_encode_fast(cold,&source,data.length));
    obor_block_state_changes(cold,&changes);
    assert(changes.proven_blocks+1==data.length/OBOR_BLOCK_STATE_BLOCK && changes.read_blocks==1);
    source.unchanged=NULL;
    uint64_t previous_clock_calls=clock_calls;
    obor_block_state_set_clock(cold,NULL);
    assert(obor_block_state_encode_fast(cold,&source,data.length));
    obor_block_state_timing(cold,&timing);
    assert(clock_calls==previous_clock_calls && !timing.proof_ns && !timing.read_ns &&
        !timing.compare_ns && !timing.compress_ns && !timing.slot_ns && !timing.crc_ns && !timing.cache_ns);
    assert(obor_block_state_decode(cold,fast,fast_size));equal_raw(cold,bytes,data.length);
    assert(obor_block_state_decode(small,fast,fast_size));equal_raw(small,bytes,data.length);
    assert(obor_block_state_encode_fast(small,&source,data.length));equal_raw(small,bytes,data.length);
    uint32_t small_size; assert(obor_block_state_image(small,&small_size) && small_size<=4U<<20);
    assert(obor_block_state_encode_fast(cache,&source,data.length));
    obor_block_state_changes(cache,&changes); assert(!changes.blocks && !changes.raw_bytes && !changes.slot_bytes);
    assert(changes.equal_blocks==changes.read_blocks && changes.read_bytes==data.length);
    bytes[17]^=1;
    assert(obor_block_state_encode_mutable(cache,&source,data.length));
    uint32_t direct_size; unsigned char *direct=copy_image(cache,&direct_size);
    assert(get32(direct+32+16)==0); /* Only changed block promoted to raw. */
    bytes[31]^=1;
    assert(obor_block_state_encode_mutable(cache,&source,data.length));
    uint32_t next_size; const unsigned char *next=obor_block_state_image(cache,&next_size);
    assert(next_size==direct_size);
    unsigned differences=0;
    for(uint32_t i=0;i<next_size;++i) differences+=next[i]!=direct[i];
    /* One byte plus its four-byte checksum, without compressed-stream shifts. */
    assert(differences>0 && differences<=5);
    assert(obor_block_state_decode(cold,next,next_size));equal_raw(cold,bytes,data.length);
    free(direct); bytes[17]^=1; bytes[31]^=1;
    free(fast); obor_block_state_forget(cache); obor_block_state_forget(cold);
    assert(obor_block_state_encode(cache,&source,data.length));equal_raw(cache,bytes,data.length);
    uint32_t old_size;unsigned char *old=copy_image(cache,&old_size);
    memcpy(prior,bytes,data.length);
    obor_block_state_set_compaction(cache, 1);
    for(uint32_t iteration=0;iteration<48;++iteration){
        uint32_t before_length=data.length;
        memcpy(prior,bytes,before_length);
        free(old);old=copy_image(cache,&old_size);
        uint32_t seed=iteration+1;
        for(uint32_t i=0;i<700;++i)bytes[random_word(&seed)%data.length]^=(unsigned char)random_word(&seed);
        if(iteration==5)data.length=2U<<20;
        if(iteration==19)data.length=700019;
        if(iteration==27)data.length=(3U<<20)+17;
        assert(obor_block_state_encode(cache,&source,data.length));equal_raw(cache,bytes,data.length);
        obor_block_state_changes(cache,&changes);
        assert(changes.compact_written <= 512U << 10 && changes.compact_examined <= 512 &&
            changes.compact_holes <= 4096);
        uint32_t size;unsigned char *image=copy_image(cache,&size);
        obor_block_state_forget(cold);
        assert(obor_block_state_decode(cold,image,size));equal_raw(cold,bytes,data.length);
        /* Reverse from the newer cache into a complete older image. */
        assert(obor_block_state_decode(cache,old,old_size));equal_raw(cache,prior,before_length);
        assert(obor_block_state_decode(cache,image,size));equal_raw(cache,bytes,data.length);
        free(image);
    }
    obor_block_state_set_compaction(cache, 0);
    /* A dirty proof may avoid reading only ranges it actually covers. */
    bytes[3*OBOR_BLOCK_STATE_BLOCK+11]^=0x71;
    source.unchanged=unchanged_source;data.reads=0;
    assert(obor_block_state_encode(cache,&source,data.length));
    assert(data.reads==1);equal_raw(cache,bytes,data.length);source.unchanged=NULL;
    obor_block_state_changes(cache,&changes);
    assert(changes.read_blocks==1 && changes.read_bytes==OBOR_BLOCK_STATE_BLOCK &&
        changes.proven_blocks==(data.length+OBOR_BLOCK_STATE_BLOCK-1)/OBOR_BLOCK_STATE_BLOCK-1);

    uint32_t valid_size;unsigned char *valid=copy_image(cache,&valid_size);
    unsigned char *bad=malloc(valid_size);assert(bad);
    unsigned rejected=0;
    for(unsigned field=0;field<8;++field){
        memcpy(bad,valid,valid_size);put32(bad+4*field,UINT32_MAX);
        assert(!obor_block_state_decode(cold,bad,valid_size));++rejected;
    }
    for(unsigned field=0;field<6;++field){
        memcpy(bad,valid,valid_size);put32(bad+32+4*field,UINT32_MAX);
        assert(!obor_block_state_decode(cold,bad,valid_size));++rejected;
    }
    memcpy(bad,valid,valid_size);put32(bad+32+24,get32(bad+32));
    assert(!obor_block_state_decode(cold,bad,valid_size));++rejected; /* overlapping slots */
    assert(obor_block_state_decode(cold,valid,valid_size));
    memcpy(bad,valid,valid_size);bad[get32(bad+32)]^=0x80;
    assert(!obor_block_state_decode(cold,bad,valid_size));++rejected; /* cached CRC reuse */
    for(uint32_t size=0;size<64;++size){assert(!obor_block_state_decode(cold,valid,size));++rejected;}
    assert(!obor_block_state_decode(cold,valid,valid_size-1));++rejected;
    assert(obor_block_state_decode(cold,valid,valid_size));equal_raw(cold,bytes,data.length);
    /* Invalid unused table entries must never become trusted allocator state
     * when the decoded image subsequently grows. */
    memcpy(bad,valid,valid_size);uint32_t count=get32(bad+12);
    memset(bad+32+count*24,0xff,24);
    assert(obor_block_state_decode(cold,bad,valid_size));
    data.length+=2*OBOR_BLOCK_STATE_BLOCK;
    assert(obor_block_state_encode(cold,&source,data.length));equal_raw(cold,bytes,data.length);

    data.fail=1;assert(!obor_block_state_encode(cache,&source,data.length));
    assert(!obor_block_state_image(cache,NULL));data.fail=0;
    assert(obor_block_state_encode(cache,&source,data.length));
    /* Failure after a changed block must not publish a mixed old/new image.
     * The next complete capture must recover without stale dirty proofs. */
    bytes[0]^=0x80; data.fail=2; data.reads=0;
    assert(!obor_block_state_encode(cache,&source,data.length));
    assert(data.reads==2 && !obor_block_state_image(cache,NULL));
    assert(!obor_block_state_raw(cache,NULL));
    data.fail=0;
    assert(obor_block_state_encode(cache,&source,data.length));equal_raw(cache,bytes,data.length);
    /* Memory failure on decoded-cache growth invalidates only the private cache. */
    data.length=4U<<20;fail_at=calls+1;
    assert(!obor_block_state_encode(cache,&source,data.length));fail_at=0;
    assert(obor_block_state_encode(cache,&source,data.length));equal_raw(cache,bytes,data.length);
    /* Small mutations throughout cold, entropy-coded data can promote every
     * block to a larger fast encoding. The compact retry must remain complete
     * and independently decodable within the SAME eight-MiB budget. */
    uint32_t repack_seed=0x761db3;
    data.length=6U<<20;
    for(uint32_t i=0;i<data.length;++i)bytes[i]=(unsigned char)(random_word(&repack_seed)&15);
    obor_block_state_forget(cache);
    /* LZ4 does not fit this input, but the full DEFLATE retry must. */
    assert(obor_block_state_encode_fast(cache,&source,data.length));
    unsigned char *fast_repacked=copy_image(cache,&fast_size);
    assert(fast_size>4U<<20);
    assert(!obor_block_state_decode(small,fast_repacked,fast_size));
    assert(!obor_block_state_image(small,NULL));
    assert(!obor_block_state_encode_fast(small,&source,data.length));
    assert(!obor_block_state_image(small,NULL));
    for(uint32_t i=0;i<data.length/OBOR_BLOCK_STATE_BLOCK;++i)
        assert(get32(fast_repacked+32+i*24+16)==2);
    obor_block_state_forget(cold);
    assert(obor_block_state_decode(cold,fast_repacked,fast_size));equal_raw(cold,bytes,data.length);
    free(fast_repacked); obor_block_state_forget(cache);
    obor_block_state_destroy(small);
    assert(obor_block_state_encode(cache,&source,data.length));
    for(uint32_t i=0;i<data.length;i+=OBOR_BLOCK_STATE_BLOCK)bytes[i]^=1;
    assert(obor_block_state_encode(cache,&source,data.length));equal_raw(cache,bytes,data.length);
    uint32_t repack_size;unsigned char *repacked=copy_image(cache,&repack_size);
    for(uint32_t i=0;i<data.length/OBOR_BLOCK_STATE_BLOCK;++i)
        assert(get32(repacked+32+i*24+16)==2); /* all blocks recompressed */
    obor_block_state_forget(cold);
    assert(obor_block_state_decode(cold,repacked,repack_size));equal_raw(cold,bytes,data.length);
    free(repacked);
    /* This test is compiled with an 8MiB encoded-image budget. Incompressible
     * input must fail, never truncate or return a history-dependent image. */
    uint32_t seed=0xa7c19;
    for(uint32_t i=0;i<maximum;++i)bytes[i]=(unsigned char)random_word(&seed);
    data.length=maximum;obor_block_state_forget(cache);
    assert(!obor_block_state_encode(cache,&source,data.length));
    assert(!obor_block_state_image(cache,NULL));
    assert(!obor_block_state_encode_fast(cache,&source,data.length));
    assert(!obor_block_state_image(cache,NULL));
    assert(obor_block_state_decode(cache,valid,valid_size));
    printf("independent_images=48 reverse_restores=48 malformed_rejected=%u allocator_cases=%lu overflow_rejected=1 complete_repack=1\n",rejected,(unsigned long)construction_calls);
    free(bad);free(valid);free(old);free(prior);free(bytes);
    obor_block_state_destroy(cache);obor_block_state_destroy(cold);
    assert(reservations==releases);
    printf("virtual_cache=%d reservations=%lu releases=%lu growths=%lu\n",
        virtual_cache,(unsigned long)reservations,(unsigned long)releases,(unsigned long)grows);
    return 0;
}
