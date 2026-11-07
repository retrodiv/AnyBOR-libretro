/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_ENGINE_IDENTITY_H
#define OBOR_ENGINE_IDENTITY_H
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <sys/stat.h>
#if defined(_WIN32)
#include <windows.h>
#else
#include <dirent.h>
#include <strings.h>
#endif
#include "obor_sha256.h"
#include "obor_engine_executables.h"

#define OBOR_ENGINE_MAX_FILE (64U << 20)
#define OBOR_ENGINE_MAX_TOTAL (128U << 20)
#define OBOR_ENGINE_MAX_EXES 16U
#define OBOR_ENGINE_MAX_ENTRIES 1024U

enum obor_engine_identity_status {
    OBOR_ENGINE_UNKNOWN, OBOR_ENGINE_IDENTIFIED,
    OBOR_ENGINE_AMBIGUOUS, OBOR_ENGINE_SCAN_INCOMPLETE
};
typedef struct {
    enum obor_engine_identity_status status;
    const obor_engine_executable *engine;
    const obor_engine_executable *conflict;
    char evidence[4096];
    char conflicting_evidence[4096];
    unsigned files;
    uint64_t bytes;
} obor_engine_identity;

static const obor_engine_executable *obor_engine_lookup(const char *digest, uint64_t bytes)
{
    size_t first = 0, end = sizeof(obor_engine_executables) / sizeof(obor_engine_executables[0]);
    const size_t count = end;
    while (first < end) {
        size_t mid = first + (end - first) / 2;
        int order = strcmp(digest, obor_engine_executables[mid].sha256);
        if (order <= 0) end = mid; else first = mid + 1;
    }
    return first < count && !strcmp(digest, obor_engine_executables[first].sha256) &&
        obor_engine_executables[first].bytes == bytes ? &obor_engine_executables[first] : NULL;
}

static void obor_engine_observe(obor_engine_identity *identity,
                                const char *digest, uint64_t bytes, const char *evidence)
{
    const obor_engine_executable *engine = obor_engine_lookup(digest, bytes);
    if (!engine || identity->status == OBOR_ENGINE_SCAN_INCOMPLETE ||
        identity->status == OBOR_ENGINE_AMBIGUOUS) return;
    /* Some preserved platform binaries occur unchanged in several releases.
     * Keep every verified fact; a shared hash does not invent a unique build. */
    const obor_engine_executable *end = obor_engine_executables +
        sizeof(obor_engine_executables) / sizeof(obor_engine_executables[0]);
    for (const obor_engine_executable *other = engine + 1; other < end &&
            !strcmp(other->sha256, digest); ++other) {
        if (other->build != engine->build || strcmp(other->variant, engine->variant)) {
            identity->engine = engine;
            identity->conflict = other;
            identity->status = OBOR_ENGINE_AMBIGUOUS;
            snprintf(identity->evidence, sizeof(identity->evidence), "%s", evidence);
            snprintf(identity->conflicting_evidence, sizeof(identity->conflicting_evidence), "%s", evidence);
            return;
        }
    }
    if (identity->engine && (identity->engine->build != engine->build ||
            strcmp(identity->engine->variant, engine->variant))) {
        identity->status = OBOR_ENGINE_AMBIGUOUS;
        identity->conflict = engine;
        snprintf(identity->conflicting_evidence, sizeof(identity->conflicting_evidence), "%s", evidence);
        return;
    }
    identity->engine = engine;
    identity->status = OBOR_ENGINE_IDENTIFIED;
    snprintf(identity->evidence, sizeof(identity->evidence), "%s", evidence);
}

static int obor_engine_reserve(obor_engine_identity *identity, uint64_t bytes)
{
    if (++identity->files > OBOR_ENGINE_MAX_EXES || bytes > OBOR_ENGINE_MAX_FILE ||
            bytes > OBOR_ENGINE_MAX_TOTAL - identity->bytes) {
        if (identity->status != OBOR_ENGINE_AMBIGUOUS) identity->status = OBOR_ENGINE_SCAN_INCOMPLETE;
        return 0;
    }
    identity->bytes += bytes;
    return 1;
}

static int obor_engine_binary_name(const char *name)
{
    size_t n = strlen(name);
    const char *suffix = strrchr(name, '.');
    if (suffix && (!strcasecmp(suffix, ".exe") || !strcasecmp(suffix, ".appimage") ||
            !strcasecmp(suffix, ".apk") || !strcasecmp(suffix, ".elf") ||
            !strcasecmp(suffix, ".gpe") || !strcasecmp(suffix, ".dge") ||
            !strcasecmp(suffix, ".opk"))) return 1;
    if (!strcasecmp(name, "boot.dol") || !strcasecmp(name, "eboot.pbp") ||
            !strcasecmp(name, "1st_read.bin")) return 1;
    /* Bare engine names include the published architecture variants.
     * Game archives and documents never become candidates from this prefix. */
    return n >= 7 && !strncasecmp(name, "openbor", 7) &&
        (n == 7 || (!suffix && (name[7] == '-' || name[7] == '_')));
}

