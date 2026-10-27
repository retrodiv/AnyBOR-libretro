"""Observe complete image units copying into a declared smaller rectangle.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import PurePosixPath

from historical_bitmap_dimensions import render_bitmap_dimensions


def render_image_rows(*, image_source, row_cases, allocation_services=False, **options):
    if (not isinstance(image_source, str) or not PurePosixPath(image_source).is_absolute() or
            not image_source.endswith('.c') or len(image_source) > 4096 or
            any(c in image_source for c in ('\0', '\r', '\n')) or
            type(allocation_services) is not bool or
            not isinstance(row_cases, list) or not 0 < len(row_cases) <= 16):
        raise ValueError('Complete image unit and bounded row cases required')
    rows=[]
    for row in row_cases:
        if not isinstance(row,dict) or set(row)!={'path','width','height','target_width','target_height'}:
            raise ValueError('Explicit source and output rectangle required')
        path=row['path']
        if (not isinstance(path,str) or not PurePosixPath(path).is_absolute() or len(path)>4096 or
                any(c in path for c in ('\0','\r','\n')) or
                any(type(row[k])is not int or not 0<row[k]<=8192
                    for k in ('width','height','target_width','target_height')) or
                row['width']*row['height']>65536 or row['target_width']>row['width'] or
                row['target_height']>row['height']):
            raise ValueError('Small valid images and contained output rectangles required')
        rows.append('{%s,%du,%du,%du,%du}'%(json.dumps(path),row['width'],row['height'],
                                         row['target_width'],row['target_height']))
    code=render_bitmap_dimensions(**options)
    include='#include "packfile.h"\n'
    main_output=' printf("{\\"status\\":\\"PASS\\",\\"cases\\":%u}\\n",observations);'
    if code.count(include)!=1 or code.count(main_output)!=1:
        raise ValueError('One native image interface and observation output required')
    code=code.replace(include,include+'#include '+json.dumps(image_source)+'\n#pragma pack()\n')
    if allocation_services:
        services=r'''
#include <stdarg.h>
/* Native wrappers still perform the allocations. This service accepts only
 * successful allocations (or a zero-size result), preserving their pointer. */
void *checkAlloc(void *pointer,size_t size,const char *function,const char *file,int line){
 (void)function;(void)file;(void)line;assert(size==0 || pointer);return pointer;
}
void exitIfFalse(int value,const char *condition,const char *function,const char *file,int line){
 (void)condition;(void)function;(void)file;(void)line;assert(value);
}
void abortIfFalse(int value,const char *condition,const char *function,const char *file,int line){
 exitIfFalse(value,condition,function,file,line);
}
void writeToLogFile(const char *format,...){
 va_list arguments;va_start(arguments,format);vfprintf(stderr,format,arguments);va_end(arguments);
}
'''
        code=code.replace('int main(void){',services+'int main(void){')
    extra=r'''
 {
  static const image_case row_cases[]={@ROWS@};
  for(unsigned n=0;n<sizeof(row_cases)/sizeof(row_cases[0]);++n){
   current=&row_cases[n];
   for(int mode=0;mode<2;++mode){
    unsigned source_size=current->width*current->height;
    unsigned output_size=current->expected_width*current->expected_height;
    /* Extra owned bytes let the old source be observed without an invalid
     * allocation access. Only the declared output rectangle may change. */
    unsigned char *owned=malloc(source_size+32u);
    _Alignas(4) unsigned char pal[768];
    assert(owned);memset(owned,0xa5,source_size+32u);memset(pal,0,sizeof(pal));
    assert(openimage((char*)current->path,"native-image-control"));
    assert(readimage(owned+16u,mode?pal:NULL,(int)current->expected_width,(int)current->expected_height));
    closeimage();
    for(unsigned y=0;y<current->expected_height;++y)
     for(unsigned x=0;x<current->expected_width;++x)
      assert(owned[16u+y*current->expected_width+x]==(unsigned char)((x+2*y)%3+1));
    for(unsigned i=0;i<16u;++i)assert(owned[i]==0xa5);
    for(unsigned i=16u+output_size;i<source_size+32u;++i){
     if(owned[i]!=0xa5){fprintf(stderr,"Native image row boundary mismatch\n");abort();}
    }
    if(mode)assert(!memcmp(pal,expected_palette,sizeof(pal)));
    for(int i=0;i<8;++i)assert(!streams[i]);
    free(owned);++observations;
   }
  }
 }
'''.replace('@ROWS@',',\n'.join(rows)).replace('pal[768]', 'pal[%d]' % len(options['palette']))
    return code.replace(main_output,extra+main_output)
