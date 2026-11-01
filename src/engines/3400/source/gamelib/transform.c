/* AnyBOR modification record: 2026-10-30.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Restore the original inverse-transform renderer with profile-specific
 * projection, triangle and water semantics; validate source and destination
 * spans.
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

///////////////////////////////////////////////////////////////////////////
//         This file defines some commmon methods used by the gamelib
////////////////////////////////////////////////////////////////////////////
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <float.h>
#include "globals.h"
#include "types.h"
#include "transform.h"
#include "obor_water.h"
extern uint32_t obor_profile_build;

static transpixelfunc pfp;
static unsigned int fillcolor;
static blend16fp pfp16;
static blend32fp pfp32;
static unsigned char* table;
static int transbg;
int trans_sw, trans_sh, trans_dw, trans_dh;
static void (*drawfp)(s_screen* dest, gfx_entry* src, int dx, int dy, int sx, int sy);


static size_t obor_transform_offset(int x, int y, int width)
{
    return (size_t)((int64_t)x + (int64_t)y * width);
}
static int obor_transform_inside(int x, int y, int width, int height)
{
    int64_t at = (int64_t)x + (int64_t)y * width;
    return width > 0 && height > 0 && at >= 0 &&
           (uint64_t)at < (uint64_t)(unsigned)width * (unsigned)height;
}

/*transpixelfunc, 8bit*/
static unsigned char remapcolor(unsigned char* table, unsigned char color, unsigned char unused)
{
	return table[color];
}

static unsigned char blendcolor(unsigned char* table, unsigned char color1, unsigned char color2)
{
	if(!table) return color1;
	return table[color1<<8|color2];
}

static unsigned char blendfillcolor(unsigned char* table, unsigned char unused, unsigned char color)
{
	if(!table) return fillcolor;
	return table[fillcolor<<8|color];
}


/**

 draw a pixel from source gfx surface to destination screen
 complex

*/

static void draw_pixel_dummy(s_screen* dest, gfx_entry* src, int dx, int dy, int sx, int sy)  
{
	int pb = pixelbytes[(int)dest->pixelformat];
	unsigned char* pd = ((unsigned char*)(dest->data)) + obor_transform_offset(dx,dy,dest->width)*pb; 
	memset(pd, 0, pb);
}

static void draw_pixel_screen(s_screen* dest, gfx_entry* src, int dx, int dy, int sx, int sy)
{
	unsigned char *ptrd8, *ptrs8, ps8;
	unsigned short *ptrd16, *ptrs16, pd16, ps16;
	unsigned int *ptrd32, *ptrs32, pd32, ps32;
	switch(dest->pixelformat)
	{
		case PIXEL_8:
			ps8 = *(((unsigned char*)src->screen->data) + obor_transform_offset(sx,sy,src->screen->width));
			if(transbg && !ps8) return;
			else if(fillcolor) ps8 = fillcolor;
			ptrd8 = ((unsigned char*)dest->data) + obor_transform_offset(dx,dy,dest->width);
			*ptrd8 =pfp?pfp(table, ps8, *ptrd8):ps8;
			break;
		case PIXEL_16:
			ptrd16 = ((unsigned short*)dest->data) + obor_transform_offset(dx,dy,dest->width);
			pd16 = *ptrd16;
			switch(src->screen->pixelformat)
			{
			case PIXEL_16:
				ptrs16 = ((unsigned short*)src->screen->data) + obor_transform_offset(sx,sy,src->screen->width);
				ps16 = *ptrs16;
				if(transbg && !ps16) return;
				break;
			case PIXEL_x8:
				ptrs8 = ((unsigned char*)src->screen->data) + obor_transform_offset(sx,sy,src->screen->width);
				if(transbg && !*ptrs8) return;
				ps16 = table?((unsigned short*)table)[*ptrs8]:((unsigned short*)src->screen->palette)[*ptrs8];
				break;
			default:
				return;
			}
			if(fillcolor) ps16 = fillcolor;
			if(!pfp16) *ptrd16 = ps16;
			else       *ptrd16 = pfp16(ps16, pd16);
			break;
		case PIXEL_32:
			ptrd32 = ((unsigned int*)dest->data) + obor_transform_offset(dx,dy,dest->width);
			pd32 = *ptrd32;
			switch(src->screen->pixelformat)
			{
			case PIXEL_32:
				ptrs32 = ((unsigned int*)src->screen->data) + obor_transform_offset(sx,sy,src->screen->width);
				ps32 = *ptrs32;
				if(transbg && !ps32) return;
				break;
			case PIXEL_x8:
				ptrs8 = ((unsigned char*)src->screen->data) + obor_transform_offset(sx,sy,src->screen->width);
				if(transbg && !*ptrs8) return;
				ps32 = table?((unsigned int*)table)[*ptrs8]:((unsigned int*)src->screen->palette)[*ptrs8];
				break;
			default:
				return;
			}
			if(fillcolor) ps32 = fillcolor;
			if(!pfp32) *ptrd32 = ps32;
			else       *ptrd32 = pfp32(ps32, pd32);
			break;

	}
}


