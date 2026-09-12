/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Include the libretro platform interface.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/4086.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2013 OpenBOR Team
 */

/////////////////////////////////////////////////////////////////////////////

#ifndef GLOBALS_H
#define GLOBALS_H

/////////////////////////////////////////////////////////////////////////////

#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <errno.h>
#include <inttypes.h>
#include <ctype.h>

#include "utils.h"

#ifdef PSP
#include <stdarg.h>
#include <psppower.h>
#include "pspport.h"
#include "graphics.h"
#endif

#ifdef SDL
#include "sdlport.h"
#endif

#ifdef LIBRETRO
#include "libretroport.h"
#endif

#ifdef GP2X
#include "gp2xport.h"
#endif

#ifdef DOS
#include "dosport.h"
#endif

#ifdef DC
#include "dcport.h"
#endif

#ifdef XBOX
#include "xboxport.h"
#endif

#ifdef WII
#include <gctypes.h>
#include <ogc/conf.h>
#include "wiiport.h"
#endif

#include "packfile.h"

/////////////////////////////////////////////////////////////////////////////

#ifndef PP_TEST
#define printf writeToLogFile

#undef assert
#define assert(x)    exitIfFalse((x)?1:0, #x, __func__, __FILE__, __LINE__)
#define sysassert(x) abortIfFalse((x)?1:0, #x, __func__, __FILE__, __LINE__)
#endif

/////////////////////////////////////////////////////////////////////////////

extern int int_assert[sizeof(int) == 4 ? 1 : -1];

#define MIN_INT (int)0x80000000
#define MAX_INT	(int)0x7fffffff

#ifndef MAX
#define MAX(a,b) ((a) > (b) ? (a) : (b))
#define MIN(a,b) ((a) < (b) ? (a) : (b))
#endif

#define __realloc(p, n) \
p = realloc((p), sizeof(*(p))*((n)+1));\
memset((p)+(n), 0, sizeof(*(p)));

#define __reallocto(p, n, s) \
p = realloc((p), sizeof(*(p))*(s));\
memset((p)+(n), 0, sizeof(*(p))*((s)-(n)));

#endif
