/* AnyBOR modification record: 2026-11-09.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Remove a guard whose only statement assigned the counter to itself. Bound
 * screen blend selectors and use transparent copy when an indexed table is
 * unavailable. Select native screen-drawing enable and transparency flags by
 * profile.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/7533.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c)  OpenBOR Team
 */

/*
	Code for handling 'screen' structures.
	(Memory allocation and copy functions)
	Last update: 10 feb 2003
*/
#include <stdio.h>
#include <string.h>
#include "types.h"
#include "transform.h"
#include "screen.h"

s_screen *allocscreen(int width, int height, int pixelformat)
{
    s_screen *screen;
    int psize;
    width &= (0xFFFFFFFF - 3);
    psize = width * height * pixelbytes[pixelformat];
    if(pixelformat == PIXEL_x8)
    {
        screen = (s_screen *)malloc(sizeof(s_screen) + psize + PAL_BYTES + ANYNUMBER);
    }
    else
    {
        screen = (s_screen *)malloc(sizeof(s_screen) + psize + ANYNUMBER);
    }
    if(screen == NULL)
    {
        return NULL;
    }
    screen->width = width;
    screen->height = height;
    screen->pixelformat = pixelformat;
    screen->magic = screen_magic;
    if(pixelformat == PIXEL_x8)
    {
        screen->palette = ((unsigned char *)screen->data) + width * height * pixelbytes[(int)pixelformat];
    }
    else
    {
        screen->palette = NULL;
    }
    return screen;
}

void freescreen(s_screen **screen)
{
    s_screen *owned;
    if(!screen) return;
    memcpy(&owned, (const void *)screen, sizeof(owned));
    if(owned) free(owned);
    owned = NULL;
    memcpy((void *)screen, &owned, sizeof(owned));
}

// Screen copy func. Supports clipping.
void copyscreen(s_screen *dest, s_screen *src)
{
    unsigned char *sp, *dp;
    int width = src->width;
    int height = src->height;
    int pixelformat = src->pixelformat;

    if(pixelformat != dest->pixelformat)
    {
        return;
    }

    if(height > dest->height)
    {
        height = dest->height;
    }
    if(width > dest->width)
    {
        width = dest->width;
    }

    dp = dest->data;
    sp = src->data;
    // Copy unclipped
    if(dest->width == src->width)
    {
        memcpy(dest->data, src->data, width * height * pixelbytes[(int)pixelformat]);
        return;
    }

    // Copy clipped
    do
    {
        memcpy(dp, sp, width * pixelbytes[(int)pixelformat]);
        sp += src->width * pixelbytes[(int)pixelformat];
        dp += dest->width * pixelbytes[(int)pixelformat];
    }
    while(--height);
}

void clearscreen(s_screen *s)
{
    if(s == NULL)
    {
        return;
    }
    memset(s->data, 0, s->width * s->height * pixelbytes[(int)s->pixelformat]);
}

// Screen copy function with offset options. Supports clipping.
void copyscreen_o(s_screen *dest, s_screen *src, int x, int y)
{
    unsigned char *sp, *dp;
    int pixelformat = src->pixelformat;
    int sw = src->width;
    int sh = src->height;
    int dw = dest->width;
    int cw = sw, ch = sh;
    int linew, slinew, dlinew;
    int sox, soy;

    int xmin = useclip ? clipx1 : 0,
        xmax = useclip ? clipx2 : dest->width,
        ymin = useclip ? clipy1 : 0,
        ymax = useclip ? clipy2 : dest->height;

    // Copy anything at all?
    if(x >= xmax)
    {
        return;
    }
    if(sw + x <= xmin)
    {
        return;
    }
    if(y >= ymax)
    {
        return;
    }
    if(sh + y <= ymin)
    {
        return;
    }

    sox = 0;
    soy = 0;

    // Clip?
    if(x < xmin)
    {
        sox = xmin - x;
        cw -= sox;
    }
    if(y < ymin)
    {
        soy = ymin - y;
        ch -= soy;
    }

    if(x + sw > xmax)
    {
        cw -= (x + sw) - xmax;
    }
    if(y + sh > ymax)
    {
        ch -= (y + sh) - ymax;
    }

    if(x < xmin)
    {
        x = xmin;
    }
    if(y < ymin)
    {
        y = ymin;
    }

    if(dest->pixelformat != src->pixelformat)
    {
        return;
    }

    sp = src->data + (soy * sw + sox) * pixelbytes[(int)pixelformat];
    dp = dest->data + (y * dw + x) * pixelbytes[(int)pixelformat];
    linew = cw * pixelbytes[(int)pixelformat];
    slinew = sw * pixelbytes[(int)pixelformat];
    dlinew = dw * pixelbytes[(int)pixelformat];
    // Copy data
    do
    {
        memcpy(dp, sp, linew);
        sp += slinew;
        dp += dlinew;
    }
    while(--ch);
}

