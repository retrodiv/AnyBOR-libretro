/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_CONTENT_CONTRACTS_H
#define OBOR_CONTENT_CONTRACTS_H
/* Syntax facts for refining an imprecise declaration. The source boundaries
 * and branch exceptions are documented in docs/AUTO_SELECTION_RULES.md.
 * This header follows content_lex; no source is executed during detection. */
enum obor_contract_kind {
    OBOR_CT_FUNCTION, OBOR_CT_CONSTANT, OBOR_CT_COMMAND,
    OBOR_CT_PLAYER, OBOR_CT_PLAYER_WRITE, OBOR_CT_LEVEL,
    OBOR_CT_SYSTEM, OBOR_CT_AIFLAG_READ, OBOR_CT_ATTACK_NAME,
    OBOR_CT_PALETTE
};
enum { OBOR_CT_NO_4453 = 1, OBOR_CT_OLD_ANIMATION_BRANCH = 2 };
struct obor_contract_rule {
    const char *name;
    obor_contract_kind kind;
    int lower, upper;
    unsigned flags;
};
static const obor_contract_rule kContentContracts[] = {
    { "16bit", OBOR_CT_PALETTE, 1, INT_MAX, OBOR_CT_NO_4453 },
    { "8bit", OBOR_CT_PALETTE, 1, INT_MAX, OBOR_CT_NO_4453 },
    { "allocate_palette", OBOR_CT_FUNCTION, 7582, INT_MAX, 0 },
    { "ani_prop_animhits", OBOR_CT_CONSTANT, 4232, 7083, OBOR_CT_OLD_ANIMATION_BRANCH },
    { "ani_prop_numframes", OBOR_CT_CONSTANT, 4232, 7083, OBOR_CT_OLD_ANIMATION_BRANCH },
    { "atk_land", OBOR_CT_CONSTANT, 3831, INT_MAX, 0 },
    { "atk_lifespan", OBOR_CT_CONSTANT, 3831, INT_MAX, 0 },
    { "atk_pit", OBOR_CT_CONSTANT, 3831, INT_MAX, 0 },
    { "atk_timeover", OBOR_CT_CONSTANT, 3831, INT_MAX, 0 },
    { "binding_ani_animation_kill", OBOR_CT_CONSTANT, 6397, 6434, 0 },
    { "binding_ani_animation_match", OBOR_CT_CONSTANT, 6397, 6434, 0 },
    { "binding_ani_frame_kill", OBOR_CT_CONSTANT, 6397, 6434, 0 },
    { "binding_ani_frame_match", OBOR_CT_CONSTANT, 6397, 6434, 0 },
    { "binding_ani_none", OBOR_CT_CONSTANT, 6397, 6434, 0 },
    { "binding_matching_none", OBOR_CT_CONSTANT, 6436, 6964, 0 },
    { "boomerang", OBOR_CT_COMMAND, 1, 6376, 0 },
    { "boomerangvalues", OBOR_CT_COMMAND, 1, 6376, 0 },
    { "custboomerang", OBOR_CT_COMMAND, 1, 6376, 0 },
    { "ebox", OBOR_CT_COMMAND, 6332, INT_MAX, 0 },
    { "exit", OBOR_CT_FUNCTION, 3834, INT_MAX, 0 },
    { "freezetime", OBOR_CT_AIFLAG_READ, 1, 3796, 0 },
    { "get_colorset_property", OBOR_CT_FUNCTION, 7470, INT_MAX, 0 },
    { "get_command_input_event_property", OBOR_CT_FUNCTION, 7843, INT_MAX, 0 },
    { "get_entity_collision_collection", OBOR_CT_FUNCTION, 6340, 7823, 0 },
    { "get_entity_collision_instance", OBOR_CT_FUNCTION, 6340, 7823, 0 },
    { "get_entity_collision_property", OBOR_CT_FUNCTION, 6340, 7823, 0 },
    { "get_faction_property", OBOR_CT_FUNCTION, 7445, INT_MAX, 0 },
    { "get_sound_property", OBOR_CT_FUNCTION, 7871, INT_MAX, 0 },
    { "keys", OBOR_CT_PLAYER_WRITE, 3798, INT_MAX, 0 },
    { "land", OBOR_CT_ATTACK_NAME, 3831, INT_MAX, 0 },
    { "lifespan", OBOR_CT_ATTACK_NAME, 3831, INT_MAX, 0 },
    { "movie_load", OBOR_CT_FUNCTION, 7964, INT_MAX, 0 },
    { "movie_play", OBOR_CT_FUNCTION, 7964, INT_MAX, 0 },
    { "movie_stop", OBOR_CT_FUNCTION, 7964, INT_MAX, 0 },
    { "on_bind_update_other_to_self_script", OBOR_CT_COMMAND, 6421, INT_MAX, 0 },
    { "on_bind_update_self_to_other_script", OBOR_CT_COMMAND, 6421, INT_MAX, 0 },
    { "onmodelcopyscript", OBOR_CT_COMMAND, 3793, INT_MAX, 0 },
    { "pain_time", OBOR_CT_AIFLAG_READ, 1, 3796, 0 },
    { "pit", OBOR_CT_ATTACK_NAME, 3831, INT_MAX, 0 },
    { "remap", OBOR_CT_COMMAND, 1, INT_MAX, OBOR_CT_NO_4453 },
    { "sample_play_id", OBOR_CT_SYSTEM, 3838, INT_MAX, 0 },
    { "scrollmaxx", OBOR_CT_SYSTEM, 3783, INT_MAX, 0 },
    { "scrollminx", OBOR_CT_SYSTEM, 3783, INT_MAX, 0 },
    { "set_entity_collision_property", OBOR_CT_FUNCTION, 6340, 7823, 0 },
    { "set_sound_property", OBOR_CT_FUNCTION, 7871, INT_MAX, 0 },
    { "spawnhealth", OBOR_CT_PLAYER, 3797, INT_MAX, 0 },
    { "spawnmp", OBOR_CT_PLAYER, 3797, INT_MAX, 0 },
    { "timeover", OBOR_CT_ATTACK_NAME, 3831, INT_MAX, 0 },
    { "type", OBOR_CT_LEVEL, 3820, INT_MAX, 0 },
    { "unload_model", OBOR_CT_FUNCTION, 6411, INT_MAX, 0 },
    { "weapnum", OBOR_CT_PLAYER, 3821, INT_MAX, 0 },
    { "weaponum", OBOR_CT_PLAYER, 1, 3820, 0 },
};
static bool g_contract_valid, g_contract_scripts_ambiguous;
static unsigned char g_contract_seen[sizeof(kContentContracts) / sizeof(kContentContracts[0])];

