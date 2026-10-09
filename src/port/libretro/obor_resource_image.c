/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_resource_image.h"
#include <png.h>
#include <string.h>

#define PNG_WORK_LIMIT (16U << 20)
typedef union {
    size_t size;
    long double alignment;
    void *pointer_alignment;
} image_allocation;
typedef struct {
    obor_resource_image_allocator allocator;
    const unsigned char *input;
    size_t input_size, position, allocated;
} image_png_work;

static int image_dimensions(uint32_t w, uint32_t h, size_t capacity)
{
    return w && h && w <= OBOR_RESOURCE_IMAGE_DIMENSION &&
        h <= OBOR_RESOURCE_IMAGE_DIMENSION &&
        (uint64_t)w * h <= OBOR_RESOURCE_IMAGE_PIXELS &&
        (uint64_t)w * h <= capacity;
}

static png_voidp image_png_allocate(png_structp png, png_alloc_size_t size)
{
    image_png_work *work = png_get_mem_ptr(png);
    if (!size || size > PNG_WORK_LIMIT - work->allocated ||
        size > SIZE_MAX - sizeof(image_allocation)) return NULL;
    image_allocation *allocation = work->allocator.allocate(sizeof(*allocation) + size);
    if (!allocation) return NULL;
    allocation->size = size;
    work->allocated += size;
    return allocation + 1;
}

static void image_png_release(png_structp png, png_voidp pointer)
{
    if (!pointer) return;
    image_png_work *work = png_get_mem_ptr(png);
    image_allocation *allocation = (image_allocation *)pointer - 1;
    work->allocated -= allocation->size;
    work->allocator.release(allocation);
}

static void image_png_read(png_structp png, png_bytep bytes, png_size_t size)
{
    image_png_work *work = png_get_io_ptr(png);
    if (size > work->input_size - work->position) png_error(png, "truncated image");
    memcpy(bytes, work->input + work->position, size);
    work->position += size;
}

static void image_png_error(png_structp png, png_const_charp message)
{ (void)message; png_longjmp(png, 1); }
static void image_png_warning(png_structp png, png_const_charp message)
{ (void)png; (void)message; }

static int image_png_decode(const void *input, size_t size, unsigned char *pixels,
        size_t capacity, uint32_t *width, uint32_t *height,
        const obor_resource_image_allocator *allocator)
{
    /* Mutable work lives on the heap: libpng's longjmp must not invalidate
     * automatic variables subsequently used by its destruction callbacks. */
    image_png_work *work = allocator->allocate(sizeof(*work));
    if (!work) return 0;
    memset(work, 0, sizeof(*work));
    work->allocator = *allocator;
    work->input = input;
    work->input_size = size;
    png_structp png = png_create_read_struct_2(PNG_LIBPNG_VER_STRING, work,
            image_png_error, image_png_warning, work,
            image_png_allocate, image_png_release);
    if (!png) { allocator->release(work); return 0; }
    png_infop info = png_create_info_struct(png);
    if (!info) { png_destroy_read_struct(&png, NULL, NULL); allocator->release(work); return 0; }
    volatile int success = 0;
    if (!setjmp(png_jmpbuf(png))) {
        png_set_read_fn(png, work, image_png_read);
        png_set_user_limits(png, OBOR_RESOURCE_IMAGE_DIMENSION, OBOR_RESOURCE_IMAGE_DIMENSION);
        png_set_chunk_malloc_max(png, PNG_WORK_LIMIT);
        png_set_chunk_cache_max(png, 128);
        png_set_crc_action(png, PNG_CRC_ERROR_QUIT, PNG_CRC_ERROR_QUIT);
        png_read_info(png, info);
        png_uint_32 w, h;
        int depth, color, interlace, compression, filter;
        if (!png_get_IHDR(png, info, &w, &h, &depth, &color, &interlace, &compression, &filter) ||
            depth != 8 || (color != PNG_COLOR_TYPE_PALETTE && color != PNG_COLOR_TYPE_GRAY) ||
            !image_dimensions(w, h, capacity)) png_error(png, "unsupported image");
        int passes = png_set_interlace_handling(png);
        png_read_update_info(png, info);
        if (png_get_rowbytes(png, info) != w || png_get_channels(png, info) != 1)
            png_error(png, "unexpected indexed layout");
        memset(pixels, 0, (size_t)w * h);
        for (int pass = 0; pass < passes; ++pass)
            for (png_uint_32 y = 0; y < h; ++y)
                png_read_row(png, pixels + (size_t)y * w, NULL);
        png_read_end(png, info);
        *width = w;
        *height = h;
        success = 1;
    }
    png_destroy_read_struct(&png, &info, NULL);
    allocator->release(work);
    return success;
}

