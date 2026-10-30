"""Exercise complete early sprite/triangle units and their script entry points.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from test_historical_player import function


def render_early_triangle(engine, fixture):
    if type(fixture['vertex_capacity']) is not int or not 4 <= fixture['vertex_capacity'] <= 4096:
        raise ValueError('Bounded source-derived vertex capacity required')
    rows = fixture['sources']
    if not rows or len(rows) > 128 or len({r['revision'] for r in rows}) != len(rows):
        raise ValueError('Unique bounded historical contexts required')
    for row in rows:
        if (type(row['revision']) is not int or not 0 < row['revision'] <= 0xffffffff or
                any(type(row[k]) is not bool for k in ('triangle_route', 'triangle_api'))):
            raise ValueError('Explicit source-derived route and API availability required')
        for name in ('width_after_clear', 'shift_aware'):
            if row[name] is not None and type(row[name]) is not bool:
                raise ValueError('Explicit scanline domains or an absent route required')
            if (row[name] is None) != row['triangle_route']:
                raise ValueError('Scanline domains must match actual source reachability')
    checks = '\n'.join('check(%d,%d,%d,%d,%d);' % (r['revision'], r['triangle_route'], r['triangle_api'],
                       -1 if r['width_after_clear'] is None else r['width_after_clear'],
                       -1 if r['shift_aware'] is None else r['shift_aware'])
                       for r in rows)
    cases = []
    for row in fixture['geometry']:
        keys = ['x', 'y', 'scalex', 'scaley', 'flipx', 'flipy', 'shiftx', 'rotate',
                'centerx', 'centery', 'frame_centerx', 'frame_centery']
        if (set(row) != set(keys) | {'vertices'} or
                any(type(row[k]) is not int or not -1024 <= row[k] <= 1024 for k in keys) or
                not 0 <= row['rotate'] < 360 or not 0 < row['scalex'] <= 512 or
                not 0 < row['scaley'] <= 512 or row['flipx'] not in (0, 1) or row['flipy'] not in (0, 1) or
                len(row['vertices']) != 4 or any(len(v) != 4 or any(type(x) is not int or
                    not -4096 <= x <= 4096 for x in v) for v in row['vertices'])):
            raise ValueError('Finite geometry and complete source-derived vertex expectations required')
        cases.append('{' + ','.join(str(row[k]) for k in keys) + ',{' +
                     ','.join('{' + ','.join(map(str, v)) + '}' for v in row['vertices']) + '}}')
    if not 1 <= len(cases) <= 128:
        raise ValueError('Bounded geometry case inventory required')
    source = (engine / 'openborscript.c').read_text()
    storage = re.search(r'(?m)^static[ \t]+gfx_entry[ \t]+texture;\s*'
                        r'#define[ \t]+vert_buf_size[ \t]+[0-9]+\s*'
                        r'static[ \t]+vert2d[ \t]+verts\[vert_buf_size\];', source)
    if storage is None:
        raise ValueError('Actual texture and vertex storage declarations required')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    methods = '\n'.join(function(source, n) for n in
                        ['Script_GetFunctionName', 'Script_LoadSystemFunctions'])
    callbacks = ['openbor_setvertex', 'openbor_settexture', 'openbor_trianglelist']
    symbols = sorted(set(re.findall(r'\(void\*\)\s*(\w+)', methods)))
    if not symbols or len(symbols) > 512 or not set(callbacks) <= set(symbols):
        raise ValueError('Complete bounded script registry required')
    stubs = '\n'.join('static void ' + name + '(void){}' for name in symbols if name not in callbacks)
    callback_source = '\n'.join(function(source, n) for n in callbacks)
    variants = '\n'.join(function(variant, n) for n in
                         ['ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue'])
    triangle = (engine / 'source/gamelib/triangle.c').read_text()
    # Keep complete units together while giving their file-local names distinct identities.
    for name in ['remapcolor', 'blendcolor', 'blendfillcolor', 'draw_triangle_list']:
        triangle = re.sub(r'\b' + name + r'\b', 'triangle_' + name, triangle)
    triangle = re.sub(r'(?<!->)(?<!\.)\bfillcolor\b', 'triangle_fillcolor', triangle)
    code = r'''
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "source/scriptlib/ScriptVariant.h"
@TRIANGLE_UNIT@
#include "source/gamelib/spritef.c"
#undef printf
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"triangle contract revision=%u line=%d: %s\n",obor_profile_build,__LINE__,#c);abort();}}while(0)
uint32_t obor_profile_build;
void writeToLogFile(const char *format,...) {(void)format;}
static unsigned triangle_calls;
static vert2d observed[4];
void draw_triangle_list(vert2d *vertices,s_screen *dest,gfx_entry *src,s_drawmethod *method,int count){
 assert(count>0);++triangle_calls;
 for(int i=0;i<4 && i<count+2;++i)observed[i]=vertices[i];
 triangle_draw_triangle_list(vertices,dest,src,method,count);
}
static int theFunctionList;
static unsigned registered;
HRESULT openbor_setvertex(ScriptVariant **args,ScriptVariant **out,int count);
HRESULT openbor_settexture(ScriptVariant **args,ScriptVariant **out,int count);
HRESULT openbor_trianglelist(ScriptVariant **args,ScriptVariant **out,int count);
static void List_Reset(int *list){assert(list==&theFunctionList);registered=0;}
static void List_InsertAfter(int *list,void *callback,const char *name){
 assert(list==&theFunctionList && callback);
 if(!strcmp(name,"setvertex")){assert(callback==(void*)openbor_setvertex);registered|=1;}
 if(!strcmp(name,"settexture")){assert(callback==(void*)openbor_settexture);registered|=2;}
 if(!strcmp(name,"trianglelist")){assert(callback==(void*)openbor_trianglelist);registered|=4;}
}
@VERTEX_STORAGE@
s_drawmethod drawmethod;
s_screen *vscreen;
CHAR *StrCache_Get(int index){assert(index==0);return (CHAR*)"0";}
void StrCache_Collect(int index){assert(index==0);}
int StrCache_Pop(void){abort();}
@VARIANTS@
@STUBS@
#define printf writeToLogFile
@CALLBACKS@
@METHODS@
#undef printf
struct geometry_case {
 int x,y,scalex,scaley,flipx,flipy,shiftx,rotate,centerx,centery,frame_centerx,frame_centery;
 vert2d vertices[4];
};
static const struct geometry_case geometries[]={@GEOMETRY@};
static unsigned short palette16[256],override16[256];
static unsigned palette32[256],override32[256];
static unsigned char remap[256],blend[65536];
static unsigned blend_calls;
static unsigned short xor16(unsigned short a,unsigned short b){++blend_calls;return a^b;}
static unsigned xor32(unsigned a,unsigned b){++blend_calls;return a^b;}
static unsigned pixel(s_screen *s,int x,int y){
 int i=x+y*s->width;
 if(s->pixelformat==PIXEL_8)return s->data[i];
 if(s->pixelformat==PIXEL_16)return ((unsigned short*)s->data)[i];
 assert(s->pixelformat==PIXEL_32);return ((unsigned*)s->data)[i];
}
static void put(s_screen *s,int x,int y,unsigned value){
 int i=x+y*s->width;
 if(s->pixelformat==PIXEL_8)s->data[i]=value;
 else if(s->pixelformat==PIXEL_16)((unsigned short*)s->data)[i]=value;
 else {assert(s->pixelformat==PIXEL_32);((unsigned*)s->data)[i]=value;}
}
static s_screen *screen(int format,int width,int height,unsigned value){
 s_screen *s=calloc(1,sizeof(*s)+(size_t)width*height*pixelbytes[format]);assert(s);
 s->pixelformat=format;s->width=width;s->height=height;
 for(int y=0;y<height;++y)for(int x=0;x<width;++x)put(s,x,y,value);
 return s;
}
static s_sprite *sprite_data(int format,int width,int height,int visible_x){
 screenformat=format;
 s_bitmap *b=calloc(1,sizeof(*b)+(size_t)width*height);assert(b);b->width=width;b->height=height;
 b->pixelformat=format==PIXEL_8?PIXEL_8:PIXEL_x8;
 b->palette=format==PIXEL_16?(unsigned char*)palette16:(unsigned char*)palette32;
 if(visible_x<0)memset(b->data,7,(size_t)width*height);
 else {assert(height==1 && visible_x<width);b->data[visible_x]=7;}
 unsigned size=encodesprite(0,0,b,NULL);assert(size>=sizeof(s_sprite));
 s_sprite *s=calloc(1,size);assert(s);assert(encodesprite(0,0,b,s)==size);
 free(b);return s;
}
static s_sprite *sprite(int format){return sprite_data(format,4,4,-1);}
static s_drawmethod method(void){
 s_drawmethod m={0};m.flag=1;m.scalex=m.scaley=256;return m;
}
static unsigned source_color(int format,int override){
 return format==PIXEL_8?(override?remap[7]:7):format==PIXEL_16?(override?override16[7]:palette16[7]):(override?override32[7]:palette32[7]);
}
static void rectangle(s_screen *s,int x0,int y0,int width,int height,unsigned foreground,unsigned background){
 for(int y=0;y<s->height;++y)for(int x=0;x<s->width;++x)
  assert(pixel(s,x,y)==(x>=x0 && x<x0+width && y>=y0 && y<y0+height?foreground:background));
}
static void sprite_routes(int triangle){
 for(int format=PIXEL_8;format<=PIXEL_32;++format){
  if(format!=PIXEL_8 && format!=PIXEL_16 && format!=PIXEL_32)continue;
  s_sprite *s=sprite(format);s_screen *dest=screen(format,24,20,3);s_drawmethod m=method();
  m.scalex=m.scaley=512;triangle_calls=0;putsprite(2,2,s,dest,&m);
  assert(triangle_calls==(unsigned)triangle);rectangle(dest,2,2,8,8,source_color(format,0),3);
  for(int y=0;y<dest->height;++y)for(int x=0;x<dest->width;++x)put(dest,x,y,3);
  m=method();triangle_calls=0;putsprite(2,2,s,dest,&m);
  assert(!triangle_calls);rectangle(dest,2,2,4,4,source_color(format,0),3);
  if(triangle)for(unsigned j=0;j<sizeof(geometries)/sizeof(*geometries);++j){
   const struct geometry_case *g=geometries+j;m=method();
   m.scalex=g->scalex;m.scaley=g->scaley;m.flipx=g->flipx;m.flipy=g->flipy;
   m.shiftx=g->shiftx;m.rotate=g->rotate;m.centerx=g->centerx;m.centery=g->centery;
   s->centerx=g->frame_centerx;s->centery=g->frame_centery;triangle_calls=0;
   putsprite(g->x,g->y,s,dest,&m);assert(triangle_calls==1);
   for(int i=0;i<4;++i){assert(observed[i].x==g->vertices[i].x && observed[i].y==g->vertices[i].y);
    assert(observed[i].tx==g->vertices[i].tx && observed[i].ty==g->vertices[i].ty);}
  }
  free(s);free(dest);
 }
}
static void triangle_pixels(void){
 for(int format=PIXEL_8;format<=PIXEL_32;++format){
  if(format!=PIXEL_8 && format!=PIXEL_16 && format!=PIXEL_32)continue;
  s_sprite *s=sprite(format);gfx_entry src={gfx_sprite,{.sprite=s}};
  vert2d v[4]={{2,2,0,0},{6,2,4,0},{2,6,0,4},{6,6,4,4}};
  for(int fill=0;fill<2;++fill)for(int table=0;table<2;++table)for(int alpha=0;alpha<2;++alpha){
   s_screen *dest=screen(format,12,10,3);s_drawmethod m=method();
   m.fillcolor=fill?23:0;m.alpha=alpha;m.table=table?(format==PIXEL_8?remap:format==PIXEL_16?(unsigned char*)override16:(unsigned char*)override32):NULL;
   blend_calls=0;draw_triangle_list(v,dest,&src,&m,2);
   unsigned color=fill?23:source_color(format,table);
   if(format==PIXEL_8 && table)color=remap[fill?23:7];
   if(alpha && !(format==PIXEL_8 && table))color^=3;
   rectangle(dest,2,2,4,4,color,3);
   if(format!=PIXEL_8)assert(blend_calls==(alpha?16u:0u));
   free(dest);
  }
  /* Repeated overlapping triangles must shade each destination only once. */
  vert2d repeated[6]={{2,2,0,0},{6,2,4,0},{2,6,0,4},{2,2,0,0},{6,2,4,0},{2,6,0,4}};
  s_screen *dest=screen(format,12,10,3);s_drawmethod m=method();m.fillcolor=23;m.alpha=1;blend_calls=0;
  draw_triangle_list(repeated,dest,&src,&m,4);
  for(int y=0;y<10;++y)for(int x=0;x<12;++x){int inside=y>=2 && y<6 && x>=2 && x<8-y;
   assert(pixel(dest,x,y)==(inside?(23u^3u):3u));}
  if(format!=PIXEL_8)assert(blend_calls==10);
  free(dest);free(s);
 }
}
static void scanline_pixels(int after_clear,int shift_aware){
 for(int format=PIXEL_8;format<=PIXEL_32;++format){
  if(format!=PIXEL_8 && format!=PIXEL_16 && format!=PIXEL_32)continue;
  s_sprite *s=sprite_data(format,295,1,294);
  for(int rotate=0;rotate<2;++rotate)for(int flip=0;flip<2;++flip){
   s_screen *dest=screen(format,rotate?12:1200,rotate?1200:4,3);s_drawmethod m=method();
   m.scalex=512;m.flipx=flip;m.rotate=rotate?90:0;
   int x=rotate?10:(flip?1000:0),y=rotate?(flip?1000:2):1;
   putsprite(x,y,s,dest,&m);
   int displacement=after_clear?588:80;
   int first=rotate?y+(flip?-displacement:displacement):x+(flip?-displacement:displacement);
   int perpendicular=rotate?(flip?9:10):1;
   for(int cy=0;cy<dest->height;++cy)for(int cx=0;cx<dest->width;++cx){
    int along=rotate?cy:cx,cross=rotate?cx:cy;
    int visible=cross==perpendicular && (along==first || along==first+(flip?-1:1));
    assert(pixel(dest,cx,cy)==(visible?source_color(format,0):3));
   }
   free(dest);
  }
  free(s);s=sprite_data(format,2,2,-1);
  for(int flip=0;flip<2;++flip){
   s_screen *dest=screen(format,12,6,3);s_drawmethod m=method();
   m.scaley=512;m.shiftx=-256;m.flipx=flip;
   putsprite(flip?14:12,0,s,dest,&m);
   for(int y=0;y<6;++y)for(int x=0;x<12;++x){
    int first=(flip?14:12)-y;
    int visible=shift_aware && y<4 && (x==first || x==first+(flip?-1:1));
    assert(pixel(dest,x,y)==(visible?source_color(format,0):3));
   }
   free(dest);
  }
  free(s);
 }
}
static void script_entries(int available){
 Script_LoadSystemFunctions();assert(registered==(available?7u:0u));
 assert(!strcmp(Script_GetFunctionName((void*)openbor_setvertex),available?"setvertex":"<unknown function>"));
 assert(!strcmp(Script_GetFunctionName((void*)openbor_settexture),available?"settexture":"<unknown function>"));
 assert(!strcmp(Script_GetFunctionName((void*)openbor_trianglelist),available?"trianglelist":"<unknown function>"));
 if(!available)return;
 assert(vert_buf_size==@VERTEX_CAPACITY@);
 ScriptVariant values[5],*args[5],*out=&values[0];memset(values,0,sizeof(values));
 for(int i=0;i<5;++i){args[i]=values+i;values[i].vt=VT_INTEGER;}
 values[0].lVal=0;values[1].lVal=2;values[2].lVal=3;values[3].lVal=1;values[4].lVal=2;
 assert(openbor_setvertex(args,&out,5)==S_OK && !out);
 assert(verts[0].x==2 && verts[0].y==3 && verts[0].tx==1 && verts[0].ty==2);
 values[0].lVal=vert_buf_size-1;values[1].lVal=-2;
 assert(openbor_setvertex(args,&out,5)==S_OK && !out && verts[vert_buf_size-1].x==-2);
 values[0].lVal=0;values[1].lVal=2;
 s_screen *src=screen(PIXEL_8,4,4,7);vscreen=screen(PIXEL_8,12,10,3);
 values[0].vt=VT_PTR;values[0].ptrVal=src;values[1].lVal=0;
 assert(openbor_settexture(args,&out,2)==S_OK && !out && texture.type==gfx_screen && texture.screen==src);
 vert2d quad[4]={{2,2,0,0},{6,2,4,0},{2,6,0,4},{6,6,4,4}};memcpy(verts,quad,sizeof(quad));
 drawmethod=method();values[0].ptrVal=vscreen;values[1].lVal=0;values[2].lVal=2;triangle_calls=0;
 assert(openbor_trianglelist(args,&out,3)==S_OK && !out && triangle_calls==1);rectangle(vscreen,2,2,4,4,7,3);
 values[2].lVal=0;triangle_calls=0;assert(openbor_trianglelist(args,&out,3)==S_OK && !out && !triangle_calls);
 free(src);free(vscreen);vscreen=NULL;
}
static void check(unsigned revision,int triangle,int api,int after_clear,int shift_aware){
 obor_profile_build=revision;sprite_routes(triangle);script_entries(api);
 if(api)triangle_pixels();
 if(!triangle)scanline_pixels(after_clear,shift_aware);
}
int main(void){
 assert(sizeof(LONG)==4);
 for(int i=0;i<256;++i){palette16[i]=(unsigned short)(i*257);override16[i]=(unsigned short)(i*129);
  palette32[i]=(unsigned)i*0x010101u;override32[i]=(unsigned)i*0x000102u;remap[i]=(unsigned char)(i^90);}
 for(int a=0;a<256;++a)for(int b=0;b<256;++b)blend[a*256+b]=(unsigned char)(a^b);
 blendtables[0]=blend;blendfunctions16[0]=xor16;blendfunctions32[0]=xor32;
 @CHECKS@
 puts("early_triangle=1");return 0;
}
'''
    for key, value in dict(VERTEX_STORAGE=storage[0], VERTEX_CAPACITY=str(fixture['vertex_capacity']),
                           TRIANGLE_UNIT=triangle, VARIANTS=variants, STUBS=stubs, CALLBACKS=callback_source,
                           METHODS=methods, GEOMETRY=','.join(cases), CHECKS=checks).items():
        code = code.replace('@' + key + '@', value)
    return code
