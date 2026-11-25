/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PAK_VOLUMES_H
#define OBOR_PAK_VOLUMES_H
#if !defined(OBOR_ENGINE_BUILD)
#include "anybor_file_io.h"
#endif
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "anybor_file64.h"

/* PACK 1.1 stores independent, unchanged data/index pairs in numbered
 * volumes. Offsets are relative to their own volume, never the combined
 * archive. This reader performs no payload transformation. */
#define OBOR_PAK_MAX_VOLUMES 16
#define OBOR_PAK_DIRECTORY_LIMIT (32u << 20)
typedef struct {
    char path[4096];
    unsigned char *directory;
    uint32_t start, bytes, minimum;
} obor_pak_volume;
typedef struct {
    obor_pak_volume volumes[OBOR_PAK_MAX_VOLUMES];
    unsigned count, entries;
    uint32_t version;
} obor_pak_volumes;
static inline uint32_t obor_volume_u32(const unsigned char *p)
{
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 |
        (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static inline void obor_pak_volumes_close(obor_pak_volumes *pak)
{
    unsigned i;
    for (i = 0; i < pak->count; ++i) free(pak->volumes[i].directory);
    memset(pak, 0, sizeof(*pak));
}
static inline const char *obor_pak_volumes_open(obor_pak_volumes *pak, const char *path)
{
    unsigned i, total = 1;
    size_t directory_bytes = 0;
    const char *error = "Invalid or truncated PAK volume directory";
    FILE *file = NULL;
    memset(pak, 0, sizeof(*pak));
    for (i = 0; i < total; ++i) {
        obor_pak_volume *volume = &pak->volumes[i];
        unsigned char header[16], footer[4];
        int written = i ? snprintf(volume->path, sizeof(volume->path), "%s.%03u", path, i) :
            snprintf(volume->path, sizeof(volume->path), "%s", path);
        int64_t end;
        uint32_t position;
        if (written < 0 || (size_t)written >= sizeof(volume->path)) goto failed;
#if defined(OBOR_ENGINE_BUILD)
        /* The engine partial link supplies the session-scoped fopen. */
        file = fopen(volume->path, "rb");
#else
        file = obor_fopen(volume->path, "rb");
#endif
        if (!file) { error = "Missing or unreadable PAK volume"; goto failed; }
        if (fread(header, 1, 8, file) != 8 || memcmp(header, "PACK", 4)) goto failed;
        if (!i) {
            pak->version = obor_volume_u32(header + 4);
            if (pak->version != 0 && pak->version != 0x00010100u) {
                error = "Unsupported PAK version"; goto failed;
            }
        } else if (obor_volume_u32(header + 4) != pak->version) goto failed;
        volume->minimum = pak->version ? 16 : 8;
        if (pak->version) {
            uint32_t following;
            if (fread(header + 8, 1, 8, file) != 8) goto failed;
            following = obor_volume_u32(header + 8);
            /* The first header declares its numbered companions. A
             * companion cannot silently introduce another volume chain. */
            if ((!i && following >= OBOR_PAK_MAX_VOLUMES) || (i && following)) goto failed;
            if (!i) total += following;
        }
        if (obor_file_seek64(file, -4, SEEK_END) ||
            (end = obor_file_tell64(file)) < (int64_t)volume->minimum ||
            end > (int64_t)UINT32_MAX - 4 || fread(footer, 1, 4, file) != 4) goto failed;
        volume->start = obor_volume_u32(footer);
        if (volume->start < volume->minimum || volume->start > (uint64_t)end) goto failed;
        volume->bytes = (uint32_t)end - volume->start;
        directory_bytes += volume->bytes;
        if (directory_bytes > OBOR_PAK_DIRECTORY_LIMIT) goto failed;
        pak->count = i + 1;
        volume->directory = (unsigned char *)malloc(volume->bytes ? volume->bytes : 1);
        if (!volume->directory || obor_file_seek64(file, volume->start, SEEK_SET) ||
            fread(volume->directory, 1, volume->bytes, file) != volume->bytes) goto failed;
        for (position = 0; position < volume->bytes;) {
            const unsigned char *p = volume->directory + position;
            uint32_t length, start, size;
            if (++pak->entries > 1048576 || volume->bytes - position < 12) goto failed;
            length = obor_volume_u32(p);
            start = obor_volume_u32(p + 4);
            size = obor_volume_u32(p + 8);
            if (length < 14 || length > 1036 || length > volume->bytes - position ||
                !p[12] || p[length - 1] || memchr(p + 12, 0, length - 13) ||
                start < volume->minimum || start > volume->start || size > volume->start - start) goto failed;
            position += length;
        }
        fclose(file); file = NULL;
    }
    return NULL;
failed:
    if (file) fclose(file);
    obor_pak_volumes_close(pak);
    return error;
}
static inline unsigned char obor_pak_name_char(unsigned char c)
{
    if (c == '\\') return '/';
    return c >= 'A' && c <= 'Z' ? (unsigned char)(c + ('a' - 'A')) : c;
}
static inline int obor_pak_name_compare(const char *a, const char *b)
{
    while (*a && obor_pak_name_char((unsigned char)*a) == obor_pak_name_char((unsigned char)*b)) { ++a; ++b; }
    return (int)obor_pak_name_char((unsigned char)*a) - (int)obor_pak_name_char((unsigned char)*b);
}
static inline const unsigned char *obor_pak_volumes_find(const obor_pak_volumes *pak,
    const char *name, unsigned *volume_index)
{
    unsigned v;
    for (v = 0; v < pak->count; ++v) {
        const obor_pak_volume *volume = &pak->volumes[v];
        uint32_t position;
        for (position = 0; position < volume->bytes;) {
            const unsigned char *record = volume->directory + position;
            if (!obor_pak_name_compare((const char *)record + 12, name)) {
                *volume_index = v;
                return record;
            }
            position += obor_volume_u32(record);
        }
    }
    return NULL;
}
#endif
