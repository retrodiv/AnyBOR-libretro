/* AnyBOR modification record: 2026-10-19.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Declare the true-color background loading entry point.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/4086.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2014 OpenBOR Team
 */

#ifndef	LOADIMAGE_H
#define LOADIMAGE_H

// Blah.

int loadscreen(char *filename, char *packfile, unsigned char *pal, int format, s_screen **screen);
int loadscreen32(char *filename, char *packfile, s_screen **screen);
s_bitmap *loadbitmap(char *filename, char *packfile, int format);
int loadimagepalette(char *filename, char *packfile, unsigned char *pal);
#endif


