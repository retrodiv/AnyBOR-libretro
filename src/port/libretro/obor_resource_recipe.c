/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include "obor_resource_recipe.h"
#include "lz4.h"
#define OBOR_SHA256_STREAM_ONLY
#include "obor_sha256.h"
#include <string.h>

#define RECIPE_BUCKETS 4096U
typedef struct recipe_cache {
    struct recipe_cache *previous, *next, *bucket_next;
    uint32_t stored;
    int compressed;
    obor_resource_recipe recipe;
    unsigned char body[];
} recipe_cache;
struct obor_resource_materializer {
    const obor_resource_source *source;
    obor_resource_image_allocator allocator;
    recipe_cache *first, *last, *buckets[RECIPE_BUCKETS];
    size_t cached, limit;
    unsigned char *pixels, *temporary;
    size_t temporary_capacity;
};

/* One reusable source-derived workspace, never an engine image or history.
 * Release before growing so even a failed allocation keeps the same bound. */
static unsigned char *recipe_temporary(obor_resource_materializer *m, size_t size)
{
    if (!size || size > OBOR_RESOURCE_BODY_LIMIT) return NULL;
    if (size <= m->temporary_capacity) return m->temporary;
    m->allocator.release(m->temporary); m->temporary = NULL;
    m->temporary_capacity = 0;
    m->temporary = m->allocator.allocate(size);
    if (m->temporary) m->temporary_capacity = size;
    return m->temporary;
}

static uint32_t recipe_u32(const unsigned char *p)
{ return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24; }
static void recipe_put(unsigned char *p, uint32_t value)
{ for (unsigned i = 0; i < 4; ++i) p[i] = (unsigned char)(value >> (i * 8)); }

static int recipe_name(char *out, const char *name, size_t n)
{
    if (!name || !n || n >= OBOR_RESOURCE_RECIPE_PATH) return 0;
    size_t component = 0;
    for (size_t i = 0; i <= n; ++i) {
        unsigned char c = i == n ? '/' : (unsigned char)name[i];
        if (c == '\\') c = '/';
        if (!c || c == ':') return 0;
        if (c == '/') {
            size_t length = i - component;
            if (!length || (length == 1 && name[component] == '.') ||
                (length == 2 && name[component] == '.' && name[component + 1] == '.')) return 0;
            component = i + 1;
        }
        if (i < n) out[i] = (char)(c >= 'A' && c <= 'Z' ? c + 'a' - 'A' : c);
    }
    memset(out + n, 0, OBOR_RESOURCE_RECIPE_PATH - n);
    return 1;
}

int obor_resource_recipe_valid(const obor_resource_recipe *r)
{
    if (!r || r->version != 2 || !r->length || r->length > OBOR_RESOURCE_BODY_LIMIT) return 0;
    if (r->kind == OBOR_RESOURCE_RLE8) {
        if (r->member_offset || !r->source_width || !r->source_height ||
            r->source_width > OBOR_RESOURCE_IMAGE_DIMENSION || r->source_height > OBOR_RESOURCE_IMAGE_DIMENSION ||
            (uint64_t)r->source_width * r->source_height > OBOR_RESOURCE_IMAGE_PIXELS ||
            r->x >= r->source_width || r->y >= r->source_height || !r->width || !r->height ||
            r->width > r->source_width - r->x || r->height > r->source_height - r->y) return 0;
    } else if (r->kind == OBOR_RESOURCE_MEMBER_BYTES) {
        if (r->source_width || r->source_height || r->x || r->y || r->width || r->height ||
            r->member_offset > OBOR_RESOURCE_IMAGE_INPUT ||
            r->length > OBOR_RESOURCE_IMAGE_INPUT - r->member_offset) return 0;
    } else return 0;
    const char *end = memchr(r->name, 0, sizeof(r->name));
    char normalized[OBOR_RESOURCE_RECIPE_PATH];
    return end && recipe_name(normalized, r->name, (size_t)(end - r->name)) &&
        !memcmp(normalized, r->name, sizeof(normalized));
}

