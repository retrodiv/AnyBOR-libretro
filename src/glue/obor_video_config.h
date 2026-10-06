/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_VIDEO_CONFIG_H
#define OBOR_VIDEO_CONFIG_H
#include <ctype.h>
#include <stdbool.h>
#include <stdlib.h>
#include "obor_detection_clock.h"
#include "obor_pak_repair.h"

/* Startup-only metadata probe, not a replacement for full content validation.
 * Read the bounded file table once, then only the selected video settings.
 * Ordinary structurally damaged PACK headers/offsets use the existing generic
 * repair detection; no protected format or game identity is decoded here. */
static int obor_video_settings(const char *text, int *width, int *height)
{
    static const int modes[][2] = {
        {320, 240}, {480, 272}, {640, 480}, {720, 480},
        {800, 480}, {800, 600}, {960, 540}
    };
    int w = 320, h = 240;
    const char *line = text;
    while (*line) {
        const char *end = line;
        while (*end && *end != '\n' && *end != '\r') ++end;
        const char *p = line;
        while (p < end && isspace((unsigned char)*p)) ++p;
        if (end - p >= 5 && tolower((unsigned char)p[0]) == 'v' &&
            tolower((unsigned char)p[1]) == 'i' && tolower((unsigned char)p[2]) == 'd' &&
            tolower((unsigned char)p[3]) == 'e' && tolower((unsigned char)p[4]) == 'o' &&
            p + 5 < end && isspace((unsigned char)p[5])) {
            p += 5;
            while (p < end && isspace((unsigned char)*p)) ++p;
            int quote = p < end && *p == '"';
            if (quote) ++p;
            char *next;
            long first = strtol(p, &next, 10);
            if (next == p || next > end) return 0;
            if (next < end && *next == 'x') {
                p = next + 1;
                long second = strtol(p, &next, 10);
                if (next == p || next > end || first < 4 || second < 1 ||
                    first > 4096 || second > 4096) return 0;
                /* Engine screen allocations align pixel widths down to four. */
                w = (int)first & ~3; h = (int)second;
            } else {
                if (first < 0 || first >= (long)(sizeof(modes) / sizeof(modes[0]))) return 0;
                w = modes[first][0]; h = modes[first][1];
            }
            if (quote) {
                if (next >= end || *next != '"') return 0;
                ++next;
            }
            if (next < end && !isspace((unsigned char)*next) && *next != '#') return 0;
        }
        line = end;
        while (*line == '\n' || *line == '\r') ++line;
    }
    *width = w; *height = h;
    return 1;
}

static int obor_video_resolution(const char *path, int *width, int *height)
{
    FILE *fp = fopen(path, "rb");
    unsigned char header[8], tail[4], *table = NULL;
    char *text = NULL;
    int result = 0;
    if (!fp) return 0;
    do {
        if (fread(header, 1, 8, fp) != 8 || !memcmp(header, "SPAK", 4) ||
            obor_pak_u32(header + 4) || fseek(fp, 0, SEEK_END)) break;
        long size = ftell(fp);
        if (size < 12 || size > INT_MAX || fseek(fp, -4, SEEK_END) ||
            fread(tail, 1, 4, fp) != 4) break;
        uint32_t directory = obor_pak_u32(tail);
        if (directory < 8 || directory >= (uint32_t)size - 4) break;
        size_t bytes = (size_t)size - 4 - directory;
        if (bytes > (32u << 20)) break;
        int64_t bias = 0;
        if (memcmp(header, "PACK", 4)) {
            if (!obor_pak_header_repair_detect(fp)) break;
        } else {
            /* A repairable rebase is only an offset translation of an
             * exhaustive ordinary directory; detection validates its shape. */
            obor_pak_repair_detect(fp, &bias);
        }
        table = (unsigned char *)malloc(bytes);
        if (!table || fseek(fp, directory, SEEK_SET) || fread(table, 1, bytes, fp) != bytes) break;
        uint32_t starts[2] = {0, 0}, lengths[2] = {0, 0};
        size_t position = 0;
        unsigned count = 0;
        uint64_t started = obor_detection_now();
        int valid = 1;
        while (position < bytes) {
            if (++count > 1048576 || ((count & 1023) == 0 && obor_detection_expired(started)) ||
                bytes - position < 12) { valid = 0; break; }
            const unsigned char *entry = table + position;
            uint32_t length = obor_pak_u32(entry), stored = obor_pak_u32(entry + 4);
            uint32_t amount = obor_pak_u32(entry + 8);
            int64_t offset = (int64_t)stored - bias;
            if (length < 14 || length > 268 || length > bytes - position ||
                offset < 8 || offset > directory || amount > directory - offset) { valid = 0; break; }
            size_t n = length - 12;
            const unsigned char *terminator = (const unsigned char *)memchr(entry + 12, 0, n);
            if (!terminator || terminator == entry + 12) { valid = 0; break; }
            n = (size_t)(terminator - entry - 12);
            char name[256];
            for (size_t i = 0; i < n; ++i) {
                unsigned char c = entry[12 + i];
                name[i] = c == '\\' ? '/' : (char)tolower(c);
            }
            name[n] = 0;
            const char *normalized = name;
            while (*normalized == '/') ++normalized;
            int slot = !strcmp(normalized, "data/videopc.txt") ? 0 :
                       !strcmp(normalized, "data/video.txt") ? 1 : -1;
            if (slot >= 0 && !starts[slot]) {
                starts[slot] = (uint32_t)offset; lengths[slot] = amount;
            }
            position += length;
        }
        if (!valid) break;
        int slot = starts[0] ? 0 : 1;
        if (!starts[slot]) { *width = 320; *height = 240; result = 1; break; }
        if (lengths[slot] > 65536) break;
        text = (char *)malloc((size_t)lengths[slot] + 1);
        if (!text || fseek(fp, starts[slot], SEEK_SET) ||
            fread(text, 1, lengths[slot], fp) != lengths[slot]) break;
        if (memchr(text, 0, lengths[slot])) break;
        text[lengths[slot]] = 0;
        result = obor_video_settings(text, width, height);
    } while (0);
    free(text); free(table); fclose(fp);
    return result;
}

static int obor_video_directory_resolution(const char *root, int *width, int *height)
{
    static const char *names[] = { "data/videopc.txt", "data/video.txt" };
    for (unsigned i = 0; i < 2; ++i) {
        char path[4096];
        int n = snprintf(path, sizeof(path), "%s/%s", root, names[i]);
        if (n < 0 || (size_t)n >= sizeof(path)) return 0;
        FILE *fp = fopen(path, "rb");
        if (!fp) continue;
        long bytes = -1;
        if (!fseek(fp, 0, SEEK_END)) bytes = ftell(fp);
        char *text = bytes >= 0 && bytes <= 65536 ? (char *)malloc((size_t)bytes + 1) : NULL;
        int result = 0;
        if (text && !fseek(fp, 0, SEEK_SET) && fread(text, 1, bytes, fp) == (size_t)bytes &&
            !memchr(text, 0, bytes)) {
            text[bytes] = 0;
            result = obor_video_settings(text, width, height);
        }
        free(text); fclose(fp);
        return result;
    }
    *width = 320; *height = 240;
    return 1;
}
#endif
