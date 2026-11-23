"""Compare complete native transform geometry with finite pixel expectations.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""


def render_transform_geometry(*, revision, clipping, assert_refusal, cases, perturb_pixel=False):
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            any(type(v) is not bool for v in (clipping, assert_refusal, perturb_pixel)) or
            not isinstance(cases, list) or not 1 <= len(cases) <= 2048):
        raise ValueError('Explicit native revision, clipping context and bounded geometry cases required')
    rows = []
    for row in cases:
        if (not isinstance(row, dict) or set(row) - {'palette', 'indexed_source', 'alpha'} != {
                'operation', 'bits', 'x', 'y', 'anchor',
                'center', 'scale', 'flip', 'shift', 'angle', 'key', 'fill', 'clip', 'source', 'before', 'expected'} or
                row['operation'] not in ('scale', 'rotate', 'water') or type(row['bits']) is not int or
                row['bits'] not in (8, 16, 32) or type(row['key']) is not bool or
                type(row.get('palette', False)) is not bool or (row.get('palette') and row['bits'] == 8) or
                type(row.get('indexed_source', False)) is not bool or
                (row.get('indexed_source') and not row.get('palette')) or
                type(row.get('alpha', 0)) is not int or not 0 <= row.get('alpha', 0) <= 6 or
                (row.get('alpha') and row['bits'] == 8) or
                any(type(row[k]) is not int or not -16 <= row[k] <= 16 for k in ('x', 'y')) or
                type(row['angle']) is not int or not 0 <= row['angle'] < 360 or
                type(row['shift']) is not int or row['shift'] not in (-128, 0, 128) or
                type(row['fill']) is not int or not 0 <= row['fill'] <= 255):
            raise ValueError('Complete finite native geometry inputs required')
        source_bits = 8 if row.get('indexed_source', False) else row['bits']
        for key, length, predicate in (
                ('anchor', 2, lambda v: type(v) is int and -4 <= v <= 4),
                ('center', 2, lambda v: type(v) is int and -4 <= v <= 4),
                ('scale', 2, lambda v: type(v) is int and 64 <= v <= 1024),
                ('flip', 2, lambda v: type(v) is bool),
                ('clip', 4, lambda v: type(v) is int and 0 <= v <= 12),
                ('source', 16, lambda v: type(v) is int and 0 <= v < 1 << source_bits),
                ('before', 120, lambda v: type(v) is int and 0 <= v < 1 << row['bits']),
                ('expected', 120, lambda v: type(v) is int and 0 <= v < 1 << row['bits'])):
            if not isinstance(row[key], list) or len(row[key]) != length or not all(predicate(v) for v in row[key]):
                raise ValueError('Bounded native geometry arrays and complete pixel expectations required')
        if (not 0 <= row['clip'][0] < row['clip'][2] <= 12 or
                not 0 <= row['clip'][1] < row['clip'][3] <= 10 or
                (not clipping and row['clip'] != [0, 0, 12, 10])):
            raise ValueError('Explicit in-screen clipping domain required')
        values = [str(('scale', 'rotate', 'water').index(row['operation'])),
                  *[str(int(row[k])) for k in ('bits', 'x', 'y')],
                  str(int(row.get('palette', False))), str(source_bits), str(row.get('alpha', 0))]
        for key in ('anchor', 'center', 'scale', 'flip'):
            values.append('{' + ','.join(str(int(v)) for v in row[key]) + '}')
        values.extend(str(int(row[k])) for k in ('shift', 'angle', 'key', 'fill'))
        for key in ('clip', 'source', 'before', 'expected'):
            values.append('{' + ','.join(str(v) + 'u' for v in row[key]) + '}')
        rows.append('{' + ','.join(values) + '}')
    code = r'''
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "transform.c"
#undef calloc
#undef free
#undef printf
#undef assert
#ifdef NDEBUG
#error Native geometry assertions must remain enabled
#endif
@ASSERT_REFUSAL@
uint32_t obor_profile_build=@REVISION@;
static unsigned active_case;
#define assert(c) do{if(!(c)){fprintf(stderr,"Native geometry invariant mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
struct geometry_case {int operation,bits,x,y,palette,source_bits,alpha;
 int anchor[2],center[2],scale[2],flip[2],shift,angle,key,fill;
 unsigned clip[4],source[16],before[120],expected[120];};
static const struct geometry_case tests[]={@CASES@};
static s_screen *owned_screen(int width,int height,int bits){
 size_t bytes=offsetof(s_screen,data)+(size_t)width*height*(bits/8);
 if(bytes<sizeof(s_screen))bytes=sizeof(s_screen);
 s_screen *s=calloc(1,bytes);assert(s);s->width=width;s->height=height;
 s->pixelformat=bits==8?PIXEL_8:bits==16?PIXEL_16:PIXEL_32;s->magic=screen_magic;return s;
}
static void store_pixel(s_screen *s,int bits,unsigned index,unsigned value){
 unsigned char *data=(unsigned char*)s+offsetof(s_screen,data);
 if(bits==8)data[index]=(unsigned char)value;
 else if(bits==16)((unsigned short*)data)[index]=(unsigned short)value;
 else ((unsigned*)data)[index]=value;
}
static unsigned load_pixel(s_screen *s,int bits,unsigned index){
 unsigned char *data=(unsigned char*)s+offsetof(s_screen,data);
 return bits==8?data[index]:bits==16?((unsigned short*)data)[index]:((unsigned*)data)[index];
}
int main(void){
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct geometry_case *test=tests+active_case;
  s_screen *dest=owned_screen(12,10,test->bits),*src=owned_screen(4,4,test->source_bits);
  if(test->source_bits!=test->bits)src->pixelformat=PIXEL_x8;
  for(unsigned p=0;p<120;++p)store_pixel(dest,test->bits,p,test->before[p]);
  for(unsigned p=0;p<16;++p)store_pixel(src,test->source_bits,p,test->source[p]);
  const size_t source_bytes=(size_t)16*(test->source_bits/8);
  unsigned char original_source[64];memcpy(original_source,src->data,source_bytes);
  gfx_entry graphics;memset(&graphics,0,sizeof(graphics));graphics.screen=src;
  s_drawmethod method;memset(&method,0,sizeof(method));method.flag=test->bits>0;
  method.scalex=test->scale[0];method.scaley=test->scale[1];method.flipx=test->flip[0];method.flipy=test->flip[1];
  method.shiftx=test->shift;method.rotate=test->angle;method.transbg=test->key;method.fillcolor=(unsigned)test->fill;
  method.alpha=test->alpha;
  method.centerx=test->center[0];method.centery=test->center[1];@CLIP@
  unsigned palette[256];
  unsigned short palette16[256];
  if(test->palette && test->bits==16){
   for(unsigned p=0;p<256;++p)palette16[p]=0x1000u|p<<4;
   method.table=(unsigned char*)palette16;
  }
  else if(test->palette){
   for(unsigned p=0;p<256;++p)palette[p]=0x10000u|p<<8|p;
   method.table=(unsigned char*)palette;
  }
  method.water.wavelength=64.0f;
  method.water.watermode=1;
  unsigned char original_method[sizeof(method)];memcpy(original_method,&method,sizeof(method));
  if(test->operation==2){
   pixelformat=dest->pixelformat;
   gfx_draw_water(dest,&graphics,test->x,test->y,test->anchor[0],test->anchor[1],&method);
  }
  else if(test->operation==1)gfx_draw_rotate(dest,&graphics,test->x,test->y,test->anchor[0],test->anchor[1],&method);
  else gfx_draw_scale(dest,&graphics,test->x,test->y,test->anchor[0],test->anchor[1],&method);
  assert(!memcmp(original_source,src->data,source_bytes) && !memcmp(original_method,&method,sizeof(method)));
  if(@PERTURB@ && active_case==0)store_pixel(dest,test->bits,0,load_pixel(dest,test->bits,0)^1);
  for(unsigned p=0;p<120;++p){unsigned actual=load_pixel(dest,test->bits,p);
   if(actual!=test->expected[p]){fprintf(stderr,"Native transform geometry pixel mismatch: case=%u pixel=%u actual=%u expected=%u\n",active_case,p,actual,test->expected[p]);abort();}}
  free(src);free(dest);
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    refusal = ('''void exitIfFalse(int value,const char *assertion,const char *func,const char *file,int line){
 (void)value;(void)assertion;(void)func;(void)file;(void)line;
 fputs("Unexpected native bitmap assertion service\\n",stderr);abort();}''' if assert_refusal else '')
    clip = ('''useclip=1;clipx1=(int)test->clip[0];clipy1=(int)test->clip[1];
 clipx2=(int)test->clip[2];clipy2=(int)test->clip[3];''' if clipping else '')
    for key, value in dict(REVISION=str(revision) + 'u', CASES=',\n'.join(rows),
                           ASSERT_REFUSAL=refusal, CLIP=clip, PERTURB=str(int(perturb_pixel))).items():
        code = code.replace('@' + key + '@', value)
    return code