int obor_resource_recipe_equal(const obor_resource_recipe *a, const obor_resource_recipe *b)
{
    return a && b && a->version == b->version && a->kind == b->kind &&
        a->member_offset == b->member_offset && a->source_width == b->source_width &&
        a->source_height == b->source_height && a->x == b->x && a->y == b->y &&
        a->width == b->width && a->height == b->height && a->length == b->length &&
        !memcmp(a->digest, b->digest, sizeof(a->digest)) && !memcmp(a->name, b->name, sizeof(a->name));
}

int obor_resource_recipe_write(const obor_resource_recipe *r, void *output, size_t size)
{
    if (!output || size != OBOR_RESOURCE_RECIPE_SIZE || !obor_resource_recipe_valid(r)) return 0;
    unsigned char *p = output;
    const uint32_t fields[10] = {r->version, r->source_width, r->source_height,
        r->x, r->y, r->width, r->height, r->length, r->kind, r->member_offset};
    for (unsigned i = 0; i < 10; ++i) recipe_put(p + i * 4, fields[i]);
    memcpy(p + 40, r->digest, 32);
    memcpy(p + 72, r->name, OBOR_RESOURCE_RECIPE_PATH);
    return 1;
}

int obor_resource_recipe_read(obor_resource_recipe *r, const void *input, size_t size)
{
    if (!r || !input || size != OBOR_RESOURCE_RECIPE_SIZE) return 0;
    const unsigned char *p = input;
    obor_resource_recipe candidate;
    memset(&candidate, 0, sizeof(candidate));
    candidate.version = recipe_u32(p); candidate.source_width = recipe_u32(p + 4);
    candidate.source_height = recipe_u32(p + 8); candidate.x = recipe_u32(p + 12);
    candidate.y = recipe_u32(p + 16); candidate.width = recipe_u32(p + 20);
    candidate.height = recipe_u32(p + 24); candidate.length = recipe_u32(p + 28);
    candidate.kind = recipe_u32(p + 32); candidate.member_offset = recipe_u32(p + 36);
    memcpy(candidate.digest, p + 40, 32);
    memcpy(candidate.name, p + 72, OBOR_RESOURCE_RECIPE_PATH);
    if (!obor_resource_recipe_valid(&candidate)) return 0;
    *r = candidate;
    return 1;
}

static uint32_t recipe_bucket(const obor_resource_recipe *r)
{
    /* Distribution only; all hits require full key equality below. */
    return (recipe_u32(r->digest) ^ r->x ^ (r->y << 5) ^ (r->width << 10) ^ r->height ^
        r->kind ^ r->member_offset ^ r->length) % RECIPE_BUCKETS;
}

static void recipe_unlink(obor_resource_materializer *m, recipe_cache *entry)
{
    if (entry->previous) entry->previous->next = entry->next; else m->first = entry->next;
    if (entry->next) entry->next->previous = entry->previous; else m->last = entry->previous;
}

static void recipe_recent(obor_resource_materializer *m, recipe_cache *entry)
{
    entry->previous = NULL; entry->next = m->first;
    if (m->first) m->first->previous = entry; else m->last = entry;
    m->first = entry;
}

static void recipe_evict(obor_resource_materializer *m)
{
    recipe_cache *entry = m->last;
    if (!entry) return;
    recipe_unlink(m, entry);
    recipe_cache **at = &m->buckets[recipe_bucket(&entry->recipe)];
    while (*at && *at != entry) at = &(*at)->bucket_next;
    if (*at) *at = entry->bucket_next;
    m->cached -= sizeof(*entry) + entry->stored;
    m->allocator.release(entry);
}

void obor_resource_materializer_clear(obor_resource_materializer *m)
{
    if (!m) return;
    while (m->last) recipe_evict(m);
    m->allocator.release(m->temporary); m->temporary = NULL;
    m->temporary_capacity = 0;
}

