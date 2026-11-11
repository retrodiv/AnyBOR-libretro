/* AnyBOR modification record: 2026-10-19.
 * Port maintained by retrodiv <retrodiv@proton.me>.
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> (original contributions).
 * These contributions are licensed under BSD-3-Clause; see LICENSE at the root.
 * Upstream code retains its original license and notices.
 * Check GIF decoder storage and palette bounds while preserving the decoded
 * pixels of valid images.
 * Existing changes recorded here; this is not their implementation date.
 * See MODIFICATIONS.md and docs/modifications/4086.md
 * at the source repository root. Original notices follow below.
 */

/*
 * OpenBOR - http://www.chronocrash.com
 * -----------------------------------------------------------------------
 * All rights reserved, see LICENSE in OpenBOR root for details.
 *
 * Copyright (c) 2004 - 2014 OpenBOR Team
 */

// Animated GIF player.

#include <stdio.h>
#include <string.h>
#include "packfile.h"
#include "borendian.h"
#include "types.h"
#include "screen.h"
#include "anigif.h"
#include "obor_gif_memory.h"

// Animated GIF player.


static unsigned char readbyte(int handle)
{
    unsigned char c = 0;
    readpackfile(handle, &c, 1);
    return c;
}

static void passgifblock(anigif_info *info, int n)
{
    int len;

    // Skip all contained blocks
    while((len = readbyte(info->info[n].handle)) != 0)
    {
        seekpackfile(info->info[n].handle, len, SEEK_CUR);
    }
}

static void handle_gfx_control(anigif_info *info, int n)
{
    int len;
    int skip;
    unsigned char buf[4] = {0};

    // Handle all contained blocks
    while((len = readbyte(info->info[n].handle)) != 0)
    {
        skip = len - 4;
        if(len > 4)
        {
            len = 4;
        }
        readpackfile(info->info[n].handle, buf, len);
        if(skip > 0)
        {
            seekpackfile(info->info[n].handle, skip, SEEK_CUR);
        }

        if(buf[0] & 1)
        {
            info->info[n].transparent = buf[3];
        }
        info->info[n].lastdelay = (buf[2] << 8) | buf[1];

        // disposal = (buf[0]>>2) & 7;
        // inputflag = (buf[0]>>1) & 1;
    }
}

static void gifextension(anigif_info *info, int n)
{
    int function;

    // Get extension function code
    function = readbyte(info->info[n].handle);

    // Note: function may be repeated multiple times (size, data, size, data)
    switch(function)
    {
    case 0xF9:
        // Graphic control
        handle_gfx_control(info, n);
        return;
    default:
        // 0x01 = text
        // 0xFF = app. extension
        // 0xFE = comment
        passgifblock(info, n);
        return;
    }
}

