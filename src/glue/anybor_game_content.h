/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_GAME_CONTENT_H
#define OBOR_GAME_CONTENT_H
#include <ctype.h>
#include <sys/stat.h>
#include <dirent.h>
#include "anybor_pak_validate.h"
#include "anybor_zip_path.h"

static bool obor_game_disk_path(const char *root, const char *asset, char *out, size_t cap)
{
    if (snprintf(out, cap, "%s", root) >= (int)cap) return false;
    const char *part = asset;
    while (*part) {
        const char *slash = strchr(part, '/');
        size_t length = slash ? (size_t)(slash - part) : strlen(part);
        char name[512], candidate[4096];
        if (!length || length >= sizeof(name)) return false;
        memcpy(name, part, length); name[length] = 0;
        if (snprintf(candidate, sizeof(candidate), "%s/%s", out, name) >= (int)sizeof(candidate)) return false;
        struct stat st;
        if (stat(candidate, &st)) {
            DIR *directory = opendir(out);
            if (!directory) return false;
            unsigned seen = 0;
            bool found = false;
            struct dirent *entry;
            while ((entry = readdir(directory))) {
                if (++seen > 8194U) { found = false; break; }
                if (!strcasecmp(name, entry->d_name)) {
                    if (snprintf(candidate, sizeof(candidate), "%s/%s", out, entry->d_name) >= (int)sizeof(candidate)) break;
                    found = true;
                    break;
                }
            }
            closedir(directory);
            if (!found) return false;
        }
        if (snprintf(out, cap, "%s", candidate) >= (int)cap) return false;
        part += length;
        if (*part == '/') ++part;
    }
    return true;
}

/* Recognition is a bounded reference check, not a substitute for an engine
 * boot: models.txt must actually declare a nonempty model stored in the game. */
static FILE *obor_game_asset(const char *content, bool packed, const char *asset, uint32_t *size)
{
    char safe[512];
    if (!obor_zip_safe_name(asset, safe, sizeof(safe))) return NULL;
    if (!packed) {
        char path[4096];
        if (!obor_game_disk_path(content, safe, path, sizeof(path))) return NULL;
        struct stat st;
        if (stat(path, &st) || !S_ISREG(st.st_mode) || st.st_size < 0 || (uint64_t)st.st_size > UINT32_MAX)
            return NULL;
        *size = (uint32_t)st.st_size;
        return fopen(path, "rb");
    }
    FILE *file = fopen(content, "rb");
    unsigned char data[12];
    if (!file) return NULL;
    if (fseek(file, -4, SEEK_END) || fread(data, 1, 4, file) != 4) { fclose(file); return NULL; }
    long end = ftell(file) - 4;
    uint32_t position = obor_pak_u32(data);
    while (position < (uint64_t)end && obor_prepare_checkpoint()) {
        unsigned char name[256];
        if (fseek(file, position, SEEK_SET) || fread(data, 1, 12, file) != 12) break;
        uint32_t length = obor_pak_u32(data), start = obor_pak_u32(data + 4);
        if (length < 14 || length > 268 || length > (uint64_t)end - position ||
            fread(name, 1, length - 12, file) != length - 12 || !memchr(name, 0, length - 12)) break;
        for (unsigned i = 0; name[i]; ++i) if (name[i] == '\\') name[i] = '/';
        if (!strcasecmp((char *)name, safe)) {
            *size = obor_pak_u32(data + 8);
            if (!fseek(file, start, SEEK_SET)) return file;
            break;
        }
        position += length;
    }
    fclose(file);
    return NULL;
}

static const char *obor_game_token(const char *line, char *out, size_t cap)
{
    size_t n = 0;
    while (*line && isspace((unsigned char)*line)) ++line;
    bool quoted = *line == '"';
    if (quoted) ++line;
    while (*line && (quoted ? *line != '"' : !isspace((unsigned char)*line) && *line != '#')) {
        if (n + 1 >= cap) { out[0] = 0; return line + strlen(line); }
        out[n++] = *line++;
    }
    out[n] = 0;
    return quoted && *line == '"' ? line + 1 : line;
}

static bool obor_game_recognizable(const char *content, bool packed)
{
    if (packed && obor_pak_validate(content)) return false;
    uint32_t bytes = 0;
    FILE *models = obor_game_asset(content, packed, "data/models.txt", &bytes);
    if (!models) return false;
    /* Bound observation work independently of the archive/extraction quota. */
    if (!bytes || bytes > (4U << 20)) { fclose(models); return false; }
    char line[4096];
    bool result = false, first = true;
    unsigned references = 0;
    while (bytes && obor_prepare_checkpoint()) {
        size_t used = 0;
        bool overflow = false;
        while (bytes) {
            int c = fgetc(models); --bytes;
            if (c == EOF || c == '\n') break;
            if (!c) { overflow = true; break; }
            if (used + 1 < sizeof(line)) line[used++] = (char)c; else overflow = true;
        }
        line[used] = 0;
        if (overflow) break;
        char command[64], name[256], path[512];
        const char *start = line;
        if (first && used >= 3 && !memcmp(line, "\xef\xbb\xbf", 3)) start += 3;
        first = false;
        const char *next = obor_game_token(start, command, sizeof(command));
        if (strcasecmp(command, "load") && strcasecmp(command, "know")) continue;
        next = obor_game_token(next, name, sizeof(name));
        obor_game_token(next, path, sizeof(path));
        if (!name[0] || !path[0]) continue;
        if (++references > 32U) break;
        uint32_t model_bytes = 0;
        FILE *model = obor_game_asset(content, packed, path, &model_bytes);
        if (model) { fclose(model); if (model_bytes) { result = true; break; } }
    }
    fclose(models);
    return result;
}

/* A complete RIFF/WAVE is an audio asset even if its extension is .pak. */
static bool obor_game_wave_asset(const char *path)
{
    FILE *file = fopen(path, "rb");
    if (!file) return false;
    unsigned char header[12];
    bool result = false, format = false, audio = false;
    if (fseek(file, 0, SEEK_END)) { fclose(file); return false; }
    long bytes = ftell(file);
    if (bytes < 12 || fseek(file, 0, SEEK_SET) || fread(header, 1, 12, file) != 12 ||
        memcmp(header, "RIFF", 4) || memcmp(header + 8, "WAVE", 4) ||
        (uint64_t)obor_pak_u32(header + 4) + 8 != (uint64_t)bytes) { fclose(file); return false; }
    uint64_t position = 12;
    while (position + 8 <= (uint64_t)bytes) {
        if (fseek(file, (long)position, SEEK_SET) || fread(header, 1, 8, file) != 8) break;
        uint32_t chunk = obor_pak_u32(header + 4);
        uint64_t next = position + 8 + chunk + (chunk & 1);
        if (next > (uint64_t)bytes) break;
        if (!memcmp(header, "fmt ", 4) && chunk >= 16) format = true;
        if (!memcmp(header, "data", 4)) audio = true;
        position = next;
    }
    result = position == (uint64_t)bytes && format && audio;
    fclose(file);
    return result;
}
#endif
