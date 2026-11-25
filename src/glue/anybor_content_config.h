/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_CONTENT_CONFIG_H
#define OBOR_CONTENT_CONFIG_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <math.h>
#include "anybor_zip_path.h"
#include "anybor_abi.h"
#include "anybor_crt.h"
#include "anybor_presentation_number.h"
#include "anybor_transform_vm.h"

#define OBOR_OVERRIDE_MAX_RULES 256U
#define OBOR_DESCRIPTOR_MAX_BYTES 65536U
struct obor_override_rule { uint64_t size; bool zip; char hash[33], engine[48]; };
struct obor_content_rules {
    obor_override_rule rows[OBOR_OVERRIDE_MAX_RULES];
    unsigned count;
    obor_content_rules() : rows(), count(0) {}
};
struct obor_content_controls {
    unsigned char target[OBOR_BTN_COUNT];
    char labels[OBOR_BTN_COUNT][48];
    unsigned mapped, labelled;
    obor_content_controls() : target(), labels(), mapped(0), labelled(0) {
        for (unsigned i=0;i<OBOR_BTN_COUNT;++i) target[i]=(unsigned char)i;
    }
};
static int obor_content_button(const char *name, size_t size)
{
    static const char *names[] = {"up","down","left","right","attack","attack2",
        "attack3","attack4","jump","special","start","escape","none"};
    for (unsigned i=0;i<sizeof(names)/sizeof(*names);++i)
        if (strlen(names[i])==size && !memcmp(name,names[i],size)) return (int)i;
    return -1;
}
static unsigned obor_content_buttons(const obor_content_controls &controls, unsigned input)
{
    unsigned result=0;
    for (unsigned i=0;i<OBOR_BTN_COUNT;++i)
        if ((input & (1u<<i)) && controls.target[i]<OBOR_BTN_COUNT)
            result |= 1u<<controls.target[i];
    return result;
}
static bool obor_content_control_line(const char *line, size_t size,
                                      obor_content_controls &controls, bool label)
{
    const char *equal=(const char *)memchr(line,'=',size);
    if (!equal) return false;
    size_t key=(size_t)(equal-line), first=key+1, end=size;
    while (key && (line[key-1]==' ' || line[key-1]=='\t')) --key;
    while (first<end && (line[first]==' ' || line[first]=='\t')) ++first;
    while (end>first && (line[end-1]==' ' || line[end-1]=='\t')) --end;
    int source=obor_content_button(line,key);
    if (source<0 || source>=OBOR_BTN_COUNT || first==end) return false;
    unsigned bit=1u<<source;
    if (label) {
        if ((controls.labelled&bit) || end-first>=sizeof(controls.labels[0])) return false;
        for (size_t i=first;i<end;++i) if ((unsigned char)line[i]<32 || line[i]==127) return false;
        memcpy(controls.labels[source],line+first,end-first);
        controls.labels[source][end-first]=0;controls.labelled|=bit;
    } else {
        int target=obor_content_button(line+first,end-first);
        if ((controls.mapped&bit) || target<0) return false;
        controls.target[source]=(unsigned char)target;controls.mapped|=bit;
    }
    return true;
}
static bool obor_content_transform_name(const char *line, size_t size, char name[64])
{
    const char *equal=(const char *)memchr(line,'=',size);
    if (!equal || name[0]) return false;
    size_t key=(size_t)(equal-line), first=key+1, end=size;
    while (key && (line[key-1]==' ' || line[key-1]=='\t')) --key;
    while (first<end && (line[first]==' ' || line[first]=='\t')) ++first;
    while (end>first && (line[end-1]==' ' || line[end-1]=='\t')) --end;
    if (key!=9 || memcmp(line,"transform",9) || end==first || end-first>=64) return false;
    for (size_t i=first;i<end;++i) {
        char c=line[i];
        if (!((c>='a'&&c<='z') || (c>='0'&&c<='9') || c=='.' || c=='_' || c=='-')) return false;
    }
    memcpy(name,line+first,end-first);name[end-first]=0;return true;
}
/* Value storage keeps descriptor copies independent, including ZIP routing.
 * The compiler limits bound both buffers before anything is installed. */
