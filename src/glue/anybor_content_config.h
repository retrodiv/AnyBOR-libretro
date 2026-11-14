/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_CONTENT_CONFIG_H
#define OBOR_CONTENT_CONFIG_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "anybor_zip_path.h"

#define OBOR_OVERRIDE_MAX_RULES 256U
#define OBOR_DESCRIPTOR_MAX_BYTES 65536U
struct obor_override_rule { uint64_t size; char hash[33], engine[48]; };
struct obor_content_rules {
    obor_override_rule rows[OBOR_OVERRIDE_MAX_RULES];
    unsigned count;
    obor_content_rules() : rows(), count(0) {}
};
struct obor_content_choice {
    char source[4096], engine[48], descriptor[4096];
    obor_content_choice() : source(), engine(), descriptor() {}
};
struct obor_descriptor { char payload[512], engine[48]; };

static bool obor_content_suffix(const char *path, const char *suffix)
{
    size_t n = strlen(path), m = strlen(suffix);
    return n >= m && !strcasecmp(path + n - m, suffix);
}
static bool obor_content_engine_value(const char *value)
{
    const unsigned char *p = (const unsigned char *)value;
    if (*p == 'v' || *p == 'V') {
        ++p;
        if (!isdigit(*p)) return false;
        while (isdigit(*p)) ++p;
        if (*p++ != '.' || !isdigit(*p)) return false;
        while (isdigit(*p)) ++p;
        if (*p++ != ' ') return false;
    }
    if (*p < '1' || *p > '9') return false;
    while (isdigit(*p)) ++p;
    if (*p == '-') {
        ++p;
        if (!isalnum(*p)) return false;
        while (isalnum(*p) || *p == '-') ++p;
    }
    return !*p && strlen(value) < 48;
}
/* Called by the transform-aware INI scanner; multiline functions retain their
 * own grammar and cannot introduce configuration sections from a string. */
static bool obor_content_rule_section(const char *text, size_t n, obor_content_rules &rules)
{
    const char prefix[] = "[imohash:", suffix[] = ".overrides]";
    if (n < sizeof(prefix) + sizeof(suffix) + 32 ||
        strncmp(text, prefix, sizeof(prefix)-1) ||
        memcmp(text + n - (sizeof(suffix)-1), suffix, sizeof(suffix)-1) ||
        rules.count == OBOR_OVERRIDE_MAX_RULES) return false;
    size_t at = sizeof(prefix)-1;
    uint64_t size = 0;
    if (text[at] < '1' || text[at] > '9') return false;
    while (at < n && text[at] >= '0' && text[at] <= '9') {
        unsigned digit = (unsigned)(text[at++] - '0');
        if (size > (UINT64_MAX - digit) / 10) return false;
        size = size * 10 + digit;
    }
    if (at >= n || text[at++] != ':' || n-at != 32 + sizeof(suffix)-1) return false;
    obor_override_rule rule = {};
    rule.size = size;
    for (unsigned i = 0; i < 32; ++i) {
        unsigned char c = (unsigned char)text[at+i];
        if (!isxdigit(c)) return false;
        rule.hash[i] = (char)tolower(c);
    }
    for (unsigned i = 0; i < rules.count; ++i)
        if (rules.rows[i].size == size && !strcmp(rules.rows[i].hash, rule.hash)) return false;
    rules.rows[rules.count++] = rule;
    return true;
}
static bool obor_content_engine_line(const char *text, size_t n, char engine[48])
{
    const char *equal = (const char *)memchr(text, '=', n);
    if (!equal || engine[0]) return false;
    size_t key = (size_t)(equal-text), at = key+1, end = n;
    while (key && (text[key-1]==' ' || text[key-1]=='\t')) --key;
    while (at < end && (text[at]==' ' || text[at]=='\t')) ++at;
    while (end > at && (text[end-1]==' ' || text[end-1]=='\t')) --end;
    if (key != 6 || memcmp(text, "engine", 6) || end-at >= 48) return false;
    memcpy(engine, text+at, end-at); engine[end-at] = 0;
    return obor_content_engine_value(engine);
}
static bool obor_descriptor_parse(const char *text, size_t size, obor_descriptor &out)
{
    obor_descriptor parsed = {};
    if (!size || size > OBOR_DESCRIPTOR_MAX_BYTES || memchr(text, 0, size)) return false;
    unsigned section = 0, seen = 0;
    size_t at = size >= 3 && !memcmp(text, "\xef\xbb\xbf", 3) ? 3 : 0;
    while (at < size) {
        size_t first = at, end;
        while (at < size && text[at]!='\r' && text[at]!='\n') ++at;
        end = at;
        while (at < size && (text[at]=='\r' || text[at]=='\n')) ++at;
        while (first < end && (text[first]==' ' || text[first]=='\t')) ++first;
        while (end > first && (text[end-1]==' ' || text[end-1]=='\t')) --end;
        if (first==end || text[first]=='#' || text[first]==';') continue;
        size_t n = end-first;
        const char *line = text+first;
        if (line[0]=='[') {
            section = n==8 && !memcmp(line,"[anybor]",8) ? 1 :
                      n==11 && !memcmp(line,"[overrides]",11) ? 2 : 0;
            if (!section || (seen & section)) return false;
            seen |= section;
        } else if (section==2) {
            if (!obor_content_engine_line(line,n,parsed.engine)) return false;
        } else if (section==1) {
            const char *eq = (const char *)memchr(line,'=',n);
            if (!eq || parsed.payload[0]) return false;
            size_t key = (size_t)(eq-line), value = key+1;
            while (key && (line[key-1]==' ' || line[key-1]=='\t')) --key;
            while (value<n && (line[value]==' ' || line[value]=='\t')) ++value;
            if (key!=7 || memcmp(line,"payload",7) || n-value>=sizeof(parsed.payload)) return false;
            char path[512];
            memcpy(path,line+value,n-value); path[n-value]=0;
            if (!obor_zip_safe_name(path,parsed.payload,sizeof(parsed.payload)) ||
                (!obor_content_suffix(parsed.payload,".pak") &&
                 !obor_content_suffix(parsed.payload,".spk"))) return false;
        } else return false;
    }
    if (!parsed.payload[0] || ((seen & 2) && !parsed.engine[0])) return false;
    out = parsed;
    return true;
}
#endif
