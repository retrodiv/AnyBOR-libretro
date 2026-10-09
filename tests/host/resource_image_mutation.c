/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_resource_image.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void image_test_reset(size_t);
void *image_test_allocate(size_t);
void image_test_release(void *);
size_t image_test_live(void);
static uint32_t random_word(uint32_t *seed)
{ uint32_t x = *seed; x ^= x << 13; x ^= x >> 17; x ^= x << 5; return *seed = x; }
int main(int argc, char **argv)
{
    assert(argc > 1);
    const obor_resource_image_allocator allocator = {image_test_allocate, image_test_release};
    unsigned char *pixels = malloc(1U << 20), *encoded = malloc(3U << 20);
    assert(pixels && encoded);
    uint32_t seed = 438197;
    size_t mutations = 0;
    for (int file = 1; file < argc; ++file) {
        FILE *in = fopen(argv[file], "rb"); assert(in);
        assert(!fseek(in, 0, SEEK_END)); long length = ftell(in);
        assert(length > 0 && length < (1 << 20)); rewind(in);
        unsigned char *original = malloc((size_t)length), *changed = malloc((size_t)length);
        assert(original && changed && fread(original, 1, (size_t)length, in) == (size_t)length);
        fclose(in);
        for (unsigned iteration = 0; iteration < 321; ++iteration) {
            memcpy(changed, original, (size_t)length);
            size_t size = (size_t)length;
            if (iteration && iteration % 3) changed[random_word(&seed) % size] ^= 1U << (random_word(&seed) % 8);
            else if (iteration) size = random_word(&seed) % size;
            image_test_reset(iteration > 280 ? iteration - 280 : 0);
            uint32_t w, h;
            if (obor_resource_image_decode(changed, size, pixels, 1U << 20, &w, &h, &allocator)) {
                assert(w && h && (uint64_t)w * h <= (1U << 20));
                size_t used = obor_resource_image_rle8(pixels, w, h, w, encoded, 3U << 20);
                assert(used && used <= (3U << 20));
            } else assert(iteration);
            assert(!image_test_live());
            ++mutations;
        }
        free(original); free(changed);
    }
    free(pixels); free(encoded);
    printf("bounded_image_mutations=%zu\n", mutations);
    return 0;
}
