"""Observe the complete native jump-attack provider and its cooldown helper.

The own native records and set_attacking macro execute. Target selection,
probability, random samples, toss, spawn and animation services are explicit
observations; their implementations and complete AI remain separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import math

from native_header_fixtures import graphics_refusals, inline_refusals


def render_jump_attack(parts, *, revision, target_argument, cooldown_available,
                       throttle_time_field, animation_capacity_field,
                       game_speed, cases, unused_graphics_inlines=False,
                       unused_inline_declarations=None):
    if (not isinstance(parts, dict) or
            set(parts) != {'common_try_jumpattack', 'recheck_nextattack'} or
            any(not isinstance(s, str) or len(s) > 65536 for s in parts.values()) or
            not parts['common_try_jumpattack'].strip()):
        raise ValueError('Complete bounded native jump provider source required')
    flags = (target_argument, cooldown_available, throttle_time_field,
             animation_capacity_field)
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            type(game_speed) is not int or not 1 <= game_speed <= 10000 or
            any(type(value) is not bool for value in flags) or
            (cooldown_available and not parts['recheck_nextattack'].strip())):
        raise ValueError('Explicit native provider signature, clock and layouts required')
    if not isinstance(cases, list) or not 1 <= len(cases) <= 4096:
        raise ValueError('Bounded independent jump provider cases required')

    def numeric(value, low, high, integer=False):
        return ((type(value) is int if integer else type(value) in (int, float)) and
                low <= value <= high and math.isfinite(value))

    entries = []
    for case in cases:
        fields = {'clock', 'nextattack', 'target_argument', 'found_target',
                  'target_flags', 'vulnerable', 'available', 'direction',
                  'random_bit', 'probability', 'probability_bounds', 'throttle_time',
                  'noattack_duration', 'random', 'dust_index', 'dust_spawn',
                  'trace', 'result', 'nextattack_after', 'velocity', 'selected_animation'}
        if not isinstance(case, dict) or set(case) != fields:
            raise ValueError('Explicit complete jump inputs and result fields required')
        if (any(not numeric(case[k], 0, 0xffffffff, True) for k in
                ('clock', 'nextattack', 'nextattack_after')) or
                any(not numeric(case[k], 0, 1, True) for k in
                    ('target_argument', 'found_target', 'vulnerable', 'direction',
                     'random_bit', 'probability', 'dust_spawn', 'result')) or
                not numeric(case['dust_index'], -1, 31, True) or
                not numeric(case['selected_animation'], -1, 1, True) or
                not numeric(case['throttle_time'], 0, 10000) or
                not numeric(case['noattack_duration'], 0, 10)):
            raise ValueError('Bounded native jump fields and result values required')
        for key, length, low, high, integer in (
                ('target_flags', 5, 0, 1, True), ('available', 2, 0, 1, True),
                ('probability_bounds', 2, 0, 1, False), ('velocity', 2, -10, 10, False)):
            if (not isinstance(case[key], list) or len(case[key]) != length or
                    any(not numeric(v, low, high, integer) for v in case[key])):
                raise ValueError('Explicit bounded jump arrays required')
        random, trace = case['random'], case['trace']
        if (not isinstance(random, list) or len(random) > 1 or
                any(not isinstance(pair, list) or len(pair) != 2 or
                    not numeric(pair[0], 0, 10000) or
                    not numeric(pair[1], 0, pair[0]) for pair in random) or
                not isinstance(trace, list) or len(trace) > 8 or
                any(not numeric(v, 0, 7, True) for v in trace)):
            raise ValueError('Explicit bounded jump callback samples and trace required')
        scalars = ','.join(str(case[k]) + 'u' for k in
            ('clock', 'nextattack', 'target_argument', 'found_target', 'vulnerable',
             'direction', 'random_bit', 'probability', 'dust_spawn', 'result',
             'nextattack_after'))
        floats = ','.join(float(case[k]).hex() + 'f' for k in
                          ('throttle_time', 'noattack_duration'))
        array = lambda values: ','.join(float(v).hex() + 'f' for v in values)
        entries.append('{%s,%d,%d,%s,{%s},{%s},{%s},{%s},{%s},%d,%d,{%s}}' % (
            scalars, case['dust_index'], case['selected_animation'], floats,
            ','.join(map(str, case['target_flags'])), ','.join(map(str, case['available'])),
            array(case['probability_bounds']), array(case['velocity']),
            array(random[0] if random else [0, 0]), len(random), len(trace),
            ','.join(map(str, trace)) or '0'))

    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "openbor.h"
#undef assert
#undef printf
#undef time
#ifdef NDEBUG
#error Native jump provider assertions must remain enabled
#endif
_Static_assert(sizeof(u32)==sizeof(uint32_t),"Native clock width differs");
_Static_assert(GAME_SPEED==@GAME_SPEED@,"Native game speed differs");
_Static_assert(ANI_JUMPATTACK>=0 && ANI_JUMPATTACK2<MAX_ANIS,"Native animation extent differs");
static const char *phase="initial";
static unsigned active_case;
#define assert(c) do {if(!(c)) {fprintf(stderr,"Native jump attack mismatch: %s case=%u\n",phase,active_case);abort();}} while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
@GRAPHICS@
@REFUSALS@
struct jump_case {
 uint32_t clock,nextattack,target_argument,found_target,vulnerable,direction;
 unsigned random_bit,probability,dust_spawn,result;uint32_t nextattack_after;
 int dust_index,selected_animation;float throttle_time,noattack_duration;
 unsigned target_flags[5],available[2];float probability_bounds[2],velocity[2],random[2];
 unsigned random_count,trace_count,trace[8];
};
static const struct jump_case cases[]={@CASES@},*test;
static entity subject,opponent,dust_entity,*self=&subject;
static s_anim target_animation,jump_animations[2],*slots[MAX_ANIS];
static __typeof__(*target_animation.vulnerable) vulnerability[1];
static uint32_t fixture_clock;
static float noatk_duration;
static unsigned trace[8],trace_count,random_count,random_bit_calls;
static void observe(unsigned id) {assert(trace_count<8);trace[trace_count++]=id;}
void common_jump(void) {abort();}
static entity *observed_find(int anim,int detect) {
 assert(anim==(test->selected_animation==1?ANI_JUMPATTACK2:ANI_JUMPATTACK) && detect==0);
 observe(0);return test->found_target?&opponent:NULL;
}
static unsigned observed_random_bit(void) {
 assert(!random_bit_calls++);observe(1);return test->random_bit;
}
static int observed_chance(@CHANCE_PARAMETERS@) {
 @TARGET_CHECK@
 assert(fabsf(minimum-test->probability_bounds[0])<0.000001f);
 assert(fabsf(maximum-test->probability_bounds[1])<0.000001f);
 observe(2);return test->probability;
}
static float observed_random(float maximum) {
 assert(random_count<test->random_count && random_count<1);
 assert(fabsf(maximum-test->random[0])<0.000001f);++random_count;
 observe(3);return test->random[1];
}
static void observed_toss(entity *ent,float height) {
 assert(ent==self && height==4.0f && self->takeaction==common_jump);
 assert(self->attacking==1 && !self->idling && self->jumping==1);observe(4);
}
static entity *observed_spawn(float x,float z,float a,int direction,char *name,
                              int index,s_model *model) {
 assert(x==self->x && z==self->z && a==self->a && direction==self->direction);
 assert(!name && index==test->dust_index && !model);observe(5);
 return test->dust_spawn?&dust_entity:NULL;
}
static void observed_spawn_script(entity *ent) {
 assert(ent==&dust_entity && ent->base==self->a && ent->autokill==2);observe(6);
}
static void observed_animation(entity *ent,int animation,int reset) {
 assert(ent==self && !reset && animation==
        (test->selected_animation?ANI_JUMPATTACK2:ANI_JUMPATTACK));observe(7);
}
#define normal_find_target observed_find
#define rand32 observed_random_bit
#define check_attack_chance observed_chance
#define randf observed_random
#define toss observed_toss
#define spawn observed_spawn
#define execute_onspawn_script observed_spawn_script
#define ent_set_anim observed_animation
#define time fixture_clock
@COOLDOWN@
@PROVIDER@
#undef time
int main(void) {
 for(unsigned i=0;i<sizeof(cases)/sizeof(*cases);++i) {
  active_case=i;test=&cases[i];memset(&subject,0,sizeof(subject));
  memset(&opponent,0,sizeof(opponent));memset(&target_animation,0,sizeof(target_animation));
  memset(jump_animations,0,sizeof(jump_animations));memset(slots,0,sizeof(slots));
  memset(&dust_entity,0,sizeof(dust_entity));dust_entity.base=-9;
  subject.modeldata.animation=slots;@CAPACITY@
  for(unsigned index=0;index<2;++index)if(test->available[index]) {
   jump_animations[index].numframes=1;
   slots[index?ANI_JUMPATTACK2:ANI_JUMPATTACK]=&jump_animations[index];
  }
  @THROTTLE@
  subject.nextattack=test->nextattack;subject.direction=test->direction;
  subject.x=1.25f;subject.z=2.5f;subject.a=7;subject.xdir=3;subject.zdir=-2;
  subject.idling=1;subject.modeldata.jumpheight=4;subject.modeldata.dust[2]=test->dust_index;
  opponent.animation=&target_animation;target_animation.vulnerable=vulnerability;
  vulnerability[0]=test->vulnerable;opponent.animpos=0;
  opponent.blocking=test->target_flags[0];opponent.attacking=test->target_flags[1];
  opponent.jumping=test->target_flags[2];opponent.running=test->target_flags[3];
  opponent.drop=test->target_flags[4];
  unsigned char before[sizeof(opponent)];memcpy(before,&opponent,sizeof(opponent));
  fixture_clock=test->clock;noatk_duration=test->noattack_duration;
  trace_count=random_count=random_bit_calls=0;phase="native function";
  int result=common_try_jumpattack(test->target_argument?&opponent:NULL);
  phase="result";assert(result==(int)test->result);
  phase="timer";assert(subject.nextattack==test->nextattack_after);
  phase="action";assert(subject.takeaction==(test->result?common_jump:NULL));
  assert(subject.attacking==test->result && subject.jumping==test->result);
  assert(subject.idling==!test->result);
  phase="velocity";assert(subject.xdir==test->velocity[0] && subject.zdir==test->velocity[1]);
  phase="callback trace";assert(trace_count==test->trace_count);
  for(unsigned at=0;at<trace_count;++at)assert(trace[at]==test->trace[at]);
  assert(random_count==test->random_count);
  phase="target unchanged";assert(!memcmp(before,&opponent,sizeof(opponent)));
  phase="dust result";
  if(test->result && test->dust_index>=0 && test->dust_spawn)
   assert(dust_entity.base==subject.a && dust_entity.autokill==2);
  else assert(dust_entity.base==-9 && !dust_entity.autokill);
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",(unsigned)(sizeof(cases)/sizeof(*cases)));return 0;
}
'''
    values = dict(GAME_SPEED=str(game_speed), REVISION=str(revision),
        GRAPHICS=graphics_refusals(unused_graphics_inlines),
        REFUSALS=inline_refusals(unused_inline_declarations,
            forbidden_names=('common_try_jumpattack', 'recheck_nextattack', 'common_jump')),
        CASES=',\n'.join(entries),
        CHANCE_PARAMETERS=('entity *target,' if target_argument else '') +
                          'float minimum,float maximum',
        TARGET_CHECK='assert(target==&opponent);' if target_argument else '',
        COOLDOWN=parts['recheck_nextattack'], PROVIDER=parts['common_try_jumpattack'],
        CAPACITY='subject.modeldata.animation_capacity=MAX_ANIS;' if animation_capacity_field else '',
        THROTTLE='subject.modeldata.attackthrottletime=test->throttle_time;'
                 if throttle_time_field else '')
    for name, value in values.items():
        code = code.replace('@' + name + '@', value)
    return code
