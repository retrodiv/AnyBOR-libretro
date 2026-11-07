/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/* Hardened single-game ZIP extraction into the frontend save directory. */
#ifndef OBOR_ZIP_H
#define OBOR_ZIP_H

#include "miniz.h"
#include "obor_sha256.h"
#include "obor_storage.h"

#if !defined(_WIN32)
#include <sys/statvfs.h>
#include <unistd.h>
#endif

#define OBOR_ZIP_MAX_ENTRIES 8192U
#define OBOR_ZIP_MAX_FILE (2ULL << 30)
#define OBOR_ZIP_MAX_TOTAL (4ULL << 30)
#define OBOR_ZIP_MAX_RATIO 1000ULL

#include "obor_zip_path.h"

static size_t obor_zip_write(void *context, mz_uint64 offset, const void *data, size_t size)
{
    (void)offset;
    FILE *file = (FILE *)context;
    size_t written = fwrite(data, 1, size, file);
    obor_prepare_advance(written);
    return obor_prepare_checkpoint() ? written : 0;
}

static void obor_zip_lower(const char *in, char *out, size_t cap)
{
    size_t i = 0;
    for (; in[i] && i + 1 < cap; i++) {
        unsigned char c = (unsigned char)in[i];
        out[i] = (char)((c >= 'A' && c <= 'Z') ? c + 32 : c);
    }
    out[i] = '\0';
}

static void obor_zip_mkparents(const char *path)
{
    char dir[2200];
    snprintf(dir, sizeof(dir), "%s", path);
    char *s = strrchr(dir, '/');
    if (s) { *s = '\0'; mkdir_p(dir); }
}

static int obor_zip_space_ok(const char *path, uint64_t need)
{
#if defined(_WIN32)
    ULARGE_INTEGER avail;
    return GetDiskFreeSpaceExA(path, &avail, NULL, NULL) &&
           avail.QuadPart >= need;
#else
    struct statvfs st;
    return statvfs(path, &st) == 0 &&
           (uint64_t)st.f_bavail * (uint64_t)st.f_frsize >= need;
#endif
}

static int obor_zip_marker_ok(const char *marker, const char *hash)
{
    char line[96], expected[96];
    FILE *f = fopen(marker, "rb");
    if (!f) return 0;
    int ok = fgets(line, sizeof(line), f) != NULL;
    fclose(f);
    snprintf(expected, sizeof(expected), "oborzip-v3 %s\n", hash);
    return ok && strcmp(line, expected) == 0;
}

#include <stdlib.h>
#include "obor_engine_identity.h"
#include "obor_game_content.h"
#include "obor_packed_prepare.h"

struct obor_zip_reader_scope {
    mz_zip_archive archive;
    bool opened;
    obor_zip_reader_scope() : archive(), opened(false) {}
    ~obor_zip_reader_scope() { if (opened) mz_zip_reader_end(&archive); }
};
struct obor_zip_partial_scope {
    char path[1600];
    obor_zip_partial_scope() : path() {}
    ~obor_zip_partial_scope() { if (path[0]) obor_storage_remove(path); }
};
struct obor_zip_content_entry {
    char name[512], lower[512];
    unsigned index;
    bool directory;
};
struct obor_zip_content_entries {
    obor_zip_content_entry *data;
    explicit obor_zip_content_entries(unsigned count) :
        data((obor_zip_content_entry *)calloc(count, sizeof(obor_zip_content_entry))) {}
    ~obor_zip_content_entries() { free(data); }
};
static int obor_zip_compare_entries(const void *left, const void *right)
{
    return strcmp(((const obor_zip_content_entry *)left)->lower,
                  ((const obor_zip_content_entry *)right)->lower);
}
static const obor_zip_content_entry *obor_zip_find_entry(
    const obor_zip_content_entry *entries, unsigned count, const char *name)
{
    unsigned first = 0, end = count;
    while (first < end) {
        unsigned middle = first + (end - first) / 2;
        int order = strcmp(name, entries[middle].lower);
        if (!order) return entries + middle;
        if (order < 0) end = middle; else first = middle + 1;
    }
    return NULL;
}

