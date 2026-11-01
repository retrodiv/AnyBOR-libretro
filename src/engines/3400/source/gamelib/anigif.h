/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Restore the header's pragma pack state so including it leaves the caller's
 * alignment untouched.
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

#ifndef		ANIGIF_H
#define		ANIGIF_H


#pragma pack(push, 1)

// Animated GIF player.

// ============================== This is it! ===============================
// Should be something like this...


#define			ANIGIF_DECODE_END		0
#define			ANIGIF_DECODE_FRAME		1
#define			ANIGIF_DECODE_RETRY		3
#define			ANIGIF_DECODE_PAL		4

#define			NO_CODE				-1



typedef struct{
	char		magic[6];
	unsigned short	screenwidth, screenheight;
	unsigned char	flags;
	unsigned char	background;
	unsigned char	aspect;
}gifheaderstruct;


typedef struct {
	short	left, top;
	unsigned short width, height;
	unsigned char	flags;
}gifblockstruct;


#define sizeof_gifheaderstruct 13
#define sizeof_iblock 9

#pragma pack(pop)

typedef struct 
{
	gifheaderstruct gif_header;
	int handle; // = -1;
	int transparent; // = -1;
	int bitdepth;
	int numcolours;
	int noblackenbg; // don't blacken the first color
	int lastdelay;
	unsigned char*	global_pal;
	unsigned char*	local_pal;
} anigif_info;



// Returns true on succes
int anigif_open_ex(char *filename, char *packfilename, unsigned char *pal, anigif_info* info);

// Returns type of action (frame, retry or end)
int anigif_decode_ex(s_screen * screen, int *delay, int x, int y, unsigned char* pal, anigif_info* info);

void anigif_close_ex(anigif_info* info);

/* The single-stream entry points retain the original caller interface. */
int anigif_open(char *filename, char *packfilename, unsigned char *pal);
int anigif_decode(s_screen *screen, int *delay, int x, int y);
void anigif_close(void);

#endif
