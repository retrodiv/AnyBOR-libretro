"""Render whole-unit LUT byte comparisons and LUT-backed color observations.

Expected bytes and pixel values are independent bound inputs. This runs native
factories, not the engine allocator, eight-bit nearest-color palette or raster.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json


def lut_factory_adapters():
    """Give isolated callbacks prototypes without changing upstream C units.

    Older definitions use empty parameter lists. A direct call through each
    adapter preserves that declaration while its callback has an exact type.
    """
    return '\n'.join(
        'static unsigned char *native_%s%d(void){return create_%s%d_tbl();}' %
        (name, bits, name, bits)
        for bits in (16, 32)
        for name in ('screen', 'multiply', 'overlay', 'hardlight', 'dodge', 'half'))


def render_blend_luts(*,revision,expected_path,cases,perturb_output=False):
    if (type(revision) is not int or not 0<revision<=0xffffffff or
            not isinstance(expected_path,str) or not expected_path or len(expected_path)>4096 or
            any(c in expected_path for c in ('\0','\n','\r')) or type(perturb_output) is not bool or
            not isinstance(cases,list) or not 1<=len(cases)<=1024):
        raise ValueError('Explicit bounded revision, expected byte stream and color observations required')
    rows=[]
    for case in cases:
        if (not isinstance(case,dict) or set(case)!={'bits','mode','source','destination','expected'} or
                type(case['bits']) is not int or case['bits'] not in (16,32) or
                type(case['mode']) is not int or not 1<=case['mode']<=6 or
                any(type(case[k]) is not int or not 0<=case[k]<=(0xffff if case['bits']==16 else 0xffffff)
                    for k in ('source','destination','expected'))):
            raise ValueError('Independent bounded native LUT-backed color result required')
        rows.append('{'+','.join(str(case[k])+('u' if k in ('source','destination','expected') else '')
            for k in ('bits','mode','source','destination','expected'))+'}')
    factories=[]
    for bits in (16,32):
        for mode,name in enumerate(('screen','multiply','overlay','hardlight','dodge','half'),1):
            factories.append('{'+str(bits)+','+str(mode)+',native_'+name+str(bits)+','+str(5120 if bits==16 else 65536)+'}')
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "types.h"
#include "palette.h"
#undef printf
#undef free
#undef assert
#ifdef NDEBUG
#error Native LUT assertions must remain enabled
#endif
#define assert(c) do {if(!(c)){fprintf(stderr,"Native LUT contract mismatch: line=%d\n",__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
/* Bounded libc adapters support the isolated unit, not the engine arena. */
void *obor_malloc(size_t size){assert(size<=1u<<20);return malloc(size);}
void *obor_calloc(size_t count,size_t size){assert(!size || count<=(1u<<20)/size);return calloc(count,size);}
void *obor_realloc(void *p,size_t size){assert(size<=1u<<20);return realloc(p,size);}
void obor_free(void *p){free(p);}
struct lut_factory {int bits,mode;unsigned char *(*create)(void);size_t bytes;};
@ADAPTERS@
static const struct lut_factory factories[]={@FACTORIES@};
struct color_case {int bits,mode;unsigned source,destination,expected;};
static const struct color_case cases[]={@CASES@};
int main(void){
 FILE *expected=fopen(@EXPECTED_PATH@,"rb");assert(expected);
 unsigned char reference[65536];unsigned compared=0,observations=0;
 for(unsigned f=0;f<sizeof(factories)/sizeof(*factories);++f){
  const struct lut_factory *factory=factories+f;
  assert(fread(reference,1,factory->bytes,expected)==factory->bytes);
  unsigned char *table=factory->create();assert(table);
  if(@PERTURB@ && f==0)table[0]^=1;
  if(memcmp(reference,table,factory->bytes)){
   fprintf(stderr,"Native LUT content mismatch: bits=%d mode=%d\n",factory->bits,factory->mode);abort();
  }
  blendtables[factory->mode-1]=table;
  for(unsigned i=0;i<sizeof(cases)/sizeof(*cases);++i){
   const struct color_case *test=cases+i;
   if(test->bits!=factory->bits || test->mode!=factory->mode)continue;
   unsigned output=factory->bits==16?
    blendfunctions16[factory->mode-1]((unsigned short)test->source,(unsigned short)test->destination):
    blendfunctions32[factory->mode-1](test->source,test->destination);
   assert(output==test->expected);++observations;
  }
  blendtables[factory->mode-1]=NULL;free(table);compared+=(unsigned)factory->bytes;
 }
 assert(fgetc(expected)==EOF && !ferror(expected));assert(fclose(expected)==0);
 printf("{\"status\":\"PASS\",\"bytes\":%u,\"cases\":%u}\n",compared,observations);return 0;
}
'''.replace('@ADAPTERS@',lut_factory_adapters()).replace('@REVISION@',str(revision)+'u').replace('@EXPECTED_PATH@',json.dumps(expected_path)).replace(
        '@FACTORIES@',',\n'.join(factories)).replace('@CASES@',',\n'.join(rows)).replace('@PERTURB@',str(int(perturb_output)))
