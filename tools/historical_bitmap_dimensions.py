"""Construct bounded valid-image observations for complete native loader units.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import PurePosixPath


def render_bitmap_dimensions(*, revision, cases, palette, resource_hooks,
                             perturb_dimension=False, magic_field=True,
                             screen_format_variable=True):
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            type(resource_hooks) is not bool or type(perturb_dimension) is not bool or
            type(magic_field) is not bool or
            type(screen_format_variable) is not bool or
            not isinstance(cases, list) or not 0 < len(cases) <= 16 or
            not isinstance(palette, list) or len(palette) not in (768, 1024) or
            any(type(value) is not int or not 0 <= value <= 255 for value in palette)):
        raise ValueError('Bounded native image cases, complete palette and revision required')
    rows = []
    for row in cases:
        if not isinstance(row, dict) or set(row) != {'path', 'width', 'height', 'expected_width', 'expected_height'}:
            raise ValueError('Explicit input and expected image dimensions required')
        path = row['path']
        if (not isinstance(path, str) or not PurePosixPath(path).is_absolute() or
                len(path) > 4096 or any(char in path for char in ('\0', '\r', '\n')) or
                any(type(row[key]) is not int or not 0 < row[key] <= 8192
                    for key in ('width', 'height', 'expected_width', 'expected_height')) or
                row['width'] * row['height'] > 65536 or
                row['expected_width'] > row['width'] or row['expected_height'] > row['height']):
            raise ValueError('Small valid images and in-bounds expected rectangles required')
        rows.append('{%s,%du,%du,%du,%du}' % (json.dumps(path), row['width'], row['height'],
                                           row['expected_width'], row['expected_height']))
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "types.h"
#include "bitmap.h"
#include "loadimg.h"
#include "packfile.h"
#undef printf
#undef assert
#ifdef NDEBUG
#error Native image observations require assertions
#endif
#define assert(c) do{if(!(c)){fprintf(stderr,"Native image dimension mismatch: line=%d\n",__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
typedef struct {const char *path;unsigned width,height,expected_width,expected_height;} image_case;
static const image_case cases[]={@CASES@};
static const unsigned char expected_palette[@PALETTE_BYTES@]={@PALETTE@};
static FILE *streams[8];
static unsigned begins,opened,loaded;
static const image_case *current;

/* Plain-file transport only; the complete image decoder owns all parsing. */
int openpackfile(const char *filename,const char *packname){
 assert(filename && packname && !strcmp(packname,"native-image-control"));
 for(int i=0;i<8;++i)if(!streams[i]){
  streams[i]=fopen(filename,"rb");return streams[i]?i:-1;
 }
 return -1;
}
int readpackfile(int handle,void *buffer,int length){
 assert(handle>=0 && handle<8 && streams[handle] && length>=0);
 return (int)fread(buffer,1,(size_t)length,streams[handle]);
}
int seekpackfile(int handle,int offset,int whence){
 assert(handle>=0 && handle<8 && streams[handle]);
 if(fseek(streams[handle],offset,whence))return -1;
 return (int)ftell(streams[handle]);
}
int closepackfile(int handle){
 assert(handle>=0 && handle<8 && streams[handle]);
 int result=fclose(streams[handle]);streams[handle]=NULL;return result;
}
void obor_resources_image_begin(void){++begins;}
void obor_resources_image_opened(const char *name){
 assert(current && name && !strcmp(current->path,name));++opened;
}
void obor_resources_bitmap_loaded(const void *owner,unsigned width,unsigned height){
 const s_bitmap *bitmap=owner;
 assert(bitmap && width==(unsigned)bitmap->width && height==(unsigned)bitmap->height);++loaded;
}
void obor_resources_bitmap_cropped(const void *owner,unsigned left,unsigned top,unsigned width,unsigned height){
 (void)owner;(void)left;(void)top;(void)width;(void)height;
 assert(0); /* Cropping is a separate contract, never accepted here. */
}
int main(void){
 unsigned observations=0;
 @SCREEN_INIT@
 assert(PAL_BYTES==sizeof(expected_palette));
 for(unsigned n=0;n<sizeof(cases)/sizeof(cases[0]);++n){
  current=&cases[n];
  for(int mode=0;mode<2;++mode){
   begins=opened=loaded=0;pixelformat=mode?PIXEL_x8:PIXEL_8;
   s_bitmap *bitmap=loadbitmap((char*)current->path,"native-image-control",pixelformat);
   assert(bitmap && @MAGIC@bitmap->pixelformat==pixelformat);
   assert(bitmap->width==(int)current->expected_width+@PERTURB@ && bitmap->height==(int)current->expected_height);
   for(unsigned y=0;y<current->expected_height;++y)
    for(unsigned x=0;x<current->expected_width;++x)
     assert(bitmap->data[y*current->expected_width+x]==(unsigned char)((x+2*y)%3+1));
   if(mode)assert(bitmap->palette && !memcmp(bitmap->palette,expected_palette,sizeof(expected_palette)));
   else assert(!bitmap->palette);
   assert(begins==@HOOKS@ && opened==@HOOKS@ && loaded==@HOOKS@);
   for(int i=0;i<8;++i)assert(!streams[i]);
   freebitmap(bitmap);++observations;
  }
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",observations);
 return 0;
}
'''.replace('@REVISION@', str(revision)+'u').replace('@CASES@', ',\n'.join(rows)).replace(
        '@PALETTE@', ','.join(map(str, palette))).replace('@HOOKS@', '1' if resource_hooks else '0').replace(
        '@PERTURB@', '1' if perturb_dimension else '0').replace(
        '@MAGIC@', 'bitmap->magic==bitmap_magic && ' if magic_field else '').replace(
        '@PALETTE_BYTES@', str(len(palette))).replace(
        '@SCREEN_INIT@', 'screenformat=PIXEL_8;' if screen_format_variable else '')