static void draw_pixel_bitmap(s_screen* dest, gfx_entry* src, int dx, int dy, int sx, int sy)
{
    if(obor_profile_build < 3454) return;
#ifndef NDEBUG
    if(sizeof(s_screen)==sizeof(s_bitmap)) {
        obor_port_assert(0, "sizeof(s_screen)!=sizeof(s_bitmap)",
                         "draw_pixel_bitmap", "source/gamelib/transform.c", 125);
        return;
    }
#endif
    draw_pixel_screen(dest, src, dx, dy, sx, sy);
}

// get a pixel from specific sprite
// should be fairly slow due to the RLE compression
static char sprite_get_pixel(s_sprite* sprite, int x, int y){
	int *linetab;
	register int lx = 0, count;
	unsigned char * data;

	//should we check? 
	//if(y<0 || y>=sprite->height || x<0 || x>=sprite->width)
	//	return 0;


	linetab = ((int*)sprite->data) + y;

	data = ((unsigned char*)linetab) + (*linetab);

	while(1) {
		count = *data++;
		if(count == 0xFF) return 0;
		if(lx+count>x) return 0; // transparent pixel
		lx += count;
		count = *data++;
		if(!count) continue;
		if(lx + count > x)
		{
			return data[x-lx]; // not transparent pixel
		}
		lx+=count;
		data+=count;
	}

	return 0;

}

static void draw_pixel_sprite(s_screen* dest, gfx_entry* src, int dx, int dy, int sx, int sy)
{
	unsigned char *ptrd8, ps8;
	unsigned short *ptrd16, pd16, ps16;
	unsigned int *ptrd32, pd32, ps32;
	switch(dest->pixelformat)
	{
		case PIXEL_8:
			if(!(ps8 = sprite_get_pixel(src->sprite, sx, sy)))
				return;
			ptrd8 = ((unsigned char*)dest->data) + obor_transform_offset(dx,dy,dest->width);
			if(fillcolor) ps8 = fillcolor;
			*ptrd8 =pfp?pfp(table, ps8, *ptrd8):ps8;
			break;
		case PIXEL_16:
			if(!(ps8 = sprite_get_pixel(src->sprite, sx, sy)))
				return;
			ptrd16 = ((unsigned short*)dest->data) + obor_transform_offset(dx,dy,dest->width);
			pd16 = *ptrd16;
			if(fillcolor) ps16 = fillcolor;
			else ps16 = table?((unsigned short*)table)[ps8]:((unsigned short*)src->sprite->palette)[ps8];
			if(!pfp16) *ptrd16 = ps16;
			else       *ptrd16 = pfp16(ps16, pd16);
			break;
		case PIXEL_32:
			if(!(ps8 = sprite_get_pixel(src->sprite, sx, sy)))
				return;
			ptrd32 = ((unsigned int*)dest->data) + obor_transform_offset(dx,dy,dest->width);
			pd32 = *ptrd32;
			if(fillcolor) ps32 = fillcolor;
			else ps32 = table?((unsigned int*)table)[ps8]:((unsigned int*)src->sprite->palette)[ps8];
			if(!pfp32) *ptrd32 = ps32;
			else       *ptrd32 = pfp32(ps32, pd32);
			break;
	}

}

