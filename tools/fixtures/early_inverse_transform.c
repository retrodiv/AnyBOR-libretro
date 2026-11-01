/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Exact half-step samples isolate common inverse mapping from rounding cases.
 * Contexts and source-owned vectors are supplied by private JSON evidence.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include "globals.h"
#include "types.h"
#include "transform.h"
#define CHECK(v) do { if(!(v)) {fprintf(stderr,"inverse check line %d: %s\n",__LINE__,#v);abort();} } while(0)
uint32_t obor_profile_build;
int pixelbytes[]={1,1,2,3,4};
blend16fp blendfunctions16[MAX_BLENDINGS];
blend32fp blendfunctions32[MAX_BLENDINGS];
unsigned char *blendtables[MAX_BLENDINGS];
@VECTORS@
static jmp_buf stop_context;
static int expect_stop, diagnostic_line, stopped;
void obor_port_assert(int value,const char *expression,const char *function,
                      const char *file,int line)
{
    if(value) return;
    CHECK(expect_stop);
    CHECK(!strcmp(expression,"sizeof(s_screen)!=sizeof(s_bitmap)"));
    CHECK(!strcmp(function,"draw_pixel_bitmap"));
    CHECK(!strcmp(file,"source/gamelib/transform.c"));
    CHECK(line==diagnostic_line);
    stopped=1;
    longjmp(stop_context,1);
}
static s_screen *screen(int format,int width,int height)
{
    s_screen *s=calloc(1,sizeof(*s)+(size_t)width*height*pixelbytes[format]);
    CHECK(s);s->pixelformat=format;s->width=width;s->height=height;
    return s;
}
static unsigned get(s_screen *s,int i)
{
    if(s->pixelformat==PIXEL_8) return s->data[i];
    if(s->pixelformat==PIXEL_16) return ((unsigned short*)s->data)[i];
    CHECK(s->pixelformat==PIXEL_32);return ((unsigned*)s->data)[i];
}
static void put(s_screen *s,int i,unsigned value)
{
    if(s->pixelformat==PIXEL_8)s->data[i]=value;
    else if(s->pixelformat==PIXEL_16)((unsigned short*)s->data)[i]=value;
    else {CHECK(s->pixelformat==PIXEL_32);((unsigned*)s->data)[i]=value;}
}
static void pixels(s_screen *s,const unsigned *expected)
{
    for(int i=0;i<16;i++) if(get(s,i)!=expected[i]) {
        fprintf(stderr,"revision=%u format=%d pixel=%d got=%u expected=%u\n",
                obor_profile_build,s->pixelformat,i,get(s,i),expected[i]);
        abort();
    }
}
static void clear(s_screen *s)
{
    memset(s->data,0,(size_t)s->width*s->height*pixelbytes[(int)s->pixelformat]);
}
static s_sprite *sprite(int format,int first)
{
    s_sprite *s=calloc(1,sizeof(*s)+32);
    CHECK(s);s->width=s->height=2;s->pixelformat=format==PIXEL_8?PIXEL_8:PIXEL_x8;
    s->palette=calloc(256,pixelbytes[format]);CHECK(s->palette);
    for(unsigned i=0;i<256;i++) {
        if(format==PIXEL_8)s->palette[i]=i;
        else if(format==PIXEL_16)((unsigned short*)s->palette)[i]=i;
        else ((unsigned*)s->palette)[i]=i;
    }
    int *rows=s->data;
    unsigned char *data=(unsigned char*)(rows+2);
    unsigned char values[2][5]={{0,2,first,first+1,255},{0,2,first+2,first+3,255}};
    if(first==128) {values[1][2]=254;values[1][3]=255;}
    for(int y=0;y<2;y++) {
        rows[y]=(int)(data-(unsigned char*)(rows+y));
        memcpy(data,values[y],5);data+=5;
    }
    return s;
}
static void check(int revision,int center_added,int bitmap_present,int own_line)
{
    static const unsigned scaled[]={1,1,1,2,1,1,1,2,1,1,1,2,3,3,3,4};
    static const unsigned rotated[]={1,1,2,2,1,1,2,2,3,3,4,4,3,3,4,4};
    static const unsigned shifted[]={1,2,0,0,3,4,0,0,0,0,0,0,0,0,0,0};
    static const unsigned rotate_shifted[]={4,4,0,0,4,4,0,0,0,0,0,0,0,0,0,0};
    static const unsigned high[]={128,128,128,129,128,128,128,129,128,128,128,129,254,254,254,255};
    static const unsigned hole_fill[]={0,0,0,7,0,0,0,7,0,0,0,7,7,7,7,7};
    static const unsigned horizontal_shift[]={1,2,0,0,1,2,0,0,1,2,0,0,3,4,0,0};
    static const unsigned wide_window[]={7,7,7,7,0,0,0,0,0,0,0,0,0,0,0,0};
    static const unsigned empty[16]={0};
    int formats[]={PIXEL_8,PIXEL_16,PIXEL_32};
    obor_profile_build=revision;
    for(unsigned f=0;f<sizeof(formats)/sizeof(formats[0]);f++) {
        s_screen *src=screen(formats[f],2,2),*dest=screen(formats[f],4,4);
        gfx_entry entry={0};s_drawmethod method={0};
        for(int i=0;i<4;i++)put(src,i,i+1);
        entry.type=gfx_screen;entry.screen=src;
        method.flag=1;method.scalex=method.scaley=512;
        gfx_draw_scale(dest,&entry,0,0,0,0,&method);pixels(dest,scaled);
        clear(dest);
        gfx_draw_rotate(dest,&entry,0,0,0,0,&method);pixels(dest,rotated);
        clear(dest);method.centerx=method.centery=1;
        gfx_draw_scale(dest,&entry,0,0,0,0,&method);
        pixels(dest,center_added?shifted:scaled);
        clear(dest);
        gfx_draw_rotate(dest,&entry,0,0,0,0,&method);
        pixels(dest,center_added?rotate_shifted:rotated);
        method.centerx=method.centery=0;clear(dest);
        method.scalex=0;
        gfx_draw_scale(dest,&entry,0,0,0,0,&method);pixels(dest,empty);
        gfx_draw_rotate(dest,&entry,0,0,0,0,&method);pixels(dest,empty);
        method.scalex=512;
        /* Candidate-only range controls have no unsafe original execution. */
        method.rotate=-1;
        gfx_draw_rotate(dest,&entry,0,0,0,0,&method);pixels(dest,empty);
        method.rotate=360;
        gfx_draw_rotate(dest,&entry,0,0,0,0,&method);pixels(dest,empty);
        method.rotate=0;
        gfx_draw_rotate(dest,&entry,0,0,INT_MIN,0,&method);pixels(dest,empty);
        method.centerx=INT_MAX;
        gfx_draw_scale(dest,&entry,0,0,1,0,&method);
        pixels(dest,center_added?empty:horizontal_shift);
        method.centerx=0;clear(dest);
        s_screen *wide=screen(formats[f],512,1);
        for(int i=0;i<512;i++)put(wide,i,7);
        entry.screen=wide;method.scalex=INT_MAX;method.scaley=256;
        gfx_draw_scale(dest,&entry,0,0,0,0,&method);pixels(dest,wide_window);
        free(wide);entry.screen=src;clear(dest);
        method.scalex=method.scaley=512;
        /* A bitmap has the same layout, but remains a distinct object type.
         * The preserved original condition is literal, not inverted by intent. */
        s_bitmap *bitmap=calloc(1,sizeof(*bitmap)+4*pixelbytes[formats[f]]);
        CHECK(bitmap);bitmap->pixelformat=formats[f];bitmap->width=bitmap->height=2;
        memcpy(bitmap->data,src->data,4*pixelbytes[formats[f]]);
        entry.type=gfx_bitmap;entry.bitmap=bitmap;stopped=0;
        diagnostic_line=own_line;
#ifdef NDEBUG
        expect_stop=0;
        gfx_draw_scale(dest,&entry,0,0,0,0,&method);
        CHECK(!stopped);pixels(dest,bitmap_present?scaled:empty);
#else
        expect_stop=bitmap_present;
        if(!setjmp(stop_context))gfx_draw_scale(dest,&entry,0,0,0,0,&method);
        CHECK(stopped==bitmap_present);expect_stop=0;pixels(dest,empty);
#endif
        free(bitmap);clear(dest);
        s_sprite *image=sprite(formats[f],1);
        entry.type=gfx_sprite;entry.sprite=image;
        gfx_draw_scale(dest,&entry,0,0,0,0,&method);pixels(dest,scaled);
        clear(dest);
        gfx_draw_rotate(dest,&entry,0,0,0,0,&method);pixels(dest,rotated);
        /* The first run becomes one transparent pixel and one source pixel.
         * Transparency precedes fill, for all three output widths. */
        unsigned char *line=(unsigned char*)image->data+image->data[0];
        line[0]=1;line[1]=1;line[2]=2;line[3]=255;
        clear(dest);method.fillcolor=7;
        gfx_draw_scale(dest,&entry,0,0,0,0,&method);pixels(dest,hole_fill);
        method.fillcolor=0;
        free(image->palette);free(image);
        image=sprite(formats[f],128);entry.sprite=image;clear(dest);
        gfx_draw_scale(dest,&entry,0,0,0,0,&method);pixels(dest,high);
        free(image->palette);free(image);free(dest);free(src);
    }
}
int main(void)
{
    @CHECKS@
    puts("inverse_transform_halfsteps=1");
    return 0;
}
