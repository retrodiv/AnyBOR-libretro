/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_CONTENT_SCAN_H
#define OBOR_CONTENT_SCAN_H
#include "obor_detection_clock.h"
#include <ctype.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "obor_markers.h"

/* Exact, syntax-scoped history facts take precedence over the older sparse
 * marker estimates. No resource names or content identities select a rule. */
struct obor_content_rule { const char *name; int lower, upper; };
static const obor_content_rule kContentCommands[] = {
    { "cameraoffset", 2048, INT_MAX },
    { "colourdepth", 1612, INT_MAX },
    { "counterframe", 1, 4258 },
    { "counterrange", 2718, INT_MAX },
    { "dropframe", 868, INT_MAX },
    { "forcemap", 1140, INT_MAX },
    { "fshadow", 1121, INT_MAX },
    { "hmap", 952, INT_MAX },
    { "keyscript", 1401, INT_MAX },
    { "landframe", 868, INT_MAX },
    { "maxattacks", 834, INT_MAX },
    { "maxattacktypes", 834, INT_MAX },
    { "maxfollows", 834, INT_MAX },
    { "maxfreespecials", 834, INT_MAX },
    { "offscreen_noatk_factor", 4404, INT_MAX },
    { "offscreenkill", 2414, INT_MAX },
    { "shadowcoords", 1121, INT_MAX },
    { "spdirection", 62, INT_MAX },
    { "stun", 1196, INT_MAX },
    { "sync", 3841, INT_MAX },
    { "vbgspeed", 4201, INT_MAX },
};
static const obor_content_rule kContentAnimations[] = {
    { "backbdie", 6303, INT_MAX },
    { "backburn", 6283, INT_MAX },
    { "ducking", 6295, INT_MAX },
    { "duckrise", 6295, INT_MAX },
    { "victory", 6301, INT_MAX },
    { "walkoff", 3398, INT_MAX },
};
static const obor_content_rule kContentConstants[] = {
    { "ani_freespecial", 3826, INT_MAX },
    { "ani_walkoff", 3466, INT_MAX },
    { "max_int", 3552, INT_MAX },
    { "min_int", 3552, INT_MAX },
    { "player_max_z", 1, 7468 },
    { "player_min_z", 1, 7468 },
    { "type_reserved", 3597, INT_MAX },
    { "vt_ptr", 3922, INT_MAX },
};
static const obor_content_rule kContentFunctions[] = {
    { "array", 3428, INT_MAX },
    { "checkrange", 1723, INT_MAX },
    { "getentityvar", 1205, INT_MAX },
    { "getindexedvar", 1205, INT_MAX },
    { "getscriptvar", 1205, INT_MAX },
    { "jumptobranch", 1262, INT_MAX },
    { "setentityvar", 1205, INT_MAX },
    { "setindexedvar", 1205, INT_MAX },
    { "setscriptvar", 1205, INT_MAX },
    { "sin", 3869, INT_MAX },
};

static int g_content_lower, g_content_upper;
static bool g_content_range_seen, g_content_scan_complete;

struct obor_content_scan {
    int lower, upper, script_lower, script_upper, hint_lower, hint_upper;
    bool seen, script_seen, ambiguous_scripts, complete;
    size_t work;
    uint64_t started;
};

/* Checks occur during lexical work as well as between reads. No regex, include
 * graph, expression evaluation, decompression, or history lookup runs here.
 * The deadline bounds processing, not a host filesystem's blocking read. */
static bool content_budget(obor_content_scan *s, size_t work)
{
    s->work += work;
    if (s->work >= 4096) {
        s->work = 0;
        if (obor_detection_expired(s->started))
            s->complete = false;
    }
    return s->complete;
}

template<size_t N>
static const obor_content_rule *content_rule(const obor_content_rule (&rules)[N], const char *name)
{
    size_t lo = 0, hi = N;
    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        int cmp = strcmp(name, rules[mid].name);
        if (!cmp) return &rules[mid];
        if (cmp < 0) hi = mid; else lo = mid + 1;
    }
    return NULL;
}

