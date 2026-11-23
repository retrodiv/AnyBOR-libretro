/* AnyBOR modification record: 2026-09-12.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Preserve the original legacy decoder and streamed GIF frames, palettes and
 * timing from 3870.
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

// Animated GIF player.

#include <stdio.h>
#include <string.h>
#include "packfile.h"
#include "borendian.h"
#include "types.h"
#include "screen.h"
#include "anigif.h"
#include "anybor_gif_memory.h"

// Animated GIF player.


static unsigned char readbyte(int handle){
	unsigned char c = 0;
	readpackfile(handle, &c, 1);
	return c;
}

static void passgifblock(anigif_info* info){
	int len;

	// Skip all contained blocks
	while((len=readbyte(info->handle))!=0) seekpackfile(info->handle, len, SEEK_CUR);
}



static void handle_gfx_control(anigif_info* info){
	int len;
	int skip;
	unsigned char buf[4] = {0};


	// Handle all contained blocks
	while((len=readbyte(info->handle))!=0){
		skip = len - 4;
		if(len>4) len = 4;
		readpackfile(info->handle, buf, len);
		if(skip>0) seekpackfile(info->handle, skip, SEEK_CUR);

		if(buf[0]&1) info->transparent = buf[3];
		info->lastdelay = (buf[2]<<8) | buf[1];

		// disposal = (buf[0]>>2) & 7;
		// inputflag = (buf[0]>>1) & 1;
	}
}



static void gifextension(anigif_info* info){
	int function;

	// Get extension function code
	function = readbyte(info->handle);

	// Note: function may be repeated multiple times (size, data, size, data)
	switch(function){
		case 0xF9:
			// Graphic control
			handle_gfx_control(info);
			return;
		default:
			// 0x01 = text
			// 0xFF = app. extension
			// 0xFE = comment
			passgifblock(info);
			return;
	}
}



/*
int readnonzero(int handle){
	char b = 0;
	while(b==0){
		if(readpackfile(handle, &b, 1) < 1) return 0;
	}
	return b;
}
*/




