"""Render native attack-probability contracts with explicit source oracles.

The native distance helper and complete decision function are retained. Random
samples and entity counts are observed inputs; callers and the RNG are separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from historical_model_defense import number
from native_header_fixtures import graphics_refusals, inline_refusals


def render_attack_probability(parts, *, revision, target_argument, throttle_field,
                              cases, unused_graphics_inlines=False,
                              unused_inline_declarations=None):
    if (not isinstance(parts, dict) or set(parts) != {'check_attack_chance', 'diff'}
            or any(not isinstance(value, str) or not value.strip() or len(value) > 65536
                   for value in parts.values())):
        raise ValueError('Complete bounded native probability and distance functions required')
    if type(revision) is not int or not 0 < revision <= 0xffffffff:
        raise ValueError('Explicit native revision required')
    if any(type(flag) is not bool for flag in (target_argument, throttle_field)):
        raise ValueError('Explicit native signature and throttle-field layout required')
    if not isinstance(cases, list) or not 1 <= len(cases) <= 512:
        raise ValueError('Bounded independent probability cases required')
    entries = []
    float_fields = ('x', 'z', 'destx', 'destz', 'screenx', 'minimum', 'maximum',
                    'sample', 'move_factor', 'group_factor', 'offscreen_factor', 'throttle')
    integer_fields = ('width', 'height', 'entity_count', 'ai_flags', 'expected',
                      'random_calls', 'count_calls')
    for case in cases:
        if not isinstance(case, dict) or set(case) != set(float_fields + integer_fields):
            raise ValueError('Explicit probability inputs, result and callback counts required')
        values = {key: number(case[key]) for key in float_fields}
        if (any(abs(case[key]) > 32768 for key in float_fields) or
                not 0 <= case['minimum'] <= case['maximum'] <= 1 or
                not 0 <= case['sample'] <= 1 or
                any(not 0 <= case[key] <= 1 for key in ('offscreen_factor', 'throttle')) or
                any(not 0 <= case[key] <= 16 for key in ('move_factor', 'group_factor')) or
                any(type(case[key]) is not int for key in integer_fields) or
                any(not 1 <= case[key] <= 4096 for key in ('width', 'height')) or
                not 1 <= case['entity_count'] <= 256 or
                not 0 <= case['ai_flags'] <= 0xffffffff or
                any(case[key] not in (0, 1) for key in ('expected', 'random_calls')) or
                not 0 <= case['count_calls'] <= 2):
            raise ValueError('Probability inputs and observations must remain within declared limits')
        entries.append('{' + ','.join([values[key] for key in float_fields] +
                                      [str(case[key]) for key in integer_fields]) + '}')
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef assert
#undef printf
#ifdef NDEBUG
#error Native probability assertions must remain enabled
#endif
static const char *phase="initial";
static unsigned active_case;
#define assert(condition) do {if(!(condition)) { \
 fprintf(stderr,"Native attack probability mismatch: %s case=%u\n",phase,active_case);abort();}} while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *interpreter) {(void)interpreter;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *interpreter) {(void)interpreter;abort();}
@GRAPHICS@
@REFUSALS@
static entity subject,opponent,*self=&subject;
static s_videomodes videomodes;
static float fixture_screenx,fixture_sample;
static int fixture_entity_count;
static unsigned random_calls,count_calls;
static float move_noatk_factor,group_noatk_factor,offscreen_noatk_factor;
static float observed_random(float maximum) {
 assert(maximum==1.0f && !random_calls);++random_calls;return fixture_sample;
}
static int observed_count(int types) {
 assert(types==TYPE_ENEMY && count_calls<2);++count_calls;return fixture_entity_count;
}
#undef screenx
#define screenx fixture_screenx
#define randf observed_random
#define count_ents observed_count
@DISTANCE@
@DECISION@
#undef randf
#undef count_ents
#undef screenx
struct probability_case {
 float x,z,destx,destz,screenx,minimum,maximum,sample;
 float move_factor,group_factor,offscreen_factor,throttle;
 unsigned width,height,entity_count,ai_flags,expected,random_calls,count_calls;
};
static const struct probability_case cases[]={@CASES@};
int main(void) {
 for(unsigned index=0;index<sizeof(cases)/sizeof(*cases);++index) {
  active_case=index;
  const struct probability_case *test=&cases[index];
  memset(&subject,0,sizeof(subject));memset(&opponent,0,sizeof(opponent));
  subject.x=test->x;subject.z=test->z;subject.destx=test->destx;subject.destz=test->destz;
  subject.modeldata.type=TYPE_ENEMY;subject.modeldata.aiattack=test->ai_flags;
  @THROTTLE@
  videomodes.hRes=test->width;videomodes.vRes=test->height;
  fixture_screenx=test->screenx;fixture_sample=test->sample;
  fixture_entity_count=test->entity_count;random_calls=count_calls=0;
  move_noatk_factor=test->move_factor;group_noatk_factor=test->group_factor;
  offscreen_noatk_factor=test->offscreen_factor;
  phase="native function";int result=check_attack_chance(@ARGUMENTS@);
  phase="decision";
  assert(result==(int)test->expected);
  phase="random observation";assert(random_calls==test->random_calls);
  phase="entity-count observation";assert(count_calls==test->count_calls);
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",
        (unsigned)(sizeof(cases)/sizeof(*cases)));return 0;
}
'''
    values = dict(REVISION=str(revision), DISTANCE=parts['diff'],
        DECISION=parts['check_attack_chance'], CASES=',\n'.join(entries),
        GRAPHICS=graphics_refusals(unused_graphics_inlines),
        REFUSALS=inline_refusals(unused_inline_declarations,
            forbidden_names=('check_attack_chance', 'diff', 'observed_random', 'observed_count')),
        THROTTLE='subject.modeldata.attackthrottle=test->throttle;' if throttle_field else '',
        ARGUMENTS=('&opponent,' if target_argument else '') + 'test->minimum,test->maximum')
    for name, value in values.items():
        code = code.replace('@' + name + '@', value)
    return code
