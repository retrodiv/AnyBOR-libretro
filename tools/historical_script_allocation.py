"""Compare exact fresh-script allocation with independent native expectations.

This contract owns and releases only fresh records. Initialized script sharing,
allocation failure, interpreter execution and entity ownership are separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from native_header_fixtures import graphics_refusals, inline_refusals


def render_script_allocation(parts, *, revision, expected_magic, variable_counts,
                             unused_graphics_inlines=False,
                             unused_inline_declarations=None):
    if (not isinstance(parts, dict) or set(parts) != {'alloc_script', 'ScriptVariant_Init'} or
            any(not isinstance(v, str) or not v.strip() or len(v) > 16384 for v in parts.values())):
        raise ValueError('Two complete bounded native allocation/initialization functions required')
    if type(revision) is not int or not 0 < revision <= 0xffffffff or type(expected_magic) is not bool:
        raise ValueError('Explicit native revision and independent tag expectation required')
    if (not isinstance(variable_counts, list) or not 1 <= len(variable_counts) <= 16 or
            any(type(v) is not int or not 0 <= v <= 32 for v in variable_counts) or
            len(set(variable_counts)) != len(variable_counts)):
        raise ValueError('Unique bounded native variable counts required')
    code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "openbor.h"
#undef printf
#undef assert
#ifdef NDEBUG
#error Fresh script assertions must remain enabled
#endif
static unsigned active_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Native script allocation mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
int max_script_vars;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
@GRAPHICS@
@REFUSALS@
@VARIANT_INIT@
@ALLOCATION@
static const int counts[]={@COUNTS@};
int main(void){
 for(unsigned i=0;i<sizeof(counts)/sizeof(*counts);++i){
  max_script_vars=counts[i];
  for(unsigned repeat=0;repeat<3;++repeat){
   Script *script=alloc_script();assert(script);
   assert(script->magic==(@MAGIC@?script_magic:0));
   assert(!script->initialized && !script->pinterpreter && !script->comment);
   assert((script->vars!=NULL)==(max_script_vars>0));
   for(int j=0;j<max_script_vars;++j){
    assert(script->vars[j].vt==VT_EMPTY && script->vars[j].ptrVal==NULL);
   }
   free(script->vars);free(script);++active_case;
  }
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    values = dict(REVISION=str(revision)+'u', MAGIC=str(int(expected_magic)),
                  COUNTS=','.join(map(str,variable_counts)),
                  VARIANT_INIT=parts['ScriptVariant_Init'], ALLOCATION=parts['alloc_script'],
                  GRAPHICS=graphics_refusals(unused_graphics_inlines),
                  REFUSALS=inline_refusals(unused_inline_declarations,
                                          forbidden_names=('alloc_script','ScriptVariant_Init')))
    return re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],code)