void draw_pixel_gfx(s_screen* dest, gfx_entry* src, int dx, int dy, int sx, int sy){
    if(!dest || !src || !obor_transform_inside(dx,dy,dest->width,dest->height))
        return;
    if(dest->pixelformat!=PIXEL_8 && dest->pixelformat!=PIXEL_16 &&
       dest->pixelformat!=PIXEL_32) return;
    if(src->type==gfx_sprite) {
        if(!src->sprite || sx<0 || sy<0 || sy>=src->sprite->height) return;
        if(dest->pixelformat!=PIXEL_8 && !fillcolor && !table &&
           !src->sprite->palette) return;
    } else if(src->type==gfx_screen || src->type==gfx_bitmap) {
        if(!src->screen ||
           !obor_transform_inside(sx,sy,src->screen->width,src->screen->height))
            return;
        if(src->screen->pixelformat==PIXEL_x8 && dest->pixelformat!=PIXEL_8 &&
           !table && !src->screen->palette) return;
    }

	switch(src->type){
	case gfx_sprite:
		draw_pixel_sprite(dest, src, dx, dy, sx, sy);
		break;
	case gfx_screen:
		draw_pixel_screen(dest, src, dx, dy, sx, sy);
		break;
	case gfx_bitmap:
		draw_pixel_bitmap(dest, src, dx, dy, sx, sy);
		break;
	default:
		draw_pixel_dummy(dest, src, dx, dy, sx, sy);//debug purpose
		break;
	}
}


void init_gfx_global_draw_stuff(s_screen* dest, gfx_entry* src, s_drawmethod* drawmethod){

	int spf = 0; //source pixel format
	drawfp = draw_pixel_dummy;
	pfp = NULL; fillcolor = 0; pfp16 = NULL;pfp32 = NULL; table = NULL; transbg = 0;
	trans_sw = trans_sh = trans_dw = trans_dh = 0;

	//nasty checkings due to those different pixel formats
	switch(src->type)
	{
	case gfx_screen:
		//printf("gfx_screen\n");
		drawfp = draw_pixel_screen;
		trans_sw = src->screen->width;
		trans_sh = src->screen->height;
		break;
	case gfx_bitmap:
		//printf("gfx_bitmap\n");
		spf = src->bitmap->pixelformat;
		drawfp = draw_pixel_bitmap;
		trans_sw = src->bitmap->width;
		trans_sh = src->bitmap->height;
		break;
	case gfx_sprite:
		//printf("gfx_sprite\n");
		spf = src->sprite->pixelformat;
		drawfp = draw_pixel_sprite;
		trans_sw = src->sprite->width;
		trans_sh = src->sprite->height;
		break;
	default:
		//printf("gfx_unknown\n");
		return;
	}

	trans_dw = dest->width;
	trans_dh = dest->height;
	switch(dest->pixelformat)
	{
	case PIXEL_8:
		if(drawmethod->fillcolor) fillcolor = drawmethod->fillcolor&0xFF;
		else fillcolor = 0;

		table = NULL;

		if(drawmethod->table)
		{
			table = drawmethod->table;
			pfp = remapcolor;
		}
		else if(drawmethod->alpha>0 && drawmethod->alpha<=MAX_BLENDINGS)
		{
			table = blendtables[drawmethod->alpha-1];
			pfp = (fillcolor==TRANSPARENT_IDX?blendcolor:blendfillcolor);
		}
		else pfp = (fillcolor==TRANSPARENT_IDX?NULL:blendfillcolor);
		break;
	case PIXEL_16:
		fillcolor = drawmethod->fillcolor;
		if(drawmethod->alpha>0 && drawmethod->alpha<=MAX_BLENDINGS) pfp16 = blendfunctions16[drawmethod->alpha-1];
		else pfp16 = NULL;
		table = drawmethod->table;
		break;
	case PIXEL_32:
		fillcolor = drawmethod->fillcolor;
		if(drawmethod->alpha>0 && drawmethod->alpha<=MAX_BLENDINGS) pfp32 = blendfunctions32[drawmethod->alpha-1];
		else pfp32 = NULL;
		table = drawmethod->table;
		break;
	default: 
		return;
	}

	transbg = drawmethod->transbg; // check color key, we'll need this for screen and bitmap
}


//sin cos tables
//sin cos tables
extern const double sin_table[];
extern const double cos_table[];

#define _max(a,b) (((a)>(b))?(a):(b))
#define _min(a,b) (((a)<(b))?(a):(b))


