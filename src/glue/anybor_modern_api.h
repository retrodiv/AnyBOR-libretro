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
enum obor_modern_role {
    OBOR_MODERN_UNUSED, OBOR_MODERN_SCRIPT, OBOR_MODERN_MODEL_INDEX, OBOR_MODERN_MODEL,
    OBOR_MODERN_LEVEL_INDEX, OBOR_MODERN_LEVEL
};
struct obor_modern_entry {
    char name[256];
    unsigned start, size;
    obor_modern_role role;
};
struct obor_modern_state {
    obor_content_scan clock;
    obor_modern_entry *entries;
    unsigned count, queued, queue[OBOR_MODERN_FILES];
    unsigned calls, shadows;
    bool constant, constant_shadow;
    unsigned char native[sizeof(g_bound_native)];
    unsigned char contracts[sizeof(g_bound_contracts)];
};

enum { OBOR_NATIVE_CALL = 1, OBOR_NATIVE_SHADOW = 2 };

/* These are engine loader paths, shared by every game. Only existing roots
 * and their imports are inspected; unused bundled source is not evidence. */
static obor_modern_role modern_root(const char *name)
{
    if (!strcmp(name, "data/models.txt")) return OBOR_MODERN_MODEL_INDEX;
    if (g_content_infer && !strcmp(name, "data/levels.txt")) return OBOR_MODERN_LEVEL_INDEX;
    if (strncmp(name, "data/scripts/", 13)) return OBOR_MODERN_UNUSED;
    name += 13;
    static const char *const roots[] = {
        "update.c", "updated.c", "updatelogic.c", "updatedlogic.c",
        "modelload.c", "modelunload.c", "level.c", "endlevel.c",
        "inputall.c", "keyall.c", "scoreall.c", "joinall.c",
        "respawnall.c", "dieall.c", "timetick.c", "loading.c",
    };
    for (size_t i = 0; i < sizeof(roots) / sizeof(roots[0]); ++i)
        if (!strcmp(name, roots[i])) return OBOR_MODERN_SCRIPT;
    static const char *const numbered[] = { "score", "key", "join", "respawn", "die" };
    for (size_t i = 0; i < sizeof(numbered) / sizeof(numbered[0]); ++i) {
        size_t n = strlen(numbered[i]);
        if (!strncmp(name, numbered[i], n) && name[n] >= '1' && name[n] <= '4' &&
            !strcmp(name + n + 1, ".c")) return OBOR_MODERN_SCRIPT;
    }
    return OBOR_MODERN_UNUSED;
}

static bool modern_require(obor_modern_state *s, const char *name, obor_modern_role role)
{
    unsigned lo = 0, hi = s->count;
    while (lo < hi) {
        if (!content_budget(&s->clock, 1)) return false;
        unsigned mid = lo + (hi - lo) / 2;
        int cmp = strcmp(name, s->entries[mid].name);
        if (!cmp) {
            if (s->entries[mid].role == OBOR_MODERN_UNUSED) {
                s->entries[mid].role = role;
                s->queue[s->queued++] = mid;
            }
            return s->entries[mid].role == role;
        }
        if (cmp < 0) hi = mid; else lo = mid + 1;
    }
    return false;
}

static int modern_compare_names(const void *left, const void *right)
{
    return strcmp(static_cast<const obor_modern_entry *>(left)->name,
                  static_cast<const obor_modern_entry *>(right)->name);
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
    if (modern_require(s, name, OBOR_MODERN_SCRIPT)) return true;
    const char *slash = strrchr(from, '/');
    if (!slash || strstr(name, "..") || name[0] == '/' || strchr(name, ':')) return false;
    char path[256];
    int n = snprintf(path, sizeof(path), "%.*s/%s", (int)(slash - from), from, name);
    return n >= 0 && (size_t)n < sizeof(path) && modern_require(s, path, OBOR_MODERN_SCRIPT);
}

static bool modern_script(obor_modern_state *s, const char *name, const char *data, size_t n);

