"""Render native model-switch decisions with explicit callback observations.

The engine header supplies real entity/model/animation records. Callbacks here
observe selection and ordering; their complete implementations, model loading,
script execution, ownership, platform lifecycle and gameplay are separate gates.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from native_header_fixtures import inline_refusals, graphics_refusals


def render_model_switch(source, *, contract, revision, native_capacity,
                        function_arity=None, capacity_cases=False, unused_graphics_inlines=False,
                        unused_inline_declarations=None, helpers='', missing_previous_model=False):
    if not isinstance(source,str) or not source.strip() or len(source)>65536:
        raise ValueError('Bounded exact native model-switch function required')
    if (not isinstance(helpers,str) or len(helpers)>65536 or
            ('obor_scene_counter_adjust(' in source and not helpers.strip())):
        raise ValueError('Explicit bounded native dependency definitions required')
    keys={'arity','sync_effect','checks_slot','reset_attacking','player_bitmask',
          'idle_guard','select_transition','screen_flags','tracks_platforms'}
    effects=('none','assign','update','deadline','deadline_keep_infinite','timestamp')
    if (not isinstance(contract,dict) or set(contract)!=keys or
            type(contract['arity']) is not int or contract['arity'] not in (2,3) or
            contract['sync_effect'] not in effects or
            any(type(contract[key]) is not bool for key in keys-{'arity','sync_effect'}) or
            (contract['arity']==2 and contract['sync_effect']!='none') or
            (contract['arity']==3 and contract['sync_effect']=='none')):
        raise ValueError('Explicit consistent source-defined model-switch contract required')
    if type(revision) is not int or not 0<revision<=0xffffffff:
        raise ValueError('Bounded explicit profile revision required')
    if type(native_capacity) is not bool:
        raise ValueError('Explicit native capacity representation required')
    if (type(missing_previous_model) is not bool or
            (missing_previous_model and (not native_capacity or not helpers.strip()))):
        raise ValueError('Missing previous model is an explicit prepared-only stability case')
    if type(capacity_cases) is not bool or (capacity_cases and not native_capacity):
        raise ValueError('Short-table controls require explicit native capacity representation')
    function_arity=contract['arity'] if function_arity is None else function_arity
    if type(function_arity) is not int or function_arity not in (2,3):
        raise ValueError('Explicit native function argument count required')
    refusals=inline_refusals(unused_inline_declarations,
                            forbidden_names=('ent_set_model','model_switch_under_test'))
    graphics=graphics_refusals(unused_graphics_inlines)
    flags={key:int(value) for key,value in contract.items() if type(value) is bool}
    effects_index={name:n for n,name in enumerate(effects)}
    program=r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "openbor.h"
#undef assert
#undef printf
#undef malloc
#undef calloc
#undef free
#ifdef NDEBUG
#error Native contract assertions must remain enabled
#endif
#define assert(condition) do {if(!(condition)) { \
 fputs("Native model-switch contract mismatch\n",stderr);abort();}} while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *interpreter) {(void)interpreter;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *interpreter) {(void)interpreter;abort();}
@GRAPHICS@
@REFUSALS@
enum {EFFECT=@EFFECT@,ARITY=@ARITY@,CAPACITY=@CAPACITY@,
 CHECKS_SLOT=@CHECKS_SLOT@,RESET_ATTACKING=@RESET_ATTACKING@,
 PLAYER_BITMASK=@PLAYER_BITMASK@,IDLE_GUARD=@IDLE_GUARD@,
 SELECT_TRANSITION=@SELECT_TRANSITION@,SCREEN_FLAGS=@SCREEN_FLAGS@,
 TRACKS_PLATFORMS=@TRACKS_PLATFORMS@};
static s_model old_model,new_model;
static s_anim idle_anim,spawn_anim,respawn_anim,select_anim,transition_anim,custom_anim;
static s_anim *old_table[MAX_ANIS+32],**new_table;
static entity subject;
static unsigned event_count,events[16];
static int fixture_clock,fixture_select,fixture_screen,fixture_platforms;
static int selected_animation,update_position,delay_position;
@HELPERS@
static void event(unsigned value) {
 assert(event_count<16);events[event_count++]=value;
}
static void check_model(entity *ent) {
 assert(ent==&subject && ent->model==&new_model);
 assert(ent->modeldata.animation==new_model.animation);
}
static s_model *observed_findmodel(char *name) {
 assert(!strcmp(name,"next"));event(1);return &new_model;
}
static void observed_copy_uninit(entity *ent,s_model *previous) {
 check_model(ent);assert(previous->animation==old_model.animation);event(2);
}
/* The data-only copy keeps this caller independent of the separately tested
   model/colourmap ownership implementation. It is not an ownership oracle. */
static int observed_model_copy(s_model *dest,const s_model *src) {
 assert(dest==&subject.modeldata && src==&new_model);*dest=*src;return 1;
}
static void observed_colourmap(entity *ent,uint64_t map) {
 check_model(ent);assert(map==17);event(3);
}
static void observed_set_anim(entity *ent,int animation,int reset) {
 check_model(ent);assert(!reset);selected_animation=animation;event(4);
}
static void observed_update_frame(entity *ent,int position) {
 check_model(ent);assert(ent->animation==&custom_anim);
 update_position=position;event(5);
}
static int observed_delay(entity *ent,int position) {
 check_model(ent);assert(ent->animation==&custom_anim);
 delay_position=position;event(6);return 17;
}
static uint64_t observed_timestamp(uint64_t now,int delay) {
 assert(now==(unsigned)fixture_clock && delay==17);event(7);return now+3u*(unsigned)delay;
}
static void observed_shutdown(int code,const char *message,...) {
 (void)code;(void)message;abort();
}
#define findmodel observed_findmodel
#define ent_copy_uninit observed_copy_uninit
#define obor_model_copy observed_model_copy
#define ent_set_colourmap observed_colourmap
#define ent_set_anim observed_set_anim
#define update_frame observed_update_frame
#define calculate_edelay observed_delay
#define animation_timestamp_from_delay observed_timestamp
#undef shutdown
#undef borShutdown
#undef time
#undef _time
#define shutdown observed_shutdown
#define borShutdown observed_shutdown
#define time fixture_clock
#define _time fixture_clock
#define selectScreen fixture_select
#define screen_status fixture_screen
#define numPlatforms fixture_platforms
#define ent_set_model model_switch_under_test
@FUNCTION@
#undef ent_set_model
static unsigned cases;
static void check_case(unsigned mask,int menu,int clock_on,int type_case,
                       int synchronize,int slot,int position,int infinite,int short_table) {
 memset(&old_model,0,sizeof(old_model));memset(&new_model,0,sizeof(new_model));
 memset(&subject,0,sizeof(subject));memset(old_table,0,sizeof(old_table));
 const int table_capacity=short_table?MAX_ANIS:MAX_ANIS+32;
 new_table=calloc((size_t)table_capacity,sizeof(*new_table));assert(new_table);
 idle_anim.numframes=spawn_anim.numframes=respawn_anim.numframes=3;
 select_anim.numframes=transition_anim.numframes=custom_anim.numframes=3;
 if(mask&1)new_table[ANI_IDLE]=&idle_anim;
 if(mask&2)new_table[ANI_SPAWN]=&spawn_anim;
 if(mask&4)new_table[ANI_RESPAWN]=&respawn_anim;
 if(mask&8)new_table[ANI_SELECT]=&select_anim;
 @TRANSITION_SLOT@
 const int custom_id=MAX_ANIS+7;
 old_table[custom_id]=&custom_anim;
 if(slot)new_table[custom_id]=&custom_anim;
 old_model.animation=old_table;new_model.animation=new_table;
 @NATIVE_CAPACITY@
 new_model.type=type_case==0?TYPE_PLAYER:type_case==1?TYPE_ENEMY:(TYPE_PLAYER|TYPE_ENEMY);
 @PLATFORM_FLAGS@
 subject.model=@PREVIOUS_MODEL@;subject.modeldata=old_model;
 subject.animation=&custom_anim;subject.animnum=custom_id;subject.animpos=position;
 subject.attacking=1;subject.map=17;
 @INITIAL_DEADLINE@
 __typeof__(subject.nextanim) original_deadline=subject.nextanim;
 fixture_clock=clock_on?100:0;fixture_select=menu;
 @SCREEN_STATUS@
 fixture_platforms=10;event_count=0;
 selected_animation=update_position=delay_position=-99;
 @CALL@
 check_model(&subject);assert(events[0]==1 && events[1]==2 && events[2]==3);
 assert(fixture_platforms==10+TRACKS_PLATFORMS);
 int sync_taken=ARITY==3 && synchronize && (!CHECKS_SLOT || slot);
 if(sync_taken) {
  assert(slot);assert(subject.animation==&custom_anim && subject.attacking==1);
  assert(selected_animation==-99);
  if(EFFECT==2) {
   assert(event_count==4 && events[3]==5 && update_position==position);
   assert(subject.animpos==(__typeof__(+subject.animpos))position && subject.nextanim==original_deadline);
  } else if(EFFECT>=3) {
   int clipped=position>=3?2:position;
   assert(subject.animpos==(__typeof__(+subject.animpos))clipped && update_position==-99);
   if(EFFECT==4 && infinite) {
    assert(event_count==3 && delay_position==-99 && subject.nextanim==original_deadline);
   } else {
    assert(events[3]==6 && delay_position==clipped);
    assert(event_count==(EFFECT==5?5u:4u));
    if(EFFECT==5)assert(events[4]==7);
    assert(subject.nextanim==(unsigned)fixture_clock+(EFFECT==5?51u:17u));
   }
  } else {
   assert(EFFECT==1 && event_count==3 && subject.animpos==(__typeof__(+subject.animpos))position);
   assert(subject.nextanim==original_deadline && update_position==-99 && delay_position==-99);
  }
 } else {
  assert(subject.attacking==(RESET_ATTACKING?0:1));
  int is_player=PLAYER_BITMASK?!!(new_model.type&TYPE_PLAYER):new_model.type==TYPE_PLAYER;
  int expected=ANI_IDLE;
  if((!menu && !clock_on)||!is_player) {if(mask&2)expected=ANI_SPAWN;}
  else if(!menu && clock_on && is_player) {
   if(mask&4)expected=ANI_RESPAWN;else if(mask&2)expected=ANI_SPAWN;
  } else if(menu && (mask&8)) {
   expected=@SELECT_EXPECTATION@;
  }
  if(expected==ANI_IDLE && !(mask&1) && IDLE_GUARD) {
   assert(event_count==3 && selected_animation==-99);
  } else {
   assert(event_count==4 && events[3]==4 && selected_animation==expected);
  }
  assert(subject.animpos==(__typeof__(+subject.animpos))position && subject.nextanim==original_deadline);
 }
 ++cases;free(new_table);new_table=NULL;
}
int main(void) {
 assert(MAX_ANIS>0 && MAX_ANIS<4096);
 for(unsigned mask=0;mask<32;++mask)for(int menu=0;menu<2;++menu)
 for(int clock_on=0;clock_on<2;++clock_on)for(int type_case=0;type_case<3;++type_case)
 for(int sync=0;sync<2;++sync)for(int slot=0;slot<2;++slot)
 for(int position=1;position<=7;position+=6)for(int inf=0;inf<@INFINITE_MODES@;++inf)
 for(int short_table=0;short_table<@TABLE_MODES@;++short_table) {
  /* The earlier unchecked destination-slot path is excluded from original
     runtime oracles. Defined bounded-core fallbacks are separate tests. */
  if(ARITY==3 && sync && !CHECKS_SLOT && !slot)continue;
  if(short_table && slot)continue;
  check_case(mask,menu,clock_on,type_case,sync,slot,position,inf,short_table);
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''
    transition=contract['select_transition']
    infinite=contract['sync_effect']=='deadline_keep_infinite'
    values={key.upper():str(value) for key,value in flags.items()}
    values.update(REVISION=str(revision),FUNCTION=source,GRAPHICS=graphics,REFUSALS=refusals,
                  HELPERS=helpers,
                  PREVIOUS_MODEL='NULL' if missing_previous_model else '&old_model',
                  EFFECT=str(effects_index[contract['sync_effect']]),ARITY=str(contract['arity']),
                  CAPACITY=str(int(native_capacity)),
                  TRANSITION_SLOT='if(mask&16)new_table[ANI_SELECTIN]=&transition_anim;' if transition else '',
                  SELECT_EXPECTATION='(mask&16)?ANI_SELECTIN:ANI_SELECT' if transition else 'ANI_SELECT',
                  NATIVE_CAPACITY=('old_model.animation_capacity=MAX_ANIS+32;'
                      'new_model.animation_capacity=table_capacity;' if native_capacity else ''),
                  PLATFORM_FLAGS='old_model.hasPlatforms=0;new_model.hasPlatforms=1;' if
                                 contract['tracks_platforms'] else '',
                  SCREEN_STATUS='fixture_screen=menu?IN_SCREEN_SELECT:0;' if contract['screen_flags'] else
                                'fixture_screen=0;',
                  INITIAL_DEADLINE='subject.nextanim=infinite?DELAY_INFINITE:501;' if infinite else
                                   '(void)infinite;subject.nextanim=501;',
                  INFINITE_MODES='2' if infinite else '1',
                  TABLE_MODES='2' if capacity_cases else '1',
                  CALL='model_switch_under_test(&subject,"next"'+(',synchronize' if function_arity==3 else '')+');')
    for key,value in values.items():program=program.replace('@'+key+'@',value)
    return program
