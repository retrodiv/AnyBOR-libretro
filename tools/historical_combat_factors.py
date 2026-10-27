"""Native damage, pain, knockdown and periodic-damage factor contracts.

Complete functions and actual engine records are retained. Callbacks only
observe decisions and payloads; they do not implement scripts or entity death.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from native_header_fixtures import graphics_refusals, inline_refusals


def render_combat_factors(parts, *, revision, representation, factor_target,
                          configurable_drop, dot_loop, projectile_factors=False,
                          attack_types=16, helpers='', unused_graphics_inlines=False,
                          unused_inline_declarations=None):
    names = {'checkdamage', 'checkdamagedrop', 'checkdamageflip', 'common_dot'}
    if (not isinstance(parts, dict) or set(parts) != names or
            any(not isinstance(v, str) or not v.strip() or len(v) > 65536 for v in parts.values())):
        raise ValueError('Four bounded complete native combat functions required')
    if type(revision) is not int or not 0 < revision <= 0xffffffff:
        raise ValueError('Explicit bounded profile revision required')
    if representation not in ('parallel', 'record') or factor_target not in ('model', 'entity'):
        raise ValueError('Explicit native representation and source-defined reader target required')
    if representation == 'parallel' and factor_target != 'model':
        raise ValueError('Parallel native factor records require the original model target')
    if (type(configurable_drop) is not bool or type(projectile_factors) is not bool or
            dot_loop not in ('inclusive', 'exclusive')):
        raise ValueError('Explicit drop defaults and valid-prefix loop context required')
    if not isinstance(helpers, str) or len(helpers) > 65536:
        raise ValueError('Bounded exact prepared helper definitions required')
    if type(attack_types) is not int or not 0 < attack_types <= 256:
        raise ValueError('Explicit bounded native attack-type extent required')
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef assert
#undef printf
#undef malloc
#undef calloc
#undef free
#undef time
#ifdef NDEBUG
#error Native assertions must remain enabled
#endif
static const char *fixture_phase="initial";
#define assert(condition) do {if(!(condition)) { \
 fprintf(stderr,"Native combat factor contract mismatch: %s\n",fixture_phase);abort();}} while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *interpreter) {(void)interpreter;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *interpreter) {(void)interpreter;abort();}
@GRAPHICS@
@REFUSALS@
enum {FACTOR_COUNT=@ATTACK_TYPES@,MODEL_TARGET=@MODEL_TARGET@,CONFIGURABLE_DROP=@CONFIGURABLE_DROP@,
 PROJECTILE_FACTORS=@PROJECTILE_FACTORS@,
 DOT_SLOT_COUNT=sizeof(((entity*)0)->dot_time)/sizeof(((entity*)0)->dot_time[0])};
static entity subject,attacker,*self=&subject;
static int fixture_attack_types=FACTOR_COUNT;
static unsigned fixture_clock=100;
static s_attack emptyattack,observed_attack;
static float default_model_dropv[3]={9.f,4.f,2.f};
static float model_offense[FACTOR_COUNT],private_offense[FACTOR_COUNT];
@DEFENSE_DECLARATIONS@
static unsigned damage_calls,death_calls,kill_calls,attack_calls;
static int observed_force,observed_type;
static void observed_damage(entity *ent,entity *other,int force,int drop,int type,
                            int noblock,int guardcost,int jugglecost,int pauseadd) {
 assert(ent==self && (other==&attacker || other==self));
 (void)drop;(void)noblock;(void)guardcost;(void)jugglecost;(void)pauseadd;
 ++damage_calls;observed_force=force;observed_type=type;
}
static void observed_death(entity *ent,entity *other,int force,int drop,int type,
                           int noblock,int guardcost,int jugglecost,int pauseadd) {
 assert(ent==self && (other==&attacker || other==self));
 (void)drop;(void)noblock;(void)guardcost;(void)jugglecost;(void)pauseadd;
 ++death_calls;assert(force==observed_force && type==observed_type);
}
static void observed_kill(entity *ent) {assert(ent==self);++kill_calls;}
static int observed_takedamage(entity *other,s_attack *attack) {
 assert(other==&attacker);observed_attack=*attack;++attack_calls;return 1;
}
#define time fixture_clock
#undef max_attack_types
#define max_attack_types fixture_attack_types
#define execute_takedamage_script observed_damage
#define execute_ondeath_script observed_death
#undef kill
#define kill observed_kill
/* Original inclusive loops also visit an invalid suffix slot. Keep their
 * exact function text and native array types, but limit this oracle to its
 * defined prefix. Prepared exclusive loops use the complete native extent.
 * This is not an unmodified-original whole-engine execution claim. */
#undef MAX_DOTS
#define MAX_DOTS @DOT_EXTENT@
@HELPERS@
@FUNCTIONS@
static unsigned cases;
static void setup(float model_factor,float private_factor,float model_pain,float private_pain,
                  float model_knock,float private_knock,float offense_model,float offense_private) {
 memset(&subject,0,sizeof(subject));memset(&attacker,0,sizeof(attacker));
 memset(&emptyattack,0,sizeof(emptyattack));memset(&observed_attack,0,sizeof(observed_attack));
 damage_calls=death_calls=kill_calls=attack_calls=0;observed_force=observed_type=-99;
 subject.modeldata.health=2000;subject.health=1000;subject.mp=100;
 for(unsigned i=0;i<FACTOR_COUNT;++i) {
  model_offense[i]=offense_model;private_offense[i]=offense_private;
  @DEFENSE_VALUES@
 }
 @DEFENSE_POINTERS@
 subject.modeldata.offense_factors=attacker.modeldata.offense_factors=model_offense;
 subject.offense_factors=attacker.offense_factors=private_offense;
}
static void damage_case(int index,int mode,int force,float offense,float defense) {
 fixture_phase="damage";
 setup(defense,0.25f,30,5,2,0.5f,offense,0.5f);
 s_attack attack;memset(&attack,0,sizeof(attack));attack.attack_type=index;
 attack.attack_force=force;attack.attack_drop=3;
 entity *other=&attacker;int initial=1000;
 if(mode==1)other->projectile=1;
 if(mode==2){subject.damage_on_landing=1;other=self;}
 if(mode==3){subject.modeldata.guardpoints.maximum=1;subject.modeldata.guardpoints.current=0;}
 if(mode>=4){initial=1;subject.health=1;}
 if(mode==4)attack.no_kill=1;
 if(mode==5)subject.invincible=2;
 if(mode==6)subject.invincible=3;
 if(mode==7){subject.invincible=3;subject.a=PIT_DEPTH-1;}
 if(mode==8){subject.invincible=3;subject.lifespancountdown=-1;}
 int applied=mode==3?0:force;
 if(PROJECTILE_FACTORS || (mode!=1 && mode!=2)) {
  applied=(int)(applied*(MODEL_TARGET?offense:0.5f));
  applied=(int)(applied*(MODEL_TARGET?defense:0.25f));
 }
 int health=initial-applied;if(health>2000)health=2000;
 if(attack.no_kill && health<=0)health=1;
 unsigned death=health<=0;
 if(death && mode==5)health=1;
 if(death && mode==6)health=2000;
 checkdamage(other,&attack);
 assert(subject.health==health && damage_calls==1 && death_calls==death);
 assert(observed_force==applied && observed_type==index);++cases;
}
static void drop_case(int index,int mode,int drop,float knockdown) {
 fixture_phase="drop";
 setup(0.5f,0.25f,30,5,knockdown,0.5f,2,0.5f);
 s_attack attack;memset(&attack,0,sizeof(attack));attack.attack_type=index;attack.attack_drop=drop;
 subject.knockdowncount=3;subject.modeldata.knockdowncount=5;
 if(mode==1)subject.modeldata.animal=1;
 if(mode==2)subject.drop=1;
 if(mode==3)attack.no_pain=1;
 if(mode==4){subject.modeldata.guardpoints.maximum=1;subject.modeldata.guardpoints.current=0;}
 if(mode==5)subject.knockdowntime=99;
 float expected=mode==5?5:3;
 int skipped=mode==1 || mode==2 || mode==3;
 if(!skipped)expected-=(mode==4?0:drop)*(MODEL_TARGET?knockdown:0.5f);
 else expected=3;
 checkdamagedrop(&attack);
 assert(subject.knockdowncount==expected);
 assert(subject.drop==((mode==1 || mode==2 || expected<0)?1:0));
 assert(subject.knockdowntime==(skipped?0u:100u+GAME_SPEED));++cases;
}
static void flip_case(int index,int mode,int direction,int relative,float pain) {
 fixture_phase="flip";
 setup(0.5f,0.25f,pain,5,2,0.5f,2,0.5f);
 s_attack attack;memset(&attack,0,sizeof(attack));attack.attack_type=index;
 attack.attack_force=20;attack.force_direction=direction;
 subject.x=relative;attacker.x=0;attacker.direction=1;
 entity *other=&attacker;
 if(mode==1)attack.no_pain=1;
 if(mode==2)subject.modeldata.nopain=1;
 if(mode==3)subject.drop=1;
 if(mode==4)subject.frozen=1;
 if(mode==5)subject.modeldata.noflip=1;
 if(mode==6)other=NULL;
 if(mode==7)other=self;
 float selected=MODEL_TARGET?pain:5;int expected=0;
 int blocked=other==NULL || other==self ||
   (!subject.drop && (attack.no_pain || subject.modeldata.nopain || (selected && 20<selected))) ||
   subject.frozen || subject.modeldata.noflip;
 if(!blocked) {
  if(direction==0)expected=relative<0?1:0;
  else if(direction==1 || direction==2)expected=1;
 }
 checkdamageflip(other,&attack);assert(subject.direction==expected);++cases;
}
static void dot_case(int index,int mode,int health,int handler,float offense,float defense) {
 fixture_phase="dot";
 setup(defense,0.25f,30,5,2,0.5f,offense,0.5f);subject.health=health;
 int slot=DOT_SLOT_COUNT-1;assert(slot>=0);
 subject.dot[slot]=mode;subject.dot_time[slot]=200;subject.dot_cnt[slot]=100;
 subject.dot_rate[slot]=100;subject.dot_atk[slot]=index;subject.dot_force[slot]=25;
 subject.dot_owner[slot]=&attacker;
 if(handler)subject.takedamage=observed_takedamage;
 int applied=25;float off=MODEL_TARGET?offense:0.5f,def=MODEL_TARGET?defense:0.25f;
 if(off)applied=(int)(applied*off);
 if(def)applied=(int)(applied*def);
 int hp=mode==1 || mode==3 || mode==4 || mode==5;
 int lethal=hp && applied>=health && (mode==4 || mode==5);
 int expected_health=hp && !lethal?(health>applied?health-applied:1):health;
 common_dot();
 assert(subject.health==expected_health && subject.mp==((mode==2 || mode==3 || mode==5)?75:100));
 assert(subject.dot_cnt[slot]==100+GAME_SPEED);
 assert(attack_calls==(unsigned)(lethal && handler) && kill_calls==(unsigned)(lethal && !handler));
 assert(damage_calls==(unsigned)(hp && !lethal));
 if(damage_calls)assert(observed_force==25 && observed_type==index);
 if(attack_calls) {
  assert(observed_attack.attack_type==index && observed_attack.attack_force==25);
  assert(observed_attack.dropv[0]==(CONFIGURABLE_DROP?9.f:3.f));
  assert(observed_attack.dropv[1]==(CONFIGURABLE_DROP?4.f:1.2f));
  assert(observed_attack.dropv[2]==(CONFIGURABLE_DROP?2.f:0.f));
 }
 ++cases;
}
int main(void) {
 const float offense[]={0.f,0.5f,1.25f,2.f},defense[]={0.f,0.5f,2.f};
 for(int index=0;index<FACTOR_COUNT;++index) {
  for(int mode=0;mode<9;++mode)for(int force=-12;force<=21;force+=11)
   for(unsigned o=0;o<4;++o)for(unsigned d=0;d<3;++d)
    damage_case(index,mode,force,offense[o],defense[d]);
  for(int mode=0;mode<6;++mode)for(int drop=0;drop<=3;++drop)
   for(unsigned d=0;d<3;++d)drop_case(index,mode,drop,defense[d]);
  for(int mode=0;mode<8;++mode)for(int dir=-2;dir<=2;++dir)
   for(int x=-1;x<=1;++x)for(int p=0;p<=30;p+=15)flip_case(index,mode,dir,x,(float)p);
  for(int mode=1;mode<=5;++mode)for(int hp=1;hp<=100;hp+=99)
   for(int handler=0;handler<2;++handler)for(unsigned o=0;o<4;++o)for(unsigned d=0;d<3;++d)
    dot_case(index,mode,hp,handler,offense[o],defense[d]);
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''
    if representation == 'parallel':
        declarations = 'static float model_defense[3][FACTOR_COUNT],private_defense[3][FACTOR_COUNT];'
        values = ('model_defense[0][i]=model_factor;private_defense[0][i]=private_factor;'
                  'model_defense[1][i]=model_pain;private_defense[1][i]=private_pain;'
                  'model_defense[2][i]=model_knock;private_defense[2][i]=private_knock;')
        pointers = '\n'.join('subject.modeldata.%s=model_defense[%d];subject.%s=private_defense[%d];' %
                             (field, n, field, n) for n, field in enumerate(
                                 ('defense_factors', 'defense_pain', 'defense_knockdown')))
    else:
        declarations = 'static s_defense model_defense[FACTOR_COUNT],private_defense[FACTOR_COUNT];'
        values = ('memset(&model_defense[i],0,sizeof(model_defense[i]));'
                  'memset(&private_defense[i],0,sizeof(private_defense[i]));'
                  'model_defense[i].factor=model_factor;private_defense[i].factor=private_factor;'
                  'model_defense[i].pain=model_pain;private_defense[i].pain=private_pain;'
                  'model_defense[i].knockdown=model_knock;private_defense[i].knockdown=private_knock;')
        pointers = 'subject.modeldata.defense=model_defense;subject.defense=private_defense;'
    replacements = dict(REVISION=str(revision), MODEL_TARGET=str(int(factor_target == 'model')),
        ATTACK_TYPES=str(attack_types),
        PROJECTILE_FACTORS=str(int(projectile_factors)),
        CONFIGURABLE_DROP=str(int(configurable_drop)), DOT_EXTENT='(DOT_SLOT_COUNT-1)' if dot_loop == 'inclusive' else 'DOT_SLOT_COUNT',
        HELPERS=helpers, FUNCTIONS='\n'.join(parts[name] for name in sorted(names)),
        DEFENSE_DECLARATIONS=declarations, DEFENSE_VALUES=values, DEFENSE_POINTERS=pointers)
    replacements['GRAPHICS'] = graphics_refusals(unused_graphics_inlines)
    replacements['REFUSALS'] = inline_refusals(unused_inline_declarations,
        forbidden_names=tuple(names))
    for key, value in replacements.items():
        code = code.replace('@' + key + '@', value)
    return code
