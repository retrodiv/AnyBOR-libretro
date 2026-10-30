"""Render native counter-attack loading and damage predicates with source oracles.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from test_historical_player import function
from test_early_jump_walkoff import braced_statement


def render_counter_range(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    attack = re.sub(r'/\*.*?\*/|//[^\r\n]*', '', function(source, 'do_attack'), flags=re.S)
    start = re.search(r'else\s+if\s*\(\(self->animpos\s*>=\s*self->animation->counterrange\.framestart', attack).start()
    branch = braced_statement(attack, attack[start:attack.index('{', start)].strip())
    condition = branch[:branch.index('{')].strip()
    damage = re.search(r'if\(self->animation->counterrange\.damaged\)\s*self->health\s*-=\s*force;', branch)[0]
    sentinel = re.search(r'\(e->animation->counterrange\.framestart\s*==\s*-1\)', attack)[0]
    default = re.search(r'(?m)^[ \t]*newanim->counterrange\.framestart\s*=\s*-1;[^\r\n]*\r?\n'
        r'(?:[ \t]*newanim->counterrange\.(?:frameend|condition|damaged)\s*=[^;\r\n]+;[^\r\n]*\r?\n){3}', source)[0]
    bodies = []
    for name in ('COUNTERFRAME', 'COUNTERRANGE'):
        label = 'case CMD_MODEL_' + name + ':'
        if source.count(label) != 1:
            raise ValueError('Exactly one native model command required: ' + name)
        start = source.index(label) + len(label)
        rest = source[start:]
        bodies.append(rest[:re.search(r'\bcase CMD_MODEL_\w+:', rest).start()])
    numbers = ','.join('{%d,%d,%d}' % (row['input'], row['signed8'], row['signed16'])
                       for row in fixture['cases'])
    contexts = ','.join('{%d,%d}' % (row['revision'], row['flag_bits']) for row in fixture['sources'])
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
static entity actor,*self=&actor,*e=&actor;
static int supplied[5];
#define GET_INT_ARG(i) (assert((i)>=1 && (i)<=4),supplied[i])
static void defaults(s_anim *newanim){@DEFAULT@}
static void load(s_anim *newanim,int range,int frame,int end,int condition,int damaged){
 supplied[1]=frame;supplied[2]=range?end:condition;supplied[3]=range?condition:damaged;supplied[4]=damaged;
 if(range){do{@RANGE@}while(0);}else{do{@FRAME@}while(0);}
}
static int counter(int force){
 if(0){}@CONDITION@{@DAMAGE@ return 1;}return 0;
}
static int normal_follow(void){return @SENTINEL@;}
static const struct {int input,v8,v16;} numbers[]={@NUMBERS@};
static const struct {unsigned revision;int bits;} contexts[]={@CONTEXTS@};
static int expected(unsigned i,int bits){assert(bits==8 || bits==16);return bits==8?numbers[i].v8:numbers[i].v16;}
int main(void){
 assert(sizeof(short)==2 && sizeof(int)==4);actor.animation=&animation;
 const unsigned count=sizeof(numbers)/sizeof(numbers[0]);
 const int positions[]={0,1,2,9,20,127,300,32767};
 for(unsigned p=0;p<sizeof(contexts)/sizeof(contexts[0]);++p){
  obor_profile_build=contexts[p].revision;
  memset(&animation,0x35,sizeof(animation));defaults(&animation);
  assert(animation.counterrange.framestart==-1 && animation.counterrange.frameend==-1);
  assert(animation.counterrange.condition==0 && animation.counterrange.damaged==0 && normal_follow());
  actor.animpos=0;actor.frozen=0;actor.health=100;assert(!counter(7) && actor.health==100);
  for(unsigned i=0;i<count;++i)for(int range=0;range<2;++range){
   unsigned j=(i+3)%count,k=(i+7)%count,l=(i+11)%count;
   volatile int input=numbers[k].input;signed char original8=input;short original16=input;
   assert(original8==numbers[k].v8 && original16==numbers[k].v16);
   load(&animation,range,numbers[i].input,numbers[j].input,numbers[k].input,numbers[l].input);
   int first=numbers[i].v16,last=range?numbers[j].v16:first;
   int condition=expected(k,contexts[p].bits),damaged=expected(l,contexts[p].bits);
   assert(animation.counterrange.framestart==first && animation.counterrange.frameend==last);
   assert(animation.counterrange.condition==condition && animation.counterrange.damaged==damaged);
   assert(normal_follow()==(first==-1));
   for(unsigned pos=0;pos<sizeof(positions)/sizeof(positions[0]);++pos)for(int frozen=0;frozen<2;++frozen){
    actor.animpos=positions[pos];actor.frozen=frozen;actor.health=100;
    int hits=positions[pos]>=first && positions[pos]<=last && !frozen;
    assert(counter(7)==hits && actor.health==100-(hits && damaged?7:0));
   }
  }
  // Values that become zero only in the later byte domain affect damage.
  for(unsigned i=0;i<count;++i){
   load(&animation,1,1,3,numbers[i].input,numbers[i].input);
   int damaged=expected(i,contexts[p].bits);
   for(int pos=0;pos<=4;++pos)for(int frozen=0;frozen<2;++frozen){
    actor.animpos=pos;actor.frozen=frozen;actor.health=100;
    int hits=pos>=1 && pos<=3 && !frozen;
    assert(counter(7)==hits && actor.health==100-(hits && damaged?7:0));
   }
  }
 }
 printf("counter range contexts: %zu\n",sizeof(contexts)/sizeof(contexts[0]));return 0;
}
'''.replace('@DEFAULT@', default).replace('@FRAME@', bodies[0]).replace('@RANGE@', bodies[1]).replace(
        '@CONDITION@', condition).replace('@DAMAGE@', damage).replace('@SENTINEL@', sentinel).replace(
        '@NUMBERS@', numbers).replace('@CONTEXTS@', contexts)
