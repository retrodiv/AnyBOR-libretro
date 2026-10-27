"""Render native variant integer-conversion contracts from explicit JSON cases.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import math


def render_integer_value(revisions, cases):
    if (not isinstance(revisions,list) or not 0<len(revisions)<=512 or
            any(type(r)is not int or not 0<r<=0xffffffff for r in revisions) or
            len(set(revisions))!=len(revisions)):
        raise ValueError('Distinct bounded profile revisions required')
    if not isinstance(cases,list) or not 0<len(cases)<=128:
        raise ValueError('Explicit bounded conversion cases required')
    statements=[]
    for row in cases:
        if (not isinstance(row,dict) or set(row)!={'kind','value','status','output'} or
                row['kind'] not in ['integer','decimal','empty','null-input','null-output'] or
                row['status'] not in ['S_OK','E_FAIL'] or type(row['output'])is not int or
                not -2147483648<=row['output']<=2147483647):
            raise ValueError('Typed conversion case, status and signed output required')
        kind,value=row['kind'],row['value']
        init='input.vt=VT_EMPTY;'
        if kind=='integer':
            if type(value)is not int or not -2147483648<=value<=2147483647:
                raise ValueError('Native signed integer input required')
            init='input.vt=VT_INTEGER;input.lVal=(LONG)('+str(value)+');'
        elif kind=='decimal':
            if type(value)in [int,float] and math.isfinite(value):
                literal=repr(float(value))
            elif isinstance(value,str) and value in ['nan','+inf','-inf']:
                literal={'nan':'NAN','+inf':'INFINITY','-inf':'(-INFINITY)'}[value]
            else:
                raise ValueError('Explicit decimal or named non-finite value required')
            init='input.vt=VT_DECIMAL;input.dblVal='+literal+';'
        elif value is not None:
            raise ValueError('Unavailable or empty input has no scalar value')
        call='ScriptVariant_IntegerValue('+('NULL' if kind=='null-input' else '&input')+','+('NULL' if kind=='null-output' else '&output')+')'
        statements.append('{ ScriptVariant input={0};LONG output=777;'+init+
            'CHECK('+call+'=='+row['status']+',"conversion status");'+
            'CHECK(output==(LONG)('+str(row['output'])+'),"conversion output");++checks;}')
    return r'''#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <math.h>
#include "ScriptVariant.h"
/* Fixture output uses libc; native variant code keeps its own logging service. */
#undef printf
uint32_t obor_profile_build;
#define CHECK(c,m) do{if(!(c)){fprintf(stderr,"Integer conversion mismatch: %s\n",m);abort();}}while(0)
int main(void){
 _Static_assert(sizeof(LONG)==4,"native signed script integer width");
 const uint32_t revisions[]={@REVISIONS@};unsigned checks=0;
 for(unsigned n=0;n<sizeof(revisions)/sizeof(*revisions);++n){
  obor_profile_build=revisions[n];@CASES@
 }
 printf("{\"status\":\"PASS\",\"contexts\":%u,\"checks\":%u}\n",
  (unsigned)(sizeof(revisions)/sizeof(*revisions)),checks);return 0;
}
'''.replace('@REVISIONS@',','.join(map(str,revisions))).replace('@CASES@','\n'.join(statements))