static void obor_engine_inspect_file(obor_engine_identity *identity, const char *path)
{
    struct stat st;
    if (stat(path, &st) || !S_ISREG(st.st_mode) || st.st_size < 0) return;
    if (!obor_engine_reserve(identity, (uint64_t)st.st_size)) return;
    FILE *file = fopen(path, "rb");
    if (!file) { identity->status = OBOR_ENGINE_SCAN_INCOMPLETE; return; }
    obor_sha256_ctx hash;
    obor_sha256_init(&hash);
    unsigned char block[65536], digest[32];
    uint64_t remaining = (uint64_t)st.st_size;
    while (remaining) {
        size_t want = remaining < sizeof(block) ? (size_t)remaining : sizeof(block);
        size_t got = fread(block, 1, want, file);
        if (got != want || !obor_prepare_checkpoint()) break;
        obor_sha256_update(&hash, block, got);
        remaining -= got;
    }
    int complete = !remaining && fgetc(file) == EOF && !ferror(file);
    fclose(file);
    if (!complete) { identity->status = OBOR_ENGINE_SCAN_INCOMPLETE; return; }
    obor_sha256_final(&hash, digest);
    char hex[65];
    static const char digits[] = "0123456789abcdef";
    for (unsigned i = 0; i < 32; ++i) {
        hex[2*i] = digits[digest[i] >> 4]; hex[2*i+1] = digits[digest[i] & 15];
    }
    hex[64] = 0;
    obor_engine_observe(identity, hex, (uint64_t)st.st_size, path);
}

/* Only the content's own directory, never its siblings or a parent of a PAK.
 * For unpacked content the caller supplies the directory containing data/. */
static obor_engine_identity obor_engine_in_directory(const char *directory)
{
    obor_engine_identity identity = {};
    unsigned entries = 0;
#if defined(_WIN32)
    char pattern[4096];
    if (snprintf(pattern, sizeof(pattern), "%s/*", directory) >= (int)sizeof(pattern)) {
        identity.status = OBOR_ENGINE_SCAN_INCOMPLETE; return identity;
    }
    WIN32_FIND_DATAA data;
    HANDLE handle = FindFirstFileA(pattern, &data);
    if (handle == INVALID_HANDLE_VALUE) return identity;
    do {
        if (++entries > OBOR_ENGINE_MAX_ENTRIES) { identity.status = OBOR_ENGINE_SCAN_INCOMPLETE; break; }
        if ((data.dwFileAttributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT)) ||
            !obor_engine_binary_name(data.cFileName)) continue;
        char path[4096];
        if (snprintf(path, sizeof(path), "%s/%s", directory, data.cFileName) >= (int)sizeof(path)) {
            identity.status = OBOR_ENGINE_SCAN_INCOMPLETE; break;
        }
        obor_engine_inspect_file(&identity, path);
        if (identity.status == OBOR_ENGINE_SCAN_INCOMPLETE) break;
    } while (FindNextFileA(handle, &data));
    if (identity.status != OBOR_ENGINE_SCAN_INCOMPLETE && GetLastError() != ERROR_NO_MORE_FILES)
        identity.status = OBOR_ENGINE_SCAN_INCOMPLETE;
    FindClose(handle);
#else
    DIR *dir = opendir(directory);
    if (!dir) return identity;
    struct dirent *entry;
    for (;;) {
        errno = 0;
        entry = readdir(dir);
        if (!entry) { if (errno) identity.status = OBOR_ENGINE_SCAN_INCOMPLETE; break; }
        if (++entries > OBOR_ENGINE_MAX_ENTRIES) { identity.status = OBOR_ENGINE_SCAN_INCOMPLETE; break; }
        if (!obor_engine_binary_name(entry->d_name)) continue;
        char path[4096];
        if (snprintf(path, sizeof(path), "%s/%s", directory, entry->d_name) >= (int)sizeof(path)) {
            identity.status = OBOR_ENGINE_SCAN_INCOMPLETE; break;
        }
        struct stat st;
        if (lstat(path, &st) || !S_ISREG(st.st_mode)) continue;
        obor_engine_inspect_file(&identity, path);
        if (identity.status == OBOR_ENGINE_SCAN_INCOMPLETE) break;
    }
    closedir(dir);
#endif
    return identity;
}

static obor_engine_identity obor_engine_for_content(const char *path, bool unpacked)
{
    char directory[4096];
    obor_engine_identity unknown = {};
    if (snprintf(directory, sizeof(directory), "%s", path) >= (int)sizeof(directory)) return unknown;
    if (!unpacked) {
        char *a = strrchr(directory, '/'), *b = strrchr(directory, '\\');
        char *slash = b && (!a || b > a) ? b : a;
        if (!slash) snprintf(directory, sizeof(directory), ".");
        else if (slash == directory || (slash == directory + 2 && directory[1] == ':')) slash[1] = 0;
        else *slash = 0;
    }
    return obor_engine_in_directory(directory);
}
#endif
