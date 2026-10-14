/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_RESOURCE_RECIPE_H
#define OBOR_RESOURCE_RECIPE_H
#include "obor_resource_source.h"

#define OBOR_RESOURCE_RECIPE_PATH 512U
#define OBOR_RESOURCE_RECIPE_SIZE (40U + 32U + OBOR_RESOURCE_RECIPE_PATH)
#define OBOR_RESOURCE_BODY_LIMIT (16U << 20)
#define OBOR_RESOURCE_CACHE_LIMIT (128U << 20)
enum { OBOR_RESOURCE_RLE8 = 1, OBOR_RESOURCE_MEMBER_BYTES = 2,
       OBOR_RESOURCE_ABGR32_FRAME = 3 };

typedef struct {
    uint32_t owner, allocation, offset, stride;
} obor_framebuffer_source;
/* The tag selects these canonical wire bytes. File recipes keep their exact
 * existing digest; frame recipes describe one fully captured live allocation.
 * Mutable frame pixels never enter the source-member materializer/cache. */
typedef union {
    unsigned char digest[32];
    unsigned char framebuffer[32];
} obor_resource_origin;

/* All identity is source/layout/integrity information. No game classification.
 * Header/palette/pointer bytes are intentionally absent from this recipe.
 * The source member belongs to the current content, never a host filename. */
typedef struct {
    uint32_t version, source_width, source_height, x, y, width, height, length;
    uint32_t kind, member_offset;
    obor_resource_origin origin;
    char name[OBOR_RESOURCE_RECIPE_PATH];
} obor_resource_recipe;
typedef struct obor_resource_materializer obor_resource_materializer;

/* Source and reader lifetime must outlive the materializer. Cache contains
 * only losslessly compressed source-derived bodies and their complete recipes;
 * never mutable data or rewind history. The limit includes entry metadata and
 * stored bytes. A zero-byte cache is supported for cold-load tests. Separate
 * reconstruction workspaces are bounded by IMAGE_PIXELS and BODY_LIMIT;
 * the body workspace is reused and released when the cache is cleared. */
obor_resource_materializer *obor_resource_materializer_create(
        const obor_resource_source *, const obor_resource_image_allocator *, size_t cache_limit);
void obor_resource_materializer_destroy(obor_resource_materializer *);
void obor_resource_materializer_clear(obor_resource_materializer *);
size_t obor_resource_materializer_cached(const obor_resource_materializer *);

/* Construct and verify an engine-declared candidate by exact byte comparison.
 * A failure leaves the engine body fully mutable. Recipe is published only on
 * success; generated/procedural or modified images are never silently omitted. */
int obor_resource_recipe_prove(obor_resource_materializer *, obor_resource_recipe *,
        const char *name, size_t name_length, uint32_t source_width, uint32_t source_height,
        uint32_t x, uint32_t y, uint32_t width, uint32_t height,
        const void *body, size_t body_length);
/* Exact source-member slice, declared after the engine has read it. PCM
 * samples are one consumer; no container-specific decoder or mutable mixer
 * state belongs in this recipe. All image-only fields must be zero. */
int obor_resource_recipe_prove_bytes(obor_resource_materializer *, obor_resource_recipe *,
        const char *name, size_t name_length, uint32_t member_offset,
        const void *body, size_t body_length);
/* Reconstruct/validate source integrity. Returned view remains valid until the
 * next materializer operation. Does not read or modify the engine's live heap. */
const void *obor_resource_recipe_body(obor_resource_materializer *, const obor_resource_recipe *);
int obor_resource_recipe_valid(const obor_resource_recipe *);
int obor_resource_recipe_equal(const obor_resource_recipe *, const obor_resource_recipe *);
/* Fixed-size, deterministic little-endian wire encoding. No padding leaks. */
int obor_resource_recipe_write(const obor_resource_recipe *, void *, size_t);
int obor_resource_recipe_read(obor_resource_recipe *, const void *, size_t);
/* Version 3 only for this new kind; existing version-2 PAK wire bytes and the
 * manifest record size remain unchanged. Structural registration is followed
 * by exact per-capture proof in the catalog, with raw bytes on any mismatch. */
int obor_resource_recipe_framebuffer(obor_resource_recipe *, const obor_framebuffer_source *,
        uint32_t width, uint32_t height);
int obor_resource_recipe_framebuffer_source(const obor_resource_recipe *, obor_framebuffer_source *);
#endif
