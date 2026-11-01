/* AnyBOR modification record: 2026-10-30.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Declare the historical indexed and true-color screen rendering interfaces.
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

#ifndef SCREEN_H
#define SCREEN_H
#include "types.h"
#include "globals.h"
s_screen * allocscreen(int width, int height, int pixelformat);
void freescreen(s_screen **screen);
void copyscreen(s_screen * dest, s_screen * src);
void putscreen8_water(s_screen *dest, s_screen *src, int x, int y, int key,
                     unsigned char *remap, unsigned char *lut, int amplitude,
                     float wavelength, int time, int watermode);
void copyscreen_water(s_screen * dest, s_screen * src, int x, int y, int amplitude, float wavelength, int time, int watermode);
void copyscreen_o(s_screen * dest, s_screen * src, int x, int y);

void clearscreen(s_screen * s);
void scalescreen(s_screen * dest, s_screen * src);

void copyscreen_trans_water(s_screen * dest, s_screen * src, int x, int y, int amplitude, float wavelength, int time, int watermode);
void copyscreen_trans(s_screen * dest, s_screen * src, int x, int y);
void copyscreen_remap(s_screen * dest, s_screen * src, int x, int y, unsigned char* remap);
void blendscreen_water(s_screen * dest, s_screen * src, int x, int y, int amplitude, float wavelength, int time, int watermode, unsigned char* lut);
void blendscreen(s_screen * dest, s_screen * src, int x, int y, unsigned char* lut);
void putscreen(s_screen* dest, s_screen* src, int x, int y, s_drawmethod* drawmethod);
void putscreen_water(s_screen* dest, s_screen* src, int x, int y, int amplitude, float wavelength, int time, int watermode, s_drawmethod* drawmethod);
void zoomscreen(s_screen* dest, s_screen* src, int centerx, int centery, int scalex, int scaley);

//------------------------------16

void putscreenx8p16(s_screen * dest, s_screen * src, int x, int y, int key, u16* remap, u16(*blendfp)(u16,u16));
void putscreenx8p16_water(s_screen * dest, s_screen * src, int x, int y, int key, u16* remap, u16(*blendfp)(u16,u16), int amplitude, float wavelength, int time, int watermode);
void blendscreen16(s_screen * dest, s_screen * src, int x, int y, int key, u16(*blendfp)(u16, u16));
void scalescreen16(s_screen * dest, s_screen * src);


//------------------------------24

void putscreenx8p24(s_screen * dest, s_screen * src, int x, int y, int key, unsigned char* remap, u32(*blendfp)(u32,u32));
void blendscreen24(s_screen * dest, s_screen * src, int x, int y, int key, u32(*blendfp)(u32, u32));


//------------------------------32

void putscreenx8p32(s_screen * dest, s_screen * src, int x, int y, int key, u32* remap, u32(*blendfp)(u32,u32));
void putscreenx8p32_water(s_screen * dest, s_screen * src, int x, int y, int key, u32* remap, u32 (*blendfp)(u32,u32), int amplitude, float wavelength, int time, int watermode);
void blendscreen32(s_screen * dest, s_screen * src, int x, int y, int key, u32(*blendfp)(u32, u32));
void scalescreen32(s_screen * dest, s_screen * src);


#endif

