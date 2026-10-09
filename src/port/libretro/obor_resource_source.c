/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_resource_source.h"
#include <string.h>

typedef struct { uint32_t name, name_length, offset, length; } resource_member;
struct obor_resource_source {
    obor_resource_image_allocator allocator;
    obor_resource_reader reader;
    unsigned char *directory;
    resource_member *members;
    uint32_t *order, *temporary;
    uint32_t count;
};

static uint32_t source_u32(const unsigned char *p)
{ return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24; }

static int source_path(char *out, const char *input, size_t size)
{
    if (!size || size >= OBOR_RESOURCE_PATH_LIMIT) return 0;
    size_t component = 0;
    for (size_t i = 0; i <= size; ++i) {
        unsigned char c = i == size ? '/' : (unsigned char)input[i];
        if (c == '\\') c = '/';
        if (!c || c == ':') return 0;
        if (c == '/') {
            size_t length = i - component;
            if (!length || (length == 1 && input[component] == '.') ||
                (length == 2 && input[component] == '.' && input[component + 1] == '.')) return 0;
            component = i + 1;
        }
        if (i < size) out[i] = (char)(c >= 'A' && c <= 'Z' ? c + 'a' - 'A' : c);
    }
    out[size] = 0;
    return 1;
}

static int source_compare(const obor_resource_source *source, uint32_t a, uint32_t b)
{
    const resource_member *left = source->members + a, *right = source->members + b;
    uint32_t count = left->name_length < right->name_length ? left->name_length : right->name_length;
    int compared = memcmp(source->directory + left->name, source->directory + right->name, count);
    if (compared) return compared;
    return (left->name_length > right->name_length) - (left->name_length < right->name_length);
}

static int source_sort(obor_resource_source *source)
{
    /* Deterministic bounded O(n log n), independent of path hashes or hostile
     * hash collisions. The extra index is released after construction. */
    for (uint32_t i = 0; i < source->count; ++i) source->order[i] = i;
    for (uint32_t width = 1; width < source->count; width *= 2) {
        for (uint32_t start = 0; start < source->count; start += 2 * width) {
            uint32_t middle = start + width, end = middle + width;
            if (middle > source->count) middle = source->count;
            if (end > source->count) end = source->count;
            uint32_t left = start, right = middle;
            for (uint32_t out = start; out < end; ++out) {
                if (left < middle && (right == end ||
                    source_compare(source, source->order[left], source->order[right]) <= 0))
                    source->temporary[out] = source->order[left++];
                else source->temporary[out] = source->order[right++];
            }
        }
        uint32_t *swap = source->order; source->order = source->temporary; source->temporary = swap;
    }
    for (uint32_t i = 1; i < source->count; ++i)
        if (!source_compare(source, source->order[i - 1], source->order[i])) return 0;
    return 1;
}

void obor_resource_source_destroy(obor_resource_source *source)
{
    if (!source) return;
    obor_resource_image_allocator allocator = source->allocator;
    allocator.release(source->directory);
    allocator.release(source->members);
    allocator.release(source->order);
    allocator.release(source->temporary);
    allocator.release(source);
}

obor_resource_source *obor_resource_source_create(const obor_resource_reader *reader,
        const obor_resource_image_allocator *allocator)
{
    if (!reader || !reader->read || !allocator || !allocator->allocate || !allocator->release ||
        reader->size < 12 || reader->size > UINT32_MAX) return NULL;
    unsigned char prefix[4], footer[4];
    if (!reader->read(reader->context, 0, prefix, 4) || memcmp(prefix, "PACK", 4) ||
        !reader->read(reader->context, reader->size - 4, footer, 4)) return NULL;
    uint32_t start = source_u32(footer);
    if (start < 8 || start >= reader->size - 4) return NULL;
    uint32_t size = (uint32_t)(reader->size - 4 - start);
    if (size > OBOR_RESOURCE_DIRECTORY_LIMIT) return NULL;
    obor_resource_source *source = allocator->allocate(sizeof(*source));
    if (!source) return NULL;
    memset(source, 0, sizeof(*source));
    source->allocator = *allocator;
    source->reader = *reader;
    source->directory = allocator->allocate(size);
    if (!source->directory || !reader->read(reader->context, start, source->directory, size)) goto fail;
    uint32_t at = 0;
    while (at < size) {
        if (size - at < 13 || source->count == OBOR_RESOURCE_MEMBER_LIMIT) goto fail;
        uint32_t length = source_u32(source->directory + at);
        if (length < 13 || length > OBOR_RESOURCE_PATH_LIMIT || length > size - at) goto fail;
        at += length;
        ++source->count;
    }
    source->members = allocator->allocate(source->count * sizeof(*source->members));
    source->order = allocator->allocate(source->count * sizeof(*source->order));
    source->temporary = allocator->allocate(source->count * sizeof(*source->temporary));
    if (!source->members || !source->order || !source->temporary) goto fail;
    at = 0;
    for (uint32_t i = 0; i < source->count; ++i) {
        const unsigned char *record = source->directory + at;
        uint32_t length = source_u32(record), offset = source_u32(record + 4), bytes = source_u32(record + 8);
        const unsigned char *end = memchr(record + 12, 0, length - 12);
        if (!end || offset < 8 || offset > start || bytes > start - offset) goto fail;
        size_t name_length = (size_t)(end - record - 12);
        char *name = (char *)source->directory + at + 12;
        if (!source_path(name, name, name_length)) goto fail;
        source->members[i] = (resource_member){at + 12, (uint32_t)name_length, offset, bytes};
        at += length;
    }
    if (!source_sort(source)) goto fail;
    allocator->release(source->temporary);
    source->temporary = NULL;
    return source;
fail:
    obor_resource_source_destroy(source);
    return NULL;
}

uint32_t obor_resource_source_count(const obor_resource_source *source)
{ return source ? source->count : 0; }

int obor_resource_source_find(const obor_resource_source *source, const char *name,
        size_t name_length, uint32_t *member, uint32_t *length)
{
    char normalized[OBOR_RESOURCE_PATH_LIMIT];
    if (!source || !name || !member || !length || !source_path(normalized, name, name_length)) return 0;
    uint32_t low = 0, high = source->count;
    while (low < high) {
        uint32_t middle = low + (high - low) / 2, index = source->order[middle];
        const resource_member *candidate = source->members + index;
        size_t n = name_length < candidate->name_length ? name_length : candidate->name_length;
        int compared = memcmp(normalized, source->directory + candidate->name, n);
        if (!compared) compared = (name_length > candidate->name_length) - (name_length < candidate->name_length);
        if (compared < 0) high = middle;
        else if (compared > 0) low = middle + 1;
        else { *member = index; *length = candidate->length; return 1; }
    }
    return 0;
}

int obor_resource_source_read(const obor_resource_source *source, uint32_t member,
        void *output, size_t capacity)
{
    if (!source || member >= source->count || !output) return 0;
    const resource_member *entry = source->members + member;
    if (capacity < entry->length) return 0;
    return source->reader.read(source->reader.context, entry->offset, output, entry->length);
}