static char *modern_text_word(char *&cursor)
{
    while (isspace((unsigned char)*cursor)) ++cursor;
    if (!*cursor || *cursor == '#') return NULL;
    bool quoted = *cursor == '"';
    if (quoted) ++cursor;
    char *word = cursor;
    while (*cursor && (quoted ? *cursor != '"' : !isspace((unsigned char)*cursor) && *cursor != '#'))
        ++cursor;
    if (quoted && !*cursor) return NULL;
    if (*cursor == '#') *cursor = 0;
    else if (*cursor) *cursor++ = 0;
    return word;
}

static void modern_path_fold(char *path)
{
    for (; *path; ++path)
        *path = *path == '\\' ? '/' : (char)tolower((unsigned char)*path);
}

static bool modern_model_script_command(const char *command)
{
    static const char *const commands[] = {
        "animationscript", "didblockscript", "didhitscript", "inholescript", "keyscript",
        "modelloadscript", "modelunloadscript", "on_bind_update_other_to_self_script",
        "on_bind_update_self_to_other_script", "onblockascript", "onblockoscript",
        "onblockpscript", "onblocksscript", "onblockwscript", "onblockyscript",
        "onblockzscript", "ondeathscript", "ondoattackscript", "ondrawscript",
        "onentitycollisionscript", "onfallscript", "onkillscript", "onmodelcopyscript",
        "onmoveascript", "onmovexscript", "onmoveyscript", "onmovezscript",
        "onpainscript", "onspawnscript", "script", "takedamagescript", "thinkscript",
    };
    for (const char *name : commands)
        if (!strcmp(command, name)) return true;
    return false;
}

static bool modern_level_script_command(const char *command)
{
    static const char *const commands[] = {
        "endlevelscript", "keyscript", "levelscript", "spawnscript", "updatedlogicscript",
        "updatedscript", "updatelogicscript", "updatescript",
    };
    for (const char *name : commands)
        if (!strcmp(command, name)) return true;
    return false;
}

