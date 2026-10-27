"""Render complete native spawn/kill functions with bounded record observations.

Allocation, script execution, colourmap ownership and AI initialization remain
separate contracts. The fixture observes those services and executes the native
pool selection, factor initialization, counter updates and reference cleanup.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from native_header_fixtures import graphics_refusals, inline_refusals


def render_entity_spawn(parts, *, revision, factor_layout, scripts_pointer,
                        flag_member, contract, cases,
                        unused_graphics_inlines=False, unused_inline_declarations=None):
    if (not isinstance(parts, dict) or set(parts) != {'spawn', 'kill', 'helpers'} or
            any(not isinstance(v, str) or len(v) > 65536 or
                (key != 'helpers' and not v.strip()) for key, v in parts.items())):
        raise ValueError('Complete bounded native spawn/kill and dependency source required')
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            factor_layout not in ('parallel', 'record') or
            type(scripts_pointer) is not bool or type(flag_member) is not bool):
        raise ValueError('Explicit native record and revision context required')
    keys = {'zero_factors', 'priority_reuse', 'counter_updates'}
    if (not isinstance(contract, dict) or set(contract) != keys or
            any(type(v) is not bool for v in contract.values()) or
            (contract['counter_updates'] and not flag_member)):
        raise ValueError('Explicit independent spawn/kill expectations required')
    if not isinstance(cases, list) or not 1 <= len(cases) <= 1024:
        raise ValueError('Bounded explicit entity spawn cases required')
    entries = []
    for case in cases:
        bounds = {'type': 5, 'flag': 1, 'variables': 2, 'route': 2,
                  'occupied': 1, 'expected_slot': 1}
        if (not isinstance(case, dict) or set(case) != set(bounds) or
                any(type(case[k]) is not int or not 0 <= case[k] <= maximum
                    for k, maximum in bounds.items()) or case['variables'] == 1):
            raise ValueError('Explicit bounded record inputs and expected pool slot required')
        if case['expected_slot'] != (0 if not case['occupied'] or
                                    contract['priority_reuse'] else 1):
            raise ValueError('Pool expectation must agree with the independently declared contract')
        entries.append('{%s}' % ','.join(str(case[k]) for k in bounds))
    fields = ('factor', 'pain', 'knockdown', 'blockpower', 'blockthreshold',
              'blockratio', 'blocktype')
    native_fields = ('defense_factors', 'defense_pain', 'defense_knockdown',
                     'defense_blockpower', 'defense_blockthreshold',
                     'defense_blockratio', 'defense_blocktype')
    if factor_layout == 'parallel':
        factor_data = 'static float model_defense[7][16],entity_defense[3][7][16];'
        model_setup = '\n'.join('model.%s=model_defense[%d];' % (f, i)
                                 for i, f in enumerate(native_fields))
        entity_setup = '\n'.join('pool[i].%s=entity_defense[i][%d];' % (f, j)
                                  for j, f in enumerate(native_fields))
        factor_fill = ('for(unsigned f=0;f<7;++f)for(unsigned i=0;i<16;++i){'
                       'model_defense[f][i]=1;'
                       'for(unsigned e=0;e<3;++e)entity_defense[e][f][i]=9;}')
        factor_check = '\n'.join('for(unsigned i=0;i<16;++i)assert(e->%s[i]==expected);' % f
                                  for f in native_fields)
    else:
        factor_data = 'static s_defense model_defense[16],entity_defense[3][16];'
        model_setup = 'model.defense=model_defense;'
        entity_setup = 'pool[i].defense=entity_defense[i];'
        factor_fill = 'for(unsigned i=0;i<16;++i){' + ''.join(
            'model_defense[i].%s=1;' % f for f in fields) + \
            'for(unsigned e=0;e<3;++e){' + ''.join(
                'entity_defense[e][i].%s=9;' % f for f in fields) + '}}'
        factor_check = 'for(unsigned i=0;i<16;++i){' + ''.join(
            'assert(e->defense[i].%s==expected);' % f for f in fields) + '}'
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef assert
#undef printf
#undef time
#undef free
#ifdef NDEBUG
#error Native spawn assertions must remain enabled
#endif
static const char *phase="setup";
static unsigned active_case;
#define assert(c) do {if(!(c)){fprintf(stderr,"Native entity spawn mismatch: %s case=%u\n",phase,active_case);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
@GRAPHICS@
@REFUSALS@
struct spawn_case {int type,flag,variables,route,occupied,expected_slot;};
static const struct spawn_case cases[]={@CASES@},*test;
static const int native_types[]={TYPE_ENEMY,TYPE_OBSTACLE,TYPE_TRAP,TYPE_PLAYER,TYPE_TEXTBOX,TYPE_SHOT};
static entity pool[3],*ent_list[]={&pool[0],&pool[1],&pool[2]};
static entity *self,*smartbomber,*textbox;
static s_model model;
static s_modelcache fixture_cache[1];
s_modelcache *model_cache;
static s_scripts model_scripts,entity_scripts[3];
static ScriptVariant variables[3][2];
static float model_offense[16],entity_offense[3][16];
@FACTOR_DATA@
static s_level scene,*level;
s_savedata savedata;
static s_player player[4];
const s_drawmethod plainmethod = {0};
static s_attack emptyattack;
static float default_model_dropv[3];
static int ent_count,ent_max,ent_list_size=3,max_attack_types=16;
int max_entity_vars;
static int currentspawnplayer,level_completed,spawnoverride;
static int numPlatforms,numObstacles;
static uint32_t fixture_clock;
static unsigned cleared,copied,initialized,unlinked,killed,variants;
@HELPERS@
static void observed_clear(void *scripts,int mode){
 assert(scripts && mode==1);++cleared;
}
static void observed_copy(void *from,void *to,int mode){
 assert(from==@MODEL_SCRIPTS@ && to && mode==1);++copied;
 *(s_scripts*)to=*(s_scripts*)from;
}
static s_model *observed_find(char *name){assert(!strcmp(name,"actor"));return &model;}
static void observed_variant(ScriptVariant *v){
 assert(v);memset(v,0,sizeof(*v));++variants;
}
static int observed_grow(void){abort();}
static void observed_default(entity *e){assert(e && e->exists);++initialized;}
static void observed_unlink(entity *e){assert(e && e->exists);++unlinked;}
static void observed_onkill(entity *e){(void)e;++killed;}
static void observed_colourmap(entity *e,uint64_t map){assert(e && !map);}
static void observed_release(s_model *m){assert(m);}
static int observed_model_copy(s_model *to,const s_model *from){
 assert(to && from==&model);*to=*from;return 1;
}
static void observed_shutdown(int status,const char *message,...){(void)status;(void)message;abort();}
static void refused_free(void *p){(void)p;abort();}
#define clear_all_scripts observed_clear
#define copy_all_scripts observed_copy
#define findmodel observed_find
#define ScriptVariant_Clear observed_variant
#define alloc_ents observed_grow
#define ent_default_init observed_default
#define ent_unlink observed_unlink
#define execute_onkill_script observed_onkill
#define ent_set_colourmap observed_colourmap
#define obor_colourmap_owner_release observed_release
#define obor_model_copy observed_model_copy
#undef shutdown
#undef borShutdown
#define shutdown observed_shutdown
#define borShutdown observed_shutdown
#define time fixture_clock
#define free refused_free
#undef kill
#define kill native_kill
@KILL@
@SPAWN@
#undef kill
#undef time
#undef free
static void verify_factors(entity *e){
 float expected=@ZERO_FACTORS@?0:1;
 @FACTOR_CHECK@
 for(unsigned i=0;i<16;++i)assert(e->offense_factors[i]==(@ZERO_FACTORS@?0:2));
}
int main(void){
 for(unsigned n=0;n<sizeof(cases)/sizeof(*cases);++n){
  active_case=n;test=&cases[n];phase="setup";
  memset(pool,0,sizeof(pool));memset(&model,0,sizeof(model));
  memset(&scene,0,sizeof(scene));memset(&savedata,0,sizeof(savedata));
  memset(player,0,sizeof(player));memset(variables,0,sizeof(variables));
  memset(&model_scripts,0,sizeof(model_scripts));memset(entity_scripts,0,sizeof(entity_scripts));
  memset(model_defense,0,sizeof(model_defense));memset(entity_defense,0,sizeof(entity_defense));
  memset(entity_offense,0,sizeof(entity_offense));
  @FACTOR_FILL@
  for(unsigned i=0;i<16;++i){model_offense[i]=2;
   for(unsigned e=0;e<3;++e)entity_offense[e][i]=9;}
  model.offense_factors=model_offense;@MODEL_SETUP@
  model.name="actor";model.type=native_types[test->type];model.health=40;model.mp=9;
  model.knockdowncount=5;model.lifespan=7;@MODEL_PRIORITY@ @FLAG_SETUP@
  @MODEL_SCRIPT_SETUP@
  for(unsigned i=0;i<3;++i){
   pool[i].sortid=10+i;pool[i].entvars=variables[i];
   pool[i].offense_factors=entity_offense[i];@ENTITY_SETUP@
   @ENTITY_SCRIPT_SETUP@
  }
  pool[0].exists=test->occupied;pool[0].modeldata.type=TYPE_ENEMY;
  @PRIORITY_SETUP@ pool[2].exists=1;pool[2].modeldata.type=TYPE_ENEMY;
  self=&pool[2];smartbomber=textbox=NULL;model_cache=fixture_cache;model_cache[0].model=&model;
  ent_count=1+test->occupied;ent_max=3;max_entity_vars=test->variables;
  currentspawnplayer=0;level_completed=0;spawnoverride=1;
  level=&scene;fixture_clock=123;numPlatforms=numObstacles=0;
  cleared=copied=initialized=unlinked=killed=variants=0;
  phase="native pool selection";
  entity *e=spawn(3,4,5,1,test->route==2?"actor":NULL,
                 test->route==1?0:-1,test->route==0?&model:NULL);
  assert(e==&pool[test->expected_slot] && e->exists && e->model==&model && e->defaultmodel==&model);
  assert(e->sortid==10+test->expected_slot && e->health==40 && e->mp==9);
  assert(e->x==3 && e->z==4 && e->a==5 && e->direction==1);
  assert(e->timestamp==123 && e->nextthink==124 && initialized==1 && copied==1);
  assert(variants==(unsigned)max_entity_vars);
  unsigned reused=test->occupied && test->expected_slot==0;
  assert(killed==reused && unlinked==reused && cleared==1+reused);
  assert(ent_count==2+test->occupied-(int)reused);
  phase="spawn factors";verify_factors(e);
  phase="spawn counters";
  assert(numPlatforms==(@COUNTER_UPDATES@?test->flag:0));
  assert(numObstacles==(@COUNTER_UPDATES@?(test->type==1||test->type==2):0));
  phase="native reference cleanup";
  entity *neighbor=&pool[2];e->parent=neighbor;neighbor->subentity=e;
  neighbor->parent=e;neighbor->owner=e;neighbor->opponent=e;neighbor->bound=e;
  smartbomber=e;
  if(test->type==3)player[0].ent=e;
  if(test->type==5){player[0].ent=neighbor;neighbor->cantfire=1;}
  int before=ent_count;native_kill(e);
  assert(!e->exists && e->health==0 && ent_count==before-1);
  assert(!e->parent && !e->subentity && !neighbor->parent && !neighbor->subentity);
  assert(!neighbor->owner && !neighbor->opponent && !neighbor->bound);
  assert(!smartbomber && !textbox && self==neighbor);
  if(test->type==3)assert(!player[0].ent);
  if(test->type==5)assert(!neighbor->cantfire);
  assert(!numPlatforms && !numObstacles);
  assert(killed==reused+1 && unlinked==reused+1 && cleared==reused+2);
  native_kill(e);native_kill(NULL);
  assert(killed==reused+3 && unlinked==reused+1 && cleared==reused+2);
  assert(ent_count==before-1 && !numPlatforms && !numObstacles);
 }
 printf("{\"status\":\"PASS\",\"cases\":%u}\n",(unsigned)(sizeof(cases)/sizeof(*cases)));
 return 0;
}
'''
    values = dict(parts, revision=str(revision), cases=','.join(entries),
        graphics=graphics_refusals(unused_graphics_inlines),
        refusals=inline_refusals(unused_inline_declarations, forbidden_names=('spawn', 'kill')),
        factor_data=factor_data, model_setup=model_setup, entity_setup=entity_setup,
        factor_fill=factor_fill, factor_check=factor_check,
        model_scripts='model.scripts' if scripts_pointer else '&model.scripts',
        model_script_setup='model.scripts=&model_scripts;' if scripts_pointer else '',
        entity_script_setup='pool[i].scripts=&entity_scripts[i];' if scripts_pointer else '',
        model_priority='model.priority=0;' if contract['priority_reuse'] else '',
        priority_setup='pool[0].modeldata.priority=-1;' if contract['priority_reuse'] else '',
        flag_setup='model.hasPlatforms=test->flag;' if flag_member else '',
        **{k:str(int(v)) for k,v in contract.items()})
    for key, value in values.items():
        code = code.replace('@'+key.upper()+'@', value)
    return code