struct obor_content_function {
    unsigned char program[OBOR_TRANSFORM_MAX_PROGRAM_BYTES];
    unsigned char parameters[OBOR_TRANSFORM_MAX_PARAMETER_BYTES];
    size_t program_size, parameter_size;
    obor_content_function() : program(), parameters(), program_size(0), parameter_size(0) {}
};
struct obor_window_raster {
    int width, height;
};

struct obor_presentation_directives {
    obor_crt_mode crt_mode;
    obor_window_raster crt_rasters[2];
    uint16_t level_rates[OBOR_PRESENTATION_LEVELS];
    obor_numeric_override numbers[OBOR_PRESENTATION_OVERRIDES];
    unsigned number_count;
};

struct obor_content_choice {
    char source[4096], archive[4096], engine[48], descriptor[4096];
    char zip_engine[48], zip_descriptor[512], transform[64];
    obor_content_function function;
    obor_content_controls controls;
    obor_presentation_directives presentation;
    obor_content_choice() : source(), archive(), engine(), descriptor(), zip_engine(), zip_descriptor(), transform(), controls(), presentation() {}
};
struct obor_descriptor {
    char payload[512], engine[48], transform[64];
    obor_content_controls controls;
    obor_content_function function;
    obor_presentation_directives presentation;
};

static bool obor_same_numeric_target(const obor_numeric_override &a, const obor_numeric_override &b)
{
    return a.scope == b.scope && a.target == b.target &&
           !strcmp(a.name, b.name) && !strcmp(a.condition, b.condition);
}

static bool obor_add_numeric_override(obor_presentation_directives &policy,
                                      const obor_numeric_override &rule)
{
    unsigned i = 0;
    for (; i < policy.number_count; ++i)
        if (obor_same_numeric_target(policy.numbers[i], rule)) break;
    if (i == policy.number_count && i == OBOR_PRESENTATION_OVERRIDES) return false;
    if (i < policy.number_count) {
        --policy.number_count;
        memmove(&policy.numbers[i], &policy.numbers[i+1],
                (policy.number_count - i) * sizeof(rule));
    }
    policy.numbers[policy.number_count++] = rule;
    return true;
}

