/* SPDX-License-Identifier: LicenseRef-OpenBOR-NoSale AND BSD-3-Clause
 * Original OpenBOR functions retain their terms; see LICENSES/OpenBOR-3400.txt
 * in the distribution. Adapter edits: Copyright (c) 2026 retrodiv
 * <retrodiv@proton.me>, BSD-3-Clause for those contributions only. */
/*
 * OpenBOR - http://www.LavaLit.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2011 OpenBOR Team
 */

/* Reference adapters rename services only; discarded comma operands have no required value and are removed for defined execution. Arithmetic statements and their order are retained. */

void reference_rotate_0(s_screen* dest, gfx_entry* src, int x, int y, int centerx, int centery, s_drawmethod* drawmethod)
{
	double zoomx, zoomy, rzoomx, rzoomy, sina, cosa, ax, ay, bx, by, rx0, ry0, cx, cy, srcx0_f, srcx_f, srcy0_f, srcy_f, angle;
	int i, j, srcx, srcy;
	int xbound[4], ybound[4], xmin, xmax, ymin, ymax;
	double xboundf[4], yboundf[4];
	zoomx = drawmethod->scalex / 256.0;
	zoomy = drawmethod->scaley / 256.0;
	angle = drawmethod->rotate;
    sina = sin_table[(int)angle];
    cosa = cos_table[(int)angle];

	reference_init(dest, src, drawmethod);
	
	/////////////////begin clipping////////////////////////////
	xboundf[0] = drawmethod->flipx? (centerx-reference_sw)*zoomx : -centerx*zoomx;
	yboundf[0] = drawmethod->flipy? (centery-reference_sh)*zoomy : -centery*zoomy;
	xboundf[1] = xboundf[0] + reference_sw*zoomx;
	yboundf[1] = yboundf[0];
	xboundf[2] = xboundf[0];
	yboundf[2] = yboundf[0] + reference_sh*zoomy;
	xboundf[3] = xboundf[1];
	yboundf[3] = yboundf[2];

	for(i=0; i<4; i++){
		xbound[i] =  (int)(x + xboundf[i]*cosa - yboundf[i]*sina);
        ybound[i] =  (int)(y + xboundf[i]*sina + yboundf[i]*cosa);
	}

	xmin = REF_MAX(REF_MIN(REF_MIN(xbound[0],xbound[1]), REF_MIN(xbound[2],xbound[3])), 0);
	xmax = REF_MIN(REF_MAX(REF_MAX(xbound[0],xbound[1]), REF_MAX(xbound[2],xbound[3])), reference_dw);
	ymin = REF_MAX(REF_MIN(REF_MIN(ybound[0],ybound[1]), REF_MIN(ybound[2],ybound[3])), 0);
	ymax = REF_MIN(REF_MAX(REF_MAX(ybound[0],ybound[1]), REF_MAX(ybound[2],ybound[3])), reference_dh);
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
	x -= rx0;
	y -= ry0;
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
            srcx=(int)(srcx_f);
            srcy=(int)(srcy_f);
			if(srcx>=0 && srcx<reference_sw && srcy>=0 && srcy<reference_sh)
				reference_pixel(dest, src, i, j, srcx, srcy);
            srcx_f+=ax;
            srcy_f+=ay;
        }
        srcx0_f+=bx;
        srcy0_f+=by;
    }
}

