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
    snprintf(expected, sizeof(expected), "oborzip-v2 %s\n", hash);
    return ok && strcmp(line, expected) == 0;
}

static int obor_zip_prepare(const char *zip_path, const char *save_dir,
                            char *out, size_t out_cap)
{
    char hash[65];
    if (!obor_sha256_file(zip_path, hash)) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] zip: cannot hash %s\n", zip_path);
        return 0;
    }

    mz_zip_archive za;
    memset(&za, 0, sizeof(za));
    if (!mz_zip_reader_init_file(&za, zip_path, 0)) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] zip: cannot read %s\n", zip_path);
        return 0;
    }

    unsigned n = (unsigned)mz_zip_reader_get_num_files(&za);
    if (n == 0 || n > OBOR_ZIP_MAX_ENTRIES) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] zip: unsafe entry count %u\n", n);
        mz_zip_reader_end(&za);
        return 0;
    }

    char pak_entry[512] = "", models_entry[512] = "", root[512] = "";
    int npak = 0, nroot = 0;
    uint64_t total_sz = 0;
    for (unsigned i = 0; i < n; i++) {
        mz_zip_archive_file_stat st;
        if (!mz_zip_reader_file_stat(&za, i, &st)) goto unsafe;
        char nm[512], low[512];
        if (!obor_zip_safe_name(st.m_filename, nm, sizeof(nm))) goto unsafe;
        obor_zip_lower(nm, low, sizeof(low));
        if (((st.m_external_attr >> 16) & 0170000) == 0120000) goto unsafe;
        if (st.m_uncomp_size > OBOR_ZIP_MAX_FILE ||
            total_sz > OBOR_ZIP_MAX_TOTAL - st.m_uncomp_size ||
            (st.m_uncomp_size > (1U << 20) &&
             (st.m_comp_size == 0 ||
              st.m_uncomp_size / st.m_comp_size > OBOR_ZIP_MAX_RATIO)))
            goto unsafe;
        total_sz += st.m_uncomp_size;
        if (st.m_is_directory || strstr(low, "__macosx/")) continue;
        size_t ln = strlen(low);
        if (ln > 4 && strcmp(low + ln - 4, ".pak") == 0) {
            npak++;
            snprintf(pak_entry, sizeof(pak_entry), "%s", nm);
        }
        const char *dm = strstr(low, "data/models.txt");
        if (dm && (dm == low || dm[-1] == '/') &&
            dm[strlen("data/models.txt")] == '\0') {
            size_t rl = (size_t)(dm - low);
            char candidate[512];
            memcpy(candidate, nm, rl); candidate[rl] = '\0';
            snprintf(models_entry, sizeof(models_entry), "%s", nm + rl);
            if (nroot == 0 || strcasecmp(candidate, root) != 0) {
                nroot++;
                snprintf(root, sizeof(root), "%s", candidate);
            }
        }
    }

    if (npak + nroot != 1) {
        log_cb(RETRO_LOG_ERROR,
               "[OpenBOR] zip: %d games inside (%d .pak, %d data trees); "
               "exactly one is required\n", npak + nroot, npak, nroot);
        mz_zip_reader_end(&za);
        return 0;
    }

    char parent[1200], cache[1400], marker[1500];
    if (!obor_storage_parent(save_dir, "zipcache", parent, sizeof(parent))) {
        mz_zip_reader_end(&za); return 0;
    }
    snprintf(cache, sizeof(cache), "%s/%s", parent, hash);
    snprintf(marker, sizeof(marker), "%s/.complete", cache);
    if (!obor_storage_track(cache)) { mz_zip_reader_end(&za); return 0; }

    if (!obor_storage_directory(cache) || !obor_zip_marker_ok(marker, hash)) {
        if (!obor_zip_space_ok(parent, total_sz + (64ULL << 20))) {
            log_cb(RETRO_LOG_ERROR,
                   "[OpenBOR] zip: insufficient cache space for %llu bytes\n",
                   (unsigned long long)total_sz);
            mz_zip_reader_end(&za);
            return 0;
        }
#if defined(_WIN32)
        unsigned long pid = (unsigned long)GetCurrentProcessId();
#else
        unsigned long pid = (unsigned long)getpid();
#endif
        char temp[1500];
        snprintf(temp, sizeof(temp), "%s.partial-%lu", cache, pid);
        if (!obor_storage_track(temp)) { mz_zip_reader_end(&za); return 0; }
        mkdir_p(temp);
        if (!obor_storage_directory(temp)) { mz_zip_reader_end(&za); return 0; }
        int extracted = 0;
        for (unsigned i = 0; i < n; i++) {
            mz_zip_archive_file_stat st;
            char nm[512], low[512], rel[600] = "";
            if (!mz_zip_reader_file_stat(&za, i, &st) || st.m_is_directory)
                continue;
            if (!obor_zip_safe_name(st.m_filename, nm, sizeof(nm))) goto unsafe;
            obor_zip_lower(nm, low, sizeof(low));
            if (strstr(low, "__macosx/")) continue;
            if (npak) {
                size_t ln = strlen(low);
                if (ln > 4 && strcmp(low + ln - 4, ".pak") == 0) {
                    const char *b = strrchr(nm, '/');
                    snprintf(rel, sizeof(rel), "%s", b ? b + 1 : nm);
                } else if (ln > 4 && strcmp(low + ln - 4, ".exe") == 0 &&
                           st.m_uncomp_size < (16U << 20)) {
                    const char *b = strrchr(nm, '/');
                    snprintf(rel, sizeof(rel), "%s", b ? b + 1 : nm);
                }
            } else if (strncasecmp(nm, root, strlen(root)) == 0) {
                snprintf(rel, sizeof(rel), "%s", nm + strlen(root));
            }
            if (!rel[0] || !obor_zip_safe_name(rel, low, sizeof(low))) continue;
            char dst[2200];
            snprintf(dst, sizeof(dst), "%s/%s", temp, rel);
            obor_zip_mkparents(dst);
            if (!mz_zip_reader_extract_to_file(&za, i, dst, 0)) {
                log_cb(RETRO_LOG_ERROR, "[OpenBOR] zip: extraction failed\n");
                mz_zip_reader_end(&za);
                return 0;
            }
            extracted++;
        }
        if (!extracted) goto unsafe;
        char temp_marker[1600];
        snprintf(temp_marker, sizeof(temp_marker), "%s/.complete", temp);
        FILE *m = fopen(temp_marker, "wb");
        if (!m) { mz_zip_reader_end(&za); return 0; }
        fprintf(m, "oborzip-v2 %s\n", hash);
        if (fclose(m) != 0) { mz_zip_reader_end(&za); return 0; }
        if (rename(temp, cache) != 0 &&
            (!obor_storage_directory(cache) || !obor_zip_marker_ok(marker, hash))) {
            log_cb(RETRO_LOG_ERROR, "[OpenBOR] zip: cannot publish cache\n");
            mz_zip_reader_end(&za);
            return 0;
        }
        log_cb(RETRO_LOG_INFO, "[OpenBOR] zip: extracted %d files\n", extracted);
    } else {
        log_cb(RETRO_LOG_INFO, "[OpenBOR] zip: using SHA-256 cache\n");
    }
    mz_zip_reader_end(&za);

    if (npak) {
        const char *b = strrchr(pak_entry, '/');
        snprintf(out, out_cap, "%s/%s", cache, b ? b + 1 : pak_entry);
    } else {
        snprintf(out, out_cap, "%s/%s", cache, models_entry);
    }
    return 1;

unsafe:
    log_cb(RETRO_LOG_ERROR, "[OpenBOR] zip: unsafe path, link or size quota\n");
    mz_zip_reader_end(&za);
    return 0;
}

#endif