static int obor_zip_prepare(const char *zip_path, const char *save_dir,
                            char *out, size_t out_cap, const char *system_dir = NULL,
                            obor_engine_identity *engine_identity = NULL)
{
    obor_prepare_range progress = obor_prepare_phase;
    obor_prepare_stage(progress, 0, 150, 0);
    char hash[65];
    if (!obor_sha256_file(zip_path, hash)) return 0;
    obor_zip_reader_scope reader;
    mz_zip_archive *za = &reader.archive;
    reader.opened = mz_zip_reader_init_file(za, zip_path, 0);
    if (!reader.opened) return 0;
    unsigned n = (unsigned)mz_zip_reader_get_num_files(za);
    if (!n || n > OBOR_ZIP_MAX_ENTRIES) return 0;

    obor_zip_content_entries entries(n);
    if (!entries.data) return 0;
    unsigned count = 0;
    uint64_t total_sz = 0;
    for (unsigned i = 0; i < n; ++i) {
        mz_zip_archive_file_stat st;
        char name[512], low[512];
        if (!mz_zip_reader_file_stat(za, i, &st) ||
            !obor_zip_safe_name(st.m_filename, name, sizeof(name)) ||
            ((st.m_external_attr >> 16) & 0170000) == 0120000 ||
            st.m_uncomp_size > OBOR_ZIP_MAX_FILE ||
            total_sz > OBOR_ZIP_MAX_TOTAL - st.m_uncomp_size ||
            (st.m_uncomp_size > (1U << 20) && (!st.m_comp_size ||
             st.m_uncomp_size / st.m_comp_size > OBOR_ZIP_MAX_RATIO))) {
            log_cb(RETRO_LOG_ERROR, "[OpenBOR] zip: unsafe path, link or size quota\n");
            return 0;
        }
        total_sz += st.m_uncomp_size;
        obor_zip_lower(name, low, sizeof(low));
        if (strstr(low, "__macosx/")) continue;
        size_t length = strlen(low);
        if (length && low[length - 1] == '/') low[length - 1] = 0;
        obor_zip_content_entry *entry = entries.data + count++;
        snprintf(entry->name, sizeof(entry->name), "%s", name);
        snprintf(entry->lower, sizeof(entry->lower), "%s", low);
        entry->index = i;
        entry->directory = st.m_is_directory;
    }
    qsort(entries.data, count, sizeof(*entries.data), obor_zip_compare_entries);
    for (unsigned i = 0; i < count; ++i) {
        const obor_zip_content_entry *entry = entries.data + i;
        if (i && !strcmp(entry->lower, entries.data[i - 1].lower) &&
            (!entry->directory || !entries.data[i - 1].directory)) {
            log_cb(RETRO_LOG_ERROR, "[OpenBOR] zip: duplicate portable path\n"); return 0;
        }
        /* A file cannot also be the parent of another archive member. */
        char ancestor[512];
        snprintf(ancestor, sizeof(ancestor), "%s", entry->lower);
        char *slash;
        while ((slash = strrchr(ancestor, '/'))) {
            *slash = 0;
            const obor_zip_content_entry *parent = obor_zip_find_entry(entries.data, count, ancestor);
            if (parent && !parent->directory) return 0;
        }
    }
    char parent[1200], cache[1400], marker[1500];
    if (!obor_storage_parent(save_dir, "zipcache", parent, sizeof(parent))) return 0;
    /* A new namespace avoids trusting caches made with the older extraction
     * layout or deleting a cache another frontend could still be using. */
    snprintf(cache, sizeof(cache), "%s/v3-%s", parent, hash);
    snprintf(marker, sizeof(marker), "%s/.complete", cache);
    if (!obor_storage_track(cache)) return 0;
    if (!obor_storage_directory(cache) || !obor_zip_marker_ok(marker, hash)) {
        if (!obor_zip_space_ok(parent, total_sz + (64ULL << 20))) return 0;
#if defined(_WIN32)
        unsigned long pid = (unsigned long)GetCurrentProcessId();
#else
        unsigned long pid = (unsigned long)getpid();
#endif
        obor_zip_partial_scope partial;
        snprintf(partial.path, sizeof(partial.path), "%s.partial-%lu", cache, pid);
        if (!obor_storage_track(partial.path) ||
            !obor_storage_remove(partial.path)) return 0;
        mkdir_p(partial.path);
        if (!obor_storage_directory(partial.path)) return 0;
        obor_prepare_stage(progress, 150, 800, total_sz);
        unsigned extracted = 0;
        for (unsigned i = 0; i < count; ++i) {
            const obor_zip_content_entry *entry = entries.data + i;
            if (entry->directory) continue;
            char dst[2200];
            snprintf(dst, sizeof(dst), "%s/%s", partial.path, entry->name);
            obor_zip_mkparents(dst);
            FILE *file = fopen(dst, "wb");
            bool ok = file && mz_zip_reader_extract_to_callback(za, entry->index, obor_zip_write, file, 0);
            if (file && fclose(file)) ok = false;
            if (!ok) return 0;
            ++extracted;
        }
        char temp_marker[1700];
        snprintf(temp_marker, sizeof(temp_marker), "%s/.complete", partial.path);
        FILE *file = fopen(temp_marker, "wb");
        if (!file) return 0;
        bool written = fprintf(file, "oborzip-v3 %s\n", hash) > 0;
        if (fclose(file) || !written) return 0;
        if (rename(partial.path, cache)) {
            if (!obor_storage_directory(cache) || !obor_zip_marker_ok(marker, hash)) return 0;
        } else partial.path[0] = 0;
        log_cb(RETRO_LOG_INFO, "[OpenBOR] zip: extracted %u files\n", extracted);
    } else log_cb(RETRO_LOG_INFO, "[OpenBOR] zip: using SHA-256 cache\n");

    unsigned games = 0, unknown = 0;
    char chosen[4096] = "";
    obor_engine_identity identity = {};
    obor_prepare_stage(progress, 800, 1000, 0);
    for (unsigned i = 0; i < count; ++i) {
        const obor_zip_content_entry *entry = entries.data + i;
        if (entry->directory) continue;
        char path[2200];
        const char *low = entry->lower;
        snprintf(path, sizeof(path), "%s/%s", cache, entry->name);
        const char *binary_name = strrchr(low, '/');
        binary_name = binary_name ? binary_name + 1 : low;
        if (engine_identity && obor_engine_binary_name(binary_name) && identity.status != OBOR_ENGINE_SCAN_INCOMPLETE)
            obor_engine_inspect_file(&identity, path);
        size_t length = strlen(low);
        bool packed = length > 4 && (!strcmp(low + length - 4, ".pak") || !strcmp(low + length - 4, ".spk"));
        const size_t models_length = strlen("data/models.txt");
        const char *models = length >= models_length && !strcmp(low + length - models_length, "data/models.txt") ?
            low + length - models_length : NULL;
        bool raw = models && (models == low || models[-1] == '/');
        if (!packed && !raw) continue;
        char candidate[4096];
        if (packed) {
            if (obor_game_wave_asset(path)) {
                log_cb(RETRO_LOG_INFO, "[OpenBOR] zip: auxiliary RIFF/WAVE %s\n", entry->name);
                continue;
            }
            if (!obor_packed_prepare(path, save_dir, system_dir, candidate, sizeof(candidate)) ||
                !obor_game_recognizable(candidate, true)) { ++unknown; continue; }
            snprintf(chosen, sizeof(chosen), "%s", candidate);
        } else {
            size_t root_length = strlen(cache) + 1 + (size_t)(models - low);
            snprintf(candidate, sizeof(candidate), "%s", path);
            candidate[root_length] = 0;
            if (!obor_game_recognizable(candidate, false)) { ++unknown; continue; }
            snprintf(chosen, sizeof(chosen), "%s", path);
        }
        ++games;
    }
    if (games != 1 || unknown) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] zip: %u recognizable games, %u inconclusive candidates; one game and no inconclusive candidates required\n", games, unknown);
        return 0;
    }
    if (engine_identity) *engine_identity = identity;
    int written = snprintf(out, out_cap, "%s", chosen);
    return written >= 0 && (size_t)written < out_cap;
}

#endif