static int decodegifblock(anigif_info* info, s_screen* buf, int width, int height, gifblockstruct *gb){

	unsigned char bits;
	short bits2;
	short codesize;
	short codesize2;
	short nextcode;
	short thiscode;
	short oldtoken;
	short currentcode;
	short oldcode;
	short bitsleft;
	short blocksize;
	int64_t line = 0;
	int byte = gb->left;
	int pass = 0;

	unsigned char *p;
	unsigned char *u;

	unsigned char *q;
	unsigned char b[255];

	static unsigned char firstcodestack[4096];
	static unsigned char lastcodestack[4096];
	static short codestack[4096];

	static short wordmasktable[] = {0x0000, 0x0001, 0x0003, 0x0007,
					0x000f, 0x001f, 0x003f, 0x007f,
					0x00ff, 0x01ff, 0x03ff, 0x07ff,
					0x0fff, 0x1fff, 0x3fff, 0x7fff };

	static short inctable[] = { 8, 8, 4, 2, 0 };
	static short startable[] = { 0, 4, 2, 1, 0 };


	// get the initial LZW code bits
	bits = readbyte(info->handle);
	if(bits<2 || bits>8) return 0;

	p = q = b;
	bitsleft = 8;

	bits2 = 1 << bits;
	nextcode = bits2 + 2;
	codesize2 = 1 << (codesize = bits + 1);
	oldcode = oldtoken = NO_CODE;


	// loop until something breaks
	for(;;){
		if(bitsleft == 8){
			if(++p >= q && (((blocksize = readbyte(info->handle)) < 1) ||
				(q = obor_gif_read_block(info->handle, (p = b), blocksize)) < (b+blocksize))){
				return 1;	// Done
			}
			bitsleft = 0;
		}
		thiscode = *p;
		if((currentcode=(codesize+bitsleft)) <= 8){
			*p >>= codesize;
			bitsleft = currentcode;
		}
		else{
			if(++p >= q && (((blocksize = readbyte(info->handle)) < 1) ||
				(q = obor_gif_read_block(info->handle, (p = b), blocksize)) < (b+blocksize))){
				return 1;	// Done
			}

			thiscode |= *p << (8 - bitsleft);
			if(currentcode<=16) *p >>= (bitsleft = currentcode - 8);
			else{
				if(++p >= q && (((blocksize = readbyte(info->handle)) < 1) ||
					(q = obor_gif_read_block(info->handle, (p = b), blocksize)) < (b+blocksize))){
					return 1;	// Done
				}

				thiscode |= *p << (16 - bitsleft);
				*p >>= (bitsleft = currentcode - 16);
			}
		}
		thiscode &= wordmasktable[codesize];
		currentcode = thiscode;

		if(thiscode==(bits2+1)) break;
		if(thiscode>nextcode){
			return 0;			// Bad code
		}

		if(thiscode==bits2){
			nextcode = bits2 + 2;
			codesize2 = 1 << (codesize = (bits+1));
			oldtoken = oldcode = NO_CODE;
			continue;
		}

		u = firstcodestack;

		if(thiscode==nextcode){
			if(oldcode==NO_CODE){
				return 0;		// Bad code
			}
			*u++ = oldtoken;
			thiscode = oldcode;
		}

		while(thiscode>=bits2){
            if(thiscode >= nextcode || thiscode >= 4096 || u >= firstcodestack + 4096) return 0;
			*u++ = lastcodestack [thiscode];
			thiscode = codestack[thiscode];
		}

		oldtoken = thiscode;
		do{
			if(byte < width && byte >= 0 && line >= -(int64_t)gb->top &&
               line < (int64_t)height - gb->top && thiscode != info->transparent)
            {
                size_t position = (size_t)(gb->top + line) * (size_t)width + (size_t)byte;
                obor_gif_store_pixel(buf, info->local_pal ? info->local_pal : info->global_pal, position, (unsigned char)thiscode);
            }
			byte++;
			if(byte >= gb->left + gb->width){
				byte = gb->left;
				// check for interlaced image
				if(gb->flags&0x40){
					line += inctable[pass];
					if(line >= gb->height) { if(pass >= 4) return 0; line = startable[++pass]; }
				}
				else { if(line == INT64_MAX) return 0; ++line; }
			}
			if (u<=firstcodestack) break;
			thiscode = *--u;
		}while(1);

		if(nextcode<4096 && oldcode!=NO_CODE){
			codestack[nextcode] = oldcode;
			lastcodestack[nextcode] = oldtoken;
			if(++nextcode>=codesize2 && codesize<12) codesize2 = 1<<++codesize;
		}
		oldcode = currentcode;
	}

	return 1;
}








void anigif_close(anigif_info* info){
    if(!info) return;
	closepackfile(info->handle);
	info->handle = -1;
}