static int decodegifblock(anigif_info *info, gifblockstruct *gb, int n)
{

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
    int transparent = info->info[n].transparent;
    int handle = info->info[n].handle;
    s_screen *buf = info->gifbuffer[n];
    int width = buf->width;
    int height = buf->height;
    unsigned char *pal = info->info[n].local_pal ? info->info[n].local_pal : info->info[n].global_pal;

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
                                    0x0fff, 0x1fff, 0x3fff, 0x7fff
                                   };

    static short inctable[] = { 8, 8, 4, 2, 0 };
    static short startable[] = { 0, 4, 2, 1, 0 };


    // get the initial LZW code bits
    bits = readbyte(handle);
    if(bits < 2 || bits > 8)
    {
        return 0;
    }

    p = q = b;
    bitsleft = 8;

    bits2 = 1 << bits;
    nextcode = bits2 + 2;
    codesize2 = 1 << (codesize = bits + 1);
    oldcode = oldtoken = NO_CODE;


    // loop until something breaks
    for(;;)
    {
        if(bitsleft == 8)
        {
            if(++p >= q && (((blocksize = readbyte(handle)) < 1) ||
                            (q = obor_gif_read_block(handle, (p = b), blocksize)) < (b + blocksize)))
            {
                return 1;	// Done
            }
            bitsleft = 0;
        }
        thiscode = *p;
        if((currentcode = (codesize + bitsleft)) <= 8)
        {
            *p >>= codesize;
            bitsleft = currentcode;
        }
        else
        {
            if(++p >= q && (((blocksize = readbyte(handle)) < 1) ||
                            (q = obor_gif_read_block(handle, (p = b), blocksize)) < (b + blocksize)))
            {
                return 1;	// Done
            }

            thiscode |= *p << (8 - bitsleft);
            if(currentcode <= 16)
            {
                *p >>= (bitsleft = currentcode - 8);
            }
            else
            {
                if(++p >= q && (((blocksize = readbyte(handle)) < 1) ||
                                (q = obor_gif_read_block(handle, (p = b), blocksize)) < (b + blocksize)))
                {
                    return 1;	// Done
                }

                thiscode |= *p << (16 - bitsleft);
                *p >>= (bitsleft = currentcode - 16);
            }
        }
        thiscode &= wordmasktable[codesize];
        currentcode = thiscode;

        if(thiscode == (bits2 + 1))
        {
            break;
        }
        if(thiscode > nextcode)
        {
            return 0;			// Bad code
        }

        if(thiscode == bits2)
        {
            nextcode = bits2 + 2;
            codesize2 = 1 << (codesize = (bits + 1));
            oldtoken = oldcode = NO_CODE;
            continue;
        }

        u = firstcodestack;

        if(thiscode == nextcode)
        {
            if(oldcode == NO_CODE)
            {
                return 0;		// Bad code
            }
            *u++ = oldtoken;
            thiscode = oldcode;
        }

        while(thiscode >= bits2)
        {
            if(thiscode >= nextcode || thiscode >= 4096 || u >= firstcodestack + 4096) return 0;
            *u++ = lastcodestack [thiscode];
            thiscode = codestack[thiscode];
        }

        oldtoken = thiscode;
        do
        {
            if(byte < width && byte >= 0 && line >= -(int64_t)gb->top &&
               line < (int64_t)height - gb->top && thiscode != transparent)
            {
                size_t position = (size_t)(gb->top + line) * (size_t)width + (size_t)byte;
                obor_gif_store_pixel(buf, pal, position, (unsigned char)thiscode);
            }
            byte++;
            if(byte >= gb->left + gb->width)
            {
                byte = gb->left;
                // check for interlaced image
                if(gb->flags & 0x40)
                {
                    line += inctable[pass];
                    if(line >= gb->height)
                    {
                        { if(pass >= 4) return 0; line = startable[++pass]; }
                    }
                }
                else
                {
                    { if(line == INT64_MAX) return 0; ++line; }
                }
            }
            if (u <= firstcodestack)
            {
                break;
            }
            thiscode = *--u;
        }
        while(1);

        if(nextcode < 4096 && oldcode != NO_CODE)
        {
            codestack[nextcode] = oldcode;
            lastcodestack[nextcode] = oldtoken;
            if(++nextcode >= codesize2 && codesize < 12)
            {
                codesize2 = 1 << ++codesize;
            }
        }
        oldcode = currentcode;
    }

    return 1;
}


static void obor_gif_release_screen(void *slot)
{
    s_screen *screen;
    memcpy(&screen, slot, sizeof(screen));
    freescreen(&screen);
    memcpy(slot, &screen, sizeof(screen));
}

