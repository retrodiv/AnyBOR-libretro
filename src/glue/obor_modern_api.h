/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_MODERN_API_H
#define OBOR_MODERN_API_H

/* Used after PACK validation. This probe follows automatic engine scripts
 * and their literal imports, rather than sampling every model in a large PAK.
 * Requirements describe APIs, not the major-version label in version.sh:
 * development snapshots of the 4.0 alpha still reported version 3.
 * Model commands child_follow_* were introduced at 7530 (96959080),
 * immediately before the 7533 release, and are absent in both 7123 and 7142.
 *
 * index.c registrations: 6965 (5d14cdf1), 6982 (91e39bb1),
 * 7368 (7eae91a9). All are absent in pinned 6391; the first two also
 * exist in alpha v7142 and release v7533.
 * constants.c: 7556 (fc92d78d) adds GLOBAL_CONFIG_PROPERTY_*.
 * These constants are absent in 7533 and present in the latest anchor.
 * Returning a requirement lets pick_anchor use a future updated engine. */
static const obor_content_rule kModernFunctions[] = {
    { "allocate_drawmethod", 6982, INT_MAX },
    { "copy_drawmethod", 6982, INT_MAX },
    { "free_drawmethod", 6982, INT_MAX },
    { "get_bind_property", 6965, INT_MAX },
    { "get_drawmethod_property", 6982, INT_MAX },
    { "get_global_config_property", 7368, INT_MAX },
    { "set_bind_property", 6965, INT_MAX },
    { "set_drawmethod_property", 6982, INT_MAX },
    { "set_global_config_property", 7368, INT_MAX },
};
static const char *const kModernConstants[] = {
    "global_config_property_ajspecial",
    "global_config_property_block_ratio",
    "global_config_property_block_type",
    "global_config_property_cheats",
    "global_config_property_flash_layer_adjust",
    "global_config_property_flash_layer_source",
    "global_config_property_flash_z_source",
    "global_config_property_show_go",
};

enum { OBOR_MODERN_FILES = 4096, OBOR_MODERN_DIRECTORY = 65536,
       OBOR_MODERN_SOURCE = 2 << 20, OBOR_MODERN_BYTES = 16 << 20 };
struct obor_modern_entry {
    char name[256];
    unsigned start, size;
    bool required;
};
struct obor_modern_state {
    obor_content_scan clock;
    obor_modern_entry *entries;
    unsigned count, queued, queue[OBOR_MODERN_FILES];
    unsigned calls, shadows;
    bool constant, constant_shadow;
};

/* These are engine loader paths, shared by every game. Only existing roots
 * and their imports are inspected; unused bundled source is not evidence. */
static bool modern_root(const char *name)
{
    if (!strcmp(name, "data/models.txt")) return true;
    if (strncmp(name, "data/scripts/", 13)) return false;
    name += 13;
    static const char *const roots[] = {
        "update.c", "updated.c", "updatelogic.c", "updatedlogic.c",
        "modelload.c", "modelunload.c", "level.c", "endlevel.c",
        "inputall.c", "keyall.c", "scoreall.c", "joinall.c",
        "respawnall.c", "dieall.c", "timetick.c", "loading.c",
    };
    for (size_t i = 0; i < sizeof(roots) / sizeof(roots[0]); ++i)
        if (!strcmp(name, roots[i])) return true;
    static const char *const numbered[] = { "score", "key", "join", "respawn", "die" };
    for (size_t i = 0; i < sizeof(numbered) / sizeof(numbered[0]); ++i) {
        size_t n = strlen(numbered[i]);
        if (!strncmp(name, numbered[i], n) && name[n] >= '1' && name[n] <= '4' &&
            !strcmp(name + n + 1, ".c")) return true;
    }
    return false;
}

/* models.txt supplies the engine's model paths. A bundled, unreferenced
 * model does not establish a requirement. Only literal load/cache entries
 * are followed; no names, hashes or game identities select an engine. */
static bool modern_models(obor_modern_state *s, const char *data, size_t n);

static bool modern_require(obor_modern_state *s, const char *name)
{
    for (unsigned i = 0; i < s->count; ++i) {
        if (!content_budget(&s->clock, 1)) return false;
        if (strcmp(s->entries[i].name, name)) continue;
        if (!s->entries[i].required) {
            s->entries[i].required = true;
            s->queue[s->queued++] = i;
        }
        return true;
    }
    return false;
}

