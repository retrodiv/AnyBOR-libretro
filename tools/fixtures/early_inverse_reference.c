/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Independent coordinate-to-colour adapter. Original geometry bodies are
 * inserted separately with their own upstream notices and source identities.
 */
extern const double sin_table[],cos_table[];
static int reference_sw,reference_sh,reference_dw,reference_dh;
static const s_drawmethod *reference_method;
static unsigned reference_values[4];
#ifdef REFERENCE_BOUNDED_PIXELS
static unsigned reference_outside;
#endif
static void reference_init(s_screen *dest,gfx_entry *src,s_drawmethod *method)
{
    reference_dw=dest->width;reference_dh=dest->height;
    reference_sw=src->type==gfx_sprite?src->sprite->width:src->screen->width;
    reference_sh=src->type==gfx_sprite?src->sprite->height:src->screen->height;
    reference_method=method;
}
static void reference_pixel(s_screen *dest,gfx_entry *src,int x,int y,int sx,int sy)
{
    const s_drawmethod *m=reference_method;
    unsigned colour,mask,fill=m->fillcolor;
    int index;
#ifdef REFERENCE_BOUNDED_PIXELS
    if(x<0 || x>=dest->width || y<0 || y>=dest->height) {
        ++reference_outside;return;
    }
    if(src->type==gfx_sprite) {
        if(sx<0 || sy<0 || sy>=reference_sh || sx>=reference_sw)return;
    }
    index=sx+sy*reference_sw;
    if(index<0 || index>=reference_sw*reference_sh) {
        ++reference_outside;return;
    }
#else
    CHECK(x>=0 && x<dest->width && y>=0 && y<dest->height);
    CHECK(sx>=0 && sy>=0);
    if(src->type==gfx_sprite) {
        CHECK(sy<reference_sh);
        if(sx>=reference_sw)return;
    }
    index=sx+sy*reference_sw;
    CHECK(index>=0 && index<reference_sw*reference_sh);
#endif
    CHECK(reference_sw*reference_sh==4);
    colour=reference_values[index];
    if((src->type==gfx_sprite || m->transbg) && !colour)return;
    if(dest->pixelformat==PIXEL_8) {
        fill&=255;
        if(fill)colour=fill;
        if(m->table)colour=(colour*5+3)&255;
        else if(m->alpha>0)colour=(colour+3*get(dest,x+y*dest->width)+m->alpha*17)&255;
    } else {
        if(fill)colour=fill;
        else if(m->table && (src->type==gfx_sprite || src->screen->pixelformat==PIXEL_x8))
            colour=colour*5+3;
        if(m->alpha>0)colour=colour+3*get(dest,x+y*dest->width)+m->alpha*17;
        mask=dest->pixelformat==PIXEL_16?65535:0xffffffffU;
        colour&=mask;
    }
    put(dest,x+y*dest->width,colour);
}
#define REF_MAX(a,b) (((a)>(b))?(a):(b))
#define REF_MIN(a,b) (((a)<(b))?(a):(b))
@MATH_BODIES@
#undef REF_MAX
#undef REF_MIN
