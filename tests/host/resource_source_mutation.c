/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_resource_source.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void image_test_reset(size_t);
void *image_test_allocate(size_t);
void image_test_release(void *);
size_t image_test_live(void);
size_t image_test_peak(void);

typedef struct {
    unsigned char *bytes;
    size_t size, reads, fail_read;
} source_input;

static int read_source(void *opaque, uint64_t offset, void *out, size_t length)
{
    source_input *input = opaque;
    /* An invalid request is a bug in the reader, not a tolerated short read. */
    assert(offset <= input->size && length <= input->size - offset);
    if (++input->reads == input->fail_read) return 0;
    memcpy(out, input->bytes + offset, length);
    return 1;
}

static uint32_t random_word(uint32_t *seed)
{ uint32_t x = *seed; x ^= x << 13; x ^= x >> 17; x ^= x << 5; return *seed = x; }

int main(int argc, char **argv)
{
    assert(argc > 1);
    const obor_resource_image_allocator allocator = {image_test_allocate, image_test_release};
    uint32_t seed = 871249;
    size_t mutations = 0;
    for (int file = 1; file < argc; ++file) {
        FILE *in = fopen(argv[file], "rb"); assert(in);
        assert(!fseek(in, 0, SEEK_END)); long length = ftell(in);
        assert(length > 0 && length < (1 << 20)); rewind(in);
        size_t capacity = (size_t)length;
        unsigned char *original = malloc(capacity), *changed = malloc(capacity);
        unsigned char *output = malloc(capacity);
        assert(original && changed && output);
        assert(fread(original, 1, capacity, in) == capacity);
        fclose(in);
        for (unsigned iteration = 0; iteration < 1025; ++iteration) {
            memcpy(changed, original, capacity);
            source_input input = {changed, capacity, 0, 0};
            if (iteration && iteration < 960) {
                if (iteration % 3) {
                    size_t at = random_word(&seed) % capacity;
                    if (iteration % 2) changed[at] ^= 1U << (random_word(&seed) % 8);
                    else memset(changed + at, 0xff, capacity - at > 4 ? 4 : capacity - at);
                } else input.size = random_word(&seed) % capacity;
            }
            size_t fail_allocation = iteration >= 960 && iteration < 992 ? iteration - 959 : 0;
            input.fail_read = iteration >= 992 ? iteration - 991 : 0;
            image_test_reset(fail_allocation);
            obor_resource_reader reader = {&input, input.size, read_source};
            obor_resource_source *source = obor_resource_source_create(&reader, &allocator);
            if (source) {
                uint32_t count = obor_resource_source_count(source);
                assert(count && count <= OBOR_RESOURCE_MEMBER_LIMIT);
                for (uint32_t member = 0; member < count; ++member) {
                    /* Exercise validated payload offsets, including injected
                     * I/O failure after successful directory construction. */
                    (void)obor_resource_source_read(source, member, output, capacity);
                    (void)obor_resource_source_read(source, member, output, 0);
                }
                assert(!obor_resource_source_read(source, count, output, capacity));
                assert(!obor_resource_source_read(source, UINT32_MAX, output, capacity));
                const char *names[] = {"DATA\\IMAGE.PNG", "data/second.gif", "missing",
                                      "../escape", "data//empty", "C:/host"};
                for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); ++i) {
                    uint32_t member = 0, bytes = 0;
                    if (obor_resource_source_find(source, names[i], strlen(names[i]), &member, &bytes))
                        assert(member < count && bytes <= capacity);
                }
            } else assert(iteration);
            obor_resource_source_destroy(source);
            assert(!image_test_live());
            assert(image_test_peak() <= OBOR_RESOURCE_DIRECTORY_LIMIT +
                   (size_t)OBOR_RESOURCE_MEMBER_LIMIT * 24 + 128);
            ++mutations;
        }
        free(output); free(changed); free(original);
    }
    printf("bounded_source_mutations=%zu\n", mutations);
    return 0;
}