void gfx_draw_rotate(s_screen* dest, gfx_entry* src, int x, int y, int centerx, int centery, s_drawmethod* drawmethod)
{
    if(!dest || !src || !drawmethod || !drawmethod->scalex ||
       !drawmethod->scaley) return;

	double zoomx, zoomy, rzoomx, rzoomy, sina, cosa, ax, ay, bx, by, rx0, ry0, cx, cy, srcx0_f, srcx_f, srcy0_f, srcy_f, angle;
	int i, j, srcx, srcy;
	int xbound[4], ybound[4], xmin, xmax, ymin, ymax;
	double xboundf[4], yboundf[4];
	zoomx = drawmethod->scalex / 256.0;
	zoomy = drawmethod->scaley / 256.0;
	angle = drawmethod->rotate;
    if(angle<0 || angle>=360) return;
    sina = sin_table[(int)angle];
    cosa = cos_table[(int)angle];

	init_gfx_global_draw_stuff(dest, src, drawmethod);
    if(trans_sw<=0 || trans_sh<=0 || trans_dw<=0 || trans_dh<=0) return;
    if(obor_profile_build>=3454) {
        if(!obor_transform_add_center(&centerx,&centery,drawmethod)) return;
    }
	
	/////////////////begin clipping////////////////////////////
	xboundf[0] = drawmethod->flipx? ((double)centerx-trans_sw)*zoomx : -(double)centerx*zoomx;
	yboundf[0] = drawmethod->flipy? ((double)centery-trans_sh)*zoomy : -(double)centery*zoomy;
	xboundf[1] = xboundf[0] + trans_sw*zoomx;
	yboundf[1] = yboundf[0];
	xboundf[2] = xboundf[0];
	yboundf[2] = yboundf[0] + trans_sh*zoomy;
	xboundf[3] = xboundf[1];
	yboundf[3] = yboundf[2];

	for(i=0; i<4; i++){
        double px=x + xboundf[i]*cosa - yboundf[i]*sina;
        double py=y + xboundf[i]*sina + yboundf[i]*cosa;
        if(!(px>=INT_MIN && px<=INT_MAX && py>=INT_MIN && py<=INT_MAX))
            return;
        xbound[i]=(int)px;ybound[i]=(int)py;
	}

	xmin = _max(_min(_min(xbound[0],xbound[1]), _min(xbound[2],xbound[3])), 0);
	xmax = _min(_max(_max(xbound[0],xbound[1]), _max(xbound[2],xbound[3])), trans_dw);
	ymin = _max(_min(_min(ybound[0],ybound[1]), _min(ybound[2],ybound[3])), 0);
	ymax = _min(_max(_max(ybound[0],ybound[1]), _max(ybound[2],ybound[3])), trans_dh);
	/////////////////end clipping////////////////////////////

	// tricks to keep rotate not affected by flip
	if(drawmethod->flipx) {zoomx = -zoomx;}
	else  {angle = -angle;}
	if(drawmethod->flipy) {	zoomy = -zoomy; angle = -angle;}

	angle = (((int)angle)%360+360)%360;
	//if(!zoomx || !zoomy) return; //should be checked already
    rzoomx = 1.0 / zoomx;
    rzoomy = 1.0 / zoomy;
    sina = sin_table[(int)angle];
    cosa = cos_table[(int)angle];
    ax = rzoomx*cosa; 
    ay = rzoomx*sina; 
    bx = -rzoomy*sina; 
    by = rzoomy*cosa; 
    rx0 = centerx;
    ry0 = centery;
    if((int64_t)x-centerx<INT_MIN || (int64_t)x-centerx>INT_MAX ||
       (int64_t)y-centery<INT_MIN || (int64_t)y-centery>INT_MAX) return;
    x -= centerx;
    y -= centery;
    cx = -(rx0+x)*rzoomx*cosa+(ry0+y)*rzoomy*sina+rx0;
    cy = -(rx0+x)*rzoomx*sina-(ry0+y)*rzoomy*cosa+ry0; 
	srcx0_f= cx+ymin*bx+xmin*ax;
    srcy0_f= cy+ymin*by+xmin*ay;

    for (j=ymin; j<ymax; j++)
    {
        srcx_f = srcx0_f;
        srcy_f = srcy0_f;
        for (i=xmin;i<xmax;i++)
        {
            if(!(srcx_f>=INT_MIN && srcx_f<=INT_MAX &&
                 srcy_f>=INT_MIN && srcy_f<=INT_MAX)) {
                srcx_f+=ax;srcy_f+=ay;
                continue;
            }
            srcx=(int)(srcx_f);
            srcy=(int)(srcy_f);
			if(srcx>=0 && srcx<trans_sw && srcy>=0 && srcy<trans_sh)
				draw_pixel_gfx(dest, src, i, j, srcx, srcy);
            srcx_f+=ax;
            srcy_f+=ay;
        }
        srcx0_f+=bx;
        srcy0_f+=by;
    }
}

