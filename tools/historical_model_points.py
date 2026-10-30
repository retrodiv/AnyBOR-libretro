"""Render source-bound guard and juggle point stores and arithmetic windows.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from test_historical_player import function
from test_early_jump_walkoff import braced_statement


def render_model_points(engine, fixture):
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    attack = function(core, 'do_attack')
    clean = re.sub(r'/\*.*?\*/|//[^\r\n]*', '', attack, flags=re.S)
    juggle_gate = next(line.strip().rstrip('&').strip() for line in clean.splitlines()
                       if 'falling == 0 && attack->jugglecost' in line)
    guard_gates = [line.strip().rstrip('&').strip() for line in clean.splitlines()
                   if 'guardpoints.maximum == 0' in line]
    if len(guard_gates) != 2:
        raise ValueError('Two native block admission predicates required')
    juggle_spend = re.search(r'if\(inair\(self\)\) self->modeldata\.jugglepoints\.current[^;]+;', clean)[0]
    guard_spends = re.findall(r'if\(self->modeldata\.guardpoints\.maximum > 0\) self->modeldata\.guardpoints\.current[^;]+;', clean)
    if len(guard_spends) != 2:
        raise ValueError('Two native guard deduction statements required')
    recovery = braced_statement(function(core, 'update_health'),
                               'if(self->modeldata.guardpoints.maximum > 0 && time >= self->guardtime)')
    resets = [re.search(r'iRise(?:attack)?->modeldata\.jugglepoints\.current[^;]+;',
                       function(core, name))[0] for name in ('set_rise', 'set_riseattack')]
    pain = function(core, 'set_pain')
    pain_gate = re.search(r'if\(iPain->modeldata\.guardpoints\.maximum > 0[^\r\n]+pain = ANI_GUARDBREAK;', pain)[0]
    pain_reset = re.search(r'if\(iPain->modeldata\.guardpoints\.maximum > 0[^\r\n]+iPain->modeldata\.guardpoints\.current = iPain->modeldata\.guardpoints\.maximum;', pain)[0]
    drop = re.search(r'if\(self->modeldata\.guardpoints\.maximum > 0[^\r\n]+attackdrop = 0;', function(core, 'checkdamagedrop'))[0]
    damage = re.search(r'if\(self->modeldata\.guardpoints\.maximum > 0[^\r\n]+force = 0;', function(core, 'checkdamage'))[0]
    effects = re.search(r'if\(!\(self->modeldata\.guardpoints\.maximum > 0[^\r\n]+checkdamageeffects\(attack\);', function(core, 'common_takedamage'))[0]
    names = ('guardpoints', 'maxguardpoints', 'jugglepoints', 'maxjugglepoints')
    getters = [braced_statement(script, 'case _gep_' + n + ':') for n in names]
    setters = [braced_statement(script, 'case _cep_' + n + ':') for n in names]
    def body(case):
        return case[case.index('{'):]
    get_cases = '\n'.join('case %d:%s' % (i, body(c)) for i, c in enumerate(getters))
    set_cases = '\n'.join('case %d:%s' % (i, body(c)) for i, c in enumerate(setters))
    loads = []
    for name in ('GUARDPOINTS', 'JUGGLEPOINTS'):
        label = 'case CMD_MODEL_' + name + ':'
        if core.count(label) != 1:
            raise ValueError('Exactly one model point command required')
        rest = core[core.index(label) + len(label):]
        loads.append(rest[:re.search(r'\bcase CMD_MODEL_\w+:', rest).start()])
    variants = '\n'.join(function(variant, name) for name in
                         ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue'))
    numbers = ','.join('{%d,%d}' % (r['input'], r['signed16']) for r in fixture['cases'])
    contexts = ','.join('{%d,%d}' % (r['revision'], r['point_bits']) for r in fixture['sources'])
    program = r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef exit
#undef time
#undef pause
#undef shutdown
#undef kill
uint32_t obor_profile_build;
static entity actor,*self=&actor,*ent_list[]={&actor};
static unsigned int time;
static int effect_calls;
CHAR *StrCache_Get(int index){(void)index;abort();}
void StrCache_Collect(int index){(void)index;abort();}
int StrCache_Pop(void){abort();}
@VARIANTS@
@PHYSICS@
static void set(int property,int value){
 entity *ent=self;ScriptVariant input={0},result={0},*out=&result,**pretvar=&out,*varlist[]={NULL,NULL,&input};LONG ltemp;
 input.vt=VT_INTEGER;input.lVal=value;switch(property){@SETTERS@ default:assert(0);}
 assert(result.lVal==1);
}
static int get(int property){
 entity *ent=self;ScriptVariant result={0},*out=&result,**pretvar=&out;
 switch(property){@GETTERS@ default:assert(0);}assert(result.vt==VT_INTEGER);return (int)result.lVal;
}
static void load(int family,int input){
 s_model *newchar=&actor.modeldata;char number[32],*value;snprintf(number,sizeof(number),"%d",input);
#define GET_ARG(i) (assert((i)==1),number)
 if(family){do{@LOADJ@}while(0);}else{do{@LOADG@}while(0);}
#undef GET_ARG
}
static int juggle_allowed(s_attack *attack){int i=0;return @JUGGLEGATE@;}
static int guard_allowed(int which){return which?@GUARDGATE1@:@GUARDGATE0@;}
static void spend(s_attack *attack,int which){if(which<0){@JUGGLESPEND@}else if(which){@GUARDSPEND1@}else{@GUARDSPEND0@}}
static void recover(void){@RECOVERY@}
static void rise(int which){entity *iRise=self,*iRiseattack=self;if(which){@RISE1@}else{@RISE0@}}
static int pain_reset(void){entity *iPain=self;int pain=123;@PAINGATE@ @PAINRESET@ return pain;}
void checkdamageeffects(s_attack *attack){(void)attack;++effect_calls;}
static void guard_break(int *drop,int *damage,s_attack *attack){int attackdrop=9,force=7;effect_calls=0;@DROP@ @DAMAGE@ @EFFECTS@ *drop=attackdrop;*damage=force;}
static const struct {int input,v16;} numbers[]={@NUMBERS@};
static const struct {unsigned revision;int bits;} contexts[]={@CONTEXTS@};
static int expected(unsigned i,int bits){return bits==16?numbers[i].v16:numbers[i].input;}
static int convert_defined(long long value,int bits){assert(value>=INT_MIN && value<=INT_MAX);return bits==16?(short)value:(int)value;}
int main(void){
 assert(sizeof(int)==4 && sizeof(short)==2);const unsigned count=sizeof(numbers)/sizeof(numbers[0]);
 const int costs[]={-32768,-2,-1,0,1,2,7,32767};s_attack attack;memset(&attack,0,sizeof(attack));
 for(unsigned p=0;p<sizeof(contexts)/sizeof(contexts[0]);++p){
  obor_profile_build=contexts[p].revision;int bits=contexts[p].bits;assert(bits==16 || bits==32);
  // Candidate-only arithmetic beyond the original int domain has a defined store.
  assert(obor_model_points_value(2147483648LL,obor_profile_build)==(bits==32?INT_MIN:0));
  assert(obor_model_points_value(-2147483649LL,obor_profile_build)==(bits==32?INT_MAX:-1));
  for(unsigned n=0;n<count;++n){
   int value=expected(n,bits);for(int family=0;family<2;++family){load(family,numbers[n].input);assert(get(2*family)==value && get(2*family+1)==value);}
   for(int field=0;field<4;++field){set(field,numbers[n].input);assert(get(field)==value);}
   for(unsigned m=0;m<count;++m){
    int maximum=expected(m,bits),guard=maximum==0 || (maximum>0 && value>0);
    set(0,numbers[n].input);set(1,numbers[m].input);set(2,numbers[n].input);set(3,numbers[m].input);
    assert(guard_allowed(0)==guard && guard_allowed(1)==guard);
    int dropped,damaged,broken=maximum>0 && value<=0;guard_break(&dropped,&damaged,&attack);
    assert(dropped==(broken?0:9) && damaged==(broken?0:7) && effect_calls==!broken);
    assert(pain_reset()==(broken?ANI_GUARDBREAK:123));assert(get(0)==(broken?maximum:value));
    for(int which=0;which<2;++which){set(2,numbers[n].input);rise(which);assert(get(2)==maximum);}
    for(unsigned k=0;k<sizeof(costs)/sizeof(costs[0]);++k){
     int cost=costs[k];attack.jugglecost=attack.guardcost=cost;
     for(int falling=0;falling<2;++falling){actor.falling=falling;set(2,numbers[n].input);assert(juggle_allowed(&attack)==(falling?cost<=value:cost>=0));}
     long long raw=(long long)value-cost;if(raw<INT_MIN || raw>INT_MAX)continue;
     for(int air=0;air<2;++air){set(2,numbers[n].input);actor.base=0;actor.a=air;spend(&attack,-1);assert(get(2)==(air?convert_defined(raw,bits):value));}
     for(int which=0;which<2;++which){set(0,numbers[n].input);spend(&attack,which);assert(get(0)==(maximum>0?convert_defined(raw,bits):value));}
    }
    const int rates[]={0,1,2,3,127};
    for(unsigned r=0;r<sizeof(rates)/sizeof(rates[0]);++r)for(int block=0;block<2;++block)for(int due=0;due<2;++due){
     int amount=block?rates[r]/2:rates[r];long long raw=(long long)value+amount;if(raw<INT_MIN || raw>INT_MAX)continue;
     set(0,numbers[n].input);actor.modeldata.guardrate=rates[r];actor.blocking=block;time=100;actor.guardtime=due?100:101;
     int want=value;if(maximum>0 && due){want=convert_defined(raw,bits);if(want>maximum)want=maximum;}
     recover();assert(get(0)==want && actor.guardtime==(unsigned)(maximum>0 && due?100+GAME_SPEED:due?100:101));
    }
   }
  }
 }
 printf("model point contexts: %zu\n",sizeof(contexts)/sizeof(contexts[0]));return 0;
}
'''
    replacements = dict(VARIANTS=variants, PHYSICS=function(core, 'diff') + '\n' + function(core, 'inair'),
                        SETTERS=set_cases, GETTERS=get_cases, LOADJ=loads[1], LOADG=loads[0],
                        JUGGLEGATE=juggle_gate, GUARDGATE0=guard_gates[0], GUARDGATE1=guard_gates[1],
                        JUGGLESPEND=juggle_spend, GUARDSPEND0=guard_spends[0], GUARDSPEND1=guard_spends[1],
                        RECOVERY=recovery, RISE0=resets[0], RISE1=resets[1], PAINGATE=pain_gate,
                        PAINRESET=pain_reset, DROP=drop, DAMAGE=damage, EFFECTS=effects,
                        NUMBERS=numbers, CONTEXTS=contexts)
    for name, text in replacements.items():
        program = program.replace('@' + name + '@', text)
    return program
