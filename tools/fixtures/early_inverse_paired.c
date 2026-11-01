/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me>
 * Source geometry and candidate execute with the same host floating-point
 * rules. Pixel, palette and blend expectations use an independent adapter.
 */
@HELPERS@
@REFERENCE@
struct geometry {int x,y,scalex,scaley,flipx,flipy,shiftx,angle,cx,cy,ox,oy;};
static const struct geometry geometries[]={@GEOMETRIES@};
struct triangle_case {int count;vert2d vertices[6];};
static const struct triangle_case triangles[]={@TRIANGLES@};
static unsigned char map8[256],alpha8[MAX_BLENDINGS][65536];
static unsigned short map16[256];
static unsigned map32[256];
#define MIX(n) \
static unsigned short mix16_##n(unsigned short a,unsigned short b){return (unsigned short)(a+3U*b+17U*n);} \
static unsigned mix32_##n(unsigned a,unsigned b){return a+3U*b+17U*n;}
MIX(1) MIX(2) MIX(3) MIX(4) MIX(5) MIX(6)
#undef MIX
static void providers(void)
{
    blend16fp p16[]={mix16_1,mix16_2,mix16_3,mix16_4,mix16_5,mix16_6};
    blend32fp p32[]={mix32_1,mix32_2,mix32_3,mix32_4,mix32_5,mix32_6};
    CHECK(MAX_BLENDINGS==6);
    for(unsigned i=0;i<256;i++) {
        map8[i]=(i*5+3)&255;map16[i]=i*5+3;map32[i]=i*5+3;
    }
    for(unsigned b=0;b<MAX_BLENDINGS;b++) {
        blendfunctions16[b]=p16[b];blendfunctions32[b]=p32[b];blendtables[b]=alpha8[b];
        for(unsigned i=0;i<65536;i++)alpha8[b][i]=((i>>8)+3*(i&255)+17*(b+1))&255;
    }
}
static void background(s_screen *s)
{
    for(int i=0;i<s->width*s->height;i++)put(s,i,17);
}
static void style(s_drawmethod *method,int format,int mode)
{
    if(mode==1 || mode==4 || mode==5 || mode==7)method->fillcolor=7;
    if(mode==2 || mode==5)method->alpha=1;
    if(mode==4 || mode==6)method->alpha=6;
    if(mode==3 || mode==5 || mode==6)
        method->table=format==PIXEL_8?map8:format==PIXEL_16?(unsigned char*)map16:(unsigned char*)map32;
    if(mode==7)method->transbg=1;
}
static void compare(s_screen *actual,s_screen *expected,unsigned geometry,int mode,int source,int hole)
{
    for(int i=0;i<actual->width*actual->height;i++)if(get(actual,i)!=get(expected,i)) {
        fprintf(stderr,"revision=%u geometry=%u mode=%d source=%d hole=%d format=%d pixel=%d got=%u expected=%u\n",
                obor_profile_build,geometry,mode,source,hole,actual->pixelformat,i,get(actual,i),get(expected,i));
        abort();
    }
}
static void paired(int revision,int epoch)
{
    int formats[]={PIXEL_8,PIXEL_16,PIXEL_32};
    obor_profile_build=revision;
    for(unsigned f=0;f<3;f++)for(int type=0;type<3;type++)for(int hole=0;hole<2;hole++) {
        int format=formats[f];
        s_screen *source=screen(type==2?PIXEL_x8:format,2,2);
        s_screen *actual=screen(format,12,12),*expected=screen(format,12,12);
        s_sprite *frame=sprite(format,1);
        gfx_entry entry={0};
        unsigned char *line=(unsigned char*)frame->data+frame->data[0];
        source->palette=calloc(256,pixelbytes[format]);CHECK(source->palette);
        for(int i=0;i<4;i++) {
            reference_values[i]=hole && !i?0:(unsigned)(i+1);
            if(type==2)source->data[i]=(unsigned char)reference_values[i];
            else put(source,i,reference_values[i]);
        }
        for(unsigned i=0;i<256;i++) {
            if(format==PIXEL_8)source->palette[i]=i;
            else if(format==PIXEL_16)((unsigned short*)source->palette)[i]=i;
            else ((unsigned*)source->palette)[i]=i;
        }
        if(hole){line[0]=1;line[1]=1;line[2]=2;line[3]=255;}
        entry.type=type==1?gfx_sprite:gfx_screen;
        if(type==1)entry.sprite=frame;else entry.screen=source;
        for(unsigned g=0;g<sizeof(geometries)/sizeof(geometries[0]);g++)for(int mode=0;mode<8;mode++) {
            const struct geometry *c=geometries+g;
            s_drawmethod method={0};
            method.flag=1;method.scalex=c->scalex;method.scaley=c->scaley;
            method.flipx=c->flipx;method.flipy=c->flipy;method.shiftx=c->shiftx;
            method.rotate=c->angle;method.centerx=c->cx;method.centery=c->cy;
            style(&method,format,mode);
            background(actual);background(expected);
            if(c->angle) {
                gfx_draw_rotate(actual,&entry,c->x,c->y,c->ox,c->oy,&method);
                if(epoch)reference_rotate_1(expected,&entry,c->x,c->y,c->ox,c->oy,&method);
                else reference_rotate_0(expected,&entry,c->x,c->y,c->ox,c->oy,&method);
            } else {
                gfx_draw_scale(actual,&entry,c->x,c->y,c->ox,c->oy,&method);
                if(epoch)reference_scale_1(expected,&entry,c->x,c->y,c->ox,c->oy,&method);
                else reference_scale_0(expected,&entry,c->x,c->y,c->ox,c->oy,&method);
            }
            compare(actual,expected,g,mode,type,hole);
        }
        for(unsigned g=0;g<sizeof(triangles)/sizeof(triangles[0]);g++)for(int mode=0;mode<8;mode++) {
            vert2d vertices[6],control_vertices[6];
            s_drawmethod method={0};method.flag=1;method.scalex=method.scaley=256;
            style(&method,format,mode);
            memcpy(vertices,triangles[g].vertices,sizeof(vertices));
            memcpy(control_vertices,vertices,sizeof(vertices));
            background(actual);background(expected);
            obor_transform_triangle(vertices,actual,&entry,&method,triangles[g].count);
            reference_triangle(control_vertices,expected,&entry,&method,triangles[g].count);
            compare(actual,expected,(unsigned)(1000+g),mode,type,hole);
            CHECK(!memcmp(vertices,control_vertices,sizeof(vertices)));
        }
        free(source->palette);free(frame->palette);free(frame);
        free(expected);free(actual);free(source);
    }
}
@PARENTS@
int main(void)
{
    providers();
    @CHECKS@
    @PARENT_CHECKS@
    puts("inverse_transform_paired=1");
    return 0;
}
