/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_resource_recipe.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void image_test_reset(size_t);
void *image_test_allocate(size_t);
void image_test_release(void *);
size_t image_test_live(void);
size_t image_test_peak(void);
size_t image_test_attempts(void);
static const obor_resource_image_allocator allocator = {image_test_allocate, image_test_release};

typedef struct { unsigned char *bytes; size_t length, reads; int fail; } input_data;
static int read_input(void *opaque, uint64_t offset, void *out, size_t length)
{
    input_data *in = opaque;
    assert(offset <= in->length && length <= in->length - offset);
    ++in->reads;
    if (in->fail) return 0;
    memcpy(out, in->bytes + offset, length);
    return 1;
}

static obor_resource_source *open_source(input_data *input)
{
    const obor_resource_reader reader = {input, input->length, read_input};
    return obor_resource_source_create(&reader, &allocator);
}

static const unsigned char expected[] = {
    12,0,0,0, 16,0,0,0, 20,0,0,0,
    1,2,5,6,1,1,7,255, 1,2,5,6,1,1,7,255, 1,2,5,6,1,1,7,255
};

static int prove(obor_resource_materializer *m, obor_resource_recipe *r, const char *name, const void *body)
{
    return obor_resource_recipe_prove(m, r, name, strlen(name), 5,3,0,0,5,3,body,sizeof(expected));
}

