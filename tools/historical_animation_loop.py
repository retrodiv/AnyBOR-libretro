"""Exercise native animation loop stores and frame/selection consumers.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from test_historical_player import function
from test_early_jump_walkoff import continued_macro
from native_allocation_policy import bind_named_allocation_support


def render_animation_loop(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    update = function(source, 'update_animation')
    start = update.index('f = self->animpos + self->animating;')
    end = update.index('if(self->modeldata.subject_to_platform', start)
    # The last brace closes the outer frame-time condition, supplied by the test.
    transition = update[start:end].rstrip()
    if not transition.endswith('}'):
        raise ValueError('Animation frame-time block is incomplete')
    transition = transition[:-1]
    pick = re.search(r'if\(\(!validanim\(example\[i\],ANI_PICK\).*?ready\[i\]\s*=\s*1;',
                     function(source, 'selectplayer'))[0]
    label = 'case CMD_MODEL_LOOP:'
    if source.count(label) != 1:
        raise ValueError('Exactly one model loop command required')
    rest = source[source.index(label) + len(label):]
    load = rest[:re.search(r'\bcase CMD_MODEL_\w+:', rest).start()]
    contexts = ','.join('{%d,%d,%d}' % (row['revision'], row['mode_bits'], row['frame_bits'])
                        for row in fixture['sources'])
    numbers = ','.join('{%d,%d,%d}' % (row['input'], row['signed8'], row['signed16'])
                       for row in fixture['cases'])
    program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef exit
#undef time
#undef pause
#undef shutdown
#undef kill
uint32_t obor_profile_build;
@MODEL_ERROR@
static int anims_loaded;
@ALLOC@
static s_anim animation;
static entity actor,*self=&actor,*example[1]={&actor};
static int supplied[4],ready[1],pick_valid,applied,killed;
static unsigned time;
static const char *shutdownmessage;
#define GET_INT_ARG(i) (assert((i)>=1 && (i)<=3),supplied[i])
static void load(s_anim *newanim,int mode,int start,int end){
 @MODEL_ERROR_STORAGE@
 supplied[1]=mode;supplied[2]=start;supplied[3]=end;do{@LOAD@}while(0);
 return;
lCleanup:assert(!"unexpected animation rejection");
}
static int validanim_provider(entity *who,int ani){assert(who==self && ani==ANI_PICK);return pick_valid;}
#undef validanim
#define validanim validanim_provider
static void selection(void){int i=0;@PICK@}
static void kill_provider(entity *who){assert(who==self);++killed;}
static void update_frame_provider(entity *who,int frame){assert(who==self);applied=frame;}
#define kill kill_provider
#define update_frame update_frame_provider
static void advance(void){int f;@TRANSITION@}
static const struct {int input,v8,v16;} numbers[]={@NUMBERS@};
static const struct {unsigned revision;int mode_bits,frame_bits;} contexts[]={@CONTEXTS@};
static int expected(unsigned i,int bits){assert(bits==8 || bits==16 || bits==32);
 return bits==8?numbers[i].v8:bits==16?numbers[i].v16:numbers[i].input;}
static void check_advance(int mode,int start,int end,int pos,int direction,int autokill){
 int f=pos+direction,moving=direction,dead=0,frame=-99999;
 if(mode && end){
  if(f==end){f=f<0?7:0;if(start)f=start;}
  else if((unsigned)f>=8){moving=0;if(autokill)dead=1;}
 }else if((unsigned)f>=8){
  f=f<0?7:0;
  if(!mode){moving=0;if(autokill)dead=1;}else if(start)f=start;
 }
 if(moving && !dead)frame=f;
 actor.animpos=pos;actor.animating=direction;actor.autokill=autokill;actor.update_mark=0;
 applied=-99999;killed=0;advance();
 assert(actor.animating==moving && killed==dead && applied==frame);
 assert(actor.update_mark==(moving && !dead?1:0));
}
int main(void){
 assert(sizeof(int)==4 && sizeof(short)==2);actor.animation=&animation;
 s_anim *pick_slots[ANI_PICK+1];memset(pick_slots,0,sizeof(pick_slots));
 pick_slots[ANI_PICK]=&animation;actor.modeldata.animation=pick_slots;
 const unsigned count=sizeof(numbers)/sizeof(numbers[0]);
 for(unsigned p=0;p<sizeof(contexts)/sizeof(contexts[0]);++p){
  obor_profile_build=contexts[p].revision;
  s_anim *first=alloc_anim(),*second=alloc_anim();
  assert(first && second && first!=second && anims_loaded==2 && anim_list->next);
  assert(!first->loop.mode && !first->loop.framestart && !first->loop.frameend);
  assert(!second->loop.mode && !second->loop.framestart && !second->loop.frameend);
  while(anim_list){s_anim_list *node=anim_list;anim_list=node->next;free(node->anim);free(node);}anims_loaded=0;
  memset(&animation,0,sizeof(animation));animation.numframes=8;
  for(unsigned i=0;i<count;++i){
   volatile int input=numbers[i].input;signed char original8=input;short original16=input;
   assert(original8==numbers[i].v8 && original16==numbers[i].v16);
   unsigned j=(i+7)%count,k=(i+11)%count;
   load(&animation,numbers[i].input,numbers[j].input,numbers[k].input);
   int mode=expected(i,contexts[p].mode_bits),start=expected(j,contexts[p].frame_bits),end=expected(k,contexts[p].frame_bits);
   assert(animation.loop.mode==mode && animation.loop.framestart==start && animation.loop.frameend==end);
   for(int valid=0;valid<2;++valid)for(unsigned tick=GAME_SPEED*2;tick<=GAME_SPEED*2+1;++tick){
    pick_valid=valid;time=tick;ready[0]=0;selection();
    assert(ready[0]==((!valid || mode) && tick>GAME_SPEED*2));
   }
   for(int pos=0;pos<8;++pos)for(int direction=-1;direction<=1;direction+=2)for(int death=0;death<2;++death)
    check_advance(mode,start,end,pos,direction,death);
   // Exercise a specified end frame and the mode truth value independently.
   load(&animation,numbers[i].input,2,5);mode=expected(i,contexts[p].mode_bits);
   for(int pos=0;pos<8;++pos)for(int direction=-1;direction<=1;direction+=2)for(int death=0;death<2;++death)
    check_advance(mode,2,5,pos,direction,death);
   // No explicit end: preserve wide restart frames at either animation boundary.
   load(&animation,1,numbers[i].input,0);start=expected(i,contexts[p].frame_bits);
   check_advance(1,start,0,7,1,0);check_advance(1,start,0,0,-1,0);
  }
 }
 printf("animation loop contexts: %zu\n",sizeof(contexts)/sizeof(contexts[0]));return 0;
}
'''.replace('@MODEL_ERROR@', function(source, 'obor_model_error') + '\n' + continued_macro(source, 'OBOR_MODEL_ERROR')).replace(
        '@MODEL_ERROR_STORAGE@', re.search(r'char legacy_model_error\[\d+\][^;]*;', function(source, 'load_cached_model')).group()).replace(
        '@ALLOC@', function(source, 'alloc_anim')).replace('@LOAD@', load).replace(
        '@PICK@', pick).replace('@TRANSITION@', transition).replace('@NUMBERS@', numbers).replace(
        '@CONTEXTS@', contexts)
    return bind_named_allocation_support(program, engine)
