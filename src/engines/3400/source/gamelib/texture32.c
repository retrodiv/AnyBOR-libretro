/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Validate 32-bit texture dimensions and palette transfers before drawing.
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

// see texture.c, this file uses 32bit palette and screen
#include <string.h>
#include "types.h"
#include "anybor_texture_bounds.h"

//static int distortion[256];
extern float _sinfactors[256];
extern float _amp;
#define distortion(x) ((int)(_sinfactors[x]*_amp+0.5))


void texture_wavex8p32(s_screen *screen, int x, int y, int width, int height, int offsx, int offsy, s_bitmap *bitmap, int offsd, int step, unsigned* pal32){
    if(!screen || !bitmap) return;
    size_t obor_source_bytes, obor_dest_bytes;
    int obor_distortion;
    int64_t obor_source_y = offsy;


	unsigned char *src, *sp;
	unsigned char *dest, *dp;
	int s, i;
	int sy;
	int twidth;
	int tx;
    const unsigned char *thepal = pal32 ? (const unsigned char *)pal32 : bitmap->palette;

	    if(!obor_texture_palette(bitmap, thepal, 4)) return;
	/* AnyBOR: validate texture dimensions and owned storage. */
    if(!obor_texture_clip(screen->width, screen->height, bitmap->width, bitmap->height,
            &x, &y, &width, &height) ||
       !obor_texture_storage(screen, screen->data, screen->width, screen->height, 4, &obor_dest_bytes) ||
       !obor_texture_storage(bitmap, bitmap->data, bitmap->width, bitmap->height, 1, &obor_source_bytes)) return;
    /* AnyBOR: native clipped texture follows. */

	// Dest ptr
    dest = screen->data + ((size_t)y * (size_t)screen->width + (size_t)x) * 4;

	// Fill area
	do{
		// Source line ptr
		sy = (int)(obor_source_y % bitmap->height);
        if(sy < 0) return;
        src = bitmap->data + (size_t)sy * (size_t)bitmap->width;
		obor_source_y++;

		// Adjust distortion stuff
		offsd &= 255;
		if(!obor_texture_distortion(_sinfactors[offsd], _amp, &obor_distortion)) return;
        s = (int)(((int64_t)offsx + obor_distortion) % bitmap->width);
        if(s < 0) return;
		offsd = (int)(((unsigned int)offsd + (unsigned int)step) & 255u);

		// Copy loop
		tx = 0;
		twidth = bitmap->width - s;
		if(twidth > width) twidth = width;
		while(twidth > 0){
			// apply texture to 24bit screen
			dp = dest + (size_t)tx * 4;
			sp = src+s;
			for(i=0; i<twidth; i++) obor_texture_palette_pixel(dp + (size_t)i * 4, thepal, sp[i], 4);
			s = 0;
			tx += twidth;
			twidth = width - tx;
			if(twidth > bitmap->width) twidth = bitmap->width;
		}

		// Advance destination line pointer
		if(height > 1) dest += (size_t)screen->width * 4;
	}while(--height);

}



static void draw_plane_line(unsigned char *destline, unsigned char *srcline, int destlen, int srclen, uint64_t stretchto, int texture_offset, const unsigned char *table, size_t source_available){
    if(!destline || !srcline || destlen <= 0 || srclen <= 0 || !stretchto) return;

	int i;
	unsigned int s, s_pos, s_step;
	int center_offset = destlen / 2;

	s_pos = (unsigned int)texture_offset + (unsigned int)srclen * 256u;
	s_step = (unsigned int)((uint64_t)(unsigned int)srclen * 256u / stretchto);
	s_pos -= center_offset * s_step;

	for(i=0; i<destlen; i++){
		s = s_pos >> 8;
		if(s > srclen){
			s %= srclen;
			s_pos = (s_pos & 0xFF) | (s << 8);
		}
        if((size_t)s >= source_available) return;
        obor_texture_palette_pixel(destline + (size_t)i * 4, table, srcline[s], 4);
		s_pos += s_step;
	}
}



// Draw a plane (like the sea)
void texture_planex8p32(s_screen *screen, int x, int y, int width, int height, int fixp_offs, int factor, s_bitmap *bitmap, unsigned* pal32){
    if(!screen || !bitmap) return;
    size_t obor_source_bytes, obor_dest_bytes;


	int i;
	unsigned char *dest;
	unsigned char *src;
	int sy;
    const unsigned char *thepal = pal32 ? (const unsigned char *)pal32 : bitmap->palette;

	    if(!obor_texture_palette(bitmap, thepal, 4)) return;

	if(factor < 0) return;
	uint64_t obor_factor = (uint64_t)(unsigned int)factor + 1;

	/* AnyBOR: validate texture dimensions and owned storage. */
    if(!obor_texture_clip(screen->width, screen->height, bitmap->width, bitmap->height,
            &x, &y, &width, &height) ||
       !obor_texture_storage(screen, screen->data, screen->width, screen->height, 4, &obor_dest_bytes) ||
       !obor_texture_storage(bitmap, bitmap->data, bitmap->width, bitmap->height, 1, &obor_source_bytes)) return;
    /* AnyBOR: native clipped texture follows. */


    dest = screen->data + ((size_t)y * (size_t)screen->width + (size_t)x) * 4;
	sy = 0;
	for(i=0; i<height; i++){

		sy = i % bitmap->height;
        src = bitmap->data + (size_t)sy * (size_t)bitmap->width;

		draw_plane_line(dest, src, width, bitmap->width,
            (uint64_t)(unsigned int)bitmap->width + (uint64_t)(unsigned int)bitmap->width * (unsigned int)i / obor_factor,
            fixp_offs, thepal, obor_source_bytes - (size_t)sy * (size_t)bitmap->width);

		if(i + 1 < height) dest += (size_t)screen->width * 4;
	}
}