void reference_scale_0(s_screen *dest, gfx_entry* src, int x, int y, int centerx, int centery, s_drawmethod* drawmethod)
{
	double osx, sx, sy, dx, dy, w, h, cx, cy, stepdx, stepdy;
	int beginy, endy, beginx, endx;
	int i, j;
	double zoomx = drawmethod->scalex / 256.0;
	double zoomy = drawmethod->scaley / 256.0;
	double shiftf = drawmethod->shiftx / 256.0;
	
	//if(!zoomy || !zoomx) return; //should be checked already

	//printf("==%d %d %d %d %d\n", drawmethod->scalex, drawmethod->scaley, drawmethod->flipx, drawmethod->flipy, drawmethod->shiftx);

	reference_init(dest, src, drawmethod);

	w = reference_sw * zoomx;
	h = reference_sh * zoomy;
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
		osx = reference_sw - 1.0;
	}
	if(drawmethod->flipy){
		stepdy = 1.0/zoomy;
		sy = 0.0;
	}else{
		stepdy = -1.0/zoomy;
		sy = reference_sh - 1.0;
	}

	if(REF_MAX(dx+w, dx+w-shiftf*h)<=0) return;
	if(REF_MIN(dx, dx-shiftf*h)>=reference_dw) return;
	if(dy>=reference_dh) return;
	if(dy+h<=0) return;

	if(dy+h>reference_dh) {
		endy = reference_dh;
		dx -= shiftf*(dy+h-endy);
		sy += stepdy*(dy+h-endy);
	} else endy = dy+h;

	if(dy<0) beginy = 0;
	else beginy = dy;

	//printf("=%d, %d, %lf, %lf, %lf, %lf, %lf, %lf\n ",x, y, w, h, osx, sy, dx, dy);
	// =64, 144, 44.000000, 36.500000, 43.000000, 0.000000, 38.000000, 143.000000

	for(j=endy-1; j>=beginy; j--, sy+=stepdy, dx -= shiftf){
		if(dx>=reference_dw) continue;
		if(dx+w<=0) continue;
		sx = osx;
		beginx = dx;
		endx = dx+w;
		if(dx<0) beginx = 0;
		else beginx = dx;
		if(dx+w>reference_dw) {
			endx = reference_dw;
			sx += stepdx*(dx+w-reference_dw);
		} else endx = dx+w;
		for(i=endx-1; i>=beginx; i--, sx+=stepdx){
			//printf("%d, %d, %d, %d\n", i, j, (int)sx, (int)sy);
			reference_pixel(dest, src, i, j, (int)sx, (int)sy);
		}
	}

}

void reference_rotate_1(s_screen* dest, gfx_entry* src, int x, int y, int centerx, int centery, s_drawmethod* drawmethod)
{
	double zoomx, zoomy, rzoomx, rzoomy, sina, cosa, ax, ay, bx, by, rx0, ry0, cx, cy, srcx0_f, srcx_f, srcy0_f, srcy_f, angle;
	int i, j, srcx, srcy;
	int xbound[4], ybound[4], xmin, xmax, ymin, ymax;
	double xboundf[4], yboundf[4];
	zoomx = drawmethod->scalex / 256.0;
	zoomy = drawmethod->scaley / 256.0;
	angle = drawmethod->rotate;
    sina = sin_table[(int)angle];
    cosa = cos_table[(int)angle];

	reference_init(dest, src, drawmethod);

	centerx += drawmethod->centerx;
	centery += drawmethod->centery;
	
	/////////////////begin clipping////////////////////////////
	xboundf[0] = drawmethod->flipx? (centerx-reference_sw)*zoomx : -centerx*zoomx;
	yboundf[0] = drawmethod->flipy? (centery-reference_sh)*zoomy : -centery*zoomy;
	xboundf[1] = xboundf[0] + reference_sw*zoomx;
	yboundf[1] = yboundf[0];
	xboundf[2] = xboundf[0];
	yboundf[2] = yboundf[0] + reference_sh*zoomy;
	xboundf[3] = xboundf[1];
	yboundf[3] = yboundf[2];

	for(i=0; i<4; i++){
		xbound[i] =  (int)(x + xboundf[i]*cosa - yboundf[i]*sina);
        ybound[i] =  (int)(y + xboundf[i]*sina + yboundf[i]*cosa);
	}

	xmin = REF_MAX(REF_MIN(REF_MIN(xbound[0],xbound[1]), REF_MIN(xbound[2],xbound[3])), 0);
	xmax = REF_MIN(REF_MAX(REF_MAX(xbound[0],xbound[1]), REF_MAX(xbound[2],xbound[3])), reference_dw);
	ymin = REF_MAX(REF_MIN(REF_MIN(ybound[0],ybound[1]), REF_MIN(ybound[2],ybound[3])), 0);
	ymax = REF_MIN(REF_MAX(REF_MAX(ybound[0],ybound[1]), REF_MAX(ybound[2],ybound[3])), reference_dh);
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
	x -= rx0;
	y -= ry0;
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
            srcx=(int)(srcx_f);
            srcy=(int)(srcy_f);
			if(srcx>=0 && srcx<reference_sw && srcy>=0 && srcy<reference_sh)
				reference_pixel(dest, src, i, j, srcx, srcy);
            srcx_f+=ax;
            srcy_f+=ay;
        }
        srcx0_f+=bx;
        srcy0_f+=by;
    }
}

