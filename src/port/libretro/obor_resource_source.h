/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_RESOURCE_SOURCE_H
#define OBOR_RESOURCE_SOURCE_H
#include "obor_resource_image.h"

#define OBOR_RESOURCE_DIRECTORY_LIMIT (32U << 20)
#define OBOR_RESOURCE_MEMBER_LIMIT 100000U
#define OBOR_RESOURCE_PATH_LIMIT 4096U

typedef struct {
    void *context;
    uint64_t size;
    /* Read exactly length bytes at offset; return zero on any failure. The
     * source belongs to the current content, never a state-provided host path. */
    int (*read)(void *context, uint64_t offset, void *output, size_t length);
} obor_resource_reader;
typedef struct obor_resource_source obor_resource_source;

/* Independent read-only index of an ordinary PACK archive. No engine handles,
 * filecache, allocation lists or globals are touched. Unsupported/invalid
 * archives disable reconstruction, preserving ordinary complete state bytes. */
obor_resource_source *obor_resource_source_create(const obor_resource_reader *,
        const obor_resource_image_allocator *);
void obor_resource_source_destroy(obor_resource_source *);
uint32_t obor_resource_source_count(const obor_resource_source *);
int obor_resource_source_find(const obor_resource_source *, const char *name,
        size_t name_length, uint32_t *member, uint32_t *length);
int obor_resource_source_read(const obor_resource_source *, uint32_t member,
        void *output, size_t capacity);
#endif
