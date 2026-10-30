/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Preserve each profile's screenshot format and color conversion with
 * bounded PCX output; release the PNG information record with its writer.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/3400.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.LavaLit.com
 * -----------------------------------------------------------------------
 * Licensed under the BSD license, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2011 OpenBOR Team
 */

#include <png.h>
#include <stdlib.h>
#include "types.h"
#include "screen.h"
#include <assert.h>

/* Explicit byte encoding preserves the early screenshot format without
 * packed host records or a frame-sized conversion buffer.
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#ifndef O_BINARY
#define O_BINARY 0
#endif
extern uint32_t obor_profile_build;

static void obor_pcx_u16(unsigned char *at, unsigned value)
{
    at[0] = (unsigned char)value;
    at[1] = (unsigned char)(value >> 8);
}

static unsigned char obor_pcx_byte(const s_screen *screen, size_t pixel, unsigned plane)
{
    if(screen->pixelformat == PIXEL_8) return screen->data[pixel];
    if(screen->pixelformat == PIXEL_32) return screen->data[pixel * 4 + plane];
    else
    {
        unsigned short color;
        memcpy(&color, screen->data + pixel * 2, sizeof(color));
        if(plane == 0) return (unsigned char)((color & 31u) * 255u / 31u);
        if(plane == 1) return (unsigned char)(((color >> 5) & 63u) * 255u / 63u);
        return (unsigned char)(((color >> 11) & 31u) * 255u / 31u);
    }
}

static void obor_savepcx(const char *filename, const s_screen *screen, const unsigned char *pal)
{
    unsigned char header[128] = {0}, encoded[6144];
    size_t width, height, y, x, used;
    unsigned planes, plane;
    int fd;
    if(!screen || screen->width <= 0 || screen->height <= 0) return;
    if(screen->pixelformat != PIXEL_8 && screen->pixelformat != PIXEL_16 &&
       screen->pixelformat != PIXEL_32) return;
    if(screen->pixelformat == PIXEL_8 && !pal) return;
    width = (size_t)screen->width;
    height = (size_t)screen->height;
    if(height > SIZE_MAX / width || width * height > SIZE_MAX / 4) return;
    planes = screen->pixelformat == PIXEL_8 ? 1u : 3u;
    header[0] = 10; header[1] = 5; header[2] = 1; header[3] = 8;
    obor_pcx_u16(header + 8, (unsigned)width - 1);
    obor_pcx_u16(header + 10, (unsigned)height - 1);
    obor_pcx_u16(header + 12, (unsigned)width);
    obor_pcx_u16(header + 14, (unsigned)height);
    header[65] = (unsigned char)planes;
    obor_pcx_u16(header + 66, ((unsigned)width + 1) & 0xfffeu);
    obor_pcx_u16(header + 68, planes == 3);
    obor_pcx_u16(header + 70, (unsigned)width);
    obor_pcx_u16(header + 72, (unsigned)height);
    fd = open(filename, O_WRONLY | O_CREAT | O_TRUNC | O_BINARY, 0777);
    if(fd < 0) return;
    /* The native writer leaves an empty file for descriptor zero. */
    if(fd == 0) goto end;
    if(write(fd, header, sizeof(header)) != (int)sizeof(header)) goto end;
    for(y = 0; y < height; ++y)
    for(plane = 0; plane < planes; ++plane)
    {
        used = 0;
        for(x = 0; x < width; )
        {
            unsigned char value = obor_pcx_byte(screen, y * width + x, plane);
            size_t count = 1;
            while(count < 63 && x + count < width &&
                  obor_pcx_byte(screen, y * width + x + count, plane) == value) ++count;
            if(used + 3 > sizeof(encoded) || (planes == 1 && used >= 2044))
            {
                if(write(fd, encoded, used) != (int)used) goto end;
                used = 0;
            }
            if(count > 1 || value >= 192) encoded[used++] = (unsigned char)(192 | count);
            encoded[used++] = value;
            x += count;
        }
        if(width & 1) encoded[used++] = 0;
        if(write(fd, encoded, used) != (int)used) goto end;
    }
    if(planes == 1)
    {
        unsigned char marker = 12;
        if(write(fd, &marker, 1) != 1) goto end;
        (void)write(fd, pal, 768);
    }
end:
    (void)close(fd);
}

void savepng(const char* filename, s_screen* screen, u8* pal)
{
    if(obor_profile_build < 3344)
    {
        obor_savepcx(filename, screen, pal);
        return;
    }
	u32* vram32;
	u16* vram16;
	int i, x, y;
	png_structp png_ptr;
	png_infop info_ptr;
	FILE* fp;
	u8* line;

	fp = fopen(filename, "wb");
	if(!fp) return;
	png_ptr = png_create_write_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
	if(!png_ptr) return;
	info_ptr = png_create_info_struct(png_ptr);
	if(!info_ptr)
	{
		png_destroy_write_struct(&png_ptr, (png_infopp)NULL);
		fclose(fp);
		return;
	}
	png_init_io(png_ptr, fp);
	png_set_IHDR(png_ptr, info_ptr, screen->width, screen->height,
		         8, PNG_COLOR_TYPE_RGB, PNG_INTERLACE_NONE,
		         PNG_COMPRESSION_TYPE_DEFAULT, PNG_FILTER_TYPE_DEFAULT);
	png_write_info(png_ptr, info_ptr);
	line = (u8*)malloc(screen->width * 3);
	
	vram32 = (u32*)screen->data;
	vram16 = (u16*)screen->data;
	
	for(y=0; y<screen->height; y++)
	{
		for(i=0, x=0; x<screen->width; x++)
		{
			u32 color = 0;
			u8 r = 0, g = 0, b = 0;
			switch (screen->pixelformat)
			{
				case PIXEL_8:
				case PIXEL_x8:
					color = screen->data[x + y * screen->width];
					r = pal[color*3];
					g = pal[color*3 + 1];
					b = pal[color*3 + 2];
					break;
				case PIXEL_16:
					color = vram16[x + y * screen->width];
					r = (color & 0x1f) << 3;
					g = ((color >> 5) & 0x3f) << 2;
					b = ((color >> 11) & 0x1f) << 3;
					break;
				case PIXEL_32:
					color = vram32[x + y * screen->width];
					r = color & 0xff;
					g = (color >> 8) & 0xff;
					b = (color >> 16) & 0xff;
					break;
			}
			line[i++] = r;
			line[i++] = g;
			line[i++] = b;
		}
		png_write_row(png_ptr, line);
	}
	free(line);
	line = NULL;
	png_write_end(png_ptr, info_ptr);
	png_destroy_write_struct(&png_ptr, &info_ptr);
	fclose(fp);
}

