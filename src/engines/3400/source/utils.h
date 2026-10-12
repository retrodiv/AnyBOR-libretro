/* AnyBOR modification record: 2026-10-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Declare the capacity of content-derived filename destinations. Derive
 * output names from the content basename with explicit destination
 * capacities, and reject overflowing output path joins.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/3400.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.LavaLit.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2011 OpenBOR Team
 */

#ifndef UTILS_H
#define UTILS_H

// *** INCLUDES ***
#include "types.h"
#include "stringptr.h"

// *** TYPE DECLARATIONS ***
#define SCRIPT_LOG 0
#define OPENBOR_LOG 1

// *** VARIABLE DECLARATIONS ***
extern char debug_msg[2048];
extern unsigned long debug_time;

// *** FUNCTIONS DECLARATIONS ***
void writeToLogFile(const char *, ...);
void writeToScriptLog(const char *msg);

#ifndef DC
int fileExists(char *fnam);
int dirExists(char *dname, int create);
stringptr* readFromLogFile(int which);
#endif

#if XBOX || DC
typedef struct{
	char filename[80];
}s_filelist;
s_filelist paklist[20];

int findmods(void);
#endif

void lc(char* buf, size_t size);
size_t getNewLineStart(char* buf);
void debugBuf(unsigned char* buf, size_t size, int columns);
void debug_printf(char *, ...);
void getPakName(char *name, size_t capacity, int type);
void screenshot(s_screen *vscreen, unsigned char *pal, int ingame);
void getBasePath(char *newName, char *name, int type);
unsigned readlsb32(const unsigned char *src);
int searchList(const char* list[], const char* value, int length);
char *commaprint(u64 n);

void Array_Check_Size( const char* f_caller, char** array, int new_size, int* curr_size_allocated, int grow_step );

#endif

