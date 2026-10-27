"""Observe native blend selector results through a complete color unit.

Pointer observations preserve native operation choice without replacing color
implementations. Pixel contracts remain independent evidence.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re


def render_blend_selectors(*, revision, tint_fields, dye_names, cases, perturb_observation=False):
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            type(tint_fields) is not bool or type(perturb_observation) is not bool or
            not isinstance(dye_names, list) or len(dye_names) not in (0, 2) or
            any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z_]\w*', v) for v in dye_names) or
            not isinstance(cases, list) or not 1 <= len(cases) <= 512):
        raise ValueError('Explicit native selector fields, functions and bounded observations required')
    rows = []
    for row in cases:
        if (not isinstance(row, dict) or set(row) != {'alpha', 'tint', 'channels', 'kind', 'slot'} or
                type(row['alpha']) is not int or not -0x80000000 <= row['alpha'] <= 0x7fffffff or
                type(row['tint']) is not int or not 0 <= row['tint'] <= 0xffffffff or
                type(row['channels']) is not bool or type(row['kind']) is not int or not 0 <= row['kind'] <= 4 or
                type(row['slot']) is not int or not -1 <= row['slot'] <= 6 or
                (row['kind'] == 1) != (row['slot'] >= 0) or
                row['kind'] in (2, 3) and not tint_fields or
                row['kind'] == 4 and not dye_names):
            raise ValueError('Complete independent bounded blend selector expectation required')
        rows.append('{' + ','.join([str(row['alpha']), str(row['tint']) + 'u',
                                  str(int(row['channels'])), str(row['kind']), str(row['slot'])]) + '}')
    code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "pixelformat.c"
#undef printf
#undef assert
#ifdef NDEBUG
#error Native selector assertions must remain enabled
#endif
uint32_t obor_profile_build=@REVISION@;
static unsigned active_case;
#define assert(c) do{if(!(c)){fprintf(stderr,"Native blend selector mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
struct selector_case {int alpha;unsigned tint;int channels,kind,slot;};
static const struct selector_case tests[]={@CASES@};
int main(void){
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct selector_case *t=tests+active_case;usechannel=t->channels;
  channelr=127;channelg=255;channelb=63;
#if @TINT@
  tintmode=t->tint;tintcolor=0x1234;
  tint16fp1=blendfunctions16[0];tint16fp2=blendfunctions16[1];
  tint32fp1=blendfunctions32[0];tint32fp2=blendfunctions32[1];
#endif
  blend16fp actual16=getblendfunction16(t->alpha),expected16=NULL;
  blend32fp actual32=getblendfunction32(t->alpha),expected32=NULL;
  if(t->kind==1){
   assert((unsigned)t->slot<sizeof(blendfunctions16)/sizeof(blendfunctions16[0]));
   assert((unsigned)t->slot<sizeof(blendfunctions32)/sizeof(blendfunctions32[0]));
   expected16=blendfunctions16[t->slot];expected32=blendfunctions32[t->slot];
  }
#if @TINT@
  else if(t->kind==2){expected16=blend_tint16;expected32=blend_tint32;}
  else if(t->kind==3){expected16=blend_rgbchannel16;expected32=blend_rgbchannel32;}
#endif
#if @DYE@
  else if(t->kind==4){expected16=@DYE16@;expected32=@DYE32@;}
#endif
  if(@PERTURB@ && active_case==0)actual16=expected16?NULL:blendfunctions16[0];
  assert(actual16==expected16 && actual32==expected32);
#if @TINT@
  if(t->kind==2){
   assert(t->tint>0 && t->tint<=sizeof(blendfunctions16)/sizeof(blendfunctions16[0]));
   assert(tint16fp1==blendfunctions16[t->tint-1] && tint32fp1==blendfunctions32[t->tint-1]);
   assert(tint16fp2==(t->alpha>0?blendfunctions16[t->alpha-1]:NULL));
   assert(tint32fp2==(t->alpha>0?blendfunctions32[t->alpha-1]:NULL));
  }else{
   assert(tint16fp1==blendfunctions16[0] && tint16fp2==blendfunctions16[1]);
   assert(tint32fp1==blendfunctions32[0] && tint32fp2==blendfunctions32[1]);
  }
#endif
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    values = dict(REVISION=str(revision) + 'u', CASES=',\n'.join(rows), TINT=str(int(tint_fields)),
                  DYE=str(int(bool(dye_names))), DYE16=dye_names[0] if dye_names else 'NULL',
                  DYE32=dye_names[1] if dye_names else 'NULL', PERTURB=str(int(perturb_observation)))
    for key, value in values.items(): code = code.replace('@' + key + '@', value)
    return code
