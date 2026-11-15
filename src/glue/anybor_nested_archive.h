/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_NESTED_ARCHIVE_H
#define OBOR_NESTED_ARCHIVE_H

/* Nested archives share the outer extraction budget and atomic publication.
 * A warm cache is verified against the current streams, including descriptors;
 * cached routing text is never accepted merely because a marker exists. */
static bool obor_archive_disk_path(const char *root, const char *name, char *out,
                                  size_t capacity, bool create, bool directory = false)
{
    if (!obor_storage_directory(root) || !obor_storage_join(out, capacity, root, name)) return false;
    size_t start = strlen(root) + 1;
    for (size_t i = start; out[i]; ++i) {
        if (out[i] != '/') continue;
        out[i] = 0;
        if (create) mkdir_p(out);
        bool ok = obor_storage_directory(out);
        out[i] = '/';
        if (!ok) return false;
    }
    if (directory) {
        if (create) mkdir_p(out);
        return obor_storage_directory(out);
    }
#if defined(_WIN32)
    DWORD attributes = GetFileAttributesA(out);
    if (attributes == INVALID_FILE_ATTRIBUTES)
        return create && GetLastError() == ERROR_FILE_NOT_FOUND;
    return !(attributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT));
#else
    struct stat status;
    if (lstat(out, &status)) return create && errno == ENOENT;
    return S_ISREG(status.st_mode);
#endif
}

static bool obor_archive_check_file(const char *root, const obor_zip_content_entry &entry)
{
    char path[2200];
    if (!obor_archive_disk_path(root, entry.name, path, sizeof(path), false, entry.directory)) return false;
    if (entry.directory) return true;
    FILE *file = fopen(path, "rb");
    if (!file) return false;
    unsigned char buffer[65536];
    uint64_t size = 0;
    mz_ulong crc = MZ_CRC32_INIT;
    size_t got;
    bool ok = true;
    while ((got = fread(buffer, 1, sizeof(buffer), file))) {
        size += got;
        if (size > entry.size || !obor_prepare_checkpoint()) { ok = false; break; }
        crc = mz_crc32(crc, buffer, got);
    }
    ok = ok && !ferror(file) && size == entry.size && crc == entry.crc;
    fclose(file);
    return ok;
}

#if defined(OBOR_WITH_RAR5)
#include <archive.h>
#include <archive_entry.h>

#define OBOR_ARCHIVE_MAX_DEPTH 4U

static int obor_archive_seek(FILE *file,uint64_t offset) {
#if defined(_WIN32)
    return offset>INT64_MAX ? -1 : _fseeki64(file,(__int64)offset,SEEK_SET);
#else
    return offset>INT64_MAX ? -1 : fseeko(file,(off_t)offset,SEEK_SET);
#endif
}
static int64_t obor_archive_length(FILE *file) {
#if defined(_WIN32)
    if(_fseeki64(file,0,SEEK_END)) return -1;
    return _ftelli64(file);
#else
    if(fseeko(file,0,SEEK_END)) return -1;
    return ftello(file);
#endif
}

static uint16_t obor_archive_u16(const unsigned char *p) { return p[0] | (uint16_t)p[1] << 8; }

/* Accept a bare RAR5 stream or a PE with a RAR5 stream exactly after all raw
 * sections. No signature search, executable launch or engine-scan limit change. */
