/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PREPARED_CACHE_H
#define OBOR_PREPARED_CACHE_H

#ifndef OBOR_CORE_VERSION
#include "anybor_engines.h"
#endif
#include "anybor_imohash.h"
#include "anybor_pak_volumes.h"
#include "anybor_prepare_progress.h"
#include "anybor_prepare_sync.h"
#include "anybor_sha256.h"
#include "anybor_storage.h"

struct obor_prepared_sample {
    uint64_t size;
    unsigned char hash[16];
};

static int obor_prepared_read(void *context, uint64_t offset, void *data, size_t size)
{
    FILE *file = (FILE *)context;
    return obor_prepare_checkpoint() && !obor_file_seek64(file, (int64_t)offset, SEEK_SET) &&
        fread(data, 1, size, file) == size;
}

static bool obor_prepared_sample_file(FILE *file, obor_prepared_sample &sample)
{
    if (obor_file_seek64(file, 0, SEEK_END)) return false;
    int64_t size = obor_file_tell64(file);
    if (size < 0) return false;
    sample.size = (uint64_t)size;
    return obor_imohash_read(obor_prepared_read, file, sample.size, sample.hash) != 0;
}

static bool obor_prepared_equal(const obor_prepared_sample &a, const obor_prepared_sample &b)
{
    return a.size == b.size && !memcmp(a.hash, b.hash, sizeof(a.hash));
}

/* A stat of the final component is intentional. Prepared outputs and their
 * marker may only be regular files in the loader-owned directory. */
static bool obor_prepared_regular(const char *path)
{
#if defined(_WIN32)
    DWORD attrs = obor_win_attributes(path);
    return attrs != INVALID_FILE_ATTRIBUTES &&
        !(attrs & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DEVICE));
#else
    struct stat st;
    return !lstat(path, &st) && S_ISREG(st.st_mode);
#endif
}

static FILE *obor_prepared_open(const char *path)
{
    return obor_prepared_regular(path) ? obor_fopen(path, "rb") : NULL;
}

static bool obor_prepared_sample_path(const char *path, obor_prepared_sample &sample)
{
    FILE *fp = obor_prepared_open(path);
    if (!fp) return false;
    bool ok = obor_prepared_sample_file(fp, sample);
    return !fclose(fp) && ok;
}

/* Hash only the bounded recipe record. The producer version advances with
 * every core commit, including changes to either preparation algorithm. */
static void obor_prepared_key(const char *kind, const obor_prepared_sample &source,
                              const char *relative, size_t length,
                              const char *recipe, char key[65])
{
    obor_sha256_ctx ctx;
    unsigned char digest[32];
    char size[32];
    snprintf(size, sizeof(size), "%llu", (unsigned long long)source.size);
    obor_sha256_init(&ctx);
    obor_sha256_update(&ctx, kind, strlen(kind) + 1);
    obor_sha256_update(&ctx, OBOR_CORE_VERSION, strlen(OBOR_CORE_VERSION) + 1);
    obor_sha256_update(&ctx, size, strlen(size) + 1);
    obor_sha256_update(&ctx, source.hash, sizeof(source.hash));
    obor_sha256_update(&ctx, recipe, strlen(recipe) + 1);
    obor_sha256_update(&ctx, relative, length);
    obor_sha256_final(&ctx, digest);
    for (unsigned i = 0; i < sizeof(digest); ++i) snprintf(key + 2*i, 3, "%02x", digest[i]);
}

static constexpr const char *obor_prepared_marker_name = ".complete";

static void obor_prepared_header(const char *key, char line[96])
{
    snprintf(line, 96, "anybor-prepared-v1 %s\n", key);
}

static bool obor_prepared_line_matches(FILE *fp, const char *expected)
{
    char line[640];
    /* Compare the newline and every byte, including any embedded NUL. */
    size_t length = strlen(expected);
    return length < sizeof(line) && fread(line, 1, length, fp) == length &&
        !memcmp(line, expected, length);
}