void reference_scale_1(s_screen *dest, gfx_entry* src, int x, int y, int centerx, int centery, s_drawmethod* drawmethod)
{
	double osx, sx, sy, dx, dy, w, h, cx, cy, stepdx, stepdy;
	int beginy, endy, beginx, endx;
	int i, j;
	double zoomx = drawmethod->scalex / 256.0;
	double zoomy = drawmethod->scaley / 256.0;
	double shiftf = drawmethod->shiftx / 256.0;
	
	//if(!zoomy || !zoomx) return; //should be checked already

	//printf("==%d %d %d %d %d\n", drawmethod->scalex, drawmethod->scaley, drawmethod->flipx, drawmethod->flipy, drawmethod->shiftx);

	reference_init(dest, src, drawmethod);
	centerx += drawmethod->centerx;
	centery += drawmethod->centery;

	w = reference_sw * zoomx;
	h = reference_sh * zoomy;
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
		osx = reference_sw - 1.0;
	}
	if(drawmethod->flipy){
		stepdy = 1.0/zoomy;
		sy = 0.0;
	}else{
		stepdy = -1.0/zoomy;
		sy = reference_sh - 1.0;
	}

	if(REF_MAX(dx+w, dx+w-shiftf*h)<=0) return;
	if(REF_MIN(dx, dx-shiftf*h)>=reference_dw) return;
	if(dy>=reference_dh) return;
	if(dy+h<=0) return;

	if(dy+h>reference_dh) {
		endy = reference_dh;
		dx -= shiftf*(dy+h-endy);
		sy += stepdy*(dy+h-endy);
	} else endy = dy+h;

	if(dy<0) beginy = 0;
	else beginy = dy;

	//printf("=%d, %d, %lf, %lf, %lf, %lf, %lf, %lf\n ",x, y, w, h, osx, sy, dx, dy);
	// =64, 144, 44.000000, 36.500000, 43.000000, 0.000000, 38.000000, 143.000000

	for(j=endy-1; j>=beginy; j--, sy+=stepdy, dx -= shiftf){
		if(dx>=reference_dw) continue;
		if(dx+w<=0) continue;
		sx = osx;
		beginx = dx;
		endx = dx+w;
		if(dx<0) beginx = 0;
		else beginx = dx;
		if(dx+w>reference_dw) {
			endx = reference_dw;
			sx += stepdx*(dx+w-reference_dw);
		} else endx = dx+w;
		for(i=endx-1; i>=beginx; i--, sx+=stepdx){
			//printf("%d, %d, %d, %d\n", i, j, (int)sx, (int)sy);
			reference_pixel(dest, src, i, j, (int)sx, (int)sy);
		}
	}

}

#define REF_SWAP(va,vb) {vsw=va;va=vb;vb=vsw;}
void reference_triangle(vert2d* vertices, s_screen *dest, gfx_entry *src, s_drawmethod* drawmethod, int triangleCount)
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

	reference_init(dest, src, drawmethod);

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
		if (v1->x > v2->x)	REF_SWAP(v1, v2);
		if (v1->x > v3->x)	REF_SWAP(v1, v3);
		if (v2->x > v3->x)	REF_SWAP(v2, v3);

		if ((v1->x - v3->x) == 0)
			continue;

		trect.ulx = v1->x;
		trect.lrx = v3->x;

		// sort in order of v1 <= v2 <= v3
		if (v1->y > v2->y)	REF_SWAP(v1, v2);
		if (v1->y > v3->y)	REF_SWAP(v1, v3);
		if (v2->y > v3->y)	REF_SWAP(v2, v3);

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
								reference_pixel(dest, src, hSpanBegin, targetY, (int)spanTx, (int)spanTy);
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
#undef REF_SWAP