static bool obor_archive_rar_offset(FILE *file, uint64_t *offset, uint64_t *length)
{
    unsigned char header[64];
    static const unsigned char signature[8] = {'R','a','r','!',0x1a,7,1,0};
    int64_t end = obor_archive_length(file);
    if (end < 8 || obor_archive_seek(file,0) || fread(header,1,8,file)!=8) return false;
    uint64_t start = 0;
    if (memcmp(header,signature,8)) {
        if (end < 64 || obor_archive_seek(file,0) || fread(header,1,64,file)!=64 || memcmp(header,"MZ",2)) return false;
        uint64_t pe = obor_pak_u32(header+60);
        if (pe < 64 || pe > (uint64_t)end-24 || obor_archive_seek(file,pe) || fread(header,1,24,file)!=24 || memcmp(header,"PE\0\0",4)) return false;
        unsigned sections = obor_archive_u16(header+6), optional = obor_archive_u16(header+20);
        uint64_t table = pe+24+optional;
        if (!sections || sections>96 || optional<64 || table>(uint64_t)end || sections*40ULL>(uint64_t)end-table) return false;
        if (obor_archive_seek(file,pe+24) || fread(header,1,64,file)!=64 ||
            (obor_archive_u16(header)!=0x10b && obor_archive_u16(header)!=0x20b)) return false;
        start = obor_pak_u32(header+60); /* SizeOfHeaders */
        if (start < table+sections*40ULL || start>(uint64_t)end) return false;
        for (unsigned i=0;i<sections;++i) {
            if (obor_archive_seek(file,table+i*40ULL) || fread(header,1,40,file)!=40) return false;
            uint64_t bytes=obor_pak_u32(header+16), raw=obor_pak_u32(header+20);
            if (bytes && (raw < table+sections*40ULL || raw>(uint64_t)end || bytes>(uint64_t)end-raw)) return false;
            if (bytes && raw+bytes>start) start=raw+bytes;
        }
        if (start>(uint64_t)end-8 || obor_archive_seek(file,start) || fread(header,1,8,file)!=8 || memcmp(header,signature,8)) return false;
    }
    *offset=start;*length=(uint64_t)end-start;
    return !obor_archive_seek(file,start);
}

/* Bound and validate RAR5 block framing independently of decoder EOF. Missing
 * end markers, split volumes, encrypted headers and trailing junk are refused. */
static bool obor_archive_vint(const unsigned char *data,size_t bytes,size_t &at,uint64_t &value) {
    value=0;
    for(unsigned i=0;i<10 && at<bytes;++i) {
        unsigned char c=data[at++];
        if(i==9 && (c&0xfe)) return false;
        value|=(uint64_t)(c&127)<<(i*7);
        if(!(c&128)) return true;
    }
    return false;
}
static bool obor_archive_framing(FILE *file,uint64_t offset,uint64_t bytes,unsigned &services,uint64_t &metadata) {
    services=0;metadata=0;
    uint64_t at=8;
    unsigned blocks=0;
    while(at<bytes && ++blocks<=OBOR_ZIP_MAX_ENTRIES+2 && obor_prepare_checkpoint()) {
        unsigned char head[14];
        if(bytes-at<7 || obor_archive_seek(file,offset+at)) return false;
        size_t have=(size_t)(bytes-at<sizeof(head)?bytes-at:sizeof(head));
        if(fread(head,1,have,file)!=have) return false;
        size_t pos=4;uint64_t size=0;
        if(!obor_archive_vint(head,have,pos,size) || size>(2U<<20) || size<2 || size>bytes-at-pos) return false;
        size_t header_bytes=pos+(size_t)size;
        unsigned char *header=(unsigned char *)malloc(header_bytes);
        if(!header) return false;
        bool ok=!obor_archive_seek(file,offset+at) && fread(header,1,header_bytes,file)==header_bytes &&
            mz_crc32(MZ_CRC32_INIT,header+4,header_bytes-4)==obor_pak_u32(header);
        uint64_t type=0,flags=0,extra=0,data=0;
        ok=ok && obor_archive_vint(header,header_bytes,pos,type) && obor_archive_vint(header,header_bytes,pos,flags);
        if(ok && (flags&1)) ok=obor_archive_vint(header,header_bytes,pos,extra);
        if(ok && (flags&2)) ok=obor_archive_vint(header,header_bytes,pos,data);
        if(ok && type==1) {uint64_t main_flags=0;ok=obor_archive_vint(header,header_bytes,pos,main_flags) && !(main_flags&1);}
        if(ok && type==3) {
            uint64_t file_flags=0,unpacked=0;
            ok=obor_archive_vint(header,header_bytes,pos,file_flags) && !(file_flags&8) &&
                obor_archive_vint(header,header_bytes,pos,unpacked) && unpacked<=(16U<<20) &&
                metadata<=(16U<<20)-unpacked;
            if(ok) {metadata+=unpacked;++services;}
        }
        if(ok && type==5) {uint64_t end_flags=0;ok=obor_archive_vint(header,header_bytes,pos,end_flags) && !end_flags && !data;}
        ok=ok && !(flags&0x18) && (type==1 || type==2 || type==3 || type==5) && extra<=header_bytes-pos &&
            data<=bytes-at-header_bytes;
        free(header);
        if(!ok) return false;
        at+=header_bytes+data;
        if(type==5) return at==bytes;
    }
    return false;
}