// scalex scaley flipy ...
void gfx_draw_scale(s_screen *dest, gfx_entry* src, int x, int y, int centerx, int centery, s_drawmethod* drawmethod)
{
    if(!dest || !src || !drawmethod || !drawmethod->scalex ||
       !drawmethod->scaley) return;

	double osx, sx, sy, dx, dy, w, h, cx, cy, stepdx, stepdy;
	int beginy, endy, beginx, endx;
	int i, j;
	double zoomx = drawmethod->scalex / 256.0;
	double zoomy = drawmethod->scaley / 256.0;
	double shiftf = drawmethod->shiftx / 256.0;
	
	//if(!zoomy || !zoomx) return; //should be checked already

	//printf("==%d %d %d %d %d\n", drawmethod->scalex, drawmethod->scaley, drawmethod->flipx, drawmethod->flipy, drawmethod->shiftx);

	init_gfx_global_draw_stuff(dest, src, drawmethod);
    if(trans_sw<=0 || trans_sh<=0 || trans_dw<=0 || trans_dh<=0) return;
    if(obor_profile_build>=3454) {
        if(!obor_transform_add_center(&centerx,&centery,drawmethod)) return;
    }

	w = trans_sw * zoomx;
	h = trans_sh * zoomy;
	cx = centerx * zoomx;
	cy = centery * zoomy;
	
	if(drawmethod->flipx) dx = cx - w + x;
	else dx = x - cx;

	if(drawmethod->flipy){
		dy = cy - h + y; 
		shiftf = - shiftf;
	}
	else dy = y - cy; 

	dx += (dy + h - y) * shiftf;

	if(drawmethod->flipx) {
		stepdx = 1.0/zoomx;
		osx = 0.0;
	}else{
		stepdx = -1.0/zoomx;
		osx = trans_sw - 1.0;
	}
	if(drawmethod->flipy){
		stepdy = 1.0/zoomy;
		sy = 0.0;
	}else{
		stepdy = -1.0/zoomy;
		sy = trans_sh - 1.0;
	}

	if(_max(dx+w, dx+w-shiftf*h)<=0) return;
	if(_min(dx, dx-shiftf*h)>=trans_dw) return;
	if(dy>=trans_dh) return;
	if(dy+h<=0) return;

	if(dy+h>trans_dh) {
		endy = trans_dh;
		dx -= shiftf*(dy+h-endy);
		sy += stepdy*(dy+h-endy);
	} else endy = dy+h;

	if(dy<0) beginy = 0;
	else beginy = dy;

	//printf("=%d, %d, %lf, %lf, %lf, %lf, %lf, %lf\n ",x, y, w, h, osx, sy, dx, dy);
	// =64, 144, 44.000000, 36.500000, 43.000000, 0.000000, 38.000000, 143.000000

	for(j=endy-1; j>=beginy; j--, sy+=stepdy, dx -= shiftf){
		if(dx>=trans_dw) continue;
		if(dx+w<=0) continue;
		sx = osx;
		if(dx<0) beginx = 0;
		else beginx = dx;
		if(dx+w>trans_dw) {
			endx = trans_dw;
			sx += stepdx*(dx+w-trans_dw);
		} else endx = dx+w;
		for(i=endx-1; i>=beginx; i--, sx+=stepdx){
			//printf("%d, %d, %d, %d\n", i, j, (int)sx, (int)sy);
            if(sx>=INT_MIN && sx<=INT_MAX && sy>=INT_MIN && sy<=INT_MAX)
			draw_pixel_gfx(dest, src, i, j, (int)sx, (int)sy);
		}
	}

}

