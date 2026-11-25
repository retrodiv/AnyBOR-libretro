/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_CONTENT_OVERRIDE_H
#define OBOR_CONTENT_OVERRIDE_H
#include "anybor_file_io.h"
#include "anybor_transform.h"
#include "anybor_imohash.h"
#include "anybor_storage.h"
#include "anybor_prepare_progress.h"

/* Bounded, regular-file inputs; never read a device/FIFO as configuration. */
static bool obor_content_regular(const char *path)
{
#if defined(_WIN32)
    DWORD a = obor_win_attributes(path);
    return a != INVALID_FILE_ATTRIBUTES && !(a & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT));
#else
    struct stat s;
    return !lstat(path,&s) && S_ISREG(s.st_mode);
#endif
}
static bool obor_descriptor_read(const char *path, obor_descriptor &out)
{
    if (!obor_content_regular(path)) return false;
    FILE *file = obor_fopen(path,"rb");
    if (!file) return false;
    char *text = (char *)malloc(OBOR_DESCRIPTOR_MAX_BYTES+1);
    size_t got = text ? fread(text,1,OBOR_DESCRIPTOR_MAX_BYTES+1,file) : 0;
    bool ok = text && !ferror(file) && obor_descriptor_parse(text,got,out);
    free(text); fclose(file);
    return ok;
}
static const char *obor_content_basename(const char *path)
{
    const char *name = path;
    for (const char *p=path; *p; ++p) if (*p=='/' || *p=='\\') name=p+1;
    return name;
}
/* The descriptor may select only a regular PAK or ZIP inside its subtree.
 * No symlink/junction component can redirect a declared relative target. */
static bool obor_descriptor_target(const char *descriptor, const char *payload, char *out, size_t cap)
{
    size_t root = (size_t)(obor_content_basename(descriptor)-descriptor);
    if (root+strlen(payload)+1 > cap) return false;
    memcpy(out,descriptor,root); strcpy(out+root,payload);
    for (char *p=out+root; *p; ++p) if (*p=='/') {
        *p=0; bool ok=obor_storage_directory(out); *p='/';
        if (!ok) return false;
    }
    return obor_content_regular(out);
}
static bool obor_content_loose(const char *path, char *out, size_t cap, obor_content_choice &choice)
{
    if (strlen(path)>=cap) return false;
    strcpy(out,path);
    if (obor_content_suffix(path,".anybor")) {
        obor_descriptor descriptor = {};
        if (!obor_descriptor_read(path,descriptor) ||
            !obor_descriptor_target(path,descriptor.payload,out,cap)) {
            log_cb(RETRO_LOG_ERROR,"[OpenBOR] invalid descriptor or missing payload: %s\n",path);
            return false;
        }
        snprintf(choice.engine,sizeof(choice.engine),"%s",descriptor.engine);
        obor_descriptor_settings(choice,descriptor);
        snprintf(choice.descriptor,sizeof(choice.descriptor),"%s",path);
    } else if (obor_content_suffix(path,".pak") || obor_content_suffix(path,".spk") ||
               obor_content_suffix(path,".zip")) {
        char parent[4096];
        size_t root=(size_t)(obor_content_basename(path)-path);
        if (!root || root>=sizeof(parent)) return false;
        memcpy(parent,path,root); parent[root]=0;
        obor_path_directory *dir=obor_opendir(parent);
        if (!dir) return false;
        unsigned scanned=0, matched=0;
        bool ok=true;
        obor_path_entry *entry;
        while ((entry=obor_readdir(dir))) {
            if (++scanned>4096) { ok=false; break; }
            if (!obor_content_suffix(entry->d_name,".anybor")) continue;
            char descriptor_path[4096], target[4096];
            obor_descriptor descriptor = {};
            int length=snprintf(descriptor_path,sizeof(descriptor_path),"%s%s",parent,entry->d_name);
            if (length<0 || (size_t)length>=sizeof(descriptor_path)) { ok=false; break; }
            if (!obor_descriptor_read(descriptor_path,descriptor)) {
                log_cb(RETRO_LOG_WARN,"[OpenBOR] ignoring invalid sibling descriptor: %s\n",descriptor_path);
                continue;
            }
            if (!obor_descriptor_target(descriptor_path,descriptor.payload,target,sizeof(target))) continue;
#if defined(_WIN32)
            bool same=!strcasecmp(path,target);
#else
            bool same=!strcmp(path,target);
#endif
            if (!same) continue;
            ++matched;
            snprintf(choice.engine,sizeof(choice.engine),"%s",descriptor.engine);
        obor_descriptor_settings(choice,descriptor);
            snprintf(choice.descriptor,sizeof(choice.descriptor),"%s",descriptor_path);
        }
        obor_closedir(dir);
        if (!ok || matched>1) {
            log_cb(RETRO_LOG_ERROR,"[OpenBOR] sibling descriptor scan incomplete or ambiguous\n");
            return false;
        }
    }
    if (obor_content_suffix(out,".pak") || obor_content_suffix(out,".spk"))
        snprintf(choice.source,sizeof(choice.source),"%s",out);
    if (obor_content_suffix(out,".zip"))
        snprintf(choice.archive,sizeof(choice.archive),"%s",out);
    return true;
}
static int obor_content_hash_read(void *context, uint64_t offset, void *data, size_t size)
{
    FILE *file=(FILE *)context;
#if defined(_WIN32)
    if (_fseeki64(file,(__int64)offset,SEEK_SET)) return 0;
#else
    if (fseeko(file,(off_t)offset,SEEK_SET)) return 0;
#endif
    return fread(data,1,size,file)==size && obor_prepare_checkpoint();
}
/* INI rules identify either the complete original ZIP or its selected,
 * untransformed PAK. Kind/size filtering avoids unnecessary sampled reads. */
