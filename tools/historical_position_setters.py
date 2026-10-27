"""Render native position-setter cases with their actual callback entry/exit.

The entry is a reviewed switch projection. Numeric mapping is a pass-through;
name mapping and unselected cases are covered separately. Native records and
the original decimal conversion remain in use.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def render_position_setters(*, entry, enumeration, decimal, mapping_names, actions,
                            contracts, symbol):
    for value, limit in [(entry, 65536), (enumeration, 32768), (decimal, 8192)]:
        if not isinstance(value, str) or not 0 < len(value) <= limit or '\0' in value:
            raise ValueError('Bounded native callback, enumeration and conversion required')
    if (not re.match(r'\s*HRESULT\s+openbor_changeentityproperty\s*\(', entry) or
            not re.match(r'\s*enum\s+entityproperty_enum\s*\{', enumeration) or
            not re.match(r'\s*HRESULT\s+ScriptVariant_DecimalValue\s*\(', decimal)):
        raise ValueError('Explicit native position callback components required')
    identifier = lambda n: isinstance(n, str) and bool(re.fullmatch(r'[A-Za-z_]\w{0,79}', n))
    if (not identifier(symbol) or not isinstance(mapping_names, list) or
            not 0 < len(mapping_names) <= 4 or any(not identifier(n) for n in mapping_names) or
            len(set(mapping_names)) != len(mapping_names)):
        raise ValueError('Distinct bounded native mapper and unit symbols required')
    if (not isinstance(actions, list) or len(actions) > 128 or
            any(not identifier(n) for n in actions) or actions != sorted(set(actions)) or
            set(actions) & set(mapping_names)):
        raise ValueError('Explicit unique sorted unselected native actions required')
    if (not isinstance(contracts, list) or not 0 < len(contracts) <= 128 or
            any(not isinstance(c, dict) or set(c) != {'revision', 'individual'} or
                type(c['revision']) is not int or not 0 < c['revision'] <= 0xffffffff or
                type(c['individual']) is not bool for c in contracts) or
            [c['revision'] for c in contracts] != sorted({c['revision'] for c in contracts})):
        raise ValueError('Explicit unique source-defined position contracts required')
    names = ['openbor_changeentityproperty', 'ScriptVariant_DecimalValue',
             'obor_profile_build', *mapping_names, *actions]
    namespace = '\n'.join('#define %s %s_%s' % (n, symbol, n) for n in names)
    mappers = '\n'.join('void %s(ScriptVariant **args,int count) {'
        'CHECK(args && count>=3 && args[1] && args[1]->vt==VT_INTEGER);}' % n
        for n in mapping_names)
    code = r'''
@NAMESPACE@
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "openbor.h"
#undef printf
#ifdef NDEBUG
#error Position contract assertions must remain enabled
#endif
#define CHECK(c) do {if(!(c)){fputs("Position setter: native snapshot\n",stderr);abort();}} while(0)
uint32_t obor_profile_build;
@ENUM@
@MAPPERS@
@ACTIONS@
@DECIMAL@
@ENTRY@
static entity actor;
static unsigned checks;
static void invoke(int property,int count,int input_type,int available,int coordinate) {
 actor=(entity){0};actor.x=3.5f;actor.z=-4.5f;actor.a=9.5f;
 ScriptVariant values[6],result;ScriptVariant *args[6];
 memset(values,0,sizeof(values));memset(&result,0,sizeof(result));
 for(int i=0;i<6;++i)args[i]=&values[i];
 values[0].vt=VT_PTR;values[0].ptrVal=&actor;
 values[1].vt=VT_INTEGER;values[1].lVal=property;
 for(int i=2;i<6;++i) {
  values[i].vt=input_type;
  if(input_type==VT_INTEGER)values[i].lVal=17+i;
  else if(input_type==VT_DECIMAL)values[i].dblVal=17.5+i;
  else values[i].ptrVal=&actor;
 }
 ScriptVariant *returned=&result;
 HRESULT status=openbor_changeentityproperty(args,&returned,count);
 CHECK(status==(available?S_OK:E_FAIL) && returned==NULL);
 float expected[3]={3.5f,-4.5f,9.5f};
 if(available && (input_type==VT_INTEGER || input_type==VT_DECIMAL)) {
  if(coordinate<0)for(int i=0;i<3 && i+2<count;++i)
   expected[i]=input_type==VT_INTEGER?(float)(19+i):(float)(19.5+i);
  else expected[coordinate]=input_type==VT_INTEGER?19.0f:19.5f;
 }
 CHECK(actor.x==expected[0] && actor.z==expected[1] && actor.a==expected[2]);
 ++checks;
}
unsigned @SYMBOL@(void) {
 static const struct {uint32_t revision;int individual;} contracts[]={@CONTRACTS@};
 const int labels[]={_ep_x,_ep_z,_ep_a};
 for(unsigned n=0;n<sizeof(contracts)/sizeof(*contracts);++n) {
  obor_profile_build=contracts[n].revision;
  for(int i=0;i<3;++i) {
   invoke(labels[i],3,VT_INTEGER,contracts[n].individual,i);
   invoke(labels[i],3,VT_DECIMAL,contracts[n].individual,i);
   invoke(labels[i],3,VT_PTR,contracts[n].individual,i);
  }
  for(int count=3;count<=5;++count) {
   invoke(_ep_position,count,VT_INTEGER,1,-1);
   invoke(_ep_position,count,VT_DECIMAL,1,-1);
   invoke(_ep_position,count,VT_PTR,1,-1);
  }
 }
 return checks;
}
'''
    return (code.replace('@NAMESPACE@', namespace).replace('@ENUM@', enumeration)
            .replace('@MAPPERS@', mappers).replace('@ACTIONS@', '\n'.join(
                'void %s(void) {abort();}' % name for name in actions))
            .replace('@DECIMAL@', decimal).replace('@ENTRY@', entry)
            .replace('@SYMBOL@', symbol).replace('@CONTRACTS@', ','.join(
                '{%du,%d}' % (c['revision'], c['individual']) for c in contracts)))
