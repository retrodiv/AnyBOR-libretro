"""Render native stealth loading and target selection with source value domains.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from test_historical_player import function


def render_model_stealth(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    label = 'case CMD_MODEL_STEALTH:'
    if source.count(label) != 1:
        raise ValueError('Exactly one stealth model command required')
    rest = source[source.index(label) + len(label):]
    load = rest[:re.search(r'\bcase CMD_MODEL_\w+:', rest).start()]
    numbers = ','.join('{%d,%d,%d}' % (row['input'], row['signed8'], row['signed16'])
                       for row in fixture['cases'])
    contexts = ','.join('{%d,%d}' % (row['revision'], row['stealth_bits']) for row in fixture['sources'])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef exit
#undef time
#undef pause
#undef shutdown
#undef kill
#undef check_range
uint32_t obor_profile_build;
static entity actor,candidate,*self=&actor,*ent_list[]={&actor,&candidate};
static int ent_max=2,range_ok,range_calls;
static int range_provider(entity *from,entity *to,int anim){
 assert(from==self && to==&candidate && anim==0);++range_calls;return range_ok;
}
#define check_range range_provider
@FUNCTIONS@
#define GET_INT_ARG(i) supplied[i]
static void load(s_model *newchar,int hide,int detect){int supplied[]={0,hide,detect};do{@LOAD@}while(0);}
static const struct {int input,v8,v16;} numbers[]={@NUMBERS@};
static const struct {unsigned revision;int bits;} contexts[]={@CONTEXTS@};
static int expected(unsigned i,int bits){assert(bits==8 || bits==16);return bits==8?numbers[i].v8:numbers[i].v16;}
int main(void){
 assert(sizeof(int)==4 && sizeof(short)==2);actor.exists=candidate.exists=1;
 actor.modeldata.hostile=TYPE_ENEMY;candidate.modeldata.type=TYPE_ENEMY;actor.direction=1;candidate.x=10;
 const unsigned count=sizeof(numbers)/sizeof(numbers[0]);
 for(unsigned p=0;p<sizeof(contexts)/sizeof(contexts[0]);++p){
  obor_profile_build=contexts[p].revision;
  for(unsigned h=0;h<count;++h)for(unsigned d=0;d<count;++d){
   load(&actor.modeldata,0,numbers[d].input);load(&candidate.modeldata,numbers[h].input,0);
   int hide=expected(h,contexts[p].bits),detect=expected(d,contexts[p].bits);
   assert(actor.modeldata.stealth.detect==detect && candidate.modeldata.stealth.hide==hide);
   range_calls=0;int found=normal_find_target(-1,0)!=NULL;
   assert(found==(hide<=detect) && !range_calls);
   for(range_ok=0;range_ok<2;++range_ok){range_calls=0;
    entity *target=normal_find_target(0,0);assert(target==(range_ok && hide<=detect?&candidate:NULL) && range_calls==1);
   }
  }
 }
 printf("model stealth contexts: %zu\n",sizeof(contexts)/sizeof(contexts[0]));return 0;
}
'''.replace('@FUNCTIONS@', function(source, 'diff') + '\n' + function(source, 'normal_find_target')).replace(
        '@LOAD@', load).replace('@NUMBERS@', numbers).replace('@CONTEXTS@', contexts)
