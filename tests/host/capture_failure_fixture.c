/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdbool.h>
#include <assert.h>
typedef struct { unsigned count; } obor_state_ranges;
static int g_booted=1, behavior, observed, reset;
static long g_frame_no;
static struct { FILE *file; } g_profile;
static FILE *g_trace;
static int g_capture_cadence;
static unsigned char *real_buffer;
static size_t real_extent;
static void obor_profile_init(void) {}
static uint64_t obor_profile_now(void) { return 1; }
static int queue_state_fault(void) { return 0; }
#define RETRO_ENVIRONMENT_GET_SAVESTATE_CONTEXT 72
static void env_cb(unsigned cmd,void *ptr) { (void)cmd;(void)ptr; }
static void obor_profile_record(const char *op,long frame,uint64_t begin,uint64_t end,
                               size_t size,uint32_t written,uint64_t heap,int ok,int ctx)
{ (void)op;(void)frame;(void)begin;(void)end;(void)size;(void)written;(void)heap;(void)ok;(void)ctx; }
static void profile_state_identity(const char *op,void *data,uint32_t size)
{ (void)op;(void)data;(void)size; }
static void obor_capture_cadence_observe(int *c,uint64_t frame)
{ (void)c;(void)frame;observed++; }
static void obor_capture_cadence_reset(int *c) { (void)c;reset++; }
static uint32_t save_stub(void *data,uint32_t size)
{
    if(behavior==1)return 0; /* Refusal before any output. */
    if(behavior==2){if(size>=8)memset((unsigned char *)data+4,0x77,4);return 0;}
    if(behavior==3)return size+1; /* Defensive invalid success size. */
    if(size<16)return 0;
    memset(data,0x5a,size);memcpy(data,"OBC1",4);return size;
}
static uint32_t owned_stub(void *data,uint32_t size,obor_state_ranges *ranges)
{ ranges->count=0;return save_stub(data,size); }
#define p_serialize save_stub
#define p_owned_serialize owned_stub
#include "capture_under_test.inc"
static int accepts_old_state(const void *data,size_t size)
{ return size>=16 && !memcmp(data,"OBC1",4); }
int main(void)
{
    unsigned char buf[96], before[96];real_buffer=buf+16;real_extent=64;
    for(int owned=0;owned<2;owned++)for(int fail=1;fail<=3;fail++){
        obor_state_ranges ranges={0};behavior=0;g_booted=1;
        memset(buf,0xa5,sizeof(buf));assert(serialize_capture(real_buffer,real_extent,owned?&ranges:NULL)==64);
        assert(accepts_old_state(real_buffer,real_extent));memcpy(before,buf,sizeof(buf));
        behavior=fail;assert(!serialize_capture(real_buffer,real_extent,owned?&ranges:NULL));
        assert(!accepts_old_state(real_buffer,real_extent));
        for(size_t i=0;i<sizeof(buf);i++){
            unsigned char want=i>=16&&i<20?0:before[i];
            if(fail==2&&i>=20&&i<24)want=0x77;
            assert(buf[i]==want);
        }
        behavior=0;assert(serialize_capture(real_buffer,real_extent,owned?&ranges:NULL)==64);
        assert(accepts_old_state(real_buffer,real_extent));
    }
    for(size_t n=0;n<9;n++){
        memset(buf,0xa5,sizeof(buf));behavior=1;
        assert(!serialize_capture(buf+16,n,NULL));
        for(size_t i=0;i<sizeof(buf);i++)assert(buf[i]==(i>=16&&i<16+(n<4?n:4)?0:0xa5));
    }
    behavior=1;assert(!serialize_capture(NULL,64,NULL));
    g_booted=0;memset(buf,0xa5,sizeof(buf));assert(!serialize_capture(buf+16,64,NULL));
    assert(!memcmp(buf+16,"\0\0\0\0",4));
    assert(observed>0&&reset>0);
    puts("PASS: refused, partial, oversized, owned, loading, NULL,0..8bounds and successful recovery");
    return 0;
}
