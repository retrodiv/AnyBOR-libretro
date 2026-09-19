/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Remove declarations of unused standalone frontend APIs and define O_BINARY
 * where macOS lacks it.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/4432.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2014 OpenBOR Team
 */

#ifndef SPK_SUPPORTED

#ifndef PACKFILE_H
#define PACKFILE_H

#include <stdio.h>
#include <dirent.h>

#ifndef WIN
#include <unistd.h>
#define O_BINARY 0
#endif

#ifdef SDL
#include <SDL.h>
#endif

#ifdef PSP
#include "image.h"
#endif

//
// Structure used for handling packfiles
//
typedef struct pnamestruct
{
    unsigned int pns_len;	    // Length of the struct in bytes
    unsigned int filestart;	    // Start position of referenced file
    unsigned int filesize;	    // Size of referenced file
    char		 namebuf[80];	// Buffer to hold the file's name
} pnamestruct;

typedef struct fileliststruct
{
    char filename[128];
    int nTracks;
    char bgmFileName[80][256];
    int bgmTrack;
    unsigned int bgmTracks[256];
#ifdef SDL
    SDL_Surface *preview;
#elif PSP
    Image *preview;
#endif
} fileliststruct;

#define	NUMPACKHANDLES	8
#define PACKVERSION	0x00000000
#define testpackfile(filename, packfilename) closepackfile(openpackfile(filename, packfilename))

extern int printFileUsageStatistics;

// All of these return -1 on error
int openpackfile(const char *filename, const char *packfilename);
int readpackfile(int handle, void *buf, int len);
int closepackfile(int handle);
int seekpackfile(int handle, int offset, int whence);
int pak_init();
void pak_term();
void packfile_mode(int mode);
int pakopen(const char *filename, int mode);
int pakread(int fd, void *buf, int len);
void pakclose(int fd);
int paklseek(int fd, int n, int whence);
int openreadaheadpackfile(const char *filename, const char *packfilename, int readaheadsize, int prebuffersize);
void freefilenamecache(void);

#endif

#endif