static void content_contract_reset(void)
{
    memset(g_contract_seen, 0, sizeof(g_contract_seen));
    g_contract_valid = false;
    g_contract_scripts_ambiguous = true;
}

static const obor_contract_rule *content_contract_lookup(obor_contract_kind kind, const char *name)
{
    size_t lo = 0, hi = sizeof(kContentContracts) / sizeof(kContentContracts[0]);
    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        if (strcmp(kContentContracts[mid].name, name) < 0) lo = mid + 1;
        else hi = mid;
    }
    while (lo < sizeof(kContentContracts) / sizeof(kContentContracts[0]) &&
           !strcmp(kContentContracts[lo].name, name)) {
        if (kContentContracts[lo].kind == kind) return &kContentContracts[lo];
        ++lo;
    }
    return NULL;
}

static void content_contract_observe(obor_contract_kind kind, const char *name)
{
    if (!g_content_triage) return;
    const obor_contract_rule *rule = content_contract_lookup(kind, name);
    if (rule) g_contract_seen[rule - kContentContracts] = 1;
}

static bool content_contract_active(size_t i)
{
    if (!g_contract_valid || !g_contract_seen[i]) return false;
    obor_contract_kind kind = kContentContracts[i].kind;
    bool script = kind != OBOR_CT_COMMAND && kind != OBOR_CT_ATTACK_NAME && kind != OBOR_CT_PALETTE;
    return !script || !g_contract_scripts_ambiguous;
}

static bool content_contract_allows(const obor_contract_rule *rule, int profile, int engine)
{
    if ((rule->flags & OBOR_CT_OLD_ANIMATION_BRANCH) && engine == 7142 &&
        (profile == 7086 || profile == 7123)) return true;
    return profile >= rule->lower && profile <= rule->upper &&
        (!(rule->flags & OBOR_CT_NO_4453) || profile != 4453);
}

