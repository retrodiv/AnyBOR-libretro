/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <assert.h>
uint32_t obor_profile_build;
typedef void (*renderer)(int,int,int,int,int,int,int,int*,uint32_t*);
@PROTOTYPES@
static renderer renderers[]={render_0,render_1,render_2};
static const unsigned char packets[][32]={@PACKETS@};
static const int cases[][6]={@CASES@};
@ORACLES@
static void check(int revision, int epoch)
{
    union { int align; unsigned char bytes[128]; } encoded;
    uint32_t output[72], repeat[72];
    unsigned int u,c,p;
    int row;
    obor_profile_build=revision;
    for(u=0;u<3;u++) for(c=0;c<sizeof(cases)/sizeof(cases[0]);c++) {
        const int *v=cases[c];
        memset(&encoded,0,sizeof(encoded));
        *(int*)encoded.bytes=sizeof(int);
        memcpy(encoded.bytes+sizeof(int),packets[v[0]],sizeof(packets[0]));
        renderers[u](epoch,v[1],v[2],v[3],v[4],v[5],4,(int*)encoded.bytes,output);
#ifdef COLLECT_ORIGINAL
        printf("%d %u %u ",epoch,u,c);
        for(p=0;p<72;p++) printf("%08x",output[p]);
        putchar('\n');
#else
        const uint32_t *expected=oracles[epoch][u][c];
        for(p=0;p<72;p++) if(output[p]!=expected[p]) {
            fprintf(stderr,"revision=%d unit=%u case=%u pixel=%u got=%x expected=%x\n",
                    revision,u,c,p,output[p],expected[p]);
            abort();
        }
        /* Edge rows have no original oracle where old pointer traversal left
         * the image. Check bounded execution and stable results separately. */
        for(row=0;row<=8;row+=8) {
            renderers[u](epoch,v[1],v[2],v[3],v[4],v[5],row,(int*)encoded.bytes,output);
            renderers[u](epoch,v[1],v[2],v[3],v[4],v[5],row,(int*)encoded.bytes,repeat);
            assert(!memcmp(output,repeat,sizeof(output)));
        }
#endif
    }
}
int main(void)
{
    @CHECKS@
    puts("early_sprite_lines=1");
    return 0;
}