struct obor_archive_input {
    FILE *file;
    uint64_t left;
    unsigned char buffer[65536];
};
static la_ssize_t obor_archive_read(struct archive *archive, void *context, const void **buffer)
{
    obor_archive_input *input=(obor_archive_input *)context;
    *buffer=input->buffer;
    if (!obor_prepare_checkpoint()) { archive_set_error(archive,ECANCELED,"Content preparation cancelled"); return -1; }
    size_t need=(size_t)(input->left<sizeof(input->buffer)?input->left:sizeof(input->buffer));
    size_t got=fread(input->buffer,1,need,input->file);
    if (got!=need) { archive_set_error(archive,EIO,"Incomplete archive stream");return -1; }
    input->left-=got;
    return (la_ssize_t)got;
}
struct obor_archive_scope {
    struct archive *value;
    obor_archive_scope() : value(archive_read_new()) {}
    ~obor_archive_scope() { if(value) archive_read_free(value); }
};

/* Check portable collisions before writing, including file/parent conflicts. */
static obor_zip_content_entry *obor_archive_add(obor_zip_content_entries &entries,
    unsigned &count, const char *prefix, const char *name, bool directory,
    uint64_t size, unsigned depth)
{
    char safe[512], full[512], lower[512];
    if (!obor_zip_safe_name(name,safe,sizeof(safe))) return NULL;
    size_t n=strlen(safe);
    if (n && safe[n-1]=='/') safe[--n]=0;
    size_t prefix_size=strlen(prefix);
    if (!n || prefix_size+1+n>=sizeof(full) || count+entries.overhead>=OBOR_ZIP_MAX_ENTRIES) return NULL;
    memcpy(full,prefix,prefix_size);full[prefix_size]='/';
    memcpy(full+prefix_size+1,safe,n+1);
    int length=(int)(prefix_size+1+n);
    obor_zip_lower(full,lower,sizeof(lower));
    for (unsigned i=0;i<count;++i) {
        const obor_zip_content_entry &old=entries.data[i];
        size_t old_size=strlen(old.lower);
        if (!strcmp(old.lower,lower)) return NULL;
        if ((!old.directory && old_size<(size_t)length && !strncmp(old.lower,lower,old_size) && lower[old_size]=='/') ||
            (!directory && (size_t)length<old_size && !strncmp(old.lower,lower,(size_t)length) && old.lower[length]=='/')) return NULL;
    }
    obor_zip_content_entry *entry=entries.data+count++;
    snprintf(entry->name,sizeof(entry->name),"%s",full);
    snprintf(entry->lower,sizeof(entry->lower),"%s",lower);
    entry->directory=directory;entry->size=size;entry->depth=depth;
    return entry;
}

