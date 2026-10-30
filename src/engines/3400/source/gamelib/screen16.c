/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Preserve native water palette fallback, row sampling, copy-case capacity
 * and blend ordering in indexed 16-bit output.
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

#include <stdio.h>
#include <string.h>
#include "types.h"

#include "obor_water.h"
extern float _sinfactors[256];
#define distortion(x, a) ((int)(_sinfactors[x]*a+0.5))

//with remap, work only under 8bit pixel format
void putscreenx8p16_water(s_screen * dest, s_screen * src, int x, int y, int key, unsigned short* remap, unsigned short(*blendfp)(unsigned short,unsigned short), int amplitude, float wavelength, int time, int watermode)
{
    obor_water_rows w;
    int row, sx, dx, count, j;
    if(!obor_water_begin(&w, dest, src, x, y, amplitude, wavelength, time, watermode)) return;
    if(obor_profile_build < 3390 && !remap) remap = (unsigned short*)src->palette;
    if(!remap) return;
    for(row = 0; row < w.rows; ++row) {
        unsigned char *sp;
        unsigned short *dp;
        if(!obor_water_span(&w, row, &sx, &dx, &count)) continue;
        sp = src->data + (size_t)(w.sy + row) * w.sw + sx;
        dp = ((unsigned short*)dest->data) + (size_t)(w.dy + row) * w.dw + dx;
        if(obor_profile_build < 3390 && !key && !blendfp) {
            if((size_t)count > (size_t)w.dw * w.dh - ((size_t)(w.dy + row) * w.dw + dx)) continue;
            u16pcpy(dp, sp, remap, (unsigned)count);
            continue;
        }
        if((size_t)count > (size_t)w.dw * w.dh - ((size_t)(w.dy + row) * w.dw + dx))
            count = (int)((size_t)w.dw * w.dh - ((size_t)(w.dy + row) * w.dw + dx));
        for(j = 0; j < count; ++j) {
            int i = obor_profile_build < 3390 ? count - 1 - j : j;
            if(!key || sp[i]) {
                if(obor_profile_build < 3390)
                    dp[i] = blendfp ? blendfp(remap[sp[i]], dp[i]) : remap[sp[i]];
                else
                    /* Color and blend destination use the original base rows. */
                    dp[i] = blendfp ? blendfp(remap[src->data[i]], ((unsigned short*)dest->data)[i]) : remap[src->data[i]];
            }
        }
    }
}

//with remap, work only under 8bit pixel format
void putscreenx8p16(s_screen * dest, s_screen * src, int x, int y, int key, unsigned short* remap, unsigned short(*blendfp)(unsigned short,unsigned short))
{
	unsigned char *sp = src->data;
	unsigned short *dp = (unsigned short*)dest->data;
	int i;
	int sw = src->width;
	int sh = src->height;
	int dw = dest->width;
	int dh = dest->height;
	int cw = sw, ch = sh;
	int sox, soy;

	// Copy anything at all?
	if(x >= dw) return;
	if(sw+x <= 0) return;
	if(y >= dh) return;
	if(sh+y <= 0) return;

	if(!remap) remap = (unsigned short*)src->palette;

	if(!remap) return;

	sox = 0;
	soy = 0;

	// Clip?
	if(x<0) {sox = -x; cw += x;}
	if(y<0) {soy = -y; ch += y;}

	if(x+sw > dw) cw -= (x+sw) - dw;
	if(y+sh > dh) ch -= (y+sh) - dh;

	if(x<0) x = 0;
	if(y<0) y = 0;

	sp += (soy*sw + sox);
	dp += (y*dw + x);

	if(blendfp)
	{
		if(key)
		{
		    // blend
			do{
				i=cw-1;
				do
				{
				   if(!sp[i])continue;
				   dp[i] = blendfp(remap[sp[i]], dp[i]);
				}while(i--);
				sp += sw;
				dp += dw;
			}while(--ch);
		}
		else
		{
		    // blend
			do{
				i=cw-1;
				do
				{
				   dp[i] = blendfp(remap[sp[i]], dp[i]);
				}while(i--);
				sp += sw;
				dp += dw;
			}while(--ch);
		}
	}
	else
	{
		if(key)
		{
			// Copy data
			do{
				i=cw-1;
				do
				{
				   if(!sp[i])continue;
				   dp[i] = remap[sp[i]];
				}while(i--);
				sp += sw;
				dp += dw;
			}while(--ch);
		}
		else
		{
			// Copy data
			do{
				u16pcpy(dp, sp, remap, cw);
				sp += sw;
				dp += dw;
			}while(--ch);
		}
	}
}


void blendscreen16(s_screen * dest, s_screen * src, int x, int y, int key, u16(*blendfp)(u16, u16))
{
	u16 *sp = (u16*)src->data;
	u16 *dp = (u16*)dest->data;
	int i;
	int sw = src->width;
	int sh = src->height;
	int dw = dest->width;
	int dh = dest->height;
	int cw = sw, ch = sh;
	int sox, soy;

	// Copy anything at all?
	if(x >= dw) return;
	if(sw+x <= 0) return;
	if(y >= dh) return;
	if(sh+y <= 0) return;

	sox = 0;
	soy = 0;

	// Clip?
	if(x<0) {sox = -x; cw += x;}
	if(y<0) {soy = -y; ch += y;}

	if(x+sw > dw) cw -= (x+sw) - dw;
	if(y+sh > dh) ch -= (y+sh) - dh;

	if(x<0) x = 0;
	if(y<0) y = 0;

	sp += (soy*sw + sox);
	dp += (y*dw + x);

	if(blendfp)
	{
		if(key)
		{
			// Copy data
			do{
				i=cw-1;
				do
				{
				   if(sp[i]==0) continue;
				   dp[i] = blendfp(sp[i], dp[i]);
				}while(i--);
				sp += sw;
				dp += dw;
			}while(--ch);
		}
		else
		{
			// Copy data
			do{
				i=cw-1;
				do
				{
				   dp[i] = blendfp(sp[i], dp[i]);
				}while(i--);
				sp += sw;
				dp += dw;
			}while(--ch);
		}
	}
	else
	{
		if(key)
		{
			// Copy data
			do{
				i=cw-1;
				do
				{
				   if(sp[i]==0) continue;
				   dp[i] = sp[i];
				}while(i--);
				sp += sw;
				dp += dw;
			}while(--ch);
		}
		else
		{
			// Copy data
			do{
				memcpy(dp, sp, cw<<1);
				sp += sw;
				dp += dw;
			}while(--ch);
		}
	}
}

// Scale screen
void scalescreen16(s_screen * dest, s_screen * src)
{
	int sw, sh;
	int dw, dh;
	int dx, dy;
	u16 *sp;
	u16 *dp;
	u16 *lineptr;
	unsigned int xstep, ystep, xpos, ypos;
	int pixelformat = src->pixelformat;

	//if(dest->pixelformat!=pixelformat || pixelformat!=PIXEL_16) return;
	if(dest->pixelformat!=pixelformat) return;

	if(src==NULL || dest==NULL) return;
	sp = (u16*)src->data;
	dp = (u16*)dest->data;

	sw = src->width;
	sh = src->height;
	dw = dest->width;
	dh = dest->height;

	xstep = (sw<<16) / dw;
	ystep = (sh<<16) / dh;

	ypos = 0;
	for(dy=0; dy<dh; dy++)
	{
		lineptr = sp + ((ypos>>16) * sw);
		ypos += ystep;
		xpos = 0;
		for(dx=0; dx<dw; dx++)
		{
			*dp = lineptr[xpos>>16];
			++dp;
			xpos += xstep;
		}
	}
}

