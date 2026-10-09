/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_RESOURCE_IMAGE_H
#define OBOR_RESOURCE_IMAGE_H
#include <stddef.h>
#include <stdint.h>

/* Reconstruction candidates only. Unsupported images remain ordinary mutable
 * snapshot bytes. An engine must prove equality with the candidate before
 * registering a reconstructible range; decoding success alone is not proof. */
#define OBOR_RESOURCE_IMAGE_PIXELS (8U << 20)
#define OBOR_RESOURCE_IMAGE_INPUT (32U << 20)
#define OBOR_RESOURCE_IMAGE_DIMENSION 4096U
typedef struct {
    void *(*allocate)(size_t);
    void (*release)(void *);
} obor_resource_image_allocator;

/* Decode exact indexed bytes, without RGB conversion, palette mutation, engine
 * allocation, filesystem access or global decoder state. Output is untrusted
 * on failure. PNG supports 8-bit grayscale/indexed images; GIF initially
 * supports a single full-canvas image, with optional interlacing/extensions. */
int obor_resource_image_decode(const void *input, size_t input_size,
        void *pixels, size_t pixels_size, uint32_t *width, uint32_t *height,
        const obor_resource_image_allocator *allocator);

/* Deterministic RLE8 body candidate, with self-relative little-endian row
 * offsets. The caller supplies the engine-declared cropped indexed rectangle.
 * No sprite header, palette, pointer or allocator padding is emitted.
 * A NULL output measures the exact initialized body length. */
size_t obor_resource_image_rle8(const void *pixels, uint32_t width,
        uint32_t height, uint32_t stride, void *output, size_t output_size);
#endif
