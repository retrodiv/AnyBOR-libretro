/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef _FILE_OFFSET_BITS
#define _FILE_OFFSET_BITS 64
#endif
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#include "obor_resources.h"
#include "obor_runtime.h"
#include "obor_state_config.h"
#include "obor_abi.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>

extern void *__real_malloc(size_t);
extern void __real_free(void *);
extern FILE *__real_fopen(const char *, const char *);
extern int __real_fclose(FILE *);
#if defined(__linux__)
extern size_t __real_fread(void *, size_t, size_t, FILE *);
#define resource_read __real_fread
#else
#define resource_read fread
#endif
#if defined(_WIN32)
#define resource_seek _fseeki64
#define resource_tell _ftelli64
#else
#define resource_seek fseeko
#define resource_tell ftello
#endif
char *obor_arena_base(void);
size_t obor_allocation_size(const void *);

/* The table holds only provenance for live bitmaps, not their pixels. Full
 * tables safely reject new candidates. Free/realloc/reset/load invalidate it. */
#define RESOURCE_BITMAP_LIMIT 4096U
#define RESOURCE_BITMAP_EMPTY UINT32_MAX
#define RESOURCE_BITMAP_DELETED (UINT32_MAX - 1U)
typedef struct {
    uint32_t owner, width, height;
    uint32_t left, top, current_width, current_height;
    char name[OBOR_RESOURCE_RECIPE_PATH];
} resource_bitmap;
typedef struct {
    pthread_mutex_t mutex;
    int mutex_ready;
    FILE *file;
    obor_resource_source *source;
    obor_resource_materializer *materializer;
    obor_resource_catalog *catalog;
    resource_bitmap bitmaps[RESOURCE_BITMAP_LIMIT];
    char opened[OBOR_RESOURCE_RECIPE_PATH];
} resource_context;
static resource_context *resources OBOR_RUNTIME;
static const obor_resource_image_allocator resource_allocator = {__real_malloc, __real_free};

/* Playback workers also free arena allocations. Protect their ownership
 * lookups against main-thread registry growth; no engine allocation occurs
 * while this native mutex is held. Captures and restoration writes require
 * joined workers; source-only restore preflight takes this mutex too. Teardown
 * joins workers before releasing this context. */
static void resource_lock(void)
{ if (pthread_mutex_lock(&resources->mutex)) abort(); }
static void resource_unlock(void)
{ if (pthread_mutex_unlock(&resources->mutex)) abort(); }

static int resource_offset(const void *p, uint32_t *offset)
{
    uintptr_t address = (uintptr_t)p, base = (uintptr_t)obor_arena_base();
    if (!p || address < base || address - base >= OBOR_ARENA_MAX_SZ) return 0;
    *offset = (uint32_t)(address - base); return 1;
}
static resource_bitmap *resource_bitmap_find(uint32_t owner, int insert)
{
    uint32_t start = (owner >> 4) * UINT32_C(2654435761);
    resource_bitmap *deleted = NULL;
    for (uint32_t n = 0; n < RESOURCE_BITMAP_LIMIT; ++n) {
        resource_bitmap *b = resources->bitmaps + ((start + n) & (RESOURCE_BITMAP_LIMIT - 1U));
        if (b->owner == owner) return b;
        if (b->owner == RESOURCE_BITMAP_DELETED && !deleted) deleted = b;
        if (b->owner == RESOURCE_BITMAP_EMPTY) return insert ? (deleted ? deleted : b) : NULL;
    }
    return insert ? deleted : NULL;
}
static void resource_clear_bitmaps(void)
{
    for (unsigned i = 0; i < RESOURCE_BITMAP_LIMIT; ++i)
        resources->bitmaps[i].owner = RESOURCE_BITMAP_EMPTY;
    resources->opened[0] = 0;
}
static int resource_read_at(void *opaque, uint64_t offset, void *out, size_t length)
{
    FILE *file = opaque;
    return offset <= INT64_MAX && !resource_seek(file, (int64_t)offset, SEEK_SET) &&
        resource_read(out, 1, length, file) == length;
}

