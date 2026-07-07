/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Route circle drawing through the port's integer rasterizer.
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

// Primitive drawing functions. Should really be done in ASM...
// Last update: 24-jun-2002

#include "types.h"
#include "draw.h"

#ifndef		NULL
#define		NULL	 ((void*)0)
#endif


#define		abso(x)		(x<0?-x:x)


// Not a particularly fast line function, but it works, and clips!
void line(int sx, int sy, int ex, int ey, int colour, s_screen *screen, int alpha){

	int diffx, diffy;
	int absdiffx, absdiffy;
	int xdir, ydir;
	int thres;
	int d;
	unsigned char *lut;

	// Some off-screen lines may slip through this test!
	if(sx<0 && ex<0) return;
	if(sy<0 && ey<0) return;
	if(sx>=screen->width && ex>=screen->width) return;
	if(sy>=screen->height && ey>=screen->height) return;


	// Check clipping and calculate new coords if necessary

	diffx = ex - sx;
	diffy = ey - sy;

	if(sx<0){
		sy -= (sx*diffy/diffx);
		sx = 0;
	}
	if(sy<0){
		sx -= (sy*diffx/diffy);
		sy = 0;
	}
	if(sx>=screen->width){
		sy -= ((sx-screen->width)*diffy/diffx);
		sx = screen->width-1;
	}
	if(sy>=screen->height){
		sx -= ((sy-screen->height)*diffx/diffy);
		sy = screen->height-1;
	}

	if(ex<0){
		ey -= (ex*diffy/diffx);
		ex = 0;
	}
	if(ey<0){
		ex -= (ey*diffx/diffy);
		ey = 0;
	}
	if(ex>=screen->width){
		ey -= ((ex-screen->width)*diffy/diffx);
		ex = screen->width-1;
	}
	if(ey>=screen->height){
		ex -= ((ey-screen->height)*diffx/diffy);
		ey = screen->height-1;
	}


	// Second test: the lines that passed test 1 won't pass this time!
	if(sx<0 || ex<0) return;
	if(sy<0 || ey<0) return;
	if(sx>=screen->width || ex>=screen->width) return;
	if(sy>=screen->height || ey>=screen->height) return;


	// Recalculate directions
	diffx = ex - sx;
	diffy = ey - sy;

	absdiffx = abso(diffx);
	absdiffy = abso(diffy);

	sy *= screen->width;
	ey *= screen->width;

	lut = alpha>0?blendtables[alpha-1]:NULL;

	if(lut) lut += (colour<<8);

	if(absdiffx > absdiffy){
		// Draw a flat line
		thres = absdiffx >> 1;
		xdir = 1;
		if(diffx<0) xdir = -xdir;
		ydir = screen->width;
		if(diffy<0) ydir = -ydir;
		while(sx!=ex){
			d = sx+sy;
			screen->data[d] = (lut && screen->data[d])?(lut[screen->data[d]]):colour;
			sx += xdir;
			if((thres-=absdiffy) <= 0){
				sy += ydir;
				thres += absdiffx;
			}
		}
		d = ex+ey;
		screen->data[d] = (lut && screen->data[d])?(lut[screen->data[d]]):colour;
		return;
	}

	// Draw a high line
	thres = absdiffy >> 1;
	xdir = 1;
	if(diffx<0) xdir = -1;
	ydir = screen->width;
	if(diffy<0) ydir = -ydir;
	while(sy!=ey){
		d = sx+sy;
		screen->data[d] = (lut && screen->data[d])?(lut[screen->data[d]]):colour;;
		sy += ydir;
		if((thres-=absdiffx) <= 0){
			sx += xdir;
			thres += absdiffy;
		}
	}
	d = ex+ey;
	screen->data[d] = (lut && screen->data[d])?(lut[screen->data[d]]):colour;
}





