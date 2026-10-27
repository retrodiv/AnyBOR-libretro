"""Observe native idle selection and animation transitions together.

The native target query is an observed service. Animation selection uses the
complete source caller; frame processing remains an explicit observation.
Private parameters supply expected choices, global context and state.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from historical_animation_transitions import render_animation_transition


def render_idle_animation(parts, *, revision, legacy_field, animation_capacity_field,
                          messages, transition_case, cases,
                          unused_graphics_inlines=False, unused_inline_declarations=None):
    if (not isinstance(parts,dict) or set(parts)!={'ent_set_anim','common_idle_anim'} or
            any(not isinstance(v,str) or not v.strip() or len(v)>32768 for v in parts.values())):
        raise ValueError('Two complete bounded native animation callers required')
    # Reuse the exact maintained native environment. The validated example is
    # discarded with its unused transition test table; it proves no idle result.
    base=render_animation_transition(parts['ent_set_anim'],revision=revision,
        legacy_field=legacy_field,animation_capacity_field=animation_capacity_field,
        messages=messages,cases=[transition_case],unused_graphics_inlines=unused_graphics_inlines,
        unused_inline_declarations=unused_inline_declarations)
    marker='struct transition_input {'
    if base.count(marker)!=1:
        raise ValueError('One maintained animation environment boundary required')
    prefix=base[:base.index(marker)]
    inputs=('available','health','sleep_deadline','animating','biker','none_type',
            'current_context','found','clock','sleepwait','last_frame','position')
    expected=('result','selected','current_context','frame_calls','xdir','zdir',
              'sleep','animating','last_frame','lasthit','altbase')
    if not isinstance(cases,list) or not 1<=len(cases)<=4096:
        raise ValueError('Bounded independent idle choices and context required')

    def integer(value,low,high):
        return type(value) is int and low<=value<=high

    rows=[]
    for case in cases:
        if (not isinstance(case,dict) or set(case)!=set(('inputs','order','expected','queries')) or
                not isinstance(case['inputs'],dict) or set(case['inputs'])!=set(inputs) or
                not isinstance(case['expected'],dict) or set(case['expected'])!=set(expected)):
            raise ValueError('Complete idle inputs and independently expected state required')
        a,b=case['inputs'],case['expected']
        bounds={'available':(0,31),'health':(0,1000),'sleep_deadline':(0,0xffffffff),
                'animating':(0,1),'biker':(0,1),'none_type':(0,1),'current_context':(0,2),
                'found':(0,3),'clock':(0,0xffffffff),'sleepwait':(0,32767),
                'last_frame':(-32768,32767),'position':(0,32767)}
        after={'result':(0,1),'selected':(-1,4),'current_context':(0,2),'frame_calls':(0,1),
               'xdir':(0,3),'zdir':(-2,0),'sleep':(0,0xffffffff),'animating':(0,1),
               'last_frame':(-32768,32767),'lasthit':(0,1),'altbase':(0,4)}
        if (any(not integer(a[k],*bounds[k]) for k in inputs) or
                any(not integer(b[k],*after[k]) for k in expected)):
            raise ValueError('Bounded native idle state required')
        order,queries=case['order'],case['queries']
        if (not isinstance(order,list) or len(order)>2 or
                any(not integer(v,0,2) for v in order) or
                not isinstance(queries,list) or len(queries)>len(order) or
                any(not isinstance(v,list) or len(v)!=2 or
                    not integer(v[0],1,2) or not integer(v[1],1,2) for v in queries)):
            raise ValueError('Explicit bounded alternate order and native query contexts required')
        emit=lambda values,names:','.join(str(values[k])+('u' if k in
            ('sleep_deadline','clock','sleep') else '') for k in names)
        flat_queries=[str(v) for pair in queries for v in pair]+['0']*(4-2*len(queries))
        rows.append('{{'+emit(a,inputs)+'},'+str(len(order))+',{' +
            ','.join(map(str,order+([0]*(2-len(order)))))+'},{'+emit(b,expected)+'},'+
            str(len(queries))+',{'+','.join(flat_queries)+'}}')
    code=r'''
static entity *self;
static s_model idle_model;
static s_anim idle_animations[5];
static int fixture_idle_count,fixture_idle_order[2];
static unsigned fixture_found,query_count;
static int query_animation[2],query_context[2];
static entity *observed_target(int animation,int argument){
 assert(query_count<2 && argument==0 && self);
 int slot=animation==MAX_ANIS-2?0:1;
 assert(animation==MAX_ANIS-2 || animation==MAX_ANIS-1);
 query_animation[query_count]=slot+1;query_context[query_count]=self==&subject?1:2;++query_count;
 return fixture_found&(1u<<slot)?&other:NULL;
}
#define max_idles fixture_idle_count
#define animidles fixture_idle_order
#define normal_find_target observed_target
@IDLE_SOURCE@
struct idle_input {int available,health;uint32_t sleep_deadline;int animating,biker,none_type,current_context,found;uint32_t clock;int sleepwait,last_frame,position;};
struct idle_expectation {int result,selected,current_context,frame_calls,xdir,zdir;uint32_t sleep;int animating,last_frame,lasthit,altbase;};
struct idle_case {struct idle_input inputs;int order_count,order[2];struct idle_expectation expected;unsigned query_count;int queries[4];};
static const struct idle_case tests[]={@CASES@};
int main(void){
 _Static_assert(ANI_IDLE>=0 && ANI_IDLE<MAX_ANIS-2 && ANI_FAINT>=0 && ANI_FAINT<MAX_ANIS-2 && ANI_SLEEP>=0 && ANI_SLEEP<MAX_ANIS-2,"native idle selector domain");
 const int selectors[5]={ANI_IDLE,ANI_FAINT,ANI_SLEEP,MAX_ANIS-2,MAX_ANIS-1};
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct idle_input *a=&tests[active_case].inputs;const struct idle_expectation *b=&tests[active_case].expected;
  memset(&subject,0,sizeof(subject));memset(&other,0,sizeof(other));memset(&idle_model,0,sizeof(idle_model));
  memset(idle_animations,0,sizeof(idle_animations));memset(animation_table,0,sizeof(animation_table));
  memset(&previous_animation,0,sizeof(previous_animation));memset(diagnostic,0,sizeof(diagnostic));
  for(unsigned i=0;i<5;++i){
   idle_animations[i].numframes=4;idle_animations[i].sync=-1;idle_animations[i].animhits=6;
   if(a->available&(1u<<i))animation_table[selectors[i]]=idle_animations+i;
  }
  previous_animation.numframes=4;previous_animation.sync=-1;
  subject.model=&idle_model;idle_model.subtype=a->biker?SUBTYPE_BIKER:0;idle_model.type=a->none_type?TYPE_NONE:TYPE_PLAYER;
  subject.modeldata.animation=animation_table;subject.modeldata.health=100;@CAPACITY@
  subject.modeldata.sleepwait=a->sleepwait;subject.health=a->health;strcpy(subject.name,"unit");
  subject.animation=&previous_animation;subject.animnum=ANI_WALK;subject.animpos=a->position;
  subject.sleeptime=a->sleep_deadline;subject.animating=a->animating;subject.xdir=3;subject.zdir=-2;
  subject.grabbing=&other;subject.lasthit=NULL;subject.altbase=4;@LEGACY_INIT@
  self=a->current_context==0?NULL:a->current_context==1?&subject:&other;
  fixture_clock=a->clock;fixture_found=a->found;fixture_idle_count=tests[active_case].order_count;
  for(int i=0;i<fixture_idle_count;++i){int slot=tests[active_case].order[i];fixture_idle_order[i]=slot==0?ANI_IDLE:MAX_ANIS-3+slot;}
  frame_calls=query_count=0;memset(query_animation,0,sizeof(query_animation));memset(query_context,0,sizeof(query_context));
  int result=common_idle_anim(&subject);
  assert(result==b->result && self==(b->current_context==0?NULL:b->current_context==1?&subject:&other));
  assert(subject.animation==(b->selected<0?&previous_animation:idle_animations+b->selected));
  assert(subject.animnum==(b->selected<0?ANI_WALK:selectors[b->selected]) && subject.animpos==a->position);
  assert(subject.xdir==b->xdir && subject.zdir==b->zdir && subject.sleeptime==b->sleep && subject.animating==b->animating);
  assert(subject.lasthit==(b->lasthit?&other:NULL) && subject.altbase==b->altbase);
  assert(frame_calls==(unsigned)b->frame_calls && query_count==tests[active_case].query_count && !*diagnostic);
  @LEGACY_CHECK@
  for(unsigned i=0;i<query_count;++i){assert(query_animation[i]==tests[active_case].queries[2*i] && query_context[i]==tests[active_case].queries[2*i+1]);}
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    values=dict(IDLE_SOURCE=parts['common_idle_anim'],CASES=',\n'.join(rows),
        CAPACITY='subject.modeldata.animation_capacity=MAX_ANIS;' if animation_capacity_field else '',
        LEGACY_INIT='subject.'+legacy_field+'=a->last_frame;' if legacy_field else '',
        LEGACY_CHECK='assert(subject.'+legacy_field+'==b->last_frame);' if legacy_field else '')
    return prefix+re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],code)