void obor_resources_close(void)
{
    if (!resources) return;
    obor_resource_catalog_destroy(resources->catalog);
    obor_resource_materializer_destroy(resources->materializer);
    obor_resource_source_destroy(resources->source);
    if (resources->file) __real_fclose(resources->file);
    if (resources->mutex_ready) pthread_mutex_destroy(&resources->mutex);
    __real_free(resources); resources = NULL;
}
void obor_resources_open(const char *path, int raw_directory)
{
    obor_resources_close();
    if (!path || raw_directory || !obor_state_resources_enabled()) return;
    resources = __real_malloc(sizeof(*resources));
    if (!resources) return;
    memset(resources, 0, sizeof(*resources));
    if (pthread_mutex_init(&resources->mutex, NULL)) goto fail;
    resources->mutex_ready = 1;
    resource_clear_bitmaps();
    resources->file = __real_fopen(path, "rb");
    if (!resources->file || resource_seek(resources->file, 0, SEEK_END)) goto fail;
    int64_t size = resource_tell(resources->file);
    if (size < 0) goto fail;
    const obor_resource_reader reader = {resources->file, (uint64_t)size, resource_read_at};
    resources->source = obor_resource_source_create(&reader, &resource_allocator);
    if (!resources->source) goto fail;
    resources->materializer = obor_resource_materializer_create(resources->source,
        &resource_allocator, OBOR_RESOURCE_CACHE_LIMIT);
    if (!resources->materializer) goto fail;
    resources->catalog = obor_resource_catalog_create(resources->materializer,
        &resource_allocator, obor_arena_base(), OBOR_ARENA_MAX_SZ);
    if (!resources->catalog) goto fail;
    return;
fail:
    obor_resources_close();
}
void obor_resources_image_begin(void)
{ if (resources) { resource_lock(); resources->opened[0] = 0; resource_unlock(); } }
void obor_resources_image_opened(const char *member)
{
    if (!resources) return;
    resource_lock();
    resources->opened[0] = 0;
    if (member) {
        size_t length = strlen(member);
        if (length && length < sizeof(resources->opened)) memcpy(resources->opened, member, length + 1);
    }
    resource_unlock();
}
void obor_resources_bitmap_loaded(const void *bitmap, unsigned width, unsigned height)
{
    uint32_t offset;
    if (!resources || !resource_offset(bitmap, &offset)) return;
    resource_lock();
    resource_bitmap *b = resource_bitmap_find(offset, 1);
    if (!b) goto done;
    /* Clear a previous binding even when this load has no usable source. */
    b->owner = RESOURCE_BITMAP_DELETED;
    if (!width || !height || !resources->opened[0]) goto done;
    b->owner = offset; b->width = width; b->height = height;
    b->left = b->top = 0;
    b->current_width = width; b->current_height = height;
    memcpy(b->name, resources->opened, sizeof(b->name));
done:
    resource_unlock();
}
void obor_resources_bitmap_cropped(const void *bitmap, unsigned left, unsigned top,
        unsigned width, unsigned height)
{
    uint32_t offset;
    if (!resources || !resource_offset(bitmap, &offset)) return;
    resource_lock();
    resource_bitmap *b = resource_bitmap_find(offset, 0);
    if (!b) goto done;
    if (!width || !height || left > b->current_width || top > b->current_height ||
        width > b->current_width - left || height > b->current_height - top) {
        b->owner = RESOURCE_BITMAP_DELETED;
        goto done;
    }
    /* Each step stays inside its previously checked source rectangle. */
    b->left += left; b->top += top;
    b->current_width = width; b->current_height = height;
done:
    resource_unlock();
}
void obor_resources_forget_owner(const void *owner)
{
    uint32_t offset;
    if (!resources || !resource_offset(owner, &offset)) return;
    resource_lock();
    obor_resource_catalog_remove(resources->catalog, offset);
    resource_bitmap *b = resource_bitmap_find(offset, 0);
    if (b) b->owner = RESOURCE_BITMAP_DELETED;
    resource_unlock();
}
void obor_resources_sprite_encoded(const void *bitmap, void *owner, void *body,
        size_t length, unsigned x, unsigned y, unsigned width, unsigned height)
{
    uint32_t bitmap_offset, owner_offset, body_offset;
    if (!resources || !resource_offset(owner, &owner_offset)) return;
    resource_lock();
    obor_resource_catalog_remove(resources->catalog, owner_offset);
    if (!resource_offset(bitmap, &bitmap_offset) || !resource_offset(body, &body_offset) ||
        !length || length > OBOR_RESOURCE_BODY_LIMIT) goto done;
    resource_bitmap *b = resource_bitmap_find(bitmap_offset, 0);
    if (!b) goto done;
    if (x > b->current_width || y > b->current_height ||
        width > b->current_width - x || height > b->current_height - y) goto done;
    size_t allocation = obor_allocation_size(owner);
    if (!allocation || allocation > UINT32_MAX || body_offset < owner_offset ||
        body_offset - owner_offset > allocation || length > allocation - (body_offset - owner_offset)) goto done;
    obor_resource_recipe recipe;
    if (!obor_resource_recipe_prove(resources->materializer, &recipe, b->name, strlen(b->name),
        b->width, b->height, b->left + x, b->top + y, width, height, body, length)) goto done;
    obor_resource_catalog_add(resources->catalog, owner_offset, (uint32_t)allocation, body_offset, &recipe);
done:
    resource_unlock();
}
void obor_resources_member_bytes_loaded(const char *member, uint32_t member_offset,
        void *owner, void *body, size_t length)
{
    uint32_t owner_offset, body_offset;
    if (!resources || !resource_offset(owner, &owner_offset)) return;
    resource_lock();
    obor_resource_catalog_remove(resources->catalog, owner_offset);
    if (!member || !resource_offset(body, &body_offset) ||
        !length || length > OBOR_RESOURCE_BODY_LIMIT) goto done;
    size_t allocation = obor_allocation_size(owner);
    if (!allocation || allocation > UINT32_MAX || body_offset < owner_offset ||
        body_offset - owner_offset > allocation || length > allocation - (body_offset - owner_offset)) goto done;
    obor_resource_recipe recipe;
    if (!obor_resource_recipe_prove_bytes(resources->materializer, &recipe, member, strlen(member),
        member_offset, body, length)) goto done;
    obor_resource_catalog_add(resources->catalog, owner_offset, (uint32_t)allocation, body_offset, &recipe);
done:
    resource_unlock();
}