static void member_slices(input_data *input)
{
    obor_resource_source *source = open_source(input); assert(source);
    obor_resource_materializer *m = obor_resource_materializer_create(source,&allocator,1400); assert(m);
    unsigned char sample[64], wire[OBOR_RESOURCE_RECIPE_SIZE];
    for (unsigned i=0;i<sizeof(sample);++i) sample[i]=(unsigned char)(44+i);
    obor_resource_recipe recipe, loaded, bad;
    assert(obor_resource_recipe_prove_bytes(m,&recipe,"data/sample.bin",15,44,sample,sizeof(sample)));
    assert(recipe.kind==OBOR_RESOURCE_MEMBER_BYTES && !recipe.source_width);
    assert(obor_resource_recipe_write(&recipe,wire,sizeof(wire)));
    size_t cached=obor_resource_materializer_cached(m), reads=input->reads;
    assert(cached && cached<=1400);
    input->fail=1;
    const void *body=obor_resource_recipe_body(m,&recipe);
    assert(body && input->reads==reads && !memcmp(body,sample,sizeof(sample)));
    input->fail=0;
    assert(obor_resource_recipe_prove_bytes(m,&loaded,"data/sample.bin",15,44,sample,sizeof(sample)));
    assert(obor_resource_materializer_cached(m)==cached && obor_resource_recipe_equal(&recipe,&loaded));
    bad=recipe; bad.member_offset=UINT32_MAX; assert(!obor_resource_recipe_valid(&bad));
    bad=recipe; bad.source_width=1; assert(!obor_resource_recipe_valid(&bad));
    bad=recipe; bad.kind=3; assert(!obor_resource_recipe_valid(&bad));
    bad=recipe; bad.kind=OBOR_RESOURCE_RLE8; assert(!obor_resource_recipe_valid(&bad));
    loaded=recipe; sample[20]^=1;
    assert(!obor_resource_recipe_prove_bytes(m,&loaded,"data/sample.bin",15,44,sample,sizeof(sample)));
    assert(obor_resource_recipe_equal(&loaded,&recipe)); sample[20]^=1;
    assert(!obor_resource_recipe_prove_bytes(m,&loaded,"data/sample.bin",15,250,sample,sizeof(sample)));
    assert(!obor_resource_recipe_prove_bytes(m,&loaded,"data/sample.bin",15,UINT32_MAX,sample,sizeof(sample)));
    obor_resource_materializer_destroy(m); obor_resource_source_destroy(source);
    assert(!image_test_live());
    source=open_source(input); assert(source);
    m=obor_resource_materializer_create(source,&allocator,0); assert(m);
    assert(obor_resource_recipe_read(&loaded,wire,sizeof(wire)));
    body=obor_resource_recipe_body(m,&loaded);
    assert(body && !memcmp(body,sample,sizeof(sample)) && !obor_resource_materializer_cached(m));
    input->fail=1; assert(!obor_resource_recipe_body(m,&loaded)); input->fail=0;
    loaded.digest[0]^=1; assert(!obor_resource_recipe_body(m,&loaded)); loaded.digest[0]^=1;
    loaded.member_offset=224; assert(!obor_resource_recipe_body(m,&loaded));
    obor_resource_materializer_destroy(m); obor_resource_source_destroy(source);
    assert(!image_test_live());
    size_t attempts=0;
    for (size_t failure=0; !failure || failure<=attempts; ++failure) {
        image_test_reset(failure);
        source=open_source(input);
        if (source) {
            m=obor_resource_materializer_create(source,&allocator,1400);
            if (m) {
                if (obor_resource_recipe_prove_bytes(m,&loaded,"data/sample.bin",15,44,sample,sizeof(sample))) {
                    body=obor_resource_recipe_body(m,&loaded);
                    if (body) assert(!memcmp(body,sample,sizeof(sample)));
                }
                obor_resource_materializer_destroy(m);
            }
            obor_resource_source_destroy(source);
        }
        if (!failure) attempts=image_test_attempts();
        assert(!image_test_live());
    }
    image_test_reset(0);
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    FILE *file = fopen(argv[1], "rb"); assert(file);
    assert(!fseek(file, 0, SEEK_END)); long length = ftell(file); assert(length > 0 && length < (1 << 20));
    rewind(file);
    input_data input = {malloc((size_t)length), (size_t)length, 0, 0}; assert(input.bytes);
    assert(fread(input.bytes, 1, input.length, file) == input.length); fclose(file);
    image_test_reset(0);
    member_slices(&input);
    obor_resource_source *source = open_source(&input); assert(source);
    obor_resource_materializer *m = obor_resource_materializer_create(source, &allocator, 1400); assert(m);
    obor_resource_recipe png, gif;
    assert(prove(m, &png, "DATA\\IMAGE.PNG", expected));
    assert(!strcmp(png.name, "data/image.png"));
    size_t cached = obor_resource_materializer_cached(m); assert(cached && cached <= 1400);
    assert(prove(m, &gif, "data/second.gif", expected));
    assert(memcmp(png.digest, gif.digest, 32));
    assert(obor_resource_materializer_cached(m) <= 1400);
    assert(prove(m, &gif, "data/second.gif", expected));
    assert(obor_resource_materializer_cached(m) <= 1400);
    unsigned char wire[OBOR_RESOURCE_RECIPE_SIZE], again[OBOR_RESOURCE_RECIPE_SIZE];
    assert(obor_resource_recipe_write(&png, wire, sizeof(wire)));
    obor_resource_recipe loaded;
    assert(obor_resource_recipe_read(&loaded, wire, sizeof(wire)));
    assert(obor_resource_recipe_equal(&loaded, &png));
    assert(obor_resource_recipe_write(&loaded, again, sizeof(again)) && !memcmp(wire, again, sizeof(wire)));
    size_t reads = input.reads;
    const void *body = obor_resource_recipe_body(m, &png);
    assert(body && !memcmp(body, expected, sizeof(expected)));
    reads = input.reads;
    body = obor_resource_recipe_body(m, &png);
    assert(body && input.reads == reads); /* actual bounded cache hit */

    /* A complete body larger than the entire cache still fits losslessly in
     * compressed form. A cache hit works with the source unavailable; after
     * eviction it must rebuild from source or fail, never consult live bytes. */
    obor_resource_materializer *compact = obor_resource_materializer_create(source,&allocator,1024);
    assert(compact);
    unsigned char pixels[4096], expanded[5000]; memset(pixels,7,sizeof(pixels));
    size_t expanded_size=obor_resource_image_rle8(pixels,64,64,64,expanded,sizeof(expanded));
    assert(expanded_size>1024 && expanded_size<=sizeof(expanded));
    obor_resource_recipe large;
    assert(obor_resource_recipe_prove(compact,&large,"data/large.png",14,
        64,64,0,0,64,64,expanded,expanded_size));
    assert(obor_resource_materializer_cached(compact)>0 && obor_resource_materializer_cached(compact)<=1024);
    reads=input.reads; input.fail=1;
    body=obor_resource_recipe_body(compact,&large);
    assert(body && input.reads==reads && !memcmp(body,expanded,expanded_size));
    /* Repeated materialization must neither allocate another decompression
     * buffer nor grow retained memory. A clear must also discard workspace. */
    size_t warm_attempts=image_test_attempts(), warm_live=image_test_live();
    for (unsigned repeat=0;repeat<64;++repeat) {
        body=obor_resource_recipe_body(compact,&large);
        assert(body && !memcmp(body,expanded,expanded_size));
    }
    assert(image_test_attempts()==warm_attempts && image_test_live()==warm_live && input.reads==reads);
    obor_resource_materializer_clear(compact);
    assert(image_test_live()+expanded_size<=warm_live);
    assert(!obor_resource_recipe_body(compact,&large));
    input.fail=0;
    body=obor_resource_recipe_body(compact,&large);
    assert(body && !memcmp(body,expanded,expanded_size));
    obor_resource_materializer_destroy(compact);

    unsigned char modified[sizeof(expected)]; memcpy(modified, expected, sizeof(modified)); modified[15] ^= 1;
    obor_resource_recipe untouched; memset(&untouched, 0x5a, sizeof(untouched)); loaded = untouched;
    assert(!prove(m, &loaded, "data/image.png", modified));
    assert(!memcmp(&loaded, &untouched, sizeof(loaded)));
    assert(!prove(m, &loaded, "data/different.png", expected));
    assert(!prove(m, &loaded, "../outside", expected));
    obor_resource_materializer_destroy(m);
    obor_resource_source_destroy(source); assert(!image_test_live());

    /* Fresh source index, zero cache, no original body or process pointer in
     * the serialized recipe. Repeat with I/O failure and corrupted integrity. */
    source = open_source(&input); assert(source);
    m = obor_resource_materializer_create(source, &allocator, 0); assert(m);
    assert(obor_resource_recipe_read(&loaded, wire, sizeof(wire)));
    body = obor_resource_recipe_body(m, &loaded);
    assert(body && !memcmp(body, expected, sizeof(expected)));
    assert(!obor_resource_materializer_cached(m));
    input.fail = 1; assert(!obor_resource_recipe_body(m, &loaded)); input.fail = 0;
    loaded.digest[0] ^= 1; assert(!obor_resource_recipe_body(m, &loaded)); loaded.digest[0] ^= 1;
    body = obor_resource_recipe_body(m, &loaded); assert(body && !memcmp(body, expected, sizeof(expected)));
    obor_resource_materializer_destroy(m);
    obor_resource_source_destroy(source); assert(!image_test_live());

    /* Every failed allocation must preserve ownership and leave clean teardown.
     * Optional cache failures may still produce an exact reconstruction. */
    size_t attempts = 0;
    for (size_t failure = 0; !failure || failure <= attempts; ++failure) {
        image_test_reset(failure);
        source = open_source(&input);
        if (source) {
            m = obor_resource_materializer_create(source, &allocator, 1400);
            if (m) {
                if (prove(m, &loaded, "data/image.png", expected)) {
                    body = obor_resource_recipe_body(m, &loaded);
                    if (body) assert(!memcmp(body, expected, sizeof(expected)));
                }
                /* Grow an already used workspace. One-shot failure during
                 * growth must leave it safely reusable by the next attempt. */
                int grown=obor_resource_recipe_prove(m,&large,"data/large.png",14,
                    64,64,0,0,64,64,expanded,expanded_size);
                if (!grown) assert(obor_resource_recipe_prove(m,&large,"data/large.png",14,
                    64,64,0,0,64,64,expanded,expanded_size));
                body=obor_resource_recipe_body(m,&large);
                if (body) assert(!memcmp(body,expanded,expanded_size));
                obor_resource_materializer_destroy(m);
            }
            obor_resource_source_destroy(source);
        }
        if (!failure) attempts = image_test_attempts();
        assert(!image_test_live()); assert(image_test_peak() < (32U << 20));
    }
    for (size_t i = 0; i < sizeof(wire); ++i) {
        memcpy(again, wire, sizeof(wire)); again[i] ^= 0xff;
        image_test_reset(0);
        if (obor_resource_recipe_read(&loaded, again, sizeof(again))) {
            source = open_source(&input); assert(source);
            m = obor_resource_materializer_create(source, &allocator, 0); assert(m);
            (void)obor_resource_recipe_body(m, &loaded);
            obor_resource_materializer_destroy(m); obor_resource_source_destroy(source);
        }
        assert(!image_test_live());
    }
    free(input.bytes);
    puts("cold_reconstruction=1 modified_fallback=1 bounded_cache=1 malformed_and_allocation_failures=1");
    return 0;
}
