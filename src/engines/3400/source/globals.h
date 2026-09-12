/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Include the libretro platform interface.
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

/////////////////////////////////////////////////////////////////////////////

#define printf writeToLogFile

/////////////////////////////////////////////////////////////////////////////

extern int int_assert[sizeof(int)==4?1:-1];

#endif
