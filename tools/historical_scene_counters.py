"""Render native scene-counter operations and their collision consumers.

Update statements retain their original types and source. The platform queries,
geometry predicate and obstacle path of testmove execute against native records.
Event wrappers are observations of update sites, not complete allocators, model
setters or disposal. Unselected geometry services refuse unexpected calls.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from native_header_fixtures import graphics_refusals, inline_refusals
import re

from test_historical_player import function

FUNCTIONS = ('testplatform', 'check_platform', 'check_platform_between',
             'check_platform_above', 'check_platform_below', 'testmove', 'diff', 'inair')
HOOKS = ('created', 'removed', 'model_reset', 'model_keep', 'platform_loaded',
         'reset_load', 'reset_unload')
OPS = ('create', 'remove', 'type', 'model_reset', 'model_keep', 'platform_loaded',
       'reset_load', 'reset_unload')


def prepared_scene_counter_parts(source):
    """Extract actual prepared updates and consumers; refuse missing/ambiguous sites.

    Full caller execution remains a separate contract. These checks retain the
    concrete source statements and their position relative to native updates.
    """
    parts = {name: function(source, name) for name in FUNCTIONS}
    block = r'if\(obor_scene_counters_active\(\)\)\s*\{[^{}]*\}'
    single = (r'if\(obor_scene_counters_active\(\)\)\s*'
              r'obor_scene_counter_adjust\([^;]+;')
    sites = (
        ('created', 'spawn', block, 'e->defaultmodel = model;', 'e->scripts = scripts;'),
        ('removed', 'kill', block, 'ent_count--;', 'clear_all_scripts('),
        ('model_reset', 'ent_set_model', single, 'oldmodel = ent->modeldata;', 'ent->model = m;'),
        ('model_keep', 'set_model_ex', single, 'ent_copy_uninit(ent, &oldmodel);', '\n\t\telse'),
        ('reset_load', 'load_level', block, 'nopause = 0;', 'nofadeout = 0;'),
        ('reset_unload', 'unload_level', block, 'time = 0;', 'cameratype = 0;'),
    )
    for key, caller, pattern, before, after in sites:
        body = function(source, caller)
        matches = list(re.finditer(pattern, body))
        if len(matches) != 1:
            raise ValueError('One explicit native counter update site required: ' + caller)
        match = matches[0]
        if not (body.index(before) < match.start() < match.end() <=
                body.index(after, match.end())):
            raise ValueError('Native counter update order differs: ' + caller)
        parts[key] = match[0]
    assignments = re.findall(r'newchar->hasPlatforms\s*=\s*1\s*;', source)
    if len(assignments) != 1:
        raise ValueError('One native cached platform flag assignment required')
    parts['platform_loaded'] = assignments[0]
    parts['helpers'] = '\n'.join(function(source, name) for name in (
        'obor_scene_counters_active', 'obor_scene_counter_adjust'))
    return parts


def render_scene_counters(parts, *, revision, flag_member, cases,
                          unused_graphics_inlines=False, unused_inline_declarations=None):
    if (not isinstance(parts, dict) or set(parts) != set(FUNCTIONS + HOOKS + ('helpers',)) or
            any(not isinstance(v, str) or len(v) > 65536 for v in parts.values()) or
            any(not parts[name].strip() for name in FUNCTIONS)):
        raise ValueError('Complete bounded native counter operations and consumers required')
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            type(flag_member) is not bool or
            (not flag_member and parts['platform_loaded'].strip())):
        raise ValueError('Explicit native revision and model flag layout required')
    if not isinstance(cases, list) or not 1 <= len(cases) <= 1024:
        raise ValueError('Bounded independent scene-counter cases required')

    def integer(v, lo, hi):
        return type(v) is int and lo <= v <= hi

    def vector(v, n, lo, hi):
        return isinstance(v, list) and len(v) == n and all(integer(x, lo, hi) for x in v)

    def outcome(value, level):
        if (not isinstance(value, dict) or set(value) != {'counts', 'queries', 'move'} or
                not vector(value['counts'], 2, -32, 32) or
                not vector(value['queries'], 4, -1, 1) or
                not vector(value['move'], 2, -1, 1) or
                value['move'][1] < 0 or
                (not level and value['move'] != [-1, 0]) or
                (level and value['move'][0] < 0)):
            raise ValueError('Explicit bounded counter/query/movement results required')
        return '{{%s},{%s},{%s}}' % tuple(','.join(map(str, value[k]))
                                         for k in ('counts', 'queries', 'move'))

    entries = []
    for case in cases:
        if (not isinstance(case, dict) or set(case) != {
                'seed', 'model_flags', 'model_types', 'scene_mask', 'exclude',
                'obstacle', 'level', 'initial', 'steps'} or
                not vector(case['seed'], 2, -16, 16) or
                not vector(case['model_flags'], 2, 0, 1) or
                not vector(case['model_types'], 2, 0, 3) or
                not integer(case['scene_mask'], 0, 3) or
                not integer(case['exclude'], -1, 1) or
                not integer(case['obstacle'], 0, 1) or not integer(case['level'], 0, 1) or
                not isinstance(case['steps'], list) or len(case['steps']) > 16):
            raise ValueError('Explicit bounded native scene and event inputs required')
        initial = outcome(case['initial'], case['level'])
        steps = []
        for event in case['steps']:
            if (not isinstance(event, dict) or set(event) != {'op', 'value', 'after'} or
                    event['op'] not in OPS or not integer(event['value'], 0,
                        3 if event['op'] == 'type' else 1 if event['op'] in (
                            'create', 'model_reset', 'model_keep', 'platform_loaded') else 0)):
                raise ValueError('Explicit bounded native counter event required')
            steps.append('{%d,%d,%s}' % (OPS.index(event['op']), event['value'],
                                        outcome(event['after'], case['level'])))
        entries.append('{{%s},{%s},{%s},%d,%d,%d,%d,%s,%d,{%s}}' % (
            ','.join(map(str, case['seed'])), ','.join(map(str, case['model_flags'])),
            ','.join(map(str, case['model_types'])), case['scene_mask'], case['exclude'],
            case['obstacle'], case['level'], initial, len(steps), ','.join(steps) or '{0}'))

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
#ifdef NDEBUG
#error Native counter assertions must remain enabled
#endif
_Static_assert(sizeof(int)==4,"Native counter width differs");
static const char *phase="initial";
static unsigned active_case,active_step;
#define assert(c) do {if(!(c)) {fprintf(stderr,"Native scene counter mismatch: %s case=%u step=%u\n",phase,active_case,active_step);abort();}} while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *p) {(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p) {(void)p;abort();}
@GRAPHICS@
@REFUSALS@
struct outcome {int counts[2],queries[4],move[2];};
struct counter_step {int op,value;struct outcome after;};
struct counter_case {
 int seed[2],model_flags[2],model_types[2],scene_mask,exclude,obstacle,level;
 struct outcome initial;unsigned step_count;struct counter_step steps[16];
};
static const struct counter_case cases[]={@CASES@},*test;
static int numPlatforms,numObstacles,nopause,nofadeout;
static uint32_t fixture_clock;
static int PLAYER_MIN_Z=0,PLAYER_MAX_Z=200;
static float advancex;
static s_videomodes videomodes;
static s_level scene,*level;
static s_model models[2];
static entity actor,platforms[2],movement_actor,obstacle;
static s_anim empty_animation,platform_animations[2];
static __typeof__(*platform_animations[0].platform) coordinates[2][1];
static entity *ent_list[]={&actor,&platforms[0],&platforms[1]};
static int ent_max=3;
static unsigned find_calls;
static const int native_types[]={TYPE_ENEMY,TYPE_OBSTACLE,TYPE_TRAP,TYPE_PLAYER};
static int refused_geometry(float x,float z) {(void)x;(void)z;abort();}
static entity *observed_find(entity *exclude,float x,float z,int types,
                             int (*predicate)(entity*,entity*)) {
 assert(exclude==&movement_actor && x==1 && z==0 && !predicate);
 assert(types==(TYPE_OBSTACLE|TYPE_TRAP));++find_calls;
 return test->obstacle?&obstacle:NULL;
}
#define time fixture_clock
@HELPERS@
static void native_created(entity *e) {
@CREATED@
}
static void native_removed(entity *victim) {
@REMOVED@
}
static void native_model_reset(entity *ent,s_model *m) {
@MODEL_RESET@
}
static void native_model_keep(s_model *model,s_model *newmodel) {
@MODEL_KEEP@
}
static void native_platform_loaded(s_model *newchar) {
@PLATFORM_LOADED@
}
static void native_load_reset(void) {
@RESET_LOAD@
}
static void native_unload_reset(void) {
@RESET_UNLOAD@
}
@DIFF@
@INAIR@
@TESTPLATFORM@
@CHECK_PLATFORM@
@CHECK_PLATFORM_BETWEEN@
@CHECK_PLATFORM_ABOVE@
@CHECK_PLATFORM_BELOW@
#define checkhole refused_geometry
#define checkwall refused_geometry
#define find_ent_here observed_find
@TESTMOVE@
#undef find_ent_here
#undef checkwall
#undef checkhole
#undef time
static int identity(entity *value) {
 if(!value)return -1;
 if(value==&platforms[0])return 0;
 assert(value==&platforms[1]);return 1;
}
static void check_outcome(const struct outcome *expected) {
 phase="counter values";assert(numPlatforms==expected->counts[0]);
 assert(numObstacles==expected->counts[1]);
 phase="platform query results";
 entity *exclude=test->exclude<0?NULL:&platforms[test->exclude];
 int queries[]={identity(check_platform(0,-5,exclude)),
                identity(check_platform_between(0,-5,10,25,exclude)),
                identity(check_platform_above(0,-5,10,exclude)),
                identity(check_platform_below(0,-5,30,exclude))};
 for(unsigned i=0;i<4;++i)assert(queries[i]==expected->queries[i]);
 phase="obstacle query result";find_calls=0;
 int result=level?testmove(&movement_actor,0,0,1,0):-1;
 assert(result==expected->move[0] && find_calls==(unsigned)expected->move[1]);
}
int main(void) {
 unsigned steps=0;
 for(unsigned n=0;n<sizeof(cases)/sizeof(*cases);++n) {
  active_case=n;active_step=0;test=&cases[n];
  memset(models,0,sizeof(models));memset(&actor,0,sizeof(actor));
  memset(platforms,0,sizeof(platforms));memset(&movement_actor,0,sizeof(movement_actor));
  memset(&obstacle,0,sizeof(obstacle));memset(&empty_animation,0,sizeof(empty_animation));
  memset(platform_animations,0,sizeof(platform_animations));memset(coordinates,0,sizeof(coordinates));
  memset(&scene,0,sizeof(scene));memset(&videomodes,0,sizeof(videomodes));
  videomodes.hRes=320;videomodes.vRes=240;scene.width=1000;
  level=test->level?&scene:NULL;numPlatforms=test->seed[0];numObstacles=test->seed[1];
  fixture_clock=123;nopause=nofadeout=1;
  for(unsigned i=0;i<2;++i) {
   models[i].type=native_types[test->model_types[i]];@INITIAL_FLAG@
   platforms[i].exists=(test->scene_mask&(1<<i))!=0;
   platforms[i].animation=&platform_animations[i];platforms[i].a=i?20:0;
   platform_animations[i].platform=coordinates[i];
   coordinates[i][0][2]=coordinates[i][0][3]=-10;
   coordinates[i][0][4]=coordinates[i][0][5]=10;
   coordinates[i][0][6]=10;coordinates[i][0][7]=8;
  }
  actor.animation=&empty_animation;actor.model=&models[0];actor.modeldata=models[0];
  movement_actor.animation=obstacle.animation=&empty_animation;
  movement_actor.modeldata.type=TYPE_PLAYER;
  movement_actor.modeldata.subject_to_obstacle=1;
  movement_actor.modeldata.height=10;obstacle.exists=1;
  check_outcome(&test->initial);
  for(unsigned i=0;i<test->step_count;++i) {
   active_step=i+1;const struct counter_step *event=&test->steps[i];
   phase="native counter event";
   switch(event->op) {
   case 0: actor.model=&models[event->value];actor.modeldata=*actor.model;
           actor.exists=1;native_created(&actor);break;
   case 1: actor.exists=0;native_removed(&actor);break;
   case 2: actor.modeldata.type=native_types[event->value];break;
   case 3: native_model_reset(&actor,&models[event->value]);
           actor.model=&models[event->value];@RESET_FLAG@ break;
   case 4: {s_model *old=actor.model;actor.model=&models[event->value];
           @RESET_FLAG@ native_model_keep(old,actor.model);break;}
   case 5: native_platform_loaded(&models[event->value]);break;
   case 6: native_load_reset();break;
   case 7: native_unload_reset();break;
   default:abort();
   }
   check_outcome(&event->after);++steps;
  }
 }
 printf("{\"status\":\"PASS\",\"cases\":%u,\"steps\":%u}\n",
        (unsigned)(sizeof(cases)/sizeof(*cases)),steps);return 0;
}
'''
    values = {key.upper(): value for key, value in parts.items()}
    values.update(REVISION=str(revision), CASES=',\n'.join(entries),
        GRAPHICS=graphics_refusals(unused_graphics_inlines),
        REFUSALS=inline_refusals(unused_inline_declarations, forbidden_names=FUNCTIONS),
        INITIAL_FLAG='models[i].hasPlatforms=test->model_flags[i];' if flag_member else '',
        RESET_FLAG='actor.modeldata.hasPlatforms=actor.model->hasPlatforms;' if flag_member else '')
    for key, value in values.items():
        code = code.replace('@' + key + '@', value)
    return code
