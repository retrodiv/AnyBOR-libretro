"""Observe native image-to-sprite dimensions, cropping and row records.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import PurePosixPath
import re

from historical_bitmap_dimensions import render_bitmap_dimensions


def render_sprite_loading(*, sprite_cases, sizing_adapter=False, **options):
    if type(sizing_adapter) is not bool or not isinstance(sprite_cases, list) or not 0 < len(sprite_cases) <= 16:
        raise ValueError('Bounded sprite cases and explicit sizing context required')
    entries=[]
    for row in sprite_cases:
        if not isinstance(row, dict) or set(row) != {'path', 'loaded_width', 'loaded_height',
                'left', 'right', 'top', 'bottom', 'width', 'height', 'pixels', 'rows', 'line_offsets'}:
            raise ValueError('Complete independent crop and encoded-row expectations required')
        path=row['path']
        if (not isinstance(path,str) or not PurePosixPath(path).is_absolute() or len(path)>4096 or
                any(c in path for c in ('\0','\r','\n')) or
                any(type(row[key])is not int or not 1<=row[key]<=8192 for key in ('loaded_width','loaded_height')) or
                row['loaded_width']*row['loaded_height']>65536 or
                any(type(row[key])is not int or not 0<=row[key]<=8192 for key in ('left','right','top','bottom')) or
                any(type(row[key])is not int or not 0<=row[key]<=16 for key in ('width','height')) or
                bool(row['width']) != bool(row['height'])):
            raise ValueError('Small valid loaded image and cropped sprite required')
        for key,length,maximum in [('pixels',row['width']*row['height'],255),
                                   ('line_offsets',row['height'],4096)]:
            if not isinstance(row[key],list) or len(row[key])!=length or any(type(v)is not int or not 0<=v<=maximum for v in row[key]):
                raise ValueError('Bounded explicit cropped pixels and line offsets required')
        if (not isinstance(row['rows'],list) or len(row['rows'])>2048 or
                any(type(v)is not int or not 0<=v<=255 for v in row['rows'])):
            raise ValueError('Bounded explicit sprite row bytes required')
        if row['width']:
            if (row['left']+row['width']+row['right']!=row['loaded_width'] or
                    row['top']+row['height']+row['bottom']!=row['loaded_height'] or not row['rows']):
                raise ValueError('Crop extents must match the loaded rectangle')
        elif any(row[key] for key in ('left','right','top','bottom','pixels','rows','line_offsets')):
            raise ValueError('Native empty sprites have zero dimensions and extents')
        values=[json.dumps(path),*[str(row[k]) for k in ('loaded_width','loaded_height','left','right','top','bottom','width','height')]]
        values += ['{%s}' % ','.join(map(str,row[key] or [0])) for key in ('pixels','rows','line_offsets')]
        values += [str(len(row['rows']))]
        entries.append('{'+','.join(values)+'}')
    code=render_bitmap_dimensions(**options)
    marker='static unsigned begins,opened,loaded;'
    declarations=r'''
#include <stddef.h>
#include "sprite.h"
extern s_sprite *loadsprite2(char *,int *,int *);
char packfile[4096]="native-image-control";
typedef struct {
 const char *path;unsigned loaded_width,loaded_height,left,right,top,bottom,width,height;
 unsigned char pixels[256],rows[2048];int line_offsets[16];unsigned row_bytes;
} sprite_case;
static const sprite_case sprite_cases[]={@SPRITES@};
static const sprite_case *active_sprite;
static const void *loaded_bitmap;
static unsigned crop_calls,encode_calls,forget_calls,wrapped_sizes;
static unsigned bitmap_frees,image_calls,clip_calls,encoder_calls;
void __attribute__((no_instrument_function)) __cyg_profile_func_enter(void *function,void *caller){
 (void)caller;
 if(function==(void*)freebitmap)++bitmap_frees;
 if(function==(void*)loadbitmap)++image_calls;
 if(function==(void*)clipbitmap)++clip_calls;
 if(function==(void*)encodesprite)++encoder_calls;
}
void __attribute__((no_instrument_function)) __cyg_profile_func_exit(void *function,void *caller){
 (void)function;(void)caller;
}
'''.replace('@SPRITES@',',\n'.join(entries))
    if code.count(marker)!=1:
        raise ValueError('One image observation context required')
    code=code.replace(marker,declarations+marker)
    code=code.replace('++loaded;', 'loaded_bitmap=owner;++loaded;')
    crop=r'''void obor_resources_bitmap_cropped(const void *owner,unsigned left,unsigned top,unsigned width,unsigned height){
 assert(active_sprite && owner==loaded_bitmap);
 assert(left==active_sprite->left && top==active_sprite->top && width==active_sprite->width && height==active_sprite->height);
 ++crop_calls;
}'''
    code,count=re.subn(r'void obor_resources_bitmap_cropped\([^}]+\}',lambda m:crop,code,count=1)
    if count!=1:
        raise ValueError('One native crop notification observer required')
    services=r'''
static unsigned expected_size(void){
 if(!active_sprite->width)return sizeof(s_sprite);
 unsigned bytes=(unsigned)offsetof(s_sprite,data)+active_sprite->height*sizeof(int)+active_sprite->row_bytes;
 unsigned pad=pixelformat==PIXEL_x8?(4u-bytes%4u)%4u:0u;
 return bytes+pad+(pixelformat==PIXEL_x8?sizeof(expected_palette):0u)+ANYNUMBER;
}
static void check_cropped_bitmap(const s_bitmap *bitmap){
 assert(active_sprite && bitmap && bitmap->width==(int)active_sprite->width && bitmap->height==(int)active_sprite->height);
 assert(!memcmp(bitmap->data,active_sprite->pixels,active_sprite->width*active_sprite->height));
 if(pixelformat==PIXEL_x8)assert(bitmap->palette && !memcmp(bitmap->palette,expected_palette,sizeof(expected_palette)));
 else assert(!bitmap->palette);
}
void obor_resources_forget_owner(const void *owner){assert(owner);++forget_calls;}
void obor_resources_sprite_encoded(const void *bitmap,void *owner,void *body,size_t size,
 unsigned x,unsigned y,unsigned width,unsigned height){
 assert(bitmap==loaded_bitmap && owner && body==(void*)((s_sprite*)owner)->data);
 assert(!x && !y && width==active_sprite->width && height==active_sprite->height);
 assert(size==active_sprite->height*sizeof(int)+active_sprite->row_bytes);
 check_cropped_bitmap(bitmap);++encode_calls;
}
@SIZING@
'''
    adapter=r'''unsigned __wrap_fakey_encodesprite(s_bitmap *bitmap){
 check_cropped_bitmap(bitmap);++wrapped_sizes;return expected_size();
}''' if sizing_adapter else ''
    code=code.replace('int main(void){',services.replace('@SIZING@',adapter)+'int main(void){')
    output=' printf("{\\"status\\":\\"PASS\\",\\"cases\\":%u}\\n",observations);'
    extra=r'''
 for(unsigned n=0;n<sizeof(sprite_cases)/sizeof(sprite_cases[0]);++n){
  active_sprite=&sprite_cases[n];
  image_case transport={active_sprite->path,active_sprite->loaded_width,active_sprite->loaded_height,
    active_sprite->loaded_width,active_sprite->loaded_height};current=&transport;
  for(int mode=0;mode<2;++mode)for(int outputs=0;outputs<4;++outputs){
   pixelformat=mode?PIXEL_x8:PIXEL_8;
   if(!@ADAPTER@){
    s_bitmap *sized=allocbitmap(active_sprite->width?active_sprite->width:1,active_sprite->height?active_sprite->height:1,pixelformat);
    assert(sized);sized->width=(int)active_sprite->width;sized->height=(int)active_sprite->height;
    memcpy(sized->data,active_sprite->pixels,active_sprite->width*active_sprite->height);
    if(mode)memcpy(sized->palette,expected_palette,sizeof(expected_palette));
    assert(fakey_encodesprite(sized)==expected_size());freebitmap(sized);
   }
   begins=opened=loaded=crop_calls=encode_calls=forget_calls=wrapped_sizes=0;
   bitmap_frees=image_calls=clip_calls=encoder_calls=0;loaded_bitmap=NULL;
   int width=-123,height=-456;
   s_sprite *sprite=loadsprite2((char*)active_sprite->path,outputs&1?&width:NULL,outputs&2?&height:NULL);
   assert(sprite && sprite->magic==sprite_magic && sprite->width==(int)active_sprite->width && sprite->height==(int)active_sprite->height);
   assert(width==(outputs&1?(int)active_sprite->loaded_width:-123));
   assert(height==(outputs&2?(int)active_sprite->loaded_height:-456));
   assert(sprite->offsetx==(int)active_sprite->left && sprite->offsety==(int)active_sprite->top);
   assert(sprite->srcwidth==(int)active_sprite->width && sprite->srcheight==(int)active_sprite->height);
   assert(sprite->centerx==-(int)active_sprite->left && sprite->centery==-(int)active_sprite->top);
   assert(sprite->pixelformat==pixelformat && !sprite->mask);
   for(unsigned y=0;y<active_sprite->height;++y)assert(sprite->data[y]==active_sprite->line_offsets[y]);
   if(active_sprite->width){
    assert(!memcmp((unsigned char*)(sprite->data+active_sprite->height),active_sprite->rows,active_sprite->row_bytes));
    if(mode)assert(sprite->palette && !memcmp(sprite->palette,expected_palette,sizeof(expected_palette)));
    else assert(!sprite->palette);
   }else assert(!sprite->palette);
   assert(begins==@HOOKS@ && opened==@HOOKS@ && loaded==@HOOKS@);
   assert(crop_calls==(@HOOKS@ && active_sprite->width));
   assert(encode_calls==(@HOOKS@ && active_sprite->width) && forget_calls==@HOOKS@);
   assert(bitmap_frees==1 && image_calls==1 && clip_calls==1 && encoder_calls==(@ADAPTER@?1:2));
   assert(wrapped_sizes==@ADAPTER@);
   for(int i=0;i<8;++i)assert(!streams[i]);
   free(sprite);++observations;
  }
 }
'''.replace('@ADAPTER@','1'if sizing_adapter else'0').replace('@HOOKS@','1'if options['resource_hooks']else'0')
    if code.count(output)!=1:
        raise ValueError('One native image observation output required')
    return code.replace(output,extra+output)
