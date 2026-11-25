/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_GAME_CONTENT_H
#define OBOR_GAME_CONTENT_H
#include "anybor_file_io.h"
#include <ctype.h>
#include <sys/stat.h>
#include <dirent.h>
#include "anybor_pak_validate.h"
#include "anybor_zip_path.h"

static bool obor_game_disk_path(const char *root, const char *asset, char *out, size_t cap)
{
    if (snprintf(out, cap, "%s", root) >= (int)cap) return false;
    const char *part = asset;
    while (*part) {
        const char *slash = strchr(part, '/');
        size_t length = slash ? (size_t)(slash - part) : strlen(part);
        char name[512], candidate[4096];
        if (!length || length >= sizeof(name)) return false;
        memcpy(name, part, length); name[length] = 0;
        if (snprintf(candidate, sizeof(candidate), "%s/%s", out, name) >= (int)sizeof(candidate)) return false;
        struct stat st;
        if (obor_stat(candidate, &st)) {
            obor_path_directory *directory = obor_opendir(out);
            if (!directory) return false;
            unsigned seen = 0;
            bool found = false;
            obor_path_entry *entry;
            while ((entry = obor_readdir(directory))) {
                if (++seen > 8194U) { found = false; break; }
                if (!strcasecmp(name, entry->d_name)) {
                    if (snprintf(candidate, sizeof(candidate), "%s/%s", out, entry->d_name) >= (int)sizeof(candidate)) break;
                    found = true;
                    break;
                }
            }
            obor_closedir(directory);
            if (!found) return false;
        }
        if (snprintf(out, cap, "%s", candidate) >= (int)cap) return false;
        part += length;
        if (*part == '/') ++part;
    }
    return true;
}

/* Recognition is a bounded reference check, not a substitute for an engine
 * boot: models.txt must actually declare a nonempty model stored in the game. */
static FILE *obor_game_asset(const char *content, bool packed, const char *asset, uint32_t *size)
{
    char safe[512];
    if (!obor_zip_safe_name(asset, safe, sizeof(safe))) return NULL;
    if (!packed) {
        char path[4096];
        if (!obor_game_disk_path(content, safe, path, sizeof(path))) return NULL;
        struct stat st;
        if (obor_stat(path, &st) || !S_ISREG(st.st_mode) || st.st_size < 0 || (uint64_t)st.st_size > UINT32_MAX)
            return NULL;
        *size = (uint32_t)st.st_size;
        return obor_fopen(path, "rb");
    }
    FILE *file = obor_fopen(content, "rb");
    unsigned char data[12];
    if (!file) return NULL;
    if (fseek(file, -4, SEEK_END) || fread(data, 1, 4, file) != 4) { fclose(file); return NULL; }
    long end = ftell(file) - 4;
    uint32_t position = obor_pak_u32(data);
    while (position < (uint64_t)end && obor_prepare_checkpoint()) {
        unsigned char name[256];
        if (fseek(file, position, SEEK_SET) || fread(data, 1, 12, file) != 12) break;
        uint32_t length = obor_pak_u32(data), start = obor_pak_u32(data + 4);
        if (length < 14 || length > 268 || length > (uint64_t)end - position ||
            fread(name, 1, length - 12, file) != length - 12 || !memchr(name, 0, length - 12)) break;
        for (unsigned i = 0; name[i]; ++i) if (name[i] == '\\') name[i] = '/';
        if (!strcasecmp((char *)name, safe)) {
            *size = obor_pak_u32(data + 8);
            if (!fseek(file, start, SEEK_SET)) return file;
            break;
        }
        position += length;
    }
    fclose(file);
    return NULL;
}

static const char *obor_game_token(const char *line, char *out, size_t cap)
{
    size_t n = 0;
    while (*line && isspace((unsigned char)*line)) ++line;
    bool quoted = *line == '"';
    if (quoted) ++line;
    while (*line && (quoted ? *line != '"' : !isspace((unsigned char)*line) && *line != '#')) {
        if (n + 1 >= cap) { out[0] = 0; return line + strlen(line); }
        out[n++] = *line++;
    }
    out[n] = 0;
    return quoted && *line == '"' ? line + 1 : line;
}

