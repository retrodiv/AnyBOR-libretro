/* AnyBOR modification record: 2026-11-06.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Declare font storage and loading interfaces. Declare per-glyph font owners
 * and the selected font-mask interface.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/3842.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.LavaLit.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2011 OpenBOR Team
 */

#ifndef	FONT_H
#define	FONT_H


#define FONT_MBS 2
#define FONT_MONO 1

#define		MAX_FONTS		8
#define		FONT_LAYER		0x0FFFFFFF


typedef struct{
	s_sprite *	token;
    s_sprite **glyphs;
	int		token_width[256];
	int		width;
	int		height;
	int		mbs;
	int		mono;
}s_font;

void font_unload(int which);
int font_load(int which, char *filename, char *packfile, int flags);
int font_loadmask(int which, char *filename, char *packfile, int flags);
int font_string_width(int which, char* buf, ...);
void font_printf(int x, int y, int which, int layeroffset, char *format, ...);
void screen_printf(s_screen * screen, int x, int y, int which, char *format, ...);
int fontmonowidth(int which);
int fontheight(int which);
#endif
