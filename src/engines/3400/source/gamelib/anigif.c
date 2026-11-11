/* AnyBOR modification record: 2026-10-30.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Preserve each profile's GIF decoding, palette, frame disposal and playback
 * results with bounded input and owned decoder storage.
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

// Animated GIF player.

#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stddef.h>
#include "packfile.h"
#include "borendian.h"
#include "types.h"
#include "screen.h"
#include "anigif.h"
#include "obor_gif_memory.h"


extern uint32_t obor_profile_build;

static void obor_gif_palette(unsigned char *destination, unsigned char *rgb,
                            int suppress_blackening)
{
    int i;
    if(obor_profile_build < 3424) rgb[0] = 0;
    else if(obor_profile_build >= 3453 && !suppress_blackening)
        rgb[0] = rgb[1] = rgb[2] = 0;
    switch(PAL_BYTES) {
    case 768: memcpy(destination, rgb, 768); break;
    case 512:
        for(i=0; i<256; ++i) {
            unsigned short color = colour16(rgb[i*3], rgb[i*3+1], rgb[i*3+2]);
            memcpy(destination+i*2, &color, sizeof(color));
        }
        break;
    case 1024:
        for(i=0; i<256; ++i) {
            unsigned color = colour32(rgb[i*3], rgb[i*3+1], rgb[i*3+2]);
            memcpy(destination+i*4, &color, sizeof(color));
        }
        break;
    }
}

static void obor_gif_pixel(anigif_info *info, s_screen *screen,
                          size_t position, unsigned char index)
{
    unsigned char *palette = info->local_pal ? info->local_pal : info->global_pal;
    if(obor_profile_build < 3477 || screen->pixelformat == PIXEL_8)
        screen->data[position] = index;
    else if(palette && screen->pixelformat == PIXEL_16)
        memcpy(screen->data+position*2, palette+(size_t)index*2, 2);
    else if(palette && screen->pixelformat == PIXEL_32)
        memcpy(screen->data+position*4, palette+(size_t)index*4, 4);
}

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
			if(u >= firstcodestack+4096) return 0;
			*u++ = oldtoken;
			thiscode = oldcode;
		}

		while(thiscode>=bits2){
            if(thiscode>=nextcode || thiscode>=4096 || u>=firstcodestack+4096) return 0;
			*u++ = lastcodestack [thiscode];
			thiscode = codestack[thiscode];
		}

		oldtoken = thiscode;
		do{
			if(byte < width && byte >= 0 && line >= -(int64_t)gb->top &&
               line < (int64_t)height - gb->top && thiscode != info->transparent)
            {
                size_t position = (size_t)(gb->top + line) * (size_t)width + (size_t)byte;
                obor_gif_pixel(info, buf, position, (unsigned char)thiscode);
            }
			byte++;
			if(byte >= gb->left + gb->width){
				byte = gb->left;
				// check for interlaced image
				if(gb->flags&0x40){
					line += inctable[pass];
					if(line >= gb->height) {
                        if(pass>=4) return 0;
                        line = startable[++pass];
                    }
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








void anigif_close_ex(anigif_info* info){
    if(!info) return;
	closepackfile(info->handle);
	info->handle = -1;
}



// Returns true on success
int anigif_open_ex(char *filename, char *packfilename, unsigned char *pal, anigif_info* info){
	unsigned char tpal[1024] = {0};
    int noblackenbg, legacy_transparent;
    if(!info) return 0;
    noblackenbg = info->noblackenbg;
    legacy_transparent = info->transparent;

	memset(info, 0, sizeof(anigif_info));

	info->handle = -1;
	info->transparent = obor_profile_build < 3418 ? legacy_transparent : -1;
	info->noblackenbg = obor_profile_build >= 3477 ? noblackenbg : 0;
    if(!filename) return 0;

#if PSP || PS2 || DC
	if((info->handle=openreadaheadpackfile(filename,packfilename,1*1024*1024, 131072))==-1) return 0;
#else
	if((info->handle=openpackfile(filename,packfilename))==-1) return 0;
#endif

	if(readpackfile(info->handle,&info->gif_header,sizeof_gifheaderstruct)!=sizeof_gifheaderstruct){
		anigif_close_ex(info);
		return 0;
	}

	if(info->gif_header.magic[0]!='G' || info->gif_header.magic[1]!='I' || info->gif_header.magic[2]!='F'){
		// Not a GIF file!
		anigif_close_ex(info);
		return 0;
	}

	//info->current_res[0] = SwapLSB16(info->gif_header.screenwidth);
	//info->current_res[1] = SwapLSB16(info->gif_header.screenheight);

    if(obor_profile_build < 3477) {
        info->bitdepth = (info->gif_header.flags&7)+1;
        info->numcolours = 1<<info->bitdepth;
    } else if(obor_profile_build == 3477) {
        info->bitdepth = info->gif_header.flags&0x80 ?
            (info->gif_header.flags&7)+1 : ((info->gif_header.flags>>4)&7)+1;
        info->numcolours = 1<<info->bitdepth;
    } else if(info->gif_header.flags&0x80) {
        info->bitdepth = (info->gif_header.flags&7)+1;
        if(obor_profile_build >= 3479) info->numcolours = 1<<info->bitdepth;
    } else info->bitdepth = 8;
	info->lastdelay = 1;
	//printf("numcolours:%d\n", info->numcolours);

	// Get global palette, if present and if wanted
	if(info->gif_header.flags&0x80){
		info->global_pal = pal;
		if(pal){
			if(readpackfile(info->handle, tpal, info->numcolours*3) != info->numcolours*3){

				anigif_close_ex(info);
				return 0;
			}
            obor_gif_palette(pal, tpal, noblackenbg);
		}
		else seekpackfile(info->handle, info->numcolours*3, SEEK_CUR);
	}

	return 1;
}




// Returns type of action to take (frame, retry, end)
int anigif_decode_ex(s_screen * screen, int *delay, int x, int y, unsigned char* pal, anigif_info* info){

	gifblockstruct iblock;
	unsigned char tpal[1024] = {0};
	unsigned char c;
	int numcolours;


	if(!info || info->handle<0) return ANIGIF_DECODE_END;
	if(screen==NULL){
		anigif_close_ex(info);
		return ANIGIF_DECODE_END;
	}

	if(readpackfile(info->handle,&c,1)!=1){
		anigif_close_ex(info);
		return ANIGIF_DECODE_END;
	}


	switch(c){
		case ',':
			// An image block
			if(readpackfile(info->handle, &iblock, sizeof_iblock)!=sizeof_iblock){
				anigif_close_ex(info);
				return ANIGIF_DECODE_END;
			}

            if(iblock.flags&0x80) {
                numcolours = obor_profile_build >= 3478 ?
                    1<<((iblock.flags&7)+1) : info->numcolours;
                if(obor_profile_build < 3477 || !pal)
                    seekpackfile(info->handle, numcolours*3, SEEK_CUR);
                else {
                    info->local_pal = pal;
                    if(readpackfile(info->handle, tpal, numcolours*3) != numcolours*3) {
                        anigif_close_ex(info);
                        return ANIGIF_DECODE_END;
                    }
                    obor_gif_palette(pal, tpal, info->noblackenbg);
                }
                if(obor_profile_build >= 3477) info->local_pal = pal;
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
				anigif_close_ex();
				return ANIGIF_DECODE_END;
			}
*/

			if(delay) *delay = info->lastdelay;
			// lastdelay = 0;
			if(obor_profile_build >= 3477 && iblock.left<0) return ANIGIF_DECODE_RETRY;

			return ANIGIF_DECODE_FRAME|((obor_profile_build >= 3477 && (iblock.flags&0x80))?ANIGIF_DECODE_PAL:0);

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
//			anigif_close_ex();
//			return ANIGIF_DECODE_END;
	}

	anigif_close_ex(info);
	return ANIGIF_DECODE_END;
}









/* Original single-stream callers keep their state and close/open ordering. */
static anigif_info obor_legacy_gif = {.handle=-1, .transparent=-1};
void anigif_close(void) { anigif_close_ex(&obor_legacy_gif); }
int anigif_open(char *filename, char *packfilename, unsigned char *pal)
{
    anigif_close();
    return anigif_open_ex(filename, packfilename, pal, &obor_legacy_gif);
}
int anigif_decode(s_screen *screen, int *delay, int x, int y)
{
    return anigif_decode_ex(screen, delay, x, y, obor_legacy_gif.global_pal,
                           &obor_legacy_gif);
}