static bool obor_game_recognizable(const char *content, bool packed)
{
    if (packed && obor_pak_validate(content)) return false;
    uint32_t bytes = 0;
    FILE *models = obor_game_asset(content, packed, "data/models.txt", &bytes);
    if (!models) return false;
    /* Bound observation work independently of the archive/extraction quota. */
    if (!bytes || bytes > (4U << 20)) { fclose(models); return false; }
    char line[4096];
    bool result = false, first = true;
    unsigned references = 0;
    while (bytes && obor_prepare_checkpoint()) {
        size_t used = 0;
        bool overflow = false;
        while (bytes) {
            int c = fgetc(models); --bytes;
            if (c == EOF || c == '\n') break;
            if (!c) { overflow = true; break; }
            if (used + 1 < sizeof(line)) line[used++] = (char)c; else overflow = true;
        }
        line[used] = 0;
        if (overflow) break;
        char command[64], name[256], path[512];
        const char *start = line;
        if (first && used >= 3 && !memcmp(line, "\xef\xbb\xbf", 3)) start += 3;
        first = false;
        const char *next = obor_game_token(start, command, sizeof(command));
        if (strcasecmp(command, "load") && strcasecmp(command, "know")) continue;
        next = obor_game_token(next, name, sizeof(name));
        obor_game_token(next, path, sizeof(path));
        if (!name[0] || !path[0]) continue;
        if (++references > 32U) break;
        uint32_t model_bytes = 0;
        FILE *model = obor_game_asset(content, packed, path, &model_bytes);
        if (model) { fclose(model); if (model_bytes) { result = true; break; } }
    }
    fclose(models);
    return result;
}

/* A complete RIFF/WAVE is an audio asset even if its extension is .pak. */
static bool obor_game_wave_asset(const char *path)
{
    FILE *file = obor_fopen(path, "rb");
    if (!file) return false;
    unsigned char header[12];
    bool result = false, format = false, audio = false;
    if (fseek(file, 0, SEEK_END)) { fclose(file); return false; }
    long bytes = ftell(file);
    if (bytes < 12 || fseek(file, 0, SEEK_SET) || fread(header, 1, 12, file) != 12 ||
        memcmp(header, "RIFF", 4) || memcmp(header + 8, "WAVE", 4) ||
        (uint64_t)obor_pak_u32(header + 4) + 8 != (uint64_t)bytes) { fclose(file); return false; }
    uint64_t position = 12;
    while (position + 8 <= (uint64_t)bytes) {
        if (fseek(file, (long)position, SEEK_SET) || fread(header, 1, 8, file) != 8) break;
        uint32_t chunk = obor_pak_u32(header + 4);
        uint64_t next = position + 8 + chunk + (chunk & 1);
        if (next > (uint64_t)bytes) break;
        if (!memcmp(header, "fmt ", 4) && chunk >= 16) format = true;
        if (!memcmp(header, "data", 4)) audio = true;
        position = next;
    }
    result = position == (uint64_t)bytes && format && audio;
    fclose(file);
    return result;
}

/* A complete CRC-checked PNG is a media resource regardless of its suffix. */
static uint32_t obor_game_big32(const unsigned char *p)
{ return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | p[3]; }
static bool obor_game_png_asset(const char *path)
{
    FILE *file=obor_fopen(path,"rb");
    if(!file) return false;
    unsigned char header[8], buffer[65536], expected[4];
    bool ok=fread(header,1,8,file)==8 && !memcmp(header,"\x89PNG\r\n\x1a\n",8);
    bool first=true, image=false, ended=false;
    unsigned chunks=0;
    while(ok && !ended && ++chunks<=8192U && obor_prepare_checkpoint()) {
        if(fread(header,1,8,file)!=8) {ok=false;break;}
        uint32_t left=obor_game_big32(header);
        bool ihdr=!memcmp(header+4,"IHDR",4), idat=!memcmp(header+4,"IDAT",4), iend=!memcmp(header+4,"IEND",4);
        if((first && (!ihdr || left!=13)) || (!first && ihdr) || (iend && (left || !image)) ||
           (!(header[4]&32) && !ihdr && !idat && !iend && memcmp(header+4,"PLTE",4))) {ok=false;break;}
        mz_ulong crc=mz_crc32(MZ_CRC32_INIT,header+4,4);
        while(left && ok) {
            size_t bytes=left<sizeof(buffer)?left:sizeof(buffer);
            if(fread(buffer,1,bytes,file)!=bytes || !obor_prepare_checkpoint()) {ok=false;break;}
            if(ihdr && (!obor_game_big32(buffer) || !obor_game_big32(buffer+4) || buffer[10] || buffer[11] || buffer[12]>1)) ok=false;
            crc=mz_crc32(crc,buffer,bytes);left-=(uint32_t)bytes;
        }
        if(!ok || fread(expected,1,4,file)!=4 || crc!=obor_game_big32(expected)) {ok=false;break;}
        first=false;image=image||idat;ended=iend;
    }
    ok=ok && ended && fgetc(file)==EOF && !ferror(file);
    fclose(file);return ok;
}