// Returns true on success
int anigif_open(char *filename, char *packfilename, unsigned char *pal, anigif_info* info){
    if(!info) return 0;
	unsigned char tpal[1024] = {0};
	int i, j;
	int noblackenbg = info->noblackenbg;

	memset(info, 0, sizeof(anigif_info));

	info->handle = -1;
	info->transparent = -1;
	info->noblackenbg = noblackenbg;
    if(!filename) return 0;

#if 0 //PSP || PS2 || DC
	if((info->handle=openreadaheadpackfile(filename,packfilename,1*1024*1024, 131072))==-1) return 0;
#else
	if((info->handle=openpackfile(filename,packfilename))==-1) return 0;
#endif

	if(readpackfile(info->handle,&info->gif_header,sizeof_gifheaderstruct)!=sizeof_gifheaderstruct){

		anigif_close(info);
		return 0;
	}

	if(info->gif_header.magic[0]!='G' || info->gif_header.magic[1]!='I' || info->gif_header.magic[2]!='F'){
		// Not a GIF file!
		anigif_close(info);
		return 0;
	}

	//info->current_res[0] = SwapLSB16(info->gif_header.screenwidth);
	//info->current_res[1] = SwapLSB16(info->gif_header.screenheight);

	if(info->gif_header.flags&0x80){
		info->bitdepth = (info->gif_header.flags&7)+1;
		info->numcolours = 1<<info->bitdepth ;
	}else{
		info->bitdepth = 8;
		info->numcolours = 0;
	}
	info->lastdelay = 1;
	//printf("numcolours:%d\n", info->numcolours);

	// Get global palette, if present and if wanted
	if(info->gif_header.flags&0x80){
		info->global_pal = pal;
		if(pal){
			if(readpackfile(info->handle, tpal, info->numcolours*3) != info->numcolours*3){

				anigif_close(info);
				return 0;
			}
			//*tpal &= 0xFF000000;
			if(!noblackenbg) tpal[0] = tpal[1] = tpal[2] = 0; 
			switch(PAL_BYTES)
			{
			case 768:
				memcpy(pal, tpal, 768);
				break;
			case 1024:
				for(i=0, j=0; i<1024; i+=4, j+=3)
				{
					{ unsigned int obor_color_value = colour32(tpal[j], tpal[j+1], tpal[j+2]); memcpy(pal + i, &obor_color_value, sizeof(obor_color_value)); }
				}
				break;
			case 512:
				for(i=0, j=0; i<512; i+=2, j+=3)
				{
					{ unsigned short obor_color_value = colour16(tpal[j], tpal[j+1], tpal[j+2]); memcpy(pal + i, &obor_color_value, sizeof(obor_color_value)); }
				}
				break;
			}
		}
		else seekpackfile(info->handle, info->numcolours*3, SEEK_CUR);
	}

	return 1;
}




// Returns type of action to take (frame, retry, end)
int anigif_decode(s_screen * screen, int *delay, int x, int y, unsigned char* pal, anigif_info* info){
    if(!info) return ANIGIF_DECODE_END;

	gifblockstruct iblock;
	unsigned char tpal[1024] = {0};
	unsigned char c;
	int i, j, numcolours;


	if(info->handle<0) return ANIGIF_DECODE_END;
	if(screen==NULL){
		anigif_close(info);
		return ANIGIF_DECODE_END;
	}

	if(readpackfile(info->handle,&c,1)!=1){
		anigif_close(info);
		return ANIGIF_DECODE_END;
	}


	switch(c){
		case ',':
			// An image block
			if(readpackfile(info->handle, &iblock, sizeof_iblock)!=sizeof_iblock){

				anigif_close(info);
				return ANIGIF_DECODE_END;
			}

			if(iblock.flags&0x80){
				info->local_pal = pal;
				numcolours = 1<<((iblock.flags&7)+1);
				if(pal){
					if(readpackfile(info->handle, tpal, numcolours*3) != numcolours*3){
						anigif_close(info);
						return ANIGIF_DECODE_END;
					}
					if(!info->noblackenbg) tpal[0] = tpal[1] = tpal[2] = 0; 
					switch(PAL_BYTES)
					{
					case 768:
						memcpy(pal, tpal, 768);
						break;
					case 1024:
						for(i=0, j=0; i<1024; i+=4, j+=3)
						{
							{ unsigned int obor_color_value = colour32(tpal[j], tpal[j+1], tpal[j+2]); memcpy(pal + i, &obor_color_value, sizeof(obor_color_value)); }
						}
						break;
					case 512:
						for(i=0, j=0; i<512; i+=2, j+=3)
						{
							{ unsigned short obor_color_value = colour16(tpal[j], tpal[j+1], tpal[j+2]); memcpy(pal + i, &obor_color_value, sizeof(obor_color_value)); }
							//printf("%d*", *(unsigned short*)(pal+i));
						}
						break;
					}
					//printf("iblock:%d,%d,%d,%d\n",  SwapLSB16(iblock.left), SwapLSB16(iblock.top), SwapLSB16(iblock.width), SwapLSB16(iblock.height));
				}
				else seekpackfile(info->handle, numcolours*3, SEEK_CUR);
			}

			iblock.left = SwapLSB16(iblock.left);
			iblock.top = SwapLSB16(iblock.top);
			iblock.width = SwapLSB16(iblock.width);
			iblock.height = SwapLSB16(iblock.height);
			iblock.left = obor_gif_offset(iblock.left, x);
			iblock.top = obor_gif_offset(iblock.top, y);

			decodegifblock(info, screen, screen->width, screen->height, &iblock);
/*
			if(!decodegifblock(handle, screen->data, screen->width, screen->height, &iblock)){
				anigif_close();
				return ANIGIF_DECODE_END;
			}
*/

			if(delay) *delay = info->lastdelay;
			// lastdelay = 0;
			if(iblock.left<0) return ANIGIF_DECODE_RETRY;

			return ANIGIF_DECODE_FRAME|((iblock.flags&0x80)?ANIGIF_DECODE_PAL:0);

		case '!':
			// Handle GIF extension
			gifextension(info);
			// if(delay) *delay = lastdelay;
			// lastdelay = 0;
			return ANIGIF_DECODE_RETRY;

//		case 0:
		default:
			// Isn't this an EOF?
			return ANIGIF_DECODE_RETRY;
//			anigif_close();
//			return ANIGIF_DECODE_END;
	}

	anigif_close(info);
	return ANIGIF_DECODE_END;
}