static unsigned modern_function_bit(const char *name)
{
    for (size_t i = 0; i < sizeof(kModernFunctions) / sizeof(kModernFunctions[0]); ++i)
        if (!strcmp(name, kModernFunctions[i].name)) return 1u << i;
    return 0;
}

static bool modern_import(obor_modern_state *s, const char *from, const char *name)
{
    /* Literal relative imports are resolved against the importing file. */
    if (modern_require(s, name)) return true;
    const char *slash = strrchr(from, '/');
    if (!slash || strstr(name, "..") || name[0] == '/' || strchr(name, ':')) return false;
    char path[256];
    int n = snprintf(path, sizeof(path), "%.*s/%s", (int)(slash - from), from, name);
    return n >= 0 && (size_t)n < sizeof(path) && modern_require(s, path);
}

static bool modern_models(obor_modern_state *s, const char *data, size_t n)
{
    size_t p = 0;
    while (p < n) {
        size_t end = p;
        while (end < n && data[end] != '\n') {
            ++end;
            if (!content_budget(&s->clock, 1)) return false;
        }
        if (end - p >= 1024) return false;
        char line[1024], command[256], model[256], path[256];
        memcpy(line, data + p, end - p); line[end - p] = 0;
        p = end < n ? end + 1 : end;
        if (sscanf(line, "%255s %255s %255s", command, model, path) != 3) continue;
        for (char *c = command; *c; ++c) *c = (char)tolower((unsigned char)*c);
        if (strcmp(command, "load") && strcmp(command, "cache")) continue;
        size_t len = strlen(path);
        if (len > 1 && path[0] == '"' && path[len - 1] == '"') {
            memmove(path, path + 1, len - 2); path[len - 2] = 0;
        }
        for (char *c = path; *c; ++c) {
            *c = (char)tolower((unsigned char)*c);
            if (*c == '\\') *c = '/';
        }
        if (!modern_require(s, path)) return false;
    }
    return true;
}

static bool modern_script(obor_modern_state *s, const char *name, const char *data, size_t n)
{
    size_t p = 0;
    char token[64], previous[64] = "", previous_kind = 0, kind;
    while (s->clock.complete && (kind = content_lex(&s->clock, data, n, &p, token))) {
        if (kind == '#') {
            char directive[64], arg[64];
            size_t end = p;
            while (end < n && data[end] != '\n') {
                ++end;
                if (!content_budget(&s->clock, 1)) return false;
            }
            if (content_lex(&s->clock, data, end, &p, directive) != 'i') return false;
            if (!strcmp(directive, "import") || !strcmp(directive, "include")) {
                if (content_lex(&s->clock, data, end, &p, arg) != 's' || !arg[0] ||
                    !modern_import(s, name, arg)) return false;
                if (content_lex(&s->clock, data, end, &p, arg)) return false;
            } else if (!strcmp(directive, "define")) {
                /* A macro mentioning a candidate native name makes its
                 * binding uncertain. Other literal defines are harmless. */
                while (content_lex(&s->clock, data, end, &p, arg)) {
                    s->shadows |= modern_function_bit(arg);
                    if (!strcmp(arg, "openborconstant")) s->constant_shadow = true;
                }
            } else return false; /* conditional/generated source is inconclusive */
            p = end;
            previous[0] = previous_kind = 0;
            continue;
        }
        unsigned bit = kind == 'i' ? modern_function_bit(token) : 0;
        bool constant = kind == 'i' && !strcmp(token, "openborconstant");
        if (bit || constant) {
            size_t q = p;
            char next[64];
            if (content_lex(&s->clock, data, n, &q, next) == '(') {
                if (previous_kind == 'i' && strcmp(previous, "return")) {
                    s->shadows |= bit;
                    if (constant) s->constant_shadow = true;
                } else if (bit) s->calls |= bit;
                else if (content_lex(&s->clock, data, n, &q, next) == 's') {
                    bool known = false;
                    for (size_t i = 0; i < sizeof(kModernConstants) / sizeof(kModernConstants[0]); ++i)
                        if (!strcmp(next, kModernConstants[i])) known = true;
                    if (known && content_lex(&s->clock, data, n, &q, next) == ')')
                        s->constant = true;
                }
            }
        }
        snprintf(previous, sizeof(previous), "%s", token);
        previous_kind = kind;
    }
    return s->clock.complete;
}

