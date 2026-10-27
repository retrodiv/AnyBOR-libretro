"""Observe complete native attack callers with independent event expectations.

Only the declared ground-hit, manual-block and item paths execute. Collision,
damage, animation and script services record their arguments; their complete
implementations and gameplay remain separate acceptance gates.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from native_header_fixtures import graphics_refusals, inline_refusals


INPUT_BOUNDS = dict(kind=(0,1),hit=(0,1),cancel=(0,1),damage=(0,1),manual_block=(0,1),
                    follow=(0,4),hostile=(0,1),allow_grab=(0,1),noslow=(0,1),
                    hitsound=(-1,15),beat=(-1,15),blocksound=(-1,15),
                    indirect=(-1,15),projectile=(0,1),nextattack=(0,200))
EXPECTED_BOUNDS = dict(context=(0,1),follow=(0,1),nextattack=(0,200),hit_id=(0,17),
                       hits=(0,1),subtype=(3,7),didhit_type=(-1,15),
                       didhit_blocked=(-1,1),sound=(-1,15),speed=(0,200),
                       pain=(0,107),paused=(0,1),guard=(0,100),rush=(0,1))


def render_attack_events(source, *, revision, factor_layout, animation_capacity_field,
                         legacy_field, helpers, cases, unused_graphics_inlines=False,
                         unused_inline_declarations=None):
    if not isinstance(source,str) or not source.strip() or len(source)>65536:
        raise ValueError('Complete bounded native attack caller required')
    if (type(revision) is not int or not 0<revision<=0xffffffff or
            factor_layout not in ('parallel','record') or type(animation_capacity_field) is not bool or
            (legacy_field is not None and (not isinstance(legacy_field,str) or
             not re.fullmatch(r'[A-Za-z_]\w{0,63}',legacy_field)))):
        raise ValueError('Explicit native profile, factor layout and pause view required')
    if (not isinstance(helpers,list) or len(helpers)>4 or
            any(not isinstance(v,str) or not v.strip() or len(v)>16384 for v in helpers) or
            (helpers and factor_layout!='record')):
        raise ValueError('Bounded complete helpers with their native factor record required')
    if not isinstance(cases,list) or not 1<=len(cases)<=2048:
        raise ValueError('Bounded independently expected attack events required')
    def integer(v,bounds):
        return type(v) is int and bounds[0]<=v<=bounds[1]
    rows=[]
    for case in cases:
        if (not isinstance(case,dict) or set(case)!={'inputs','expected'} or
                not isinstance(case['inputs'],dict) or set(case['inputs'])!=set(INPUT_BOUNDS) or
                not isinstance(case['expected'],dict) or
                set(case['expected'])!=set(EXPECTED_BOUNDS)|{'trace'}):
            raise ValueError('Complete attack inputs and independent expectations required')
        a,b=case['inputs'],case['expected']
        if (any(not integer(a[k],v) for k,v in INPUT_BOUNDS.items()) or
                any(not integer(b[k],v) for k,v in EXPECTED_BOUNDS.items()) or
                not isinstance(b['trace'],list) or len(b['trace'])>16 or
                any(not integer(v,(1,11)) for v in b['trace'])):
            raise ValueError('Bounded native attack state and service trace required')
        rows.append('{{'+','.join(str(a[k]) for k in INPUT_BOUNDS)+'},{'+
                    ','.join(str(b[k]) for k in EXPECTED_BOUNDS)+',{'+
                    ','.join(str(v) for v in b['trace']+[0]*(16-len(b['trace'])))+'},'+
                    str(len(b['trace']))+'}}')
    if factor_layout=='parallel':
        factor_declarations='static float factors[2][7][16];'
        fields=('defense_factors','defense_pain','defense_knockdown','defense_blockpower',
                'defense_blockthreshold','defense_blockratio','defense_blocktype')
        factor_setup=('memset(factors,0,sizeof(factors));for(int i=0;i<2;++i){entity *e=i?&target:&attacker;'+''.join(
            'e->modeldata.%s=factors[i][%d];'%(field,j) for j,field in enumerate(fields))+
            'for(int j=0;j<16;++j)factors[i][3][j]=2;}')
    else:
        factor_declarations='static s_defense factors[2][16];static const s_defense default_defense={0};'
        factor_setup=('memset(factors,0,sizeof(factors));for(int i=0;i<2;++i){entity *e=i?&target:&attacker;'
                      'e->modeldata.defense=factors[i];e->defense=factors[i];'
                      'for(int j=0;j<16;++j)factors[i][j].blockpower=2;}')
    code=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef printf
#undef time
#undef assert
#undef cangrab
#ifdef NDEBUG
#error Complete attack assertions must remain enabled
#endif
static unsigned active_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Native attack event mismatch: case=%u line=%d\n",active_case,__LINE__);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
@GRAPHICS@
@REFUSALS@
static entity attacker,target;
static s_anim attack_animation,target_animation,follow_animation;
static s_anim *attacker_animations[MAX_ANIS],*target_animations[MAX_ANIS];
static s_attack attack;
static s_attack *attacks[1];
entity *self;
entity **ent_list;
int ent_max,max_attack_types=16,level_completed;
int lasthitc,combodelay=11,equalairpause,nocost,healthcheat,blockratio,mpblock,nochipdeath,noslowfx;
int SAMPLE_BEAT,SAMPLE_BLOCK,SAMPLE_INDIRECT,rush[6];
float lasthitx,lasthitz,lasthita;
s_savedata savedata;
static int follow_selectors[1],fixture_max_animations=MAX_ANIS;
int *animfollows=follow_selectors;
static uint32_t fixture_clock=100;
static int trace[16],trace_count,fixture_hit,fixture_cancel,fixture_damage,fixture_grab;
static int didhit_type,didhit_blocked,sound_id,sound_speed;
@FACTOR_DECLARATIONS@
static void record(int code){assert(trace_count<16);trace[trace_count++]=code;}
static void unexpected_service(void){fputs("Unexpected native attack service\n",stderr);abort();}
static void check_payload(int force,int drop,int noblock,int guardcost,int jugglecost,int pauseadd){
 assert(force==12 && drop==0 && noblock==0 && guardcost==2 && jugglecost==0 && pauseadd==2);
}
int checkhit(entity *e,entity *other,int counter){
 assert(e==&attacker && other==&target && counter==0);record(1);return fixture_hit;
}
void execute_ondoattack_script(entity *e,entity *other,int force,int drop,int type,int noblock,int guardcost,int jugglecost,int pauseadd,int which,int id){
 assert(self==&target && id==17 && type==attack.attack_type);
 assert(which==0?(e==&target && other==&attacker):(which==1 && e==&attacker && other==&target));
 check_payload(force,drop,noblock,guardcost,jugglecost,pauseadd);record(which?3:2);
 if(which && fixture_cancel)lasthitc=0;
}
void execute_didhit_script(entity *e,entity *other,int force,int drop,int type,int noblock,int guardcost,int jugglecost,int pauseadd,int blocked){
 assert(e==&attacker && other==&target && self==&target);
 check_payload(force,drop,noblock,guardcost,jugglecost,pauseadd);
 assert(didhit_type==-1);didhit_type=type;didhit_blocked=blocked;record(5);
}
void execute_didblock_script(entity *e,entity *other,int force,int drop,int type,int noblock,int guardcost,int jugglecost,int pauseadd){
 assert(e==&target && other==&attacker && self==e && type==0);
 check_payload(force,drop,noblock,guardcost,jugglecost,pauseadd);record(9);
}
void didfind_item(entity *e){assert(e==&attacker && self==&target);record(4);target.modeldata.subtype=7;}
static int observed_damage(entity *other,s_attack *a){assert(self==&target && other==&attacker && a==&attack);record(6);return fixture_damage;}
void ent_set_anim(entity *e,int index,int resetable){
 assert(e==&attacker && index==MAX_ANIS-1 && resetable==1 && self==&target);
 record(7);e->animation=&follow_animation;
}
static int observed_grab(entity *e,entity *other){assert(e==&attacker && other==&target && self==other);record(11);return fixture_grab;}
int inair(entity *e){assert(e==&attacker || e==&target);return 0;}
int sound_play_sample(int sample,unsigned priority,int left,int right,unsigned speed){
 assert(self==&attacker && priority==0 && left==9 && right==9 && sound_id==-1);
 sound_id=sample;sound_speed=(int)speed;record(8);return 0;
}
unsigned int rand32(void){unexpected_service();return 0;}
void common_lie(void){unexpected_service();}
void common_block(void){unexpected_service();}
int set_blockpain(entity *e,int type,int reset){(void)e;(void)type;(void)reset;unexpected_service();return 0;}
entity *spawn(float x,float z,float a,int direction,char *name,int index,s_model *model){
 (void)x;(void)z;(void)a;(void)direction;(void)name;(void)index;(void)model;unexpected_service();return NULL;
}
void execute_onspawn_script(entity *e){(void)e;unexpected_service();}
void kill(entity *e){(void)e;unexpected_service();}
#define time fixture_clock
#define max_animations fixture_max_animations
#define cangrab observed_grab
@HELPERS@
@SOURCE@
struct attack_input {int kind,hit,cancel,damage,manual_block,follow,hostile,allow_grab,noslow,hitsound,beat,blocksound,indirect,projectile,nextattack;};
struct attack_expected {int context,follow,nextattack,hit_id,hits,subtype,didhit_type,didhit_blocked,sound,speed,pain,paused,guard,rush,trace[16],trace_count;};
struct attack_case {struct attack_input inputs;struct attack_expected expected;};
static const struct attack_case tests[]={@CASES@};
int main(void){
 _Static_assert(ATK_ITEM>=0 && ATK_ITEM<16 && ANI_BLOCK>=0 && ANI_BLOCK<MAX_ANIS-1,"native attack selector extent");
 for(active_case=0;active_case<sizeof(tests)/sizeof(*tests);++active_case){
  const struct attack_input *a=&tests[active_case].inputs;
  const struct attack_expected *b=&tests[active_case].expected;
  memset(&attacker,0,sizeof(attacker));memset(&target,0,sizeof(target));
  memset(&attack_animation,0,sizeof(attack_animation));memset(&target_animation,0,sizeof(target_animation));
  memset(&follow_animation,0,sizeof(follow_animation));memset(&attack,0,sizeof(attack));
  memset(attacker_animations,0,sizeof(attacker_animations));memset(target_animations,0,sizeof(target_animations));
  memset(trace,0,sizeof(trace));memset(rush,0,sizeof(rush));trace_count=0;
  didhit_type=didhit_blocked=sound_id=-1;sound_speed=0;
  fixture_hit=a->hit;fixture_cancel=a->cancel;fixture_damage=a->damage;fixture_grab=a->allow_grab;
  level_completed=0;lasthitc=1;equalairpause=nocost=healthcheat=blockratio=mpblock=nochipdeath=0;
  noslowfx=a->noslow;SAMPLE_BEAT=a->beat;SAMPLE_BLOCK=13;SAMPLE_INDIRECT=a->indirect;savedata.effectvol=9;
  entity *entities[1]={&target};ent_list=entities;ent_max=1;
  attacker.exists=target.exists=1;attacker.health=target.health=100;
  attacker.animation=&attack_animation;target.animation=&target_animation;
  attacker.modeldata.animation=attacker_animations;target.modeldata.animation=target_animations;
  @CAPACITY@
  attacker.modeldata.type=TYPE_PLAYER;target.modeldata.type=TYPE_ENEMY;
  attacker.modeldata.candamage=attacker.modeldata.projectilehit=TYPE_ENEMY;
  attacker.modeldata.hostile=a->hostile?TYPE_ENEMY:0;
  target.modeldata.subtype=3;target.modeldata.nopassiveblock=a->manual_block;
  target.blocking=a->manual_block;target.modeldata.blockback=1;target.idling=1;
  target.modeldata.guardpoints.maximum=target.modeldata.guardpoints.current=100;
  attacker.direction=1;target.direction=0;target.nextattack=a->nextattack;
  attacker.projectile=a->projectile;attacker.attack_id=17;target.takedamage=observed_damage;
  attacker.nextthink=4;attacker.nextanim=5;attacker.toss_time=6;
  target.nextthink=7;target.nextanim=8;target.toss_time=9;
  @PAUSE_INIT@
  attack_animation.numframes=target_animation.numframes=follow_animation.numframes=1;
  attack_animation.counterrange.framestart=target_animation.counterrange.framestart=-1;
  attack_animation.counterrange.frameend=target_animation.counterrange.frameend=-1;
  attack_animation.followanim=a->follow?1:0;attack_animation.followcond=a->follow;
  follow_animation.attackone=0;attacker_animations[MAX_ANIS-1]=&follow_animation;
  follow_selectors[0]=MAX_ANIS-1;
  attack.attack_type=a->kind?ATK_ITEM:0;attack.attack_force=12;attack.guardcost=2;attack.pause_add=2;
  attack.pain_time=7;attack.hitsound=a->hitsound;attack.blocksound=a->blocksound;attack.no_flash=1;
  attacks[0]=&attack;attack_animation.attacks=attacks;
  @FACTOR_SETUP@
  self=&attacker;do_attack(&attacker);
  assert(self==(b->context?&target:&attacker));
  assert(attacker.animation==(b->follow?&follow_animation:&attack_animation));
  assert(target.nextattack==(unsigned)b->nextattack && target.hit_by_attack_id==b->hit_id);
  assert(attack_animation.animhits==b->hits && target.modeldata.subtype==b->subtype);
  assert(didhit_type==b->didhit_type && didhit_blocked==b->didhit_blocked);
  assert(sound_id==b->sound && sound_speed==b->speed && target.pain_time==(unsigned)b->pain);
  assert(attacker.nextthink==4u+2u*b->paused && attacker.nextanim==5u+2u*b->paused && attacker.toss_time==6u+2u*b->paused);
  assert(target.nextthink==7u+2u*b->paused && target.nextanim==8u+2u*b->paused && target.toss_time==9u+2u*b->paused);
  @PAUSE_CHECK@
  assert(attacker.combotime==(b->paused?111u:0u));
  assert((int64_t)target.modeldata.guardpoints.current==b->guard && (int64_t)attacker.rush[0]==b->rush);
  assert(attacker.rushtime==(b->rush?100u:0u));
  assert(attacker.lasthit==(b->paused?&target:NULL));
  assert(trace_count==b->trace_count);
  for(int i=0;i<trace_count;++i)assert(trace[i]==b->trace[i]);
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",active_case);return 0;
}
'''
    values=dict(REVISION=str(revision)+'u',SOURCE=source,HELPERS='\n'.join(helpers),
                CASES=',\n'.join(rows),FACTOR_DECLARATIONS=factor_declarations,FACTOR_SETUP=factor_setup,
                CAPACITY='attacker.modeldata.animation_capacity=target.modeldata.animation_capacity=MAX_ANIS;' if animation_capacity_field else '',
                PAUSE_INIT='attacker.'+legacy_field+'=-1;' if legacy_field else 'attacker.pausetime=0;',
                PAUSE_CHECK='assert(attacker.'+legacy_field+'==(b->paused?0:-1));' if legacy_field else 'assert(attacker.pausetime==(b->paused?102u:0u));',
                GRAPHICS=graphics_refusals(unused_graphics_inlines),
                REFUSALS=inline_refusals(unused_inline_declarations,forbidden_names=('do_attack',)))
    return re.sub(r'@('+'|'.join(values)+r')@',lambda m:values[m[1]],code)
