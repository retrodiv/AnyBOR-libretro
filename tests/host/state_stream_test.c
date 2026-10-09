/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#include "obor_state_stream.h"
#include "obor_state_layout.h"
#include <assert.h>
#include <stdio.h>
#if defined(__linux__)
#include <sys/mman.h>
#endif

static int overlay(void *context, const unsigned char *address, void *out, uint32_t length)
{
    const unsigned char *base = context;
    for (uint32_t i = 0; i < length; ++i)
        ((unsigned char *)out)[i] = address + i == base + 2 ? 0 : address[i];
    return 1;
}

#if defined(__linux__)
static int opaque_heap(void *context, const unsigned char *address, void *out, uint32_t length)
{
    (void)address;
    if (!context) return 0;
    memset(out, 0x63, length);
    return 1;
}
#endif

static void heap_reader_contract(void)
{
#if defined(__linux__)
    /* No raw pre-copy may touch a heap span supplied by the reader. */
    void *inaccessible = mmap(NULL, 4096, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(inaccessible != MAP_FAILED);
    obor_state_part part;
    uint32_t count = 0, size = 0;
    assert(obor_state_part_add(&part, 1, &count, &size, inaccessible, 4096, OBOR_STATE_HEAP));
    unsigned char output[32]; memset(output, 0xa5, sizeof(output));
    assert(obor_state_part_read(&part, count, size, 13, 20, output+4, opaque_heap, &part) == output+4);
    for (unsigned i=0; i<sizeof(output); ++i)
        assert(output[i] == (i>=4 && i<24 ? 0x63 : 0xa5));
    assert(!obor_state_part_read(&part, count, size, 13, 20, output+4, opaque_heap, NULL));
    /* A reader failure after a preceding ordinary span must propagate to the
     * encoder; the partly filled scratch buffer is not a valid source view. */
    const unsigned char prefix[4] = {1,2,3,4};
    obor_state_part mixed[2]; count = size = 0;
    assert(obor_state_part_add(mixed, 2, &count, &size, prefix, sizeof(prefix), OBOR_STATE_BYTES));
    assert(obor_state_part_add(mixed, 2, &count, &size, inaccessible, 4096, OBOR_STATE_HEAP));
    memset(output, 0xa5, sizeof(output));
    assert(!obor_state_part_read(mixed, count, size, 0, 20, output+4, opaque_heap, NULL));
    assert(!memcmp(output+4, prefix, sizeof(prefix)));
    for (unsigned i=0; i<sizeof(output); ++i)
        if (i<4 || i>=8) assert(output[i]==0xa5);
    assert(obor_state_part_read(mixed, count, size, 0, 20, output+4, opaque_heap, mixed) == output+4);
    assert(!memcmp(output+4, prefix, sizeof(prefix)));
    for (unsigned i=8; i<24; ++i) assert(output[i]==0x63);
    assert(!munmap(inaccessible, 4096));
#endif
}

static void stream_boundaries(void)
{
    unsigned char input[8] = {1,2,3,4,5,6,7,8}, scratch[64];
    unsigned char expected[19] = {1,2,3,4,0,0,0,1,2,0,4,5,6,7,8,5,6,7,8};
    obor_state_part parts[4];
    uint32_t count = 0, size = 0;
    assert(obor_state_part_add(parts,4,&count,&size,input,4,OBOR_STATE_BYTES));
    assert(obor_state_part_add(parts,4,&count,&size,NULL,3,OBOR_STATE_ZERO));
    assert(obor_state_part_add(parts,4,&count,&size,input,8,OBOR_STATE_HEAP));
    assert(obor_state_part_add(parts,4,&count,&size,input+4,4,OBOR_STATE_MANIFEST));
    assert(size == sizeof(expected));
    for (uint32_t offset = 0; offset <= size; ++offset)
        for (uint32_t length = 0; length <= size-offset; ++length) {
            memset(scratch,0xff,sizeof(scratch));
            const void *p = obor_state_part_read(parts,count,size,offset,length,scratch,overlay,input);
            assert(p && !memcmp(p,expected+offset,length));
        }
    assert(!obor_state_part_read(parts,count,size,size,1,scratch,overlay,input));
    assert(!obor_state_part_read(parts,count,size,UINT32_MAX,2,scratch,overlay,input));
    assert(!obor_state_part_read(parts,count,size,0,UINT32_MAX,scratch,overlay,input));
    assert(!obor_state_part_add(parts,4,&count,&size,input,1,OBOR_STATE_BYTES));
    assert(count == 4 && size == sizeof(expected));
    count=0; size=UINT32_MAX-3;
    assert(!obor_state_part_add(parts,4,&count,&size,input,4,OBOR_STATE_BYTES));
    assert(!obor_state_part_add(parts,4,&count,&size,NULL,1,OBOR_STATE_BYTES));
    assert(!obor_state_part_add(parts,4,&count,&size,input,1,7));
    assert(!count && size == UINT32_MAX-3);
}

static void stable_windows(void)
{
    unsigned char head[32] = {0}, stack[64], manifest[OBOR_RESOURCE_MANIFEST_HEADER] = {0}, heap[128];
    memset(stack,0xa7,sizeof(stack)); memset(heap,0x46,sizeof(heap));
    obor_state_part previous[7] = {{0}}, parts[7];
    uint32_t previous_count=0;
    for (uint32_t depth=16; depth<=64; depth+=16) {
        uint32_t count=0,size=0;
        assert(obor_state_part_add(parts,7,&count,&size,head,sizeof(head),OBOR_STATE_BYTES));
        assert(obor_state_part_add(parts,7,&count,&size,NULL,OBOR_STATE_STACK_WINDOW-depth,OBOR_STATE_ZERO));
        assert(obor_state_part_add(parts,7,&count,&size,stack+64-depth,depth,OBOR_STATE_BYTES));
        assert(obor_state_part_add(parts,7,&count,&size,manifest,sizeof(manifest),OBOR_STATE_MANIFEST));
        assert(obor_state_part_add(parts,7,&count,&size,NULL,OBOR_STATE_MANIFEST_WINDOW-sizeof(manifest),OBOR_STATE_ZERO));
        assert(obor_state_part_add(parts,7,&count,&size,heap,depth*2,OBOR_STATE_HEAP));
        obor_state_resource_offsets layout;
        assert(obor_state_resource_layout(sizeof(head),depth,depth*2,size,&layout));
        assert(layout.stack == sizeof(head)+OBOR_STATE_STACK_WINDOW-depth);
        assert(layout.manifest == sizeof(head)+OBOR_STATE_STACK_WINDOW);
        assert(layout.heap == sizeof(head)+OBOR_STATE_STACK_WINDOW+OBOR_STATE_MANIFEST_WINDOW);
        unsigned char scratch[64];
        const unsigned char *bytes=obor_state_part_read(parts,count,size,layout.stack-1,2,scratch,NULL,NULL);
        assert(bytes && !bytes[0] && bytes[1]==0xa7);
        bytes=obor_state_part_read(parts,count,size,layout.heap-1,2,scratch,NULL,NULL);
        assert(bytes && !bytes[0] && bytes[1]==0x46);
        if (previous_count) {
            assert(obor_state_part_mapped(parts+1,previous,previous_count,64,64));
            assert(obor_state_part_mapped(parts+2,previous,previous_count,layout.manifest-16,16));
            assert(obor_state_part_mapped(parts+5,previous,previous_count,layout.heap,32));
            assert(obor_state_part_mapped(parts+3,previous,previous_count,layout.manifest,32));
            /* Newly active stack bytes used to be zero. No proof may skip them. */
            assert(!obor_state_part_mapped(parts+2,previous,previous_count,layout.stack,16));
            assert(!obor_state_part_mapped(parts+5,previous,previous_count,layout.heap+depth*2-1,1));
        }
        memcpy(previous,parts,count*sizeof(*parts)); previous_count=count;
        assert(!obor_state_resource_layout(sizeof(head),depth,depth*2,size-1,&layout));
        assert(!obor_state_resource_layout(sizeof(head),depth,depth*2,size+1,&layout));
        assert(!obor_state_resource_layout(UINT64_MAX,depth,0,size,&layout));
        assert(!obor_state_resource_layout(sizeof(head),UINT64_MAX,0,size,&layout));
        assert(!obor_state_resource_layout(sizeof(head),depth,UINT64_MAX,size,&layout));
    }
    /* Logical movement of the same physical bytes invalidates an old mapping. */
    obor_state_part moved=parts[5]; moved.offset++;
    assert(!obor_state_part_mapped(&moved,previous,previous_count,moved.offset,32));
    moved=parts[3]; moved.address=heap;
    assert(!obor_state_part_mapped(&moved,previous,previous_count,moved.offset,32));
    moved=parts[3]; moved.kind=OBOR_STATE_BYTES;
    assert(!obor_state_part_mapped(&moved,previous,previous_count,moved.offset,32));
    /* A formerly nonzero region may never inherit a neighbouring zero proof. */
    moved=(obor_state_part){parts[5].offset,32,NULL,OBOR_STATE_ZERO};
    assert(!obor_state_part_mapped(&moved,previous,previous_count,moved.offset,32));
    assert(obor_state_manifest_length(manifest,sizeof(manifest)) == sizeof(manifest));
    manifest[10]=1; /*65536slots is the exact fixed-window maximum.*/
    assert(obor_state_manifest_length(manifest,OBOR_STATE_MANIFEST_WINDOW) == OBOR_STATE_MANIFEST_WINDOW);
    manifest[8]=1;
    assert(!obor_state_manifest_length(manifest,OBOR_STATE_MANIFEST_WINDOW));
    assert(!obor_state_manifest_length(manifest,31));
    assert(!obor_state_manifest_length(NULL,UINT32_MAX));
    /* Bounded deterministic malformed-layout mutations; helper never reads
     * beyond its validated manifest header or materializes its zero windows. */
    uint32_t value=7;
    for (unsigned i=0;i<10000;++i) {
        value=value*1664525U+1013904223U;
        memcpy(manifest+8,&value,sizeof(value));
        (void)obor_state_manifest_length(manifest,sizeof(manifest));
        obor_state_resource_offsets layout;
        (void)obor_state_resource_layout(value,value>>4,value>>3,value>>1,&layout);
    }
}

static void aligned_heap_windows(void)
{
    /* Every possible module-prefix residue must align the first physical
     * heap byte, preserve the legacy layout, and keep stack/manifest offsets
     * independent of both stack depth and heap growth. */
    for (uint32_t prefix=0; prefix<OBOR_STATE_HEAP_ALIGNMENT; ++prefix) {
        uint32_t legacy_heap=prefix+OBOR_STATE_STACK_WINDOW+OBOR_STATE_MANIFEST_WINDOW;
        uint32_t padding=obor_state_resource_heap_padding(legacy_heap);
        assert(padding < OBOR_STATE_HEAP_ALIGNMENT);
        assert(!((legacy_heap+padding+OBOR_STATE_SPARSE_PREFIX) % OBOR_STATE_HEAP_ALIGNMENT));
        obor_state_resource_offsets legacy, aligned, grown;
        uint32_t heap_size=OBOR_STATE_SPARSE_PREFIX+32768;
        uint32_t total=legacy_heap+padding+heap_size;
        assert(obor_state_resource_layout(prefix,17,heap_size,total-padding,&legacy));
        assert(obor_state_resource_layout_aligned(prefix,17,heap_size,total,1,&aligned));
        assert(obor_state_resource_layout_aligned(prefix,33,heap_size+71,total+71,1,&grown));
        assert(aligned.heap==legacy.heap+padding && aligned.stack==legacy.stack);
        assert(aligned.manifest==legacy.manifest && grown.manifest==aligned.manifest);
        assert(grown.heap==aligned.heap && grown.stack+16==aligned.stack);
        assert(!obor_state_resource_layout_aligned(prefix,17,heap_size,total-1,1,&grown));
        assert(!obor_state_resource_layout_aligned(prefix,17,heap_size,total+1,1,&grown));
        assert(!obor_state_resource_layout_aligned(prefix,17,heap_size,legacy_heap,1,&grown));
        assert(!obor_state_resource_layout_aligned(prefix,17,UINT64_MAX,total,1,&grown));
        /* One changed tracked page previously invalidated both codec blocks
         * it overlapped. Alignment removes that geometric amplification. */
        uint32_t first=aligned.heap+OBOR_STATE_SPARSE_PREFIX;
        assert(first / OBOR_STATE_HEAP_ALIGNMENT ==
               (first+OBOR_STATE_HEAP_ALIGNMENT-1) / OBOR_STATE_HEAP_ALIGNMENT);
    }
    obor_state_resource_offsets unused;
    assert(!obor_state_resource_layout_aligned(UINT64_MAX,0,0,UINT32_MAX,1,&unused));
    assert(!obor_state_resource_layout_aligned(0,UINT64_MAX,0,UINT32_MAX,1,&unused));
    assert(!obor_state_resource_layout_aligned(0,0,0,UINT32_MAX,1,NULL));
}

int main(void)
{
    stream_boundaries(); stable_windows(); heap_reader_contract(); aligned_heap_windows();
    puts("stream_boundaries=1 fixed_windows=1 growth_dirty_proofs=1 mutations=10000");
    puts("aligned_heap_residues=16384 legacy_layout_preserved=1");
    return 0;
}
