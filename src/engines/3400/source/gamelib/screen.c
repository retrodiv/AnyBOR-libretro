/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Preserve native water phase, byte widths, clipping and transparent
 * traversal by profile; bound screen extents before drawing. Bound screen
 * blend selectors and use transparent copy when an indexed table is
 * unavailable.
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

/*
	Code for handling 'screen' structures.
	(Memory allocation and copy functions)
	Last update: 10 feb 2003
*/
#include <stdio.h>
#include <string.h>
#include "types.h"
#include "screen.h"

#include "obor_water.h"
extern float _sinfactors[256];
#define distortion(x, a) ((int)(_sinfactors[x]*a+0.5))

static char asBuf[13] = "";
static unsigned short asCnt = 0;

s_screen * allocscreen(int width, int height, int pixelformat)
{
	s_screen * screen;
	sprintf(asBuf, "as-id: %d", asCnt++);
	width &= (0xFFFFFFFF-3);
	if(pixelformat==PIXEL_x8)
	   screen = (s_screen*)malloc(sizeof(s_screen) + width*height*pixelbytes[(int)pixelformat]+PAL_BYTES+ANYNUMBER);
	else screen = (s_screen*)malloc(sizeof(s_screen) + width*height*pixelbytes[(int)pixelformat] + ANYNUMBER);
	if(screen==NULL) return NULL;
	screen->width = width;
	screen->height = height;
	screen->pixelformat = pixelformat;
	if(pixelformat==PIXEL_x8) screen->palette = ((unsigned char*)screen->data)+width*height*pixelbytes[(int)pixelformat];
	else screen->palette = NULL;
	return screen;
}

void freescreen(s_screen **screen)
{
	if((*screen) != NULL) free((*screen));
	(*screen) = NULL;
}

// Screen copy func. Supports clipping.
void copyscreen(s_screen * dest, s_screen * src)
{
	unsigned char *sp, *dp;
	int width = src->width;
	int height = src->height;
	int pixelformat = src->pixelformat;

	if(pixelformat!=dest->pixelformat) return;

	if(height > dest->height) height = dest->height;
	if(width > dest->width) width = dest->width;

	dp = dest->data; sp = src->data;
	// Copy unclipped
	if(dest->width == src->width){
		memcpy(dest->data, src->data, width * height * pixelbytes[(int)pixelformat]);
		return;
	}

	// Copy clipped
	do{
		memcpy(dp, sp, width * pixelbytes[(int)pixelformat]);
		sp += src->width*pixelbytes[(int)pixelformat];
		dp += dest->width*pixelbytes[(int)pixelformat];
	}while(--height);
}

void clearscreen(s_screen * s)
{
	if(s == NULL) return;
	memset(s->data, 0, s->width*s->height*pixelbytes[(int)s->pixelformat]);
}

// Screen copy function with offset options. Supports clipping.
void copyscreen_water(s_screen * dest, s_screen * src, int x, int y, int amplitude, float wavelength, int time, int watermode)
{
    obor_water_rows w;
    int row, sx, dx, count, bpp, format;
    if(!obor_water_begin(&w, dest, src, x, y, amplitude, wavelength, time, watermode)) return;
    format = src->pixelformat;
    if(dest->pixelformat != format ||
       format < 0 || format >= 5) return;
    bpp = pixelbytes[format];
    for(row = 0; row < w.rows; ++row) {
        if(!obor_water_span(&w, row, &sx, &dx, &count)) continue;
        if((size_t)count > (size_t)w.dw * w.dh - ((size_t)(w.dy + row) * w.dw + dx)) continue;
        memcpy(dest->data + ((size_t)(w.dy + row) * w.dw + dx) * bpp,
               src->data + ((size_t)(w.sy + row) * w.sw + sx) * bpp, (size_t)count * bpp);
    }
}

