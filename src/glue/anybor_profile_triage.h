/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_PROFILE_TRIAGE_H
#define OBOR_PROFILE_TRIAGE_H
static bool filename_triage_bounds(const char *path, filename_build_interval *out)
{
    if (build_interval_from_filename(path, out)) return true;
    const char *base = strrchr(path, PATH_SEP);
    base = base ? base + 1 : path;
    for (const char *p = base; *p; ++p) {
        if ((p != base && (isalnum((unsigned char)p[-1]) || p[-1] == '_')) ||
            strncasecmp(p, "build ", 6)) continue;
        const char *first = p + 6;
        while (*first == ' ') ++first;
        if (!isdigit((unsigned char)*first)) continue;
        const char *q = first, *upper_end = first;
        int lower, upper;
        if (!build_interval_endpoint(&q, 0, &lower) ||
            !build_interval_endpoint(&upper_end, INT_MAX, &upper)) continue;
        if (isalnum((unsigned char)*q) || (*q == '-' && !build_variant_suffix(q))) continue;
        bool partial = false;
        for (const char *x = first; x < q; ++x)
            if (*x == 'X' || *x == 'x') partial = true;
        if (!partial) {
            if (*q != '_' && lower >= 1000 && lower <= 99999)
                return false; /* The first usable complete tag stays exact. */
            continue;
        }
        if (lower < 1000 || q - first > 5) continue;
        out->lower = lower; out->upper = upper;
        out->lower_known = out->upper_known = true;
        return true;
    }
    return false;
}

static bool profile_triage_preferred(const obor_profile_def *profile)
{
    return profile->automatic ||
        (!strstr(profile->disp, "-dev") && !strstr(profile->disp, "-alpha"));
}

static bool filename_missing_exact_profile(const char *path, int declared)
{
    if (declared <= 0) return false;
    for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); ++i)
        if (kProfiles[i].build == declared && profile_is_revision(&kProfiles[i])) return false;
    const char *base = strrchr(path, PATH_SEP);
    base = base ? base + 1 : path;
    for (const char *p = base; *p; ++p) {
        if ((p != base && (isalnum((unsigned char)p[-1]) || p[-1] == '_')) ||
            strncasecmp(p, "build ", 6)) continue;
        const char *first = p + 6;
        while (*first == ' ') ++first;
        if (!isdigit((unsigned char)*first)) continue;
        char *end;
        long value = strtol(first, &end, 10);
        if (value < 1000 || value > 99999 || isalnum((unsigned char)*end) ||
            ((*end == '_' || *end == '-') && !build_variant_suffix(end))) continue;
        return value == declared;
    }
    return false;
}

static uint64_t profile_triage_distance(const obor_profile_def *profile, int legacy)
{
    uint64_t result = content_contract_distance(profile->build, profile->engine_build);
    if (g_content_range_seen) {
        uint64_t low = profile->build < g_content_lower ? (uint64_t)g_content_lower - profile->build : 0;
        uint64_t high = profile->build > g_content_upper ? (uint64_t)profile->build - g_content_upper : 0;
        if (low > result) result = low;
        if (high > result) result = high;
    }
    /* The old attack-property API was removed in upstream build4167. The
     * existing probe proves a literal use; uncertain script binding does not. */
    if (legacy && g_contract_valid && !g_contract_scripts_ambiguous && profile->build >= 4167) {
        uint64_t gap = (uint64_t)profile->build - 4166;
        if (gap > result) result = gap;
    }
    return result;
}

static void profile_triage_log_rules(const obor_profile_def *best, int legacy, bool unlabelled = false)
{
    for (size_t i = 0; i < sizeof(kContentContracts) / sizeof(kContentContracts[0]); ++i) {
        if (!content_contract_active(i) && !(unlabelled && g_bound_contracts[i])) continue;
        const obor_contract_rule *rule = &kContentContracts[i];
        log_cb(RETRO_LOG_INFO, "[OpenBOR] content rule kind=%d name=%s bounds=%d-%d flags=%u selected=%s\n",
               (int)rule->kind, rule->name, rule->lower, rule->upper, rule->flags,
               content_contract_allows(rule, best->build, best->engine_build) ? "supported" :
                   unlabelled ? "incompatible" : "tag-conflict");
    }
    if (legacy && g_contract_valid && !g_contract_scripts_ambiguous)
        log_cb(RETRO_LOG_INFO, "[OpenBOR] content rule legacy-attack bounds=1-4166 selected=%s\n",
               best->build < 4167 ? "supported" : "tag-conflict");
    for (size_t i = 0; i < g_content_evidence_count; ++i) {
        const obor_content_evidence *row = &g_content_evidence[i];
        if (row->script && g_contract_scripts_ambiguous) continue;
        log_cb(RETRO_LOG_INFO, "[OpenBOR] existing content rule name=%s bounds=%d-%d\n",
               row->name, row->lower, row->upper);
    }
}

