/* AnyBOR modification record: 2026-11-15.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Declare profile-specific cached reader coordinates without changing the
 * ordinary signed interface.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/6391.md
 * at the source repository root. Original notices follow below.
 */

/////////////////////////////////////////////////////////////////////////////
//
// filecache - code for background file reading/caching
//
/////////////////////////////////////////////////////////////////////////////

#ifndef FILECACHE_H
#define FILECACHE_H
#include "anybor_lns_pak.h"

/////////////////////////////////////////////////////////////////////////////
//
// BLOCKS MUST BE 255 OR LESS
//
// hint: if you set realfd to a negative number, that means it'll use the
// gdrom routines to read a pak file starting at that (positive) lba
//
void filecache_init(
    int realfd,
    obor_pak_int pakcdsectors,
    obor_pak_int blocksize,
    unsigned char blocks,
    obor_pak_int vfds
);

//
// Clear All Allocations
//
void filecache_term(void);

//
// attempt to read a block
// returns the number of bytes read or 0 on error
//
int filecache_readpakblock(
    unsigned char *dest,
    obor_pak_int pakblock,
    int startofs,
    int bytes,
    int blocking
);

//
// set up where the vfd pointers are
//
void filecache_setvfd(obor_pak_int vfd, obor_pak_int start, obor_pak_int block, obor_pak_int readahead);

//
// call this every now and then
//
void filecache_process(void);

void filecache_wait_for_prebuffer(obor_pak_int vfd, obor_pak_int nblocks);

/////////////////////////////////////////////////////////////////////////////

#endif

