"""Compare finite screen-copy pixels through complete native drawing units.

Transform services refuse calls; their pixels require a separate contract.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from native_header_fixtures import graphics_refusals

OPERATIONS = ('copy', 'opaque', 'transparent', 'remap', 'blend', 'packed', 'indexed', 'putscreen')


def render_screen_raster(*, revision, channels, tint, clipping, cases, perturb_output=False,
                         unexpected_transform=False):
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            any(type(v) is not bool for v in (channels, tint, clipping, perturb_output, unexpected_transform)) or
            tint and not channels or not isinstance(cases, list) or not 1 <= len(cases) <= 2048):
        raise ValueError('Explicit native fields and bounded screen pixel cases required')
    rows = []
    fields = {'bits', 'indexed', 'operation', 'width', 'height', 'source_width', 'source_height',
              'x', 'y', 'alpha', 'key', 'palette', 'method', 'center', 'repeat', 'span',
              'rgb', 'tint', 'clip', 'source', 'before', 'expected'}
    for case in cases:
        if (not isinstance(case, dict) or set(case) != fields or
                type(case['bits']) is not int or case['bits'] not in (8, 16, 32) or
                type(case['indexed']) is not bool or case['operation'] not in OPERATIONS or
                any(type(case[k]) is not int or not 1 <= case[k] <= 16
                    for k in ('width', 'height', 'source_width', 'source_height')) or
                any(type(case[k]) is not int or not -32 <= case[k] <= 32 for k in ('x', 'y')) or
                type(case['alpha']) is not int or not 0 <= case['alpha'] <= 7 or
                type(case['key']) is not bool or type(case['palette']) is not int or
                case['palette'] not in (0, 1, 2) or type(case['method']) is not int or
                case['method'] not in (-1, 0, 1)):
            raise ValueError('Explicit supported format, operation, geometry and native selector required')
        maximum = {8: 255, 16: 65535, 32: 0xffffff}[case['bits']]
        for name, length, low, high in [('center', 2, -8, 8), ('repeat', 2, 1, 3),
                                      ('span', 2, -8, 8), ('rgb', 3, 0, 255),
                                      ('tint', 2, 0, maximum), ('clip', 4, 0, 16)]:
            if (not isinstance(case[name], list) or len(case[name]) != length or
                    any(type(v) is not int or not low <= v <= high for v in case[name])):
                raise ValueError('Bounded complete native screen method required')
        if case['tint'][0] > 6 or not (case['clip'][0] < case['clip'][2] <= case['width'] and
                                     case['clip'][1] < case['clip'][3] <= case['height']):
            raise ValueError('Defined nonempty clipping rectangle and tint mode required')
        for name, count, limit in [('source', case['source_width'] * case['source_height'],
                                  255 if case['indexed'] else maximum),
                                 ('before', case['width'] * case['height'], maximum),
                                 ('expected', case['width'] * case['height'], maximum)]:
            if (not isinstance(case[name], list) or len(case[name]) != count or
                    any(type(v) is not int or not 0 <= v <= limit for v in case[name])):
                raise ValueError('Complete independent source, destination and expected pixels required')
        if ((case['operation'] in ('transparent', 'remap', 'blend') and case['bits'] != 8) or
                case['operation'] == 'blend' and not case['alpha'] or
                case['bits'] == 8 and case['indexed'] or
                case['operation'] == 'packed' and (case['bits'] == 8 or case['indexed']) or
                case['operation'] == 'indexed' and (case['bits'] == 8 or not case['indexed']) or
                case['operation'] in ('copy', 'opaque') and case['indexed'] or
                case['operation'] == 'copy' and (case['x'] or case['y'])):
            raise ValueError('Native operation must match its valid format and argument domain')
        scalars = [str(case[k]) for k in ('bits',)] + [str(int(case['indexed'])), str(OPERATIONS.index(case['operation']))]
        scalars += [str(case[k]) for k in ('width', 'height', 'source_width', 'source_height', 'x', 'y', 'alpha')]
        scalars += [str(int(case['key'])), str(case['palette']), str(case['method'])]
        rows.append('{' + ','.join(scalars + ['{' + ','.join(map(str, case[k])) + '}' for k in
                    ('center', 'repeat', 'span', 'rgb', 'tint', 'clip', 'source', 'before', 'expected')]) + '}')
    code = r'''
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "types.h"
#include "screen.h"
#include "transform.h"
#undef calloc
#undef free
#undef printf
#undef assert
#ifdef NDEBUG
#error Native screen assertions must remain enabled
#endif
static unsigned active_case;
#define assert(c) do{if(!(c)){fprintf(stderr,"Native screen raster mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
@REFUSALS@
#include "screen.c"
struct screen_case {
 int bits,indexed,operation,width,height,sw,sh,x,y,alpha,key,palette,method;
 int center[2],repeat[2],span[2],rgb[3];unsigned tint[2];int clip[4];
 unsigned source[256],before[256],expected[256];
};
static const struct screen_case tests[]={@CASES@};
static void pixel_store(s_screen *s,size_t index,unsigned value,int bytes){
 if(bytes==1)s->data[index]=(unsigned char)value;
 else if(bytes==2){uint16_t v=(uint16_t)value;memcpy(s->data+index*2,&v,2);}
 else{uint32_t v=value;memcpy(s->data+index*4,&v,4);}
}
static unsigned pixel_load(s_screen *s,size_t index,int bytes){
 if(bytes==1)return s->data[index];
 if(bytes==2){uint16_t v;memcpy(&v,s->data+index*2,2);return v;}
 uint32_t v;memcpy(&v,s->data+index*4,4);return v;
}
static s_screen *owned_screen(int width,int height,int format,int bytes){
 size_t size=offsetof(s_screen,data)+(size_t)width*height*bytes;
 if(size<sizeof(s_screen))size=sizeof(s_screen);
 s_screen *s=calloc(1,size);assert(s);s->width=width;s->height=height;s->pixelformat=format;
#ifdef screen_magic
 s->magic=screen_magic;
#endif
 return s;
}
int main(void){
 if(@UNEXPECTED_TRANSFORM@)gfx_draw_rotate(NULL,NULL,0,0,0,0,NULL);
 enum{CAPACITY=sizeof(blendtables)/sizeof(blendtables[0])};assert(CAPACITY>=6 && CAPACITY<=16);
 unsigned char *indexed=calloc(CAPACITY,65536);assert(indexed);
 unsigned char remap8[256];uint16_t palette16[256],override16[256];uint32_t palette32[256],override32[256];
 for(unsigned i=0;i<256;++i){remap8[i]=(unsigned char)(i*7+11);palette16[i]=(uint16_t)(i*193+0x1234);
  override16[i]=(uint16_t)(i*211+0x4321);palette32[i]=(i*0x10103+0x123456)&0xffffff;
  override32[i]=(i*0x30201+0x654321)&0xffffff;}
 for(unsigned m=0;m<CAPACITY;++m)for(unsigned f=0;f<256;++f)for(unsigned b=0;b<256;++b)
  indexed[m*65536+(f<<8)+b]=(unsigned char)(f*3+b*5+m+1);
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct screen_case *t=tests+active_case;int bytes=t->bits/8;
  int format=t->bits==8?PIXEL_8:t->bits==16?PIXEL_16:PIXEL_32;
  s_screen *dest=owned_screen(t->width,t->height,format,bytes);
  s_screen *src=owned_screen(t->sw,t->sh,t->indexed?PIXEL_x8:format,t->indexed?1:bytes);
  if(t->indexed && t->palette)src->palette=(unsigned char*)(t->bits==16?(void*)palette16:(void*)palette32);
  for(size_t p=0;p<(size_t)t->width*t->height;++p)pixel_store(dest,p,t->before[p],bytes);
  for(size_t p=0;p<(size_t)t->sw*t->sh;++p)pixel_store(src,p,t->source[p],t->indexed?1:bytes);
  unsigned char original_source[1024];size_t source_bytes=(size_t)t->sw*t->sh*(t->indexed?1:bytes);
  memcpy(original_source,src->data,source_bytes);
  for(unsigned m=0;m<CAPACITY;++m)blendtables[m]=t->bits==8?indexed+m*65536:NULL;
  screenformat=pixelformat=format;
#if @CHANNELS@
  channelr=channelg=channelb=255;usechannel=0;
#endif
#if @TINT@
  tintmode=tintcolor=0;
#endif
#if @CLIPPING@
  useclip=t->clip[0]!=0 || t->clip[1]!=0 || t->clip[2]!=t->width || t->clip[3]!=t->height;
  clipx1=t->clip[0];clipy1=t->clip[1];clipx2=t->clip[2];clipy2=t->clip[3];
#endif
  s_drawmethod method;memset(&method,0,sizeof(method));method.flag=t->method==1;method.alpha=t->alpha;
  method.transbg=t->key;method.scalex=method.scaley=256;method.centerx=t->center[0];method.centery=t->center[1];
  method.xrepeat=t->repeat[0];method.yrepeat=t->repeat[1];method.xspan=t->span[0];method.yspan=t->span[1];
#if @CHANNELS@
  method.channelr=t->rgb[0];method.channelg=t->rgb[1];method.channelb=t->rgb[2];
#endif
#if @TINT@
  method.tintmode=t->tint[0];method.tintcolor=t->tint[1];
#endif
  if(t->palette==2)method.table=(unsigned char*)(t->bits==8?(void*)remap8:t->bits==16?(void*)override16:(void*)override32);
  unsigned char original_method[sizeof(method)];memcpy(original_method,&method,sizeof(method));
  if(t->operation==0)copyscreen(dest,src);
  else if(t->operation==1)copyscreen_o(dest,src,t->x,t->y);
  else if(t->operation==2)copyscreen_trans(dest,src,t->x,t->y);
  else if(t->operation==3)copyscreen_remap(dest,src,t->x,t->y,remap8);
  else if(t->operation==4)blendscreen(dest,src,t->x,t->y,indexed+(t->alpha-1)*65536);
  else if(t->operation==5){
   if(t->bits==16)blendscreen16(dest,src,t->x,t->y,t->key,t->alpha?blendfunctions16[t->alpha-1]:NULL);
   else blendscreen32(dest,src,t->x,t->y,t->key,t->alpha?blendfunctions32[t->alpha-1]:NULL);
  }else if(t->operation==6){
   if(t->bits==16)putscreenx8p16(dest,src,t->x,t->y,t->key,t->palette==2?override16:NULL,t->alpha?blendfunctions16[t->alpha-1]:NULL);
   else putscreenx8p32(dest,src,t->x,t->y,t->key,t->palette==2?override32:NULL,t->alpha?blendfunctions32[t->alpha-1]:NULL);
  }else putscreen(dest,src,t->x,t->y,t->method<0?NULL:&method);
  assert(!memcmp(original_source,src->data,source_bytes) && !memcmp(original_method,&method,sizeof(method)));
  if(@PERTURB@ && active_case==0)dest->data[0]^=1;
  for(size_t p=0;p<(size_t)t->width*t->height;++p){unsigned value=pixel_load(dest,p,bytes);
   if(value!=t->expected[p]){fprintf(stderr,"Native screen pixel mismatch: case=%u pixel=%zu actual=%u expected=%u\n",active_case,p,value,t->expected[p]);abort();}}
  free(src);free(dest);
 }
 for(unsigned m=0;m<CAPACITY;++m)blendtables[m]=NULL;
 free(indexed);printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    for key, value in dict(REVISION=str(revision) + 'u', REFUSALS=graphics_refusals(True),
                           CASES=',\n'.join(rows), CHANNELS=str(int(channels)),
                           TINT=str(int(tint)), CLIPPING=str(int(clipping)),
                           PERTURB=str(int(perturb_output)),
                           UNEXPECTED_TRANSFORM=str(int(unexpected_transform))).items():
        code = code.replace('@' + key + '@', value)
    return code