static FILE *obor_prepared_marker(const char *directory, const char *key)
{
    char path[1700], header[96];
    if (!obor_storage_directory(directory) ||
        !obor_storage_join(path, sizeof(path), directory, obor_prepared_marker_name)) return NULL;
    FILE *fp = obor_prepared_open(path);
    if (!fp) return NULL;
    obor_prepared_header(key, header);
    if (obor_prepared_line_matches(fp, header)) return fp;
    fclose(fp);
    return NULL;
}

static bool obor_prepared_slot(const char *parent, const char *kind, size_t digits,
                               const char *key, char *out, size_t capacity)
{
    if (!obor_storage_directory(parent)) {
#if defined(_WIN32)
        if (obor_win_attributes(parent) != INVALID_FILE_ATTRIBUTES) return false;
        DWORD error = GetLastError();
        if (error != ERROR_FILE_NOT_FOUND && error != ERROR_PATH_NOT_FOUND) return false;
#else
        struct stat st;
        if (!lstat(parent, &st) || errno != ENOENT) return false;
#endif
    }
    /* Only a full marker key can claim an existing short locator. */
    const size_t locations = 64 / digits;
    for (size_t i = 0; i < locations; ++i) {
        int n = snprintf(out, capacity, "%s/%s-%.*s", parent, kind, (int)digits, key + i*digits);
        if (n < 0 || (size_t)n >= capacity) return false;
#if defined(_WIN32)
        if (obor_win_attributes(out) == INVALID_FILE_ATTRIBUTES) {
            DWORD error = GetLastError();
            return error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND;
        }
#else
        struct stat st;
        if (lstat(out, &st)) return errno == ENOENT;
#endif
        if (FILE *marker = obor_prepared_marker(out, key)) {
            fclose(marker);
            return true;
        }
    }
    return false;
}

static void obor_prepared_row(const obor_prepared_sample &sample, const char *relative, char row[640])
{
    char hash[33];
    for (unsigned i = 0; i < sizeof(sample.hash); ++i)
        snprintf(hash + 2*i, 3, "%02x", sample.hash[i]);
    snprintf(row, 640, "%llu %s %s\n", (unsigned long long)sample.size, hash, relative);
}

struct obor_prepared_staging {
    char path[1600];

    obor_prepared_staging() : path() {}
    ~obor_prepared_staging() { if (path[0]) obor_storage_remove(path); }

    bool create(const char *parent, const char *prefix)
    {
#if defined(_WIN32)
        unsigned long pid = GetCurrentProcessId();
#else
        unsigned long pid = (unsigned long)getpid();
#endif
        static unsigned sequence;
        char candidate[sizeof(path)];
        for (unsigned attempt = 0; attempt < 16; ++attempt) {
            int n = snprintf(candidate, sizeof(candidate), "%s/%s-%lu-%u", parent, prefix, pid, ++sequence);
            if (n < 0 || (size_t)n >= sizeof(candidate)) return false;
            if (!obor_mkdir(candidate, 0700)) {
                strcpy(path, candidate);
                return true;
            }
            if (errno != EEXIST) return false;
        }
        return false;
    }

    bool publish(const char *directory)
    {
        if (obor_rename(path, directory)) return false;
        path[0] = 0;
        return true;
    }
};

/* A verified winner can be used when another loader publishes first. If
 * the occupied slot still belongs to this recipe its invalid tree can be
 * removed and replaced with a complete, independently prepared tree. */
template<class Verify>
static bool obor_prepared_publish(obor_prepared_staging &staging, const char *directory,
                                  const char *key, Verify verify)
{
    if (staging.publish(directory) || verify()) return true;
    FILE *marker = obor_prepared_marker(directory, key);
    if (!marker) return false;
    fclose(marker);
    return (obor_storage_remove(directory) && staging.publish(directory)) || verify();
}

static FILE *obor_prepared_create_marker(const char *directory, const char *key)
{
    char path[1700], header[96];
    if (!obor_storage_join(path, sizeof(path), directory, obor_prepared_marker_name)) return NULL;
    FILE *fp = obor_fopen(path, "wb");
    if (!fp) return NULL;
    obor_prepared_header(key, header);
    if (fputs(header, fp) >= 0) return fp;
    fclose(fp);
    return NULL;
}

#endif