void obor_resource_materializer_destroy(obor_resource_materializer *m)
{
    if (!m) return;
    obor_resource_materializer_clear(m);
    m->allocator.release(m->pixels);
    m->allocator.release(m);
}

obor_resource_materializer *obor_resource_materializer_create(const obor_resource_source *source,
        const obor_resource_image_allocator *allocator, size_t limit)
{
    if (!source || !allocator || !allocator->allocate || !allocator->release || limit > OBOR_RESOURCE_CACHE_LIMIT)
        return NULL;
    obor_resource_materializer *m = allocator->allocate(sizeof(*m));
    if (!m) return NULL;
    memset(m, 0, sizeof(*m));
    m->source = source; m->allocator = *allocator; m->limit = limit;
    return m;
}

size_t obor_resource_materializer_cached(const obor_resource_materializer *m)
{ return m ? m->cached : 0; }

static const unsigned char *recipe_load(obor_resource_materializer *m, obor_resource_recipe *r, int proving)
{
    uint32_t member, length;
    size_t name_length = strlen(r->name);
    if (!obor_resource_source_find(m->source, r->name, name_length, &member, &length) ||
        !length || length > OBOR_RESOURCE_IMAGE_INPUT) return NULL;
    unsigned char *file = m->allocator.allocate(length);
    if (!file) return NULL;
    unsigned char digest[32];
    int valid = obor_resource_source_read(m->source, member, file, length);
    if (valid) {
        obor_sha256_ctx hash;
        obor_sha256_init(&hash); obor_sha256_update(&hash, file, length); obor_sha256_final(&hash, digest);
        if (!proving && memcmp(digest, r->digest, sizeof(digest))) valid = 0;
    }
    if (r->kind == OBOR_RESOURCE_MEMBER_BYTES) {
        valid = valid && r->member_offset <= length && r->length <= length - r->member_offset;
        if (valid) {
            valid = recipe_temporary(m, r->length) != NULL;
            if (valid) memcpy(m->temporary, file + r->member_offset, r->length);
        }
        m->allocator.release(file);
        if (!valid) return NULL;
        if (proving) memcpy(r->digest, digest, sizeof(digest));
        return m->temporary;
    }
    if (valid && !m->pixels) m->pixels = m->allocator.allocate(OBOR_RESOURCE_IMAGE_PIXELS);
    uint32_t width = 0, height = 0;
    if (valid) valid = m->pixels && obor_resource_image_decode(file, length, m->pixels,
            OBOR_RESOURCE_IMAGE_PIXELS, &width, &height, &m->allocator);
    m->allocator.release(file);
    if (!valid || width != r->source_width || height != r->source_height) return NULL;
    const unsigned char *crop = m->pixels + (size_t)r->y * width + r->x;
    size_t bytes = obor_resource_image_rle8(crop, r->width, r->height, width, NULL, 0);
    if (bytes != r->length || bytes > OBOR_RESOURCE_BODY_LIMIT) return NULL;
    if (!recipe_temporary(m, bytes)) return NULL;
    if (obor_resource_image_rle8(crop, r->width, r->height, width, m->temporary, bytes) != bytes) {
        return NULL;
    }
    if (proving) memcpy(r->digest, digest, sizeof(digest));
    return m->temporary;
}

