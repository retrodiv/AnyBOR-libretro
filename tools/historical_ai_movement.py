"""Render native wandering, grab placement and movement caller contracts.

Native entity/model records and linking helpers are retained. Random choices,
target lookup, grab eligibility, geometry responses and script/animation services
are explicit observations; their implementations and the full AI are separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import math

from native_header_fixtures import graphics_refusals, inline_refusals

FUNCTIONS = ('common_try_wander', 'adjust_grabposition', 'common_trymove',
             'trygrab', 'common_try_grab', 'diff', 'inair', 'ent_unlink',
             'ents_link', 'set_opponent')
OPTIONAL = ('trygrab', 'common_try_grab')


def render_ai_movement(parts, *, revision, native_animation_capacity, game_speed,
                       wander, adjust, move, unused_graphics_inlines=False,
                       unused_inline_declarations=None):
    if (not isinstance(parts, dict) or set(parts) != set(FUNCTIONS + ('helpers',)) or
            any(not isinstance(v, str) or len(v) > 65536 for v in parts.values()) or
            any(not parts[n].strip() for n in FUNCTIONS if n not in OPTIONAL) or
            bool(parts['trygrab'].strip()) != bool(parts['common_try_grab'].strip())):
        raise ValueError('Complete bounded native movement functions and explicit optional helpers required')
    if (type(revision) is not int or not 0 < revision <= 0xffffffff or
            type(native_animation_capacity) is not bool or
            type(game_speed) is not int or not 1 <= game_speed <= 10000):
        raise ValueError('Explicit native record, clock and revision context required')
    for cases in (wander, adjust, move):
        if not isinstance(cases, list) or not 1 <= len(cases) <= 1024:
            raise ValueError('Bounded independent cases for each movement routine required')

    def number(v, lo=-4096, hi=4096, integer=False):
        return ((type(v) is int if integer else type(v) in (int, float)) and
                math.isfinite(v) and lo <= v <= hi)

    def vec(v, n, lo=-4096, hi=4096, integer=False):
        return isinstance(v, list) and len(v) == n and all(number(x, lo, hi, integer) for x in v)

    def floating(v):
        return float(v).hex() + 'f'

    def fv(v):
        return '{' + ','.join(floating(x) for x in v) + '}'

    def iv(v):
        return '{' + (','.join(str(x) for x in v) or '0') + '}'

    def trace(v):
        if (not isinstance(v, list) or len(v) > 64 or any(
                not isinstance(e, list) or len(e) != 7 or
                not number(e[0], 1, 17, True) or not number(e[1], 0, 2, True) or
                not all(number(x, -100000, 100000) for x in e[2:]) for e in v)):
            raise ValueError('Explicit bounded callback arguments and order required')
        return str(len(v)) + ',{' + (','.join(
            '{%d,%d,%s}' % (e[0], e[1], fv(e[2:])) for e in v) or '{0}') + '}'

    wander_rows = []
    for c in wander:
        keys = {'video', 'camera', 'zrange', 'position', 'target', 'target_present',
                'nomove', 'dox', 'doz', 'speed', 'grabdistance', 'health', 'sortid',
                'pathblocked', 'aggression', 'clock', 'random32', 'pick', 'expected'}
        if (not isinstance(c, dict) or set(c) != keys or
                not vec(c['video'], 2, 64, 1024, True) or
                not vec(c['camera'], 2) or not vec(c['zrange'], 2, 0, 1024, True) or
                c['zrange'][0] > c['zrange'][1] or not vec(c['position'], 2) or
                not isinstance(c['target'], list) or len(c['target']) != 4 or
                not all(number(x) for x in c['target'][:2]) or
                not all(number(x, 0, 1, True) for x in c['target'][2:]) or
                any(not number(c[k], 0, 1, True) for k in ('target_present','nomove','dox','doz')) or
                not number(c['speed'], .25, 16) or
                not number(c['grabdistance'], -32, 32, True) or
                not number(c['health'], 0, 1000, True) or
                not number(c['sortid'], 0, 1000, True) or
                not number(c['pathblocked'], 0, 10, True) or
                not number(c['aggression'], 0, 100, True) or
                not number(c['clock'], 0, 10000, True) or
                not number(c['random32'], 0, 15, True) or c['pick'] not in (-1, 1) or
                type(c['pick']) is not int):
            raise ValueError('Explicit bounded wander inputs required')
        e = c['expected']
        if (not isinstance(e, dict) or set(e) != {'result','velocity','destination','trace'} or
                not number(e['result'], 0, 1, True) or not vec(e['velocity'], 2) or
                not vec(e['destination'], 2)):
            raise ValueError('Explicit independent wander results required')
        ints = [c[k] for k in ('target_present','nomove','dox','doz','grabdistance','health',
                               'sortid','pathblocked','aggression','clock','random32','pick')]
        wander_rows.append('{%s,%s,%s,%s,%s,%s,%s,%d,%s,%s,%s}' % (
            iv(c['video']),fv(c['camera']),iv(c['zrange']),fv(c['position']),fv(c['target']),
            ','.join(map(str,ints)),floating(c['speed']),e['result'],fv(e['velocity']),
            fv(e['destination']),trace(e['trace'])))

    adjust_rows = []
    for c in adjust:
        if (not isinstance(c, dict) or set(c) != {'actor','target','distance','grabin','responses','expected'} or
                not vec(c['actor'], 4) or not vec(c['target'], 4) or
                not number(c['distance'], -64, 64) or not number(c['grabin'], 0, 1, True) or
                not isinstance(c['responses'], list) or len(c['responses']) > 2 or
                not all(number(x, -1, 1, True) for x in c['responses'])):
            raise ValueError('Explicit bounded grab placement inputs required')
        e = c['expected']
        if (not isinstance(e, dict) or set(e) != {'result','positions','trace'} or
                not number(e['result'], 0, 1, True) or not vec(e['positions'], 4)):
            raise ValueError('Explicit independent grab placement results required')
        adjust_rows.append('{%s,%s,%s,%d,%d,%s,%d,%s,%s}' % (
            fv(c['actor']),fv(c['target']),floating(c['distance']),c['grabin'],
            len(c['responses']),iv(c['responses']),e['result'],fv(e['positions']),trace(e['trace'])))

    move_rows = []
    for c in move:
        keys = {'function','type','position','target','obstacle','delta','flags','exit_blocked',
                'clock','available','idling','grabdistance','grabflip','throwwait',
                'random','finds','cangrab','responses','count','target_argument','expected'}
        if (not isinstance(c, dict) or set(c) != keys or
                not number(c['function'], 0, 2, True) or
                (c['function'] and not parts['trygrab'].strip()) or
                not number(c['type'], 0, 2, True) or
                any(not vec(c[k], 2) for k in ('position','target','obstacle','delta')) or
                not vec(c['flags'], 4, 0, 1, True) or
                not number(c['exit_blocked'], 0, 1, True) or
                not number(c['clock'], 0, 10000, True) or
                not vec(c['available'], 2, 0, 1, True) or
                any(not number(c[k], 0, 1, True) for k in ('idling','cangrab','target_argument')) or
                not number(c['grabdistance'], -32, 32, True) or
                not number(c['grabflip'], 0, 3, True) or
                not number(c['throwwait'], -1, 2, True) or
                not number(c['count'], -1, 1, True)):
            raise ValueError('Explicit bounded movement/grab caller inputs required')
        for key, maximum, lo, hi in (('random',4,0,15),('finds',4,0,2),('responses',2,-1,1)):
            if (not isinstance(c[key], list) or len(c[key]) > maximum or
                    any(not number(x, lo, hi, True) for x in c[key])):
                raise ValueError('Explicit bounded callback response queues required')
        e = c['expected']
        if (not isinstance(e, dict) or set(e) != {'result','positions','directions','actions',
                'flags','velocity','timers','linked','combo_cleared','trace'} or
                not number(e['result'], 0, 2, True) or not vec(e['positions'], 4) or
                not vec(e['directions'], 2, 0, 1, True) or not vec(e['actions'], 2, 0, 2, True) or
                not vec(e['flags'], 4, 0, 1, True) or not vec(e['velocity'], 4) or
                not vec(e['timers'], 2, 0, 20000, True) or
                any(not number(e[k], 0, 1, True) for k in ('linked','combo_cleared'))):
            raise ValueError('Explicit independent movement/grab state and trace required')
        fields = [str(c['function']),str(c['type']),fv(c['position']),fv(c['target']),
            fv(c['obstacle']),fv(c['delta']),iv(c['flags']),str(c['exit_blocked']),
            str(c['clock'])+'u',iv(c['available']),str(c['idling']),str(c['grabdistance']),
            str(c['grabflip']),str(c['throwwait']),str(c['cangrab']),str(c['count']),
            str(c['target_argument']),iv(c['random']),str(len(c['random'])),
            iv(c['finds']),str(len(c['finds'])),iv(c['responses']),str(len(c['responses'])),
            str(e['result']),fv(e['positions']),iv(e['directions']),iv(e['actions']),
            iv(e['flags']),fv(e['velocity']),iv(e['timers']),str(e['linked']),
            str(e['combo_cleared']),trace(e['trace'])]
        move_rows.append('{'+','.join(fields)+'}')

    code = r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "openbor.h"
#undef assert
#undef printf
#undef time
#ifdef NDEBUG
#error Native movement assertions must remain enabled
#endif
_Static_assert(sizeof(int)==4 && GAME_SPEED==@GAME_SPEED@,"Native movement widths/clock differ");
static const char *phase="setup";
static unsigned active_case;
#define assert(c) do{if(!(c)){fprintf(stderr,"Native AI movement mismatch: %s case=%u\n",phase,active_case);abort();}}while(0)
uint32_t obor_profile_build=@REVISION@;
HRESULT Interpreter_Call(Interpreter *p){(void)p;abort();}
HRESULT Interpreter_EvalInstruction(Interpreter *p){(void)p;abort();}
@GRAPHICS@
@REFUSALS@
struct event {int op,which;float v[5];};
struct wander_case {
 int video[2];float camera[2];int zrange[2];float pos[2],target[4];
 int present,nomove,dox,doz,grabdistance,health,sortid,pathblocked,aggression,clock,random32,pick;
 float speed;int result;float velocity[2],destination[2];unsigned trace_count;struct event trace[64];
};
struct adjust_case {
 float actor[4],target[4],distance;int grabin;unsigned response_count;int responses[2];
 int result;float positions[4];unsigned trace_count;struct event trace[64];
};
struct move_case {
 int function,type;float pos[2],target[2],obstacle[2],delta[2];int flags[4],exit_blocked;
 uint32_t clock;int available[2],idling,grabdistance,grabflip,throwwait,cangrab,count,target_argument;
 int random[4];unsigned random_count;int finds[4];unsigned find_count;int responses[2];unsigned response_count;
 int result;float positions[4];int directions[2],actions[2],flags_after[4];float velocity[4];
 unsigned timers[2];int linked,combo_cleared;unsigned trace_count;struct event trace[64];
};
static const struct wander_case wanders[]={@WANDER_CASES@};
static const struct adjust_case adjusts[]={@ADJUST_CASES@};
static const struct move_case moves[]={@MOVE_CASES@};
static const struct wander_case *w;
static const struct move_case *m;
static entity actor,target,obstacle,*self=&actor;
static s_model actor_model,target_model;
static s_anim animation,*animation_table[MAX_ANIS+1];
static s_level world,*level=&world;
static s_videomodes videomodes;
static float advancex,advancey;
static int PLAYER_MIN_Z,PLAYER_MAX_Z,numObstacles;
static uint32_t fixture_clock;
static struct event observed[64];static unsigned observed_count,random_count,find_count,response_count;
static const int *responses;static unsigned response_limit;
static void emit(int op,int which,float a,float b,float c,float d,float e){
 assert(observed_count<64);observed[observed_count++]=(struct event){op,which,{a,b,c,d,e}};
}
static void near(float a,float b){assert(isfinite(a)&&a==b);}
static void verify_trace(unsigned n,const struct event *expected){
 assert(observed_count==n);
 for(unsigned i=0;i<n;++i){assert(observed[i].op==expected[i].op && observed[i].which==expected[i].which);
  for(unsigned j=0;j<5;++j)near(observed[i].v[j],expected[i].v[j]);}
}
void common_grab(void){abort();}
void common_grabbed(void){abort();}
void common_prethrow(void){abort();}
void common_throw_wait(void){abort();}
static int observed_rand(void){
 assert(m && random_count<m->random_count);int v=m->random[random_count++];emit(3,0,v,0,0,0,0);return v;
}
static uint32_t observed_rand32(void){assert(w && random_count++==0);emit(1,0,w->random32,0,0,0,0);return w->random32;}
static int observed_pick(entity *ent,int reset){assert(w && !ent && !reset);emit(2,0,w->pick,0,0,0,0);return w->pick;}
static entity *observed_find(entity *exclude,float x,float z,int type,int (*predicate)(entity*,entity*)){
 assert(m && exclude==self && !predicate && find_count<m->find_count);
 int v=m->finds[find_count++];emit(4,v,x,z,type,0,0);return v==1?&target:v==2?&obstacle:NULL;
}
static int observed_cangrab(entity *a,entity *b){assert(m && a==self && b==&target);emit(5,0,m->cangrab,0,0,0,0);return m->cangrab;}
static int observed_testmove(entity *e,float sx,float sz,float x,float z){
 assert(e==&actor||e==&target);
 if(response_count>=response_limit){phase="unexpected placement query";assert(0);}
 int v=responses[response_count++];emit(6,e==&target,sx,sz,x,z,v);return v;
}
static int refused_geometry(float x,float z){(void)x;(void)z;phase="unselected geometry";abort();}
static entity *refused_platform(float x,float z,entity *e){(void)x;(void)z;(void)e;phase="unselected geometry";abort();}
static entity *refused_between(float x,float z,float a,float b,entity *e){(void)a;(void)b;return refused_platform(x,z,e);}
@HELPERS@
@DIFF@
@INAIR@
#define ent_unlink native_ent_unlink
@ENT_UNLINK@
#define ents_link native_ents_link
@ENTS_LINK@
#undef ent_unlink
#undef ents_link
#define set_opponent native_set_opponent
@SET_OPPONENT@
#undef set_opponent
static void observed_opponent(entity *a,entity *b){assert(a==&target&&b==self);emit(7,0,0,0,0,0,0);native_set_opponent(a,b);}
static void observed_link(entity *a,entity *b){assert(a==self&&b==&target);emit(8,0,0,0,0,0,0);native_ents_link(a,b);}
static void observed_anim(entity *e,int anim,int reset){assert(e==self&&!reset);assert(anim==ANI_GRAB||anim==ANI_THROW);emit(9,0,anim==ANI_GRAB?1:2,0,0,0,0);}
static void observed_pain(entity *e,int a,int b){assert(e==&target&&a==-1&&!b);emit(10,0,a,b,0,0,0);}
static void observed_throw(void){emit(11,0,0,0,0,0,0);}
static void observed_blockz(entity *e){assert(e==self);emit(12,0,0,0,0,0,0);}
static void observed_blocks(entity *e){assert(e==self);emit(13,0,0,0,0,0,0);}
static void observed_blocko(entity *e,entity *o){assert(e==self&&o==&obstacle);emit(14,0,0,0,0,0,0);}
static void refused_blockw(entity *e,int a,double b){(void)e;(void)a;(void)b;abort();}
static void observed_movex(entity *e){assert(e==self);emit(16,0,0,0,0,0,0);}
static void observed_movez(entity *e){assert(e==self);emit(17,0,0,0,0,0,0);}
#undef rand
#undef rand32
#define rand observed_rand
#define rand32 observed_rand32
#define pick_random_attack observed_pick
#define find_ent_here observed_find
#undef cangrab
#define cangrab observed_cangrab
#define testmove observed_testmove
#define checkhole refused_geometry
#define checkwall refused_geometry
#define check_platform refused_platform
#define check_platform_between refused_between
#define set_opponent observed_opponent
#define ents_link observed_link
#define ent_set_anim observed_anim
#define set_pain observed_pain
#define dothrow observed_throw
#define execute_onblockz_script observed_blockz
#define execute_onblocks_script observed_blocks
#define execute_onblocko_script observed_blocko
#define execute_onblockw_script refused_blockw
#define execute_onmovex_script observed_movex
#define execute_onmovez_script observed_movez
#define time fixture_clock
@ADJUST_GRABPOSITION@
@TRYGRAB@
@COMMON_TRY_GRAB@
@COMMON_TRYMOVE@
@COMMON_TRY_WANDER@
#undef time
static void setup(void){
 memset(&actor,0,sizeof(actor));memset(&target,0,sizeof(target));memset(&obstacle,0,sizeof(obstacle));
 memset(&actor_model,0,sizeof(actor_model));memset(&target_model,0,sizeof(target_model));
 memset(&animation,0,sizeof(animation));memset(animation_table,0,sizeof(animation_table));
 memset(&world,0,sizeof(world));memset(&videomodes,0,sizeof(videomodes));
 actor.model=&actor_model;target.model=&target_model;self=&actor;
 animation.numframes=3;animation.range.xmin=5;animation.range.xmax=21;
 actor_model.animation=target_model.animation=animation_table;@CAPACITY@
 actor.modeldata=actor_model;target.modeldata=target_model;
 actor.animation=target.animation=obstacle.animation=&animation;
 actor.modeldata.type=TYPE_ENEMY;actor.modeldata.speed=3;actor.modeldata.grabdistance=20;
 actor.modeldata.hostile=TYPE_ENEMY;actor.modeldata.height=10;target.modeldata.type=TYPE_ENEMY;
 actor.xdir=3;actor.zdir=-2;target.xdir=4;target.zdir=-5;
 actor.idling=actor.running=actor.attacking=target.attacking=1;
 actor.releasetime=401;target.stalltime=301;
 memset(actor.combostep,7,sizeof(actor.combostep));
 actor.exists=target.exists=obstacle.exists=1;
 level=&world;world.width=1000;world.scrolldir=SCROLL_RIGHT;
 videomodes.hRes=321;videomodes.vRes=241;advancex=advancey=0;
 PLAYER_MIN_Z=0;PLAYER_MAX_Z=200;fixture_clock=100;numObstacles=0;
 observed_count=random_count=find_count=response_count=0;w=NULL;m=NULL;
 responses=NULL;response_limit=0;
}
static int actor_action(void){if(!actor.takeaction)return 0;if(actor.takeaction==common_grab)return 1;assert(actor.takeaction==common_throw_wait);return 2;}
static int target_action(void){if(!target.takeaction)return 0;if(target.takeaction==common_grabbed)return 1;assert(target.takeaction==common_prethrow);return 2;}
int main(void){
 _Static_assert(sizeof(actor.combostep)>=20,"Native grab combo storage too small");
 for(unsigned n=0;n<sizeof(wanders)/sizeof(*wanders);++n){
  setup();active_case=n;w=&wanders[n];phase="wander inputs";
  videomodes.hRes=w->video[0];videomodes.vRes=w->video[1];advancex=w->camera[0];advancey=w->camera[1];
  PLAYER_MIN_Z=w->zrange[0];PLAYER_MAX_Z=w->zrange[1];
  actor.x=w->pos[0];actor.z=w->pos[1];target.x=w->target[0];target.z=w->target[1];
  target.direction=w->target[2];target.attacking=w->target[3];actor.modeldata.nomove=w->nomove;
  actor.modeldata.speed=w->speed;actor.modeldata.grabdistance=w->grabdistance;
  actor.health=w->health;actor.sortid=w->sortid;actor.pathblocked=w->pathblocked;
  actor.modeldata.aggression=w->aggression;fixture_clock=w->clock;
  actor.xdir=9.5;actor.zdir=-4.25;actor.destx=-71.25;actor.destz=-83.5;
  animation_table[1]=&animation;
  int result=common_try_wander(w->present?&target:NULL,w->dox,w->doz);
  phase="wander result";assert(result==w->result&&random_count==1);
  near(actor.xdir,w->velocity[0]);near(actor.zdir,w->velocity[1]);near(actor.destx,w->destination[0]);near(actor.destz,w->destination[1]);
  phase="wander callback trace";verify_trace(w->trace_count,w->trace);
 }
 for(unsigned n=0;n<sizeof(adjusts)/sizeof(*adjusts);++n){
  setup();active_case=n;const struct adjust_case *c=&adjusts[n];phase="grab placement inputs";
  actor.x=c->actor[0];actor.z=c->actor[1];actor.a=c->actor[2];actor.base=c->actor[3];
  target.x=c->target[0];target.z=c->target[1];target.a=c->target[2];target.base=c->target[3];
  responses=c->responses;response_limit=c->response_count;
  int result=adjust_grabposition(&actor,&target,c->distance,c->grabin);
  phase="grab placement result";assert(result==c->result&&response_count==response_limit);
  near(actor.x,c->positions[0]);near(actor.z,c->positions[1]);near(target.x,c->positions[2]);near(target.z,c->positions[3]);
  phase="grab placement callback trace";verify_trace(c->trace_count,c->trace);
 }
 for(unsigned n=0;n<sizeof(moves)/sizeof(*moves);++n){
  setup();active_case=n;m=&moves[n];phase="movement inputs";
  const int types[]={TYPE_PLAYER,TYPE_ENEMY,TYPE_OBSTACLE};actor.modeldata.type=types[m->type];
  actor.x=m->pos[0];actor.z=m->pos[1];target.x=m->target[0];target.z=m->target[1];
  obstacle.x=m->obstacle[0];obstacle.z=m->obstacle[1];
  actor.modeldata.subject_to_minz=m->flags[0];actor.modeldata.subject_to_maxz=m->flags[1];
  actor.modeldata.subject_to_screen=m->flags[2];actor.modeldata.subject_to_obstacle=m->flags[3];
  world.exit_blocked=m->exit_blocked;fixture_clock=m->clock;
  if(m->available[0])animation_table[ANI_GRAB]=&animation;
  if(m->available[1])animation_table[ANI_THROW]=&animation;
  actor.idling=m->idling;actor.modeldata.grabdistance=m->grabdistance;
  actor_model.grabflip=m->grabflip;actor.modeldata.throwframewait=m->throwwait;
  numObstacles=m->count;responses=m->responses;response_limit=m->response_count;
  int result;
  if(m->function==0)result=common_trymove(m->delta[0],m->delta[1]);
#if @HAS_HELPERS@
  else if(m->function==1)result=trygrab(&target);
  else result=common_try_grab(m->target_argument?&target:NULL);
#else
  else {assert(0);result=-1;}
#endif
  phase="movement result";assert(result==m->result);
  near(actor.x,m->positions[0]);near(actor.z,m->positions[1]);near(target.x,m->positions[2]);near(target.z,m->positions[3]);
  assert(actor.direction==m->directions[0]&&target.direction==m->directions[1]);
  assert(actor_action()==m->actions[0]&&target_action()==m->actions[1]);
  int flags[]={actor.idling,actor.running,actor.attacking,target.attacking};
  for(unsigned i=0;i<4;++i)assert(flags[i]==m->flags_after[i]);
  near(actor.xdir,m->velocity[0]);near(actor.zdir,m->velocity[1]);near(target.xdir,m->velocity[2]);near(target.zdir,m->velocity[3]);
  assert(actor.releasetime==m->timers[0]&&target.stalltime==m->timers[1]);
  if(m->linked){assert(actor.link==&target&&target.link==&actor&&actor.grabbing==&target&&!target.grabbing);
   assert(actor.opponent==&target&&target.opponent==&actor);}
  else assert(!actor.link&&!target.link&&!actor.grabbing&&!target.grabbing&&!actor.opponent&&!target.opponent);
  phase="native combo clearing";
  for(unsigned i=0;i<sizeof(actor.combostep);++i)assert(((unsigned char*)actor.combostep)[i]==(m->combo_cleared&&i<20?0:7));
  phase="movement response consumption";
  assert(random_count==m->random_count&&find_count==m->find_count&&response_count==response_limit);
  phase="movement callback trace";verify_trace(m->trace_count,m->trace);
 }
 printf("{\"status\":\"PASS\",\"wander\":%u,\"adjust\":%u,\"move\":%u}\n",
  (unsigned)(sizeof(wanders)/sizeof(*wanders)),(unsigned)(sizeof(adjusts)/sizeof(*adjusts)),(unsigned)(sizeof(moves)/sizeof(*moves)));
 return 0;
}
'''
    values = {k.upper():v for k,v in parts.items()}
    values.update(REVISION=str(revision),GAME_SPEED=str(game_speed),
        GRAPHICS=graphics_refusals(unused_graphics_inlines),
        REFUSALS=inline_refusals(unused_inline_declarations,forbidden_names=FUNCTIONS),
        WANDER_CASES=',\n'.join(wander_rows),ADJUST_CASES=',\n'.join(adjust_rows),
        MOVE_CASES=',\n'.join(move_rows),HAS_HELPERS=str(int(bool(parts['trygrab'].strip()))),
        CAPACITY='actor_model.animation_capacity=target_model.animation_capacity=MAX_ANIS+1;' if native_animation_capacity else '')
    for key,value in values.items():
        code = code.replace('@'+key+'@',value)
    return code
