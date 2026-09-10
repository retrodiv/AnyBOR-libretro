/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PAK_REPAIR_H
#define OBOR_PAK_REPAIR_H
#include "obor_pak_validate.h"
#include <ctype.h>

static int obor_pak_write_u32(FILE *fp, uint32_t value)
{
    unsigned char b[4] = { (unsigned char)value, (unsigned char)(value >> 8),
        (unsigned char)(value >> 16), (unsigned char)(value >> 24) };
    return fwrite(b, 1, 4, fp) == 4;
}

/* Recognize only a complete, tightly packed data area with a uniform stale
 * base. Every directory range must meet the next, with no gaps, overlaps or
 * reordering, and their combined size must exactly fill [8, directory).
 * Two distinct GIF/PNG records must confirm the proposed physical positions.
 * Valid PACK files and any ambiguous/other damage are never repaired. */
static int obor_pak_repair_detect(FILE *fp, int64_t *bias)
{
    unsigned char h[12], name[256], signature[8];
    long end;
    uint32_t directory, position;
    uint64_t first = 0, cursor = 0, count = 0;
    unsigned anchors = 0, invalid_bounds = 0;
    int64_t shift = 0;
    if (fseek(fp, 0, SEEK_SET) || fread(h, 1, 8, fp) != 8 ||
        memcmp(h, "PACK\0\0\0\0", 8) || fseek(fp, 0, SEEK_END) ||
        (end = ftell(fp)) < 12 || end > INT_MAX ||
        fseek(fp, end - 4, SEEK_SET) || fread(h, 1, 4, fp) != 4)
        return 0;
    directory = obor_pak_u32(h);
    if (directory <= 8 || directory >= (uint32_t)end - 4 ||
        fseek(fp, directory, SEEK_SET)) return 0;
    position = directory;
    while (position < (uint32_t)end - 4) {
        uint32_t length, start, size, n;
        int kind = 0;
        if ((uint32_t)end - 4 - position < 12 || fread(h, 1, 12, fp) != 12)
            return 0;
        length = obor_pak_u32(h); start = obor_pak_u32(h + 4); size = obor_pak_u32(h + 8);
        if (length < 14 || length > 268 || length > (uint32_t)end - 4 - position)
            return 0;
        n = length - 12;
        if (fread(name, 1, n, fp) != n || !name[0] || name[n - 1]) return 0;
        for (uint32_t j = 0; j + 1 < n; ++j) {
            /* Archive names may use a legacy non-ASCII code page. Preserve
             * those bytes; only ASCII case folding is needed for extensions. */
            if (name[j] < 32 || name[j] == 127) return 0;
            if (name[j] >= 'A' && name[j] <= 'Z') name[j] += 'a' - 'A';
        }
        if (!count) { first = cursor = start; shift = (int64_t)first - 8; }
        if (!shift || start != cursor || (uint64_t)size > UINT32_MAX - cursor)
            return 0;
        cursor += size; ++count;
        if (count > 1048576 || cursor - first > directory - 8) return 0;
        if (start < 8 || start > directory || (uint64_t)start + size > directory)
            invalid_bounds = 1;
        if (n > 4 && !strcmp((char *)name + n - 5, ".gif")) kind = 1;
        if (n > 4 && !strcmp((char *)name + n - 5, ".png")) kind = 2;
        if (kind && anchors < 2) {
            size_t bytes = kind == 1 ? 6 : 8;
            int64_t physical = (int64_t)start - shift;
            if (size < bytes || physical < 8 || (uint64_t)physical + size > directory ||
                fseek(fp, (long)physical, SEEK_SET) || fread(signature, 1, bytes, fp) != bytes)
                return 0;
            if (kind == 1 && memcmp(signature, "GIF87a", 6) && memcmp(signature, "GIF89a", 6)) return 0;
            if (kind == 2 && memcmp(signature, "\x89PNG\r\n\x1a\n", 8)) return 0;
            ++anchors;
            if (fseek(fp, position + length, SEEK_SET)) return 0;
        }
        position += length;
    }
    if (count < 2 || anchors < 2 || !invalid_bounds || cursor - first != directory - 8)
        return 0;
    *bias = shift;
    return 1;
}

/* Detection runs again on the open source, before creating any output bytes. */
static int obor_pak_repair_bias(FILE *input, FILE *output, int64_t expected)
{
    unsigned char block[65536], h[12], name[256];
    int64_t bias;
    long end;
    uint32_t directory, remaining, pos;
    if (!obor_pak_repair_detect(input, &bias) || bias != expected ||
        fseek(input, 0, SEEK_END) || (end = ftell(input)) < 12 ||
        fseek(input, end - 4, SEEK_SET) || fread(h, 1, 4, input) != 4) return 0;
    directory = obor_pak_u32(h);
    if (fseek(input, 0, SEEK_SET)) return 0;
    remaining = directory;
    while (remaining) {
        size_t n = remaining < sizeof(block) ? remaining : sizeof(block);
        if (fread(block, 1, n, input) != n || fwrite(block, 1, n, output) != n) return 0;
        remaining -= (uint32_t)n;
    }
    pos = directory;
    while (pos < (uint32_t)end - 4) {
        uint32_t length, size;
        int64_t start;
        if (fread(h, 1, 12, input) != 12) return 0;
        length = obor_pak_u32(h); start = (int64_t)obor_pak_u32(h + 4) - bias;
        size = obor_pak_u32(h + 8);
        if (length < 14 || length > 268 || length > (uint32_t)end - 4 - pos ||
            start < 8 || (uint64_t)start + size > directory ||
            fread(name, 1, length - 12, input) != length - 12) return 0;
        if (!obor_pak_write_u32(output, length) || !obor_pak_write_u32(output, (uint32_t)start) ||
            !obor_pak_write_u32(output, size) || fwrite(name, 1, length - 12, output) != length - 12)
            return 0;
        pos += length;
    }
    return obor_pak_write_u32(output, directory) && fflush(output) == 0;
}
#endif
