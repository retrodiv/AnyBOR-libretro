/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 */

#include "openbor.h"
#include "borendian.h"
#include <assert.h>
#include <zlib.h>

uint32_t obor_profile_build;

struct png_fixture
{
    const unsigned char *data;
    int size, width, interlaced, early_rejected, output_width;
};

@FILES@
static const struct png_fixture fixtures[] = {
    @CONTEXTS@
};

static int handle = 1;
static int res[2];
static int cursor;
static const struct png_fixture *current;

void writeToLogFile(const char *message, ...)
{
    (void)message;
}

void *checkAlloc(void *pointer, size_t size, const char *function, const char *file, int line)
{
    (void)size;
    (void)function;
    (void)file;
    (void)line;
    assert(pointer);
    return pointer;
}

int seekpackfile(int descriptor, int offset, int origin)
{
    assert(descriptor == handle);
    cursor = (origin == SEEK_END ? current->size : origin == SEEK_CUR ? cursor : 0) + offset;
    assert(cursor >= 0 && cursor <= current->size);
    return cursor;
}

int readpackfile(int descriptor, void *destination, int size)
{
    assert(descriptor == handle && size >= 0 && size <= current->size - cursor);
    memcpy(destination, current->data + cursor, (size_t)size);
    cursor += size;
    return size;
}

#pragma pack(push, 1)
@METHODS@
#pragma pack(pop)

int main(void)
{
    const unsigned profiles[] = {6997, 7039, 7086, 7091, 7123, 7142};
    const char original_9x8[] =
        "111203131" "123345678" "111223334" "123345678"
        "011213132" "123345678" "112223334" "123345678";
    const char original_9x8_to_8x8_regular[] =
        "11111111" "01234567" "11234567" "12234567"
        "12334567" "12344567" "12345567" "12345667";
    const char original_9x8_to_8x8_interlaced[] =
        "11120313" "12334567" "11122333" "12344567"
        "01121313" "12345567" "11222333" "12345667";
    for(size_t p = 0; p < sizeof(profiles) / sizeof(profiles[0]); ++p)
    {
        obor_profile_build = profiles[p];
        for(size_t i = 0; i < sizeof(fixtures) / sizeof(fixtures[0]); ++i)
        {
            current = &fixtures[i];
            res[0] = current->width;
            res[1] = 8;
            png_is_interlaced = current->interlaced;
            unsigned char pixels[72] = {0};
            int palette[256] = {0};
            // readpng starts at the CRC of IHDR after the header has been read.
            cursor = 29;
            assert(readpng(NULL, (unsigned char *)palette, 0, 0));
            assert((unsigned)palette[1] == colour32(32, 64, 128));
            cursor = 29;
            const int accepted = !(obor_profile_build == 6997 && current->early_rejected);
            const char *original = NULL;
            if(obor_profile_build == 6997 && current->width == 9)
            {
                original = current->output_width == 9 ? original_9x8 : current->interlaced
                    ? original_9x8_to_8x8_interlaced : original_9x8_to_8x8_regular;
            }
            assert(readpng(pixels, NULL, current->output_width, res[1]) == accepted);
            for(int pixel = 0; pixel < current->output_width * res[1]; ++pixel)
            {
                const int expected = original ? original[pixel] - '0' : accepted;
                assert(pixels[pixel] == expected);
            }
        }
    }
}