static void content_bounds(obor_content_scan *s, int lower, int upper, bool script)
{
    int *lb = script ? &s->script_lower : &s->lower;
    int *ub = script ? &s->script_upper : &s->upper;
    if (lower > *lb) *lb = lower;
    if (upper < *ub) *ub = upper;
    if (script) s->script_seen = true; else s->seen = true;
}

static void content_hint(obor_content_scan *s, const char *name)
{
    /* Sparse estimates are used only when no exact syntax-scoped rule fired. */
    size_t lo = 0, hi = sizeof(kMarkers) / sizeof(kMarkers[0]);
    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        int cmp = strcmp(name, kMarkers[mid].tok);
        if (!cmp) { if (kMarkers[mid].build > s->hint_lower) s->hint_lower = kMarkers[mid].build; break; }
        if (cmp < 0) hi = mid; else lo = mid + 1;
    }
    lo = 0; hi = sizeof(kRemovedMarkers) / sizeof(kRemovedMarkers[0]);
    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        int cmp = strcmp(name, kRemovedMarkers[mid].tok);
        if (!cmp) {
            if (!s->hint_upper || kRemovedMarkers[mid].build < s->hint_upper)
                s->hint_upper = kRemovedMarkers[mid].build;
            break;
        }
        if (cmp < 0) hi = mid; else lo = mid + 1;
    }
}

/* A tiny lexer distinguishes identifiers, literal strings and punctuation.
 * Long/escaped strings cannot become constant evidence; their full span is
 * still consumed. Comments inside quotes remain ordinary string data. */
static char content_lex(obor_content_scan *s, const char *data, size_t n, size_t *pos, char out[64])
{
    size_t p = *pos;
    for (;;) {
        while (p < n && isspace((unsigned char)data[p])) { ++p; if (!content_budget(s, 1)) break; }
        if (!s->complete || p >= n) { *pos = p; out[0] = 0; return 0; }
        if (p + 1 < n && data[p] == '/' && data[p + 1] == '/') {
            while (p < n && data[p] != '\n') { ++p; if (!content_budget(s, 1)) break; }
        } else if (p + 1 < n && data[p] == '/' && data[p + 1] == '*') {
            p += 2;
            while (p + 1 < n && !(data[p] == '*' && data[p + 1] == '/')) {
                ++p; if (!content_budget(s, 1)) break;
            }
            p = p + 1 < n ? p + 2 : n;
        } else break;
    }
    char kind = data[p];
    size_t k = 0;
    bool valid = true;
    if (kind == '"' || kind == '\'') {
        char quote = data[p++];
        bool closed = false;
        while (p < n && s->complete) {
            char c = data[p++];
            if (c == quote) { closed = true; break; }
            if (c == '\\') { valid = false; if (p < n) ++p; }
            if (k < 63) out[k++] = (char)tolower((unsigned char)c); else valid = false;
            content_budget(s, 1);
        }
        valid = valid && closed && quote == '"';
        kind = 's';
    } else if (isalpha((unsigned char)kind) || kind == '_') {
        while (p < n && (isalnum((unsigned char)data[p]) || data[p] == '_')) {
            if (k < 63) out[k++] = data[p]; else valid = false;
            ++p; if (!content_budget(s, 1)) break;
        }
        kind = 'i';
    } else { out[k++] = data[p++]; content_budget(s, 1); }
    out[valid ? k : 0] = 0;
    *pos = p;
    return kind;
}