// same as above, with color key
void copyscreen_trans(s_screen *dest, s_screen *src, int x, int y)
{
    unsigned char *sp, *dp;
    int sw = src->width;
    int sh = src->height;
    int dw = dest->width;
    int cw = sw, ch = sh;
    int sox, soy;
    int i;

    int xmin = useclip ? clipx1 : 0,
        xmax = useclip ? clipx2 : dest->width,
        ymin = useclip ? clipy1 : 0,
        ymax = useclip ? clipy2 : dest->height;

    // Copy anything at all?
    if(x >= xmax)
    {
        return;
    }
    if(sw + x <= xmin)
    {
        return;
    }
    if(y >= ymax)
    {
        return;
    }
    if(sh + y <= ymin)
    {
        return;
    }

    sox = 0;
    soy = 0;

    // Clip?
    if(x < xmin)
    {
        sox = xmin - x;
        cw -= sox;
    }
    if(y < ymin)
    {
        soy = ymin - y;
        ch -= soy;
    }

    if(x + sw > xmax)
    {
        cw -= (x + sw) - xmax;
    }
    if(y + sh > ymax)
    {
        ch -= (y + sh) - ymax;
    }

    if(x < xmin)
    {
        x = xmin;
    }
    if(y < ymin)
    {
        y = ymin;
    }

    sp = src->data + (soy * sw + sox);
    dp = dest->data + (y * dw + x);
    // Copy data
    do
    {
        i = cw - 1;
        do
        {
            if(sp[i] == 0)
            {
                continue;
            }
            dp[i] = sp[i];
        }
        while(i--);
        sp += sw;
        dp += dw;
    }
    while(--ch);
}

//same as above, with remap, work only under 8bit pixel format
void copyscreen_remap(s_screen *dest, s_screen *src, int x, int y, unsigned char *remap)
{
    unsigned char *sp = src->data;
    unsigned char *dp = dest->data;
    int i;
    int sw = src->width;
    int sh = src->height;
    int dw = dest->width;
    int cw = sw, ch = sh;
    int sox, soy;

    int xmin = useclip ? clipx1 : 0,
        xmax = useclip ? clipx2 : dest->width,
        ymin = useclip ? clipy1 : 0,
        ymax = useclip ? clipy2 : dest->height;

    // Copy anything at all?
    if(x >= xmax)
    {
        return;
    }
    if(sw + x <= xmin)
    {
        return;
    }
    if(y >= ymax)
    {
        return;
    }
    if(sh + y <= ymin)
    {
        return;
    }

    sox = 0;
    soy = 0;

    // Clip?
    if(x < xmin)
    {
        sox = xmin - x;
        cw -= sox;
    }
    if(y < ymin)
    {
        soy = ymin - y;
        ch -= soy;
    }

    if(x + sw > xmax)
    {
        cw -= (x + sw) - xmax;
    }
    if(y + sh > ymax)
    {
        ch -= (y + sh) - ymax;
    }

    if(x < xmin)
    {
        x = xmin;
    }
    if(y < ymin)
    {
        y = ymin;
    }

    sp += (soy * sw + sox);
    dp += (y * dw + x);

    // Copy data
    do
    {
        i = cw - 1;
        do
        {
            if(!sp[i])
            {
                continue;
            }
            dp[i] = remap[sp[i]];
        }
        while(i--);
        sp += sw;
        dp += dw;
    }
    while(--ch);
}

//same as above, with alpha blend
void blendscreen(s_screen *dest, s_screen *src, int x, int y, unsigned char *lut)
{
    unsigned char *sp = src->data;
    unsigned char *dp = dest->data;
    int i;
    int sw = src->width;
    int sh = src->height;
    int dw = dest->width;
    int cw = sw, ch = sh;
    int sox, soy;
    unsigned char *d, *s;

    int xmin = useclip ? clipx1 : 0,
        xmax = useclip ? clipx2 : dest->width,
        ymin = useclip ? clipy1 : 0,
        ymax = useclip ? clipy2 : dest->height;

    // Copy anything at all?
    if(x >= xmax)
    {
        return;
    }
    if(sw + x <= xmin)
    {
        return;
    }
    if(y >= ymax)
    {
        return;
    }
    if(sh + y <= ymin)
    {
        return;
    }

    sox = 0;
    soy = 0;

    // Clip?
    if(x < xmin)
    {
        sox = xmin - x;
        cw -= sox;
    }
    if(y < ymin)
    {
        soy = ymin - y;
        ch -= soy;
    }

    if(x + sw > xmax)
    {
        cw -= (x + sw) - xmax;
    }
    if(y + sh > ymax)
    {
        ch -= (y + sh) - ymax;
    }

    if(x < xmin)
    {
        x = xmin;
    }
    if(y < ymin)
    {
        y = ymin;
    }

    sp += soy * sw + sox;
    dp += y * dw + x;

    // Copy data
    do
    {
        i = cw;
        do
        {
            d = dp + i - 1;
            s = sp + i - 1;
            if(!(*s))
            {
                continue;
            }
            *d = lut[(*s) << 8 | (*d)];
        }
        while(--i);
        sp += sw;
        dp += dw;
    }
    while(--ch);
}


