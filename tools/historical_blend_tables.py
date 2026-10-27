"""Render complete native blend-table factory, selection and release controls.

Typed providers observe factory selection and return distinct owned tokens.
They do not generate LUTs, run a game, or implement the engine allocator.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re
from test_historical_player import function


PARTS=('blendfx','blendings','blending_table_functions','blending_table_functions16',
       'blending_table_functions32','create_blending_tables','create_blend_tables_x8',
       'change_system_palette','unload_background','profile_helpers')


def blend_table_parts(script, pixel_source):
    parts={name:function(script,name) for name in PARTS[5:9]}
    for name in PARTS[:5]:
        pattern=r'(?ms)^[ \t]*(?:palette_table_function|blend_table_function|int|unsigned[ \t]+char[ \t]*\*)[ \t]+\b'+name+r'\[[^\]]+\][ \t]*=[ \t]*\{[^}]*\}[ \t]*;'
        matches=list(re.finditer(pattern,script))
        if len(matches)!=1:raise ValueError('One complete native descriptor required: '+name)
        parts[name]=matches[0][0]
    parts['profile_helpers']=(function(pixel_source,'obor_profile_blend_count')
        if 'obor_profile_blend_count(' in pixel_source else '')
    return parts


def render_blend_tables(parts, *, revision, native_modes, cases, dynamic_level_palettes,
                        negative_ownership=None):
    if (not isinstance(parts,dict) or set(parts)!=set(PARTS) or
            any(not isinstance(v,str) or len(v)>16384 or (not v.strip() and k!='profile_helpers')
                for k,v in parts.items()) or type(revision) is not int or not 0<revision<=0xffffffff or
            type(native_modes) is not int or not 1<=native_modes<=16 or
            type(dynamic_level_palettes) is not bool or
            negative_ownership not in (None,'foreign','repeated')):
        raise ValueError('Complete bounded native factories, descriptors and explicit domain required')
    if not isinstance(cases,list) or not 1<=len(cases)<=1024:
        raise ValueError('Bounded independent factory observations required')
    fields={'kind','format','mask','fail_after','palette_null','tables_null','background',
            'has_level','index','expected_result','expected_calls','expected_slots','expected_unused',
            'expected_current_palette','expected_palette_target'}
    rows=[]
    for case in cases:
        if (not isinstance(case,dict) or set(case)!=fields or
                case['kind'] not in ('palette','x8','select') or
                case['format'] not in ('PIXEL_8','PIXEL_x8','PIXEL_16','PIXEL_32') or
                any(type(case[k]) is not bool for k in ('palette_null','tables_null','background','has_level')) or
                type(case['fail_after']) is not int or not -1<=case['fail_after']<=15 or
                type(case['index']) is not int or not -1<=case['index']<=3 or
                type(case['expected_result']) is not int or case['expected_result'] not in (0,1) or
                type(case['expected_current_palette']) is not int or not 0<=case['expected_current_palette']<=99 or
                case['expected_palette_target'] not in ('none','default','level1','level2') or
                case['expected_unused'] not in ('null','sentinel')):
            raise ValueError('Explicit native factory arguments, return and selection result required')
        mask=case['mask'];calls=case['expected_calls'];slots=case['expected_slots']
        if ((mask is not None and (not isinstance(mask,list) or len(mask)!=native_modes or
                any(type(v) is not bool for v in mask))) or
                not isinstance(calls,list) or len(calls)>16 or
                any(type(v) is not int or v not in (*range(6),*range(16,22),*range(32,38)) for v in calls) or
                not isinstance(slots,list) or len(slots)!=native_modes or
                any(type(v) is not int or not -2<=v<=15 for v in slots)):
            raise ValueError('Independent bounded descriptor trace and table slots required')
        values=[str(('palette','x8','select').index(case['kind'])),case['format'],str(int(mask is None)),
                '{'+','.join(str(int(v)) for v in (mask if mask is not None else [False]*native_modes))+'}',
                str(case['fail_after']),str(int(case['palette_null'])),str(int(case['tables_null'])),
                str(int(case['background'])),str(int(case['has_level'])),str(case['index']),
                str(case['expected_result']),str(len(calls)),'{'+','.join(map(str,calls or [0]))+'}',
                '{'+','.join(map(str,slots))+'}',str(int(case['expected_unused']=='sentinel')),
                str(case['expected_current_palette']),str(('none','default','level1','level2').index(case['expected_palette_target']))]
        rows.append('{'+','.join(values)+'}')
    code=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef assert
#undef free
#ifdef NDEBUG
#error Native blend table assertions must remain enabled
#endif
static unsigned active_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Native blend table mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
int pixelformat,screenformat,current_palette;
s_level *level;
s_screen *background;
s_savedata savedata;
unsigned char pal[MAX_PAL_SIZE];
static unsigned char input_palette[MAX_PAL_SIZE],tokens[16],sentinel;
static unsigned char live[16];
static int pool_count,trace_count,trace_ids[16],fail_after,free_count,free_ids[16],clear_count,selection_calls;
static int expected_selection;
static s_level level_storage;
static s_screen background_storage;
static unsigned char *provide(int identity,unsigned char *palette){
 assert(trace_count<16 && pool_count<16);
 if(identity<16)assert(palette==input_palette);
 int attempt=trace_count;trace_ids[trace_count++]=identity;
 if(attempt==fail_after)return NULL;
 live[pool_count]=1;return tokens+pool_count++;
}
static void observe_free(void *value){
 int found=-1;for(int i=0;i<pool_count;++i)if(value==tokens+i)found=i;
 if(found<0 || !live[found]){fputs("Foreign or repeated blend-table release\n",stderr);abort();}
 live[found]=0;free_ids[free_count++]=found;
}
void clearscreen(s_screen *screen){assert(screen==&background_storage);++clear_count;}
@PROVIDERS@
@DECLARATIONS@
enum {CAPACITY=sizeof(blendings)/sizeof(*blendings)};
static unsigned char level_palettes[2][MAX_PAL_SIZE];
static unsigned char *level_tables[2][CAPACITY];
#if @DYNAMIC_PALETTES@
_Static_assert(sizeof(level_storage.palettes)==sizeof(void*) && sizeof(level_storage.blendings)==sizeof(void*),"Explicit dynamic native palette storage required");
#else
_Static_assert(sizeof(level_storage.palettes)>sizeof(void*) && sizeof(level_storage.blendings)>sizeof(void*),"Explicit embedded native palette storage required");
#endif
void palette_set_corrected(unsigned char *palette,int gr,int gg,int gb,int br,int bg,int bb){
 assert(expected_selection>=1 && expected_selection<=3);
 assert(selection_calls++==0 && gr==7 && gg==7 && gb==7 && br==11 && bg==11 && bb==11);
 assert(palette==(expected_selection==1?pal:level_storage.palettes[expected_selection-2]));
}
void set_blendtables(unsigned char *tables[]){
 assert(expected_selection>=1 && expected_selection<=3);
 assert(selection_calls++==1);
 assert(tables==(expected_selection==1?blendings:level_storage.blendings[expected_selection-2]));
}
#define free observe_free
@FUNCTIONS@
#undef free
struct table_case {
 int kind,format,mask_null,mask[16],fail_after,palette_null,tables_null,background,has_level,index;
 int result,call_count,calls[16],slots[16],unused_sentinel,current_palette,palette_target;
};
static const struct table_case tests[]={@CASES@};
int main(void){
 assert(CAPACITY>=@MODES@ && CAPACITY<=16);
 for(int i=0;i<CAPACITY;++i)assert(blendfx[i]==(i==1));
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct table_case *test=tests+active_case;
  memset(live,0,sizeof(live));pool_count=trace_count=free_count=clear_count=selection_calls=0;
  memset(&level_storage,0,sizeof(level_storage));memset(&background_storage,0,sizeof(background_storage));
  current_palette=99;pixelformat=screenformat=test->format;fail_after=test->fail_after;
  background=test->background?&background_storage:NULL;
  for(int i=0;i<CAPACITY;++i)blendings[i]=&sentinel;
  int result=1;
  if(test->kind==0){
   result=create_blending_tables(test->palette_null?NULL:input_palette,
       test->tables_null?NULL:blendings,test->mask_null?NULL:(int*)test->mask);
  }else if(test->kind==1){
   create_blend_tables_x8(blendings);
  }else{
   level_storage.numpalettes=2;
#if @DYNAMIC_PALETTES@
   level_storage.palettes=level_palettes;level_storage.blendings=level_tables;
#endif
   level=test->has_level?&level_storage:NULL;savedata.gamma=7;savedata.brightness=11;
   expected_selection=test->palette_target;change_system_palette(test->index);
   assert(selection_calls==(test->palette_target?2:0));
  }
  assert(result==test->result && trace_count==test->call_count && current_palette==test->current_palette);
  for(int i=0;i<trace_count;++i)assert(trace_ids[i]==test->calls[i]);
  if(test->kind!=2){
   for(int i=0;i<CAPACITY;++i){
    int expected=i<@MODES@?test->slots[i]:(test->unused_sentinel?-1:-2);
    unsigned char *pointer=expected==-1?&sentinel:expected==-2?NULL:tokens+expected;
    assert(blendings[i]==pointer);
   }
   /* Retire only fixture-owned created tables through the native destructor.
      This explicit call is not evidence of the level loader's error path. */
   for(int i=0;i<CAPACITY;++i)if(blendings[i]==&sentinel)blendings[i]=NULL;
   unload_background();
   assert(free_count==pool_count && clear_count==test->background);
   int released=0;
   for(int i=0;i<@MODES@;++i)if(test->slots[i]>=0)assert(free_ids[released++]==test->slots[i]);
   assert(released==free_count);
   for(int i=0;i<CAPACITY;++i)assert(!blendings[i]);
   for(int i=0;i<pool_count;++i)assert(!live[i]);
  }
 }
 @NEGATIVE@
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    providers=[]
    for i,name in enumerate(('screen','multiply','overlay','hardlight','dodge','half')):
        providers.append('unsigned char *palette_table_'+name+'(unsigned char *p){return provide('+str(i)+',p);}')
        for bits in (16,32):
            providers.append('unsigned char *create_'+name+str(bits)+'_tbl(void){return provide('+str(bits+i)+',NULL);}')
    declarations='\n'.join(parts[name] for name in PARTS[:5])
    functions='\n'.join(parts[name] for name in ('profile_helpers',*PARTS[5:9]))
    negative=''
    if negative_ownership=='foreign':negative='observe_free(&sentinel);'
    elif negative_ownership=='repeated':negative='pool_count=1;live[0]=1;observe_free(tokens);observe_free(tokens);'
    return code.replace('@DYNAMIC_PALETTES@',str(int(dynamic_level_palettes))).replace(
        '@REVISION@',str(revision)+'u').replace('@MODES@',str(native_modes)).replace(
        '@PROVIDERS@','\n'.join(providers)).replace('@DECLARATIONS@',declarations).replace(
        '@FUNCTIONS@',functions).replace('@CASES@',',\n'.join(rows)).replace('@NEGATIVE@',negative)