/* Only literal loader references join the graph. */
static bool modern_data(obor_modern_state *s, const obor_modern_entry *entry, const char *data, size_t n)
{
    bool animation = false;
    size_t p = 0, inline_start = n;
    while (p < n) {
        size_t start = p;
        size_t end = p;
        while (end < n && data[end] != '\n') {
            ++end;
            if (!content_budget(&s->clock, 1)) return false;
        }
        p = end < n ? end + 1 : end;
        char line[1024];
        if (end - start >= sizeof(line)) {
            if (inline_start < n) continue;
            return false;
        }
        memcpy(line, data + start, end - start); line[end - start] = 0;
        char *cursor = line;
        char *command = modern_text_word(cursor);
        if (!command) continue;
        modern_path_fold(command);
        if (inline_start < n) {
            if (!strcmp(command, "@end")) {
                if (!modern_script(s, entry->name, data + inline_start, start - inline_start)) return false;
                inline_start = n;
            }
            continue;
        }
        if (entry->role == OBOR_MODERN_MODEL_INDEX) {
            if (strcmp(command, "load") && strcmp(command, "cache")) {
                if (g_content_infer && content_contract_lookup(OBOR_CT_MODEL_DEFAULT, command)) {
                    unsigned required = !strcmp(command, "dropv") ? 3 : 1;
                    unsigned matched = 0;
                    for (; matched < required; ++matched) {
                        char *value = modern_text_word(cursor), *end = NULL;
                        if (!value) break;
                        strtod(value, &end);
                        if (end == value || *end) break;
                    }
                    if (matched == required)
                        content_contract_record(s->contracts, OBOR_CT_MODEL_DEFAULT, command);
                }
                continue;
            }
            if (!modern_text_word(cursor)) return false;
            char *path = modern_text_word(cursor);
            if (!path) return false;
            modern_path_fold(path);
            if (!modern_require(s, path, OBOR_MODERN_MODEL)) return false;
        } else if (entry->role == OBOR_MODERN_LEVEL_INDEX) {
            if (strcmp(command, "file")) continue;
            char *path = modern_text_word(cursor);
            if (!path) return false;
            modern_path_fold(path);
            if (!modern_require(s, path, OBOR_MODERN_LEVEL)) return false;
        } else if (!strcmp(command, "@script")) {
            inline_start = start + (size_t)(cursor - line);
        } else if (entry->role == OBOR_MODERN_MODEL ? modern_model_script_command(command) :
                   modern_level_script_command(command)) {
            char *path = modern_text_word(cursor);
            if (!path) return false;
            modern_path_fold(path);
            if (!strcmp(path, "@script")) inline_start = start + (size_t)(cursor - line);
            else if (!modern_require(s, path, OBOR_MODERN_SCRIPT)) return false;
        } else if (entry->role == OBOR_MODERN_MODEL && !strcmp(command, "anim")) {
            animation = modern_text_word(cursor) != NULL;
        } else if (animation && !strcmp(command, "jumpframe")) {
            const char *argument = modern_text_word(cursor);
            if (argument && !strcasecmp(argument, "this") && modern_text_word(cursor))
                content_contract_record(s->contracts, OBOR_CT_MODEL_ARGUMENT, command);
        }
    }
    return inline_start == n;
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
                    if (g_content_infer) {
                        if (content_contract_selector(arg) || content_rule(kContentFunctions, arg))
                            s->clock.ambiguous_scripts = true;
                        size_t index = content_native_index(OBOR_REGISTRY_FUNCTION, arg);
                        if (index < sizeof(s->native)) s->native[index] |= OBOR_NATIVE_SHADOW;
                    }
                }
            } else return false; /* conditional/generated source is inconclusive */
            p = end;
            previous[0] = previous_kind = 0;
            continue;
        }
        if (g_content_infer && kind == 'i') {
            content_contract_script(&s->clock, token, previous_kind, previous, data, n, p, s->contracts);
            content_script_bounds(&s->clock, token, previous_kind, previous, data, n, p, false);
        }
        if (g_content_infer && kind == 'i' &&
            (!strcmp(token, "getentityproperty") || !strcmp(token, "openborvariant"))) {
            bool entity = !strcmp(token, "getentityproperty");
            char argument[64];
            if (content_contract_argument(&s->clock, data, n, p, entity ? 1 : 0, argument)) {
                size_t property = content_native_index(
                    entity ? OBOR_REGISTRY_ENTITY_READ : OBOR_REGISTRY_SYSTEM_READ, argument);
                if (property < sizeof(s->native)) s->native[property] |= OBOR_NATIVE_CALL;
            }
        }
        unsigned bit = kind == 'i' ? modern_function_bit(token) : 0;
        size_t index = g_content_infer && kind == 'i' ?
            content_native_index(OBOR_REGISTRY_FUNCTION, token) : sizeof(s->native);
        bool constant = kind == 'i' && !strcmp(token, "openborconstant");
        if (bit || constant || index < sizeof(s->native)) {
            size_t q = p;
            char next[64];
            if (content_lex(&s->clock, data, n, &q, next) == '(') {
                bool declaration = previous_kind == 'i' && strcmp(previous, "return");
                if (index < sizeof(s->native))
                    s->native[index] |= declaration ? OBOR_NATIVE_SHADOW : OBOR_NATIVE_CALL;
                if (declaration) {
                    s->shadows |= bit;
                    if (constant) s->constant_shadow = true;
                } else if (bit) s->calls |= bit;
                else if (constant && content_lex(&s->clock, data, n, &q, next) == 's') {
                    bool known = false;
                    for (size_t i = 0; i < sizeof(kModernConstants) / sizeof(kModernConstants[0]); ++i)
                        if (!strcmp(next, kModernConstants[i])) known = true;
                    if (g_content_infer) index = content_native_index(OBOR_REGISTRY_CONSTANT, next);
                    if (content_lex(&s->clock, data, n, &q, next) == ')') {
                        if (known) s->constant = true;
                        if (index < sizeof(s->native)) s->native[index] |= OBOR_NATIVE_CALL;
                    }
                }
            }
        }
        snprintf(previous, sizeof(previous), "%s", token);
        previous_kind = kind;
    }
    return s->clock.complete;
}