static bool obor_archive_rar(const char *root, const char *path, const char *prefix,
    obor_zip_content_entries &entries, unsigned &count, uint64_t &total, unsigned depth, bool cold)
{
    FILE *file=fopen(path,"rb");
    if (!file) return false;
    uint64_t offset=0,length=0;
    unsigned services=0;uint64_t metadata=0;
    bool ok=obor_archive_rar_offset(file,&offset,&length) && obor_archive_framing(file,offset,length,services,metadata) &&
        services<=OBOR_ZIP_MAX_ENTRIES-count-entries.overhead && metadata<=(16U<<20)-entries.metadata &&
        total<=OBOR_ZIP_MAX_TOTAL-metadata && !obor_archive_seek(file,offset);
    if(ok) {entries.overhead+=services;entries.metadata+=metadata;total+=metadata;}
    if (!ok) { log_cb(RETRO_LOG_ERROR,"[OpenBOR] archive: invalid framing or metadata quota\n");fclose(file);return false; }
    obor_archive_input input={};input.file=file;input.left=length;
    obor_archive_scope reader;
    struct archive *archive=reader.value;
    ok=archive && archive_read_support_filter_none(archive)==ARCHIVE_OK &&
       archive_read_support_format_rar5(archive)==ARCHIVE_OK &&
       archive_read_open(archive,&input,NULL,obor_archive_read,NULL)==ARCHIVE_OK;
    struct archive_entry *item=NULL;
    int status=ARCHIVE_FATAL;
    uint64_t expanded=0;
    while (ok && (status=archive_read_next_header(archive,&item))==ARCHIVE_OK) {
        bool directory=archive_entry_filetype(item)==AE_IFDIR;
        la_int64_t bytes=archive_entry_size(item);
        if ((archive_entry_filetype(item)!=AE_IFREG && !directory) ||
            archive_entry_symlink(item) || archive_entry_hardlink(item) || archive_entry_is_encrypted(item) ||
            !archive_entry_size_is_set(item) || bytes<0 || (uint64_t)bytes>OBOR_ZIP_MAX_FILE ||
            (directory && bytes) || total>OBOR_ZIP_MAX_TOTAL-(uint64_t)bytes ||
            !obor_prepare_checkpoint()) { ok=false;break; }
        total+=(uint64_t)bytes;expanded+=(uint64_t)bytes;
        if (expanded>length*OBOR_ZIP_MAX_RATIO || !obor_zip_space_ok(root,(uint64_t)bytes+(64ULL<<20))) { ok=false;break; }
        obor_zip_content_entry *entry=obor_archive_add(entries,count,prefix,archive_entry_pathname(item),directory,(uint64_t)bytes,depth);
        char destination[2200];
        if (!entry || !obor_archive_disk_path(root,entry->name,destination,sizeof(destination),cold,directory)) { ok=false;break; }
        if (directory) continue;
        FILE *output=fopen(destination,cold?"wb":"rb");
        if (!output) { ok=false;break; }
        uint64_t got_total=0;
        mz_ulong crc=MZ_CRC32_INIT;
        unsigned char buffer[65536],existing[65536];
        la_ssize_t got=0;
        while ((got=archive_read_data(archive,buffer,sizeof(buffer)))>0) {
            got_total+=(uint64_t)got;
            if (got_total>(uint64_t)bytes || !obor_prepare_checkpoint()) {ok=false;break;}
            crc=mz_crc32(crc,buffer,(size_t)got);
            if (cold ? fwrite(buffer,1,(size_t)got,output)!=(size_t)got :
                (fread(existing,1,(size_t)got,output)!=(size_t)got || memcmp(existing,buffer,(size_t)got))) {ok=false;break;}
            obor_prepare_advance((uint64_t)got);
        }
        if (got<0 || got_total!=(uint64_t)bytes || (!cold && fgetc(output)!=EOF)) ok=false;
        if (fclose(output)) ok=false;
        entry->crc=(uint32_t)crc;
    }
    if (status!=ARCHIVE_EOF) ok=false;
    if (archive && archive_read_close(archive)!=ARCHIVE_OK) ok=false;
    fclose(file);
    if (!ok) log_cb(RETRO_LOG_ERROR,"[OpenBOR] archive: incomplete, unsupported or unsafe RAR5 stream\n");
    return ok;
}

