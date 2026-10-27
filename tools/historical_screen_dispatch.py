"""Observe complete screen dispatch with typed, non-rendering services.

The complete native color unit supplies actual blend-operation pointers.
Pixel, transform and gameplay acceptance require independent contracts.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from native_header_fixtures import graphics_refusals, inline_refusals
from test_historical_player import function


def screen_dispatch_parts(source, *, legacy_water):
    if type(legacy_water) is not bool:
        raise ValueError('Explicit native screen dispatch API required')
    names = ('putscreen', 'putscreen_water') if legacy_water else ('_putscreen',)
    result = {name: function(source, name) for name in names}
    if 'obor_screen_blend_table(' in source:
        result['obor_screen_blend_table'] = function(source, 'obor_screen_blend_table')
    return result


def render_screen_dispatch(parts, *, revision, legacy_water, config_flags, key_value, channels, tint_fields, cases,
                           perturb_observation=False, unused_inline_declarations=None, unexpected_transform=False):
    names = {'putscreen', 'putscreen_water'} if legacy_water else {'_putscreen'}
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            any(type(v) is not bool for v in (legacy_water, config_flags, channels, tint_fields,
                                            perturb_observation, unexpected_transform)) or
            type(key_value) is not int or key_value not in (-1, 1) or
            tint_fields and not channels or
            not isinstance(parts, dict) or not names <= set(parts) <= names | {'obor_screen_blend_table'} or
            any(not isinstance(v, str) or not v.strip() or len(v) > 16384 for v in parts.values()) or
            legacy_water and (config_flags or unexpected_transform) or
            not isinstance(cases, list) or not 1 <= len(cases) <= 2048):
        raise ValueError('Complete bounded native dispatcher, explicit layout and observations required')
    rows = []
    for row in cases:
        if (not isinstance(row, dict) or set(row) != {'bits', 'indexed', 'method', 'alpha', 'key',
                                                   'table', 'available', 'water', 'route', 'slot'} or
                type(row['bits']) is not int or row['bits'] not in (8, 16, 32) or
                any(type(row[k]) is not bool for k in ('indexed', 'key', 'table', 'available', 'water')) or
                type(row['method']) is not int or row['method'] not in (-1, 0, 1) or
                type(row['alpha']) is not int or not -2 <= row['alpha'] <= 63 or
                type(row['route']) is not int or not 1 <= row['route'] <= 13 or
                type(row['slot']) is not int or not -1 <= row['slot'] <= 6 or
                row['water'] and not legacy_water or row['bits'] == 8 and row['indexed'] or
                row['water'] and row['bits'] != 8 and not row['indexed']):
            raise ValueError('Explicit valid native formats, bounded selectors and typed route expected')
        rows.append('{' + ','.join(str(int(row[k])) for k in
                    ('bits', 'indexed', 'method', 'alpha', 'key', 'table', 'available', 'water', 'route', 'slot')) + '}')
    prefix = r'''
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "types.h"
#include "globals.h"
#include "screen.h"
@TRANSFORM_HEADER@
#undef printf
#undef assert
#ifdef NDEBUG
#error Native dispatch assertions must remain enabled
#endif
uint32_t obor_profile_build=@REVISION@;
static unsigned active_case;
#define assert(c) do{if(!(c)){fprintf(stderr,"Native screen dispatch mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
@GRAPHICS@
@INLINE_REFUSALS@
struct dispatch_case {int bits,indexed,method,alpha,key,table,available,water,route,slot;};
static const struct dispatch_case tests[]={@CASES@};
static s_screen *observed_dest,*observed_src;
static int calls,route;static unsigned char *wanted_table;
static blend16fp wanted16;static blend32fp wanted32;
static int expected_key(void){return tests[active_case].method==1?@EXPECTED_KEY@:0;}
static void record_route(int value,s_screen *dest,s_screen *src,int x,int y){
 assert(calls++==0 && dest==observed_dest && src==observed_src && x==3 && y==4);
 route=value;
}
static void water_args(int amplitude,float wavelength,int time,int mode){
 assert(amplitude==2 && wavelength==8.0f && time==11 && mode==1);
}
void copyscreen(s_screen *dest,s_screen *src){(void)dest;(void)src;assert(0);}
void copyscreen_o(s_screen *d,s_screen *s,int x,int y){record_route(1,d,s,x,y);}
void copyscreen_trans(s_screen *d,s_screen *s,int x,int y){record_route(2,d,s,x,y);}
void copyscreen_remap(s_screen *d,s_screen *s,int x,int y,unsigned char *table){
 record_route(3,d,s,x,y);assert(table==wanted_table && table);
}
void blendscreen(s_screen *d,s_screen *s,int x,int y,unsigned char *table){
 record_route(4,d,s,x,y);assert(table==wanted_table && table);
}
'''
    services = []
    for bits, scalar, number in ((16, 'unsigned short', 5), (32, 'unsigned', 7)):
        for indexed in (True, False):
            name = ('putscreenx8p' if indexed else 'blendscreen') + str(bits)
            remap = ', ' + scalar + ' *table' if indexed else ''
            assertion = 'assert(table==(' + scalar + '*)wanted_table);' if indexed else ''
            services.append('void ' + name + '(s_screen *d,s_screen *s,int x,int y,int key' + remap +
                            ',blend' + str(bits) + 'fp fp){record_route(' + str(number + (not indexed)) +
                            ',d,s,x,y);assert(key==expected_key());' +
                            assertion + 'assert(fp==wanted' + str(bits) + ');}')
    if legacy_water:
        services += [r'''
void copyscreen_water(s_screen *d,s_screen *s,int x,int y,int a,float w,int t,int m){
 record_route(9,d,s,x,y);water_args(a,w,t,m);
}
void copyscreen_trans_water(s_screen *d,s_screen *s,int x,int y,int a,float w,int t,int m){
 record_route(10,d,s,x,y);water_args(a,w,t,m);
}
void blendscreen_water(s_screen *d,s_screen *s,int x,int y,int a,float w,int t,int m,unsigned char *table){
 record_route(11,d,s,x,y);water_args(a,w,t,m);assert(table==wanted_table && table);
}
''']
        for bits, scalar, number in ((16, 'unsigned short', 12), (32, 'unsigned', 13)):
            services.append('void putscreenx8p' + str(bits) + '_water(s_screen *d,s_screen *s,int x,int y,int key,' +
                scalar + ' *table,blend' + str(bits) + 'fp fp,int a,float w,int t,int m){record_route(' + str(number) +
                ',d,s,x,y);water_args(a,w,t,m);assert(key==expected_key());' +
                'assert(table==(' + scalar + '*)wanted_table && fp==wanted' + str(bits) + ');}')
    code = prefix + '\n'.join(services) + r'''
@FUNCTIONS@
int main(void){
#if !@LEGACY@
 if(@UNEXPECTED_TRANSFORM@)gfx_draw_rotate(NULL,NULL,0,0,0,0,NULL);
#endif
 enum{CAPACITY=sizeof(blendtables)/sizeof(blendtables[0])};assert(CAPACITY>=6 && CAPACITY<=16);
 unsigned char tokens[CAPACITY];union{max_align_t alignment;unsigned char bytes[1024];} remap_storage;
 unsigned char *remap=remap_storage.bytes;memset(tokens,1,sizeof(tokens));memset(remap,0,1024);
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct dispatch_case *t=tests+active_case;int format=t->bits==8?PIXEL_8:t->bits==16?PIXEL_16:PIXEL_32;
  s_screen dest,src;memset(&dest,0,sizeof(dest));memset(&src,0,sizeof(src));
  dest.width=8;dest.height=6;dest.pixelformat=format;src.width=4;src.height=3;src.pixelformat=t->indexed?PIXEL_x8:format;
  observed_dest=&dest;observed_src=&src;
  for(unsigned i=0;i<CAPACITY;++i)blendtables[i]=t->available?tokens+i:NULL;
  s_drawmethod method;memset(&method,0,sizeof(method));@ENABLE@
  method.alpha=t->alpha;assert(method.alpha==t->alpha);@TRANSPARENCY@
  method.scalex=method.scaley=256;method.table=t->table?remap:NULL;
  unsigned char original[sizeof(method)];memcpy(original,&method,sizeof(method));
  wanted_table=t->method==1 && t->table?remap:NULL;
  if(t->route==4 || t->route==11){assert(t->slot>=0 && t->slot<CAPACITY);wanted_table=tokens+t->slot;}
  if(t->slot>=0){
   assert((unsigned)t->slot<sizeof(blendfunctions16)/sizeof(blendfunctions16[0]));
   assert((unsigned)t->slot<sizeof(blendfunctions32)/sizeof(blendfunctions32[0]));
  }
  wanted16=t->slot>=0?blendfunctions16[t->slot]:NULL;wanted32=t->slot>=0?blendfunctions32[t->slot]:NULL;
  calls=route=0;@INITIALIZE@
  s_drawmethod *argument=t->method<0?NULL:&method;
#if @LEGACY@
  if(t->water)putscreen_water(&dest,&src,3,4,2,8.0f,11,1,argument);
  else putscreen(&dest,&src,3,4,argument);
#else
  _putscreen(&dest,&src,3,4,argument);
#endif
  if(@PERTURB@ && active_case==0)route^=1;
  assert(calls==1 && route==t->route && !memcmp(original,&method,sizeof(method)));
 }
 for(unsigned i=0;i<CAPACITY;++i)blendtables[i]=NULL;
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    initialize = ('usechannel=0;' if channels else '') + ('tintmode=0;' if tint_fields else '')
    enable = ('method.config=(t->method==1?DRAWMETHOD_CONFIG_ENABLED:0) | '
              '(t->key?DRAWMETHOD_CONFIG_BACKGROUND_TRANSPARENCY:0);' if config_flags else
              'method.flag=t->method==1;')
    values = dict(REVISION=str(revision) + 'u', CASES=',\n'.join(rows),
                  TRANSFORM_HEADER='' if legacy_water else '#include "transform.h"',
                  GRAPHICS='' if legacy_water else graphics_refusals(True),
                  INLINE_REFUSALS=inline_refusals(unused_inline_declarations, forbidden_names=tuple(parts) +
                        ('record_route', 'expected_key', 'water_args', 'copyscreen', 'copyscreen_o',
                         'copyscreen_trans', 'copyscreen_remap', 'blendscreen', 'getblendfunction16',
                         'getblendfunction32', 'putscreenx8p16', 'putscreenx8p32', 'blendscreen16', 'blendscreen32')),
                  FUNCTIONS='\n'.join(parts[name] for name in
                        ('obor_screen_blend_table', 'putscreen', 'putscreen_water', '_putscreen') if name in parts),
                  ENABLE=enable, INITIALIZE=initialize, LEGACY=str(int(legacy_water)),
                  EXPECTED_KEY=('(tests[active_case].key?DRAWMETHOD_CONFIG_BACKGROUND_TRANSPARENCY:0)'
                                if config_flags else 'tests[active_case].key*(' + str(key_value) + ')'),
                  TRANSPARENCY='' if config_flags else 'method.transbg=t->key;',
                  PERTURB=str(int(perturb_observation)), UNEXPECTED_TRANSFORM=str(int(unexpected_transform)))
    for key, value in values.items(): code = code.replace('@' + key + '@', value)
    return code