static int obor_modern_api_build(const char *path, obor_content_rule *bound_script)
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
    int64_t end = 0;
    unsigned dir = 0, directory_count = 0, bytes = 0;
    int result = 0;
    if (!s.entries || fread(h, 1, 8, fp) != 8 || memcmp(h, "PACK\0\0\0\0", 8) ||
        obor_file_seek64(fp, -4, SEEK_END) ||
        (end = obor_file_tell64(fp)) < 8 || end > (int64_t)UINT32_MAX - 4 ||
        fread(h, 1, 4, fp) != 4) goto done;
    dir = content_u32(h);
    if (dir < 8 || (int64_t)dir > end || obor_file_seek64(fp, dir, SEEK_SET)) goto done;
    while (obor_file_tell64(fp) < end) {
        if (++directory_count > OBOR_MODERN_DIRECTORY || !content_budget(&s.clock, 4096) ||
            end - obor_file_tell64(fp) < 12 || fread(h, 1, 12, fp) != 12) goto done;
        unsigned length = content_u32(h), start = content_u32(h + 4), size = content_u32(h + 8);
        char name[256];
        if (length < 14 || length > sizeof(name) + 12 ||
            (int64_t)(length - 12) > end - obor_file_tell64(fp) ||
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
        obor_modern_entry *entry = s.entries + s.count++;
        snprintf(entry->name, sizeof(entry->name), "%s", name);
        entry->start = start; entry->size = size;
    }
    qsort(s.entries, s.count, sizeof(*s.entries), modern_compare_names);
    for (unsigned i = 0; i < s.count; ++i) {
        obor_modern_entry *entry = s.entries + i;
        if (i && !strcmp(entry[-1].name, entry->name)) goto done;
        entry->role = modern_root(entry->name);
        if (entry->role != OBOR_MODERN_UNUSED) s.queue[s.queued++] = i;
    }
    if (!s.queued) goto done;
    buffer = (char *)malloc(OBOR_MODERN_SOURCE);
    if (!buffer) goto done;
    for (unsigned i = 0; i < s.queued; ++i) {
        const obor_modern_entry *entry = s.entries + s.queue[i];
        if (entry->size > OBOR_MODERN_SOURCE || entry->size > OBOR_MODERN_BYTES - bytes ||
            !content_budget(&s.clock, 4096) || obor_file_seek64(fp, entry->start, SEEK_SET) ||
            fread(buffer, 1, entry->size, fp) != entry->size) goto done;
        bytes += entry->size;
        if (entry->role != OBOR_MODERN_SCRIPT) {
            if ((g_content_infer || entry->role == OBOR_MODERN_MODEL_INDEX) &&
                !modern_data(&s, entry, buffer, entry->size)) goto done;
            content_text(&s.clock, buffer, entry->size);
            if (!s.clock.complete) goto done;
        } else if (!modern_script(&s, entry->name, buffer, entry->size)) goto done;
    }
    if (obor_detection_expired(s.clock.started)) goto done;
    for (size_t i = 0; i < sizeof(g_bound_native); ++i) {
        obor_registry_kind kind = kNativeRequirements[i].kind;
        bool ambiguous = kind == OBOR_REGISTRY_CONSTANT ? s.constant_shadow :
            kind != OBOR_REGISTRY_FUNCTION && s.clock.ambiguous_scripts;
        g_bound_native[i] = s.native[i] == OBOR_NATIVE_CALL && !ambiguous;
    }
    for (size_t i = 0; i < sizeof(g_bound_contracts); ++i)
        g_bound_contracts[i] = s.contracts[i] &&
            (!s.clock.ambiguous_scripts || !content_contract_is_script(kContentContracts[i].kind));
    if (s.constant && !s.constant_shadow) result = 7556;
    if (s.clock.script_seen && !s.clock.ambiguous_scripts) {
        if (g_content_infer)
            *bound_script = {"bound script APIs", s.clock.script_lower, s.clock.script_upper};
        content_bounds(&s.clock, s.clock.script_lower, s.clock.script_upper, false);
    }
    if (s.clock.lower > 6391 && s.clock.lower > result) result = s.clock.lower;
    for (size_t i = 0; i < sizeof(kModernFunctions) / sizeof(kModernFunctions[0]); ++i)
        if ((s.calls & ~s.shadows) & (1u << i))
            if (kModernFunctions[i].lower > result) result = kModernFunctions[i].lower;
done:
    /* Complete declarations in a bound model remain facts even when a later
     * dependency cannot be read. Script bindings require the full closure. */
    for (size_t i = 0; i < sizeof(g_bound_contracts); ++i)
        if (!content_contract_is_script(kContentContracts[i].kind) && s.contracts[i])
            g_bound_contracts[i] = 1;
    free(buffer); free(s.entries); fclose(fp);
    return result;
}
#endif
