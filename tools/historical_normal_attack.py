"""Render the native normal-attack provider with explicit external observations.

Target selection, attack selection, probability decisions, enumeration and random
samples are observed callbacks. The native caller and cooldown helper execute
against their own records; the observed implementations remain separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import math

from native_header_fixtures import graphics_refusals, inline_refusals


def render_normal_attack(parts, *, revision, target_argument, cooldown_available,
                         throttle_time_field, game_speed, cases,
                         unused_graphics_inlines=False,
                         unused_inline_declarations=None):
    if (not isinstance(parts, dict) or
            set(parts) != {'common_try_normalattack', 'recheck_nextattack'} or
            any(not isinstance(s, str) or len(s) > 65536 for s in parts.values()) or
            not parts['common_try_normalattack'].strip()):
        raise ValueError('Complete bounded native provider source required')
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            type(game_speed) is not int or not 1 <= game_speed <= 10000 or
            any(type(v) is not bool for v in
                (target_argument, cooldown_available, throttle_time_field)) or
            (cooldown_available and not parts['recheck_nextattack'].strip())):
        raise ValueError('Explicit native signature, clock and field contracts required')
    if not isinstance(cases, list) or not 1 <= len(cases) <= 4096:
        raise ValueError('Bounded independent native provider cases required')

    def number(value, low, high, integer=False):
        return ((type(value) is int if integer else type(value) in (int, float)) and
                low <= value <= high and math.isfinite(value))

    entries = []
    for case in cases:
        fields = {'clock', 'nextattack', 'stalltime', 'combotime', 'combo', 'target',
                  'target_flags', 'vulnerable', 'rising', 'pick', 'entity_count',
                  'aggression', 'throttle_time', 'min_chance', 'max_chance',
                  'noattack_duration', 'probability', 'probability_bounds',
                  'random', 'trace', 'result', 'nextattack_after', 'stalltime_after',
                  'prepared'}
        if not isinstance(case, dict) or set(case) != fields:
            raise ValueError('Explicit complete input and result fields required')
        if (any(not number(case[k], 0, 0xffffffff, True) for k in
                ('clock', 'nextattack', 'stalltime', 'combotime',
                 'nextattack_after', 'stalltime_after')) or
                any(not number(case[k], 0, 1, True) for k in
                    ('combo', 'target', 'vulnerable', 'rising', 'probability',
                     'result', 'prepared')) or
                not number(case['pick'], -1, 1, True) or
                not number(case['entity_count'], 1, 100, True) or
                not number(case['aggression'], -100, 300, True) or
                not number(case['throttle_time'], 0, 10000) or
                any(not number(case[k], 0, 1) for k in ('min_chance', 'max_chance')) or
                not number(case['noattack_duration'], 0, 10)):
            raise ValueError('Bounded native fields, results and timing inputs required')
        flags, bounds, random, trace = (case[k] for k in
                                         ('target_flags', 'probability_bounds', 'random', 'trace'))
        if (not isinstance(flags, list) or len(flags) != 5 or
                any(not number(v, 0, 1, True) for v in flags) or
                not isinstance(bounds, list) or len(bounds) != 2 or
                any(not number(v, 0, 1) for v in bounds) or
                not isinstance(random, list) or len(random) > 1 or
                any(not isinstance(pair, list) or len(pair) != 2 or
                    not number(pair[0], 0, 10000) or
                    not number(pair[1], 0, pair[0]) for pair in random) or
                not isinstance(trace, list) or len(trace) > 8 or
                any(not number(v, 0, 5, True) for v in trace)):
            raise ValueError('Explicit bounded flags, callback arguments and trace required')
        scalar_names = ('clock', 'nextattack', 'stalltime', 'combotime', 'combo',
                        'target', 'vulnerable', 'rising', 'pick', 'entity_count',
                        'aggression', 'probability', 'result', 'nextattack_after',
                        'stalltime_after', 'prepared')
        scalars = ','.join(str(case[k]) + ('u' if k not in ('pick', 'aggression') else '')
                           for k in scalar_names)
        floats = ','.join(float(case[k]).hex() + 'f' for k in
                          ('throttle_time', 'min_chance', 'max_chance', 'noattack_duration'))
        pair = random[0] if random else [0, 0]
        entries.append('{%s,%s,{%s},{%s},{%s},%d,%d,{%s}}' % (
            scalars, floats, ','.join(map(str, flags)),
            ','.join(float(v).hex() + 'f' for v in bounds),
            ','.join(float(v).hex() + 'f' for v in pair), len(random), len(trace),
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
#error Native provider assertions must remain enabled
#endif
_Static_assert(sizeof(u32)==sizeof(uint32_t),"Native clock width differs");
_Static_assert(GAME_SPEED==@GAME_SPEED@,"Native game speed differs");
static const char *phase="initial";
static unsigned active_case;
#define assert(c) do {if(!(c)) {fprintf(stderr,"Native normal attack mismatch: %s case=%u\n",phase,active_case);abort();}} while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
@GRAPHICS@
@REFUSALS@
struct provider_case {
 uint32_t clock,nextattack,stalltime,combotime,combo,target,vulnerable,rising;
 int pick;unsigned entity_count;int aggression;
 unsigned probability,result;uint32_t nextattack_after,stalltime_after;unsigned prepared;
 float throttle_time,min_chance,max_chance,noattack_duration;
 unsigned target_flags[5];float probability_bounds[2],random[2];
 unsigned random_count,trace_count,trace[8];
};
static const struct provider_case cases[]={@CASES@},*test;
static entity subject,opponent,*self=&subject;
static s_anim animation;
static __typeof__(*animation.vulnerable) vulnerability[1];
static uint32_t fixture_clock;
static float min_noatk_chance,max_noatk_chance,noatk_duration;
static unsigned trace[8],trace_count,random_count;
static void observe(unsigned id) {assert(trace_count<8);trace[trace_count++]=id;}
void normal_prepare(void) {abort();}
void common_rise(void) {abort();}
static entity *observed_find(int anim,int detect) {
 assert(anim==-1 && detect==0);observe(0);return test->target?&opponent:NULL;
}
static int observed_pick(entity *target,int reset) {
 assert(target==&opponent && reset==1);observe(1);return test->pick;
}
static int observed_count(int type) {
 assert(type==TYPE_ENEMY);observe(2);return test->entity_count;
}
static int observed_chance(@CHANCE_PARAMETERS@) {
 @TARGET_CHECK@
 assert(fabsf(minimum-test->probability_bounds[0])<0.000001f);
 assert(fabsf(maximum-test->probability_bounds[1])<0.000001f);
 observe(3);return test->probability;
}
static float observed_random(float maximum) {
 assert(random_count<test->random_count && random_count<1);
 assert(fabsf(maximum-test->random[0])<0.000001f);++random_count;
 observe(4);return test->random[1];
}
static void observed_idle(entity *target) {assert(target==self);observe(5);}
#define normal_find_target observed_find
#define pick_random_attack observed_pick
#define count_ents observed_count
#define check_attack_chance observed_chance
#define randf observed_random
#define set_idle observed_idle
#define time fixture_clock
@COOLDOWN@
@PROVIDER@
#undef time
int main(void) {
 for(unsigned i=0;i<sizeof(cases)/sizeof(*cases);++i) {
  active_case=i;test=&cases[i];memset(&subject,0,sizeof(subject));
  memset(&opponent,0,sizeof(opponent));memset(&animation,0,sizeof(animation));
  subject.modeldata.type=TYPE_ENEMY;subject.modeldata.aggression=test->aggression;
  @THROTTLE@
  subject.nextattack=test->nextattack;subject.stalltime=test->stalltime;
  subject.combotime=test->combotime;subject.combostep[0]=test->combo;
  subject.xdir=3;subject.zdir=-2;subject.idling=1;subject.attacking=0;
  opponent.animation=&animation;animation.vulnerable=vulnerability;
  vulnerability[0]=test->vulnerable;opponent.animpos=0;
  opponent.blocking=test->target_flags[0];opponent.attacking=test->target_flags[1];
  opponent.jumping=test->target_flags[2];opponent.running=test->target_flags[3];
  opponent.drop=test->target_flags[4];opponent.takeaction=test->rising?common_rise:NULL;
  unsigned char before[sizeof(opponent)];memcpy(before,&opponent,sizeof(opponent));
  fixture_clock=test->clock;min_noatk_chance=test->min_chance;
  max_noatk_chance=test->max_chance;noatk_duration=test->noattack_duration;
  trace_count=random_count=0;phase="native function";
  int result=common_try_normalattack(NULL);
  phase="result";assert(result==(int)test->result);
  phase="timer";assert(subject.nextattack==test->nextattack_after);
  assert(subject.stalltime==test->stalltime_after);
  phase="prepared action";
  assert(subject.takeaction==(test->prepared?normal_prepare:NULL));
  assert(subject.attacking==(test->prepared?-1:0));
  assert(subject.idling==(test->prepared?0:1));
  assert(subject.xdir==(test->prepared?0:3));assert(subject.zdir==(test->prepared?0:-2));
  phase="callback trace";assert(trace_count==test->trace_count);
  for(unsigned at=0;at<trace_count;++at)assert(trace[at]==test->trace[at]);
  assert(random_count==test->random_count);
  phase="target unchanged";assert(!memcmp(before,&opponent,sizeof(opponent)));
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",(unsigned)(sizeof(cases)/sizeof(*cases)));return 0;
}
'''
    values = dict(GAME_SPEED=str(game_speed), REVISION=str(revision),
        GRAPHICS=graphics_refusals(unused_graphics_inlines),
        REFUSALS=inline_refusals(unused_inline_declarations,
            forbidden_names=('common_try_normalattack', 'recheck_nextattack',
                             'normal_prepare', 'common_rise')),
        CASES=',\n'.join(entries),
        CHANCE_PARAMETERS=('entity *target,' if target_argument else '') +
                          'float minimum,float maximum',
        TARGET_CHECK='assert(target==&opponent);' if target_argument else '',
        COOLDOWN=parts['recheck_nextattack'], PROVIDER=parts['common_try_normalattack'],
        THROTTLE='subject.modeldata.attackthrottletime=test->throttle_time;'
                 if throttle_time_field else '')
    for name, value in values.items():
        code = code.replace('@' + name + '@', value)
    return code
