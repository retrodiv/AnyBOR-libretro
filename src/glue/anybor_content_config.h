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
#include "anybor_abi.h"

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
struct obor_content_choice {
    char source[4096], archive[4096], engine[48], descriptor[4096];
    char zip_engine[48], zip_descriptor[512], transform[64];
    obor_content_controls controls;
    obor_content_choice() : source(), archive(), engine(), descriptor(), zip_engine(), zip_descriptor(), transform(), controls() {}
};
struct obor_descriptor { char payload[512], engine[48], transform[64]; obor_content_controls controls; };

static void obor_descriptor_settings(obor_content_choice &choice, const obor_descriptor &descriptor)
{
    if (!choice.transform[0]) snprintf(choice.transform,sizeof(choice.transform),"%s",descriptor.transform);
    for (unsigned i=0;i<OBOR_BTN_COUNT;++i) {
        unsigned bit=1u<<i;
        if (!(choice.controls.mapped&bit) && (descriptor.controls.mapped&bit)) choice.controls.target[i]=descriptor.controls.target[i];
        if (!(choice.controls.labelled&bit) && (descriptor.controls.labelled&bit)) memcpy(choice.controls.labels[i],descriptor.controls.labels[i],sizeof(choice.controls.labels[i]));
    }
    choice.controls.mapped|=descriptor.controls.mapped;choice.controls.labelled|=descriptor.controls.labelled;
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
    const char *prefix = "[pak-imohash:";
    bool zip = n >= 12 && !strncmp(text, "[zip-imohash:", 12);
    if (zip) prefix = "[zip-imohash:";
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
static bool obor_descriptor_parse(const char *text, size_t size, obor_descriptor &out, bool allow_zip = true)
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
                      n==11 && !memcmp(line,"[overrides]",11) ? 2 :
                      n==10 && !memcmp(line,"[controls]",10) ? 4 :
                      n==8 && !memcmp(line,"[labels]",8) ? 8 : 0;
            if (!section || (seen & section)) return false;
            seen |= section;
        } else if (section==2) {
            if (!obor_content_engine_line(line,n,parsed.engine) &&
                !obor_content_transform_name(line,n,parsed.transform)) return false;
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
    if (!parsed.payload[0] || ((seen & 2) && !parsed.engine[0] && !parsed.transform[0])) return false;
    out = parsed;
    return true;
}
#endif
