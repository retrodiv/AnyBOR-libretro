/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Parent expectations follow the source-owned non-water route. Common
 * geometry uses the separately compiled reference bodies; the plain path
 * has a small independent pixel oracle, including remap followed by blend.
 */
#include "sprite.h"
int screenformat;
static void plain_expected(s_screen *dest,s_sprite *frame,int x,int y,int flip,
                           const s_drawmethod *method)
{
    for(int sy=0;sy<2;sy++)for(int sx=0;sx<2;sx++) {
        unsigned colour=reference_values[sx+2*sy];
        if(!colour)continue;
        int dx=flip?x+frame->centerx-1-sx:x-frame->centerx+sx;
        int dy=y-frame->centery+sy;
        if(dx<0 || dx>=dest->width || dy<0 || dy>=dest->height)continue;
        if(method && method->table) {
            colour=colour*5+3;
            if(dest->pixelformat==PIXEL_8)colour&=255;
        }
        if(method && method->alpha>0)colour+=3*get(dest,dx+dy*dest->width)+method->alpha*17;
        if(dest->pixelformat==PIXEL_8)colour&=255;
        else if(dest->pixelformat==PIXEL_16)colour&=65535;
        put(dest,dx+dy*dest->width,colour);
    }
}
static void parent(int revision,int inverse,int epoch)
{
    int formats[]={PIXEL_8,PIXEL_16,PIXEL_32};
    obor_profile_build=revision;
    for(unsigned f=0;f<3;f++)for(int hole=0;hole<2;hole++) {
        int format=formats[f];screenformat=format;
        s_sprite *frame=sprite(format,1);
        s_screen *actual=screen(format,12,12),*expected=screen(format,12,12);
        gfx_entry entry={0};entry.type=gfx_sprite;entry.sprite=frame;
        unsigned char *line=(unsigned char*)frame->data+frame->data[0];
        if(hole){line[0]=1;line[1]=1;line[2]=2;line[3]=255;}
        for(int i=0;i<4;i++)reference_values[i]=hole && !i?0:(unsigned)(i+1);
        if(inverse)for(unsigned g=0;g<sizeof(geometries)/sizeof(*geometries);g++)
            for(int mode=0;mode<8;mode++)for(int flag=0;flag<2;flag++) {
                const struct geometry *c=geometries+g;
                s_drawmethod method={0},before;
                method.flag=flag;method.scalex=c->scalex;method.scaley=c->scaley;
                method.flipx=c->flipx;method.flipy=c->flipy;method.shiftx=c->shiftx;
                method.rotate=c->angle;method.centerx=c->cx;method.centery=c->cy;
                style(&method,format,mode);memcpy(&before,&method,sizeof(method));
                frame->centerx=c->ox;frame->centery=c->oy;
                background(actual);background(expected);
                putsprite(c->x,c->y,frame,actual,&method);
                CHECK(!memcmp(&before,&method,sizeof(method)));
                int cx=frame->centerx+(epoch?0:method.centerx);
                int cy=frame->centery+(epoch?0:method.centery);
                if(!flag)plain_expected(expected,frame,c->x,c->y,0,NULL);
                else if(c->angle) {
                    if(epoch)reference_rotate_1(expected,&entry,c->x,c->y,cx,cy,&method);
                    else reference_rotate_0(expected,&entry,c->x,c->y,cx,cy,&method);
                } else {
                    if(epoch)reference_scale_1(expected,&entry,c->x,c->y,cx,cy,&method);
                    else reference_scale_0(expected,&entry,c->x,c->y,cx,cy,&method);
                }
                compare(actual,expected,g,mode,10+flag,hole);
            }
        for(int flip=0;flip<2;flip++)for(int flag=0;flag<2;flag++)for(int mode=0;mode<7;mode++) {
            if(mode!=0 && mode!=2 && mode!=3 && mode!=6)continue;
            if(!inverse && flag)continue;
            s_drawmethod method={0},before;
            method.flag=flag;method.scalex=method.scaley=256;method.flipx=flip;
            style(&method,format,mode);memcpy(&before,&method,sizeof(method));
            frame->centerx=frame->centery=1;
            background(actual);background(expected);
            putsprite(5,5,frame,actual,&method);
            if(inverse)CHECK(!memcmp(&before,&method,sizeof(method)));
            plain_expected(expected,frame,5,5,flag?flip:0,flag?&method:NULL);
            compare(actual,expected,2000,mode,flip,hole);
        }
        s_drawmethod zero={0};zero.scaley=512;
        background(actual);background(expected);
        putsprite(5,5,frame,actual,&zero);
        plain_expected(expected,frame,5,5,0,NULL);
        compare(actual,expected,2001,0,0,hole);
        zero.flag=1;background(actual);background(expected);
        putsprite(5,5,frame,actual,&zero);
        compare(actual,expected,2003,0,0,hole);
        background(actual);background(expected);
        putsprite(5,5,frame,actual,NULL);
        plain_expected(expected,frame,5,5,0,NULL);
        compare(actual,expected,2002,0,0,hole);
        free(actual);free(expected);free(frame->palette);free(frame);
    }
}