static uint64_t content_contract_distance(int profile, int engine)
{
    uint64_t distance = 0;
    for (size_t i = 0; i < sizeof(kContentContracts) / sizeof(kContentContracts[0]); ++i) {
        if (!content_contract_active(i)) continue;
        const obor_contract_rule *rule = &kContentContracts[i];
        if (content_contract_allows(rule, profile, engine)) continue;
        uint64_t gap = profile < rule->lower ? (uint64_t)rule->lower - profile :
            profile > rule->upper ? (uint64_t)profile - rule->upper : 1;
        if (gap > distance) distance = gap;
    }
    return distance;
}

/* Return a literal argument only when it is the complete argument. A bounded
 * token walk permits nested first arguments without interpreting expressions. */
static bool content_contract_argument(obor_content_scan *s, const char *data,
                                      size_t n, size_t pos, unsigned argument, char out[64])
{
    size_t end = n - pos > 4096 ? pos + 4096 : n;
    char token[64];
    if (content_lex(s, data, end, &pos, token) != '(') return false;
    unsigned depth = 1, current = 0;
    char kind;
    while (s->complete && (kind = content_lex(s, data, end, &pos, token))) {
        if (depth == 1 && current == argument) {
            if (kind != 's' || !token[0]) return false;
            snprintf(out, 64, "%s", token);
            kind = content_lex(s, data, end, &pos, token);
            return kind == ',' || kind == ')';
        }
        if (kind == '(' || kind == '[' || kind == '{') ++depth;
        else if (kind == ')' || kind == ']' || kind == '}') {
            if (!--depth) return false;
        } else if (kind == ',' && depth == 1) ++current;
    }
    return false;
}

static void content_contract_script(obor_content_scan *s, const char *name,
                                    char previous_kind, const char *previous,
                                    const char *data, size_t n, size_t pos)
{
    if (!g_content_triage) return;
    bool native = content_contract_lookup(OBOR_CT_FUNCTION, name) != NULL;
    bool player = !strcmp(name, "getplayerproperty") || !strcmp(name, "changeplayerproperty");
    bool level = !strcmp(name, "getlevelproperty") || !strcmp(name, "changelevelproperty");
    bool system = !strcmp(name, "openborvariant") || !strcmp(name, "changeopenborvariant");
    bool constant = !strcmp(name, "openborconstant");
    bool entity = !strcmp(name, "getentityproperty");
    if (!(native || player || level || system || constant || entity)) return;
    if (previous_kind == 'i' && strcmp(previous, "return")) {
        s->ambiguous_scripts = true;
        return;
    }
    size_t q = pos;
    char arg[64], next[64];
    if (content_lex(s, data, n, &q, next) != '(') return;
    if (native) content_contract_observe(OBOR_CT_FUNCTION, name);
    if (constant && content_contract_argument(s, data, n, pos, 0, arg))
        content_contract_observe(OBOR_CT_CONSTANT, arg);
    if (player && content_contract_argument(s, data, n, pos, 1, arg)) {
        content_contract_observe(OBOR_CT_PLAYER, arg);
        if (!strcmp(name, "changeplayerproperty")) content_contract_observe(OBOR_CT_PLAYER_WRITE, arg);
    }
    if (level && content_contract_argument(s, data, n, pos, 0, arg))
        content_contract_observe(OBOR_CT_LEVEL, arg);
    if (system && content_contract_argument(s, data, n, pos, 0, arg))
        content_contract_observe(OBOR_CT_SYSTEM, arg);
    if (entity && content_contract_argument(s, data, n, pos, 1, arg) && !strcmp(arg, "aiflag") &&
        content_contract_argument(s, data, n, pos, 2, arg))
        content_contract_observe(OBOR_CT_AIFLAG_READ, arg);
}

static void content_contract_model(const char *command, const char *argument)
{
    content_contract_observe(OBOR_CT_COMMAND, command);
    if (!strcmp(command, "defense") || !strcmp(command, "offense"))
        content_contract_observe(OBOR_CT_ATTACK_NAME, argument);
    if (!strcmp(command, "colourdepth"))
        content_contract_observe(OBOR_CT_PALETTE, argument);
}
#endif
