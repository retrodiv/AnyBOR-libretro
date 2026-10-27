"""Render bounded color observations for a complete separately linked unit.

Private JSON supplies native selector/layout and independent color results.
This does not execute the rasterizer, palette factories or the engine arena.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json


def render_color_blend(*, revision, selector, native_modes, channels, tint, cases,
                       allow_invalid=False, table_getter=False):
    if (type(revision) is not int or not 0<revision<=0xffffffff or
            selector not in ('table','getter') or type(native_modes) is not int or
            not 1<=native_modes<=16 or type(channels) is not bool or type(tint) is not bool or
            tint and not channels or type(allow_invalid) is not bool or type(table_getter) is not bool):
        raise ValueError('Explicit native color selector,domain and global fields required')
    if not isinstance(cases,list) or not 1<=len(cases)<=8192:
        raise ValueError('Bounded independent color observations required')
    rows=[]
    for case in cases:
        fields={'bits','alpha','source','destination','rgb','tint_mode','tint_color','expected_has_blender','expected_output'}
        if (not isinstance(case,dict) or set(case)!=fields or type(case['bits']) is not int or
                case['bits'] not in (16,32) or type(case['alpha']) is not int or
                not -2<=case['alpha']<=(64 if allow_invalid else native_modes) or
                any(type(case[k]) is not int or not 0<=case[k]<=(0xffff if case['bits']==16 else 0xffffff)
                    for k in ('source','destination','tint_color','expected_output')) or
                not isinstance(case['rgb'],list) or len(case['rgb'])!=3 or
                any(type(v) is not int or not 0<=v<=255 for v in case['rgb']) or
                type(case['tint_mode']) is not int or not 0<=case['tint_mode']<=(16 if allow_invalid else 6) or
                type(case['expected_has_blender']) is not bool or
                (case['tint_mode'] and not tint)):
            raise ValueError('Valid native color arguments and complete independent result required')
        rows.append('{'+','.join(str(case[k]) for k in ('bits','alpha'))+','+
                    ','.join(str(case[k])+'u' for k in ('source','destination'))+','+
                    '{'+','.join(str(v)+'u' for v in case['rgb'])+'},'+
                    str(case['tint_mode'])+'u,'+str(case['tint_color'])+'u,'+
                    str(int(case['expected_has_blender']))+','+str(case['expected_output'])+'u}')
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "types.h"
#ifdef NDEBUG
#error Native color assertions must remain enabled
#endif
#undef assert
static unsigned active_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Native color blend mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
#if @CHANNELS@
extern unsigned channelr,channelg,channelb;
extern int usechannel;
#endif
#if @TINT@
extern unsigned tintmode,tintcolor;
#endif
/* These adapters only support independently linked native unit allocation.
 * They do not reproduce or validate the engine arena. */
void *obor_malloc(size_t size){assert(size<=1u<<20);return malloc(size);}
void *obor_calloc(size_t count,size_t size){assert(!size || count<=(1u<<20)/size);return calloc(count,size);}
void *obor_realloc(void *ptr,size_t size){assert(size<=1u<<20);return realloc(ptr,size);}
void obor_free(void *ptr){free(ptr);}
#if @TABLE_GETTER@
extern void set_blendtables(unsigned char *tables[]);
#endif
struct color_case {int bits,alpha;unsigned source,destination,rgb[3],tint_mode,tint_color;int expected_has;unsigned expected;};
static const struct color_case tests[]={@CASES@};
int main(void){
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct color_case *test=tests+active_case;unsigned output;int present;
#if @CHANNELS@
  channelr=test->rgb[0];channelg=test->rgb[1];channelb=test->rgb[2];
  usechannel=(channelr<255 || channelg<255 || channelb<255);
#endif
#if @TINT@
  tintmode=test->tint_mode;tintcolor=test->tint_color;
#endif
  if(test->bits==16){
#if @GETTER@
   blend16fp fn=getblendfunction16(test->alpha);
#else
   blend16fp fn=test->alpha>0?blendfunctions16[test->alpha-1]:NULL;
#endif
   present=fn!=NULL;output=fn?fn((unsigned short)test->source,(unsigned short)test->destination):test->source;
  }else{
#if @GETTER@
   blend32fp fn=getblendfunction32(test->alpha);
#else
   blend32fp fn=test->alpha>0?blendfunctions32[test->alpha-1]:NULL;
#endif
   present=fn!=NULL;output=fn?fn(test->source,test->destination):test->source;
  }
  assert(present==test->expected_has && output==test->expected);
 }
#if @TABLE_GETTER@
 enum {CAPACITY=sizeof(blendtables)/sizeof(blendtables[0])};
 assert(CAPACITY>=@MODES@ && CAPACITY<=64 && obor_profile_blend_count()==@MODES@);
 unsigned char markers[CAPACITY];unsigned char *provided[CAPACITY];
 for(int i=0;i<CAPACITY;++i){markers[i]=(unsigned char)i;provided[i]=markers+i;}
 set_blendtables(provided);
 unsigned table_checks=0;
 for(int i=0;i<CAPACITY;++i){assert(blendtables[i]==(i<@MODES@?provided[i]:NULL));++table_checks;}
 for(int alpha=-2;alpha<=CAPACITY+2;++alpha){
  assert(obor_blend_table(alpha)==(alpha>0 && alpha<=@MODES@?provided[alpha-1]:NULL));++table_checks;
 }
 for(int i=0;i<CAPACITY;++i)blendtables[i]=NULL;
 printf("{\"status\":\"PASS\",\"cases\":%u,\"table_checks\":%u}\n",active_case,table_checks);
#else
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);
#endif
 return 0;
}
'''.replace('@REVISION@',str(revision)+'u').replace('@CHANNELS@',str(int(channels))).replace(
        '@TINT@',str(int(tint))).replace('@GETTER@',str(int(selector=='getter'))).replace(
        '@TABLE_GETTER@',str(int(table_getter))).replace('@MODES@',str(native_modes)).replace('@CASES@',',\n'.join(rows))
