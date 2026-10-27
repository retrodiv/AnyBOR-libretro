"""Render bounded native argument-finder byte contracts from explicit data.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def render_findarg(*,revisions,parser,capacity,cases):
    if (not isinstance(revisions,list)or not 0<len(revisions)<=128 or
        any(type(n)is not int or not 0<n<=0xffffffff for n in revisions)or
        revisions!=sorted(set(revisions))or type(capacity)is not int or not 4<=capacity<=65536):
        raise ValueError('Explicit bounded revisions and native capacity required')
    if (not isinstance(parser,str)or not 0<len(parser)<=32768 or '\0'in parser or
        not re.match(r'\s*char\s*\*\s*findarg\s*\(',parser)):
        raise ValueError('Complete native findarg definition required')
    def text_bytes(value):
        return (isinstance(value,list)and 0<len(value)<=65536 and value[-1]==0 and
                0 not in value[:-1]and all(type(n)is int and 0<=n<=255 for n in value))
    if not isinstance(cases,list)or not 0<len(cases)<=256:
        raise ValueError('Explicit bounded independently expected cases required')
    for case in cases:
        if (not isinstance(case,dict)or set(case)!={'prime','input','which','expected'}or
            any(not text_bytes(case[n])for n in ['prime','input','expected'])or
            type(case['which'])is not int or not -(1<<31)<=case['which']<(1<<31)):
            raise ValueError('Terminated byte strings, signed index and exact expectation required')
    arrays=[];checks=[]
    for n,case in enumerate(cases):
        for name in ['prime','input','expected']:
            arrays.append('static const unsigned char '+name+'_'+str(n)+'[]={'+
                          ','.join(map(str,case[name]))+'};')
        checks.append('(void)findarg((char*)prime_'+str(n)+',0);')
        checks.append('CHECK(!strcmp(findarg((char*)input_'+str(n)+','+str(case['which'])+
                      '),(const char*)expected_'+str(n)+'),"native byte contract");++checks;')
    program='''#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef NDEBUG
#error Argument finder requires active checks
#endif
#define CHECK(c,m) do{if(!(c)){fprintf(stderr,"Argument finder mismatch: %s\\n",m);abort();}}while(0)
#define MAX_ARG_LEN @CAPACITY@
static uint32_t obor_profile_build;
@PARSER@
@ARRAYS@
int main(void){
 const uint32_t revisions[]={@REVISIONS@};unsigned checks=0;
 for(unsigned n=0;n<sizeof(revisions)/sizeof(*revisions);++n){
  obor_profile_build=revisions[n];
  @CHECKS@
 }
 printf("{\\"status\\":\\"PASS\\",\\"contexts\\":%u,\\"checks\\":%u}\\n",
  (unsigned)(sizeof(revisions)/sizeof(*revisions)),checks);return 0;
}
'''
    values=dict(CAPACITY=str(capacity),PARSER=parser,ARRAYS='\n'.join(arrays),
                REVISIONS=','.join(str(n)+'u'for n in revisions),CHECKS='\n'.join(checks))
    program=re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],program)
    if len(program)>2<<20:raise ValueError('Split excessive native byte contracts')
    return program