void anigif_close(anigif_info *info)
{
    if(!info) return;
    int i;
    for(i = 0; i < 3; i++)
    {
        if(info->info[i].handle >= 0)
        {
            closepackfile(info->info[i].handle);
            info->info[i].handle = -1;
        }
        if(info->info[i].global_pal)
        {
            free(info->info[i].global_pal);
            info->info[i].global_pal = NULL;
        }
        if(info->info[i].local_pal)
        {
            free(info->info[i].local_pal);
            info->info[i].local_pal = NULL;
        }
        if(info->gifbuffer[i])
        {
            obor_gif_release_screen(&info->gifbuffer[i]);
        }

    }
    if(info->backbuffer)
    {
        obor_gif_release_screen(&info->backbuffer);
    }
}

static int test_anigif_open(anigif_info *info, char *tname, char *packfilename, int n)
{
    int i, j;
    unsigned char tpal[1024] = {0};
    unsigned char *pal;
    if(
        (info->info[n].handle = openpackfile(tname, packfilename)) == -1 ||
        readpackfile(info->info[n].handle, &info->info[n].gif_header, sizeof_gifheaderstruct) != sizeof_gifheaderstruct ||
        info->info[n].gif_header.magic[0] != 'G' || info->info[n].gif_header.magic[1] != 'I' || info->info[n].gif_header.magic[2] != 'F'
    )
    {
        anigif_close(info);
        return 0;
    }

    info->info[n].gif_header.screenwidth = SwapLSB16(info->info[n].gif_header.screenwidth);
    info->info[n].gif_header.screenheight = SwapLSB16(info->info[n].gif_header.screenheight);

    if(info->info[n].gif_header.flags & 0x80)
    {
        info->info[n].bitdepth = (info->info[n].gif_header.flags & 7) + 1;
        info->info[n].numcolours = 1 << info->info[n].bitdepth ;
    }
    else
    {
        info->info[n].bitdepth = 8;
        info->info[n].numcolours = 0;
    }
    info->info[n].lastdelay = 1;
    info->info[n].code = ANIGIF_DECODE_RETRY;

    //info->current_res[0] = SwapLSB16(info->gif_header.screenwidth);
    //info->current_res[1] = SwapLSB16(info->gif_header.screenheight);

    //printf("numcolours:%d\n", info->numcolours);

    // Get global palette, if present and if wanted
    if(info->info[n].gif_header.flags & 0x80)
    {
        pal = info->info[n].global_pal = calloc(1, PAL_BYTES);
        if(!pal) { anigif_close(info); return 0; }

        if(readpackfile(info->info[n].handle, tpal, info->info[n].numcolours * 3) != info->info[n].numcolours * 3)
        {
            anigif_close(info);
            return 0;
        }
        if(!info->isRGB)
        {
            tpal[0] = tpal[1] = tpal[2] = 0;
        }
        switch(PAL_BYTES)
        {
        case 768:
            memcpy(pal, tpal, 768);
            break;
        case 1024:
            for(i = 0, j = 0; i < 1024; i += 4, j += 3)
            {
                { unsigned int obor_color_value = colour32(tpal[j], tpal[j + 1], tpal[j + 2]); memcpy(pal + i, &obor_color_value, sizeof(obor_color_value)); }
            }
            break;
        case 512:
            for(i = 0, j = 0; i < 512; i += 2, j += 3)
            {
                { unsigned short obor_color_value = colour16(tpal[j], tpal[j + 1], tpal[j + 2]); memcpy(pal + i, &obor_color_value, sizeof(obor_color_value)); }
            }
            break;
        }
    }
    return 1;

}