static unsigned char *obor_screen_blend_table(int alpha)
{
    if(alpha <= 0 || alpha > MAX_BLENDINGS) return NULL;
    return blendtables[alpha - 1];
}

static void _putscreen(s_screen *dest, s_screen *src, int x, int y, s_drawmethod *drawmethod)
{
    unsigned char *table;
    int alpha, transbg;
    gfx_entry gfx;

    if(!drawmethod || (obor_profile_build >= 7567 ? (int)(drawmethod->config & DRAWMETHOD_CONFIG_ENABLED) : drawmethod->flag) == 0)
    {
        table = NULL;
        alpha = 0;
        transbg = 0;
    }
    else if(drawmethod->water.watermode && drawmethod->water.amplitude)
    {
        gfx.screen = src;
        if(drawmethod->water.watermode == 3)
        {
            gfx_draw_plane(dest, &gfx, x, y, 0, 0, drawmethod);
        }
        else
        {
            gfx_draw_water(dest, &gfx, x, y, 0, 0, drawmethod);
        }
        return ;
    }
    else if(drawmethod->rotate)
    {
        gfx.screen = src;
        gfx_draw_rotate(dest, &gfx, x, y, 0, 0, drawmethod);
        return;
    }
    else if(drawmethod->scalex != 256 || drawmethod->scaley != 256 || drawmethod->shiftx)
    {
        gfx.screen = src;
        gfx_draw_scale(dest, &gfx, x, y, 0, 0, drawmethod);
        return;
    }
    else
    {
        table = drawmethod->table;
        alpha = drawmethod->alpha;
        transbg = (obor_profile_build >= 7567 ? (int)(drawmethod->config & DRAWMETHOD_CONFIG_BACKGROUND_TRANSPARENCY) : drawmethod->transbg);
        x -= drawmethod->centerx;
        y -= drawmethod->centery;
    }

    if(!table && alpha <= 0 && !transbg && !usechannel)
    {
        if(dest->pixelformat == src->pixelformat && dest->width == src->width && dest->height == src->height && !x && !y)
        {
            copyscreen(dest, src);
            return;
        }
    }

    if(dest->pixelformat == PIXEL_8)
    {
        if(table)
        {
            copyscreen_remap(dest, src, x, y, drawmethod->table);
        }
        else if(alpha > 0)
        {
            unsigned char *blend_table = obor_screen_blend_table(alpha);
            if(blend_table) blendscreen(dest, src, x, y, blend_table);
            else copyscreen_trans(dest, src, x, y);
        }
        else if(transbg)
        {
            copyscreen_trans(dest, src, x, y);
        }
        else
        {
            copyscreen_o(dest, src, x, y);
        }
    }
    else if(dest->pixelformat == PIXEL_16)
    {
        if(src->pixelformat == PIXEL_x8)
        {
            putscreenx8p16(dest, src, x, y, transbg, (unsigned short *)table, getblendfunction16(alpha));
        }
        else if(src->pixelformat == PIXEL_16)
        {
            blendscreen16(dest, src, x, y, transbg, getblendfunction16(alpha));
        }
    }
    else if(dest->pixelformat == PIXEL_32)
    {
        if(src->pixelformat == PIXEL_x8)
        {
            putscreenx8p32(dest, src, x, y, transbg, (unsigned *)table, getblendfunction32(alpha));
        }
        else if(src->pixelformat == PIXEL_32)
        {
            blendscreen32(dest, src, x, y, transbg, getblendfunction32(alpha));
        }
    }
}

void putscreen(s_screen *dest, s_screen *src, int x, int y, s_drawmethod *drawmethod)
{
    int xrepeat, yrepeat, xspan, yspan, i, j, dx, dy;

    drawmethod_global_init(drawmethod);

    if(drawmethod && (obor_profile_build >= 7567 ? (int)(drawmethod->config & DRAWMETHOD_CONFIG_ENABLED) : drawmethod->flag))
    {
        xrepeat = drawmethod->xrepeat;
        yrepeat = drawmethod->yrepeat;
        xspan = drawmethod->xspan;
        yspan = drawmethod->yspan;
    }
    else
    {
        xrepeat = yrepeat = 1;
        xspan = yspan = 0;
    }

    for(j = 0, dy = y; j < yrepeat; j++, dy += yspan)
    {
        for(i = 0, dx = x; i < xrepeat; i++, dx += xspan)
        {
            _putscreen(dest, src, dx, dy, drawmethod);
        }
    }

}