typedef struct {
    const unsigned char *input;
    size_t size, position;
    unsigned remaining, bits, bit_count;
    int finished;
} image_gif_reader;

static int image_gif_skip(image_gif_reader *reader, size_t count)
{
    if (count > reader->size - reader->position) return 0;
    reader->position += count;
    return 1;
}

static int image_gif_blocks(image_gif_reader *reader)
{
    while (reader->position < reader->size) {
        unsigned count = reader->input[reader->position++];
        if (!count) return 1;
        if (!image_gif_skip(reader, count)) return 0;
    }
    return 0;
}

static int image_gif_code(image_gif_reader *reader, unsigned width)
{
    while (reader->bit_count < width) {
        if (!reader->remaining) {
            if (reader->finished || reader->position == reader->size) return -1;
            reader->remaining = reader->input[reader->position++];
            if (!reader->remaining) { reader->finished = 1; return -1; }
            if (reader->remaining > reader->size - reader->position) return -1;
        }
        reader->bits |= (unsigned)reader->input[reader->position++] << reader->bit_count;
        reader->bit_count += 8;
        --reader->remaining;
    }
    unsigned code = reader->bits & ((1U << width) - 1);
    reader->bits >>= width;
    reader->bit_count -= width;
    return (int)code;
}

static unsigned image_little16(const unsigned char *p)
{ return (unsigned)p[0] | (unsigned)p[1] << 8; }

static int image_gif_pixels(image_gif_reader *reader, unsigned char *pixels,
        unsigned width, unsigned height, unsigned minimum, int interlaced)
{
    uint16_t prefix[4096];
    unsigned char suffix[4096], stack[4096];
    unsigned clear = 1U << minimum, end = clear + 1;
    unsigned next = end + 1, bits = minimum + 1, first = 0;
    unsigned written = 0, x = 0, y = 0, pass = 0;
    const unsigned starts[4] = {0, 4, 2, 1}, steps[4] = {8, 8, 4, 2};
    int previous = -1, terminated = 0;
    /* At most one code per output byte plus clear codes and input bytes.
     * The input cap also bounds hostile streams containing only clear codes. */
    for (;;) {
        int value = image_gif_code(reader, bits);
        if (value < 0) return 0;
        unsigned code = (unsigned)value, top = 0;
        if (code == clear) { next = end + 1; bits = minimum + 1; previous = -1; continue; }
        if (code == end) { terminated = 1; break; }
        unsigned original = code;
        if (code >= next) {
            if (code != next || previous < 0) return 0;
            stack[top++] = (unsigned char)first;
            code = (unsigned)previous;
        }
        while (code >= clear) {
            if (code <= end || code >= next || top == sizeof(stack)) return 0;
            stack[top++] = suffix[code];
            /* Prefix codes always predate the dictionary entry. */
            if (prefix[code] >= code) return 0;
            code = prefix[code];
        }
        first = code;
        if (top == sizeof(stack)) return 0;
        stack[top++] = (unsigned char)first;
        while (top) {
            if (written >= width * height || y >= height) return 0;
            pixels[(size_t)y * width + x] = stack[--top];
            ++written;
            if (++x == width) {
                x = 0;
                if (!interlaced) ++y;
                else {
                    y += steps[pass];
                    while (y >= height && pass < 3) y = starts[++pass];
                }
            }
        }
        if (previous >= 0 && next < 4096) {
            prefix[next] = (uint16_t)previous;
            suffix[next++] = (unsigned char)first;
            if (next == (1U << bits) && bits < 12) ++bits;
        }
        previous = (int)original;
    }
    if (!terminated || written != width * height ||
        !image_gif_skip(reader, reader->remaining)) return 0;
    reader->remaining = 0;
    return image_gif_blocks(reader);
}