#include <limits.h>

/* The 3870 decoder gives each plane its own file, palette and timing. Reuse
 * the bounded image and extension readers above for both decoder interfaces. */
struct obor_anigif_stream
{
    struct
    {
        anigif_info decoder;
        unsigned char global_palette[1024];
        unsigned char local_palette[1024];
        s_screen *image;
        u32 nextframe;
    } planes[3];
    s_screen *composite;
    int is_rgb, frame, done;
};

static void obor_anigif_stream_release(obor_anigif_stream *stream)
{
    for(int n = 0; n < 3; ++n)
    {
        if(stream->planes[n].decoder.handle >= 0)
            anigif_close(&stream->planes[n].decoder);
        freescreen(&stream->planes[n].image);
    }
    freescreen(&stream->composite);
}

void obor_anigif_stream_close(obor_anigif_stream *stream)
{
    if(!stream) return;
    obor_anigif_stream_release(stream);
    free(stream);
}

obor_anigif_stream *obor_anigif_stream_open(char *filename, char *packfilename)
{
    char channel_name[256];
    int is_rgb = pixelformat == PIXEL_x8;
    size_t basename;
    if(!filename) return NULL;
    basename = strlen(filename);
    if(basename >= 4 && !stricmp(filename + basename - 4, ".gif")) basename -= 4;
    if(basename > sizeof(channel_name) - sizeof("_.gif")) return NULL;
    memcpy(channel_name, filename, basename);
    memcpy(channel_name + basename, "_.gif", sizeof("_.gif"));
    if(is_rgb)
    {
        for(int n = 0; n < 3; ++n)
        {
            channel_name[basename] = "rgb"[n];
            if(testpackfile(channel_name, packfilename) < 0) is_rgb = 0;
        }
    }

    obor_anigif_stream *stream = calloc(1, sizeof(*stream));
    if(!stream) return NULL;
    stream->is_rgb = is_rgb;
    for(int n = 0; n < 3; ++n) stream->planes[n].decoder.handle = -1;
    const int planes = is_rgb ? 3 : 1;
    for(int n = 0; n < planes; ++n)
    {
        channel_name[basename] = "rgb"[n];
        stream->planes[n].decoder.noblackenbg = is_rgb;
        if(!anigif_open(is_rgb ? channel_name : filename, packfilename,
                        stream->planes[n].global_palette, &stream->planes[n].decoder))
            goto open_error;
    }

    const gifheaderstruct *header = &stream->planes[0].decoder.gif_header;
    int width = SwapLSB16(header->screenwidth);
    int height = SwapLSB16(header->screenheight);
    if(!height || width > (INT_MAX - 2048) / height / pixelbytes[screenformat])
        goto open_error;
    if(is_rgb)
    {
        stream->composite = allocscreen(width, height, screenformat);
        if(!stream->composite) goto open_error;
        clearscreen(stream->composite);
    }
    for(int n = planes - 1; n >= 0; --n)
    {
        stream->planes[n].image = allocscreen(width, height, screenformat);
        if(!stream->planes[n].image) goto open_error;
        clearscreen(stream->planes[n].image);
    }
    return stream;

open_error:
    obor_anigif_stream_close(stream);
    return NULL;
}