// Returns true on success
int anigif_open(char *filename, char *packfilename, anigif_info *info)
{
    if(!info) return 0;
    char tname[256] = {""};
    int i;

    memset(info, 0, sizeof(anigif_info));
    for(i = 0; i < 3; i++)
    {
        info->info[i].handle = -1;
        info->info[i].transparent = -1;
    }
    info->isRGB = (pixelformat == PIXEL_x8);
    if(!filename) return 0;
    size_t name_length = strnlen(filename, sizeof(tname));
    if(name_length >= sizeof(tname)) return 0;
    if(name_length >= 4 && !stricmp(filename + name_length - 4, ".gif"))
        name_length -= 4;
    if(name_length > sizeof(tname) - sizeof("_.gif")) return 0;
    memcpy(tname, filename, name_length);
    memcpy(tname + name_length, "_.gif", sizeof("_.gif"));

    if(info->isRGB)
    {
        tname[strlen(tname) - 5] = 'r';
        if(testpackfile(tname, packfilename) < 0)
        {
            info->isRGB = 0;
        }
        tname[strlen(tname) - 5] = 'g';
        if(testpackfile(tname, packfilename) < 0)
        {
            info->isRGB = 0;
        }
        tname[strlen(tname) - 5] = 'b';
        if(testpackfile(tname, packfilename) < 0)
        {
            info->isRGB = 0;
        }
    }

    

    if(info->isRGB)
    {
        tname[strlen(tname) - 5] = 'r';
        if(!test_anigif_open(info, tname, packfilename, 0))
        {
            return 0;
        }
        tname[strlen(tname) - 5] = 'g';
        if(!test_anigif_open(info, tname, packfilename, 1))
        {
            return 0;
        }
        tname[strlen(tname) - 5] = 'b';
        if(!test_anigif_open(info, tname, packfilename, 2))
        {
            return 0;
        }
    }
    else
    {
        if(!test_anigif_open(info, filename, packfilename, 0))
        {
            return 0;
        }
    }

    if(info->isRGB)
    {
        info->backbuffer = allocscreen(info->info[0].gif_header.screenwidth, info->info[0].gif_header.screenheight, screenformat);
        if(!info->backbuffer) { anigif_close(info); return 0; }
        clearscreen(info->backbuffer);
    }
    for(i = info->isRGB ? 2 : 0; i >= 0; i--)
    {
        info->gifbuffer[i] = allocscreen(info->info[0].gif_header.screenwidth, info->info[0].gif_header.screenheight, screenformat);
        if(!info->gifbuffer[i]) { anigif_close(info); return 0; }
        clearscreen(info->gifbuffer[i]);
    }
    info->frame = -1;
    return 1;
}


