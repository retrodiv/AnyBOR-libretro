"""Observe native sprite-map capacity and allocation transactions.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def render_sprite_map_growth(*, definition, revision, cases, mode='valid'):
    modes={'valid':0,'unavailable':1,'checked_extents':2,'all':3}
    if (not isinstance(definition,str) or not 0<len(definition)<=8192 or '\0'in definition or
            not re.match(r'\s*void\s+prepare_sprite_map\s*\(',definition) or
            type(revision)is not int or not 0<revision<=0xffffffff or
            not isinstance(mode,str) or mode not in modes or
            not isinstance(cases,list) or not 0<len(cases)<=32):
        raise ValueError('Native map definition, revision, bounded cases and observation mode required')
    records=[]
    for row in cases:
        if (not isinstance(row,dict) or set(row)!={'initial_capacity','present','request','expected_capacity','allocations'} or
                type(row['present'])is not bool or
                any(type(row[key])is not int for key in ('initial_capacity','request','expected_capacity','allocations')) or
                not 0<=row['initial_capacity']<=65536 or row['initial_capacity']%256 or
                row['present']and not row['initial_capacity'] or
                not 0<=row['request']<=65536 or
                not 0<row['expected_capacity']<=65792 or row['expected_capacity']%256 or
                row['expected_capacity']<=row['request'] or row['allocations']not in (0,1) or
                row['present']and row['expected_capacity']<row['initial_capacity'] or
                not row['allocations']and(not row['present']or row['expected_capacity']!=row['initial_capacity'])):
            raise ValueError('Explicit finite native capacity, storage and allocation expectations required')
        records.append('{'+','.join(str(int(row[key])) for key in (
            'initial_capacity','present','request','expected_capacity','allocations'))+'}')
    return r'''
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include "types.h"
#undef printf
#undef assert
#ifdef NDEBUG
#error Native map observations require assertions
#endif
#define CHECK(c,what) do{if(!(c)){fprintf(stderr,"Native sprite map mismatch: %s\n",what);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
s_sprite_map *sprite_map;
int sprite_map_max_items;
typedef struct{unsigned initial_capacity,present,request,expected_capacity,allocations;} growth_case;
static const growth_case cases[]={@CASES@};
static size_t expected_bytes;
static unsigned allocation_calls,total_allocations,unavailable,stop_armed,stops;
static jmp_buf load_stop;
static void *probe_realloc(void *pointer,size_t bytes){
 ++allocation_calls;++total_allocations;
 CHECK(bytes==expected_bytes,"native allocation size");
 if(unavailable)return NULL;
 void *result=realloc(pointer,bytes);CHECK(result,"bounded fixture allocation");return result;
}
static void probe_terminal(int status,const char *message,...){
 CHECK(stop_armed && status==1 && message && strstr(message,"sprite_map"),"native load-stop response");
 ++stops;longjmp(load_stop,1);
}
#undef realloc
#undef shutdown
#undef borShutdown
#define realloc probe_realloc
#define shutdown probe_terminal
#define borShutdown probe_terminal
@DEFINITION@
#undef realloc
#undef shutdown
#undef borShutdown
static unsigned char *saved_bytes;
static size_t saved_size;
static s_sprite_map *saved_map;
static int saved_capacity;
static void prepare(unsigned capacity,unsigned present){
 CHECK(!sprite_map,"previous fixture released");
 sprite_map_max_items=(int)capacity;allocation_calls=unavailable=stops=stop_armed=0;
 saved_map=NULL;saved_bytes=NULL;saved_size=0;saved_capacity=(int)capacity;
 if(present){
  saved_size=capacity*sizeof(*sprite_map);
  sprite_map=calloc(capacity,sizeof(*sprite_map));CHECK(sprite_map,"bounded initial map");
  for(unsigned n=0;n<capacity;++n){sprite_map[n].centerx=(int)n+7;sprite_map[n].centery=-(int)n-3;}
  saved_map=sprite_map;saved_bytes=malloc(saved_size);CHECK(saved_bytes,"bounded map snapshot");
  memcpy(saved_bytes,sprite_map,saved_size);
 }
}
static void dispose(void){
 free(sprite_map);sprite_map=NULL;free(saved_bytes);saved_bytes=NULL;saved_map=NULL;
}
static void valid_case(const growth_case *entry){
 prepare(entry->initial_capacity,entry->present);
 expected_bytes=entry->expected_capacity*sizeof(*sprite_map);
 prepare_sprite_map(entry->request);
 CHECK(sprite_map && sprite_map_max_items==(int)entry->expected_capacity,"native capacity");
 CHECK(allocation_calls==entry->allocations && !stops,"native allocation count");
 if(saved_size)CHECK(!memcmp(sprite_map,saved_bytes,saved_size),"existing map entries preserved");
 dispose();
}
static void unavailable_growth(void){
 prepare(256,1);expected_bytes=512*sizeof(*sprite_map);unavailable=stop_armed=1;
 if(!setjmp(load_stop)){prepare_sprite_map(256);CHECK(0,"unavailable growth must stop loading");}
 stop_armed=0;
 CHECK(stops==1 && allocation_calls==1,"one failed growth and load stop");
 CHECK(sprite_map==saved_map,"growth must retain prior storage");
 CHECK(sprite_map_max_items==saved_capacity,"growth must retain prior capacity");
 CHECK(!memcmp(sprite_map,saved_bytes,saved_size),"failed growth preserves entries");
 dispose();
}
static void rejected_extent(size_t request){
 prepare(256,1);stop_armed=1;expected_bytes=0;
 if(!setjmp(load_stop)){prepare_sprite_map(request);CHECK(0,"unrepresentable extent must stop loading");}
 stop_armed=0;
 CHECK(stops==1 && !allocation_calls,"extent rejected before allocation");
 CHECK(sprite_map==saved_map && sprite_map_max_items==saved_capacity,"rejected extent retains map");
 CHECK(!memcmp(sprite_map,saved_bytes,saved_size),"rejected extent preserves entries");dispose();
}
int main(void){
 unsigned observations=0;
 if(@MODE@==0 || @MODE@==3){
  for(unsigned n=0;n<sizeof(cases)/sizeof(cases[0]);++n){valid_case(cases+n);++observations;}
 }
 if(@MODE@==1 || @MODE@==3){unavailable_growth();++observations;}
 if(@MODE@==2 || @MODE@==3){
  rejected_extent(SIZE_MAX);rejected_extent((size_t)INT_MAX);rejected_extent((size_t)INT_MAX-1);observations+=3;
 }
 printf("{\"status\":\"PASS\",\"cases\":%u,\"allocations\":%u}\n",observations,total_allocations);
 return 0;
}
'''.replace('@REVISION@',str(revision)+'u').replace('@CASES@',',\n'.join(records)).replace(
        '@DEFINITION@',definition).replace('@MODE@',str(modes[mode]))
