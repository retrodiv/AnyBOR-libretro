/* SPDX-License-Identifier: MIT
 * Copyright (c) 2015 Jim Kalafut
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Adapted from AnyGM gml_hash.c, commit 31d5666d72559136327b3165bbaca3b81759965b.
 * See LICENSES/imohash.txt and LICENSES/murmur3.txt.
 */
#ifndef OBOR_IMOHASH_H
#define OBOR_IMOHASH_H
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* Standard defaults: full input below 128 KiB; otherwise three 16 KiB samples.
 * A cache identity, not a full-content integrity check. Read failures leave
 * the digest untouched. Readers must fill the complete requested range. */
typedef int (*obor_imohash_read_at)(void *, uint64_t, void *, size_t);

/* MurmurHash3 was written by Austin Appleby, and is placed in the public
 * domain. The author hereby disclaims copyright to this source code.
 * Adapted from Peter Scott's C port: only x64_128, seed zero, explicit
 * little-endian unaligned reads and big-endian output lanes for imohash.
 * imohash sampling and size encoding follow Jim Kalafut's MIT implementation.
 * See LICENSES/imohash.txt, LICENSES/murmur3.txt and docs/PROVENANCE.md. */
static uint64_t imohash_rotate(uint64_t value,unsigned count){
  return (value<<count)|(value>>(64-count));
}

static uint64_t imohash_mix(uint64_t value){
  value^=value>>33; value*=UINT64_C(0xff51afd7ed558ccd);
  value^=value>>33; value*=UINT64_C(0xc4ceb9fe1a85ec53);
  return value^(value>>33);
}

static uint64_t imohash_le64(const uint8_t *data){
  uint64_t value=0;
  for(unsigned i=0;i<8;i++) value|=(uint64_t)data[i]<<(i*8);
  return value;
}

static void imohash_murmur(const uint8_t *data,size_t size,uint8_t digest[16]){
  const uint64_t c1=UINT64_C(0x87c37b91114253d5),c2=UINT64_C(0x4cf5ad432745937f);
  uint64_t h1=0,h2=0;
  size_t blocks=size/16;
  for(size_t i=0;i<blocks;i++){
    uint64_t k1=imohash_le64(data+i*16),k2=imohash_le64(data+i*16+8);
    k1*=c1; k1=imohash_rotate(k1,31); k1*=c2; h1^=k1;
    h1=imohash_rotate(h1,27); h1+=h2; h1=h1*5+0x52dce729;
    k2*=c2; k2=imohash_rotate(k2,33); k2*=c1; h2^=k2;
    h2=imohash_rotate(h2,31); h2+=h1; h2=h2*5+0x38495ab5;
  }
  const uint8_t *tail=data+blocks*16;
  size_t remaining=size%16;
  uint64_t k1=0,k2=0;
  for(size_t i=0;i<remaining && i<8;i++) k1|=(uint64_t)tail[i]<<(i*8);
  for(size_t i=8;i<remaining;i++) k2|=(uint64_t)tail[i]<<((i-8)*8);
  if(remaining>8){ k2*=c2; k2=imohash_rotate(k2,33); k2*=c1; h2^=k2; }
  if(remaining){ k1*=c1; k1=imohash_rotate(k1,31); k1*=c2; h1^=k1; }
  h1^=size; h2^=size;
  h1+=h2; h2+=h1;
  h1=imohash_mix(h1); h2=imohash_mix(h2);
  h1+=h2; h2+=h1;
  for(unsigned i=0;i<8;i++){
    digest[i]=(uint8_t)(h1>>(56-i*8));
    digest[i+8]=(uint8_t)(h2>>(56-i*8));
  }
}

static int obor_imohash_read(obor_imohash_read_at reader,void *context,uint64_t size,uint8_t digest[16]){
  if(!reader || !digest) return 0;
  const size_t sample=16384;
  size_t count=size<131072?(size_t)size:3*sample;
  uint8_t *bytes=(uint8_t *)malloc(count?count:1);
  if(!bytes) return 0;
  int ok=1;
  if(size<131072){
    if(count) ok=reader(context,0,bytes,count);
  }else{
    uint64_t offsets[3]={0,size/2,size-sample};
    for(unsigned i=0;i<3 && ok;i++) ok=reader(context,offsets[i],bytes+i*sample,sample);
  }
  if(ok){
    uint8_t result[16];
    imohash_murmur(bytes,count,result);
    /* Unsigned LEB128 overwrites the start of the hash, rather than extending it. */
    uint64_t length=size; unsigned at=0;
    do{
      result[at++]=(uint8_t)((length&127u)|(length>=128?128u:0u));
      length>>=7;
    }while(length);
    memcpy(digest,result,sizeof result);
  }
  free(bytes);
  return ok;
}

static int imohash_memory_read(void *context,uint64_t offset,void *data,size_t size){
  memcpy(data,(const uint8_t *)context+(size_t)offset,size);
  return 1;
}

static int obor_imohash(const void *data,size_t size,uint8_t digest[16]){
  if(!data && size) return 0;
  return obor_imohash_read(imohash_memory_read,(void *)data,size,digest);
}

#endif
