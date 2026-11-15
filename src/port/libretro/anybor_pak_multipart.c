/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#if OBOR_ENGINE_BUILD == 6391
/* The explicit stdio helper enforces wide offsets. Global LFS redirects
 * would bypass the engine's session-bound fopen wrapper on Linux. */
#include <limits.h>
#include "anybor_pak_volumes.h"
#include "anybor_pak_multipart.h"

typedef struct {
    const unsigned char *record;
    unsigned volume, order;
} obor_multipart_entry;
typedef struct {
    const obor_multipart_entry *entry;
    uint32_t position;
    unsigned char *cache;
    uint32_t cache_start, cache_bytes;
} obor_multipart_handle;
#define OBOR_MULTIPART_READAHEAD 65536u
static obor_pak_volumes multipart;
static obor_multipart_entry *index_entries;
static obor_multipart_handle handles[8];

static int compare_entries(const void *a, const void *b)
{
    const obor_multipart_entry *left = (const obor_multipart_entry *)a;
    const obor_multipart_entry *right = (const obor_multipart_entry *)b;
    int result = obor_pak_name_compare((const char *)left->record + 12,
        (const char *)right->record + 12);
    /* Preserve native first-volume/first-record precedence for aliases. */
    return result ? result : (left->order > right->order) - (left->order < right->order);
}
int obor_multipart_active(void) { return multipart.count != 0; }
void obor_multipart_closeall(void)
{
    unsigned h;
    for (h = 0; h < sizeof(handles) / sizeof(handles[0]); ++h) free(handles[h].cache);
    memset(handles, 0, sizeof(handles));
}
void obor_multipart_rebind(const char *path)
{
    unsigned v;
    for (v = 0; v < multipart.count; ++v) {
        char *target = multipart.volumes[v].path;
        int written = v ? snprintf(target, sizeof(multipart.volumes[v].path), "%s.%03u", path, v) :
            snprintf(target, sizeof(multipart.volumes[v].path), "%s", path);
        if (written < 0 || (size_t)written >= sizeof(multipart.volumes[v].path)) target[0] = 0;
    }
    for (v = 0; v < sizeof(handles) / sizeof(handles[0]); ++v) handles[v].cache_bytes = 0;
}
void obor_multipart_term(void)
{
    obor_multipart_closeall();
    free(index_entries); index_entries = NULL;
    obor_pak_volumes_close(&multipart);
}
int obor_multipart_init(const char *path)
{
    FILE *file;
    unsigned char header[8];
    unsigned v, count = 0;
    if (multipart.count) return obor_pak_name_compare(path, multipart.volumes[0].path) ? -1 : 1;
    file = fopen(path, "rb");
    if (!file) return 0; /* Preserve loose-content/ordinary reader handling. */
    v = fread(header, 1, sizeof(header), file) == sizeof(header) &&
        !memcmp(header, "PACK", 4) && obor_volume_u32(header + 4) == 0x00010100u;
    fclose(file);
    if (!v) return 0;
    if (obor_pak_volumes_open(&multipart, path)) return -1;
    index_entries = (obor_multipart_entry *)malloc((multipart.entries ? multipart.entries : 1) * sizeof(*index_entries));
    if (!index_entries) { obor_multipart_term(); return -1; }
    for (v = 0; v < multipart.count; ++v) {
        const obor_pak_volume *volume = &multipart.volumes[v];
        uint32_t position;
        for (position = 0; position < volume->bytes;) {
            obor_multipart_entry *entry = &index_entries[count];
            entry->record = volume->directory + position;
            entry->volume = v; entry->order = count++;
            position += obor_volume_u32(entry->record);
        }
    }
    qsort(index_entries, count, sizeof(*index_entries), compare_entries);
    return 1;
}
int obor_multipart_open(const char *name)
{
    unsigned low = 0, high = multipart.entries, h;
    while (low < high) {
        unsigned middle = low + (high - low) / 2;
        if (obor_pak_name_compare((const char *)index_entries[middle].record + 12, name) < 0) low = middle + 1;
        else high = middle;
    }
    if (low == multipart.entries || obor_pak_name_compare((const char *)index_entries[low].record + 12, name) ||
        obor_volume_u32(index_entries[low].record + 8) > INT_MAX) return -1;
    for (h = 0; h < sizeof(handles) / sizeof(handles[0]); ++h) if (!handles[h].entry) {
        handles[h].entry = &index_entries[low]; handles[h].position = 0;
        return (int)h;
    }
    return -1;
}
static obor_multipart_handle *get_handle(int h)
{
    return h >= 0 && h < (int)(sizeof(handles) / sizeof(handles[0])) && handles[h].entry ? &handles[h] : NULL;
}
int obor_multipart_read(int h, void *data, int bytes)
{
    obor_multipart_handle *handle = get_handle(h);
    const unsigned char *record;
    uint32_t remaining;
    int total = 0;
    if (!handle || bytes < 0 || (!data && bytes)) return -1;
    record = handle->entry->record;
    remaining = obor_volume_u32(record + 8) - handle->position;
    if ((uint32_t)bytes > remaining) bytes = (int)remaining;
    if (!bytes) return 0;
    if (!handle->cache) handle->cache = (unsigned char *)malloc(OBOR_MULTIPART_READAHEAD);
    if (!handle->cache) return -1;
    while (total < bytes) {
        uint32_t available, take;
        if (!handle->cache_bytes || handle->position < handle->cache_start ||
            handle->position - handle->cache_start >= handle->cache_bytes) {
            FILE *file;
            uint32_t amount = obor_volume_u32(record + 8) - handle->position;
            size_t read_bytes;
            int error;
            if (amount > OBOR_MULTIPART_READAHEAD) amount = OBOR_MULTIPART_READAHEAD;
            /* No OS handle survives a call. The bounded cache and positions
             * belong to normal arena/BSS state. Tiny GIF/parser reads reuse
             * these bytes; reset/rewind cannot revive a captured FILE/fd. */
            file = fopen(multipart.volumes[handle->entry->volume].path, "rb");
            if (!file) return total ? total : -1;
            if (obor_file_seek64(file, (int64_t)obor_volume_u32(record + 4) + handle->position, SEEK_SET)) {
                fclose(file); return total ? total : -1;
            }
            read_bytes = fread(handle->cache, 1, amount, file);
            error = ferror(file);
            fclose(file);
            handle->cache_start = handle->position;
            handle->cache_bytes = (uint32_t)read_bytes;
            if (!read_bytes) return total ? total : error ? -1 : 0;
        }
        available = handle->cache_bytes - (handle->position - handle->cache_start);
        take = (uint32_t)(bytes - total);
        if (take > available) take = available;
        memcpy((unsigned char *)data + total, handle->cache + (handle->position - handle->cache_start), take);
        handle->position += take;
        total += (int)take;
    }
    return total;
}
int obor_multipart_seek(int h, int offset, int origin)
{
    obor_multipart_handle *handle = get_handle(h);
    uint32_t size;
    int64_t position;
    if (!handle) return -1;
    size = obor_volume_u32(handle->entry->record + 8);
    if (origin == SEEK_SET) position = offset;
    else if (origin == SEEK_CUR) position = (int64_t)handle->position + offset;
    else if (origin == SEEK_END) position = (int64_t)size + offset;
    else return -1;
    handle->position = position < 0 ? 0 : position > size ? size : (uint32_t)position;
    return (int)handle->position;
}
int obor_multipart_close(int h)
{
    obor_multipart_handle *handle = get_handle(h);
    if (!handle) return -1;
    free(handle->cache);
    memset(handle, 0, sizeof(*handle));
    return 0;
}
#endif