void drawbox(int x, int y, int width, int height, int colour, s_screen *screen, int alpha)
{
	unsigned char *cp;
	unsigned char *lut;

	if(width<=0) return;
	if(height<=0) return;
	if(screen==NULL) return;

	if(x<0){
		if((width+=x)<=0) return;
		x = 0;
	}
	else if(x>=screen->width) return;
	if(y<0){
		if((height+=y)<=0) return;
		y = 0;
	}
	else if(y>=screen->height) return;
	if(x+width>screen->width) width = screen->width-x;
	if(y+height>screen->height) height = screen->height-y;

	cp = (unsigned char*)screen->data + y*screen->width + x;
	lut = alpha>0?blendtables[alpha-1]:NULL;
	if(lut) lut += (colour<<8);
	while(--height>=0){
		for(x=0;x<width;x++){
			*cp = (lut&&*cp)?(lut[((int)(*cp)) & 0xFF]):colour;
			++cp;
		}
		cp += screen->width - width;
	}
}



// Putpixel used by circle function
void _putpixel(int x, int y, int colour, s_screen *screen, int alpha){
	int pixind;
	unsigned char *lut;
	if((unsigned)x>screen->width || (unsigned)y>screen->height) return;
	pixind = x+y*screen->width;
	lut = alpha>0?blendtables[alpha-1]:NULL;
	if(lut) lut += (colour<<8);
	screen->data[pixind] = (lut&&screen->data[pixind])?(lut[(int)(screen->data[pixind]) & 0xFF]):colour;
}




/* Circle rasterization for the libretro port. */
#include "obor_circle.h"

typedef struct {
    int colour, alpha;
    s_screen *screen;
} obor_circle_context;

static void obor_circle_emit(int x, int y, void *opaque)
{
    obor_circle_context *ctx = (obor_circle_context *)opaque;
    _putpixel(x, y, ctx->colour, ctx->screen, ctx->alpha);
}

void circle(int x, int y, int rad, int col, s_screen *screen, int alpha)
{
    obor_circle_context ctx;
    if (!screen)
        return;
    ctx.colour = col;
    ctx.alpha = alpha;
    ctx.screen = screen;
    obor_circle_raster(x, y, rad, screen->width, screen->height,
                       obor_circle_emit, &ctx);
}



static int draw_init( s_drawmethod* drawmethod)
{
	int alpha = 0;
	drawmethod_global_init(drawmethod);

	if (drawmethod && drawmethod->flag)
		alpha = drawmethod->alpha;

	return alpha;
}

//======================== root methods ==================================

void putbox(int x, int y, int width, int height, int colour, s_screen *screen, s_drawmethod* drawmethod)
{
	int alpha = draw_init(drawmethod);

	switch(screen->pixelformat)
	{
	case PIXEL_8:
		drawbox(x, y, width, height, colour, screen, alpha);
		break;
	case PIXEL_16:
		drawbox16(x, y, width, height, colour, screen, alpha);
		break;
	case PIXEL_32:
		drawbox32(x, y, width, height, colour, screen, alpha);
		break;
	}
}

void putline(int sx, int sy, int ex, int ey, int colour, s_screen *screen, s_drawmethod* drawmethod)
{
	int alpha = draw_init(drawmethod);

	switch(screen->pixelformat)
	{
	case PIXEL_8:
		line(sx, sy, ex, ey, colour, screen, alpha);
		break;
	case PIXEL_16:
		line16(sx, sy, ex, ey, colour, screen, alpha);
		break;
	case PIXEL_32:
		line32(sx, sy, ex, ey, colour, screen, alpha);
		break;
	}
}

void putpixel(unsigned x, unsigned y, int colour, s_screen *screen, s_drawmethod* drawmethod)
{
	int alpha = draw_init(drawmethod);
	switch(screen->pixelformat)
	{
	case PIXEL_8:
		_putpixel(x, y, colour, screen, alpha);
		break;
	case PIXEL_16:
		_putpixel16(x, y, colour, screen, alpha);
		break;
	case PIXEL_32:
		_putpixel32(x, y, colour, screen, alpha);
		break;
	}
}