static bool obor_descriptor_settings(obor_content_choice &choice, const obor_descriptor &descriptor)
{
    auto &higher = choice.presentation;
    const auto &lower = descriptor.presentation;
    if (!higher.crt_mode.declared) higher.crt_mode = lower.crt_mode;
    for (unsigned axis = 0; axis < 2; ++axis)
        if (!higher.crt_rasters[axis].width) higher.crt_rasters[axis] = lower.crt_rasters[axis];
    for (unsigned level = 0; level < OBOR_PRESENTATION_LEVELS; ++level)
        if (!higher.level_rates[level]) higher.level_rates[level] = lower.level_rates[level];
    if (lower.number_count) {
        obor_presentation_directives merged = lower;
        for (unsigned i = 0; i < higher.number_count; ++i)
            if (!obor_add_numeric_override(merged, higher.numbers[i])) return false;
        memcpy(higher.numbers, merged.numbers, sizeof(higher.numbers));
        higher.number_count = merged.number_count;
    }
    if (!choice.transform[0] && !choice.function.program_size) {
        snprintf(choice.transform,sizeof(choice.transform),"%s",descriptor.transform);
        choice.function=descriptor.function;
    }
    for (unsigned i=0;i<OBOR_BTN_COUNT;++i) {
        unsigned bit=1u<<i;
        if (!(choice.controls.mapped&bit) && (descriptor.controls.mapped&bit)) choice.controls.target[i]=descriptor.controls.target[i];
        if (!(choice.controls.labelled&bit) && (descriptor.controls.labelled&bit)) memcpy(choice.controls.labels[i],descriptor.controls.labels[i],sizeof(choice.controls.labels[i]));
    }
    choice.controls.mapped|=descriptor.controls.mapped;choice.controls.labelled|=descriptor.controls.labelled;
    return true;
}

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
    const char zip_prefix[] = "[imohash:zip:";
    bool zip = n >= sizeof(zip_prefix)-1 && !strncmp(text, zip_prefix, sizeof(zip_prefix)-1);
    const char *prefix = zip ? zip_prefix : "[imohash:pak:";
    const size_t prefix_size = strlen(prefix);
    const char suffix[] = ".overrides]";
    if (n != prefix_size + 32 + sizeof(suffix)-1 ||
        strncmp(text, prefix, prefix_size) ||
        memcmp(text + n - (sizeof(suffix)-1), suffix, sizeof(suffix)-1) ||
        rules.count == OBOR_OVERRIDE_MAX_RULES) return false;
    obor_override_rule rule = {};
    rule.zip = zip;
    unsigned char bytes[16] = {};
    for (unsigned i = 0; i < 32; ++i) {
        unsigned char c = (unsigned char)text[prefix_size+i];
        if (!isxdigit(c)) return false;
        c = (unsigned char)tolower(c);
        rule.hash[i] = (char)c;
        unsigned digit = c <= '9' ? c-'0' : c-'a'+10;
        bytes[i/2] = (unsigned char)((bytes[i/2] << 4) | digit);
    }
    /* Standard imohash begins with the file size as canonical unsigned LEB128.
     * Recover it for size filtering without a redundant selector field. */
    bool complete = false;
    for (unsigned i = 0; i < 10; ++i) {
        unsigned byte = bytes[i];
        if (i == 9 && byte > 1) return false;
        rule.size |= (uint64_t)(byte & 127) << (7*i);
        if (!(byte & 128)) {
            if (i && !byte) return false;
            complete = true;
            break;
        }
    }
    if (!complete || !rule.size) return false;
    for (unsigned i = 0; i < rules.count; ++i)
        if (rules.rows[i].zip == zip && rules.rows[i].size == rule.size && !strcmp(rules.rows[i].hash, rule.hash)) return false;
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
static bool obor_crt_mode_field(const char *first, const char *end, const char *follow,
                                int minimum, int maximum, int &value)
{
    if (follow && (size_t)(end - first) == strlen(follow) && !memcmp(first, follow, (size_t)(end - first))) {
        value = 0;
        return true;
    }
    if (first == end) return false;
    value = 0;
    for (; first < end; ++first) {
        if (*first < '0' || *first > '9') return false;
        value = value * 10 + (*first - '0');
        if (value > maximum) return false;
    }
    return value >= minimum;
}

static bool obor_presentation_prefix(const char *&body, const char *end, const char *prefix)
{
    size_t count = strlen(prefix);
    if ((size_t)(end - body) < count || memcmp(body, prefix, count)) return false;
    body += count;
    return true;
}

static bool obor_parse_presentation_scope(const char *&body, const char *end,
                                          obor_presentation_scope &scope)
{
    if (obor_presentation_prefix(body, end, "?crt=horizontal")) scope = OBOR_SCOPE_CRT_HORIZONTAL;
    else if (obor_presentation_prefix(body, end, "?crt=vertical")) scope = OBOR_SCOPE_CRT_VERTICAL;
    else if (obor_presentation_prefix(body, end, "?crt")) scope = OBOR_SCOPE_CRT;
    else if (obor_presentation_prefix(body, end, "?gameres")) scope = OBOR_SCOPE_GAMERES;
    else return false;
    if (body == end || (*body != ' ' && *body != '\t')) return false;
    while (body < end && (*body == ' ' || *body == '\t')) ++body;
    return body < end;
}

static bool obor_crt_mode_line(const char *width, const char *end, obor_crt_mode &mode)
{
    const char *height = (const char *)memchr(width, '|', (size_t)(end - width));
    if (!height) return false;
    const char *hz = (const char *)memchr(height + 1, '|', (size_t)(end - height - 1));
    obor_crt_mode parsed = {1, 0, 0, 0};
    if (!hz || !obor_crt_mode_field(width, height, "window_w", 16, 640, parsed.width) ||
        !obor_crt_mode_field(height + 1, hz, "window_h", 16, 480, parsed.height) ||
        !obor_crt_mode_field(hz + 1, end, "window_fps", 2, 300, parsed.hz)) return false;
    mode = parsed;
    return true;
}

