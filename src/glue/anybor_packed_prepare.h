/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PACKED_PREPARE_H
#define OBOR_PACKED_PREPARE_H
#include "anybor_file_io.h"
#include "anybor_pak_repair.h"
#include "anybor_transform.h"
#include "anybor_prepared_cache.h"

struct obor_transform_buffers {
    unsigned char *input;
    obor_transform_result result;
    obor_transform_buffers() : input(NULL), result() {}
    ~obor_transform_buffers() {
        obor_content_transform_result_release(&result);
        free(input);
    }
};

/* Large inputs stay on disk. VM loads request only the bytes they inspect;
 * readonly passthrough therefore has bounded memory independent of PAK size. */
struct obor_transform_file {
    FILE *file;
    uint64_t size, offset;
    size_t available;
    unsigned char *cache;
    obor_transform_file(FILE *input, uint64_t bytes)
        : file(input), size(bytes), offset(0), available(0), cache(NULL) {}
    ~obor_transform_file() { free(cache); }
    static int read(void *opaque, uint64_t at, void *data, size_t bytes) {
        obor_transform_file &source = *(obor_transform_file *)opaque;
        if (at > source.size || bytes > source.size-at) return 0;
        unsigned char *out = (unsigned char *)data;
        if (!source.cache && bytes) source.cache = (unsigned char *)malloc(65536);
        if (!source.cache && bytes) return 0;
        while (bytes) {
            if (!source.available || at < source.offset || at-source.offset >= source.available) {
                source.offset = at & ~UINT64_C(65535);
                size_t amount = (size_t)((source.size-source.offset) < 65536 ? source.size-source.offset : 65536);
                if (obor_file_seek64(source.file, (int64_t)source.offset, SEEK_SET) ||
                    fread(source.cache, 1, amount, source.file) != amount || !obor_prepare_checkpoint()) return 0;
                source.available = amount;
            }
            size_t within = (size_t)(at-source.offset);
            size_t amount = source.available-within;
            if (amount > bytes) amount = bytes;
            memcpy(out, source.cache+within, amount);
            out += amount; at += amount; bytes -= amount;
        }
        return 1;
    }
};

static bool obor_packed_cache_matches(const char *cache, const char *key, const char *result)
{
    FILE *marker = obor_prepared_marker(cache, key);
    if (!marker) return false;
    obor_prepared_sample sample;
    bool ok = obor_prepared_sample_path(result, sample);
    if (ok) {
        char row[640];
        obor_prepared_row(sample, "PACK", row);
        ok = obor_prepared_line_matches(marker, row) && fgetc(marker) == EOF && !ferror(marker);
    }
    return !fclose(marker) && ok;
}

/* Generic byte preparation followed by the ordinary PACK validator. No
 * encoded-format signature, recipe or automatic decoder is built in. */
