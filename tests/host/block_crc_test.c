/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#define _GNU_SOURCE 1
#include "obor_block_crc.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#if defined(__linux__)
#include <sys/mman.h>
#include <unistd.h>
#endif

static uint32_t bitwise_crc(uint32_t seed, const unsigned char *bytes, uint32_t length)
{
    uint32_t crc = ~seed;
    for (uint32_t i=0; i<length; ++i) {
        crc ^= bytes[i];
        for (unsigned bit=0; bit<8; ++bit)
            crc = (crc >> 1) ^ ((crc & 1) ? UINT32_C(0xedb88320) : 0);
    }
    return ~crc;
}

int main(void)
{
    unsigned char bytes[16384+16]; uint32_t value=0x13ad8157;
    for (size_t i=0; i<sizeof(bytes); ++i) {
        value ^= value << 13; value ^= value >> 17; value ^= value << 5;
        bytes[i]=(unsigned char)value;
    }
    const uint32_t seeds[]={0,1,UINT32_MAX,0x12345678};
    const uint32_t lengths[]={0,1,2,3,4,7,8,9,15,16,17,31,32,33,511,512,513,4095,4096,4097,16383,16384};
    assert(obor_block_crc32(0,"123456789",9)==UINT32_C(0xcbf43926));
    assert(!obor_block_crc32(UINT32_MAX,NULL,0));
    assert(!obor_block_crc32(0,NULL,13));
    size_t comparisons=0;
    for (unsigned s=0; s<sizeof(seeds)/sizeof(seeds[0]); ++s)
        for (unsigned offset=0; offset<16; ++offset)
            for (unsigned n=0; n<sizeof(lengths)/sizeof(lengths[0]); ++n) {
                uint32_t length=lengths[n], expected=bitwise_crc(seeds[s],bytes+offset,length);
                assert(obor_block_crc32(seeds[s],bytes+offset,length)==expected);
                uint32_t first=length/2, partial=obor_block_crc32(seeds[s],bytes+offset,first);
                assert(obor_block_crc32(partial,bytes+offset+first,length-first)==expected);
                ++comparisons;
            }
#if defined(__linux__)
    long page=sysconf(_SC_PAGESIZE); assert(page>=4096);
    unsigned char *p=mmap(NULL,(size_t)page*2,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    assert(p!=MAP_FAILED); memset(p,0x6d,(size_t)page);
    assert(!mprotect(p+page,(size_t)page,PROT_NONE));
    for (uint32_t n=0; n<=193; ++n)
        assert(obor_block_crc32(0,p+page-n,n)==bitwise_crc(0,p+page-n,n));
    assert(!munmap(p,(size_t)page*2));
#endif
    printf("crc_known_vector=1 exact_comparisons=%zu incremental=1 bounded_reads=1\n",comparisons);
    return 0;
}