static int profile_triage_select(const filename_build_interval *interval, int legacy)
{
    const obor_profile_def *best = NULL;
    uint64_t best_distance = UINT64_MAX;
    for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); ++i) {
        const obor_profile_def *p = &kProfiles[i];
        if (!p->triage) continue;
        if (p->build < interval->lower || p->build > interval->upper) continue;
        uint64_t distance = profile_triage_distance(p, legacy);
        bool preferred = profile_triage_preferred(p);
        if (!best || distance < best_distance ||
            (distance == best_distance && preferred && !profile_triage_preferred(best)) ||
            (distance == best_distance && preferred == profile_triage_preferred(best) && p->build > best->build)) {
            best = p; best_distance = distance;
        }
    }
    if (!best) return profile_for_range(interval->lower, interval->upper, true);
    log_cb(RETRO_LOG_INFO,
           "[OpenBOR] filename triage %d-%d; content %d-%d; profile %d%s\n",
           interval->lower, interval->upper,
           g_content_range_seen ? g_content_lower : 1,
           g_content_range_seen ? g_content_upper : INT_MAX, best->build,
           best_distance ? "; content contradicts tag, keeping closest declared profile" : "");
    profile_triage_log_rules(best, legacy);
    return best->build;
}

static int profile_triage_exact_select(int declared, int legacy)
{
    int anchor = pick_anchor(declared);
    const obor_profile_def *candidate = NULL, *best = NULL;
    for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); ++i)
        if (kProfiles[i].build == anchor && profile_is_revision(&kProfiles[i])) candidate = &kProfiles[i];
    if (!candidate || !profile_triage_distance(candidate, legacy)) return 0;
    uint64_t closest = UINT64_MAX;
    for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); ++i) {
        const obor_profile_def *p = &kProfiles[i];
        if (!p->triage) continue;
        if (profile_triage_distance(p, legacy)) continue;
        uint64_t distance = p->build < declared ? (uint64_t)declared - p->build :
                                                 (uint64_t)p->build - declared;
        bool preferred = profile_triage_preferred(p);
        if (!best || distance < closest ||
            (distance == closest && preferred && !profile_triage_preferred(best)) ||
            (distance == closest && preferred == profile_triage_preferred(best) && p->build > best->build)) {
            best = p; closest = distance;
        }
    }
    if (!best) {
        log_cb(RETRO_LOG_WARN,
               "[OpenBOR] exact tag triage %d; candidate %d; no profile satisfies all proved requirements; retaining existing routing\n",
               declared, candidate->build);
        profile_triage_log_rules(candidate, legacy);
        return 0;
    }
    log_cb(RETRO_LOG_INFO,
           "[OpenBOR] exact tag triage %d; candidate %d conflicts with proved content; closest compatible profile %d\n",
           declared, candidate->build, best->build);
    profile_triage_log_rules(best, legacy);
    return best->build;
}

static bool profile_content_allows(const obor_profile_def *profile, bool legacy_attack)
{
    if (legacy_attack && profile->build > 4166) return false;
    if (profile_triage_distance(profile, 0)) return false;
    for (size_t i = 0; i < sizeof(g_bound_contracts); ++i)
        if (g_bound_contracts[i] &&
            !content_contract_allows(&kContentContracts[i], profile->build, profile->engine_build)) return false;
    for (size_t i = 0; i < sizeof(g_bound_native); ++i)
        if (g_bound_native[i] && !content_native_allows(i, profile->build)) return false;
    return true;
}

static void profile_content_log_rules(const obor_profile_def *profile, bool legacy_attack)
{
    profile_triage_log_rules(profile, 0, true);
    if (legacy_attack)
        log_cb(RETRO_LOG_INFO, "[OpenBOR] legacy-attack bounds=1-4166 supported by profile %s\n",
               profile->name);
    static const char *const registry_kinds[] = {"function", "constant", "system query", "entity getter"};
    for (size_t i = 0; i < sizeof(g_bound_native); ++i)
        if (g_bound_native[i])
            log_cb(RETRO_LOG_INFO, "[OpenBOR] bound native %s %s %s by profile %s\n",
                   registry_kinds[kNativeRequirements[i].kind], kNativeRequirements[i].name,
                   content_native_allows(i, profile->build) ? "supported" : "unsupported", profile->name);
}

static int profile_content_select(bool legacy_attack, int fallback_build, bool &contradiction)
{
    const obor_profile_def *best = NULL, *fallback = NULL;
    bool narrowed = false;
    contradiction = false;
    for (const auto &profile : kProfiles) {
        if (!profile.automatic || !profile_is_revision(&profile)) continue;
        if (profile.build == fallback_build) fallback = &profile;
        if (!profile_content_allows(&profile, legacy_attack)) {
            if (profile.build >= OBOR_FALLBACK_BUILD) narrowed = true;
            continue;
        }
        if (!best || profile.build > best->build) best = &profile;
    }
    /* An old minimum alone is shared by later eras and cannot place content
     * in one of them. Keep the ordinary fallback until evidence narrows it. */
    if (!narrowed) return 0;
    if (!best) {
        contradiction = true;
        log_cb(RETRO_LOG_WARN,
               "[OpenBOR] content requirements have no common automatic profile; using %s.\n",
               legacy_attack ? "the legacy API route" : "fallback");
        if (fallback) profile_content_log_rules(fallback, legacy_attack);
        return 0;
    }
    profile_content_log_rules(best, legacy_attack);
    return best->build;
}
#endif
