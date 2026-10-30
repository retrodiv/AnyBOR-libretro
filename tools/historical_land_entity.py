"""Render landing effect index loading and its native spawn consumer.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from test_historical_player import function
from test_early_jump_walkoff import braced_statement


def render_land_entity(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    gravity = function(source, 'check_gravity')
    start = gravity.index('if(self->animation->landframe.frame>=0')
    landing = braced_statement(gravity, gravity[start:gravity.index('{', start)].strip())
    label = 'case CMD_MODEL_LANDFRAME:'
    if source.count(label) != 1:
        raise ValueError('Exactly one landing frame command required')
    rest = source[source.index(label) + len(label):]
    load = rest[:re.search(r'\bcase CMD_MODEL_\w+:', rest).start()]
    numbers = ','.join('{%d,%d}' % (row['input'], row['signed16']) for row in fixture['cases'])
    contexts = ','.join('{%d,%d}' % (row['revision'], row['entity_bits']) for row in fixture['sources'])
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
uint32_t obor_profile_build;
static s_anim animation;
static entity actor,effect,*self=&actor;
static int supplied_frame,supplied_index,lookups,updates,spawns,callbacks,spawn_index;
static char supplied_name[16];
#define GET_INT_ARG(i) (assert((i)==1),supplied_frame)
#define GET_ARG(i) (assert((i)==2),supplied_name)
int get_cached_model_index(char *name){assert(!strcmp(name,"effect"));++lookups;return supplied_index;}
static void load(s_anim *newanim){char *value;do{@LOAD@}while(0);}
void update_frame(entity *who,int frame){assert(who==self && frame==3);++updates;self->animpos=frame;}
entity *spawn(float x,float z,float a,int direction,char *name,int model,s_model *owner){
 assert(x==self->x && z==self->z && a==self->a && direction==self->direction && !name && !owner);
 ++spawns;spawn_index=model;return &effect;
}
void execute_onspawn_script(entity *who){assert(who==&effect && effect.base==self->a && effect.autokill==1);++callbacks;}
static void land(void){entity *dust;@LANDING@}
static const struct {int input,v16;} numbers[]={@NUMBERS@};
static const struct {unsigned revision;int bits;} contexts[]={@CONTEXTS@};
int main(void){
 assert(sizeof(int)==4 && sizeof(short)==2);actor.animation=&animation;
 actor.x=12.5f;actor.z=-4.0f;actor.a=23.0f;actor.direction=1;
 for(unsigned p=0;p<sizeof(contexts)/sizeof(contexts[0]);++p){
  obor_profile_build=contexts[p].revision;
  for(unsigned i=0;i<sizeof(numbers)/sizeof(numbers[0]);++i)for(int named=0;named<2;++named){
   if(named && numbers[i].input < -1)continue;
   memset(&animation,0,sizeof(animation));animation.numframes=4;
   supplied_frame=3;supplied_index=numbers[i].input;strcpy(supplied_name,named?"effect":"");lookups=0;
   load(&animation);int expected=named?(contexts[p].bits==16?numbers[i].v16:numbers[i].input):-1;
   assert(animation.landframe.frame==3 && animation.landframe.ent==expected && lookups==named);
   for(int position=0;position<=3;++position){
    actor.animpos=position;updates=spawns=callbacks=0;spawn_index=-1;memset(&effect,0,sizeof(effect));land();
    assert(updates==(position<3) && spawns==(position<3 && expected>=0) && callbacks==spawns);
    if(spawns)assert(spawn_index==expected);
    assert(actor.animpos==3);
   }
  }
 }
 printf("landing entity contexts: %zu\n",sizeof(contexts)/sizeof(contexts[0]));return 0;
}
'''.replace('@LOAD@', load).replace('@LANDING@', landing).replace('@NUMBERS@', numbers).replace(
        '@CONTEXTS@', contexts)
