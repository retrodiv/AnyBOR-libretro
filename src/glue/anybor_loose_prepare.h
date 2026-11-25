/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_LOOSE_PREPARE_H
#define OBOR_LOOSE_PREPARE_H
#include "anybor_file_io.h"

/* An explicit descriptor function can prepare a resolved loose game. Each
 * invocation receives one asset and its normalized relative name as metadata.
 * ZIP extraction remains immutable; publication owns a separate bounded tree. */
static bool obor_loose_prepare(const char *cache, const char *models,
    const obor_zip_content_entries &entries, unsigned count, const char *save_dir,
    const char *system_dir, const char *key, const obor_content_function *function,
    char *out, size_t capacity)
{
    bool local = function && function->program_size;
    if (!local && (!key || !*key)) {
        int n = snprintf(out,capacity,"%s",models);
        return n>=0 && (size_t)n<capacity;
    }
    obor_input_transform transform;
    if (local) {
        if (function->program_size>OBOR_TRANSFORM_MAX_PROGRAM_BYTES ||
            function->parameter_size>OBOR_TRANSFORM_MAX_PARAMETER_BYTES) return false;
        transform.program=(unsigned char *)malloc(function->program_size);
        transform.parameters=(unsigned char *)malloc(function->parameter_size ? function->parameter_size : 1u);
        if (!transform.program || !transform.parameters) return false;
        memcpy(transform.program,function->program,function->program_size);
        memcpy(transform.parameters,function->parameters,function->parameter_size);
        transform.program_size=function->program_size;transform.parameter_size=function->parameter_size;
    } else if (!obor_transform_load(system_dir,transform,key) || !transform.program) return false;

    size_t prefix=strlen(cache)+1, length=strlen(models);
    static const char suffix[]="data/models.txt";
    if (length<prefix+sizeof(suffix)-1 || strncmp(models,cache,prefix-1) || models[prefix-1]!='/') return false;
    size_t root_length=length-(sizeof(suffix)-1);
    size_t relative_root=root_length-prefix;
    uint64_t total=0;
    for (unsigned i=0;i<count;++i) {
        const obor_zip_content_entry &entry=entries.data[i];
        if (strncasecmp(entry.name,models+prefix,relative_root)) continue;
        if (entry.size>OBOR_ZIP_MAX_TOTAL-total) return false;
        total+=entry.size;
    }
    char parent[1400];
    if (!obor_storage_root(save_dir,parent,sizeof(parent)) || !obor_zip_space_ok(parent,total+(64u<<20))) return false;
    obor_zip_partial_scope partial;
    static unsigned sequence;
#if defined(_WIN32)
    unsigned long pid=(unsigned long)GetCurrentProcessId();
#else
    unsigned long pid=(unsigned long)getpid();
#endif
    int n=snprintf(partial.path,sizeof(partial.path),"%s/.files-partial-%lu-%u",parent,pid,++sequence);
    if (n<0 || (size_t)n>=sizeof(partial.path) || !obor_storage_track(partial.path) ||
        !obor_storage_remove(partial.path)) return false;
    mkdir_p(partial.path);
    if (!obor_storage_directory(partial.path)) return false;
    char config_hash[65];
    obor_transform_identity(transform,config_hash);
    obor_sha256_ctx tree;
    obor_sha256_init(&tree);
    obor_sha256_update(&tree,config_hash,sizeof(config_hash));
    obor_sha256_update(&tree,models,root_length);
    bool changed=false;
    uint64_t output_total=0;
    unsigned files=0;
    obor_prepare_range progress=obor_prepare_phase;
    obor_prepare_stage(progress,0,900,total);
    for (unsigned i=0;i<count;++i) {
        const obor_zip_content_entry &entry=entries.data[i];
        if (strncasecmp(entry.name,models+prefix,relative_root)) continue;
        const char *relative=entry.name+relative_root;
        if (!*relative) continue;
        char source[2200], destination[2200];
        if (!obor_prepare_checkpoint() ||
            !obor_archive_disk_path(cache,entry.name,source,sizeof(source),false,entry.directory) ||
            !obor_archive_disk_path(partial.path,relative,destination,sizeof(destination),true,entry.directory)) return false;
        if (entry.directory) continue;
        const char *metadata=entry.lower+relative_root;
        size_t metadata_size=strlen(metadata);
        if (metadata_size>OBOR_TRANSFORM_MAX_METADATA_BYTES || ++files>OBOR_ZIP_MAX_ENTRIES) return false;
        FILE *input=obor_fopen(source,"rb");
        if (!input) return false;
        if (obor_file_seek64(input,0,SEEK_END) || obor_file_tell64(input)!=(int64_t)entry.size) {fclose(input);return false;}
        obor_transform_file reader(input,entry.size);
        obor_transform_buffers buffers;
        char error[256]={0};
        bool ok=obor_content_transform_execute_reader(transform.program,transform.program_size,
            transform.parameters,transform.parameter_size,obor_transform_file::read,&reader,entry.size,
            metadata,metadata_size,0,&buffers.result,error,sizeof(error)) != 0;
        if (!ok || buffers.result.size>OBOR_ZIP_MAX_FILE || buffers.result.size>OBOR_ZIP_MAX_TOTAL-output_total) {
            fclose(input);
            log_cb(RETRO_LOG_ERROR,"[OpenBOR] File preparation failed for %s: %s\n",relative,error[0]?error:"output quota exceeded");
            return false;
        }
        output_total+=buffers.result.size;
        changed=changed || !buffers.result.reader_view || buffers.result.input_offset || buffers.result.size!=entry.size;
        obor_sha256_update(&tree,relative,strlen(relative)+1);
        uint64_t result_size=buffers.result.size;
        obor_sha256_update(&tree,&result_size,sizeof(result_size));
        FILE *output=obor_fopen(destination,"wb");
        if (!output) {fclose(input);return false;}
        unsigned char block[65536];
        for (size_t offset=0;ok && offset<buffers.result.size;) {
            size_t bytes=buffers.result.size-offset;
            if (bytes>sizeof(block)) bytes=sizeof(block);
            const unsigned char *data;
            if (buffers.result.reader_view) {
                ok=obor_transform_file::read(&reader,buffers.result.input_offset+offset,block,bytes)!=0;
                data=block;
            } else data=buffers.result.data+offset;
            if (ok) ok=fwrite(data,1,bytes,output)==bytes;
            if (ok) {
                obor_sha256_update(&tree,data,bytes);
                obor_prepare_advance(bytes);ok=obor_prepare_checkpoint()!=0;
            }
            offset+=bytes;
        }
        if (fclose(output)) ok=false;
        fclose(input);
        if (!ok) return false;
    }
    if (!files || !obor_game_recognizable(partial.path,false)) return false;
    if (!changed) {
        n=snprintf(out,capacity,"%s",models);
        return n>=0 && (size_t)n<capacity;
    }
    unsigned char digest[32];
    char identity[65], prepared[1600], marker[1700];
    obor_sha256_final(&tree,digest);
    for (unsigned i=0;i<32;++i) snprintf(identity+2*i,3,"%02x",digest[i]);
    n=snprintf(prepared,sizeof(prepared),"%s/files-%.16s",parent,identity);
    if (n<0 || (size_t)n>=sizeof(prepared) || !obor_storage_track(prepared)) return false;
    n=snprintf(marker,sizeof(marker),"%s/.complete",partial.path);
    if (n<0 || (size_t)n>=sizeof(marker)) return false;
    FILE *stamp=obor_fopen(marker,"wb");
    if (!stamp) return false;
    bool ok=fwrite(identity,1,64,stamp)==64 && obor_prepare_sync_file(stamp);
    if (fclose(stamp)) ok=false;
    /* Recreate the prepared tree from verified streams on every load. An old
     * marker, a modified file or an injected extra file is never authoritative. */
    if (!ok || !obor_storage_remove(prepared) || obor_rename(partial.path,prepared)) return false;
    partial.path[0]=0;
    n=snprintf(out,capacity,"%s/%s",prepared,models+root_length);
    log_cb(RETRO_LOG_INFO,"[OpenBOR] Prepared descriptor-selected loose files.\n");
    return n>=0 && (size_t)n<capacity;
}
#endif
