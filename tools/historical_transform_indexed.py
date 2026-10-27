"""Compare indexed transform pixels through a complete native transform unit.

The color provider is separate. Geometry, sprites and true-color transforms
require their own contracts.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""


def render_transform_indexed(*, revision, config_flags, cases, perturb_pixel=False, assert_refusal=False):
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            type(config_flags) is not bool or type(perturb_pixel) is not bool or type(assert_refusal) is not bool or
            not isinstance(cases, list) or not 1 <= len(cases) <= 4096):
        raise ValueError('Explicit native revision, method representation and bounded pixel cases required')
    rows = []
    for row in cases:
        if (not isinstance(row, dict) or set(row) != {'source', 'background', 'alpha', 'fill',
                                                    'remap', 'key', 'operation', 'expected'} or
                any(type(row[k]) is not int or not 0 <= row[k] <= 255
                    for k in ('source', 'background', 'expected')) or
                type(row['alpha']) is not int or not 0 <= row['alpha'] <= 7 or
                type(row['fill']) is not int or not 0 <= row['fill'] <= 65535 or
                any(type(row[k]) is not bool for k in ('remap', 'key')) or
                type(row['operation']) is not int or row['operation'] not in (0, 1)):
            raise ValueError('Complete native indexed inputs and independent pixel expectation required')
        rows.append('{' + ','.join(str(int(row[k])) for k in
                    ('source', 'background', 'alpha', 'fill', 'remap', 'key', 'operation', 'expected')) + '}')
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
#error Native transform pixel assertions must remain enabled
#endif
@ASSERT_REFUSAL@
uint32_t obor_profile_build=@REVISION@;
static unsigned active_case;
#define assert(c) do{if(!(c)){fprintf(stderr,"Native indexed transform mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
struct transform_case {int source,background,alpha,fill,remap,key,operation,expected;};
static const struct transform_case tests[]={@CASES@};
static s_screen *owned_screen(int width,int height){
 size_t bytes=offsetof(s_screen,data)+(size_t)width*height;
 if(bytes<sizeof(s_screen))bytes=sizeof(s_screen);
 s_screen *s=calloc(1,bytes);assert(s);s->width=width;s->height=height;
 s->pixelformat=PIXEL_8;s->magic=screen_magic;return s;
}
int main(void){
 enum{CAPACITY=sizeof(blendtables)/sizeof(blendtables[0])};assert(CAPACITY>=6 && CAPACITY<=16);
 unsigned char *owned_luts=calloc(CAPACITY,65536);assert(owned_luts);
 unsigned char owned_remap[256];
 for(unsigned value=0;value<256;++value)owned_remap[value]=(unsigned char)(value*7+11);
 for(unsigned mode=0;mode<CAPACITY;++mode)for(unsigned front=0;front<256;++front)for(unsigned back=0;back<256;++back)
  owned_luts[mode*65536+(front<<8)+back]=(unsigned char)(front*3+back*5+mode+1);
 for(unsigned mode=0;mode<CAPACITY;++mode)blendtables[mode]=owned_luts+mode*65536;
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct transform_case *test=tests+active_case;
  s_screen *dest=owned_screen(8,6),*src=owned_screen(4,3);
  unsigned char *destination=(unsigned char*)dest+offsetof(s_screen,data);
  memset(dest->data,test->background,48);memset(src->data,test->source,12);
  unsigned char original_source[12];memcpy(original_source,src->data,12);
  gfx_entry graphics;memset(&graphics,0,sizeof(graphics));graphics.screen=src;
  s_drawmethod method;memset(&method,0,sizeof(method));@METHOD@
  method.alpha=test->alpha;method.fillcolor=(unsigned)test->fill;
  method.table=test->remap?owned_remap:NULL;method.scalex=method.scaley=256;
  unsigned char original_method[sizeof(method)];memcpy(original_method,&method,sizeof(method));
  init_gfx_global_draw_stuff(dest,&graphics,&method);
  if(test->operation==0)draw_pixel_screen(dest,&graphics,2,2,1,1);
  else{src_seek(1,1);dest_seek(2,2);write_pixel();}
  assert(!memcmp(original_source,src->data,12) && !memcmp(original_method,&method,sizeof(method)));
  if(@PERTURB@ && active_case==0)destination[18]^=1;
  for(unsigned p=0;p<48;++p){unsigned expected=p==18?(unsigned)test->expected:(unsigned)test->background;
   if(destination[p]!=expected){fprintf(stderr,"Native indexed transform pixel mismatch: case=%u pixel=%u actual=%u expected=%u\n",active_case,p,destination[p],expected);abort();}}
  free(src);free(dest);
 }
 for(unsigned mode=0;mode<CAPACITY;++mode)blendtables[mode]=NULL;
 free(owned_luts);printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    method = ('method.config=DRAWMETHOD_CONFIG_ENABLED | '
              '(test->key?DRAWMETHOD_CONFIG_BACKGROUND_TRANSPARENCY:0);' if config_flags else
              'method.flag=test->operation<2;method.transbg=test->key;')
    for key, value in dict(REVISION=str(revision) + 'u', CASES=',\n'.join(rows), METHOD=method,
                           PERTURB=str(int(perturb_pixel)), ASSERT_REFUSAL=(
                               'void exitIfFalse(int value,const char *assertion,const char *func,const char *file,int line){'
                               '(void)value;(void)assertion;(void)func;(void)file;(void)line;'
                               'fputs("Unexpected native bitmap assertion service\\n",stderr);abort();}'
                               if assert_refusal else '')).items():
        code = code.replace('@' + key + '@', value)
    return code