// Scale screen
void scalescreen(s_screen *dest, s_screen *src)
{
    int sw, sh;
    int dw, dh;
    int dx, dy;
    unsigned char *sp;
    unsigned char *dp;
    unsigned char *lineptr;
    unsigned int xstep, ystep, xpos, ypos;
    int pixelformat = src->pixelformat;

    if(dest->pixelformat != pixelformat)
    {
        return;
    }

    if(src == NULL || dest == NULL)
    {
        return;
    }
    sp = src->data;
    dp = dest->data;

    sw = src->width * pixelbytes[(int)pixelformat];
    sh = src->height;
    dw = dest->width * pixelbytes[(int)pixelformat];
    dh = dest->height;

    xstep = (sw << 16) / dw;
    ystep = (sh << 16) / dh;

    ypos = 0;
    for(dy = 0; dy < dh; dy++)
    {
        lineptr = sp + ((ypos >> 16) * sw);
        ypos += ystep;
        xpos = 0;
        for(dx = 0; dx < dw; dx++)
        {
            *dp = lineptr[xpos >> 16];
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
#include <stddef.h>
#include <stdint.h>
#include "obor_resources.h"

static int obor_zoom_storage(const s_screen *screen, size_t *length)
{
    size_t bytes=obor_allocation_size(screen), start=offsetof(s_screen,data);
    unsigned count;
    if(bytes < start || screen->magic != screen_magic || screen->width <= 0 || screen->height <= 0) return 0;
    switch(screen->pixelformat) {
        case PIXEL_8: case PIXEL_x8: count=1; break;
        case PIXEL_16: count=2; break;
        case PIXEL_32: count=4; break;
        default: return 0;
    }
    if((size_t)screen->width > SIZE_MAX/count/(size_t)screen->height) return 0;
    *length=(size_t)screen->width*(size_t)screen->height*count;
    return *length <= bytes-start;
}

void zoomscreen(s_screen *dest, s_screen *src, int centerx, int centery, int scalex, int scaley)
{
    size_t source_bytes,dest_bytes;
    int64_t width,height,xmin,ymin;
    uint64_t xstep,ystep;
    unsigned count;
    const unsigned char *source;
    unsigned char *copy=NULL;
    if(scalex <= 0 || scaley <= 0 || !obor_zoom_storage(src,&source_bytes) ||
       !obor_zoom_storage(dest,&dest_bytes) || src->pixelformat != dest->pixelformat) return;
    width=((int64_t)src->width*256)/scalex;
    height=((int64_t)src->height*256)/scaley;
    if(width <= 0 || height <= 0) return;
    xmin=width/2-centerx; ymin=height/2-centery;
    if(xmin >= src->width || xmin+((width*scalex)/256) < 0 || ymin >= src->height) return;
    count=src->pixelformat==PIXEL_16?2:src->pixelformat==PIXEL_32?4:1;
    width &= ~INT64_C(3); /* Native allocscreen rounds its crop width down. */
    if(width <= 0) return;
    xstep=((uint64_t)width*65536)/(unsigned)dest->width;
    ystep=((uint64_t)height*65536)/(unsigned)dest->height;
    source=src->data;
    if(src==dest) {
        copy=malloc(source_bytes);
        if(!copy) return;
        memcpy(copy,source,source_bytes);source=copy;
    }
    for(int y=0;y<dest->height;++y) {
        int64_t fy=(int64_t)(((uint64_t)(unsigned)y*ystep)/65536);
        int64_t sy=fy-ymin;
        for(int x=0;x<dest->width;++x) {
            int64_t fx=(int64_t)(((uint64_t)(unsigned)x*xstep)/65536);
            int64_t sx=fx-xmin;
            unsigned char *pixel=dest->data+((size_t)y*(size_t)dest->width+(size_t)x)*count;
            if((!useclip || (fx >= clipx1 && fx < clipx2 && fy >= clipy1 && fy < clipy2)) &&
               sx >= 0 && sx < src->width && sy >= 0 && sy < src->height)
                memcpy(pixel,source+((size_t)sy*(size_t)src->width+(size_t)sx)*count,count);
            else memset(pixel,0,count); /* Define only originally unassigned crop bytes. */
        }
    }
    free(copy);
}