static const void *recipe_keep(obor_resource_materializer *m, const obor_resource_recipe *r)
{
    if (m->limit <= sizeof(recipe_cache)) return m->temporary;
    /* Compact only immutable, independently reconstructed data. This cache
     * has no snapshot age or engine allocation payload. Misses still rebuild
     * from the complete recipe, including when the cache is deliberately empty. */
    int capacity = LZ4_compressBound((int)r->length);
    unsigned char *packed = capacity > 0 ? m->allocator.allocate((size_t)capacity) : NULL;
    int n = packed ? LZ4_compress_default((const char *)m->temporary, (char *)packed,
        (int)r->length, capacity) : 0;
    int compressed = n > 0 && (uint32_t)n < r->length;
    uint32_t stored = compressed ? (uint32_t)n : r->length;
    size_t bytes = sizeof(recipe_cache) + stored;
    if (bytes > m->limit) { m->allocator.release(packed); return m->temporary; }
    while (m->cached > m->limit - bytes) recipe_evict(m);
    recipe_cache *entry = m->allocator.allocate(bytes);
    if (!entry) { m->allocator.release(packed); return m->temporary; }
    memset(entry, 0, sizeof(*entry)); entry->recipe = *r;
    entry->stored = stored; entry->compressed = compressed;
    memcpy(entry->body, compressed ? packed : m->temporary, stored);
    m->allocator.release(packed);
    uint32_t bucket = recipe_bucket(r);
    entry->bucket_next = m->buckets[bucket]; m->buckets[bucket] = entry;
    recipe_recent(m, entry); m->cached += bytes;
    return compressed ? m->temporary : entry->body;
}

const void *obor_resource_recipe_body(obor_resource_materializer *m, const obor_resource_recipe *r)
{
    if (!m || !obor_resource_recipe_valid(r)) return NULL;
    for (recipe_cache *entry = m->buckets[recipe_bucket(r)]; entry; entry = entry->bucket_next)
        if (obor_resource_recipe_equal(&entry->recipe, r)) {
            recipe_unlink(m, entry); recipe_recent(m, entry);
            if (entry->compressed) {
                if (!recipe_temporary(m, r->length)) return NULL;
                if (LZ4_decompress_safe((const char *)entry->body, (char *)m->temporary,
                    (int)entry->stored, (int)r->length) != (int)r->length) {
                    return NULL;
                }
                return m->temporary;
            }
            return entry->body;
        }
    obor_resource_recipe work = *r;
    if (!recipe_load(m, &work, 0)) return NULL;
    return recipe_keep(m, r);
}

static int recipe_prove(obor_resource_materializer *m, obor_resource_recipe *output,
        obor_resource_recipe r, const char *name, size_t name_length,
        const void *body, size_t body_length)
{
    if (!m || !output || !body || !body_length || body_length > OBOR_RESOURCE_BODY_LIMIT) return 0;
    r.version = 2; r.length = (uint32_t)body_length;
    if (!recipe_name(r.name, name, name_length) || !obor_resource_recipe_valid(&r)) return 0;
    const unsigned char *candidate = recipe_load(m, &r, 1);
    if (!candidate || memcmp(candidate, body, body_length)) return 0;
    *output = r;
    /* Do not duplicate an existing shared-resource cache entry. */
    for (recipe_cache *entry = m->buckets[recipe_bucket(&r)]; entry; entry = entry->bucket_next)
        if (obor_resource_recipe_equal(&entry->recipe, &r)) {
            recipe_unlink(m, entry); recipe_recent(m, entry);
            return 1;
        }
    (void)recipe_keep(m, &r);
    return 1;
}

int obor_resource_recipe_prove(obor_resource_materializer *m, obor_resource_recipe *output,
        const char *name, size_t name_length, uint32_t source_width, uint32_t source_height,
        uint32_t x, uint32_t y, uint32_t width, uint32_t height, const void *body, size_t body_length)
{
    obor_resource_recipe r;
    memset(&r, 0, sizeof(r)); r.kind = OBOR_RESOURCE_RLE8;
    r.source_width = source_width; r.source_height = source_height;
    r.x = x; r.y = y; r.width = width; r.height = height;
    return recipe_prove(m, output, r, name, name_length, body, body_length);
}

int obor_resource_recipe_prove_bytes(obor_resource_materializer *m, obor_resource_recipe *output,
        const char *name, size_t name_length, uint32_t member_offset,
        const void *body, size_t body_length)
{
    obor_resource_recipe r;
    memset(&r, 0, sizeof(r)); r.kind = OBOR_RESOURCE_MEMBER_BYTES;
    r.member_offset = member_offset;
    return recipe_prove(m, output, r, name, name_length, body, body_length);
}