#define _swap(va,vb) {vsw=va;va=vb;vb=vsw;}
void obor_transform_triangle(vert2d* vertices, s_screen *dest, gfx_entry *src, s_drawmethod* drawmethod, int triangleCount)
{
	vert2d *v1, *v2, *v3, *vsw = NULL;

	int i, triangleHalf;
	float tmpDiv; // temporary division factor
	float spanLongest; // saves the spanLongest span
	int height; // saves height of triangle
	int targetY; // target pointer where to plot pixels
	int spanEnd; // saves end of spans
	float leftdeltaxf; // amount of pixels to increase on left side of triangle
	float rightdeltaxf; // amount of pixels to increase on right side of triangle
	int leftx, rightx, temp; // position where we are 
	float leftxf, rightxf; // same as above, but as float values
	int span; // current span
	int	hSpanBegin, hSpanEnd; // pointer used when plotting pixels
	float leftTx, rightTx, leftTy, rightTy; // texture interpolating values
	float leftTxStep, rightTxStep, leftTyStep, rightTyStep; // texture interpolating values
	float spanTx, spanTy, spanTxStep, spanTyStep; // values of Texturecoords when drawing a span
	rect2d trect, vrect; //triangle rect
	unsigned char* shadow_buffer; // temporary fix to remove overlapping, relatively slow

	init_gfx_global_draw_stuff(dest, src, drawmethod);

	vrect.ulx = vrect.uly = 0;
	vrect.lrx = dest->width;
	vrect.lry = dest->height;

	shadow_buffer = malloc(dest->width*dest->height);

	if(!shadow_buffer) return;

	memset(shadow_buffer, 0, dest->width*dest->height);
/*
	if(triangleCount==8 && src->type == gfx_sprite){
		printf("%ld\n", src->sprite);
	}
	*/
	for (i=0; i<triangleCount; ++i)
	{
		v1 = &vertices[i];
		v2 = &vertices[i+1];
		v3 = &vertices[i+2];

		// sort in order of v1 <= v2 <= v3
		if (v1->x > v2->x)	_swap(v1, v2);
		if (v1->x > v3->x)	_swap(v1, v3);
		if (v2->x > v3->x)	_swap(v2, v3);

		if ((v1->x - v3->x) == 0)
			continue;

		trect.ulx = v1->x;
		trect.lrx = v3->x;

		// sort in order of v1 <= v2 <= v3
		if (v1->y > v2->y)	_swap(v1, v2);
		if (v1->y > v3->y)	_swap(v1, v3);
		if (v2->y > v3->y)	_swap(v2, v3);

		trect.uly = v1->y;
		trect.lry = v3->y;

		if (trect.ulx>vrect.lrx || trect.uly>vrect.lry || trect.lrx<vrect.ulx || trect.lry<vrect.uly)
			continue;

		// calculate height of triangle
		height = v3->y - v1->y;
		if (!height)
			continue;

		spanLongest = (v2->y - v1->y) / (float)height * (v3->x - v1->x) + (v1->x - v2->x);

		spanEnd = v2->y;
		span = v1->y;
		leftxf = (float)v1->x;
		rightxf = (float)v1->x;

		leftTx = rightTx = v1->tx;
		leftTy = rightTy = v1->ty;

		targetY = span;

		if (spanLongest < 0.0f)
		{
			tmpDiv = 1.0f / (float)(v2->y - v1->y);
			rightdeltaxf = (v2->x - v1->x) * tmpDiv;
			rightTxStep = (v2->tx - rightTx) * tmpDiv;
			rightTyStep = (v2->ty - rightTy) * tmpDiv;

			tmpDiv = 1.0f / (float)height;
			leftdeltaxf = (v3->x - v1->x) * tmpDiv;
			leftTxStep = (v3->tx - leftTx) * tmpDiv;
			leftTyStep = (v3->ty - leftTy) * tmpDiv;
		}
		else
		{
			tmpDiv = 1.0f / (float)height;
			rightdeltaxf = (v3->x - v1->x) * tmpDiv;
			rightTxStep = (v3->tx - rightTx) * tmpDiv;
			rightTyStep = (v3->ty - rightTy) * tmpDiv;

			tmpDiv = 1.0f / (float)(v2->y - v1->y);
			leftdeltaxf = (v2->x - v1->x) * tmpDiv;
			leftTxStep = (v2->tx - leftTx) * tmpDiv;
			leftTyStep = (v2->ty - leftTy) * tmpDiv;
		}


		//draw upper and lower half of the triangle
		for (triangleHalf=0; triangleHalf<2; ++triangleHalf)
		{
			if (spanEnd > vrect.lry)
				spanEnd = vrect.lry;

			// if the span <0, than we can skip these spans, 
			// and proceed to the next spans which are really on the screen.
			if (span < vrect.uly)
			{
				if (spanEnd < vrect.uly)
				{
					temp = spanEnd - span;
					span = spanEnd;
				}
				else
				{
					temp = vrect.uly - span; 
					span = vrect.uly;
				}

				leftxf += leftdeltaxf*temp;
				rightxf += rightdeltaxf*temp;
				targetY += temp;

				leftTx += leftTxStep*temp;
				leftTy += leftTyStep*temp;
				rightTx += rightTxStep*temp;
				rightTy += rightTyStep*temp;
			}


			// draw each line of the part
			while (span < spanEnd)
			{
				leftx = (int)(leftxf);
				rightx = (int)(rightxf + 0.5f);

				// TODO: perform clipping before going for the pixels
				if (rightx - leftx != 0)
				{
					tmpDiv = 1.0f / (rightxf - leftxf); // important: use float version of the right and left values to avoid sawtooth left edge

					hSpanBegin = leftx;
					hSpanEnd = rightx;

					spanTx = (float)leftTx;	
					spanTy = (float)leftTy;
					spanTxStep = (rightTx - leftTx) * tmpDiv;
					spanTyStep = (rightTy - leftTy) * tmpDiv;

					while (hSpanBegin < hSpanEnd)
					{
						if(hSpanBegin>=vrect.ulx && hSpanBegin<vrect.lrx)
						{
							temp = hSpanBegin + targetY*dest->width;
							//*hSpanBegin = srcp[(int)spanTy * src->width + (int)spanTx];
							if(!shadow_buffer[temp]) 
							{
								draw_pixel_gfx(dest, src, hSpanBegin, targetY, (int)spanTx, (int)spanTy);
								shadow_buffer[temp] = 1;
							}
						}

						spanTx += spanTxStep;
						spanTy += spanTyStep;
						
						++hSpanBegin;
					}
				}

				leftxf += leftdeltaxf;
				rightxf += rightdeltaxf;
				++span;
				++targetY;

				leftTx += leftTxStep;
				leftTy += leftTyStep;
				rightTx += rightTxStep;
				rightTy += rightTyStep;

				//printf("rightTyStep %d  leftTyStep %d\n", rightTyStep, leftTyStep);
			}

			if (triangleHalf>0) // break, we've gout only two halves
				break;


			// setup variables for second half of the triangle.

			if (spanLongest < 0.0f)
			{
				tmpDiv = 1.0f / (v3->y - v2->y);

				rightdeltaxf = (v3->x - v2->x) * tmpDiv;
				rightxf = (float)v2->x;

				rightTx = v2->tx;
				rightTy = v2->ty;
				rightTxStep = (v3->tx - rightTx) * tmpDiv;
				rightTyStep = (v3->ty - rightTy) * tmpDiv;
			}
			else
			{
				tmpDiv = 1.0f / (v3->y - v2->y);

				leftdeltaxf = (v3->x - v2->x) * tmpDiv;
				leftxf = (float)v2->x;

				leftTx = v2->tx;
				leftTy = v2->ty;
				leftTxStep = (v3->tx - leftTx) * tmpDiv;
				leftTyStep = (v3->ty - leftTy) * tmpDiv;
			}


			spanEnd = v3->y;
		}

	}
	free(shadow_buffer);
	shadow_buffer = NULL;
}
#undef _swap

