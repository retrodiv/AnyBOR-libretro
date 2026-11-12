/* SPDX-License-Identifier: MIT
 * Copyright (c) 2015 Jim Kalafut (known-answer vectors)
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Adapted from AnyGM test_hash.c at 31d5666d72559136327b3165bbaca3b81759965b.
 * See LICENSES/imohash.txt.
 */
#include "anybor_imohash.h"
#include <assert.h>
static int hex_value(char value){
  if(value>='0' && value<='9') return value-'0';
  if(value>='a' && value<='f') return value-'a'+10;
  return -1;
}

static void imohash_vectors(void){
  /* M(128) and expectations from Jim Kalafut's MIT spec_test.go.
   * See LICENSES/imohash.txt and docs/PROVENANCE.md. */
  static const uint8_t data[]={
    0x7f,0xc5,0x62,0x70,0xe7,0xa7,0x0f,0xa8,0x1a,0x59,0x35,0xb7,0x2e,0xac,0xbe,0x29,
    0x3b,0x98,0xe2,0xdf,0xfc,0x6c,0xb0,0x6a,0x89,0xdc,0xb0,0xd5,0xc6,0x0a,0x02,0x06,
    0xe1,0xfa,0xff,0xb3,0xe6,0x14,0xe6,0xc2,0xfb,0xa7,0x42,0x96,0x96,0x23,0x86,0xb7,
    0x09,0x88,0x90,0xdd,0xe0,0x69,0xe9,0xab,0xad,0x63,0xf1,0x9a,0x0d,0x9e,0x1f,0x32,
    0xf6,0xa6,0x26,0x31,0x67,0xc9,0x2d,0xe8,0x64,0x4a,0xc9,0x98,0xb3,0xc4,0xe4,0xd1,
    0x36,0xd0,0x4a,0x9d,0x74,0x39,0x2c,0x72,0x7b,0x1a,0x9b,0xf9,0x7a,0x7b,0xcb,0xac,
    0x84,0x30,0x89,0x4c,0xfe,0xb5,0x4a,0x36,0x25,0xf1,0x8f,0xe2,0x4f,0xce,0x27,0x2e,
    0xae,0xe9,0xe3,0x8c,0xb4,0xd4,0x0e,0xc2,0x79,0x45,0x42,0x56,0x75,0x39,0xb4,0xc8
  };
  static const struct { size_t size; const char *hex; } cases[]={
    {0,"00000000000000000000000000000000"},
    {1,"01659e2ec0f3c75bf39e43a41adb5d4f"},
    {127,"7f47671cc79d4374404b807249f3166e"},
    {128,"800183e5dbea2e5199ef7c8ea963a463"}
  };
  for(size_t i=0;i<sizeof cases/sizeof cases[0];i++){
    uint8_t digest[16];
    assert(obor_imohash(data,cases[i].size,digest));
    for(unsigned j=0;j<16;j++)
      assert(digest[j]==(uint8_t)((hex_value(cases[i].hex[j*2])<<4)|hex_value(cases[i].hex[j*2+1])));
  }
}

typedef struct { uint64_t size; size_t calls,bytes; unsigned fail; } ReadProbe;

static int probe_read(void *context,uint64_t offset,void *data,size_t size){
  ReadProbe *probe=(ReadProbe *)context;
  uint64_t expected=probe->calls==0?0:probe->calls==1?probe->size/2:probe->size-16384;
  assert(offset==expected && size==(probe->size<131072?(size_t)probe->size:16384));
  probe->calls++;probe->bytes+=size;
  memset(data,'A',size);
  return probe->calls!=probe->fail;
}

static void imohash_reads(void){
  const uint64_t sizes[]={0,1,131071,131072,500001,UINT64_C(0x100000001),UINT64_MAX};
  uint8_t digest[16];
  for(unsigned i=0;i<sizeof sizes/sizeof sizes[0];i++){
    ReadProbe probe={sizes[i],0,0,0};
    assert(obor_imohash_read(probe_read,&probe,probe.size,digest));
    assert(probe.calls==(probe.size==0?0:probe.size<131072?1:3));
    assert(probe.bytes==(probe.size<131072?(size_t)probe.size:49152));
    uint64_t value=probe.size;unsigned at=0;
    do{
      assert(digest[at++]==(uint8_t)((value&127)|(value>=128?128:0)));
      value>>=7;
    }while(value);
  }
  for(unsigned failure=1;failure<=3;failure++){
    ReadProbe probe={131072,0,0,failure};
    uint8_t original[16];memset(original,0xa5,sizeof original);
    memcpy(digest,original,sizeof digest);
    assert(!obor_imohash_read(probe_read,&probe,probe.size,digest));
    assert(probe.calls==failure && !memcmp(original,digest,sizeof digest));
  }
  assert(!obor_imohash(NULL,1,digest));
}


int main(void) {
    imohash_vectors();
    imohash_reads();
    return 0;
}