// Returns type of action to take (frame, retry, end)
int anigif_decode(anigif_info *info, int n)
{
    if(!info || n < 0 || n >= 3) return ANIGIF_DECODE_END;

    gifblockstruct iblock;
    unsigned char tpal[1024] = {0};
    unsigned char *pal;
    unsigned char c;
    int i, j, numcolours;

    if(info->info[n].handle < 0 || info->gifbuffer[n] == NULL ||
            readpackfile(info->info[n].handle, &c, 1) != 1)
    {
        goto decode_end;
    }

    switch(c)
    {
    case ',':
        // An image block
        if(readpackfile(info->info[n].handle, &iblock, sizeof_iblock) != sizeof_iblock)
        {
            goto decode_end;
        }

        if(iblock.flags & 0x80)
        {
            if(!info->info[n].local_pal)
            {
                info->info[n].local_pal = calloc(1, PAL_BYTES);
            }
            pal = info->info[n].local_pal;
            if(!pal) goto decode_end;
            numcolours = 1 << ((iblock.flags & 7) + 1);
            if(readpackfile(info->info[n].handle, tpal, numcolours * 3) != numcolours * 3)
            {
                goto decode_end;
            }
            if(!info->isRGB)
            {
                tpal[0] = tpal[1] = tpal[2] = 0;
            }
            switch(PAL_BYTES)
            {
            case 768:
                memcpy(pal, tpal, 768);
                break;
            case 1024:
                for(i = 0, j = 0; i < 1024; i += 4, j += 3)
                {
                    { unsigned int obor_color_value = colour32(tpal[j], tpal[j + 1], tpal[j + 2]); memcpy(pal + i, &obor_color_value, sizeof(obor_color_value)); }
                }
                break;
            case 512:
                for(i = 0, j = 0; i < 512; i += 2, j += 3)
                {
                    { unsigned short obor_color_value = colour16(tpal[j], tpal[j + 1], tpal[j + 2]); memcpy(pal + i, &obor_color_value, sizeof(obor_color_value)); }
                    //printf("%d*", *(unsigned short*)(pal+i));
                }
                break;
            }
        }
        else if (info->info[n].local_pal)
        {
            free(info->info[n].local_pal);
            info->info[n].local_pal = NULL;
        }

        iblock.left = SwapLSB16(iblock.left);
        iblock.top = SwapLSB16(iblock.top);
        iblock.width = SwapLSB16(iblock.width);
        iblock.height = SwapLSB16(iblock.height);

        decodegifblock(info, &iblock, n);

        // lastdelay = 0;

        return ANIGIF_DECODE_FRAME | ((iblock.flags & 0x80) ? ANIGIF_DECODE_PAL : 0);

    case '!':
        // Handle GIF extension
        gifextension(info, n);
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

decode_end:
    //anigif_close(info);
    return ANIGIF_DECODE_END;
}

static void anigif_updatebuffer(anigif_info *info)
{
    s_screen *backbuffer = info->backbuffer;
    s_screen *gifbuffer[3];
    memcpy(gifbuffer, info->gifbuffer, sizeof(gifbuffer));
    size_t i, l;
    if(!backbuffer || backbuffer->width <= 0 || backbuffer->height <= 0 ||
       !gifbuffer[0] || !gifbuffer[1] || !gifbuffer[2]) return;
    l = (size_t)backbuffer->width * (size_t)backbuffer->height;
    unsigned short *ps16, *ppr16, *ppg16, *ppb16;
    unsigned int *ps32, *ppr32, *ppg32, *ppb32;
    switch(screenformat)
    {
    case PIXEL_16:
        ps16 = (unsigned short *)(backbuffer->data);
        ppr16 = (unsigned short *)(gifbuffer[0]->data);
        ppg16 = (unsigned short *)(gifbuffer[1]->data);
        ppb16 = (unsigned short *)(gifbuffer[2]->data);
        for(i = 0; i < l; i++)
        {
            ps16[i] =  ppr16[i] | ppg16[i] | ppb16[i];
        }
        break;
    case PIXEL_32:
        ps32 = (unsigned int *)(backbuffer->data);
        ppr32 = (unsigned int *)(gifbuffer[0]->data);
        ppg32 = (unsigned int *)(gifbuffer[1]->data);
        ppb32 = (unsigned int *)(gifbuffer[2]->data);
        for(i = 0; i < l; i++)
        {
            ps32[i] = ppr32[i] | ppg32[i] | ppb32[i];
            //printf(" %u %u %u\n", ppr32[i], ppg32[i], ppb32[i]);
        }
        break;
    }

}

int anigif_decode_frame(anigif_info *info)
{
    if(!info) return 1;
    int n, num = info->isRGB ? 3 : 1;
    if(!info->done)
    {
        for(n = 0; n < num; n++)
        {
            if(info->info[n].code != ANIGIF_DECODE_END)
            {
                while((info->info[n].code = anigif_decode(info, n)) == ANIGIF_DECODE_RETRY);
                info->info[n].nextframe += info->info[n].lastdelay * 10;
            }
            if(info->info[n].code == ANIGIF_DECODE_END)
            {
                info->done = 1;
                break;
            }
        }
        if(!info->done)
        {
            if(info->isRGB)
            {
                anigif_updatebuffer(info);
            }
            info->frame++;
        }
    }
    return info->done;
}


s_screen *anigif_getbuffer(anigif_info *info)
{
    if(!info) return NULL;
    s_screen *buffer = info->isRGB ? info->backbuffer : info->gifbuffer[0];
    if(buffer)
    {
        buffer->palette = info->isRGB ? NULL : (info->info[0].local_pal ? info->info[0].local_pal : info->info[0].global_pal);
    }
    return buffer;
}