// Screen copy function with offset options. Supports clipping.
void copyscreen_o(s_screen * dest, s_screen * src, int x, int y)
{
	unsigned char *sp, *dp;
	int pixelformat = src->pixelformat;
	int sw = src->width;
	int sh = src->height;
	int dw = dest->width;
	int dh = dest->height;
	int cw = sw, ch = sh;
	int linew, slinew, dlinew;
	int sox, soy;

	if(dest->pixelformat != src->pixelformat) return;

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

	sp = src->data + (soy*sw + sox)*pixelbytes[(int)pixelformat];
	dp = dest->data + (y*dw + x)*pixelbytes[(int)pixelformat];
	linew = cw*pixelbytes[(int)pixelformat];
	slinew = sw*pixelbytes[(int)pixelformat];
	dlinew = dw*pixelbytes[(int)pixelformat];
	// Copy data
	do{
		memcpy(dp, sp, linew);
		sp += slinew;
		dp += dlinew;
	}while(--ch);
}

// Screen copy function with offset options. Supports clipping.
void copyscreen_trans_water(s_screen * dest, s_screen * src, int x, int y, int amplitude, float wavelength, int time, int watermode)
{
    obor_water_rows w;
    int row, sx, dx, count, j;
    if(!obor_water_begin(&w, dest, src, x, y, amplitude, wavelength, time, watermode)) return;
    if(obor_profile_build < 3390 && dest->pixelformat != src->pixelformat) return;
    for(row = 0; row < w.rows; ++row) {
        unsigned char *sp, *dp;
        if(!obor_water_span(&w, row, &sx, &dx, &count)) continue;
        if((size_t)count > (size_t)w.dw * w.dh - ((size_t)(w.dy + row) * w.dw + dx))
            count = (int)((size_t)w.dw * w.dh - ((size_t)(w.dy + row) * w.dw + dx));
        sp = src->data + (size_t)(w.sy + row) * w.sw + sx;
        dp = dest->data + (size_t)(w.dy + row) * w.dw + dx;
        for(j = 0; j < count; ++j) {
            int i = obor_profile_build < 3390 ? count - 1 - j : j;
            if(sp[i]) dp[i] = sp[i];
        }
    }
}

// same as above, with color key
void copyscreen_trans(s_screen * dest, s_screen * src, int x, int y)
{
	unsigned char *sp, *dp;
	int sw = src->width;
	int sh = src->height;
	int dw = dest->width;
	int dh = dest->height;
	int cw = sw, ch = sh;
	int sox, soy;
	int i;

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

	sp = src->data + (soy*sw + sox);
	dp = dest->data + (y*dw + x);
	// Copy data
	do{
		i=cw-1;
		do{
		   if(sp[i]==0)continue;
		   dp[i] = sp[i];
		}while(i--);
		sp += sw;
		dp += dw;
	}while(--ch);
}

//same as above, with remap, work only under 8bit pixel format
void copyscreen_remap(s_screen * dest, s_screen * src, int x, int y, unsigned char* remap)
{
	unsigned char *sp = src->data;
	unsigned char *dp = dest->data;
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

	// Copy data
	do{
		i=cw-1;
		do{
		   if(!sp[i])continue;
		   dp[i] = remap[sp[i]];
		}while(i--);
		sp += sw;
		dp += dw;
	}while(--ch);
}

// Screen copy function with offset options. Supports clipping.
void blendscreen_water(s_screen * dest, s_screen * src, int x, int y, int amplitude, float wavelength, int time, int watermode, unsigned char* lut)
{
    obor_water_rows w;
    int row, sx, dx, count, j;
    if(!obor_water_begin(&w, dest, src, x, y, amplitude, wavelength, time, watermode)) return;
    if(obor_profile_build < 3390 && dest->pixelformat != src->pixelformat) return;
    if(!lut) return;
    for(row = 0; row < w.rows; ++row) {
        unsigned char *sp, *dp;
        if(!obor_water_span(&w, row, &sx, &dx, &count)) continue;
        if((size_t)count > (size_t)w.dw * w.dh - ((size_t)(w.dy + row) * w.dw + dx))
            count = (int)((size_t)w.dw * w.dh - ((size_t)(w.dy + row) * w.dw + dx));
        sp = src->data + (size_t)(w.sy + row) * w.sw + sx;
        dp = dest->data + (size_t)(w.dy + row) * w.dw + dx;
        for(j = 0; j < count; ++j) {
            int i = obor_profile_build < 3390 ? count - 1 - j : j;
            if(sp[i]) dp[i] = lut[(sp[i] << 8) | dp[i]];
        }
    }
}