static bool obor_level_rate_line(const char *body, const char *end, uint16_t *rates)
{
    const char *separator = (const char *)memchr(body, '|', (size_t)(end - body));
    int rate;
    if (!separator || !obor_crt_mode_field(separator + 1, end, NULL, 1, 300, rate)) return false;
    for (;;) {
        const char *comma = (const char *)memchr(body, ',', (size_t)(separator - body));
        const char *last = comma ? comma : separator;
        const char *dash = (const char *)memchr(body, '-', (size_t)(last - body));
        int lo, hi;
        if (!obor_crt_mode_field(body, dash ? dash : last, NULL, 0, OBOR_PRESENTATION_LEVELS-1, lo))
            return false;
        hi = lo;
        if (dash && !obor_crt_mode_field(dash + 1, last, NULL, lo, OBOR_PRESENTATION_LEVELS-1, hi))
            return false;
        for (int level = lo; level <= hi; ++level) rates[level] = (uint16_t)rate;
        if (!comma) return true;
        body = comma + 1;
    }
}

static bool obor_presentation_name(const char *first, const char *last,
                                    char (&name)[OBOR_PRESENTATION_NAME])
{
    size_t size = (size_t)(last - first);
    if (!size || size >= sizeof(name)) return false;
    for (const char *p = first; p < last; ++p)
        if (!obor_presentation_name_char(*p)) return false;
    memcpy(name, first, size);
    name[size] = 0;
    return true;
}

static bool obor_numeric_override_line(const char *body, const char *end,
                                       obor_presentation_scope scope,
                                       obor_presentation_directives &policy)
{
    obor_numeric_override rule = {};
    rule.scope = (uint8_t)scope;
    if (obor_presentation_prefix(body, end, "?global.")) {
        const char *last = body;
        while (last < end && *last != ' ' && *last != '\t') ++last;
        if (last == end || !obor_presentation_name(body, last, rule.condition)) return false;
        body = last;
        while (body < end && (*body == ' ' || *body == '\t')) ++body;
    }
    bool drawing = obor_presentation_prefix(body, end, "drawhold|");
    if (!drawing && scope != OBOR_SCOPE_CRT && scope != OBOR_SCOPE_GAMERES) return false;
    const char *separator = (const char *)memchr(body, drawing ? '|' : '=', (size_t)(end - body));
    if (!separator) return false;
    if (drawing || obor_presentation_prefix(body, separator, "$")) {
        rule.target = drawing ? OBOR_TARGET_DRAW : OBOR_TARGET_GLOBAL;
        if (!obor_presentation_name(body, separator, rule.name)) return false;
    } else {
        static const char *const fields[] = {"@window_w", "@window_h", "@present_crop_left",
            "@present_crop_top", "@present_crop_right", "@present_crop_bottom",
            "@present_shift_x", "@present_shift_y"};
        static_assert(sizeof(fields) / sizeof(*fields) == OBOR_TARGET_COUNT - OBOR_TARGET_WINDOW_W,
                      "host override fields must match their target values");
        unsigned field = 0;
        while (field < sizeof(fields) / sizeof(*fields)) {
            const char *key = body;
            if (obor_presentation_prefix(key, separator, fields[field]) && key == separator) break;
            ++field;
        }
        if (field == sizeof(fields) / sizeof(*fields)) return false;
        rule.target = (uint8_t)(OBOR_TARGET_WINDOW_W + field);
    }
    size_t size = (size_t)(end - separator - 1);
    if (!size || size >= sizeof(rule.expression)) return false;
    memcpy(rule.expression, separator + 1, size);
    double ignored;
    return obor_presentation_number(rule.expression, NULL, &ignored) &&
           obor_add_numeric_override(policy, rule);
}

static bool obor_presentation_line(const char *body, size_t size,
                                   obor_presentation_directives &policy)
{
    const char *end = body + size;
    obor_presentation_scope scope;
    if (!obor_parse_presentation_scope(body, end, scope)) return false;
    if (obor_presentation_prefix(body, end, "crtmode|"))
        return scope == OBOR_SCOPE_CRT && obor_crt_mode_line(body, end, policy.crt_mode);
    if (obor_presentation_prefix(body, end, "roomspeed|"))
        return scope == OBOR_SCOPE_CRT && obor_level_rate_line(body, end, policy.level_rates);
    if (!obor_presentation_prefix(body, end, "windowraster|"))
        return obor_numeric_override_line(body, end, scope, policy);
    if (scope == OBOR_SCOPE_GAMERES) return false;
    const char *height = (const char *)memchr(body, '|', (size_t)(end - body));
    obor_window_raster raster = {};
    if (!height || !obor_crt_mode_field(body, height, NULL, 1, 3840, raster.width) ||
        !obor_crt_mode_field(height + 1, end, NULL, 1, 2160, raster.height)) return false;
    if (scope != OBOR_SCOPE_CRT_VERTICAL) policy.crt_rasters[0] = raster;
    if (scope != OBOR_SCOPE_CRT_HORIZONTAL) policy.crt_rasters[1] = raster;
    return true;
}

