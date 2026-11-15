/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Earlier incorporated material retains its original authorship notices. */
/* The 6330 modified reader used unsigned 32-bit cache coordinates and a
 * large-file ABI. Keep the ordinary reader's signed arithmetic and compile
 * the modified copy from the same patched source. OS descriptors remain
 * shared process resources so state restoration retains the live handles. */
#ifndef ANYBOR_LNS_PAK_H
#define ANYBOR_LNS_PAK_H
#include "anybor_abi.h"
extern uint32_t obor_profile_features;
#ifdef OBOR_LNS_PAK_IMPL
typedef unsigned int obor_pak_int;
#define obor_packfile_closeall obor_lns_obor_packfile_closeall
#define obor_packfile_fixup obor_lns_obor_packfile_fixup
#define tolowerOneChar obor_lns_tolowerOneChar
#define fnlc obor_lns_fnlc
#define myfilenamecmp obor_lns_myfilenamecmp
#define casesearch obor_lns_casesearch
#define getFreeHandle obor_lns_getFreeHandle
#define packfile_mode obor_lns_packfile_mode
#define isRawData obor_lns_isRawData
#define openpackfile obor_lns_openpackfile
#define openPackfile obor_lns_openPackfile
#define update_filecache_vfd obor_lns_update_filecache_vfd
#define makefilenamecache obor_lns_makefilenamecache
#define freefilenamecache obor_lns_freefilenamecache
#define openreadaheadpackfile obor_lns_openreadaheadpackfile
#define openPackfileCached obor_lns_openPackfileCached
#define readpackfile obor_lns_readpackfile
#define readPackfile obor_lns_readPackfile
#define pak_isvalidhandle obor_lns_pak_isvalidhandle
#define readpackfileblocking obor_lns_readpackfileblocking
#define readpackfile_noblock obor_lns_readpackfile_noblock
#define readPackfileCached obor_lns_readPackfileCached
#define closepackfile obor_lns_closepackfile
#define closePackfile obor_lns_closePackfile
#define closePackfileCached obor_lns_closePackfileCached
#define seekpackfile obor_lns_seekpackfile
#define seekPackfile obor_lns_seekPackfile
#define seekPackfileCached obor_lns_seekPackfileCached
#define find_iso_file obor_lns_find_iso_file
#define pak_term obor_lns_pak_term
#define pak_init obor_lns_pak_init
#define packfileeof obor_lns_packfileeof
#define packfile_supported obor_lns_packfile_supported
#define packfile_get_titlename obor_lns_packfile_get_titlename
#define packfile_music_read obor_lns_packfile_music_read
#define packfile_music_play obor_lns_packfile_music_play
#define filenamelist obor_lns_filenamelist
#define find_least_useful_cacheblock obor_lns_find_least_useful_cacheblock
#define which_pakblock_to_read obor_lns_which_pakblock_to_read
#define filecache_process obor_lns_filecache_process
#define filecache_readpakblock obor_lns_filecache_readpakblock
#define filecache_setvfd obor_lns_filecache_setvfd
#define filecache_term obor_lns_filecache_term
#define filecache_init obor_lns_filecache_init
#define filecache_wait_for_prebuffer obor_lns_filecache_wait_for_prebuffer
#else
typedef int obor_pak_int;
void obor_lns_obor_packfile_closeall(void);
void obor_lns_obor_packfile_fixup(const char *pakpath);
void obor_lns_packfile_mode(int mode);
int obor_lns_openpackfile(const char *filename, const char *packfilename);
int obor_lns_readpackfile(int handle, void *buf, int len);
int obor_lns_closepackfile(int handle);
int obor_lns_seekpackfile(int handle, int offset, int whence);
int obor_lns_openreadaheadpackfile(const char *filename, const char *packfilename, int readaheadsize, int prebuffersize);
void obor_lns_freefilenamecache(void);
int obor_lns_pak_init(void);
void obor_lns_pak_term(void);
void obor_lns_filecache_process(void);
int obor_lns_filecache_readpakblock(unsigned char *dest, unsigned int pakblock, int startofs, int bytes, int blocking);
void obor_lns_filecache_setvfd(unsigned int vfd, unsigned int start, unsigned int block, unsigned int readahead);
void obor_lns_filecache_term(void);
void obor_lns_filecache_init(int realfd, unsigned int pakcdsectors, unsigned int blocksize, unsigned char blocks, unsigned int vfds);
void obor_lns_filecache_wait_for_prebuffer(unsigned int vfd, unsigned int nblocks);
#endif
#endif