static void content_script(obor_content_scan *s, const char *data, size_t n)
{
    size_t pos = 0;
    char token[64], previous[64] = "", previous_kind = 0, kind;
    while (s->complete && (kind = content_lex(s, data, n, &pos, token)) != 0) {
        /* Any preprocessor use makes native name binding uncertain. A local
         * declaration of this builtin anywhere in the sampled PAK also makes
         * all native constant evidence uncertain, irrespective of file order. */
        if (kind == '#') s->ambiguous_scripts = true;
        const obor_content_rule *function = kind == 'i' ? content_rule(kContentFunctions, token) : NULL;
        if (function) {
            if (previous_kind == 'i' && strcmp(previous, "return")) s->ambiguous_scripts = true;
            else {
                size_t q = pos;
                char next[64];
                if (content_lex(s, data, n, &q, next) == '(')
                    content_bounds(s, function->lower, function->upper, true);
            }
        }
        if (kind == 'i' && !strcmp(token, "openborconstant")) {
            if (previous_kind == 'i' && strcmp(previous, "return")) s->ambiguous_scripts = true;
            size_t q = pos;
            char arg[64];
            if (content_lex(s, data, n, &q, arg) == '(' &&
                content_lex(s, data, n, &q, arg) == 's') {
                const obor_content_rule *rule = content_rule(kContentConstants, arg);
                int lower = rule ? rule->lower : 0, upper = rule ? rule->upper : INT_MAX;
                if (!strncmp(arg, "atk_normal", 10)) {
                    const char *suffix = arg + 10;
                    int number = 0;
                    while (isdigit((unsigned char)*suffix) && number <= 60)
                        number = number * 10 + (*suffix++ - '0');
                    if (!*suffix && number >= 1 && number <= 60) lower = 3851;
                }
                char closing[64];
                if (lower && content_lex(s, data, n, &q, closing) == ')')
                    content_bounds(s, lower, upper, true);
            }
        }
        /* Keep old function-name estimates, but do not read quoted prose or
         * declarations as calls. Imported/local names suppress these below. */
        if (kind == 'i' && token[0] && previous_kind != 'i') {
            size_t q = pos;
            char next[64];
            if (content_lex(s, data, n, &q, next) == '(') content_hint(s, token);
        }
        snprintf(previous, sizeof(previous), "%s", token);
        previous_kind = kind;
    }
}

static void content_text(obor_content_scan *s, const char *data, size_t n)
{
    size_t inline_start = n;
    for (size_t p = 0; p < n && s->complete;) {
        size_t end = p;
        while (end < n && data[end] != '\n') { ++end; if (!content_budget(s, 1)) break; }
        size_t q = p;
        char command[64] = "", arg[64] = "";
        /* Model comments use #; script literals inside @script are lexed by
         * the script path and can never become line-start model commands. */
        for (int word = 0; word < 2; ++word) {
            while (q < end && isspace((unsigned char)data[q])) ++q;
            size_t k = 0;
            char *out = word ? arg : command;
            while (q < end && !isspace((unsigned char)data[q]) && data[q] != '#') {
                if (k < 63) out[k++] = (char)tolower((unsigned char)data[q]);
                ++q;
                if (!content_budget(s, 1)) break;
            }
            out[k] = 0;
        }
        if (!strcmp(command, "@end") && inline_start < n) {
            content_script(s, data + inline_start, p - inline_start);
            inline_start = n;
        } else if (!strcmp(command, "@script")) inline_start = end < n ? end + 1 : n;
        else if (inline_start == n && command[0] && arg[0] && strncmp(command, "//", 2)) {
            const obor_content_rule *rule = content_rule(kContentCommands, command);
            if (!strcmp(command, "anim")) rule = content_rule(kContentAnimations, arg);
            if (rule) content_bounds(s, rule->lower, rule->upper, false);
            else content_hint(s, command);
            if ((!strcmp(command, "script") || !strcmp(command, "animationscript")) &&
                !strcmp(arg, "@script")) content_bounds(s, 3880, INT_MAX, false);
        }
        p = end < n ? end + 1 : n;
    }
    if (inline_start < n) s->ambiguous_scripts = true;
}