obor_resource_catalog *obor_resources_catalog(void)
{ return resources ? resources->catalog : NULL; }
obor_resource_restore *obor_resources_prepare_restore(const void *manifest,
        uint32_t size, uint32_t used, obor_resource_unchanged unchanged,
        void *context, int empty_cache)
{
    if (!resources) return NULL;
    resource_lock();
    if (empty_cache) {
        obor_resource_materializer_clear(resources->materializer);
        obor_resource_catalog_forget_proofs(resources->catalog);
        unchanged = NULL;
    }
    obor_resource_restore *plan = obor_resource_restore_prepare(resources->catalog,
        manifest, size, used, unchanged, context);
    resource_unlock();
    return plan;
}
void obor_resources_adopt(obor_resource_catalog *target)
{
    if (!resources) { obor_resource_catalog_destroy(target); return; }
    resource_clear_bitmaps();
    obor_resource_catalog_destroy(resources->catalog);
    resources->catalog = target ? target : obor_resource_catalog_create(resources->materializer,
        &resource_allocator, obor_arena_base(), OBOR_ARENA_MAX_SZ);
}
void obor_resources_clear_cache(void)
{
    if (!resources) return;
    resource_lock();
    obor_resource_materializer_clear(resources->materializer);
    obor_resource_catalog_forget_proofs(resources->catalog);
    resource_unlock();
}