/* These services preserve the historical sample coordinates. */
static int obor_transform_origin(int *x,int *y,int centerx,int centery,
                                 const s_drawmethod *method)
{
    int64_t px,py;
    if(!obor_transform_add_center(&centerx,&centery,method)) return 0;
    px=(int64_t)*x-centerx;py=(int64_t)*y-centery;
    if(px<INT_MIN || px>INT_MAX || py<INT_MIN || py>INT_MAX) return 0;
    *x=(int)px;*y=(int)py;return 1;
}

void gfx_draw_water(s_screen *dest,gfx_entry *src,int x,int y,int centerx,
                    int centery,s_drawmethod *method)
{
    s_screen extent={0};
    obor_water_rows rows;
    int row,sx,dx,count,i;
    if(obor_profile_build<3454 || !dest || !src || !method) return;
    init_gfx_global_draw_stuff(dest,src,method);
    if(!obor_transform_origin(&x,&y,centerx,centery,method)) return;
    extent.width=trans_sw;extent.height=trans_sh;
    if(!obor_water_begin(&rows,dest,&extent,x,y,method->water.amplitude,
                         method->water.wavelength,method->water.wavetime,
                         method->water.watermode)) return;
    for(row=0;row<rows.rows;++row) {
        if(!obor_water_span(&rows,row,&sx,&dx,&count)) continue;
        for(i=0;i<count;++i)
            draw_pixel_gfx(dest,src,dx+i,rows.dy+row,sx+i,rows.sy+row);
    }
}