static unsigned content_u32(const unsigned char *p)
{
    return (unsigned)p[0] | ((unsigned)p[1] << 8) | ((unsigned)p[2] << 16) | ((unsigned)p[3] << 24);
}

static int build_from_content(const char *pak_path)
{
    g_content_lower = 1; g_content_upper = INT_MAX;
    g_content_range_seen = false; g_content_scan_complete = false;
    obor_content_scan s = {1, INT_MAX, 1, INT_MAX, 0, 0, false, false, false, true, 0,
                          obor_detection_now()};
    FILE *fp = fopen(pak_path, "rb");
    if (!fp) return 0;
    unsigned char h[12];
    if (fseek(fp, -4, SEEK_END) || fread(h, 1, 4, fp) != 4) { fclose(fp); return 0; }
    long end = ftell(fp) - 4;
    unsigned dir = content_u32(h);
    if (dir < 8 || (long)dir > end || fseek(fp, dir, SEEK_SET)) { fclose(fp); return 0; }
    enum { MAX_FILES = 800, MAX_DIRECTORY = 65536, MAX_FILE_BYTES = 2 << 20, MAX_BYTES = 16 << 20 };
    struct entry { unsigned start, size; bool script; } entries[MAX_FILES];
    unsigned count = 0, bytes = 0, directory_count = 0;
    while (ftell(fp) < end && s.complete) {
        if (++directory_count > MAX_DIRECTORY || !content_budget(&s, 4096)) { s.complete = false; break; }
        if (fread(h, 1, 12, fp) != 12) { s.complete = false; break; }
        unsigned length = content_u32(h), start = content_u32(h + 4), size = content_u32(h + 8);
        char name[1024];
        if (length < 13 || length > 1035 || (long)(length - 12) > end - ftell(fp) ||
            start < 8 || start > dir || size > dir - start ||
            fread(name, 1, length - 12, fp) != length - 12) { s.complete = false; break; }
        size_t len = length - 12;
        if (name[len - 1] || memchr(name, 0, len - 1)) { s.complete = false; break; }
        --len;
        for (size_t i = 0; i < len; ++i) {
            name[i] = (char)tolower((unsigned char)name[i]);
            if (name[i] == '\\') name[i] = '/';
        }
        bool script = len > 2 && (!strcmp(name + len - 2, ".c") || !strcmp(name + len - 2, ".h"));
        bool text = len > 4 && !strncmp(name, "data/", 5) && !strcmp(name + len - 4, ".txt");
        if (!script && !text) continue;
        if (count == MAX_FILES || size > MAX_FILE_BYTES || size > MAX_BYTES - bytes) { s.complete = false; break; }
        entries[count++] = {start, size, script};
        bytes += size;
    }
    char *buffer = s.complete ? (char *)malloc(MAX_FILE_BYTES) : NULL;
    if (!buffer) s.complete = false;
    for (unsigned i = 0; i < count && s.complete; ++i) {
        if (!content_budget(&s, 4096) || fseek(fp, entries[i].start, SEEK_SET) ||
            fread(buffer, 1, entries[i].size, fp) != entries[i].size) { s.complete = false; break; }
        if (entries[i].script) content_script(&s, buffer, entries[i].size);
        else content_text(&s, buffer, entries[i].size);
    }
    free(buffer);
    fclose(fp);
    g_content_scan_complete = s.complete;
    /* A truncated scan is inconclusive, never a complete compatibility range. */
    if (!s.complete) return 0;
    if (s.script_seen && !s.ambiguous_scripts) content_bounds(&s, s.script_lower, s.script_upper, false);
    if (s.seen) {
        g_content_lower = s.lower; g_content_upper = s.upper; g_content_range_seen = true;
        return s.lower;
    }
    if (s.ambiguous_scripts) return 0;
    if (s.hint_upper && s.hint_upper < 8020 && s.hint_lower <= s.hint_upper) return s.hint_upper;
    return s.hint_lower >= 6412 ? s.hint_lower : 0;
}
#endif