/* Accept a complete model-shaped text resource only within the sole verified
 * loose game's own root. Require resolved image references and closed inline
 * script blocks; arbitrary failed packed content remains inconclusive. */
static bool obor_game_model_asset(const char *path,const char *root)
{
    size_t prefix=strlen(root);
    if(strncmp(path,root,prefix) || (prefix && root[prefix-1]!='/' && path[prefix]!='/')) return false;
    FILE *file=obor_fopen(path,"rb");if(!file) return false;
    struct stat status;
    if(obor_stat(path,&status) || status.st_size<=0 || status.st_size>(4<<20)) {fclose(file);return false;}
    char line[4096];bool ok=true, name=false,type=false,health=false,animation=false,frame=false,script=false;
    long position=0;
    while(fgets(line,sizeof(line),file) && obor_prepare_checkpoint()) {
        size_t n=strlen(line);
        long next_position=ftell(file);
        if(next_position-position!=(long)n) {ok=false;break;}
        position=next_position;
        if((n==sizeof(line)-1 && line[n-1]!='\n') || n==0) {ok=false;break;}
        for(size_t i=0;i<n;++i) if((unsigned char)line[i]<32 && line[i]!='\t' && line[i]!='\r' && line[i]!='\n') ok=false;
        char command[64],argument[512];
        const char *next=obor_game_token(line,command,sizeof(command));obor_game_token(next,argument,sizeof(argument));
        if(!strcmp(command,"@script")) {if(script) ok=false;script=true;continue;}
        if(!strcmp(command,"@end_script")) {if(!script) ok=false;script=false;continue;}
        if(script || !command[0] || command[0]=='#') continue;
        if(!name && strcasecmp(command,"name")) {ok=false;break;}
        if(!strcasecmp(command,"name")) {if(name || !argument[0]) ok=false;name=true;}
        if(!strcasecmp(command,"type")) {
            static const char *types[]={"none","player","enemy","npc","obstacle","endlevel","item","pshot","shot","steamer","panel","text","trap"};
            for(unsigned i=0;i<sizeof(types)/sizeof(*types);++i) if(!strcasecmp(argument,types[i])) type=true;
        }
        if(!strcasecmp(command,"health")) {char *end=NULL;strtol(argument,&end,10);health=argument[0] && end && !*end;}
        if(!strcasecmp(command,"anim") && argument[0]) animation=true;
        if(animation && !strcasecmp(command,"frame")) {
            char resource[4096],asset[600];
            for(unsigned i=0;i<5;++i) {
                static const char *suffix[]={"",".png",".gif",".pcx",".bmp"};
                snprintf(asset,sizeof(asset),"%s%s",argument,suffix[i]);
                if(obor_game_disk_path(root,asset,resource,sizeof(resource))) {
                    struct stat image;
                    if(!obor_stat(resource,&image) && S_ISREG(image.st_mode) && image.st_size>0) frame=true;
                }
            }
        }
        if(!ok) break;
    }
    ok=ok && !script && !ferror(file) && feof(file) && name && type && health && animation && frame;
    fclose(file);return ok;
}
#endif
