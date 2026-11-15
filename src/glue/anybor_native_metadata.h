/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_NATIVE_METADATA_H
#define OBOR_NATIVE_METADATA_H
#include <ctype.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "anybor_abi.h"
#include "anybor_detection_clock.h"
#include "anybor_pak_volumes.h"

/* Native root directives have no script function namespace. Resolve the same
 * desktop video/level binding as the engine before accepting a capability.
 * Read PACK directories and two bounded metadata members;
 * unrelated model/script counts cannot turn this into a partial positive. */
struct obor_native_member {
    uint32_t start, size;
    unsigned matches, volume;
};
struct obor_native_directory {
    obor_pak_volumes volumes;
    uint64_t started;
};
static uint32_t obor_native_u32(const unsigned char *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
        ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static bool obor_native_name(const char *input, size_t bytes, char output[1024])
{
    if (!bytes || bytes >= 1024 || input[0] == '/' || input[0] == '\\') return false;
    size_t segment = 0;
    for (size_t i = 0; i <= bytes; ++i) {
        unsigned char c = i == bytes ? 0 : (unsigned char)input[i];
        if (c == ':' || (c < 32 && c != 0)) return false;
        if (!c || c == '/' || c == '\\') {
            size_t length = i - segment;
            if (!length || (length == 1 && input[segment] == '.') ||
                (length == 2 && input[segment] == '.' && input[segment + 1] == '.')) return false;
            segment = i + 1;
        }
        output[i] = c == '\\' ? '/' : (char)tolower(c);
    }
    return true;
}
static bool obor_native_find(const obor_native_directory *pak,
    const char *const *names, size_t count, obor_native_member *members)
{
    memset(members, 0, sizeof(*members) * count);
    unsigned entries = 0;
    for (unsigned v = 0; v < pak->volumes.count; ++v) {
    const obor_pak_volume *volume = &pak->volumes.volumes[v];
    size_t position = 0;
    while (position < volume->bytes) {
        if (++entries > 1048576 || ((entries & 1023) == 0 &&
            obor_detection_expired(pak->started)) || volume->bytes - position < 12) return false;
        const unsigned char *p = volume->directory + position;
        uint32_t length = obor_native_u32(p), start = obor_native_u32(p + 4), size = obor_native_u32(p + 8);
        if (length < 14 || length > 1036 || length > volume->bytes - position ||
            start < volume->minimum || start > volume->start || size > volume->start - start) return false;
        size_t bytes = length - 12;
        if (p[length - 1] || memchr(p + 12, 0, bytes - 1)) return false;
        char name[1024];
        if (!obor_native_name((const char *)p + 12, bytes - 1, name)) return false;
        for (size_t i = 0; i < count; ++i) {
            if (strcmp(name, names[i])) continue;
            if (++members[i].matches != 1) return false;
            members[i].start = start; members[i].size = size; members[i].volume = v;
        }
        position += length;
    }
    }
    return !obor_detection_expired(pak->started);
}
static char *obor_native_text(const obor_native_directory *pak,
    const obor_native_member *member, size_t maximum)
{
    if (member->matches != 1 || member->size > maximum || obor_detection_expired(pak->started)) return NULL;
    char *text = (char *)malloc((size_t)member->size + 1);
    if (!text) return NULL;
    FILE *file = fopen(pak->volumes.volumes[member->volume].path, "rb");
    if (!file) { free(text); return NULL; }
    bool ok = !obor_file_seek64(file, member->start, SEEK_SET) &&
        fread(text, 1, member->size, file) == member->size &&
        !memchr(text, 0, member->size) && !obor_detection_expired(pak->started);
    fclose(file);
    if (!ok) { free(text); return NULL; }
    text[member->size] = 0;
    return text;
}
/* Parse the first two native arguments, retaining quote characters as the
 * engine's ParseArgs does. Refuse overlong, unterminated or escaped quoting;
 * neither an incomplete line nor a quoted command supplies a capability. */
static bool obor_native_line(const char *line, size_t length, char command[1024], char argument[1024])
{
    if (length >= 1024) return false;
    command[0] = argument[0] = 0;
    size_t position = 0;
    unsigned word = 0;
    while (position < length) {
        while (position < length && (line[position] == ' ' || line[position] == '\t')) ++position;
        if (position == length || line[position] == '#') break;
        int quote = 0;
        size_t used = 0;
        char *output = word == 0 ? command : word == 1 ? argument : NULL;
        while (position < length) {
            char c = line[position];
            if (c == '\\' && position + 1 < length &&
                (line[position + 1] == '\'' || line[position + 1] == '"')) return false;
            if (c == '\'' || c == '"') {
                if (!quote) quote = c;
                else if (quote == c) quote = 0;
            }
            if (!quote && (c == ' ' || c == '\t' || c == '#')) break;
            if ((unsigned char)c < 32) return false;
            if (output) output[used++] = c;
            ++position;
        }
        if (quote) return false;
        if (output) output[used] = 0;
        ++word;
        if (position < length && line[position] == '#') break;
    }
    for (size_t i = 0; command[i]; ++i) command[i] = (char)tolower((unsigned char)command[i]);
    return true;
}
static bool obor_native_metadata_lines(const obor_native_directory *pak, const char *text,
    bool video, char levels[1024], bool *capability)
{
    const char *line = text;
    while (*line) {
        const char *end = line;
        while (*end && *end != '\n' && *end != '\r') ++end;
        char command[1024], argument[1024];
        if (obor_detection_expired(pak->started) ||
            !obor_native_line(line, (size_t)(end - line), command, argument)) return false;
        if (video && !strcmp(command, "levels")) {
            char path[1024], normalized[1024];
            int n = snprintf(path, sizeof(path), "data/%s", argument);
            if (!argument[0] || n < 0 || (size_t)n >= sizeof(path) ||
                !obor_native_name(path, (size_t)n, normalized)) return false;
            memcpy(levels, normalized, (size_t)n + 1);
        } else if (!video && argument[0] &&
            (!strcmp(command, "hallfame_difficulties") || !strcmp(command, "hallfame_initials") ||
             !strcmp(command, "hallfame_times"))) *capability = true;
        line = end;
        while (*line == '\n' || *line == '\r') ++line;
    }
    return !obor_detection_expired(pak->started);
}
static uint32_t obor_native_metadata_features(const char *path)
{
    obor_native_directory pak = {};
    pak.started = obor_detection_now();
    if (obor_pak_volumes_open(&pak.volumes, path)) return 0;
    uint32_t features = 0;
    char *video = NULL, *levels_text = NULL;
    do {
        static const char *const video_names[] = {"data/videopc.txt", "data/video.txt"};
        obor_native_member settings[2];
        if (!obor_native_find(&pak, video_names, 2, settings)) break;
        char levels[1024] = "data/levels.txt";
        bool capability = false;
        const obor_native_member *selected = settings[0].matches ? settings : settings[1].matches ? settings + 1 : NULL;
        if (selected) {
            video = obor_native_text(&pak, selected, 65536);
            if (!video || !obor_native_metadata_lines(&pak, video, true, levels, &capability)) break;
        }
        const char *names[] = {levels};
        obor_native_member order;
        if (!obor_native_find(&pak, names, 1, &order) || order.matches != 1) break;
        levels_text = obor_native_text(&pak, &order, 2u << 20);
        if (!levels_text || !obor_native_metadata_lines(&pak, levels_text, false, levels, &capability)) break;
        if (capability) features = OBOR_PROFILE_LNS_6330;
    } while (0);
    free(levels_text); free(video); obor_pak_volumes_close(&pak.volumes);
    return features;
}
#endif
