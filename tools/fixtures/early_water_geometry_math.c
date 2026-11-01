/*
 * OpenBOR - http://www.LavaLit.com
 * Copyright (c) 2004 - 2011 OpenBOR Team
 * All rights reserved, see LICENSE in OpenBOR root for details.
 * Source functions retain LICENSES/OpenBOR-3400.txt; only service/symbol
 * adapters are BSD-3-Clause, copyright (c) 2026 retrodiv <retrodiv@proton.me>.
 * SPDX-License-Identifier: LicenseRef-OpenBOR-NoSale AND BSD-3-Clause
 */
extern float _sinfactors[256];
#define distortion(x,a) ((int)(_sinfactors[x]*(a)+0.5))
void reference_water(s_screen *dest, gfx_entry* src, int x, int y, int centerx, int centery, s_drawmethod* drawmethod){
	int sw, sh, dw, dh, ch, sy, t, u, sbeginx, sendx, dbeginx, dendx, bytestocopy, amplitude, time;
	float s, wavelength;

	reference_init(dest, src, drawmethod);
	centerx += drawmethod->centerx;
	centery += drawmethod->centery;

	sw = reference_sw;
	sh = reference_sh;
	dw = reference_dw;
	dh = reference_dh;
	ch = sh;
	x -= centerx;
	y -= centery;

	amplitude = drawmethod->water.amplitude;
	time = drawmethod->water.wavetime;

	s = (float)(time % 256);

	// Clip x
	if(x + amplitude*2 + sw <= 0 || x - amplitude*2  >= dw) return;
	if(y + sh <=0 || y >= dh) return;

	sy = 0;
	if(s<0) s+=256;

	// Clip y
	if(y<0) {sy = -y; ch += y;}
	if(y+sh > dh) ch -= (y+sh) - dh;

	if(y<0) y = 0;

	u = (drawmethod->water.watermode==1)?distortion((int)s, amplitude):amplitude;
	wavelength = 256 / drawmethod->water.wavelength;
	s += sy*wavelength;

	// Copy data
	do{
		s = s - (int)s + (int)s % 256;
		t = distortion((int)s, amplitude) - u;

		dbeginx = x+t;
		dendx = x+t+sw;
		
		if(dbeginx>=dw || dendx<=0) {dbeginx = dendx = sbeginx = sendx = 0;} //Nothing to draw
		//clip both
		else if(dbeginx<0 && dendx>dw){ 
			sbeginx = -dbeginx; sendx = sbeginx + dw;
			dbeginx = 0; dendx = dw;
		}
		//clip left
		else if(dbeginx<0) {
			sbeginx = -dbeginx; sendx = sw;
			dbeginx = 0;
		}
		// clip right
		else if(dendx>dw) {
			sbeginx = 0; sendx = dw - dbeginx;	
			dendx = dw;
		}
		// clip none
		else{
			sbeginx = 0; sendx = sw;
		}
		bytestocopy = dendx-dbeginx;
		
		//TODO: optimize this if necessary
		for(t=0; t<bytestocopy; t++, sbeginx++, dbeginx++){
			reference_pixel(dest, src, dbeginx, y, sbeginx, sy);
		}

		s += wavelength;
		y++;
		sy++;
	}while(--ch);
}
void reference_plane_0(s_screen *dest, gfx_entry* src, int x, int y, int centerx, int centery, s_drawmethod* drawmethod){

	int i, j, dx, dy, sx, sy, factor, width, height;
	int s_pos, s_step;
	int center_offset;

	reference_init(dest, src, drawmethod);
	centerx += drawmethod->centerx;
	centery += drawmethod->centery;

	x -= centerx;
	y -= centery;

	factor = drawmethod->water.wavelength;

	if(factor < 0) return;
	factor++;

	width = reference_sw;
	height = reference_sh;

	// Check dimensions
	if(x >= reference_dw) return;
	if(y >= reference_dh) return;
	if(x<0){
		width += x;
		x = 0;
	}
	if(y<0){
		height += y;
		y=0;
	}
	if(x+width > reference_dw){
		width = reference_dw - x;
	}
	if(y+height > reference_dh){
		height = reference_dh - y;
	}
	if(width<=0) return;
	if(height<=0) return;


	dy = y;
	dx = x;
	sy = 0;
	for(i=0; i<height; i++, dy++)
	{
		sy = i % reference_sh;

		center_offset = width / 2;

		s_pos = drawmethod->water.wavetime * 256 + (256 * reference_sw);
		s_step = reference_sw * 256 / (reference_sw + reference_sw * i / factor);
		s_pos -= center_offset * s_step;

		for(j=0; j<width; j++, s_pos += s_step){
			sx = s_pos >> 8;
			if(sx > reference_sw){
				sx %= reference_sw;
				s_pos = (s_pos & 0xFF) | (sx << 8);
			}
			reference_pixel(dest, src, dx+j, dy, sx, sy);
		}
	}

}
void reference_plane_1(s_screen *dest, gfx_entry* src, int x, int y, int centerx, int centery, s_drawmethod* drawmethod){

	int i, j, dx, dy, sx, sy, factor, width, height;
	int s_pos, s_step, x_pos;
	int center_offset;

	reference_init(dest, src, drawmethod);
	centerx += drawmethod->centerx;
	centery += drawmethod->centery;

	x -= centerx;
	y -= centery;

	x_pos = x;

	factor = drawmethod->water.wavelength;

	if(factor < 0) return;
	factor++;

	width = reference_sw;
	height = reference_sh;

	// Check dimensions
	if(x >= reference_dw) return;
	if(y >= reference_dh) return;
	if(x<0){
		width += x;
		x = 0;
	}
	if(y<0){
		height += y;
		y=0;
	}
	if(x+width > reference_dw){
		width = reference_dw - x;
	}
	if(y+height > reference_dh){
		height = reference_dh - y;
	}
	if(width<=0) return;
	if(height<=0) return;


	dy = y;
	dx = x;
	sy = 0;
	for(i=0; i<height; i++, dy++)
	{
		sy = i % reference_sh;

		center_offset = reference_dw / 2 - x;

		s_pos = (drawmethod->water.wavetime - x_pos) * 256 + (256 * reference_sw);
		s_step = reference_sw * 256 / (reference_sw + reference_sw * i / factor);
		s_pos -= center_offset * s_step;

		for(j=0; j<width; j++, s_pos += s_step){
			sx = s_pos >> 8;
			if(sx > reference_sw){
				sx %= reference_sw;
				s_pos = (s_pos & 0xFF) | (sx << 8);
			}
			reference_pixel(dest, src, dx+j, dy, sx, sy);
		}
	}

}
void reference_plane_2(s_screen *dest, gfx_entry* src, int x, int y, int centerx, int centery, s_drawmethod* drawmethod){

	int i, j, dx, dy, sx, sy, factor, width, height;
	int s_pos, s_step, x_pos;
	int center_offset;

	reference_init(dest, src, drawmethod);
	centerx += drawmethod->centerx;
	centery += drawmethod->centery;

	x -= centerx;
	y -= centery;

	x_pos = x;

	factor = drawmethod->water.wavelength;

	if(factor < 0) return;
	factor++;

	width = reference_sw;
	height = reference_sh;

	// Check dimensions
	if(x >= reference_dw) return;
	if(y >= reference_dh) return;
	if(x<0){
		width += x;
		x = 0;
	}
	if(y<0){
		height += y;
		y=0;
	}
	if(x+width > reference_dw){
		width = reference_dw - x;
	}
	if(y+height > reference_dh){
		height = reference_dh - y;
	}
	if(width<=0) return;
	if(height<=0) return;


	dy = y;
	dx = x;
	sy = 0;
	for(i=0; i<height; i++, dy++)
	{
		sy = i % reference_sh;

		center_offset = reference_dw / 2 - x;

		s_pos = (drawmethod->water.wavetime - x_pos) * 256 + (256 * reference_sw);
		s_step = reference_sw * 256 / (reference_sw + reference_sw * i / factor);
		s_pos -= center_offset * s_step;

		for(j=0; j<width; j++, s_pos += s_step){
			sx = s_pos >> 8;
			if(sx >= reference_sw){
				sx %= reference_sw;
				s_pos = (s_pos & 0xFF) | (sx << 8);
			}
			reference_pixel(dest, src, dx+j, dy, sx, sy);
		}
	}

}
void reference_plane_3(s_screen *dest, gfx_entry* src, int x, int y, int centerx, int centery, s_drawmethod* drawmethod){

	int i, j, dx, dy, sx, sy, factor, width, height;
	int o_s_pos, s_pos, s_step, x_pos;
	int center_offset;

	reference_init(dest, src, drawmethod);
	centerx += drawmethod->centerx;
	centery += drawmethod->centery;

	x -= centerx;
	y -= centery;

	x_pos = x;

	factor = drawmethod->water.wavelength;

	if(factor < 0) return;
	factor++;

	width = reference_sw;
	height = reference_sh;

	// Check dimensions
	if(x >= reference_dw) return;
	if(y >= reference_dh) return;
	if(x<0){
		width += x;
		x = 0;
	}
	if(y<0){
		height += y;
		y=0;
	}
	if(x+width > reference_dw){
		width = reference_dw - x;
	}
	if(y+height > reference_dh){
		height = reference_dh - y;
	}
	if(width<=0) return;
	if(height<=0) return;


	dy = y;
	dx = x;
	sy = 0;

	center_offset = reference_dw / 2 - x;
	o_s_pos = (drawmethod->water.wavetime - x_pos) * 256 + (256 * reference_sw);

	for(i=0; i<height; i++, dy++)
	{
		sy = i % reference_sh;
		s_step = reference_sw * 256 / (reference_sw + reference_sw * i / factor);
		s_pos = o_s_pos - center_offset * s_step;

		for(j=0; j<width; j++, s_pos += s_step){
			sx = s_pos >> 8;
			if(sx >= reference_sw){
				sx %= reference_sw;
				s_pos = (s_pos & 0xFF) | (sx << 8);
			}
			reference_pixel(dest, src, dx+j, dy, sx, sy);
		}
	}

}
void reference_plane_4(s_screen *dest, gfx_entry* src, int x, int y, int centerx, int centery, s_drawmethod* drawmethod){

	int i, j, dx, dy, sx, sy, width, height;
	float osxpos, sxpos, sypos, sxstep, systep, xpos, factor, size, cx, beginsize, endsize;

	reference_init(dest, src, drawmethod);
	centerx += drawmethod->centerx;
	centery += drawmethod->centery;

	x -= centerx;
	y -= centery;

	xpos = x;

	beginsize = drawmethod->water.beginsize;
	endsize = drawmethod->water.endsize;

	if(beginsize<0 || endsize<0) return;

	width = reference_sw;
	height = reference_sh;

	// Check dimensions
	if(x >= reference_dw) return;
	if(y >= reference_dh) return;
	if(x<0){
		width += x;
		x = 0;
	}
	if(y<0){
		height += y;
		y=0;
	}
	if(x+width > reference_dw){
		width = reference_dw - x;
	}
	if(y+height > reference_dh){
		height = reference_dh - y;
	}
	if(width<=0) return;
	if(height<=0) return;


	dy = y;
	dx = x;

	cx = reference_dw / 2.0 - x;

	osxpos = drawmethod->water.wavetime - xpos + reference_sw;

	factor = (endsize - beginsize) / reference_sh;
	size = beginsize;

	sypos = 0.0;
	for(i=0; i<height; i++, dy++, size+=factor, sypos+=systep)
	{
		sy = (int)sypos;
		sy %= reference_sh;
		if(sy<0) sy += reference_sh;
		sxstep = 1 / size;
		switch(drawmethod->water.perspective){
		case 1: // tile
			systep = sxstep;
			break;
		case 2: //stretch
			systep = sxstep*reference_sh/(float)reference_sw;
			break;
		default:
			systep = 1.0;
		}
		sxpos = osxpos - cx * sxstep;

		for(j=0; j<width; j++, sxpos += sxstep){
			sx = (int)sxpos;
			sx %= reference_sw;
			if(sx<0) sx += reference_sw;
			reference_pixel(dest, src, dx+j, dy, sx, sy);
		}
	}

}
void reference_plane_5(s_screen *dest, gfx_entry* src, int x, int y, int centerx, int centery, s_drawmethod* drawmethod){

	int i, j, dx, dy, sx, sy, width, height;
	float osxpos, sxpos, sypos, sxstep, systep, xpos, ypos, factor, size, cx, beginsize, endsize;

	reference_init(dest, src, drawmethod);
	centerx += drawmethod->centerx;
	centery += drawmethod->centery;

	x -= centerx;
	y -= centery;

	xpos = x;
	ypos = y;

	beginsize = drawmethod->water.beginsize;
	endsize = drawmethod->water.endsize;

	if(beginsize<0 || endsize<0) return;

	width = reference_sw;
	height = reference_sh;

	// Check dimensions
	if(x >= reference_dw) return;
	if(y >= reference_dh) return;
	if(x<0){
		width += x;
		x = 0;
	}
	if(y<0){
		height += y;
		y=0;
	}
	if(x+width > reference_dw){
		width = reference_dw - x;
	}
	if(y+height > reference_dh){
		height = reference_dh - y;
	}
	if(width<=0) return;
	if(height<=0) return;


	dy = ypos;
	dx = x;

	cx = reference_dw / 2.0 - x;

	osxpos = drawmethod->water.wavetime - xpos + reference_sw;

	factor = (endsize - beginsize) / reference_sh;
	size = beginsize;

	sypos = 0.0;
	for(i=0; i<reference_sh; i++, dy++, size+=factor, sypos+=systep)
	{
		sy = (int)sypos;
		sy %= reference_sh;
		if(sy<0) sy += reference_sh;
		sxstep = 1 / size;
		switch(drawmethod->water.perspective){
		case 1: // tile
			systep = sxstep;
			break;
		case 2: //stretch
			systep = sxstep*reference_sh/(float)reference_sw;
			break;
		default:
			systep = 1.0;
		}
		if(dy<0) continue;
		sxpos = osxpos - cx * sxstep;


		for(j=0; j<width; j++, sxpos += sxstep){
			sx = (int)sxpos;
			sx %= reference_sw;
			if(sx<0) sx += reference_sw;
			reference_pixel(dest, src, dx+j, dy, sx, sy);
		}
	}

}
void reference_plane_6(s_screen *dest, gfx_entry* src, int x, int y, int centerx, int centery, s_drawmethod* drawmethod){

	int i, j, dx, dy, sx, sy, width, height, copyh;
	float osxpos, sxpos, sypos, sxstep, systep, xpos, ypos, factor, size, cx, beginsize, endsize;

	reference_init(dest, src, drawmethod);
	centerx += drawmethod->centerx;
	centery += drawmethod->centery;

	x -= centerx;
	y -= centery;

	xpos = x;
	ypos = y;

	beginsize = drawmethod->water.beginsize;
	endsize = drawmethod->water.endsize;

	if(beginsize<0 || endsize<0) return;

	width = reference_sw;
	height = reference_sh;

	// Check dimensions
	if(x >= reference_dw) return;
	if(y >= reference_dh) return;
	if(x<0){
		width += x;
		x = 0;
	}
	if(y<0){
		copyh = -y;
		height += y;
		y=0;
	}else copyh = 0;
	if(x+width > reference_dw){
		width = reference_dw - x;
	}
	if(y+height > reference_dh){
		height = reference_dh - y;
	}
	if(width<=0) return;
	if(height<=0) return;

	copyh += height;

	dy = ypos;
	dx = x;

	cx = reference_dw / 2.0 - x;

	osxpos = drawmethod->water.wavetime - xpos + reference_sw;

	factor = (endsize - beginsize) / reference_sh;
	size = beginsize;

	sypos = 0.0;
	for(i=0; i<copyh; i++, dy++, size+=factor, sypos+=systep)
	{
		sy = (int)sypos;
		sy %= reference_sh;
		if(sy<0) sy += reference_sh;
		sxstep = 1 / size;
		switch(drawmethod->water.perspective){
		case 1: // tile
			systep = sxstep;
			break;
		case 2: //stretch
			systep = sxstep*reference_sh/(float)reference_sw;
			break;
		default:
			systep = 1.0;
		}
		if(dy<0) continue;
		sxpos = osxpos - cx * sxstep;


		for(j=0; j<width; j++, sxpos += sxstep){
			sx = (int)sxpos;
			sx %= reference_sw;
			if(sx<0) sx += reference_sw;
			reference_pixel(dest, src, dx+j, dy, sx, sy);
		}
	}

}
#undef distortion