static void obor_draw_plane_integer(s_screen *dest,gfx_entry *src,int x,int y,
                                    s_drawmethod *method)
{
    int width=trans_sw,height=trans_sh,xpos=x,dy,i,j,sy;
    int factor;
    int64_t center,origin,step,position,denominator,sample;
    float rawfactor=method->water.wavelength;
    if(!((double)rawfactor>=INT_MIN && (double)rawfactor<INT_MAX)) return;
    factor=(int)rawfactor;
    if(factor<0) return;
    ++factor;
    if(x>=trans_dw || y>=trans_dh) return;
    if(x<0) {width+=x;x=0;}
    if(y<0) {height+=y;y=0;}
    if((int64_t)x+width>trans_dw) width=trans_dw-x;
    if((int64_t)y+height>trans_dh) height=trans_dh-y;
    if(width<=0 || height<=0) return;
    dy=y;
    center=obor_profile_build<3458?width/2:trans_dw/2-x;
    origin=((int64_t)method->water.wavetime-
            (obor_profile_build<3458?0:xpos))*256+(int64_t)256*trans_sw;
    for(i=0;i<height;++i,++dy) {
        sy=i%trans_sh;
        denominator=(int64_t)trans_sw+(int64_t)trans_sw*i/factor;
        if(!denominator) return;
        step=(int64_t)trans_sw*256/denominator;
        position=origin-center*step;
        /* Wider intermediates define formerly unrepresentable input safely. */
        if(step<INT_MIN || step>INT_MAX || position<INT_MIN || position>INT_MAX) return;
        for(j=0;j<width;++j,position+=step) {
            sample=position>>8;
            if(sample>trans_sw || (obor_profile_build>=3459 && sample==trans_sw)) {
                sample%=trans_sw;
                position=(position&255)|(sample<<8);
            }
            if(sample>=INT_MIN && sample<=INT_MAX)
                draw_pixel_gfx(dest,src,x+j,dy,(int)sample,sy);
        }
    }
}

static void obor_draw_plane_float(s_screen *dest,gfx_entry *src,int x,int y,
                                  s_drawmethod *method)
{
    int i,j,dx,sx,sy,width,height,copyh=0,ypos=y;
    int64_t dy;
    float osxpos,sxpos,sypos,sxstep,systep=1.0f,xpos,factor,size,cx,beginsize,endsize;
    xpos=x;
    beginsize=method->water.beginsize;endsize=method->water.endsize;
    if(!(beginsize>=0 && endsize>=0) || beginsize>FLT_MAX || endsize>FLT_MAX) return;
    width=trans_sw;height=trans_sh;
    if(x>=trans_dw || y>=trans_dh) return;
    if(x<0) {width+=x;x=0;}
    if(y<0) {
        if(y==INT_MIN) return;
        copyh=-y;height+=y;y=0;
    }
    if((int64_t)x+width>trans_dw) width=trans_dw-x;
    if((int64_t)y+height>trans_dh) height=trans_dh-y;
    if(width<=0 || height<=0) return;
    copyh+=height;
    dy=obor_profile_build<3463?y:ypos;dx=x;
    cx=trans_dw/2.0-x;
    osxpos=method->water.wavetime-xpos+trans_sw;
    factor=(endsize-beginsize)/trans_sh;size=beginsize;
    sypos=0.0;
    for(i=0;i<(obor_profile_build<3463?height:
                obor_profile_build<3464?trans_sh:copyh);
        ++i,++dy,size+=factor,sypos+=systep) {
        if(!((double)sypos>=INT_MIN && (double)sypos<=INT_MAX) ||
           !(size>0) || size>FLT_MAX) return;
        sy=(int)sypos;sy%=trans_sh;if(sy<0)sy+=trans_sh;
        sxstep=1/size;
        switch(method->water.perspective) {
        case 1:systep=sxstep;break;
        case 2:systep=sxstep*trans_sh/(float)trans_sw;break;
        default:systep=1.0;
        }
        if(obor_profile_build>=3463 && dy<0) continue;
        if(dy<INT_MIN || dy>INT_MAX) return;
        sxpos=osxpos-cx*sxstep;
        for(j=0;j<width;++j,sxpos+=sxstep) {
            if(!((double)sxpos>=INT_MIN && (double)sxpos<=INT_MAX)) continue;
            sx=(int)sxpos;sx%=trans_sw;if(sx<0)sx+=trans_sw;
            draw_pixel_gfx(dest,src,dx+j,(int)dy,sx,sy);
        }
    }
}

void gfx_draw_plane(s_screen *dest,gfx_entry *src,int x,int y,int centerx,
                    int centery,s_drawmethod *method)
{
    if(obor_profile_build<3454 || !dest || !src || !method) return;
    init_gfx_global_draw_stuff(dest,src,method);
    if(trans_sw<=0 || trans_sh<=0 || trans_dw<=0 || trans_dh<=0 ||
       !obor_transform_origin(&x,&y,centerx,centery,method)) return;
    if(obor_profile_build<3462) obor_draw_plane_integer(dest,src,x,y,method);
    else obor_draw_plane_float(dest,src,x,y,method);
}