//same as above, with alpha blend
void blendscreen(s_screen * dest, s_screen * src, int x, int y, unsigned char* lut)
{
	unsigned char *sp = src->data;
	unsigned char *dp = dest->data;
	int i;
	int sw = src->width;
	int sh = src->height;
	int dw = dest->width;
	int dh = dest->height;
	int cw = sw, ch = sh;
	int sox, soy;
	unsigned char* d, *s;

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

	sp += soy*sw + sox;
	dp += y*dw + x;

	// Copy data
	do{
		i=cw;
		do{
		   d = dp+i-1;
		   s = sp+i-1;
		   if(!(*s)) continue;
		   *d = lut[(*s)<<8|(*d)];
		}while(--i);
		sp += sw;
		dp += dw;
	}while(--ch);
}


static unsigned char *obor_screen_blend_table(int alpha)
{
    if(alpha <= 0 || alpha > MAX_BLENDINGS) return NULL;
    return blendtables[alpha - 1];
}

void putscreen(s_screen* dest, s_screen* src, int x, int y, s_drawmethod* drawmethod)
{
	unsigned char* table;
	int alpha, transbg;
	if(!drawmethod || drawmethod->flag==0)
	{
		table = NULL;
		alpha = 0;
		transbg = 0;
	}
	else
	{
		table = drawmethod->table;
		alpha = drawmethod->alpha;
		transbg = drawmethod->transbg;
	}

	if(!table && alpha<=0 && !transbg)
	{
		if(dest->pixelformat==src->pixelformat && dest->width==src->width && dest->height==src->height)
		{
			copyscreen(dest, src);
			return;
		}
	}

	if(dest->pixelformat==PIXEL_8)
	{
		if(table)
		{
			copyscreen_remap(dest, src, x, y, drawmethod->table);
		}
		else if(alpha>0)
		{
			unsigned char *blend_table = obor_screen_blend_table(alpha);
            if(blend_table) blendscreen(dest, src, x, y, blend_table);
            else copyscreen_trans(dest, src, x, y);
		}
		else if(transbg) copyscreen_trans(dest, src, x, y);
		else copyscreen_o(dest, src, x, y);
	}
	else if(dest->pixelformat==PIXEL_16)
	{
		if(src->pixelformat==PIXEL_x8)
			putscreenx8p16(dest, src, x, y, transbg, (unsigned short*)table, alpha > 0 && alpha <= MAX_BLENDINGS ? blendfunctions16[alpha-1] : NULL);
		else if(src->pixelformat==PIXEL_16)
			blendscreen16(dest, src, x, y, transbg, alpha > 0 && alpha <= MAX_BLENDINGS ? blendfunctions16[alpha-1] : NULL);
	}
	else if(dest->pixelformat==PIXEL_32)
	{
		if(src->pixelformat==PIXEL_x8)
			putscreenx8p32(dest, src, x, y, transbg, (unsigned*)table, alpha > 0 && alpha <= MAX_BLENDINGS ? blendfunctions32[alpha-1] : NULL);
		else if(src->pixelformat==PIXEL_32)
			blendscreen32(dest, src, x, y, transbg, alpha > 0 && alpha <= MAX_BLENDINGS ? blendfunctions32[alpha-1] : NULL);
	}
}

