"""Observe complete frame callers with native records and explicit services.

Cases and expectations are supplied independently. Script execution, spawning,
damage, audio and rendering implementations are separate acceptance gates.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import math
import re

from native_header_fixtures import graphics_refusals, inline_refusals


INPUT_BOUNDS = dict(frame=(0, 4), animating=(0, 1), context=(0, 2),
                    child=(0, 2), handler=(0, 1), spawn=(0, 1),
                    summon=(0, 1), unsummon=(0, 1), interrupt=(0, 2),
                    clock=(0, 0xffffffff), delay=(1, 20), mode=(0, 1),
                    cap_min=(0, 20), cap_max=(0, 20), range_min=(0, 20),
                    range_max=(0, 20))
EXPECTED_BOUNDS = dict(position=(0, 4), nextanim=(0, 0xffffffff),
                       marker=(-32768, 0xffffffff), child=(0, 2),
                       animation=(0, 1), context=(0, 2), victim=(0, 2),
                       force=(0, 100), attack_type=(0, 10))


def render_frame_events(source, *, revision, legacy_field, helpers, cases,
                        unused_graphics_inlines=False,
                        unused_inline_declarations=None):
    if not isinstance(source, str) or not source.strip() or len(source) > 32768:
        raise ValueError('Complete bounded native frame caller required')
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            not isinstance(legacy_field, str) or
            not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,63}', legacy_field)):
        raise ValueError('Explicit profile and native pause/frame storage required')
    if (not isinstance(helpers, list) or len(helpers) > 4 or
            any(not isinstance(v, str) or not v.strip() or len(v) > 16384
                for v in helpers)):
        raise ValueError('Bounded complete source helpers required')
    if not isinstance(cases, list) or not 1 <= len(cases) <= 2048:
        raise ValueError('Bounded independently expected frame cases required')

    def integer(v, bounds):
        return type(v) is int and bounds[0] <= v <= bounds[1]

    def number(v):
        return type(v) in (int, float) and math.isfinite(v) and -32 <= v <= 32

    def emit(values, keys):
        return ','.join(str(values[k]) + ('u' if k in ('clock', 'nextanim') else '')
                        for k in keys)

    rows = []
    for case in cases:
        if (not isinstance(case, dict) or set(case) != {'inputs', 'expected'} or
                not isinstance(case['inputs'], dict) or
                set(case['inputs']) != set(INPUT_BOUNDS) | {'factor'} or
                not isinstance(case['expected'], dict) or
                set(case['expected']) != set(EXPECTED_BOUNDS) | {'trace', 'drop'}):
            raise ValueError('Complete independent input and expectation required')
        a, b = case['inputs'], case['expected']
        if (any(not integer(a[k], v) for k, v in INPUT_BOUNDS.items()) or
                not number(a['factor']) or
                any(not integer(b[k], v) for k, v in EXPECTED_BOUNDS.items()) or
                not isinstance(b['trace'], list) or len(b['trace']) > 8 or
                any(not integer(v, (1, 7)) for v in b['trace']) or
                not isinstance(b['drop'], list) or len(b['drop']) != 3 or
                any(not number(v) for v in b['drop'])):
            raise ValueError('Bounded frame values, services and payload required')
        rows.append('{{' + emit(a, INPUT_BOUNDS) + ',' + str(float(a['factor'])) +
                    'f},{' + emit(b, EXPECTED_BOUNDS) + ',{' +
                    ','.join(str(v) for v in b['trace'] + [0]*(8-len(b['trace']))) +
                    '},' + str(len(b['trace'])) + ',{' +
                    ','.join(str(float(v))+'f' for v in b['drop']) + '}}}')
    code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "openbor.h"
#undef printf
#undef time
#undef assert
#ifdef NDEBUG
#error Native frame assertions must remain enabled
#endif
static unsigned active_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Native frame event mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
@GRAPHICS@
@REFUSALS@
static entity subject,other,old_child,fresh_child;
static s_anim animation,replacement;
entity *self;
s_level *level;
s_attack emptyattack;
s_savedata savedata;
int max_attack_types=7;
float default_model_dropv[3]={9.0f,4.0f,2.0f};
static uint32_t fixture_clock;
static int interrupt_mode,trace[8],trace_count,victim,force,attack_type;
static float observed_drop[3];
static void record(int code){assert(trace_count<8);trace[trace_count++]=code;}
static void unexpected_service(void){fputs("Unexpected native frame service\n",stderr);abort();}
void execute_animation_script(entity *ent){
 assert(ent==&subject && self==ent);record(1);
 if(interrupt_mode==1)ent->animation=&replacement;
 if(interrupt_mode==2)ent->animpos=3;
}
void ent_spawn_ent(entity *ent){assert(ent==&subject && self==ent);record(2);}
void ent_summon_ent(entity *ent){assert(ent==&subject && self==ent);record(3);ent->subentity=&fresh_child;}
static int observed_damage(entity *ent,s_attack *attack){
 assert(self==ent && (ent==&old_child || ent==&fresh_child));
 victim=ent==&old_child?1:2;record(victim==1?4:6);
 force=attack->attack_force;attack_type=attack->attack_type;
 for(int i=0;i<3;++i)observed_drop[i]=attack->dropv[i];
 return 1;
}
void kill(entity *ent){assert(self==ent && (ent==&old_child || ent==&fresh_child));record(ent==&old_child?5:7);}
void dropweapon(int flag){(void)flag;unexpected_service();}
void set_weapon(entity *ent,int weapon,int flag){(void)ent;(void)weapon;(void)flag;unexpected_service();}
int set_idle(entity *ent){(void)ent;unexpected_service();return 0;}
int sound_play_sample(int sample,unsigned priority,int left,int right,unsigned speed){
 (void)sample;(void)priority;(void)left;(void)right;(void)speed;unexpected_service();return 0;
}
void toss(entity *ent,float lift){(void)ent;(void)lift;unexpected_service();}
entity *spawn(float x,float z,float a,int direction,char *name,int index,s_model *model){
 (void)x;(void)z;(void)a;(void)direction;(void)name;(void)index;(void)model;unexpected_service();return NULL;
}
void execute_onspawn_script(entity *ent){(void)ent;unexpected_service();}
int star_spawn(float x,float z,float a,int direction){(void)x;(void)z;(void)a;(void)direction;unexpected_service();return 0;}
entity *knife_spawn(char *name,int index,float x,float z,float a,int direction,int type,int map){
 (void)name;(void)index;(void)x;(void)z;(void)a;(void)direction;(void)type;(void)map;unexpected_service();return NULL;
}
entity *bomb_spawn(char *name,int index,float x,float z,float a,int direction,int map){
 (void)name;(void)index;(void)x;(void)z;(void)a;(void)direction;(void)map;unexpected_service();return NULL;
}
#define time fixture_clock
@HELPERS@
@SOURCE@
struct frame_input {
 int frame,animating,context,child,handler,spawn,summon,unsummon,interrupt;
 uint32_t clock;
 int delay,mode,cap_min,cap_max,range_min,range_max;
 float factor;
};
struct frame_expected {
 int position;uint32_t nextanim;int64_t marker;
 int child,animation,context,victim,force,attack_type,trace[8],trace_count;
 float drop[3];
};
struct frame_case {struct frame_input inputs;struct frame_expected expected;};
static const struct frame_case tests[]={@CASES@};
int main(void){
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct frame_input *a=&tests[active_case].inputs;
  const struct frame_expected *b=&tests[active_case].expected;
  memset(&subject,0,sizeof(subject));memset(&other,0,sizeof(other));
  memset(&old_child,0,sizeof(old_child));memset(&fresh_child,0,sizeof(fresh_child));
  memset(&animation,0,sizeof(animation));memset(&replacement,0,sizeof(replacement));
  memset(trace,0,sizeof(trace));memset(observed_drop,0,sizeof(observed_drop));
  trace_count=victim=force=attack_type=0;level=NULL;
  __typeof__(*animation.delay) delay[4]={a->delay,a->delay,a->delay,a->delay};
  __typeof__(*animation.spawnframe) spawnframe[1]={a->spawn?a->frame:-1};
  __typeof__(*animation.summonframe) summonframe[1]={a->summon?a->frame:-1};
  animation.numframes=4;animation.delay=delay;
  animation.flipframe=animation.jumpframe.f=animation.throwframe=animation.shootframe=animation.tossframe=-1;
  animation.quakeframe.framestart=-1;
  animation.spawnframe=spawnframe;animation.summonframe=summonframe;
  animation.unsummonframe=a->unsummon?a->frame:-1;animation.subentity=1;
  subject.animation=&animation;subject.animpos=1;subject.animating=a->animating;
  subject.nextanim=77;subject.@FIELD@=@INITIAL_MARKER@;
  subject.modeldata.edelay.mode=a->mode;subject.modeldata.edelay.factor=a->factor;
  subject.modeldata.edelay.cap_min=a->cap_min;subject.modeldata.edelay.cap_max=a->cap_max;
  subject.modeldata.edelay.range_min=a->range_min;subject.modeldata.edelay.range_max=a->range_max;
  old_child.health=37;fresh_child.health=59;
  old_child.dead=a->child==2;
  old_child.takedamage=fresh_child.takedamage=a->handler?observed_damage:NULL;
  subject.subentity=a->child?&old_child:NULL;
  self=a->context==0?NULL:a->context==1?&subject:&other;
  entity *incoming=self;
  fixture_clock=a->clock;interrupt_mode=a->interrupt;
  update_frame(&subject,a->frame);
  assert(subject.animpos==b->position && subject.nextanim==b->nextanim);
  assert((int64_t)subject.@FIELD@==b->marker);
  assert(subject.subentity==(b->child==0?NULL:b->child==1?&old_child:&fresh_child));
  assert(subject.animation==(b->animation?&replacement:&animation));
  assert(self==incoming && b->context==a->context);
  assert(victim==b->victim && force==b->force && attack_type==b->attack_type);
  assert(trace_count==b->trace_count);
  for(int i=0;i<trace_count;++i)assert(trace[i]==b->trace[i]);
  for(int i=0;i<3;++i)assert(fabsf(observed_drop[i]-b->drop[i])<0.00001f);
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    values = dict(REVISION=str(revision)+'u', SOURCE=source,
                  HELPERS='\n'.join(helpers), CASES=',\n'.join(rows),
                  FIELD=legacy_field, INITIAL_MARKER='9',
                  GRAPHICS=graphics_refusals(unused_graphics_inlines),
                  REFUSALS=inline_refusals(unused_inline_declarations,
                                          forbidden_names=('update_frame',)))
    return re.sub(r'@('+'|'.join(values)+r')@', lambda m: values[m[1]], code)
