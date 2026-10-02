/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_LEGACY_API_H
#define OBOR_LEGACY_API_H
#include "obor_pak_validate.h"
#include <stdlib.h>
#include <ctype.h>
#include "obor_detection_clock.h"

/* Skip whitespace/comments without interpreting quoted data as code. */
static size_t obor_script_space(const char *s, size_t n, size_t p)
{
    for (;;) {
        while (p < n && isspace((unsigned char)s[p])) ++p;
        if (p + 1 < n && s[p] == '/' && s[p + 1] == '/') {
            while (p < n && s[p] != '\n' && s[p] != '\r') ++p;
        } else if (p + 1 < n && s[p] == '/' && s[p + 1] == '*') {
            p += 2;
            while (p + 1 < n && !(s[p] == '*' && s[p + 1] == '/')) ++p;
            if (p + 1 >= n) return n;
            p += 2;
        } else return p;
    }
}

static size_t obor_script_quote(const char *s, size_t n, size_t p)
{
    char quote = s[p++];
    while (p < n) {
        if (s[p] == '\\') { p += p + 1 < n ? 2 : 1; continue; }
        if (s[p++] == quote) break;
    }
    return p;
}

/* The legacy getentityproperty(..., "attack", ...) API is present through
 * pinned build 4086 and absent in 4432, 6391 and 8023. Those later compilers
 * reject it, whereas model-command vocabulary can merely be ignored by an
 * older parser. This is an API-support constraint, not content identity.
 * Recognize a literal second argument, including nested first arguments. */
static int obor_script_legacy_build(const char *s, size_t n,
                                  const uint64_t *scan_started = NULL)
{
    size_t p = 0;
    size_t deadline_check = 4096;
    const auto started = scan_started ? *scan_started : obor_detection_now();
    while ((p = obor_script_space(s, n, p)) < n) {
        if (p >= deadline_check) {
            if (obor_detection_expired(started)) return 0;
            deadline_check = p + 4096;
        }
        if (s[p] == '"' || s[p] == '\'') { p = obor_script_quote(s, n, p); continue; }
        if (!isalpha((unsigned char)s[p]) && s[p] != '_') { ++p; continue; }
        size_t start = p++;
        while (p < n && (isalnum((unsigned char)s[p]) || s[p] == '_')) ++p;
        if (p - start != 17 || memcmp(s + start, "getentityproperty", 17)) continue;
        size_t q = obor_script_space(s, n, p);
        if (q == n || s[q++] != '(') continue;
        /* Nested or generated arguments beyond this lookahead are inconclusive.
         * This prevents repeated nested calls from making the scan quadratic. */
        size_t lookahead_end = n - q > 4096 ? q + 4096 : n;
        unsigned depth = 1;
        for (;;) {
            q = obor_script_space(s, lookahead_end, q);
            if (q >= lookahead_end) break;
            if (s[q] == '"' || s[q] == '\'') { q = obor_script_quote(s, lookahead_end, q); continue; }
            if (s[q] == '(' || s[q] == '[' || s[q] == '{') ++depth;
            else if (s[q] == ')' || s[q] == ']' || s[q] == '}') {
                if (!--depth) break;
            } else if (s[q] == ',' && depth == 1) {
                q = obor_script_space(s, lookahead_end, q + 1);
                if (lookahead_end - q >= 8 && !memcmp(s + q, "\"attack\"", 8)) {
                    q = obor_script_space(s, lookahead_end, q + 8);
                    if (q < lookahead_end && (s[q] == ',' || s[q] == ')')) return 4086;
                }
                break;
            }
            ++q;
        }
    }
    return 0;
}

/* Called after PACK validation. Inspect bounded script sources only; names
 * and bytes do not select a game-specific profile. */
static int obor_legacy_api_build(const char *path)
{
    FILE *fp = fopen(path, "rb");
    unsigned char h[12];
    char name[256], *source = NULL;
    long end;
    unsigned budget = 16u << 20, count = 0;
    int build = 0;
    const auto started = obor_detection_now();
    if (!fp) return 0;
    if (fseek(fp, -4, SEEK_END) || (end = ftell(fp)) < 8 ||
        fread(h, 1, 4, fp) != 4 || fseek(fp, obor_pak_u32(h), SEEK_SET)) goto done;
    source = (char *)malloc(2u << 20);
    if (!source) goto done;
    while (ftell(fp) < end && count < 800) {
        if (obor_detection_expired(started)) break;
        if (fread(h, 1, 12, fp) != 12) break;
        unsigned length = obor_pak_u32(h), start = obor_pak_u32(h + 4), size = obor_pak_u32(h + 8);
        if (length < 14 || length > 268 || fread(name, 1, length - 12, fp) != length - 12) break;
        name[length - 13] = 0;
        size_t n = strlen(name);
        if (n < 3 || name[n - 2] != '.' ||
            (tolower((unsigned char)name[n - 1]) != 'c' && tolower((unsigned char)name[n - 1]) != 'h') ||
            size > (2u << 20) || size > budget) continue;
        long next = ftell(fp);
        ++count; budget -= size;
        if (fseek(fp, start, SEEK_SET) || fread(source, 1, size, fp) != size) break;
        build = obor_script_legacy_build(source, size, &started);
        if (build || fseek(fp, next, SEEK_SET)) break;
    }
done:
    free(source);
    fclose(fp);
    return build;
}
#endif
