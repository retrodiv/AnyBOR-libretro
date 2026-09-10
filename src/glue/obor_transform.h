/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_TRANSFORM_H
#define OBOR_TRANSFORM_H
#include "obor_transform_vm.h"
#include "obor_sha256.h"
#include <errno.h>

struct obor_input_transform {
    unsigned char *program, *parameters;
    size_t program_size, parameter_size;
    obor_input_transform() : program(NULL), parameters(NULL), program_size(0), parameter_size(0) {}
    ~obor_input_transform() { free(program); free(parameters); }
private:
    obor_input_transform(const obor_input_transform &);
    obor_input_transform &operator=(const obor_input_transform &);
};

/* Only the frontend's explicit system directory supplies configuration. The
 * compiler owns multiline functions, so section-shaped text in a comment or
 * string cannot escape into INI syntax. Parse everything before execution. */
static bool obor_transform_parse(const char *text, size_t size, obor_input_transform &input,
                                  char *error, size_t capacity)
{
    char names[OBOR_TRANSFORM_MAX_PROGRAMS][64] = {{0}};
    unsigned count = 0;
    bool active = false, seen = false;
    size_t at = size >= 3 && !memcmp(text, "\xef\xbb\xbf", 3) ? 3 : 0;
    unsigned char *selected = NULL, *parameters = NULL;
    size_t selected_size = 0, parameter_size = 0;
    if (size > OBOR_TRANSFORM_MAX_CONFIG_BYTES || memchr(text, 0, size)) goto invalid;
    while (at < size) {
        size_t start = at, end;
        while (at < size && text[at] != '\r' && text[at] != '\n') ++at;
        end = at;
        while (at < size && (text[at] == '\r' || text[at] == '\n')) ++at;
        while (start < end && (text[start] == ' ' || text[start] == '\t')) ++start;
        while (end > start && (text[end-1] == ' ' || text[end-1] == '\t')) --end;
        if (start == end || text[start] == '#' || text[start] == ';') continue;
        if (text[start] == '[') {
            if (text[end-1] != ']') goto invalid;
            active = end-start == 12 && !memcmp(text+start, "[transforms]", 12);
            if (active && seen) goto invalid;
            seen |= active;
            continue;
        }
        if (!active) continue;
        const char *equal = (const char *)memchr(text+start, '=', end-start);
        if (!equal || count == OBOR_TRANSFORM_MAX_PROGRAMS) goto invalid;
        size_t n = (size_t)(equal-text)-start;
        while (n && (text[start+n-1] == ' ' || text[start+n-1] == '\t')) --n;
        if (!n || n >= sizeof(names[0])) goto invalid;
        for (size_t i = 0; i < n; ++i) {
            char c = text[start+i];
            if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '.' || c == '_' || c == '-')) goto invalid;
        }
        memcpy(names[count], text+start, n);
        for (unsigned i = 0; i < count; ++i) if (!strcmp(names[i], names[count])) goto invalid;
        unsigned char *code = NULL, *params = NULL;
        size_t consumed = 0, code_size = 0, params_size = 0;
        const char *source = equal+1;
        if (!obor_content_transform_compile(source, size-(size_t)(source-text), &consumed,
                &code, &code_size, &params, &params_size, error, capacity)) goto invalid;
        if (!strcmp(names[count], "input")) {
            selected = code; selected_size = code_size;
            parameters = params; parameter_size = params_size;
        } else { free(code); free(params); }
        ++count;
        at = (size_t)(source-text)+consumed;
        while (at < size && (text[at] == ' ' || text[at] == '\t')) ++at;
        if (at < size && text[at] != '\r' && text[at] != '\n') goto invalid;
    }
    free(input.program); free(input.parameters);
    input.program = selected; input.program_size = selected_size;
    input.parameters = parameters; input.parameter_size = parameter_size;
    return true;
invalid:
    free(selected); free(parameters);
    if (capacity && !error[0]) snprintf(error, capacity, "malformed transform configuration");
    return false;
}

static bool obor_transform_load(const char *system_dir, obor_input_transform &input)
{
    if (!system_dir || !system_dir[0]) return true;
    char path[4096], error[256] = {0};
    int n = snprintf(path, sizeof(path), "%s/AnyBOR.ini", system_dir);
    if (n < 0 || (size_t)n >= sizeof(path)) return false;
    FILE *fp = fopen(path, "rb");
    if (!fp) {
        if (errno == ENOENT) return true;
        log_cb(RETRO_LOG_ERROR, "[OpenBOR] Cannot read %s\n", path);
        return false;
    }
    char *text = (char *)malloc(OBOR_TRANSFORM_MAX_CONFIG_BYTES + 1u);
    if (!text) { fclose(fp); return false; }
    size_t size = fread(text, 1, OBOR_TRANSFORM_MAX_CONFIG_BYTES + 1u, fp);
    bool ok = !ferror(fp) && size <= OBOR_TRANSFORM_MAX_CONFIG_BYTES;
    fclose(fp);
    if (ok) ok = obor_transform_parse(text, size, input, error, sizeof(error));
    free(text);
    if (!ok) log_cb(RETRO_LOG_ERROR, "[OpenBOR] %s: %s\n", path,
                    error[0] ? error : "oversized or unreadable configuration");
    return ok;
}

static void obor_transform_identity(const obor_input_transform &input, char hex[65])
{
    obor_sha256_ctx ctx;
    unsigned char digest[32];
    obor_sha256_init(&ctx);
    obor_sha256_update(&ctx, "buffer-transform-v1", 19);
    /* Compiled instructions have a fixed width; this boundary is explicit. */
    unsigned char size[8];
    for (unsigned i = 0; i < 8; ++i) size[i] = (unsigned char)((uint64_t)input.program_size >> (i*8));
    obor_sha256_update(&ctx, size, sizeof(size));
    obor_sha256_update(&ctx, input.program, input.program_size);
    obor_sha256_update(&ctx, input.parameters, input.parameter_size);
    obor_sha256_final(&ctx, digest);
    for (unsigned i = 0; i < 32; ++i) snprintf(hex+i*2, 3, "%02x", digest[i]);
}
#endif
