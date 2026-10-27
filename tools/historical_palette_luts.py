"""Render complete indexed-palette unit byte and nearest-color controls.

Expected palettes, tables and query results are bound independently.
This does not run the rasterizer, model loader or engine arena.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json


def render_palette_luts(*,revision,expected_path,queries,perturb_output=False):
    if (type(revision) is not int or not 0<revision<=0xffffffff or
            not isinstance(expected_path,str) or not expected_path or len(expected_path)>4096 or
            any(c in expected_path for c in ('\0','\r','\n')) or type(perturb_output) is not bool or
            not isinstance(queries,list) or not 1<=len(queries)<=1024):
        raise ValueError('Explicit bounded native revision, stream and nearest-color observations required')
    rows=[]
    for row in queries:
        if (not isinstance(row,dict) or set(row)!={'palette','rgb','expected'} or
                type(row['palette']) is not int or row['palette'] not in (0,1) or
                type(row['expected']) is not int or not 0<=row['expected']<=255 or
                not isinstance(row['rgb'],list) or len(row['rgb'])!=3 or
                any(type(v) is not int or not 0<=v<=255 for v in row['rgb'])):
            raise ValueError('Finite authored palette and independent nearest-color index required')
        rows.append('{'+str(row['palette'])+',{'+','.join(map(str,row['rgb']))+'},'+str(row['expected'])+'}')
    names=('screen','multiply','overlay','hardlight','dodge','half')
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "palette.h"
#undef printf
#undef free
#undef assert
#ifdef NDEBUG
#error Native palette assertions must remain enabled
#endif
#define assert(c) do {if(!(c)){fprintf(stderr,"Native indexed palette mismatch: line=%d\n",__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
void *obor_malloc(size_t size){assert(size<=1u<<20);return malloc(size);}
void *obor_calloc(size_t count,size_t size){assert(!size || count<=(1u<<20)/size);return calloc(count,size);}
void *obor_realloc(void *p,size_t size){assert(size<=1u<<20);return realloc(p,size);}
void obor_free(void *p){free(p);}
static palette_table_function factories[]={@FACTORIES@};
struct nearest_case {int palette,rgb[3],expected;};
static const struct nearest_case queries[]={@QUERIES@};
int main(void){
 FILE *expected=fopen(@EXPECTED_PATH@,"rb");assert(expected);
 unsigned char palette[768],reference[65536];unsigned compared=0,observations=0;
 for(unsigned p=0;p<2;++p){
  assert(fread(palette,1,sizeof(palette),expected)==sizeof(palette));
  for(unsigned i=0;i<sizeof(queries)/sizeof(*queries);++i){
   const struct nearest_case *test=queries+i;if(test->palette!=(int)p)continue;
   assert(palette_find(palette,test->rgb[0],test->rgb[1],test->rgb[2])==test->expected);++observations;
  }
  for(unsigned f=0;f<sizeof(factories)/sizeof(*factories);++f){
   assert(factories[f](NULL)==NULL);
   assert(fread(reference,1,sizeof(reference),expected)==sizeof(reference));
   unsigned char *table=factories[f](palette);assert(table);
   if(@PERTURB@ && p==0 && f==0)table[0]^=1;
   if(memcmp(table,reference,sizeof(reference))){
    fprintf(stderr,"Native indexed LUT content mismatch: palette=%u mode=%u\n",p,f+1);abort();
   }
   free(table);compared+=(unsigned)sizeof(reference);
  }
 }
 assert(fgetc(expected)==EOF && !ferror(expected));assert(fclose(expected)==0);
 printf("{\"status\":\"PASS\",\"bytes\":%u,\"queries\":%u}\n",compared,observations);return 0;
}
'''.replace('@REVISION@',str(revision)+'u').replace('@EXPECTED_PATH@',json.dumps(expected_path)).replace(
        '@FACTORIES@',','.join('palette_table_'+n for n in names)).replace('@QUERIES@',',\n'.join(rows)).replace(
        '@PERTURB@',str(int(perturb_output)))