static int image_gif_decode(const unsigned char *input, size_t size,
        unsigned char *pixels, size_t capacity, uint32_t *width, uint32_t *height)
{
    if (size < 13 || (memcmp(input, "GIF87a", 6) && memcmp(input, "GIF89a", 6))) return 0;
    unsigned w = image_little16(input + 6), h = image_little16(input + 8);
    if (!image_dimensions(w, h, capacity)) return 0;
    image_gif_reader reader = {input, size, 13, 0, 0, 0, 0};
    if ((input[10] & 128) && !image_gif_skip(&reader, 3U << ((input[10] & 7) + 1))) return 0;
    int image_seen = 0;
    while (reader.position < size) {
        unsigned tag = input[reader.position++];
        if (tag == 0x3b) {
            if (!image_seen) return 0;
            *width = w; *height = h;
            return 1;
        }
        if (tag == 0x21) {
            if (!image_gif_skip(&reader, 1) || !image_gif_blocks(&reader)) return 0;
            continue;
        }
        if (tag != 0x2c || image_seen || size - reader.position < 9) return 0;
        const unsigned char *descriptor = input + reader.position;
        /* Partial canvases/multiple images can contain engine-dependent
         * uninitialized pixels or compositing. Leave those resources raw. */
        if (image_little16(descriptor) || image_little16(descriptor + 2) ||
            image_little16(descriptor + 4) != w || image_little16(descriptor + 6) != h) return 0;
        unsigned flags = descriptor[8];
        reader.position += 9;
        if ((flags & 128) && !image_gif_skip(&reader, 3U << ((flags & 7) + 1))) return 0;
        if (reader.position == size) return 0;
        unsigned minimum = input[reader.position++];
        if (minimum < 2 || minimum > 8 ||
            !image_gif_pixels(&reader, pixels, w, h, minimum, flags & 64)) return 0;
        image_seen = 1;
    }
    return 0;
}

int obor_resource_image_decode(const void *input, size_t input_size,
        void *pixels, size_t pixels_size, uint32_t *width, uint32_t *height,
        const obor_resource_image_allocator *allocator)
{
    if (!input || !pixels || !width || !height || !allocator ||
        !allocator->allocate || !allocator->release || input_size > OBOR_RESOURCE_IMAGE_INPUT)
        return 0;
    *width = *height = 0;
    if (input_size >= 8 && !png_sig_cmp(input, 0, 8))
        return image_png_decode(input, input_size, pixels, pixels_size, width, height, allocator);
    return image_gif_decode(input, input_size, pixels, pixels_size, width, height);
}

size_t obor_resource_image_rle8(const void *input, uint32_t width,
        uint32_t height, uint32_t stride, void *output, size_t capacity)
{
    if (!input || !image_dimensions(width, height, OBOR_RESOURCE_IMAGE_PIXELS) ||
        stride < width || (uint64_t)stride * height > OBOR_RESOURCE_IMAGE_PIXELS) return 0;
    const unsigned char *pixels = input;
    unsigned char *encoded = output;
    size_t used = (size_t)height * 4;
    if (encoded && used > capacity) return 0;
    for (uint32_t y = 0; y < height; ++y) {
        uint32_t relative = (uint32_t)(used - (size_t)y * 4);
        if (encoded) for (unsigned b = 0; b < 4; ++b) encoded[y * 4 + b] = (unsigned char)(relative >> (8 * b));
        const unsigned char *row = pixels + (size_t)y * stride;
        uint32_t x = 0;
        for (;;) {
            uint32_t begin = x;
            while (x < width && x - begin < 254 && !row[x]) ++x;
            if (encoded && used == capacity) return 0;
            if (x == width) { if (encoded) encoded[used] = 255; ++used; break; }
            if (encoded) encoded[used] = (unsigned char)(x - begin);
            ++used;
            begin = x;
            while (x < width && x - begin < 255 && row[x]) ++x;
            size_t count = x - begin;
            if (encoded && (used >= capacity || count > capacity - used - 1)) return 0;
            if (encoded) {
                encoded[used] = (unsigned char)count;
                memcpy(encoded + used + 1, row + begin, count);
            }
            used += 1 + count;
        }
    }
    return used;
}
