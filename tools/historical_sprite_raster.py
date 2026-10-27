"""Compare pixels from complete native sprite encoding and drawing units.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""


def render_sprite_raster(*, revision, clipping, resource_hooks, assert_refusal,
                         palettes, cases, perturb_pixel=False, check_routes=True, composition=None):
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            any(type(v) is not bool for v in (clipping, resource_hooks, assert_refusal, perturb_pixel, check_routes)) or
            not isinstance(cases, list) or not 1 <= len(cases) <= 2048 or
            not isinstance(palettes, dict) or set(palettes) != {'8', '16', '32'}):
        raise ValueError('Explicit native sprite context, finite palettes and bounded cases required')
    for bits, entry in palettes.items():
        if not isinstance(entry, dict) or set(entry) != {'original', 'override'}:
            raise ValueError('Both authored native palette sources required')
        for values in entry.values():
            if (not isinstance(values, list) or len(values) != 256 or
                    any(type(v) is not int or not 0 <= v < 1 << int(bits) for v in values)):
                raise ValueError('Native palette needs exactly256bounded entries')
    if composition is not None and (
            not isinstance(composition, dict) or set(composition) != {'channels','tint','native_modes'} or
            any(type(composition[k]) is not bool for k in ('channels','tint')) or
            type(composition['native_modes']) is not int or composition['native_modes'] not in (6,7) or
            composition['tint'] and not composition['channels']):
        raise ValueError('Explicit native wrapper color field availability required')
    extra_fields={'rgb','tint','lookup'} if composition is not None else set()
    rows = []
    for row in cases:
        if (not isinstance(row, dict) or set(row) != {'bits', 'x', 'y', 'anchor', 'center',
                'scale', 'flip', 'shift', 'angle', 'key', 'fill', 'clip', 'source', 'before',
                'expected', 'alpha', 'remap', 'expected_route'} | extra_fields or type(row['bits']) is not int or row['bits'] not in (8,16,32) or
                any(type(row[k]) is not int or not -16 <= row[k] <= 16 for k in ('x','y')) or
                any(type(row[k]) is not bool for k in ('key','remap')) or
                type(row['alpha']) is not int or not 0 <= row['alpha'] <= 7 or
                (composition is None and row['bits'] != 8 and row['alpha'] != 0) or
                type(row['expected_route']) is not int or not 0 <= row['expected_route'] <= 4 or
                type(row['fill']) is not int or not 0 <= row['fill'] <= 255 or
                type(row['shift']) is not int or row['shift'] not in (-128,0,128) or
                type(row['angle']) is not int or row['angle'] not in (0,90,180,270)):
            raise ValueError('Complete finite sprite inputs required; true-color alpha needs a separate contract')
        for key, length, predicate in (
                ('anchor',2,lambda v: type(v) is int and -4 <= v <= 4),
                ('center',2,lambda v: type(v) is int and -4 <= v <= 4),
                ('scale',2,lambda v: type(v) is int and v in (128,256,512)),
                ('flip',2,lambda v: type(v) is bool),
                ('clip',4,lambda v: type(v) is int and 0 <= v <= 12),
                ('source',16,lambda v: type(v) is int and 0 <= v <= 255),
                ('before',120,lambda v: type(v) is int and 0 <= v < 1 << row['bits']),
                ('expected',120,lambda v: type(v) is int and 0 <= v < 1 << row['bits'])):
            if not isinstance(row[key],list) or len(row[key]) != length or not all(predicate(v) for v in row[key]):
                raise ValueError('Bounded sprite arrays and complete independent pixel expectations required')
        if (not 0 <= row['clip'][0] < row['clip'][2] <= 12 or
                not 0 <= row['clip'][1] < row['clip'][3] <= 10 or
                (not clipping and row['clip'] != [0,0,12,10])):
            raise ValueError('Explicit in-screen sprite clipping domain required')
        if composition is not None:
            if (row['alpha']>composition['native_modes'] or not isinstance(row['rgb'],list) or len(row['rgb'])!=3 or
                    any(type(v) is not int or not 0<=v<=255 for v in row['rgb']) or
                    not isinstance(row['tint'],list) or len(row['tint'])!=2 or
                    any(type(v) is not int for v in row['tint']) or not 0<=row['tint'][0]<=6 or
                    not 0<=row['tint'][1]<=(0xffff if row['bits']==16 else 0xffffff) or
                    type(row['lookup']) is not bool or row['bits']==8 and row['lookup']):
                raise ValueError('Bounded color channels, tint and explicit table state required')
        values = [str(row[k]) for k in ('bits','x','y')]
        for key in ('anchor','center','scale','flip'):
            values.append('{' + ','.join(str(int(v)) for v in row[key]) + '}')
        values.extend(str(int(row[k])) for k in ('shift','angle','key','fill','alpha','remap','expected_route'))
        if composition is not None:
            values.extend('{' + ','.join(str(v)+'u' for v in row[k]) + '}' for k in ('rgb','tint'))
            values.append(str(int(row['lookup'])))
        for key in ('clip','source','before','expected'):
            values.append('{' + ','.join(str(v) + 'u' for v in row[key]) + '}')
        rows.append('{' + ','.join(values) + '}')
    declarations = []
    for bits, ctype in (('8','unsigned char'),('16','unsigned short'),('32','unsigned')):
        for kind in ('original','override'):
            declarations.append('static ' + ctype + ' palette_' + bits + '_' + kind + '[256]={' +
                                ','.join(str(v) + 'u' for v in palettes[bits][kind]) + '};')
    code = r'''
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sprite.c"
#undef calloc
#undef malloc
#undef free
#undef printf
#undef assert
#ifdef NDEBUG
#error Native sprite raster assertions must remain enabled
#endif
@ASSERT_REFUSAL@
uint32_t obor_profile_build=@REVISION@;
static unsigned active_case;
#define assert(c) do{if(!(c)){fprintf(stderr,"Native sprite invariant mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
@PALETTES@
@RESOURCE_HOOKS@
static unsigned tracking,route_counts[5];
void __cyg_profile_func_enter(void *function,void *caller) __attribute__((no_instrument_function));
void __cyg_profile_func_exit(void *function,void *caller) __attribute__((no_instrument_function));
void __cyg_profile_func_enter(void *function,void *caller){
 (void)caller;if(!tracking)return;
 if(function==(void*)putsprite_8)++route_counts[0];
 else if(function==(void*)putsprite_x8p16)++route_counts[1];
 else if(function==(void*)putsprite_x8p32)++route_counts[2];
 else if(function==(void*)gfx_draw_scale)++route_counts[3];
 else if(function==(void*)gfx_draw_rotate)++route_counts[4];
}
void __cyg_profile_func_exit(void *function,void *caller){(void)function;(void)caller;}
struct sprite_case {int bits,x,y,anchor[2],center[2],scale[2],flip[2],shift,angle,key,fill,alpha,remap,expected_route;
 unsigned clip[4],source[16],before[120],expected[120];};
static const struct sprite_case tests[]={@CASES@};
static s_screen *owned_screen(int bits){
 size_t bytes=offsetof(s_screen,data)+(size_t)120*(bits/8);
 if(bytes<sizeof(s_screen))bytes=sizeof(s_screen);
 s_screen *s=calloc(1,bytes);assert(s);s->width=12;s->height=10;
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
 enum{CAPACITY=sizeof(blendtables)/sizeof(blendtables[0])};assert(CAPACITY>=6 && CAPACITY<=16);
 unsigned char *luts=calloc(CAPACITY,65536);assert(luts);
 for(unsigned mode=0;mode<CAPACITY;++mode)for(unsigned front=0;front<256;++front)for(unsigned back=0;back<256;++back)
  luts[mode*65536+(front<<8)+back]=(unsigned char)(front*3+back*5+mode+1);
 for(unsigned mode=0;mode<CAPACITY;++mode)blendtables[mode]=luts+mode*65536;
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct sprite_case *test=tests+active_case;
  s_screen *dest=owned_screen(test->bits);screenformat=dest->pixelformat;
  for(unsigned p=0;p<120;++p)store_pixel(dest,test->bits,p,test->before[p]);
  size_t palette_bytes=test->bits==8?0:(size_t)(test->bits/8)*256;
  assert(!palette_bytes || palette_bytes==(size_t)PAL_BYTES);
  size_t bitmap_bytes=offsetof(s_bitmap,data)+16+palette_bytes;
  if(bitmap_bytes<sizeof(s_bitmap))bitmap_bytes=sizeof(s_bitmap);
  s_bitmap *bitmap=calloc(1,bitmap_bytes);assert(bitmap);bitmap->magic=bitmap_magic;
  bitmap->width=bitmap->height=4;bitmap->pixelformat=test->bits==8?PIXEL_8:PIXEL_x8;
  for(unsigned p=0;p<16;++p)bitmap->data[p]=(unsigned char)test->source[p];
  if(palette_bytes){bitmap->palette=bitmap->data+16;
   memcpy(bitmap->palette,test->bits==16?(void*)palette_16_original:(void*)palette_32_original,palette_bytes);}
  unsigned char *original_bitmap=malloc(bitmap_bytes);assert(original_bitmap);memcpy(original_bitmap,bitmap,bitmap_bytes);
  size_t capacity=sizeof(s_sprite)+4*sizeof(int)+4*(2*4+1)+palette_bytes+32;
  s_sprite *frame=calloc(1,capacity);assert(frame);@OWNER_SETUP@
  unsigned size=encodesprite(test->anchor[0],test->anchor[1],bitmap,frame);
  assert(size>=offsetof(s_sprite,data) && (size_t)size<=capacity && frame->width==4 && frame->height==4);
  assert(frame->centerx==test->anchor[0] && frame->centery==test->anchor[1]);
  unsigned char *encoded_copy=malloc(size);assert(encoded_copy);memcpy(encoded_copy,frame,size);
  s_drawmethod method;memset(&method,0,sizeof(method));method.flag=test->bits>0;
  method.scalex=test->scale[0];method.scaley=test->scale[1];method.flipx=test->flip[0];method.flipy=test->flip[1];
  method.shiftx=test->shift;method.rotate=test->angle;method.transbg=test->key;
  method.fillcolor=(unsigned)test->fill;method.alpha=test->alpha;
  method.centerx=test->center[0];method.centery=test->center[1];
  if(test->remap)method.table=test->bits==8?palette_8_override:
     test->bits==16?(unsigned char*)palette_16_override:(unsigned char*)palette_32_override;
  @CLIP@
  unsigned char original_method[sizeof(method)];memcpy(original_method,&method,sizeof(method));
  memset(route_counts,0,sizeof(route_counts));tracking=1;
  putsprite_ex(test->x,test->y,frame,dest,&method);tracking=0;
  if(@CHECK_ROUTES@)for(unsigned r=0;r<5;++r)if(route_counts[r]!=(r==(unsigned)test->expected_route)){
   fprintf(stderr,"Native sprite route mismatch: case=%u route=%u count=%u expected=%u\n",active_case,r,route_counts[r],r==(unsigned)test->expected_route);abort();}
  assert(!memcmp(original_method,&method,sizeof(method)) && !memcmp(encoded_copy,frame,size));
  assert(!memcmp(original_bitmap,bitmap,bitmap_bytes));@OWNER_CHECK@
  if(@PERTURB@ && active_case==0)store_pixel(dest,test->bits,0,load_pixel(dest,test->bits,0)^1);
  for(unsigned p=0;p<120;++p){unsigned actual=load_pixel(dest,test->bits,p);
   if(actual!=test->expected[p]){fprintf(stderr,"Native sprite raster pixel mismatch: case=%u pixel=%u actual=%u expected=%u\n",active_case,p,actual,test->expected[p]);abort();}}
  free(encoded_copy);free(original_bitmap);free(frame);free(bitmap);free(dest);
 }
 for(unsigned mode=0;mode<CAPACITY;++mode)blendtables[mode]=NULL;
 free(luts);printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    hooks = r'''static const void *expected_bitmap,*expected_owner;
static size_t owner_capacity;
static unsigned forget_calls,encode_calls;
void obor_resources_forget_owner(const void *owner){assert(owner==expected_owner);++forget_calls;}
void obor_resources_sprite_encoded(const void *bitmap,void *owner,void *body,size_t length,
 unsigned x,unsigned y,unsigned width,unsigned height){
 assert(bitmap==expected_bitmap && owner==expected_owner && !x && !y && width==4 && height==4);
 uintptr_t base=(uintptr_t)owner,ptr=(uintptr_t)body;
 assert(ptr>=base && ptr-base<=owner_capacity && length<=owner_capacity-(ptr-base));++encode_calls;
}'''
    refusal = ('''void exitIfFalse(int value,const char *assertion,const char *func,const char *file,int line){
 (void)value;(void)assertion;(void)func;(void)file;(void)line;
 fputs("Unexpected native bitmap assertion service\\n",stderr);abort();}''' if assert_refusal else '')
    values = dict(REVISION=str(revision)+'u', CASES=',\n'.join(rows), PALETTES='\n'.join(declarations),
        ASSERT_REFUSAL=refusal, RESOURCE_HOOKS=hooks if resource_hooks else '',
        OWNER_SETUP=('expected_bitmap=bitmap;expected_owner=frame;owner_capacity=capacity;forget_calls=encode_calls=0;'
                     if resource_hooks else ''),
        OWNER_CHECK='assert(forget_calls==1 && encode_calls==1);' if resource_hooks else '',
        CLIP=('useclip=1;clipx1=(int)test->clip[0];clipy1=(int)test->clip[1];'
              'clipx2=(int)test->clip[2];clipy2=(int)test->clip[3];' if clipping else ''),
        PERTURB=str(int(perturb_pixel)), CHECK_ROUTES=str(int(check_routes)))
    for key,value in values.items():code=code.replace('@'+key+'@',value)
    if composition is not None:
        code=_composition_program(code,composition,clipping)
    return code


def _composition_program(code,fields,clipping):
    """Extend the finite sprite program without changing ordinary raster output."""
    code=code.replace('#include "sprite.c"','#include "sprite.c"\n#include "palette.h"')
    code=code.replace('expected_route;\n unsigned clip','expected_route;\n unsigned rgb[3],tint[2];int lookup;\n unsigned clip')
    declarations=r'''/* Bounded libc adapters support isolated native LUT factories, not the arena. */
void *obor_malloc(size_t size){assert(size<=1u<<20);return malloc(size);}
void *obor_calloc(size_t count,size_t size){assert(!size || count<=(1u<<20)/size);return calloc(count,size);}
void *obor_realloc(void *ptr,size_t size){assert(size<=1u<<20);return realloc(ptr,size);}
void obor_free(void *ptr){free(ptr);}
typedef unsigned char *(*native_factory)(void);
static native_factory true_factories[2][6]={
 {create_screen16_tbl,create_multiply16_tbl,create_overlay16_tbl,create_hardlight16_tbl,create_dodge16_tbl,create_half16_tbl},
 {create_screen32_tbl,create_multiply32_tbl,create_overlay32_tbl,create_hardlight32_tbl,create_dodge32_tbl,create_half32_tbl}};
'''
    code=code.replace('struct sprite_case {',declarations+'struct sprite_case {')
    marker=' for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){'
    if code.count(marker)!=1:raise ValueError('One native sprite case loop required')
    code=code.replace(marker,''' for(unsigned mode=0;mode<CAPACITY;++mode)blendtables[mode]=NULL;
 unsigned char *true_tables[2][6];
 for(unsigned format=0;format<2;++format)for(unsigned mode=0;mode<6;++mode){
  true_tables[format][mode]=true_factories[format][mode]();assert(true_tables[format][mode]);
 }
'''+marker)
    marker='  const struct sprite_case *test=tests+active_case;'
    code=code.replace(marker,marker+'''
  for(unsigned mode=0;mode<CAPACITY;++mode)blendtables[mode]=test->bits==8?luts+mode*65536:
   test->lookup && mode<6?true_tables[test->bits==16?0:1][mode]:NULL;
''')
    initialization='  method.xrepeat=method.yrepeat=1;\n'
    if fields['channels']:
        initialization+='  method.channelr=test->rgb[0];method.channelg=test->rgb[1];method.channelb=test->rgb[2];\n'
    if fields['tint']:
        initialization+='  method.tintmode=test->tint[0];method.tintcolor=test->tint[1];\n'
    if clipping:
        initialization+='  method.clipx=(int)test->clip[0];method.clipy=(int)test->clip[1];method.clipw=(int)(test->clip[2]-test->clip[0]);method.cliph=(int)(test->clip[3]-test->clip[1]);\n'
    marker='  unsigned char original_method[sizeof(method)];'
    code=code.replace(marker,initialization+marker)
    marker='  putsprite_ex(test->x,test->y,frame,dest,&method);'
    if code.count(marker)!=1:raise ValueError('One actual sprite draw entry required')
    code=code.replace(marker,'  putsprite(test->x,test->y,frame,dest,&method);')
    marker=' free(luts);printf('
    code=code.replace(marker,' for(unsigned format=0;format<2;++format)for(unsigned mode=0;mode<6;++mode)free(true_tables[format][mode]);\n'+marker)
    return code
