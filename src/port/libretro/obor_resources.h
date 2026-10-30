/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_RESOURCES_H
#define OBOR_RESOURCES_H
#include "obor_resource_catalog.h"

/* Engine declarations, never inferred from object bytes or game identity.
 * This adapter owns native allocations and a private read-only source handle.
 * Unsupported content or proof failures leave all engine bytes in the state. */
void obor_resources_open(const char *content_path, int raw_directory);
void obor_resources_close(void);
void obor_resources_image_begin(void);
void obor_resources_image_opened(const char *member);
void obor_resources_bitmap_loaded(const void *bitmap, unsigned width, unsigned height);
/* Older engines physically compact a bitmap when clipping transparent edges.
 * They must declare the resulting crop; newer engines pass their crop directly
 * to sprite_encoded. Invalid or unknown provenance always falls back to raw. */
void obor_resources_bitmap_cropped(const void *bitmap, unsigned left, unsigned top,
        unsigned width, unsigned height);
void obor_resources_sprite_encoded(const void *bitmap, void *owner, void *body,
        size_t length, unsigned x, unsigned y, unsigned width, unsigned height);
/* Successful exact member read, e.g. a PCM sample payload. The member offset
 * is relative to that member, not the archive; allocation tails and mixer
 * state stay raw. Unknown origins and mismatches preserve complete bytes. */
void obor_resources_member_bytes_loaded(const char *member, uint32_t member_offset,
        void *owner, void *body, size_t length);
/* Invoke before free or after successful realloc, even at the same address. */
void obor_resources_forget_owner(const void *owner);
size_t obor_allocation_size(const void *owner);
/* Check an interior reference against live chunks without reading metadata
 * at the supplied address. Zero bytes and unsupported heap layouts refuse. */
int obor_allocation_contains(const void *address, size_t length);
/* Called from the video backend immediately before capture. A missing or
 * unsupported source removes only the conditional output-copy declaration. */
void obor_resources_framebuffer(void *frame, const void *source_owner,
        const void *source_pixels, uint32_t width, uint32_t height);

obor_resource_catalog *obor_resources_catalog(void);
/* Serialized-target preflight may run while current movie workers are alive.
 * The native registry/cache are locked against their free hooks. Pass NULL
 * for unchanged in that case: no current engine body may be reused. This
 * neither joins workers nor writes the arena; commit/adopt requires them joined. */
obor_resource_restore *obor_resources_prepare_restore(const void *manifest,
        uint32_t size, uint32_t arena_used, obor_resource_unchanged unchanged,
        void *context, int empty_cache);
obor_resource_restore *obor_resources_prepare_restore_snapshot(const void *manifest,
        uint32_t size, uint32_t arena_used, obor_resource_unchanged unchanged,
        void *context, int empty_cache, obor_resource_snapshot_read, void *snapshot);
/* After a complete state restore: discard bitmap provenance from the future,
 * adopt the target catalog. Its checked bodies describe the committed target;
 * callers may use them only after establishing a new write-watch epoch.
 * A raw state supplies NULL and clears the catalog without touching the cache. */
void obor_resources_adopt(obor_resource_catalog *target);
/* Test control for a genuinely empty derived cache before a cold restore. */
void obor_resources_clear_cache(void);
#endif