static bool obor_packed_prepare(const char *source, const char *save_dir,
                                const char *system_dir, char *out, size_t out_cap,
                                const char *transform_key = NULL,
                                const obor_content_function *function = NULL)
{
    obor_prepare_range progress = obor_prepare_phase;
    obor_input_transform transform;
    FILE *input = obor_fopen(source, "rb");
    if (!input) return false;
    bool header_repair = obor_pak_header_repair_detect(input) != 0;
    /* A complete plain PACK structure takes precedence over an unrelated
     * external transform, including a malformed or unavailable configuration. */
    bool local=function && function->program_size;
    if (local && obor_pak_validate(source)) {
        fclose(input);
        log_cb(RETRO_LOG_ERROR,"[OpenBOR] Descriptor function requires an ordinary PACK input.\n");
        return false;
    }
    if (!header_repair && local) {
        if (function->program_size>OBOR_TRANSFORM_MAX_PROGRAM_BYTES ||
            function->parameter_size>OBOR_TRANSFORM_MAX_PARAMETER_BYTES) { fclose(input);return false; }
        transform.program=(unsigned char *)malloc(function->program_size);
        transform.parameters=(unsigned char *)malloc(function->parameter_size ? function->parameter_size : 1u);
        if (!transform.program || !transform.parameters) { fclose(input);return false; }
        memcpy(transform.program,function->program,function->program_size);
        memcpy(transform.parameters,function->parameters,function->parameter_size);
        transform.program_size=function->program_size;transform.parameter_size=function->parameter_size;
    } else if (!header_repair && !obor_transform_load(system_dir, transform, transform_key)) {
        fclose(input);
        return false;
    }
    if (header_repair && (local || (transform_key && *transform_key))) {
        fclose(input);
        log_cb(RETRO_LOG_ERROR,"[OpenBOR] Named transform requires an ordinary PACK input.\n");
        return false;
    }
    int64_t bias = 0;
    bool repair = !header_repair && !transform.program && obor_pak_repair_detect(input, &bias);
    if (!transform.program && !repair && !header_repair) {
        fclose(input);
        int n = snprintf(out, out_cap, "%s", source);
        return n >= 0 && (size_t)n < out_cap;
    }
    char parent[1400], cache[1600], key[65], recipe[65], error[256] = {0};
    obor_prepared_sample original;
    if (!obor_prepared_sample_file(input, original) ||
        original.size > OBOR_TRANSFORM_MAX_READER_BYTES || original.size > SIZE_MAX ||
        !obor_storage_join(parent, sizeof(parent), save_dir, "AnyBOR-cache")) {
        fclose(input);
        return false;
    }
    if (transform.program) obor_transform_identity(transform, recipe);
    else snprintf(recipe, sizeof(recipe), "%s",
                  header_repair ? "pack-header-repair-v1" : "directory-rebase-v2");
    const char *base = strrchr(source, '/'), *backslash = strrchr(source, '\\');
    if (!base || (backslash && backslash > base)) base = backslash;
    base = base ? base + 1 : source;
    auto locate = [&]() {
        obor_prepared_key("PACK", original, base, strlen(base), recipe, key);
        return obor_prepared_slot(parent, "input", 8, key, cache, sizeof(cache)) &&
            obor_storage_join(out, out_cap, cache, base);
    };
    auto matches = [&]() {
        return obor_storage_directory(parent) && obor_packed_cache_matches(cache, key, out);
    };
    auto reused = [&]() {
        fclose(input);
        if (!obor_storage_track(cache)) return false;
        log_cb(RETRO_LOG_INFO, "[OpenBOR] Reusing prepared PACK.\n");
        return true;
    };
    bool located = locate();
    if (located && matches()) return reused();
    size_t bytes = (size_t)original.size;
    bool streamed = original.size > OBOR_TRANSFORM_MAX_INPUT_BYTES;
    obor_transform_file reader(input, original.size);
    obor_transform_buffers buffers;
    if (transform.program) {
        obor_prepare_stage(progress, 0, 100, bytes);
        if (!streamed) buffers.input = (unsigned char *)malloc(bytes ? (size_t)bytes : 1u);
        bool ok = streamed || (buffers.input && !obor_file_seek64(input, 0, SEEK_SET));
        for (size_t offset = 0; !streamed && ok && offset < (size_t)bytes;) {
            size_t chunk = (size_t)bytes - offset;
            if (chunk > 65536) chunk = 65536;
            ok = fread(buffers.input + offset, 1, chunk, input) == chunk;
            if (ok) { obor_prepare_advance(chunk); ok = obor_prepare_checkpoint(); }
            offset += chunk;
        }
        /* The external program's running time is unknown: hold this phase
         * until it returns instead of fabricating progress from its clock. */
        obor_prepare_stage(progress, 100, 200, 0);
        if (ok) {
            if (streamed) ok = obor_content_transform_execute_reader(transform.program, transform.program_size,
                transform.parameters, transform.parameter_size, obor_transform_file::read, &reader, (uint64_t)bytes,
                NULL, 0, 0, &buffers.result, error, sizeof(error)) != 0;
            else ok = obor_content_transform_execute_view(transform.program, transform.program_size,
                transform.parameters, transform.parameter_size, buffers.input, (size_t)bytes, NULL, 0, 0,
                &buffers.result, error, sizeof(error)) != 0;
        }
        if (!ok) {
            fclose(input);
            log_cb(RETRO_LOG_ERROR, "[OpenBOR] Content preparation failed: %s\n",
                   error[0] ? error : "cannot read transform input");
            return false;
        }
        bool unchanged = buffers.result.reader_view ?
            !buffers.result.input_offset && buffers.result.size == (size_t)bytes :
            buffers.input && buffers.result.size == (size_t)bytes && !memcmp(buffers.input, buffers.result.data, buffers.result.size);
        if (unchanged) {
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
        if (repair) {
            /* A declined transform has no cached result. The structural
             * repair has its own recipe and may be used after the decline. */
            snprintf(recipe, sizeof(recipe), "directory-rebase-v2");
            if (!locate()) { fclose(input); return false; }
            if (matches()) return reused();
        }
        if (buffers.result.owned) { free(buffers.input); buffers.input = NULL; }
    }
    if (!located || !obor_storage_root(save_dir, parent, sizeof(parent)) ||
        !obor_zip_space_ok(parent, original.size + (64u << 20))) { fclose(input); return false; }
    obor_prepared_staging staging;
    char temp[4096];
    if (!staging.create(parent, ".partial") ||
        !obor_storage_join(temp, sizeof(temp), staging.path, base)) { fclose(input); return false; }
    FILE *output = obor_fopen(temp, "wb");
    if (!output) { fclose(input); return false; }
    bool ok = false;
    obor_prepare_stage(progress, transform.program ? 350 : 200,
                       transform.program ? 500 : 400,
                       (header_repair || repair) ? (uint64_t)bytes : buffers.result.size);
    if (header_repair) {
        ok = obor_pak_repair_header(input, output) != 0;
    } else if (repair) {
        ok = obor_pak_repair_bias(input, output, bias) != 0;
    } else {
        ok = true;
        unsigned char block[65536];
        for (size_t offset = 0; ok && offset < buffers.result.size;) {
            size_t chunk = buffers.result.size - offset;
            if (chunk > 65536) chunk = 65536;
            const unsigned char *data;
            if (buffers.result.reader_view) {
                ok = obor_transform_file::read(&reader, buffers.result.input_offset+offset, block, chunk) != 0;
                data = block;
            } else data = buffers.result.data + offset;
            if (ok) ok = fwrite(data, 1, chunk, output) == chunk;
            if (ok) { obor_prepare_advance(chunk); ok = obor_prepare_checkpoint(); }
            offset += chunk;
        }
    }
    fclose(input);
    /* Finish the generated input's writeback before publishing it for engine
     * streaming. The cooperative helper keeps the loading screen responsive
     * and retains no worker or extra content cache after preparation. */
    if (ok && !obor_prepare_sync_file(output)) ok = false;
    if (fclose(output)) ok = false;
    /* Selected transforms never bypass result validation or reuse an old
     * decoded file when their configuration is absent, changed or invalid. */
    if (ok && obor_pak_validate(temp)) ok = false;
    obor_prepared_sample prepared, current;
    if (ok) {
        obor_prepare_stage(progress, transform.program ? 500 : 400, 800, 0);
        ok = obor_prepared_sample_path(temp, prepared);
    }
    if (ok) {
        FILE *original_file = obor_fopen(source, "rb");
        ok = original_file && obor_prepared_sample_file(original_file, current) &&
            obor_prepared_equal(original, current);
        if (original_file && fclose(original_file)) ok = false;
    }
    if (!ok) {
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] Content preparation failed: %s\n",
               error[0] ? error : "invalid PACK result or source changed");
        return false;
    }
    obor_prepare_stage(progress, 800, 1000, 0);
    FILE *marker = obor_prepared_create_marker(staging.path, key);
    if (!marker) return false;
    char row[640];
    obor_prepared_row(prepared, "PACK", row);
    ok = fputs(row, marker) >= 0 && obor_prepare_sync_file(marker);
    if (fclose(marker)) ok = false;
    if (!ok || !locate() || !obor_prepared_publish(staging, cache, key, matches) ||
        !obor_storage_track(cache)) return false;
    log_cb(RETRO_LOG_INFO, "[OpenBOR] %s: validated prepared PACK\n",
           header_repair ? "structural header repair" :
           repair ? "structural directory repair" : "configured input transform");
    return true;
}
#endif
