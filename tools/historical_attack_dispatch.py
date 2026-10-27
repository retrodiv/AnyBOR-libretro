"""Render native attack-dispatch and cooldown contracts with real records.

Provider decisions and the airborne query are explicit callback observations.
Their implementations, damage, movement and VM execution remain separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from native_header_fixtures import graphics_refusals, inline_refusals

PROVIDERS = ('common_try_grab', 'common_try_upper', 'common_try_block',
             'common_try_runattack', 'common_try_normalattack', 'common_try_jumpattack')
MODES = {'normal': 0, 'common': 1, 'cooldown': 2}


def render_attack_dispatch(parts, *, revision, think_speed, cooldown_available,
                           cases, unused_graphics_inlines=False,
                           unused_inline_declarations=None):
    if (not isinstance(parts, dict) or
            set(parts) != {'normal_attack', 'common_attack', 'recheck_nextattack'} or
            any(not isinstance(value, str) or len(value) > 65536 for value in parts.values()) or
            any(not parts[name].strip() for name in ('normal_attack', 'common_attack'))):
        raise ValueError('Bounded complete native dispatch functions required')
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            type(think_speed) is not int or not 1 <= think_speed <= 64 or
            type(cooldown_available) is not bool or
            (cooldown_available and not parts['recheck_nextattack'].strip())):
        raise ValueError('Explicit native revision, clock and cooldown contract required')
    if not isinstance(cases, list) or not 1 <= len(cases) <= 2048:
        raise ValueError('Bounded independent native dispatch cases required')
    entries = []
    keys = {'mode', 'clock', 'ai_flags', 'running', 'airborne', 'nextattack',
            'target_flags', 'providers', 'repetitions', 'result', 'running_after',
            'nextattack_after', 'trace'}
    for case in cases:
        if (not isinstance(case, dict) or set(case) != keys or
                not isinstance(case['mode'], str) or case['mode'] not in MODES or
                (case['mode'] == 'cooldown' and not cooldown_available) or
                any(type(case[key]) is not int or not 0 <= case[key] <= 0xffffffff
                    for key in ('clock', 'ai_flags', 'nextattack', 'nextattack_after', 'result')) or
                (case['mode'] != 'cooldown' and case['result'] not in (0, 1)) or
                any(type(case[key]) is not int or case[key] not in (0, 1)
                    for key in ('running', 'airborne', 'running_after')) or
                type(case['repetitions']) is not int or not 1 <= case['repetitions'] <= 2 or
                (case['mode'] != 'cooldown' and case['repetitions'] != 1)):
            raise ValueError('Explicit bounded native mode, inputs and scalar results required')
        for name, count, first, last in [('target_flags', 4, 0, 1), ('providers', 6, -1, 2)]:
            if (not isinstance(case[name], list) or len(case[name]) != count or
                    any(type(value) is not int or not first <= value <= last
                        for value in case[name])):
                raise ValueError('Explicit bounded native flags and callback results required')
        trace = case['trace']
        if (not isinstance(trace, list) or len(trace) > 8 or
                any(type(value) is not int or not 0 <= value <= 6 for value in trace)):
            raise ValueError('Explicit bounded native callback trace required')
        numbers = [MODES[case['mode']], case['running'], case['airborne'], case['repetitions']]
        unsigned = [case[name] for name in ('clock', 'ai_flags', 'nextattack', 'result',
                                          'running_after', 'nextattack_after')]
        entries.append('{%s,%s,{%s},{%s},%d,{%s}}' % (
            ','.join(map(str, numbers)), ','.join(str(value) + 'u' for value in unsigned),
            ','.join(map(str, case['target_flags'])), ','.join(map(str, case['providers'])),
            len(trace), ','.join(map(str, trace)) or '0'))
    callbacks = []
    aliases = []
    for index, name in enumerate(PROVIDERS):
        callbacks.append('static int observed_%s(entity *target) {return observe(%d,target);}'
                         % (name, index))
        aliases.append('#define %s observed_%s' % (name, name))
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
#error Native dispatch assertions must remain enabled
#endif
_Static_assert(sizeof(u32)==sizeof(uint32_t),"Explicit native clock width required");
_Static_assert(THINK_SPEED==@THINK_SPEED@,"Native think interval differs from oracle");
static const char *phase="initial";
static unsigned active_case;
#define assert(condition) do {if(!(condition)) { \
 fprintf(stderr,"Native attack dispatch mismatch: %s case=%u\n",phase,active_case);abort();}} while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *interpreter) {(void)interpreter;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *interpreter) {(void)interpreter;abort();}
@GRAPHICS@
@REFUSALS@
static entity subject,opponent,*self=&subject;
static uint32_t fixture_clock;
static int fixture_airborne;
static const int *provider_results;
static unsigned observed_trace[8],observed_count;
static void observe_call(unsigned id) {
 assert(observed_count<8);observed_trace[observed_count++]=id;
}
static int observe(unsigned id,entity *target) {
 assert(id<6 && target==NULL);observe_call(id);return provider_results[id];
}
static int observed_inair(entity *target) {
 assert(target==self);observe_call(6);return fixture_airborne;
}
@CALLBACKS@
#define time fixture_clock
#define inair observed_inair
@ALIASES@
@NORMAL@
@COMMON@
@COOLDOWN@
@UNDEF@
#undef inair
#undef time
struct dispatch_case {
 int mode,running,airborne,repetitions;
 uint32_t clock,ai_flags,nextattack,result,running_after,nextattack_after;
 int target_flags[4],providers[6];unsigned trace_count,trace[8];
};
static const struct dispatch_case cases[]={@CASES@};
int main(void) {
 for(unsigned index=0;index<sizeof(cases)/sizeof(*cases);++index) {
  active_case=index;const struct dispatch_case *test=&cases[index];
  memset(&subject,0,sizeof(subject));memset(&opponent,0,sizeof(opponent));
  subject.modeldata.aiattack=test->ai_flags;subject.running=test->running;
  subject.nextattack=test->nextattack;fixture_clock=test->clock;
  opponent.blocking=test->target_flags[0];opponent.attacking=test->target_flags[1];
  opponent.jumping=test->target_flags[2];opponent.running=test->target_flags[3];
  unsigned char target_before[sizeof(opponent)];memcpy(target_before,&opponent,sizeof(opponent));
  fixture_airborne=test->airborne;provider_results=test->providers;observed_count=0;
  phase="native function";uint32_t result=0;
  switch(test->mode) {
   case 0:result=normal_attack();break;
   case 1:result=common_attack();break;
   case 2:@RECHECK@ break;
   default:abort();
  }
  phase="result";assert(result==test->result);
  phase="running";assert(subject.running==(int)test->running_after);
  phase="cooldown";assert(subject.nextattack==test->nextattack_after);
  phase="callback trace";assert(observed_count==test->trace_count);
  for(unsigned at=0;at<observed_count;++at)assert(observed_trace[at]==test->trace[at]);
  phase="target unchanged";assert(!memcmp(target_before,&opponent,sizeof(opponent)));
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",
        (unsigned)(sizeof(cases)/sizeof(*cases)));return 0;
}
'''
    values = dict(REVISION=str(revision), THINK_SPEED=str(think_speed),
        GRAPHICS=graphics_refusals(unused_graphics_inlines),
        REFUSALS=inline_refusals(unused_inline_declarations,
            forbidden_names=(*PROVIDERS, 'normal_attack', 'common_attack', 'recheck_nextattack')),
        CALLBACKS='\n'.join(callbacks), ALIASES='\n'.join(aliases),
        UNDEF='\n'.join('#undef ' + name for name in PROVIDERS),
        NORMAL=parts['normal_attack'], COMMON=parts['common_attack'],
        COOLDOWN=parts['recheck_nextattack'], CASES=',\n'.join(entries),
        RECHECK='for(int n=0;n<test->repetitions;++n)result=recheck_nextattack(&opponent);'
            if cooldown_available else 'abort();')
    for name, value in values.items():
        code = code.replace('@' + name + '@', value)
    return code
