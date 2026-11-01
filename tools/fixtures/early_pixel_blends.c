/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Native tables/operators with bounded libc ownership and independent pixels.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "types.h"
#include "palette.h"
#undef printf
#undef assert
#define assert(c) do { if(!(c)) { fprintf(stderr,"pixel blend line=%d revision=%u\n",__LINE__,obor_profile_build); abort(); } } while(0)
uint32_t obor_profile_build;
static void *owned[6];
static int calls, freed, live, fail_at, startup_done;
void *obor_malloc(size_t size)
{
    assert(size == 5120 || size == 65536);
    assert(calls < 6);
    if(++calls == fail_at) return NULL;
    void *p = malloc(size);
    assert(p);
    owned[calls-1] = p;
    ++live;
    return p;
}
static void obor_free(void *p)
{
    if(!p) return;
    int i;
    for(i=0; i<6 && owned[i]!=p; ++i) {}
    assert(i<6);
    owned[i] = NULL;
    --live;
    ++freed;
    free(p);
}
@REGISTRIES@
#define free obor_free
@HELPERS@
#undef free
static void start_tables(void) { @START_TABLES@ }
static void stop_tables(void) { @STOP_TABLES@ }
struct pixel_case { int bits, mode; unsigned source, destination, expected[3][3]; };
static const struct pixel_case cases[] = { @CASES@ };
static const unsigned char old_dodge[] = { @OLD_DODGE@ };
static unsigned char reference[423936], custom[65536];
static void pixels(int era, int path)
{
    for(unsigned i=0; i<sizeof(cases)/sizeof(*cases); ++i) {
        const struct pixel_case *c=cases+i;
        unsigned output = c->bits==16 ?
            blendfunctions16[c->mode]((unsigned short)c->source,(unsigned short)c->destination) :
            blendfunctions32[c->mode](c->source,c->destination);
        assert(output == c->expected[era][path]);
    }
}
static void reset(void)
{
    assert(live==0);
    memset(owned,0,sizeof(owned));
    memset(blendtables,0,MAX_BLENDINGS*sizeof(*blendtables));
    calls=freed=fail_at=0;
}
static void check(int revision, int era)
{
    obor_profile_build=(uint32_t)revision;
    reset(); pixels(era,0);
    for(int mode=0; mode<MAX_BLENDINGS; ++mode) blendtables[mode]=custom;
    pixels(era,2);
    pixelformat=PIXEL_8; startup_done=1; stop_tables();
    for(int mode=0; mode<MAX_BLENDINGS; ++mode) assert(blendtables[mode]==custom);
    memset(blendtables,0,MAX_BLENDINGS*sizeof(*blendtables));
    for(int bits=16; bits<=32; bits+=16) {
        screenformat = bits==16 ? PIXEL_16 : PIXEL_32;
        /* Startup owns tables only for the indexed true-colour data format. */
        for(int format=PIXEL_8; format<=PIXEL_32; ++format) {
            pixelformat=format; reset(); start_tables();
            assert(calls==(era && format==PIXEL_x8 ? 6 : 0));
            if(calls) {
                size_t size=bits==16 ? 5120 : 65536;
                size_t offset=bits==16 ? 0 : 6*5120;
                for(int mode=0; mode<6; ++mode) {
                    const unsigned char *expected=era==1 && bits==16 && mode==BLEND_DODGE ?
                        old_dodge : reference+offset+(size_t)mode*size;
                    assert(!memcmp(blendtables[mode],expected,size));
                }
                /* Only call the operators corresponding to this table width. */
                for(unsigned i=0; i<sizeof(cases)/sizeof(*cases); ++i) {
                    const struct pixel_case *c=cases+i;
                    if(c->bits!=bits) continue;
                    unsigned output=bits==16 ? blendfunctions16[c->mode](c->source,c->destination) :
                        blendfunctions32[c->mode](c->source,c->destination);
                    assert(output==c->expected[era][1]);
                }
                startup_done=0; stop_tables(); assert(live==6);
                startup_done=1; stop_tables(); assert(live==0 && freed==6);
                stop_tables(); assert(freed==6);
                for(int mode=0; mode<6; ++mode) assert(!blendtables[mode]);
            }
        }
        if(!era) continue;
        for(int failure=1; failure<=6; ++failure) {
            reset(); pixelformat=PIXEL_x8; fail_at=failure;
            start_tables(); assert(calls==6 && live==5 && !blendtables[failure-1]);
            for(unsigned i=0; i<sizeof(cases)/sizeof(*cases); ++i) {
                const struct pixel_case *c=cases+i;
                if(c->bits!=bits || c->mode!=failure-1) continue;
                unsigned output=bits==16 ? blendfunctions16[c->mode](c->source,c->destination) :
                    blendfunctions32[c->mode](c->source,c->destination);
                assert(output==c->expected[era][0]);
            }
            startup_done=1; stop_tables(); assert(live==0 && freed==5);
        }
    }
    reset(); screenformat=PIXEL_8; pixelformat=PIXEL_x8;
    start_tables(); assert(calls==0); stop_tables();
    create_blend_tables_x8(NULL); assert(calls==0);
    printf("revision=%d era=%d pixels=%zu tables=12 ownership=1\n",revision,era,sizeof(cases)/sizeof(*cases));
}
int main(void)
{
    FILE *stream=fopen(@REFERENCE@,"rb"); assert(stream);
    assert(fread(reference,1,sizeof(reference),stream)==sizeof(reference));
    assert(fgetc(stream)==EOF && !ferror(stream) && fclose(stream)==0);
    for(unsigned i=0; i<sizeof(custom); ++i) custom[i]=(unsigned char)(i*37+11);
    @CHECKS@
    puts("early_pixel_blends=1");
    return 0;
}
