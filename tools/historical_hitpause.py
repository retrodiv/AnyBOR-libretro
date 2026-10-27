"""Render source-bound hit-pause state transitions using native records.

The selected statements remain exact. Air detection is an observed service;
the complete attack caller, damage handling and gameplay are separate gates.
Expected values and source field names come from independent private JSON.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from native_header_fixtures import graphics_refusals, inline_refusals


def render_hitpause(source, *, revision, legacy_field, timer_field, cases,
                    unused_graphics_inlines=False, unused_inline_declarations=None):
    if not isinstance(source, str) or not source.strip() or len(source) > 16384:
        raise ValueError('Bounded exact native hit-pause statements required')
    if type(revision) is not int or not 0 < revision <= 0xffffffff:
        raise ValueError('Explicit source profile revision required')
    for name in (legacy_field, timer_field):
        if name is not None and (not isinstance(name, str) or
                not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,63}', name)):
            raise ValueError('Explicit native entity field identifiers required')
    if not (legacy_field or timer_field) or legacy_field == timer_field:
        raise ValueError('Distinct native frame/timer representations required')
    if not isinstance(cases, list) or not 1 <= len(cases) <= 2048:
        raise ValueError('Bounded independent hit-pause observations required')

    def integer(value, low, high):
        return type(value) is int and low <= value <= high

    entries = []
    fields = {'frame', 'last_frame', 'pause_until', 'clock', 'pause_add',
              'airborne', 'equal_airpause', 'repeat', 'timers',
              'expected_attacker_timers', 'expected_target_timers',
              'expected_last_frame', 'expected_pause_until', 'expected_air_calls'}
    scalar = ('frame', 'last_frame', 'pause_until', 'clock', 'pause_add',
              'airborne', 'equal_airpause', 'repeat', 'expected_last_frame',
              'expected_pause_until', 'expected_air_calls')
    for case in cases:
        if not isinstance(case, dict) or set(case) != fields:
            raise ValueError('Complete independently expected pause case required')
        if (any(not integer(case[k], -32768, 32767) for k in
                ('frame', 'last_frame', 'pause_add', 'expected_last_frame')) or
                any(not integer(case[k], 0, 0xffffffff) for k in
                    ('pause_until', 'clock', 'expected_pause_until')) or
                any(not integer(case[k], 0, 1) for k in ('airborne', 'equal_airpause')) or
                not integer(case['repeat'], 1, 4) or
                not integer(case['expected_air_calls'], 0, case['repeat'])):
            raise ValueError('Bounded native frame, clock and callback values required')
        for name, count in (('timers', 6), ('expected_attacker_timers', 3),
                            ('expected_target_timers', 3)):
            if (not isinstance(case[name], list) or len(case[name]) != count or
                    any(not integer(v, 0, 0xffffffff) for v in case[name])):
                raise ValueError('Explicit native timer arrays required')
        numbers = ','.join(str(case[k]) + ('u' if k in
            ('pause_until', 'clock', 'expected_pause_until') else '') for k in scalar)
        arrays = ','.join('{' + ','.join(str(v) + 'u' for v in case[k]) + '}' for k in
                          ('timers', 'expected_attacker_timers', 'expected_target_timers'))
        entries.append('{' + numbers + ',' + arrays + '}')
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef assert
#undef printf
#undef time
#ifdef NDEBUG
#error Native hit-pause assertions must remain enabled
#endif
static unsigned active_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Native hitpause contract mismatch: case=%u\n",active_case);abort();}}while(0)
_Static_assert(sizeof(u32)==sizeof(uint32_t),"Native timer width differs");
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
@GRAPHICS@
@REFUSALS@
static entity attacker,target,*self=&target;
static uint32_t fixture_clock;
static unsigned air_calls;
static int fixture_airborne,fixture_equal_airpause;
static int observed_inair(entity *ent){assert(ent==&attacker);++air_calls;return fixture_airborne;}
#undef inair
#define inair observed_inair
#define equalairpause fixture_equal_airpause
#define time fixture_clock
static void hitpause_under_test(entity *e,const s_attack *attack){
@SOURCE@
}
struct pause_case {
 int frame,last_frame;uint32_t pause_until,clock;int pause_add,airborne,equal_airpause,repeat;
 int expected_last_frame;uint32_t expected_pause_until;unsigned expected_air_calls;
 uint32_t timers[6],expected_attacker_timers[3],expected_target_timers[3];
};
static const struct pause_case tests[]={@CASES@};
int main(void){
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct pause_case *test=tests+active_case;s_attack attack={0};
  memset(&attacker,0,sizeof(attacker));memset(&target,0,sizeof(target));
  attacker.animpos=test->frame;attack.pause_add=test->pause_add;
  @LEGACY_INIT@
  @TIMER_INIT@
  attacker.toss_time=test->timers[0];attacker.nextanim=test->timers[1];attacker.nextthink=test->timers[2];
  target.toss_time=test->timers[3];target.nextanim=test->timers[4];target.nextthink=test->timers[5];
  fixture_clock=test->clock;fixture_airborne=test->airborne;fixture_equal_airpause=test->equal_airpause;
  self=&target;air_calls=0;
  for(int hit=0;hit<test->repeat;++hit)hitpause_under_test(&attacker,&attack);
  assert(attacker.animpos==test->frame && attack.pause_add==test->pause_add && self==&target);
  @LEGACY_CHECK@
  @TIMER_CHECK@
  assert(attacker.toss_time==test->expected_attacker_timers[0] &&
         attacker.nextanim==test->expected_attacker_timers[1] &&
         attacker.nextthink==test->expected_attacker_timers[2]);
  assert(target.toss_time==test->expected_target_timers[0] &&
         target.nextanim==test->expected_target_timers[1] &&
         target.nextthink==test->expected_target_timers[2]);
  assert(air_calls==test->expected_air_calls);
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    values = dict(REVISION=str(revision)+'u', SOURCE=source, CASES=',\n'.join(entries),
        GRAPHICS=graphics_refusals(unused_graphics_inlines),
        REFUSALS=inline_refusals(unused_inline_declarations,
                                forbidden_names=('inair', 'hitpause_under_test')),
        LEGACY_INIT='attacker.'+legacy_field+'=test->last_frame;' if legacy_field else '',
        TIMER_INIT='attacker.'+timer_field+'=test->pause_until;' if timer_field else '',
        LEGACY_CHECK='assert(attacker.'+legacy_field+'==test->expected_last_frame);' if legacy_field else '',
        TIMER_CHECK='assert(attacker.'+timer_field+'==test->expected_pause_until);' if timer_field else '')
    return re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],code)
