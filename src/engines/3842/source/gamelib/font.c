/* AnyBOR modification record: 2026-10-20.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Reject missing or undersized indexed font palettes before copying their
 * true-color entries; retain atlas raster output for valid fonts.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/3842.md
 * at the source repository root. Original notices follow below.
 */

#include <stdint.h>
#include <stddef.h>
#include "obor_resources.h"

/*
 * OpenBOR - http://www.LavaLit.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2011 OpenBOR Team
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include "openbor.h"


s_font** fonts[MAX_FONTS];

static char b[1024];

void _font_unload(s_font* font){
	free(font->token);
	font->token = NULL;
	free(font);
}

void font_unload(int which){
	int j, max;
	s_font** sets, *font;

	which %= MAX_FONTS;
	if(which < 0) return;

	sets = fonts[which];

	if(!sets) return;

	max = (sets[0]&&sets[0]->mbs)?256:1;

	for(j=0; j<max; j++){
		font = sets[j];
		if(!font) continue;
		_font_unload(font);
		sets[j] = NULL;
	}

	free(sets);
	fonts[which] = NULL;
}



static int obor_font_palette_valid(const s_screen *screen)
{
    size_t bytes, offset;
    uintptr_t owner, palette;
    if(!screen) return 0;
    if(screen->pixelformat != PIXEL_x8) return 1;
    if(!screen->palette) return 0;
    bytes = obor_allocation_size(screen);
    owner = (uintptr_t)screen;
    palette = (uintptr_t)screen->palette;
    if(palette < owner || palette - owner < offsetof(s_screen, data)) return 0;
    offset = palette - owner;
    return offset <= bytes && (size_t)PAL_BYTES <= bytes - offset;
}

int _font_load(s_font* font, char *filename, char *packfile){
	int x, y;
	int index = 0;
	int size;
	int cx = 0, cy = 0;
	s_bitmap *bitmap = NULL;
	s_screen *screen = NULL;
	int rval = 0;
	int tw, th;

	if(!loadscreen(filename, packfile, NULL, pixelformat, &screen)) goto err;
	if(!obor_font_palette_valid(screen)) goto err;
	font->width = tw = screen->width/16;
	font->height = th = screen->height/16;
	if(!(bitmap = allocbitmap(tw,th,pixelformat))) goto err;

	// grab tokens
	for(y=0; y<16; y++){
		for(x=0; x<16; x++){
			getbitmap(x*tw, y*th, tw,th, bitmap, screen);
			clipbitmap(bitmap, &cx, NULL, &cy, NULL);
			font->token_width[index] = font->mono?tw:(bitmap->width+(tw/10));
			if(font->token_width[index] <= 1) font->token_width[index] = tw/3;
			++index;
		}
	}

	freebitmap(bitmap);
	if(!(bitmap = allocbitmap(screen->width,screen->height,pixelformat))) goto err;
	getbitmap(0, 0, screen->width,screen->height, bitmap, screen);
	clipbitmap(bitmap, &cx, NULL, &cy, NULL);
	if(bitmap->palette && screen->palette)
		memcpy(bitmap->palette, screen->palette, PAL_BYTES);
	size = fakey_encodesprite(bitmap);
	if(!(font->token=malloc(size))) goto err;
	encodesprite(-cx, -cy, bitmap, font->token);

	rval = 1;

err:
	freebitmap(bitmap);
	freescreen(&screen);

	return rval;
}


int font_load(int which, char *filename, char *packfile, int flags){
	s_font** sets, *font;
	int i, max;

	which %= MAX_FONTS;
	if(which < 0) return 0;

	font_unload(which);

	max = (flags&FONT_MBS)?256:1;
	// UT: 129 should be enough for mbs, use 256 to keep the logic simpler

	fonts[which] = sets = malloc(sizeof(s_font*)*max);
	memset(sets, 0, sizeof(s_font*)*max);

	for(i=0; i<max; i++){
		if(i==1) i=128;
		font = malloc(sizeof(s_font));
		memset(font,0,sizeof(s_font));
		font->mono = ((flags&FONT_MONO)!=0);
		font->mbs = ((flags&FONT_MBS)!=0);
		if(font->mbs){
			sprintf(b, "%s/%02x", filename, i);
		}else 
			strcpy(b, filename);
		
		if(!_font_load(font, b, packfile)){
			_font_unload(font);
			font = NULL;
		}
		sets[i] = font;
	}

	if(sets[0]==NULL){
		font_unload(which);
		return 0;
	}

	return 1;

}

int fontmonowidth(int which){

	s_font** sets;
	which %= MAX_FONTS;
	if(which < 0) return 0;

	sets = fonts[which];

	if(!sets || !sets[0]) return 0;

	return sets[0]->width;
}

int fontheight(int which){
	s_font** sets;
	which %= MAX_FONTS;
	if(which < 0) return 0;

	sets = fonts[which];

	if(!sets || !sets[0]) return 0;

	return sets[0]->height;
}


int font_string_width(int which, char* format, ...)
{
	int w=0;
	char * buf = b, c;
	va_list arglist;
	s_font** sets, *font;
	int mbs, index;

	which %= MAX_FONTS;
	if(which < 0) return 0;

	sets = fonts[which];

	if(!sets || !format) return 0;

	mbs = sets[0]->mbs;

	va_start(arglist, format);
	vsprintf(buf, format, arglist);
	va_end(arglist);

	if(!mbs){
		font = sets[0];

		if(font)
		while(*buf)
		{
			w += font->token_width[((int)(*buf)) & 0xFF];
			buf++;
		}
	}else{
		while((c=*buf))
		{
			if((c&0x80)&&buf[1]){
				index = (unsigned char)c;
				buf++;
			}
			else index = 0;

			font = sets[index];

			if(font) w += font->token_width[((int)(*buf)) & 0xFF];
			buf++;
		}
	}
	return w;
}

void font_printf(int x, int y, int which, int layeroffset,char *format, ...){
	char * buf = b, c;
	va_list arglist;
	int ox = x;
	s_drawmethod dm = plainmethod;
	s_font** sets, *font;
	int mbs, index, w, lf, id;

	which %= MAX_FONTS;
	if(which < 0) return;

	sets = fonts[which];

	if(!sets) return;

	mbs = sets[0]->mbs;

	va_start(arglist, format);
	vsprintf(buf, format, arglist);
	va_end(arglist);

	while((c=*buf)){
		lf = (c=='\n');

		if(mbs&&(c&0x80)&&buf[1]){
			index = (unsigned char)c;
			buf++;
		}
		else index = 0;

		font = sets[index];

		if(font){
			if(lf){
				x = ox;
				y += font->height;
			} else {
				id = ((int)(*buf)) & 0xFF;
				w = font->token_width[id];
				dm.centerx = (id&0xf)*font->width;
				dm.centery = (id>>4)*font->height;
				dm.clipx = x;
				dm.clipy = y;
				dm.clipw = font->width;
				dm.cliph = font->height;
				//printf("%d %d %d %d %d %d \n", dm.centerx, dm.centery, dm.clipx, dm.clipy, dm.clipw, dm.cliph);
				spriteq_add_frame(x,y, FONT_LAYER + layeroffset, font->token, &dm, 0);
				x += w;
			}
		}
		buf++;
	}
}


// Print to a screen rather than queueing the sprites
void screen_printf(s_screen * screen, int x, int y, int which, char *format, ...){
	char * buf = b, c;
	va_list arglist;
	int ox = x;
	s_drawmethod dm = plainmethod;
	s_font** sets, *font;
	int mbs, index, w, lf, id;

	which %= MAX_FONTS;
	if(which < 0) return;

	sets = fonts[which];

	if(!sets) return;

	mbs = sets[0]->mbs;

	va_start(arglist, format);
	vsprintf(buf, format, arglist);
	va_end(arglist);

	while((c=*buf)){
		lf = (c=='\n');

		if(mbs&&(c&0x80)&&buf[1]){
			index = (unsigned char)c;
			buf++;
		}
		else index = 0;

		font = sets[index];

		if(font){
			if(lf){
				x = ox;
				y += font->height;
			} else {
				id = ((int)(*buf)) & 0xFF;
				w = font->token_width[id];
				dm.centerx = (id&0xf)*font->width;
				dm.centery = (id>>4)*font->height;
				dm.clipx = x;
				dm.clipy = y;
				dm.clipw = font->width;
				dm.cliph = font->height;
				putsprite(x, y, font->token, screen, &dm);
				x += w;
			}
		}
		buf++;
	}
}



