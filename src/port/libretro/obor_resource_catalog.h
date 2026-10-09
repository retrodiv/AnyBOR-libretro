/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_RESOURCE_CATALOG_H
#define OBOR_RESOURCE_CATALOG_H
#include "obor_resource_recipe.h"

#define OBOR_RESOURCE_CATALOG_LIMIT 65536U
#define OBOR_RESOURCE_STAGE_LIMIT (256U << 20)
#define OBOR_RESOURCE_MANIFEST_MAGIC UINT32_C(0x3143524f) /* ORC1 */
#define OBOR_RESOURCE_MANIFEST_HEADER 32U
#define OBOR_RESOURCE_MANIFEST_RECORD (16U + OBOR_RESOURCE_RECIPE_SIZE)

typedef struct obor_resource_catalog obor_resource_catalog;
typedef struct obor_resource_restore obor_resource_restore;
/* Proof since the last prepare/committed restore, including all threads and
 * allocation reuse. Return false whenever coverage or the epoch is uncertain.
 * Offsets are relative to the supplied arena, not the serialized stream. */
typedef int (*obor_resource_unchanged)(void *context, uint32_t offset, uint32_t length);

obor_resource_catalog *obor_resource_catalog_create(obor_resource_materializer *,
        const obor_resource_image_allocator *, void *arena, uint32_t arena_size);
void obor_resource_catalog_destroy(obor_resource_catalog *);
/* Caller must unregister BEFORE free and after every successful realloc,
 * including in-place realloc. An untracked replacement always remains raw. */
void obor_resource_catalog_remove(obor_resource_catalog *, uint32_t owner);
int obor_resource_catalog_add(obor_resource_catalog *, uint32_t owner, uint32_t allocation_size,
        uint32_t body, const obor_resource_recipe *);
uint64_t obor_resource_catalog_generation(const obor_resource_catalog *);
/* Native catalog writes explicitly stamp affected wire slots. This proves
 * unchanged entries since a successful capture of THIS catalog instance.
 * The caller must also prove the same logical mapping and invalidate its
 * saved generation when replacing/restoring a catalog or discarding a cache.
 * The mutable manifest header is always excluded. Only bounded per-slot
 * generation metadata is retained; no older manifest or resource payload. */
int obor_resource_catalog_manifest_unchanged(const obor_resource_catalog *,
        uint64_t previous_generation, uint32_t offset, uint32_t length);
void obor_resource_catalog_forget_proofs(obor_resource_catalog *);

/* Exact dirty comparison before omitting bytes. Records have stable slots;
 * empty slots are zero. At most256MiB of bodies can be omitted, bounding cold
 * reconstruction staging. Other bodies remain complete mutable state bytes.
 * Manifest pointer describes ONLY the current state; not a second history. */
int obor_resource_catalog_prepare(obor_resource_catalog *, uint32_t arena_used,
        obor_resource_unchanged, void *context);
const void *obor_resource_catalog_manifest(const obor_resource_catalog *, uint32_t *size);
/* Replace proven derived body ranges in an already copied logical heap span
 * with zeros. Never touches headers, palettes, pointers or allocation padding. */
void obor_resource_catalog_zero(const obor_resource_catalog *, uint32_t offset, void *, uint32_t length);
/* Read the prepared logical snapshot directly: copy ordinary bytes and write
 * zeros for verified omissions, without reading the omitted live bodies.
 * Output must not overlap the arena. Invalid bounds fail before writing. */
int obor_resource_catalog_read(const obor_resource_catalog *, uint32_t offset,
        void *output, uint32_t length);
/* Metadata for the CURRENT encoded image only, never another state/history.
 * A copied mask remains valid across live catalog creation/removal. Compare it
 * before reusing a dirty-page proof: unchanged memory with changed omission
 * coverage does not necessarily produce unchanged serialized bytes. */
typedef struct { uint32_t offset, length; } obor_resource_mask_range;
uint32_t obor_resource_catalog_mask_count(const obor_resource_catalog *);
int obor_resource_catalog_copy_mask(const obor_resource_catalog *,
        obor_resource_mask_range *output, uint32_t capacity);
int obor_resource_catalog_mask_unchanged(const obor_resource_catalog *,
        const obor_resource_mask_range *previous, uint32_t previous_count,
        uint32_t offset, uint32_t length);

/* Preflight all recipes and required bodies before touching any live bytes.
 * Every non-reusable body is reconstructed into bounded transient staging.
 * On failure the existing catalog/arena remains unchanged. Caller separately
 * validates the ordinary mutable snapshot and its allocation/span ownership. */
obor_resource_restore *obor_resource_restore_prepare(obor_resource_catalog *,
        const void *manifest, uint32_t manifest_size, uint32_t arena_used,
        obor_resource_unchanged, void *context);
/* Copy ordinary heap spans while preserving body holes; then fill staged
 * bodies and adopt the target catalog. Only call after ALL state preflights.
 * The source's logical omitted ranges must be zero and covered by the ordinary
 * snapshot, which the state adapter must validate before these commit calls. */
void obor_resource_restore_copy(const obor_resource_restore *, uint32_t offset,
        const void *source, uint32_t length);
obor_resource_catalog *obor_resource_restore_commit(obor_resource_restore *);
void obor_resource_restore_destroy(obor_resource_restore *);
size_t obor_resource_restore_staged(const obor_resource_restore *);
/* Access sorted omitted ranges for independent snapshot-span validation. */
uint32_t obor_resource_restore_count(const obor_resource_restore *);
int obor_resource_restore_range(const obor_resource_restore *, uint32_t index,
        uint32_t *offset, uint32_t *length);
/* Iterate stable slots, including raw entries. A zero return denotes an empty
 * slot. The adapter validates every recorded owner against snapshot allocator
 * metadata before adopting the catalog, not just currently omitted bodies. */
uint32_t obor_resource_restore_slots(const obor_resource_restore *);
int obor_resource_restore_allocation(const obor_resource_restore *, uint32_t slot,
        uint32_t *owner, uint32_t *allocation_size);
#endif