static bool obor_archive_zip(const char *root, const char *path, const char *prefix,
    obor_zip_content_entries &entries, unsigned &count, uint64_t &total, unsigned depth, bool cold)
{
    obor_zip_reader_scope reader;
    mz_zip_archive *archive=&reader.archive;
    reader.opened=mz_zip_reader_init_file(archive,path,0);
    if (!reader.opened) return false;
    unsigned files=mz_zip_reader_get_num_files(archive);
    if (!files || files>OBOR_ZIP_MAX_ENTRIES-count-entries.overhead) return false;
    for (unsigned i=0;i<files;++i) {
        mz_zip_archive_file_stat st;
        if (!mz_zip_reader_file_stat(archive,i,&st) || ((st.m_external_attr>>16)&0170000)==0120000 ||
            st.m_uncomp_size>OBOR_ZIP_MAX_FILE || total>OBOR_ZIP_MAX_TOTAL-st.m_uncomp_size ||
            (st.m_uncomp_size>(1U<<20) && (!st.m_comp_size || st.m_uncomp_size/st.m_comp_size>OBOR_ZIP_MAX_RATIO))) return false;
        total+=st.m_uncomp_size;
        obor_zip_content_entry *entry=obor_archive_add(entries,count,prefix,st.m_filename,st.m_is_directory,st.m_uncomp_size,depth);
        char destination[2200];
        if (!entry || !obor_archive_disk_path(root,entry->name,destination,sizeof(destination),cold,entry->directory)) return false;
        entry->crc=st.m_crc32;
        if (entry->directory) continue;
        if (cold) {
            if (!obor_zip_space_ok(root,st.m_uncomp_size+(64ULL<<20))) return false;
            FILE *output=fopen(destination,"wb");
            bool ok=output && mz_zip_reader_extract_to_callback(archive,i,obor_zip_write,output,0);
            if (output && fclose(output)) ok=false;
            if (!ok) return false;
        } else if (!obor_archive_check_file(root,*entry)) return false;
    }
    return true;
}

static bool obor_archive_expand(const char *root, obor_zip_content_entries &entries,
                               unsigned &count, uint64_t &total, bool cold)
{
    for (unsigned i=0;i<count;++i) {
        obor_zip_content_entry &entry=entries.data[i];
        if (entry.directory) continue;
        char path[2200];
        if (!obor_archive_disk_path(root,entry.name,path,sizeof(path),false)) return false;
        FILE *file=fopen(path,"rb");
        if (!file) return false;
        unsigned char magic[8]={};
        size_t got=fread(magic,1,sizeof(magic),file);
        uint64_t offset=0,length=0;
        bool rar=obor_archive_rar_offset(file,&offset,&length);
        fclose(file);
        bool zip=got>=4 && (!memcmp(magic,"PK\3\4",4) || !memcmp(magic,"PK\5\6",4));
        if (!rar && !zip) continue;
        if (entry.depth>=OBOR_ARCHIVE_MAX_DEPTH) return false;
        entry.container=true;
        char prefix[512],destination[2200];
        if (snprintf(prefix,sizeof(prefix),"%s.unpacked",entry.name)>=(int)sizeof(prefix)) return false;
        /* The synthetic extraction directory is reserved in the same namespace. */
        char lower[512];obor_zip_lower(prefix,lower,sizeof(lower));
        size_t size=strlen(lower);
        for (unsigned j=0;j<count;++j)
            if (!strncmp(entries.data[j].lower,lower,size) &&
                (!entries.data[j].lower[size] || entries.data[j].lower[size]=='/')) return false;
        if (!obor_archive_disk_path(root,prefix,destination,sizeof(destination),cold,true)) return false;
        bool ok=rar ? obor_archive_rar(root,path,prefix,entries,count,total,entry.depth+1,cold) :
                      obor_archive_zip(root,path,prefix,entries,count,total,entry.depth+1,cold);
        if (!ok) return false;
    }
    return true;
}
#else
static bool obor_archive_expand(const char *,obor_zip_content_entries &,unsigned &,uint64_t &,bool) { return true; }
#endif
#endif
