/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PAK_VALIDATE_H
#define OBOR_PAK_VALIDATE_H
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static uint32_t obor_pak_u32(const unsigned char *p)
{
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 |
           (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

/* Validate before entering an engine: their legacy readers assume a valid
 * directory and can loop forever when a text asset points into the index.
 * Stream only metadata; no game extraction or payload copies are needed. */
static const char *obor_pak_validate(const char *path)
{
    FILE *fp = fopen(path, "rb");
    unsigned char header[12], name[256];
    const char *error = "Invalid or truncated PAK directory";
    long end;
    uint32_t directory, position;
    if (!fp)
        return "Cannot open PAK file";
    if (fread(header, 1, 8, fp) != 8)
        goto done;
    /* Report recognized unsupported input with a specific load error. */
    if (!memcmp(header, "SPAK", 4)) {
        error = "Unsupported SPAK archive";
        goto done;
    }
    if (memcmp(header, "PACK", 4) || obor_pak_u32(header + 4)) {
        error = "Unsupported PAK signature or version";
        goto done;
    }
    if (fseek(fp, 0, SEEK_END) || (end = ftell(fp)) < 12 || end > INT_MAX)
        goto done;
    if (fseek(fp, end - 4, SEEK_SET) || fread(header, 1, 4, fp) != 4)
        goto done;
    directory = obor_pak_u32(header);
    if (directory < 8 || directory >= (uint32_t)end - 4 ||
        fseek(fp, directory, SEEK_SET))
        goto done;
    position = directory;
    while (position < (uint32_t)end - 4) {
        uint32_t length, start, size;
        if ((uint32_t)end - 4 - position < 12 || fread(header, 1, 12, fp) != 12)
            goto done;
        length = obor_pak_u32(header);
        start = obor_pak_u32(header + 4);
        size = obor_pak_u32(header + 8);
        if (length < 14 || length > 12 + sizeof(name) ||
            length > (uint32_t)end - 4 - position ||
            fread(name, 1, length - 12, fp) != length - 12 ||
            !name[0] || !memchr(name, 0, length - 12))
            goto done;
        if (start < 8 || start > directory || size > directory - start) {
            error = "Corrupt PAK: an asset points outside the data area (into the directory or beyond EOF)";
            goto done;
        }
        position += length;
    }
    error = NULL;
done:
    fclose(fp);
    return error;
}
#endif