static bool obor_content_override(const char *system, const obor_content_choice &choice,
                                  char engine[48], char *evidence, size_t capacity)
{
    engine[0]=0; evidence[0]=0;
    obor_content_rules rules;
    if (system && system[0]) {
        char path[4096], error[256]={0};
        if (!obor_storage_join(path,sizeof(path),system,"AnyBOR.ini")) return false;
        struct stat configuration;
        if (!obor_stat(path,&configuration) && !S_ISREG(configuration.st_mode)) return false;
        FILE *file=obor_fopen(path,"rb");
        if (file) {
            char *text=(char *)malloc(OBOR_TRANSFORM_MAX_CONFIG_BYTES+1u);
            size_t size=text ? fread(text,1,OBOR_TRANSFORM_MAX_CONFIG_BYTES+1u,file) : 0;
            obor_input_transform transform;
            bool ok=text && !ferror(file) && size<=OBOR_TRANSFORM_MAX_CONFIG_BYTES;
            /* Content preparation owns transform errors and its structural
             * repair exception. Only section-shaped selector declarations
             * opt into this independent engine configuration surface. The
             * real parser then owns function/comment/string boundaries. */
            bool selectors=false;
            for (size_t at=0; ok && at<size;) {
                size_t first=at, end;
                while (at<size && text[at]!='\r' && text[at]!='\n') ++at;
                end=at;
                while (at<size && (text[at]=='\r' || text[at]=='\n')) ++at;
                while (first<end && (text[first]==' ' || text[first]=='\t')) ++first;
                if (size>=3 && first==0 && !memcmp(text,"\xef\xbb\xbf",3)) first=3;
                if (first<end && text[first]=='[' && memchr(text+first,':',end-first)) selectors=true;
            }
            if (ok && selectors) ok=obor_transform_parse(text,size,transform,error,sizeof(error),&rules);
            free(text); fclose(file);
            if (!ok) { log_cb(RETRO_LOG_ERROR,"[OpenBOR] AnyBOR.ini: %s\n",error); return false; }
        } else if (errno!=ENOENT) return false;
    }
    /* The outer ZIP rule wins over the selected, untransformed PAK rule. */
    for (unsigned kind=0; kind<2; ++kind) {
        bool zip = kind==0;
        const char *source = zip ? choice.archive : choice.source;
        bool relevant=false;
        for (unsigned i=0;i<rules.count;++i) if (rules.rows[i].zip==zip) relevant=true;
        if (!relevant || !source[0]) continue;
#if defined(_WIN32)
        struct _stat64 st;
        if (obor_win_stat64(source,&st) || !(st.st_mode & _S_IFREG) || st.st_size<0) return false;
#else
        struct stat st;
        if (obor_stat(source,&st) || !S_ISREG(st.st_mode) || st.st_size<0) return false;
#endif
        bool candidate=false;
        for (unsigned i=0;i<rules.count;++i) if (rules.rows[i].zip==zip && rules.rows[i].size==(uint64_t)st.st_size) candidate=true;
        if (candidate) {
            FILE *file=obor_fopen(source,"rb");
            unsigned char digest[16]; char hex[33];
            bool ok=file && obor_imohash_read(obor_content_hash_read,file,(uint64_t)st.st_size,digest);
            if (file) fclose(file);
            if (!ok) return false;
            for (unsigned i=0;i<16;++i) snprintf(hex+2*i,3,"%02x",digest[i]);
            for (unsigned i=0;i<rules.count;++i)
                if (rules.rows[i].zip==zip && rules.rows[i].size==(uint64_t)st.st_size && !strcmp(rules.rows[i].hash,hex)) {
                    snprintf(engine,48,"%s",rules.rows[i].engine);
                    snprintf(evidence,capacity,"AnyBOR.ini imohash:%s:%s", zip ? "zip" : "pak", hex);
                    return true;
                }
        }
    }
    if (choice.engine[0]) {
        snprintf(engine,48,"%s",choice.engine);
        snprintf(evidence,capacity,"descriptor %s",choice.descriptor);
    } else if (choice.zip_engine[0]) {
        snprintf(engine,48,"%s",choice.zip_engine);
        snprintf(evidence,capacity,"descriptor %s",choice.zip_descriptor);
    }
    return true;
}
#endif