static bool obor_presentation_lines(const char *first, size_t size,
                                    obor_presentation_directives &policy)
{
    const char *end = first + size;
    while (first < end) {
        const char *separator = (const char *)memchr(first, ';', (size_t)(end - first));
        const char *last = separator ? separator : end;
        while (first < last && (*first == ' ' || *first == '\t')) ++first;
        while (last > first && (last[-1] == ' ' || last[-1] == '\t')) --last;
        if (first != last && !obor_presentation_line(first, (size_t)(last - first), policy))
            return false;
        first = separator ? separator + 1 : end;
    }
    return true;
}

static bool obor_descriptor_parse(const char *text, size_t size, obor_descriptor &out, bool allow_zip = true)
{
    obor_descriptor parsed = {};
    if (!size || size > OBOR_DESCRIPTOR_MAX_BYTES || memchr(text, 0, size)) return false;
    unsigned section = 0, seen = 0;
    bool has_presentation = false;
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
                      n==11 && !memcmp(line,"[overrides]",11) ? 2 :
                      n==10 && !memcmp(line,"[controls]",10) ? 4 :
                      n==8 && !memcmp(line,"[labels]",8) ? 8 : 0;
            if (!section || (seen & section)) return false;
            seen |= section;
        } else if (section==2) {
            if (line[0]=='?') {
                if (!obor_presentation_lines(line, n, parsed.presentation)) return false;
                has_presentation = true;
                continue;
            }
            if (obor_content_engine_line(line,n,parsed.engine)) continue;
            if (parsed.transform[0] || parsed.function.program_size) return false;
            if (obor_content_transform_name(line,n,parsed.transform)) continue;
            const char *equal=(const char *)memchr(line,'=',n);
            size_t key=equal ? (size_t)(equal-line) : 0;
            while (key && (line[key-1]==' ' || line[key-1]=='\t')) --key;
            if (!equal || key!=9 || memcmp(line,"transform",9)) return false;
            const char *source=equal+1;
            unsigned char *program=NULL,*parameters=NULL;
            size_t consumed=0,program_size=0,parameter_size=0;
            char error[256]={0};
            bool ok=obor_content_transform_compile(source,size-(size_t)(source-text),&consumed,
                &program,&program_size,&parameters,&parameter_size,error,sizeof(error)) != 0;
            ok=ok && consumed && consumed<=size-(size_t)(source-text) && program_size &&
                program_size<=sizeof(parsed.function.program) && parameter_size<=sizeof(parsed.function.parameters);
            if (ok) {
                memcpy(parsed.function.program,program,program_size);
                memcpy(parsed.function.parameters,parameters,parameter_size);
                parsed.function.program_size=program_size;parsed.function.parameter_size=parameter_size;
            }
            free(program);free(parameters);
            if (!ok) return false;
            at=(size_t)(source-text)+consumed;
            while (at<size && (text[at]==' ' || text[at]=='\t')) ++at;
            if (at<size && text[at]!='\r' && text[at]!='\n') return false;
        } else if (section==4 || section==8) {
            if (!obor_content_control_line(line,n,parsed.controls,section==8)) return false;
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
                 !obor_content_suffix(parsed.payload,".spk") &&
                 !(allow_zip && obor_content_suffix(parsed.payload,".zip")))) return false;
        } else return false;
    }
    if (!parsed.payload[0] || ((seen & 2) && !parsed.engine[0] && !parsed.transform[0] &&
        !parsed.function.program_size && !has_presentation)) return false;
    out = parsed;
    return true;
}
#endif