static int obor_modern_api_build(const char *path)
{
    FILE *fp = fopen(path, "rb");
    if (!fp) return 0;
    obor_modern_state s = {};
    s.clock.lower = s.clock.script_lower = 1;
    s.clock.upper = s.clock.script_upper = INT_MAX;
    s.clock.complete = true;
    s.clock.started = obor_detection_now();
    s.entries = (obor_modern_entry *)calloc(OBOR_MODERN_FILES, sizeof(*s.entries));
    char *buffer = NULL;
    unsigned char h[12];
    long end = 0;
    unsigned dir = 0, directory_count = 0, bytes = 0;
    int result = 0;
    if (!s.entries || fread(h, 1, 8, fp) != 8 || memcmp(h, "PACK\0\0\0\0", 8) ||
        fseek(fp, -4, SEEK_END) || (end = ftell(fp)) < 8 ||
        fread(h, 1, 4, fp) != 4) goto done;
    dir = content_u32(h);
    if (dir < 8 || (long)dir > end || fseek(fp, dir, SEEK_SET)) goto done;
    while (ftell(fp) < end) {
        if (++directory_count > OBOR_MODERN_DIRECTORY || !content_budget(&s.clock, 4096) ||
            end - ftell(fp) < 12 || fread(h, 1, 12, fp) != 12) goto done;
        unsigned length = content_u32(h), start = content_u32(h + 4), size = content_u32(h + 8);
        char name[256];
        if (length < 14 || length > sizeof(name) + 12 || (long)(length - 12) > end - ftell(fp) ||
            start < 8 || start > dir || size > dir - start ||
            fread(name, 1, length - 12, fp) != length - 12) goto done;
        size_t len = length - 12;
        if (name[len - 1] || memchr(name, 0, len - 1)) goto done;
        --len;
        for (size_t i = 0; i < len; ++i) {
            name[i] = (char)tolower((unsigned char)name[i]);
            if (name[i] == '\\') name[i] = '/';
        }
        bool source = len > 2 && (!strcmp(name + len - 2, ".c") || !strcmp(name + len - 2, ".h"));
        bool text = len > 4 && !strcmp(name + len - 4, ".txt");
        if (!source && !text) continue;
        if (s.count == OBOR_MODERN_FILES) goto done;
        for (unsigned i = 0; i < s.count; ++i) {
            if (!content_budget(&s.clock, 1) || !strcmp(name, s.entries[i].name)) goto done;
        }
        obor_modern_entry *entry = s.entries + s.count++;
        snprintf(entry->name, sizeof(entry->name), "%s", name);
        entry->start = start; entry->size = size;
        if (modern_root(name)) {
            entry->required = true;
            s.queue[s.queued++] = s.count - 1;
        }
    }
    if (!s.queued) goto done;
    buffer = (char *)malloc(OBOR_MODERN_SOURCE);
    if (!buffer) goto done;
    for (unsigned i = 0; i < s.queued; ++i) {
        const obor_modern_entry *entry = s.entries + s.queue[i];
        if (entry->size > OBOR_MODERN_SOURCE || entry->size > OBOR_MODERN_BYTES - bytes ||
            !content_budget(&s.clock, 4096) || fseek(fp, entry->start, SEEK_SET) ||
            fread(buffer, 1, entry->size, fp) != entry->size) goto done;
        bytes += entry->size;
        if (!strcmp(entry->name, "data/models.txt")) {
            if (!modern_models(&s, buffer, entry->size)) goto done;
            content_text(&s.clock, buffer, entry->size);
            if (!s.clock.complete) goto done;
        } else if (strstr(entry->name, ".txt") &&
                   !strcmp(entry->name + strlen(entry->name) - 4, ".txt")) {
            content_text(&s.clock, buffer, entry->size);
            if (!s.clock.complete) goto done;
        } else if (!modern_script(&s, entry->name, buffer, entry->size)) goto done;
    }
    if (obor_detection_expired(s.clock.started)) goto done;
    if (s.constant && !s.constant_shadow) result = 7556;
    if (s.clock.script_seen && !s.clock.ambiguous_scripts)
        content_bounds(&s.clock, s.clock.script_lower, s.clock.script_upper, false);
    if (s.clock.lower > 6391 && s.clock.lower > result) result = s.clock.lower;
    for (size_t i = 0; i < sizeof(kModernFunctions) / sizeof(kModernFunctions[0]); ++i)
        if ((s.calls & ~s.shadows) & (1u << i))
            if (kModernFunctions[i].lower > result) result = kModernFunctions[i].lower;
done:
    free(buffer); free(s.entries); fclose(fp);
    return result;
}
#endif