static int obor_anigif_stream_step(anigif_info *decoder, s_screen *image,
                                  unsigned char *local_palette)
{
    gifblockstruct block;
    unsigned char marker;
    if(readpackfile(decoder->handle, &marker, 1) != 1) return ANIGIF_DECODE_END;
    if(marker == '!') gifextension(decoder);
    if(marker != ',') return ANIGIF_DECODE_RETRY;
    if(readpackfile(decoder->handle, &block, sizeof_iblock) != sizeof_iblock)
        return ANIGIF_DECODE_END;
    if(block.flags & 0x80)
    {
        unsigned char colors[768] = {0};
        int bytes = 3 * (1 << ((block.flags & 7) + 1));
        if(readpackfile(decoder->handle, colors, bytes) != bytes)
            return ANIGIF_DECODE_END;
        if(!decoder->noblackenbg) colors[0] = colors[1] = colors[2] = 0;
        switch(PAL_BYTES)
        {
        case 768:
            memcpy(local_palette, colors, sizeof(colors));
            break;
        case 512:
            for(int i = 0; i < 256; ++i)
            {
                unsigned short value = colour16(colors[3*i], colors[3*i+1], colors[3*i+2]);
                memcpy(local_palette + 2*i, &value, sizeof(value));
            }
            break;
        case 1024:
            for(int i = 0; i < 256; ++i)
            {
                unsigned int value = colour32(colors[3*i], colors[3*i+1], colors[3*i+2]);
                memcpy(local_palette + 4*i, &value, sizeof(value));
            }
            break;
        }
        decoder->local_pal = local_palette;
    }
    block.left = SwapLSB16(block.left);
    block.top = SwapLSB16(block.top);
    block.width = SwapLSB16(block.width);
    block.height = SwapLSB16(block.height);
    decodegifblock(decoder, image, image->width, image->height, &block);
    return ANIGIF_DECODE_FRAME;
}

int obor_anigif_stream_decode(obor_anigif_stream *stream)
{
    if(!stream || stream->done) return 1;
    const int planes = stream->is_rgb ? 3 : 1;
    for(int n = 0; n < planes; ++n)
    {
        anigif_info *decoder = &stream->planes[n].decoder;
        int code;
        do
        {
            code = obor_anigif_stream_step(decoder, stream->planes[n].image,
                                          stream->planes[n].local_palette);
        } while(code == ANIGIF_DECODE_RETRY);
        stream->planes[n].nextframe += decoder->lastdelay * 10u;
        if(code == ANIGIF_DECODE_END)
        {
            stream->done = 1;
            obor_anigif_stream_release(stream);
            return 1;
        }
    }
    if(stream->is_rgb && (screenformat == PIXEL_16 || screenformat == PIXEL_32))
    {
        s_screen *image = stream->composite;
        size_t bytes = (size_t)image->width * image->height * pixelbytes[screenformat];
        for(size_t i = 0; i < bytes; ++i)
            image->data[i] = stream->planes[0].image->data[i] |
                             stream->planes[1].image->data[i] |
                             stream->planes[2].image->data[i];
    }
    ++stream->frame;
    return 0;
}

s_screen *obor_anigif_stream_buffer(obor_anigif_stream *stream)
{
    return stream->is_rgb ? stream->composite : stream->planes[0].image;
}

obor_anigif_status obor_anigif_stream_status(const obor_anigif_stream *stream)
{
    const s_screen *image = stream->planes[0].image;
    return (obor_anigif_status){ .done = stream->done, .frame = stream->frame,
        .is_rgb = stream->is_rgb, .width = image ? image->width : 0,
        .height = image ? image->height : 0,
        .nextframe = stream->planes[0].nextframe, .lastdelay = stream->planes[0].decoder.lastdelay };
}
