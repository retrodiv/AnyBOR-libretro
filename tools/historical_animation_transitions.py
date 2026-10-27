"""Observe complete native animation selection with real entity records.

Frame updates are recorded without implementing their effects. Diagnostics,
expected state and the native legacy field come from independent parameters;
this contract does not approve frame loading, scripts or gameplay.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re

from native_header_fixtures import graphics_refusals, inline_refusals


def render_animation_transition(source, *, revision, legacy_field,
                                animation_capacity_field, messages, cases,
                                unused_graphics_inlines=False,
                                unused_inline_declarations=None):
    if not isinstance(source,str) or not source.strip() or len(source)>32768:
        raise ValueError('Complete bounded native animation transition required')
    if (type(revision) is not int or not 0<revision<=0xffffffff or
            type(animation_capacity_field) is not bool or
            (legacy_field is not None and (not isinstance(legacy_field,str) or
             not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,63}',legacy_field)))):
        raise ValueError('Explicit native profile, capacity and legacy field required')
    keys=('missing_entity','invalid_index','missing_animation')
    if (not isinstance(messages,dict) or set(messages)!=set(keys) or
            any(not isinstance(v,str) or not 0<len(v)<=255 for v in messages.values())):
        raise ValueError('Three bounded independent native diagnostic patterns required')
    for key in keys:
        pattern=messages[key]
        tokens=re.findall(r'%%|%[sdi]',pattern)
        if ('%' in re.sub(r'%%|%[sdi]','',pattern) or
                [v for v in tokens if v!='%%'] not in
                ([[]] if key=='missing_entity' else [['%s','%i'],['%s','%d']])):
            raise ValueError('Native diagnostic argument types must remain explicit')
    inputs=('entity_present','index_mode','slot','frames','previous','previous_sync',
            'target_sync','position','resetable','clock','sleepwait','last_frame')
    expected=('animation','animnum','position','sleep','animhits','animating',
              'lasthit','altbase','last_frame','frame_calls','diagnostic_kind')
    if not isinstance(cases,list) or not 1<=len(cases)<=2048:
        raise ValueError('Bounded independently expected transition cases required')

    def integer(value,low,high):
        return type(value) is int and low<=value<=high

    rows=[]
    for case in cases:
        if (not isinstance(case,dict) or set(case)!={'inputs','expected'} or
                not isinstance(case['inputs'],dict) or set(case['inputs'])!=set(inputs) or
                not isinstance(case['expected'],dict) or set(case['expected'])!=set(expected)):
            raise ValueError('Complete native inputs and independent expected state required')
        a,b=case['inputs'],case['expected']
        bounds={'entity_present':(0,1),'index_mode':(0,3),'slot':(0,1),'frames':(0,8),
                'previous':(0,2),'previous_sync':(-1,8),'target_sync':(-1,8),
                'position':(0,32767),'resetable':(0,1),'clock':(0,0xffffffff),
                'sleepwait':(-32768,32767),'last_frame':(-32768,32767)}
        after={'animation':(0,2),'animnum':(-1,1),'position':(0,32767),
               'sleep':(0,0xffffffff),'animhits':(0,6),'animating':(0,1),
               'lasthit':(0,1),'altbase':(0,4),'last_frame':(-32768,32767),
               'frame_calls':(0,1),'diagnostic_kind':(0,3)}
        if (any(not integer(a[k],*bounds[k]) for k in inputs) or
                any(not integer(b[k],*after[k]) for k in expected)):
            raise ValueError('Bounded native animation state and callback expectations required')
        emit=lambda values,names:','.join(str(values[k])+('u' if k in ('clock','sleep') else '') for k in names)
        rows.append('{{'+emit(a,inputs)+'},{'+emit(b,expected)+'}}')
    code=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "openbor.h"
#undef printf
#undef time
#undef assert
#ifdef NDEBUG
#error Native animation transition assertions must remain enabled
#endif
static unsigned active_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Native animation transition mismatch: case=%u\n",active_case);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
@GRAPHICS@
@REFUSALS@
static entity subject,other;
static s_anim previous_animation,next_animation;
static s_anim *animation_table[MAX_ANIS];
static unsigned frame_calls;
static uint32_t fixture_clock;
static int fixture_max_animations=MAX_ANIS;
static char diagnostic[512];
static int observed_printf(const char *format,...){
 size_t length=strlen(diagnostic);va_list args;va_start(args,format);
 int count=vsnprintf(diagnostic+length,sizeof(diagnostic)-length,format,args);va_end(args);
 assert(count>=0 && (size_t)count<sizeof(diagnostic)-length);return count;
}
static void observed_frame(entity *ent,int frame){assert(ent==&subject && frame==0);++frame_calls;}
#define time fixture_clock
#define max_animations fixture_max_animations
#define update_frame observed_frame
#define printf observed_printf
@SOURCE@
#undef printf
struct transition_input {int entity_present,index_mode,slot,frames,previous,previous_sync,target_sync,position,resetable;uint32_t clock;int sleepwait,last_frame;};
struct transition_expectation {int animation,animnum,position;uint32_t sleep;int animhits,animating,lasthit,altbase,last_frame,frame_calls,diagnostic_kind;};
struct transition_case {struct transition_input inputs;struct transition_expectation expected;};
static const struct transition_case tests[]={@CASES@};
static const char *messages[]={"",@MESSAGES@};
int main(void){
 _Static_assert(ANI_IDLE>=0 && ANI_IDLE<MAX_ANIS && ANI_SLEEP>=0 && ANI_SLEEP<MAX_ANIS,"native animation selectors");
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct transition_input *a=&tests[active_case].inputs;
  const struct transition_expectation *b=&tests[active_case].expected;
  memset(&subject,0,sizeof(subject));memset(&other,0,sizeof(other));
  memset(&previous_animation,0,sizeof(previous_animation));memset(&next_animation,0,sizeof(next_animation));
  memset(animation_table,0,sizeof(animation_table));memset(diagnostic,0,sizeof(diagnostic));frame_calls=0;
  int index=a->index_mode==0?ANI_IDLE:a->index_mode==1?ANI_SLEEP:a->index_mode==2?-1:MAX_ANIS;
  if(index>=0 && index<MAX_ANIS && a->slot)animation_table[index]=&next_animation;
  previous_animation.sync=a->previous_sync;previous_animation.numframes=4;
  next_animation.sync=a->target_sync;next_animation.numframes=a->frames;next_animation.animhits=6;
  subject.animation=a->previous==0?NULL:a->previous==1?&previous_animation:&next_animation;
  subject.modeldata.animation=animation_table;@CAPACITY@
  strcpy(subject.name,"unit");subject.modeldata.sleepwait=a->sleepwait;
  subject.animpos=a->position;subject.animnum=ANI_WALK;subject.sleeptime=44;
  subject.grabbing=&other;subject.lasthit=NULL;subject.altbase=4;subject.animating=0;
  @LEGACY_INIT@
  fixture_clock=a->clock;
  ent_set_anim(a->entity_present?&subject:NULL,index,a->resetable);
  s_anim *expected_animation=b->animation==0?NULL:b->animation==1?&previous_animation:&next_animation;
  int expected_animnum=b->animnum==-1?ANI_WALK:b->animnum==0?ANI_IDLE:ANI_SLEEP;
  assert(subject.animation==expected_animation && subject.animnum==expected_animnum && subject.animpos==b->position);
  assert(subject.sleeptime==b->sleep && next_animation.animhits==b->animhits && subject.animating==b->animating);
  assert(subject.lasthit==(b->lasthit?&other:NULL) && subject.altbase==b->altbase);
  assert(frame_calls==(unsigned)b->frame_calls && subject.grabbing==&other);
  @LEGACY_CHECK@
  char expected_diagnostic[512];int length=snprintf(expected_diagnostic,sizeof(expected_diagnostic),messages[b->diagnostic_kind],"unit",index);
  assert(length>=0 && (size_t)length<sizeof(expected_diagnostic) && !strcmp(diagnostic,expected_diagnostic));
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    values=dict(REVISION=str(revision)+'u',SOURCE=source,CASES=',\n'.join(rows),
        MESSAGES=','.join(json.dumps(messages[k]) for k in keys),
        GRAPHICS=graphics_refusals(unused_graphics_inlines),
        REFUSALS=inline_refusals(unused_inline_declarations,
                                forbidden_names=('ent_set_anim','update_frame')),
        CAPACITY='subject.modeldata.animation_capacity=MAX_ANIS;' if animation_capacity_field else '',
        LEGACY_INIT='subject.'+legacy_field+'=a->last_frame;' if legacy_field else '',
        LEGACY_CHECK='assert(subject.'+legacy_field+'==b->last_frame);' if legacy_field else '')
    return re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],code)
