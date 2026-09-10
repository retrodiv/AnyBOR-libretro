/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PACKED_PREPARE_H
#define OBOR_PACKED_PREPARE_H
#include "obor_pak_repair.h"
#include "obor_transform.h"
#include <fcntl.h>

struct obor_transform_buffers {
    unsigned char *input, *output;
    size_t size;
    obor_transform_buffers() : input(NULL), output(NULL), size(0) {}
    ~obor_transform_buffers() { free(input); free(output); }
};

/* Generic byte preparation followed by the ordinary PACK validator. No
 * encoded-format signature, recipe or automatic decoder is built in. */
static bool obor_packed_prepare(const char *source, const char *save_dir,
                                const char *system_dir, char *out, size_t out_cap)
{
    obor_input_transform transform;
    if (!obor_transform_load(system_dir, transform)) return false;
    FILE *input = fopen(source, "rb");
    if (!input) return false;
    int64_t bias = 0;
    bool repair = !transform.program && obor_pak_repair_detect(input, &bias);
    if (!transform.program && !repair) {
        fclose(input);
        int n = snprintf(out, out_cap, "%s", source);
        return n >= 0 && (size_t)n < out_cap;
    }
    char source_hash[65], config_hash[65], result_hash[65], current_hash[65];
    char parent[1400], cache[1800], temp[1500], error[256] = {0};
    if (fseek(input, 0, SEEK_END)) { fclose(input); return false; }
    long bytes = ftell(input);
    if (bytes < 0 || (uint64_t)bytes > OBOR_TRANSFORM_MAX_INPUT_BYTES) { fclose(input); return false; }
    obor_transform_buffers buffers;
    if (transform.program) {
        buffers.input = (unsigned char *)malloc(bytes ? (size_t)bytes : 1u);
        bool ok = buffers.input && !fseek(input, 0, SEEK_SET) &&
                  fread(buffers.input, 1, (size_t)bytes, input) == (size_t)bytes;
        if (ok) ok = obor_content_transform_execute(transform.program, transform.program_size,
            transform.parameters, transform.parameter_size, buffers.input, (size_t)bytes, NULL, 0, 0,
            &buffers.output, &buffers.size, error, sizeof(error)) != 0;
        if (!ok) {
            fclose(input);
            log_cb(RETRO_LOG_ERROR, "[OpenBOR] Content preparation failed: %s\n",
                   error[0] ? error : "cannot read transform input");
            return false;
        }
        if (buffers.size == (size_t)bytes && !memcmp(buffers.input, buffers.output, buffers.size)) {
            repair = obor_pak_repair_detect(input, &bias) != 0;
            if (!repair) {
                /* The transform declined this input. Keep the ordinary
                 * source path and its normal pre-boot validator, without
                 * writing or hashing an unnecessary full archive copy. */
                fclose(input);
                int n = snprintf(out, out_cap, "%s", source);
                return n >= 0 && (size_t)n < out_cap;
            }
        }
        /* Identify the exact bytes the VM saw, then recheck the source
         * before publishing a prepared result. */
        obor_sha256_ctx hash;
        unsigned char digest[32];
        obor_sha256_init(&hash);
        obor_sha256_update(&hash, buffers.input, (size_t)bytes);
        obor_sha256_final(&hash, digest);
        for (unsigned i = 0; i < 32; ++i) snprintf(source_hash + 2*i, 3, "%02x", digest[i]);
        free(buffers.input); buffers.input = NULL;
        obor_transform_identity(transform, config_hash);
    } else {
        if (!obor_sha256_file(source, source_hash)) { fclose(input); return false; }
        snprintf(config_hash, sizeof(config_hash), "directory-rebase-v2");
    }
    int n = snprintf(parent, sizeof(parent), "%s/AnyBOR/prepared-v1", save_dir);
    if (n < 0 || (size_t)n >= sizeof(parent)) { fclose(input); return false; }
    mkdir_p(parent);
    if (!obor_zip_space_ok(parent, (uint64_t)bytes + (64u << 20))) { fclose(input); return false; }
#if defined(_WIN32)
    unsigned long pid = (unsigned long)GetCurrentProcessId();
#else
    unsigned long pid = (unsigned long)getpid();
#endif
    static unsigned sequence;
    n = snprintf(temp, sizeof(temp), "%s/.partial-%lu-%u", parent, pid, ++sequence);
    if (n < 0 || (size_t)n >= sizeof(temp)) { fclose(input); return false; }
    int fd = open(temp, O_WRONLY | O_CREAT | O_EXCL
#if defined(_WIN32)
        | O_BINARY
#endif
        , 0600);
    if (fd < 0) { fclose(input); return false; }
    FILE *output = fdopen(fd, "wb");
    if (!output) { close(fd); remove(temp); fclose(input); return false; }
    bool ok = false;
    if (repair) {
        ok = obor_pak_repair_bias(input, output, bias) != 0;
    } else {
        ok = fwrite(buffers.output, 1, buffers.size, output) == buffers.size;
    }
    fclose(input);
    if (fclose(output)) ok = false;
    /* Selected transforms never bypass result validation or reuse an old
     * decoded file when their configuration is absent, changed or invalid. */
    if (ok && obor_pak_validate(temp)) ok = false;
    if (ok) ok = obor_sha256_file(temp, result_hash) && obor_sha256_file(source, current_hash) &&
                 !strcmp(source_hash, current_hash);
    if (!ok) {
        remove(temp);
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] Content preparation failed: %s\n", error[0] ? error : "invalid PACK result or source changed");
        return false;
    }
    /* An identity transform retains ordinary structural repair and the
     * original content path. It is applied exactly once. */
    if (!strcmp(source_hash, result_hash)) {
        remove(temp);
        n = snprintf(out, out_cap, "%s", source);
        return n >= 0 && (size_t)n < out_cap;
    }
    obor_sha256_ctx identity;
    unsigned char digest[32];
    char key[65];
    obor_sha256_init(&identity);
    obor_sha256_update(&identity, source_hash, strlen(source_hash) + 1);
    obor_sha256_update(&identity, config_hash, strlen(config_hash) + 1);
    obor_sha256_update(&identity, result_hash, strlen(result_hash) + 1);
    obor_sha256_final(&identity, digest);
    for (unsigned i = 0; i < 32; ++i) snprintf(key + i*2, 3, "%02x", digest[i]);
    n = snprintf(cache, sizeof(cache), "%s/%s", parent, key);
    if (n < 0 || (size_t)n >= sizeof(cache)) { remove(temp); return false; }
    const char *base = strrchr(source, '/'), *backslash = strrchr(source, '\\');
    if (!base || (backslash && backslash > base)) base = backslash;
    base = base ? base+1 : source;
    n = snprintf(out, out_cap, "%s/%s", cache, base);
    if (n < 0 || (size_t)n >= out_cap) { remove(temp); return false; }


    mkdir_p(cache);
    if (obor_sha256_file(out, current_hash) && !strcmp(current_hash, result_hash)) {
        remove(temp);
    } else {
#if defined(_WIN32)
        ok = MoveFileExA(temp, out, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != 0;
#else
        ok = rename(temp, out) == 0;
#endif
        if (!ok) { remove(temp); return false; }
    }
    log_cb(RETRO_LOG_INFO, "[OpenBOR] %s: validated prepared PACK\n",
           repair ? "structural directory repair" : "configured input transform");
    return true;
}
#endif
