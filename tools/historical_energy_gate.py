"""Render native special-move admission and projectile energy charging.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from test_historical_player import function


def render_energy_gate(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    attack = function(source, 'do_attack')
    start = attack.index('if(current_anim->energycost.mponly')
    charge = attack[start:attack.index('topowner->cantfire', start)]
    start = source.index('case CMD_MODEL_ENERGYCOST:')
    load = source[start:source.index('case CMD_MODEL_CHARGETIME:', start)]
    numbers = ','.join('{%d,%d,%d}' % (row['input'], row['signed8'], row['signed16'])
                       for row in fixture['cases'])
    contexts = ','.join('{%d,%d}' % (row['revision'], row['flag_bits'])
                        for row in fixture['sources'])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "openbor.h"
#include "commands.h"
#undef printf
#undef exit
#undef time
#undef pause
#undef shutdown
#undef kill
uint32_t obor_profile_build;
static entity actor,*self=&actor;
static s_anim animation;
@ADMISSION@
#define GET_INT_ARG(i) supplied[i]
static void load(int command,int cost,int mode,int disable){
 int supplied[]={0,cost,mode,disable};s_anim *newanim=&animation;
 switch(command){@LOAD@ default:assert(0);}
}
static void charge(entity *topowner){s_anim *current_anim=&animation;@CHARGE@}
static const struct {int input,v8,v16;} numbers[]={@NUMBERS@};
static const struct {unsigned revision;int bits;} contexts[]={@CONTEXTS@};
static int expected(unsigned i,int bits){assert(bits==8 || bits==16);return bits==8?numbers[i].v8:numbers[i].v16;}
static void check_admission(int mode,int disable){
 const int types[]={TYPE_PLAYER,TYPE_ENEMY,TYPE_NPC},seals[]={0,6,7},magic[]={0,6,7},health[]={0,7,8};
 for(unsigned t=0;t<3;++t)for(unsigned s=0;s<3;++s)for(unsigned m=0;m<3;++m)for(unsigned h=0;h<3;++h)for(int which=0;which<2;++which){
  actor.modeldata.type=types[t];actor.seal=seals[s];actor.mp=magic[m];actor.health=health[h];
  int blocked=disable==types[t] || disable==-1 ||
   (disable==-2 && (types[t]==TYPE_ENEMY || types[t]==TYPE_NPC)) ||
   (disable==-3 && (types[t]==TYPE_PLAYER || types[t]==TYPE_NPC)) ||
   (disable==-4 && (types[t]==TYPE_PLAYER || types[t]==TYPE_ENEMY));
  int allowed=!blocked && (!seals[s] || seals[s]>=7) &&
   (which?(mode!=2 && magic[m]>=7):(mode!=1 && health[h]>7));
  assert(check_energy(which,0)==allowed);
 }
}
int main(void){
 assert(sizeof(short)==2 && sizeof(int)==4);s_anim *slots[]={&animation};
 actor.modeldata.animation=slots;actor.modeldata.animation_capacity=1;animation.numframes=1;
 const unsigned count=sizeof(numbers)/sizeof(numbers[0]);
 for(unsigned p=0;p<sizeof(contexts)/sizeof(contexts[0]);++p){
  obor_profile_build=contexts[p].revision;
  for(unsigned i=0;i<count;++i){
   int value=numbers[i].input,want=expected(i,contexts[p].bits);
   for(int command=0;command<2;++command){
    load(command?CMD_MODEL_MPCOST:CMD_MODEL_ENERGYCOST,7,value,0);
    assert(animation.energycost.cost==7 && animation.energycost.mponly==want && !animation.energycost.disable);
    check_admission(want,0);
    for(int mp=0;mp<=9;mp+=3)for(int hp=1;hp<=10;hp+=3){
     entity owner;memset(&owner,0,sizeof(owner));owner.mp=mp;owner.health=hp;
     charge(&owner);int from_magic=want!=2 && mp>0;
     assert(owner.mp==(from_magic?(mp>7?mp-7:0):mp));
     assert(owner.health==(from_magic?hp:(hp>7?hp-7:1)));
    }
    load(command?CMD_MODEL_MPCOST:CMD_MODEL_ENERGYCOST,7,0,value);
    assert(!animation.energycost.mponly && animation.energycost.disable==want);check_admission(0,want);
   }
   load(CMD_MODEL_ENERGYCOST,7,0,0);load(CMD_MODEL_MPONLY,value,0,0);
   assert(animation.energycost.cost==7 && animation.energycost.mponly==want && !animation.energycost.disable);
   check_admission(want,0);
  }
 }
 printf("energy gate contexts: %zu\n",sizeof(contexts)/sizeof(contexts[0]));return 0;
}
'''.replace('@ADMISSION@', function(source, 'check_energy')).replace('@CHARGE@', charge).replace(
        '@LOAD@', load).replace('@NUMBERS@', numbers).replace('@CONTEXTS@', contexts)