void putscreen_water(s_screen* dest, s_screen* src, int x, int y, int amplitude, float wavelength, int time, int watermode, s_drawmethod* drawmethod)
{
	unsigned char* table;
	int alpha, transbg;
	if(!drawmethod || drawmethod->flag==0)
	{
		table = NULL;
		alpha = 0;
		transbg = 0;
	}
	else
	{
		table = drawmethod->table;
		alpha = drawmethod->alpha;
		transbg = drawmethod->transbg;
	}

	/*if(!table && alpha<=0 && !transbg)
	{
		if(dest->pixelformat==src->pixelformat && dest->width==src->width && dest->height==src->height)
		{
			copyscreen(dest, src);
			return;
		}
	}*/

	if(dest->pixelformat==PIXEL_8)
	{
		if(alpha>0)
		{
			unsigned char *blend_table = obor_screen_blend_table(alpha);
            if(blend_table) blendscreen_water(dest, src, x, y, amplitude, wavelength, time, watermode, blend_table);
            else copyscreen_trans_water(dest, src, x, y, amplitude, wavelength, time, watermode);
		}
		else if(transbg) copyscreen_trans_water(dest, src, x, y, amplitude, wavelength, time, watermode);
		else copyscreen_water(dest, src, x, y, amplitude, wavelength, time, watermode);
	}
	else if(dest->pixelformat==PIXEL_16)
	{
		putscreenx8p16_water(dest, src, x, y, transbg, (unsigned short*)table, alpha > 0 && alpha <= MAX_BLENDINGS ? blendfunctions16[alpha-1] : NULL, amplitude, wavelength, time, watermode);
	}
	else if(dest->pixelformat==PIXEL_32)
	{
		putscreenx8p32_water(dest, src, x, y, transbg, (u32*)table, alpha > 0 && alpha <= MAX_BLENDINGS ? blendfunctions32[alpha-1] : NULL, amplitude, wavelength, time, watermode);
	}
}

// Scale screen
void scalescreen(s_screen * dest, s_screen * src)
{
	int sw, sh;
	int dw, dh;
	int dx, dy;
	unsigned char *sp;
	unsigned char *dp;
	unsigned char *lineptr;
	unsigned int xstep, ystep, xpos, ypos;
	int pixelformat = src->pixelformat;

	if(dest->pixelformat!=pixelformat) return;

	if(src==NULL || dest==NULL) return;
	sp = src->data;
	dp = dest->data;

	sw = src->width*pixelbytes[(int)pixelformat];
	sh = src->height;
	dw = dest->width*pixelbytes[(int)pixelformat];
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

/*
 * Zooms in or out on the screen.
 * Parameters:
 *     centerx - x coord of zoom center on unclipped, unscaled screen
 *     centery - y coord of zoom center on unclipped, unscaled screen
 *     scalex - x scale factor
 *     scaley - y scale factor
 */
void zoomscreen(s_screen* dest, s_screen* src, int centerx, int centery, int scalex, int scaley)
{
	s_screen* frame;
	int screenwidth = src->width;
	int screenheight = src->height;
	int width = (screenwidth<<8)/scalex; // width of clipped, unscaled screen
	int height = (screenheight<<8)/scaley; // height of clipped, unscaled screen
	int xmin = (width>>1)-centerx; // x coord before clipping corresponding to x=0 after clipping
	int ymin = (height>>1)-centery; // y coord before clipping corresponding to y=0 after clipping
	int pixelformat = dest->pixelformat;

	if(src->pixelformat!=pixelformat) return;
	if(xmin>=screenwidth || xmin+((width*scalex)>>8)<0) return; // out of left or right border
	if(ymin>=screenheight) return;

	frame = allocscreen(width, height, pixelformat); // the part of the screen that will be zoomed
	copyscreen_o(frame, src, xmin, ymin);

	if(pixelbytes[pixelformat]==1)
	{
		scalescreen(dest, frame);
	}
	else if(pixelbytes[pixelformat]==2)
	{
		scalescreen16(dest, frame);
	}
	else if(pixelbytes[pixelformat]==4)
	{
		scalescreen32(dest, frame);
	}

	freescreen(&frame);
}
