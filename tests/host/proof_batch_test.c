/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_block_state.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BLOCK OBOR_BLOCK_STATE_BLOCK
#define MAXIMUM (320U * BLOCK + 19)
typedef struct {
    unsigned char *bytes;
    unsigned char dirty[321];
    uint32_t length, prior_length;
    unsigned reads, groups, accepted, interior_rejected;
    int broad, valid, fail, boundary;
} input;

static const void *read_bytes(void *context,uint32_t offset,uint32_t length,void *scratch)
{
    input *in=context;(void)scratch;++in->reads;
    if(in->fail || offset>in->length || length>in->length-offset)return NULL;
    return in->bytes+offset;
}
static int unchanged(void *context,uint32_t offset,uint32_t length)
{
    input *in=context;
    if(length>BLOCK)++in->groups;
    if(!in->valid || !length || offset>in->prior_length || length>in->prior_length-offset ||
       (length>BLOCK && !in->broad))return 0;
    /* Simulate a mapping/manifest boundary whose combined span cannot be
     * proven, even though individual blocks on either side can be proven. */
    if(in->boundary && offset<97*BLOCK && offset+length>97*BLOCK)return 0;
    for(uint32_t i=offset/BLOCK;i<=(offset+length-1)/BLOCK;++i)
        if(in->dirty[i]) {
            if(length>BLOCK && i>offset/BLOCK && i<(offset+length-1)/BLOCK)++in->interior_rejected;
            return 0;
        }
    if(length>BLOCK)++in->accepted;
    return 1;
}
static void equal_image(obor_block_state *a,obor_block_state *b,const input *in)
{
    uint32_t an,bn,rn;
    const void *ai=obor_block_state_image(a,&an),*bi=obor_block_state_image(b,&bn);
    const void *raw=obor_block_state_raw(a,&rn);
    assert(ai && bi && an==bn && !memcmp(ai,bi,an));
    assert(raw && rn==in->length && !memcmp(raw,in->bytes,rn));
}

int main(void)
{
    const obor_block_allocator allocator={.calloc=calloc,.realloc=realloc,.free=free};
    unsigned total=0,groups=0,interior=0;
    for(unsigned worker=0;worker<2;++worker)for(unsigned boundary=0;boundary<2;++boundary) {
        unsigned char *bytes=malloc(MAXIMUM);assert(bytes);
        for(uint32_t i=0;i<MAXIMUM;++i)bytes[i]=(unsigned char)((i/31+i/4096)%17);
        input candidate={.bytes=bytes,.length=256*BLOCK,.broad=1,.boundary=(int)boundary};
        input reference=candidate;reference.broad=0;
        obor_block_source ca={&candidate,read_bytes,unchanged},re={&reference,read_bytes,unchanged};
        obor_block_state *a=obor_block_state_create(&allocator),*b=obor_block_state_create(&allocator);
        obor_block_state *cold=obor_block_state_create(&allocator);assert(a && b && cold);
        obor_block_state_set_worker(a,worker);obor_block_state_set_worker(b,worker);
        obor_block_state_set_compaction(a,1);obor_block_state_set_compaction(b,1);
        for(unsigned turn=0;turn<36;++turn) {
            memset(candidate.dirty,0,sizeof(candidate.dirty));
            uint32_t prior=candidate.length;
            if(turn==8)candidate.length=MAXIMUM;
            if(turn==16)candidate.length=129*BLOCK+7;
            if(turn==24)candidate.length=256*BLOCK;
            candidate.valid=turn!=0 && turn!=18 && turn!=30;
            candidate.prior_length=prior;
            const unsigned points[]={0,31,63,64,65,96,127,128,191,255,319};
            if(turn%4==1) {
                unsigned i=31;candidate.dirty[i]=1;bytes[i*BLOCK+17]^=0x71;
            } else if(turn%4==2) {
                for(unsigned j=0;j<sizeof(points)/sizeof(*points);++j) {
                    unsigned i=points[j];
                    if(i*BLOCK+17>=candidate.length)continue;
                    candidate.dirty[i]=1;bytes[i*BLOCK+17]^=(unsigned char)(turn+j+1);
                }
            } else if(turn%4==3) {
                for(unsigned i=0;i<(candidate.length+BLOCK-1)/BLOCK;++i) {
                    candidate.dirty[i]=1;bytes[i*BLOCK]^=0x35;
                }
            }
            if(turn==18) {obor_block_state_forget(a);obor_block_state_forget(b);}
            reference.length=candidate.length;reference.prior_length=candidate.prior_length;
            reference.valid=candidate.valid;
            memcpy(reference.dirty,candidate.dirty,sizeof(candidate.dirty));
            assert(obor_block_state_encode_fast(a,&ca,candidate.length));
            assert(obor_block_state_encode_fast(b,&re,reference.length));
            equal_image(a,b,&candidate);
            uint32_t size;const void *image=obor_block_state_image(a,&size);
            obor_block_state_forget(cold);assert(obor_block_state_decode(cold,image,size));
            uint32_t raw_size;const void *raw=obor_block_state_raw(cold,&raw_size);
            assert(raw_size==candidate.length && !memcmp(raw,bytes,raw_size));
            if(turn==29) {
                candidate.valid=reference.valid=0;candidate.fail=reference.fail=1;
                assert(!obor_block_state_encode_fast(a,&ca,candidate.length));
                assert(!obor_block_state_encode_fast(b,&re,reference.length));
                candidate.fail=reference.fail=0;
            }
            ++total;
        }
        assert(candidate.accepted>0 && candidate.interior_rejected>0);
        groups+=candidate.accepted;interior+=candidate.interior_rejected;
        obor_block_state_destroy(a);obor_block_state_destroy(b);obor_block_state_destroy(cold);free(bytes);
    }
    printf("identical_complete_images=%u cold_decodes=%u accepted_group_proofs=%u interior_dirty_rejections=%u failure_recovery=4\n",total,total,groups,interior);
    return 0;
}
