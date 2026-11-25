/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_LOOSE_PREPARE_H
#define OBOR_LOOSE_PREPARE_H
#include "anybor_file_io.h"

/* Use the verified archive inventory as the authority for output names.
 * A marker can supply fingerprints only for that exact sequence of files. */
static bool obor_loose_manifest(const char *prepared, const char *root, size_t root_length,
    const obor_zip_content_entries &entries, unsigned count, FILE *marker,
    bool verify, unsigned &files)
{
    files = 0;
    for (unsigned i = 0; i < count; ++i) {
        const obor_zip_content_entry &entry = entries.data[i];
        if (entry.directory || strncasecmp(entry.name, root, root_length)) continue;
        const char *relative = entry.name + root_length;
        char path[2200], row[640];
        obor_prepared_sample sample;
        if (!*relative || !obor_prepare_checkpoint() ||
            !obor_archive_disk_path(prepared, relative, path, sizeof(path), false) ||
            !obor_prepared_sample_path(path, sample)) return false;
        obor_prepared_row(sample, relative, row);
        if (verify ? !obor_prepared_line_matches(marker, row) : fputs(row, marker) < 0)
            return false;
        ++files;
    }
    return files && (!verify || (fgetc(marker) == EOF && !ferror(marker)));
}

/* Counting regular entries here also rejects injected non-regular entries.
 * The expected names were separately checked without following redirected
 * directories. Limit depth and visits even for an unexpected empty subtree. */
static bool obor_loose_tree_count(const char *path, unsigned &files, size_t &visits, unsigned depth = 0)
{
    if (depth > 64) return false;
    obor_path_directory *dir = obor_opendir(path);
    if (!dir) return false;
    bool ok = true;
    while (ok) {
        errno = 0;
        obor_path_entry *entry = obor_readdir(dir);
        if (!entry) { ok = !errno; break; }
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..") ||
            (!depth && !strcmp(entry->d_name, obor_prepared_marker_name))) continue;
        char child[2200];
        if (!visits || !obor_prepare_checkpoint() ||
            !obor_storage_join(child, sizeof(child), path, entry->d_name)) { ok = false; break; }
        --visits;
        if (obor_storage_directory(child)) ok = obor_loose_tree_count(child, files, visits, depth + 1);
        else if (files && obor_prepared_regular(child)) --files;
        else ok = false;
    }
    return !obor_closedir(dir) && ok;
}

/* An explicit descriptor function can prepare a resolved loose game. Each
 * invocation receives one asset and its normalized relative name as metadata.
 * ZIP extraction remains immutable; publication owns a separate bounded tree. */
static bool obor_loose_prepare(const char *cache, const char *models,
    const obor_prepared_sample &archive,
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
    const char *root = models + prefix;
    char parent[1400], prepared[1600], recipe[65], identity[65];
    obor_transform_identity(transform, recipe);
    obor_prepared_key("loose", archive, root, relative_root, recipe, identity);
    auto locate = [&]() {
        return obor_prepared_slot(parent, "files", 16, identity, prepared, sizeof(prepared)) &&
            obor_storage_join(out, capacity, prepared, models + root_length);
    };
    if (!obor_storage_join(parent, sizeof(parent), save_dir, "AnyBOR-cache") || !locate()) return false;

    /* Reuse the prepared tree only when its marker records the exact output
     * inventory and every sampled fingerprint matches the files on disk. */
    auto matches = [&]() {
        if (!obor_storage_directory(parent)) return false;
        FILE *marker = obor_prepared_marker(prepared, identity);
        if (!marker) return false;
        unsigned remaining;
        bool ok = obor_loose_manifest(prepared, root, relative_root, entries, count, marker, true, remaining);
        if (fclose(marker)) ok = false;
        size_t visits = (size_t)count * sizeof(entries.data[0].name);
        return ok && obor_loose_tree_count(prepared, remaining, visits) && !remaining;
    };
    if (matches()) {
        if (!obor_storage_track(prepared)) return false;
        log_cb(RETRO_LOG_INFO, "[OpenBOR] Reusing prepared loose files.\n");
        return true;
    }

    uint64_t total = 0;
    for (unsigned i = 0; i < count; ++i) {
        const obor_zip_content_entry &entry = entries.data[i];
        if (strncasecmp(entry.name, root, relative_root)) continue;
        const char *relative = entry.name + relative_root;
        size_t first = strcspn(relative, "/");
        if (first == strlen(obor_prepared_marker_name) &&
            !strncasecmp(relative, obor_prepared_marker_name, first)) return false;
        if (entry.size > OBOR_ZIP_MAX_TOTAL - total) return false;
        total += entry.size;
    }
    if (!obor_storage_root(save_dir, parent, sizeof(parent)) ||
        !obor_zip_space_ok(parent, total + (64u << 20))) return false;
    obor_prepared_staging partial;
    if (!partial.create(parent, ".files-partial")) return false;
    bool changed=false;
    uint64_t output_total=0;
    unsigned files=0;
    obor_prepare_range progress=obor_prepare_phase;
    obor_prepare_stage(progress,0,900,total);
    for (unsigned i=0;i<count;++i) {
        const obor_zip_content_entry &entry=entries.data[i];
        if (strncasecmp(entry.name,root,relative_root)) continue;
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
        changed = changed || buffers.result.input_offset || buffers.result.size != entry.size;
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
            if (ok && !changed && !buffers.result.reader_view) {
                ok = obor_transform_file::read(&reader, offset, block, bytes) != 0;
                if (ok) changed = memcmp(data, block, bytes) != 0;
            }
            if (ok) ok=fwrite(data,1,bytes,output)==bytes;
            if (ok) {
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
        int n = snprintf(out, capacity, "%s", models);
        return n >= 0 && (size_t)n < capacity;
    }
    FILE *marker = obor_prepared_create_marker(partial.path, identity);
    if (!marker) return false;
    unsigned remaining;
    bool ok = obor_loose_manifest(partial.path, root, relative_root, entries, count, marker, false, remaining) &&
        obor_prepare_sync_file(marker);
    if (fclose(marker)) ok = false;
    size_t visits = (size_t)count * sizeof(entries.data[0].name);
    if (!ok || !obor_loose_tree_count(partial.path, remaining, visits) || remaining || !locate() ||
        !obor_prepared_publish(partial, prepared, identity, matches) || !obor_storage_track(prepared)) return false;
    log_cb(RETRO_LOG_INFO,"[OpenBOR] Prepared descriptor-selected loose files.\n");
    return true;
}
#endif
