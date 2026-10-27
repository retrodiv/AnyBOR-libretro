"""Observe bounded primitive pixels through complete native drawing units.

Inputs provide independent before/after images and native API availability.
The indexed table is an authored selector control, not a palette factory.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""


def render_primitive_raster(*, revision, method_api, channels, tint, cases, perturb_output=False):
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            any(type(v) is not bool for v in (method_api, channels, tint, perturb_output)) or
            tint and not channels or not isinstance(cases, list) or not 1 <= len(cases) <= 1024):
        raise ValueError('Explicit native revision, drawing API, fields and bounded pixel observations required')
    rows = []
    for case in cases:
        fields = {'bits', 'operation', 'width', 'height', 'coords', 'color', 'alpha',
                  'method', 'rgb', 'tint', 'before', 'expected'}
        if (not isinstance(case, dict) or set(case) != fields or type(case['bits']) is not int or
                case['bits'] not in (8, 16, 32) or case['operation'] not in ('box', 'line', 'pixel') or
                any(type(case[k]) is not int or not 1 <= case[k] <= 16 for k in ('width', 'height'))):
            raise ValueError('Explicit bounded native format, primitive and image dimensions required')
        maximum = {8: 255, 16: 65535, 32: 0xffffff}[case['bits']]
        if (not isinstance(case['coords'], list) or len(case['coords']) != 4 or
                any(type(v) is not int or not -32 <= v <= 32 for v in case['coords']) or
                type(case['color']) is not int or not 0 <= case['color'] <= maximum or
                type(case['alpha']) is not int or not 0 <= case['alpha'] <= 7 or
                type(case['method']) is not int or case['method'] not in (-1, 0, 1) or
                not isinstance(case['rgb'], list) or len(case['rgb']) != 3 or
                any(type(v) is not int or not 0 <= v <= 255 for v in case['rgb']) or
                not isinstance(case['tint'], list) or len(case['tint']) != 2 or
                any(type(v) is not int for v in case['tint']) or
                not 0 <= case['tint'][0] <= 6 or not 0 <= case['tint'][1] <= maximum or
                any(not isinstance(case[k], list) or len(case[k]) != case['width'] * case['height'] or
                    any(type(v) is not int or not 0 <= v <= maximum for v in case[k])
                    for k in ('before', 'expected'))):
            raise ValueError('Complete bounded primitive arguments and independent pixel images required')
        # Line and point controls stay inside the native valid-coordinate domain.
        # Rectangles exercise their documented clipping and empty-size behavior.
        x, y, a, b = case['coords']
        if (case['operation'] == 'pixel' and not (0 <= x < case['width'] and 0 <= y < case['height']) or
                case['operation'] == 'line' and not (0 <= x < case['width'] and 0 <= a < case['width'] and
                                                     0 <= y < case['height'] and 0 <= b < case['height'])):
            raise ValueError('Native point and line controls require valid in-image coordinates')
        scalar = [str(case[k]) for k in ('bits',)] + [str(('box', 'line', 'pixel').index(case['operation']))]
        scalar += [str(case[k]) for k in ('width', 'height', 'color', 'alpha', 'method')]
        rows.append('{' + ','.join(scalar + ['{' + ','.join(map(str, case[k])) + '}'
                                            for k in ('coords', 'rgb', 'tint', 'before', 'expected')]) + '}')
    return r'''
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "types.h"
#include "draw.h"
#undef calloc
#undef free
#undef printf
#undef assert
#ifdef NDEBUG
#error Native primitive raster assertions must remain enabled
#endif
static unsigned active_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Native primitive raster mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
struct raster_case {
 int bits,operation,width,height;unsigned color;int alpha,method,coords[4],rgb[3];
 unsigned tint[2],before[256],expected[256];
};
static const struct raster_case tests[]={@CASES@};
static void invoke(const struct raster_case *test,s_screen *screen,s_drawmethod *method){
 int x=test->coords[0],y=test->coords[1],a=test->coords[2],b=test->coords[3];
#if @METHOD_API@
 if(test->operation==0)putbox(x,y,a,b,(int)test->color,screen,method);
 else if(test->operation==1)putline(x,y,a,b,(int)test->color,screen,method);
 else putpixel((unsigned)x,(unsigned)y,(int)test->color,screen,method);
#else
 int alpha=method && method->flag?test->alpha:0;
 if(test->bits==8){
  if(test->operation==0)drawbox(x,y,a,b,(int)test->color,screen,alpha);
  else if(test->operation==1)line(x,y,a,b,(int)test->color,screen,alpha);
  else putpixel(x,y,(int)test->color,screen,alpha);
 }else if(test->bits==16){
  if(test->operation==0)drawbox16(x,y,a,b,(unsigned short)test->color,screen,alpha);
  else if(test->operation==1)line16(x,y,a,b,(unsigned short)test->color,screen,alpha);
  else putpixel16(x,y,(unsigned short)test->color,screen,alpha);
 }else{
  if(test->operation==0)drawbox32(x,y,a,b,test->color,screen,alpha);
  else if(test->operation==1)line32(x,y,a,b,test->color,screen,alpha);
  else putpixel32(x,y,test->color,screen,alpha);
 }
#endif
}
int main(void){
 enum {CAPACITY=sizeof(blendtables)/sizeof(blendtables[0])};assert(CAPACITY>=6 && CAPACITY<=16);
 unsigned char *indexed=calloc(CAPACITY,65536);assert(indexed);
 for(unsigned mode=0;mode<CAPACITY;++mode)for(unsigned front=0;front<256;++front)for(unsigned back=0;back<256;++back)
  indexed[mode*65536+(front<<8)+back]=(unsigned char)(front*3+back*5+mode+1);
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct raster_case *test=tests+active_case;size_t count=(size_t)test->width*test->height;
  int bytes=test->bits/8;size_t size=offsetof(s_screen,data)+count*(size_t)bytes;
  if(size<sizeof(s_screen))size=sizeof(s_screen);
  s_screen *screen=calloc(1,size);assert(screen);screen->magic=screen_magic;
  screen->width=test->width;screen->height=test->height;
  screen->pixelformat=test->bits==8?PIXEL_8:(test->bits==16?PIXEL_16:PIXEL_32);
  screenformat=pixelformat=screen->pixelformat;
  for(unsigned mode=0;mode<CAPACITY;++mode)blendtables[mode]=test->bits==8?indexed+mode*65536:NULL;
  for(size_t p=0;p<count;++p){
   if(bytes==1)screen->data[p]=(unsigned char)test->before[p];
   else if(bytes==2){uint16_t value=(uint16_t)test->before[p];memcpy(screen->data+p*2,&value,2);}
   else {uint32_t value=test->before[p];memcpy(screen->data+p*4,&value,4);}
  }
  s_drawmethod method;memset(&method,0,sizeof(method));method.flag=test->method==1;method.alpha=test->alpha;
#if @CHANNELS@
  method.channelr=(unsigned)test->rgb[0];method.channelg=(unsigned)test->rgb[1];method.channelb=(unsigned)test->rgb[2];
#endif
#if @TINT@
  method.tintmode=test->tint[0];method.tintcolor=test->tint[1];
#endif
  s_drawmethod before=method;invoke(test,screen,test->method<0?NULL:&method);
  assert(memcmp(&method,&before,sizeof(method))==0);
  if(@PERTURB@ && active_case==0)screen->data[0]^=1;
  for(size_t p=0;p<count;++p){
   unsigned value=0;
   if(bytes==1)value=screen->data[p];
   else if(bytes==2){uint16_t packed;memcpy(&packed,screen->data+p*2,2);value=packed;}
   else {uint32_t packed;memcpy(&packed,screen->data+p*4,4);value=packed;}
   if(value!=test->expected[p]){fprintf(stderr,"Native primitive pixel mismatch: case=%u pixel=%zu actual=%u expected=%u\n",active_case,p,value,test->expected[p]);abort();}
  }
  free(screen);
 }
 for(unsigned mode=0;mode<CAPACITY;++mode)blendtables[mode]=NULL;
 free(indexed);printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''.replace('@REVISION@', str(revision) + 'u').replace('@CASES@', ',\n'.join(rows)).replace(
        '@METHOD_API@', str(int(method_api))).replace('@CHANNELS@', str(int(channels))).replace(
        '@TINT@', str(int(tint))).replace('@PERTURB@', str(int(perturb_output)))
