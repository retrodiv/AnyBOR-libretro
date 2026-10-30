"""Render complete native camera stepping with authored source expectations.

Models, spawns and callbacks are reduced fixtures; no pixels or games run.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re

from test_historical_player import function


def render_camera(engine, rows):
    source = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    constants = '\n'.join(re.search(r'^#define\s+'+name+r'\b[^\n]*', header, re.M)[0]
        for name in ('SCROLL_RIGHT', 'SCROLL_LEFT', 'SCROLL_OUTWARD', 'SCROLL_INWARD',
                     'SCROLL_UP', 'SCROLL_DOWN', 'SCROLL_BACK', 'TYPE_ENEMY',
                     'TYPE_ENDLEVEL', 'TYPE_ITEM', 'TYPE_OBSTACLE', 'GAME_SPEED', 'COUNTER_SPEED'))
    contexts = ','.join('{%d,%d,%d,%d}' % (
        row['revision'], row['separate_limits'], row['early_blockade'], row['bounding_box']) for row in rows)
    loader = function(source, 'load_level')
    start = loader.index('case CMD_LEVEL_SCROLLZ:')
    parser = loader[start:loader.index('case CMD_LEVEL_BLOCKADE:', start)]
    initialization = re.search(r'scrollmaxx\s*=[^;]+;\s*scrollmaxz\s*=[^;]+;', loader)[0]
    clearing = re.search(r'scrollminz\s*=\s*0;\s*scrollmaxz\s*=\s*0;\s*'
        r'scrollminx\s*=\s*0;\s*scrollmaxx\s*=\s*0;', function(source, 'unload_level'))[0]
    return r'''
#include <assert.h>
#include <stdint.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
@CONSTANTS@
static uint32_t obor_profile_build;
static unsigned test_case;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Camera revision=%u case=%u line=%d x=%g y=%g pos=%d\n",obor_profile_build,test_case,__LINE__,(double)advancex,(double)advancey,storage.pos);abort();}}while(0)
typedef struct {float x,z,a;int dead;} entity;
typedef struct {
 int at,musicfade,musicoffset,wait,groupmin,groupmax,nojoin,scrollminz,scrollmaxz,
     scrollminx,scrollmaxx,blockade,palette,light[2],shadowcolor,shadowalpha;
 char music[128];
} s_spawn_entry;
static s_spawn_entry spawns[2];
static struct {
 unsigned advancetime;
 int width,numspawns,pos,waiting,type,noreset,settime,scrolldir,cameraxoffset,camerazoffset,rocking;
 float scrollspeed;
 s_spawn_entry *spawnpoints;
} storage,*level=&storage;
static entity actors[4];
static struct {entity *ent;} player[4];
static struct {int maxplayers;} levelsets[1];
static struct {int hRes,vRes;} videomodes={320,240};
static struct {int musicvol;} savedata;
static unsigned time;
static int freezeall,level_completed,current_spawn,current_set,groupmin,groupmax,go_time,
 timeleft,musicoffset,musicloop,nojoin,light[2],shadowcolor,shadowalpha,panel_height,cameratype,enemy_count;
static float scrolldx,scrolldy,advancex,advancey,scrollminx,scrollmaxx,scrollminz,scrollmaxz,blockade,musicfade[2];
static char musicname[129];
static entity *findent(int mask) {return (mask&TYPE_ENEMY) && enemy_count?&actors[0]:NULL;}
static int count_ents(int mask) {assert(mask==TYPE_ENEMY);return enemy_count;}
static void change_system_palette(int index) {(void)index;abort();}
static void smartspawn(s_spawn_entry *entry) {(void)entry;abort();}
@SCROLLER@
enum {CMD_LEVEL_SCROLLZ,CMD_LEVEL_SCROLLX};
static s_spawn_entry next;
#define GET_INT_ARG(i) ((i)==1?low:high)
static void parse_scroll(int command,int low,int high) {switch(command){@PARSER@}}
static void initial_limits(void) {@INITIALIZATION@}
static void clear_limits(void) {@CLEARING@}
static void coordinates(float x,float z) {
 for(int i=0;i<3;++i){actors[i].x=x;actors[i].z=z;actors[i].a=0;}
}
static void reset(void) {
 memset(&storage,0,sizeof(storage));memset(actors,0,sizeof(actors));memset(spawns,0,sizeof(spawns));
 for(int i=0;i<3;++i){player[i].ent=&actors[i];}player[3].ent=NULL;
 levelsets[0].maxplayers=3;current_set=0;time=1;freezeall=level_completed=0;
 current_spawn=1;storage.numspawns=2;storage.spawnpoints=spawns;
 groupmin=0;groupmax=1;enemy_count=1;storage.width=1000;panel_height=600;
 storage.pos=17;storage.scrolldir=SCROLL_RIGHT;storage.scrollspeed=1000;
 scrollminx=scrollminz=0;scrollmaxx=680;scrollmaxz=360;blockade=0;
 advancex=advancey=80;scrolldx=scrolldy=123;cameratype=0;coordinates(400,200);
}
static void observe(float x,float y,int pos,int deltas) {
 float oldx=advancex,oldy=advancey;++test_case;update_scroller();
 assert(fabsf(advancex-x)<0.001f && fabsf(advancey-y)<0.001f && storage.pos==pos);
 assert(fabsf(scrolldx-(deltas?advancex-oldx:0))<0.001f);
 assert(fabsf(scrolldy-(deltas?advancey-oldy:0))<0.001f);
}
static void check(int limits,int early,int box) {
 // The old average and later bounding-box center differ with three players.
 reset();actors[0].x=100;actors[1].x=200;actors[2].x=700;
 observe(box?80:1000.0f/3-160,80,box?80:173,1);
 reset();advancex=0;actors[0].x=100;actors[1].x=110;actors[2].x=400;
 observe(box?90:610.0f/3-160,80,box?90:43,1);
 // Reverse speed limiting and exact end points have native progress rules.
 reset();storage.scrolldir=SCROLL_LEFT;storage.scrollspeed=20;advancex=300;coordinates(0,200);
 observe(280,80,limits?400:18,1);
 reset();storage.scrolldir=SCROLL_INWARD;storage.scrollspeed=20;advancey=300;coordinates(400,0);
 observe(100,280,limits?80:18,1);
 reset();advancex=680;coordinates(840,200);observe(680,80,limits?18:680,1);
 reset();storage.scrolldir=SCROLL_LEFT;advancex=0;coordinates(160,200);observe(0,80,limits?18:680,1);
 reset();storage.scrolldir=SCROLL_INWARD;advancey=0;coordinates(400,120);observe(240,0,limits?18:360,1);
 // Blockades apply after speed limiting before the relocation boundary.
 reset();storage.scrolldir=SCROLL_LEFT|SCROLL_BACK;storage.scrollspeed=20;
 advancex=600;blockade=300;coordinates(1000,200);observe(early?580:380,80,early?100:300,1);
 reset();storage.scrolldir=SCROLL_OUTWARD|SCROLL_BACK;storage.scrollspeed=20;
 advancey=40;blockade=200;coordinates(400,0);observe(100,early?60:200,early?60:200,1);
 reset();storage.scrolldir=SCROLL_INWARD|SCROLL_BACK;storage.scrollspeed=20;
 advancey=300;blockade=200;coordinates(400,700);observe(100,early?280:160,early?80:200,1);
 // Shared earlier limits and zero-as-unspecified are distinct contracts.
 reset();storage.scrolldir=SCROLL_OUTWARD;advancex=100;advancey=0;
 scrollminz=30;scrollmaxz=150;scrollminx=300;scrollmaxx=400;coordinates(600,120);
 observe(limits?400:150,limits?30:0,limits?30:0,1);
 reset();advancex=0;advancey=200;scrollminz=scrollmaxz=0;coordinates(200,500);
 observe(40,limits?0:348,40,1);
 // Height-aware centering retains the later original's initial Z bounds.
 reset();cameratype=1;coordinates(300,300);actors[1].z=350;actors[2].z=400;
 for(int i=0;i<3;++i)actors[i].a=100;
 observe(140,box?180:130,140,1);
 reset();storage.scrolldir=SCROLL_OUTWARD;storage.cameraxoffset=10;storage.camerazoffset=-10;
 coordinates(400,400);observe(250,box?270:290,box?270:290,1);
 // Spawn bounds at frame zero reset Y even without a current player.
 reset();for(int i=0;i<3;++i)player[i].ent=NULL;
 current_spawn=0;storage.numspawns=1;groupmin=groupmax=1;enemy_count=0;time=0;
 spawns[0].scrollminz=limits?(int32_t)(UINT32_C(0x80000000)|40):40;spawns[0].scrollmaxz=100;
 observe(80,40,17,0);assert(scrollminz==40 && scrollmaxz==100 && current_spawn==1);
 reset();for(int i=0;i<3;++i)player[i].ent=NULL;observe(80,80,17,0);
 reset();storage.waiting=1;advancey=200;observe(80,80,17,1);assert(storage.waiting);
 reset();freezeall=1;observe(80,80,17,0);
 reset();storage.advancetime=2;observe(80,80,17,0);assert(storage.advancetime==2);
 // Two elevator calls return the native static half-step counter to zero.
 reset();storage.scrolldir=SCROLL_UP;observe(80,80,80,1);observe(80,81,81,1);
 const int limits_input[][2]={{-3,0},{0,0},{10,100},{10,0},{0,90}};
 for(unsigned i=0;i<sizeof(limits_input)/sizeof(*limits_input);++i)
 for(int axis=CMD_LEVEL_SCROLLZ;axis<=CMD_LEVEL_SCROLLX;++axis) {
  ++test_case;int low=limits_input[i][0],high=limits_input[i][1];
  memset(&next,0x7f,sizeof(next));parse_scroll(axis,low,high);
  if(!limits) {
   assert(next.scrollminz==(low>0?low:0) && next.scrollmaxz==(high>0?high:0));
   assert(next.scrollminx==0 && next.scrollmaxx==0);
  } else {
   int encoded=low;encoded|=UINT32_C(0x80000000);
   assert(axis==CMD_LEVEL_SCROLLZ?
    next.scrollminz==encoded && next.scrollmaxz==high && next.scrollminx==0 && next.scrollmaxx==0:
    next.scrollminx==encoded && next.scrollmaxx==high && next.scrollminz==0 && next.scrollmaxz==0);
  }
 }
 ++test_case;reset();scrollmaxx=scrollmaxz=123;initial_limits();
 assert(scrollmaxx==680 && scrollmaxz==(limits?600:0));
 // X bounds are private inactive storage in the earlier profile. Clearing
 // that storage is shared; the native earlier Z resets remain observable.
 ++test_case;scrollminx=scrollminz=77;scrollmaxx=scrollmaxz=123;clear_limits();
 assert(scrollminx==0 && scrollmaxx==0 && scrollminz==0 && scrollmaxz==0);
}
int main(void) {
 const struct {unsigned revision;int limits,early,box;} rows[]={@ROWS@};
 for(unsigned i=0;i<sizeof(rows)/sizeof(*rows);++i) {
  obor_profile_build=rows[i].revision;check(rows[i].limits,rows[i].early,rows[i].box);
 }
 assert(test_case==sizeof(rows)/sizeof(*rows)*33);return 0;
}
'''.replace('@CONSTANTS@', constants).replace('@SCROLLER@', function(source, 'update_scroller')).replace('@ROWS@', contexts).replace(
        '@PARSER@', parser).replace('@INITIALIZATION@', initialization).replace('@CLEARING@', clearing)


def render_camera_step(engine, rows):
    """Render full early camera stepping with bounded entity/spawn providers."""
    source = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    constants = '\n'.join(re.search(r'^#define\s+' + name + r'\b[^\n]*', header, re.M)[0]
        for name in ('SCROLL_RIGHT', 'SCROLL_LEFT', 'SCROLL_OUTWARD', 'SCROLL_INWARD',
                     'SCROLL_UP', 'SCROLL_DOWN', 'SCROLL_BACK', 'TYPE_ENEMY',
                     'TYPE_ENDLEVEL', 'TYPE_ITEM', 'TYPE_OBSTACLE', 'GAME_SPEED', 'COUNTER_SPEED'))
    contexts = []
    for row in rows:
        if row['integer_target'] not in (0, 1) or row['progress_mode'] not in (0, 1, 2):
            raise ValueError('Own integer and progress contracts required')
        contexts.append('check(%d,%d,%d,%d,%d);' % (
            row['revision'], row['integer_target'], row['progress_mode'],
            row['offsets'], row['exclusive_music']))
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
@CONSTANTS@
static uint32_t obor_profile_build;
static unsigned test_case;
typedef struct {
 float x,z,a;
 int dead;
 struct {float speed,runspeed;} modeldata;
} entity;
typedef struct {
 int at,musicfade,musicoffset,wait,groupmin,groupmax,nojoin,scrollminz,scrollmaxz,
     blockade,palette,light[2],shadowcolor,shadowalpha;
 char music[128];
} s_spawn_entry;
static s_spawn_entry spawns[2];
static struct {
 unsigned advancetime;
 int width,numspawns,pos,waiting,type,noreset,settime,scrolldir,cameraxoffset,camerazoffset,rocking;
 float scrollspeed;
 s_spawn_entry *spawnpoints;
} storage,*level=&storage;
static entity actors[4];
static struct {entity *ent;} player[4];
static int maxplayers[]={3},current_set;
static struct {int hRes,vRes;} videomodes={320,240};
static struct {int musicvol;} savedata;
static unsigned time;
static int freezeall,level_completed,current_spawn,groupmin,groupmax,go_time,timeleft,
 musicoffset,musicloop,nojoin,light[2],shadowcolor,shadowalpha,panel_height,cameratype,enemy_count,spawn_calls;
static float scrolldx,scrolldy,advancex,advancey,scrollminz,scrollmaxz,blockade,musicfade[2];
static char musicname[129];
#undef assert
#define assert(c) do{if(!(c)){fprintf(stderr,"Camera step revision=%u case=%u line=%d x=%g y=%g pos=%d clock=%u\n",obor_profile_build,test_case,__LINE__,(double)advancex,(double)advancey,storage.pos,storage.advancetime);abort();}}while(0)
static entity *findent(int mask){return (mask&TYPE_ENEMY) && enemy_count?&actors[0]:NULL;}
static int count_ents(int mask){assert(mask==TYPE_ENEMY);return enemy_count;}
static void change_system_palette(int index){(void)index;abort();}
static void smartspawn(s_spawn_entry *entry){assert(entry==&spawns[0]);spawn_calls++;enemy_count++;}
@SCROLLERS@
static void coordinates(float x,float z){
 for(int i=0;i<4;i++){actors[i].x=x;actors[i].z=z;actors[i].a=0;}
}
static void reset(void){
 test_case++;
 memset(&storage,0,sizeof(storage));memset(actors,0,sizeof(actors));memset(spawns,0,sizeof(spawns));
 for(int i=0;i<4;i++){player[i].ent=i<3?&actors[i]:NULL;actors[i].modeldata.speed=1;}
 time=21;freezeall=level_completed=0;current_spawn=1;storage.numspawns=2;storage.spawnpoints=spawns;
 groupmin=0;groupmax=1;enemy_count=1;storage.width=1000;panel_height=600;
 storage.pos=17;storage.scrolldir=SCROLL_RIGHT;storage.scrollspeed=1000;
 scrollminz=scrollmaxz=blockade=0;advancex=advancey=80;scrolldx=scrolldy=123;
 cameratype=0;coordinates(400,200);spawn_calls=0;
 musicfade[0]=musicfade[1]=0;strcpy(musicname,"old");musicoffset=11;musicloop=0;savedata.musicvol=64;
}
static void observe(float x,float y,int pos){
 float oldx=advancex,oldy=advancey;update_scroller();
 float dx=advancex-x,dy=advancey-y;
 assert(dx>-0.001f && dx<0.001f && dy>-0.001f && dy<0.001f && storage.pos==pos);
 assert(scrolldx==advancex-oldx && scrolldy==advancey-oldy);
}
static void check(unsigned revision,int integer,int progress,int offsets,int exclusive){
 obor_profile_build=revision;
 reset();observe(integer?81:240,80,integer?81:240);
 /* Fractional input and integer division differ before final coordinate storage. */
 reset();actors[0].x=240.9f;actors[1].x=actors[2].x=241.9f;advancex=80.5f;
 observe(integer?80.5f:722.0f/3-160,80,80);
 reset();advancex=80.75f;storage.scrollspeed=0.5f;coordinates(1000,200);
 observe(integer?81:81.25f,80,81);
 reset();storage.scrollspeed=0;observe(integer?81:80,80,integer?81:80);
 reset();storage.scrollspeed=-0.5f;observe(integer?81:79.5f,80,integer?81:79);
 /* End overshoot, exact edge and a previously advanced progress counter. */
 reset();advancex=680;coordinates(1000,200);observe(680,80,progress==2?18:680);
 reset();advancex=680;coordinates(840,200);observe(680,80,680);
 reset();advancex=680;storage.pos=680;observe(680,80,progress==0?681:680);
 reset();storage.scrolldir=SCROLL_LEFT;advancex=300;storage.scrollspeed=20;coordinates(0,200);
 observe(integer?299:280,80,progress==0?381:progress==1?400:18);
 reset();storage.scrolldir=SCROLL_OUTWARD;advancey=360;coordinates(400,700);
 observe(integer?81:240,360,progress==2?18:360);
 reset();storage.scrolldir=SCROLL_INWARD;advancey=300;storage.scrollspeed=20;coordinates(400,0);
 observe(integer?81:100,integer?299:280,progress==0?61:progress==1?80:18);
 /* The RIGHT clamp order differs for a level narrower than the display. */
 reset();storage.width=300;coordinates(400,200);
 observe(progress==2?-20:0,80,progress==0?18:progress==1?0:18);
 /* Offset selection is direction-specific, including OUTWARD using X. */
 reset();storage.cameraxoffset=11;storage.camerazoffset=17;coordinates(480,300);
 observe(integer?81:331,integer?81:197,integer?81:331);
 reset();storage.scrolldir=SCROLL_LEFT;advancex=600;storage.cameraxoffset=11;storage.camerazoffset=17;coordinates(480,300);
 observe(integer?599:offsets?331:320,integer?81:197,integer?81:offsets?349:360);
 reset();storage.scrolldir=SCROLL_OUTWARD;storage.cameraxoffset=11;storage.camerazoffset=17;coordinates(480,300);
 observe(integer?81:offsets?331:320,integer?81:offsets?191:180,integer?81:offsets?191:180);
 reset();storage.scrolldir=SCROLL_INWARD;advancey=300;storage.cameraxoffset=11;storage.camerazoffset=17;coordinates(480,300);
 observe(integer?81:offsets?331:320,integer?299:offsets?197:180,integer?61:offsets?163:180);
 /* Reverse traversal and fractional blockade values exercise both step directions. */
 reset();storage.scrolldir=SCROLL_RIGHT|SCROLL_BACK;advancex=100.5f;blockade=100.75f;coordinates(100,200);
 observe(integer?100.5f:100.75f,80,100);
 reset();storage.scrolldir=SCROLL_RIGHT|SCROLL_BACK;advancex=300.75f;storage.scrollspeed=20;coordinates(200,200);
 observe(integer?299:280.75f,80,integer?299:280);
 reset();storage.scrolldir=SCROLL_LEFT|SCROLL_BACK;advancex=100.25f;storage.scrollspeed=20;coordinates(800,200);
 observe(integer?101:120.25f,80,integer?579:559);
 reset();storage.scrolldir=SCROLL_OUTWARD|SCROLL_BACK;advancey=300.75f;storage.scrollspeed=20;coordinates(400,200);
 observe(integer?81:100,integer?299:280.75f,integer?299:280);
 reset();storage.scrolldir=SCROLL_INWARD|SCROLL_BACK;advancey=100.25f;storage.scrollspeed=20;coordinates(400,500);
 observe(integer?81:100,integer?101:120.25f,integer?259:239);
 reset();storage.scrolldir=SCROLL_LEFT|SCROLL_BACK;advancex=600;blockade=300.75f;storage.scrollspeed=20;coordinates(1000,200);
 observe(379.25f,80,300);
 /* The shared Z bounds also clamp the orthogonal X path in these builds. */
 for(int lower=0;lower<2;lower++){
  reset();advancey=100.5f;if(lower)scrollminz=100.75f;else scrollmaxz=100.75f;
  coordinates(400,lower?200:300);observe(integer?81:240,integer?100:100.75f,integer?81:240);
  reset();storage.scrolldir=SCROLL_OUTWARD;advancex=100.5f;
  if(lower)scrollminz=100.75f;else scrollmaxz=100.75f;
  coordinates(lower?160:480,200);observe(integer?100:100.75f,80,80);
 }
 reset();advancey=100.25f;storage.scrollspeed=20;coordinates(400,500);
 observe(integer?81:100,integer?101:120.25f,integer?81:100);
 reset();advancey=100.25f;storage.scrollspeed=20;coordinates(400,0);
 observe(integer?81:100,integer?99:80.25f,integer?81:100);
 reset();storage.scrolldir=SCROLL_OUTWARD;advancex=100.25f;storage.scrollspeed=20;coordinates(800,200);
 observe(integer?101:120.25f,80,80);
 reset();storage.scrolldir=SCROLL_OUTWARD;advancex=100.25f;storage.scrollspeed=20;coordinates(0,200);
 observe(integer?99:80.25f,80,80);
 reset();storage.scrolldir=SCROLL_INWARD;advancey=4;coordinates(400,0);
 observe(integer?81:240,4,356);
 reset();storage.scrolldir=SCROLL_OUTWARD;panel_height=220;coordinates(400,700);
 observe(integer?81:240,4,progress==1?4:18);
 /* Waiting still permits the orthogonal auto-scroll path. */
 reset();storage.waiting=1;coordinates(400,300);observe(80,integer?81:180,17);
 reset();storage.scrolldir=SCROLL_UP;observe(80,80,80);observe(80,81,81);
 reset();storage.scrolldir=SCROLL_DOWN;observe(80,80,80);observe(80,81,81);
 /* Every slot participates in the original speed timing check. */
 for(int slot=0;slot<4;slot++)for(int run=0;run<2;run++)for(int fast=0;fast<2;fast++){
  reset();player[slot].ent=&actors[slot];
  if(run)actors[slot].modeldata.runspeed=fast?12:11.9f;
  else actors[slot].modeldata.speed=fast?12:11.9f;
  update_scroller();assert(storage.advancetime==time-(integer && fast));
 }
 reset();time=0;actors[0].modeldata.speed=12;update_scroller();
 assert(storage.advancetime==(integer?UINT32_MAX:0));
 float x=advancex,y=advancey;int pos=storage.pos;time=1;update_scroller();
 if(integer)assert(advancex==x && advancey==y && storage.pos==pos && !scrolldx && !scrolldy);
 reset();freezeall=1;update_scroller();assert(advancex==80 && advancey==80 && storage.advancetime==0 && !scrolldx && !scrolldy);
 reset();storage.advancetime=time+1;update_scroller();assert(advancex==80 && !scrolldx && !scrolldy);
 reset();for(int i=0;i<4;i++)player[i].ent=NULL;update_scroller();
 assert(advancex==80 && advancey==80 && storage.pos==17 && !scrolldx && !scrolldy);
 /* Music-only entries also wait or spawn before the priority boundary. */
 for(int fade=0;fade<2;fade++)for(int song=0;song<2;song++)for(int wait=0;wait<2;wait++){
  if(!fade && !song)continue;
  reset();groupmin=groupmax=2;current_spawn=0;storage.numspawns=1;
  spawns[0].musicfade=fade?2:0;spawns[0].wait=wait;
  if(song){strcpy(spawns[0].music,"song");spawns[0].musicoffset=7;}
  update_scroller();assert(current_spawn==1);
  assert(storage.waiting==(!exclusive && wait));
  assert(spawn_calls==(!exclusive && !wait));
  assert(musicfade[0]==(fade?2:0) && musicfade[1]==(fade?64:0));
  int played=song && (!exclusive || !fade);
  assert(!strcmp(musicname,played?"song":"old") && musicoffset==(played?7:11) && musicloop==played);
 }
}
int main(void){@CHECKS@ puts("early_camera_step=1");return 0;}
'''.replace('@CONSTANTS@', constants).replace('@SCROLLERS@',
        function(source, 'obor_update_scroller_legacy') + '\n' + function(source, 'update_scroller')).replace(
        '@CHECKS@', '\n'.join(contexts))


def render_camera_quake(engine, fixture):
    """Run native loading/event/quake statements with authored numeric oracles."""
    from test_early_jump_walkoff import braced_statement
    core = (engine / 'openbor.c').read_text()
    frame = function(core, 'update_frame')
    event = braced_statement(frame,
        'if(self->animation->quakeframe.framestart+self->animation->quakeframe.cnt == f)')
    gravity = re.search(r'if\(!self->modeldata.noquake\)\s*level->quake\s*=\s*4;',
                        function(core, 'check_gravity'))[0]
    bg = function(core, 'draw_scrolled_bg')
    window = bg[re.search(r'bgbuffer_updated\s*=\s*1;', bg).end():]
    rocking = braced_statement(window, 'if(level->rocking)') + '\n' + braced_statement(window, 'else if(time)')
    decay = braced_statement(window, 'if(level->quake!=0 && time>=level->quaketime)')
    arrays = '\n'.join(re.search(r'static int ' + name + r'\[32\]\s*=\s*\{[^}]+\};', bg, re.S)[0]
                       for name in fixture['rock_tables'])
    expected_tables = '\n'.join('static const int expected_' + name + '[32]={' +
        ','.join(map(str, values)) + '};' for name, values in fixture['rock_tables'].items())
    start = core.index('case CMD_MODEL_QUAKEFRAME:')
    loader = core[start + len('case CMD_MODEL_QUAKEFRAME:'):core.index('case CMD_MODEL_SUBENTITY:', start)]
    initializer = re.search(r'obor_quakeframe_init\(&newanim->quakeframe,\s*obor_profile_build\);', core)[0]
    contexts = ','.join('{%d,%d,%d,%d,%d,%d}' % (
        row['revision'], row['frame_bits'], row['repeat_bits'], row['count_bits'],
        row['amplitude_bits'], row['clear_all_default']) for row in fixture['sources'])
    numbers = ','.join('{%d,%d,%d}' % (row['input'], row['signed8'], row['signed16'])
                       for row in fixture['cases'])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#include "ram.h"
#undef time
#undef printf
#undef exit
#undef shutdown
#undef pause
#undef kill
uint32_t obor_profile_build;
static s_level storage,*level=&storage;
static s_anim animation;
static entity actor,*self=&actor;
static unsigned time;
static int gfx_y_offset;
static s_screen *bgbuffer;
static int models_loaded,nojoin,current_spawn,groupmin,groupmax,level_completed,tospeedup,
 reached[4],showtimeover,pause,endgame,go_time,neon_time,cameratype,light[2];
static float advancex,advancey,scrollminz,scrollmaxz,blockade;
static unsigned cleanup_step,level_cleanup_calls;
void unload_background(void){assert(cleanup_step==0);cleanup_step++;}
void unload_texture(void){assert(cleanup_step==1);cleanup_step++;}
void freepanels(void){assert(cleanup_step==2);cleanup_step++;}
void freescreen(s_screen **screen){assert(cleanup_step==3 && screen==&bgbuffer);cleanup_step++;*screen=NULL;}
void getRamStatus(int unit){assert(unit==BYTES);}
s_model *getModelAt(int index){(void)index;abort();}
s_model *getFirstModel(void){return NULL;}
s_model *getNextModel(void){abort();}
s_model *getCurrentModel(void){abort();}
int free_model(s_model *model){(void)model;abort();}
void free_level(s_level *lv){
 // This provider observes the reset/call order; it does not release static storage.
 assert(lv==&storage && cleanup_step==4 && !lv->name);
 assert(!lv->pos && !lv->waiting && !lv->advancetime && !lv->quake && !lv->quaketime);
 level_cleanup_calls++;
}
@UNLOAD@
@ARRAYS@
@EXPECTED_TABLES@
static int provided[4];
#define GET_INT_ARG(i) (assert((i)>=1 && (i)<=3),provided[i])
static void initialize(s_anim *newanim) {@INITIALIZER@}
static void load(s_anim *newanim,int start,int repeat,int amplitude) {
 provided[1]=start;provided[2]=repeat;provided[3]=amplitude;
 do {@LOADER@}while(0);
}
static void frame(int f) {@EVENT@}
static void impact(void) {@GRAVITY@}
static void draw(void) {int rockpos;@ROCKING@}
static void decay(void) {@DECAY@}
static const struct {int input,v8,v16;} numbers[]={@NUMBERS@};
static const struct {unsigned revision;int frame,repeat,count,amplitude,clear;} contexts[]={@CONTEXTS@};
static int value(unsigned index,int bits) {
 assert(bits==8 || bits==16);return bits==8?numbers[index].v8:numbers[index].v16;
}
int main(void) {
 assert(sizeof(short)==2 && sizeof(int)==4);
 const unsigned count=sizeof(numbers)/sizeof(numbers[0]);
 actor.animation=&animation;
 for(unsigned p=0;p<sizeof(contexts)/sizeof(contexts[0]);++p){
  obor_profile_build=contexts[p].revision;level=&storage;
  assert(contexts[p].repeat==contexts[p].count && contexts[p].repeat==contexts[p].amplitude);
  animation.quakeframe.framestart=31;animation.quakeframe.cnt=14;
  animation.quakeframe.repeat=12;animation.quakeframe.v=13;initialize(&animation);
  assert(animation.quakeframe.framestart==0);
  assert(animation.quakeframe.cnt==(contexts[p].clear?0:14));
  assert(animation.quakeframe.repeat==(contexts[p].clear?0:12));
  assert(animation.quakeframe.v==(contexts[p].clear?0:13));
  for(unsigned i=0;i<count;++i){
   unsigned j=(i+3)%count,k=(i+7)%count;
   // Targeted control for the implementation-defined conversions in the originals.
   volatile int source_value=numbers[i].input;
   signed char original8=source_value;short original16=source_value;
   assert(original8==numbers[i].v8 && original16==numbers[i].v16);
   load(&animation,numbers[i].input,numbers[j].input,numbers[k].input);
   assert(animation.quakeframe.framestart==value(i,contexts[p].frame));
   assert(animation.quakeframe.repeat==value(j,contexts[p].repeat));
   assert(animation.quakeframe.v==value(k,contexts[p].amplitude) && animation.quakeframe.cnt==0);
  }
  // Long original repetitions pass through the signed-eight-bit counter boundary.
  for(unsigned i=0;i<count;++i)for(unsigned amplitude=0;amplitude<2;++amplitude){
   int repeat=value(i,contexts[p].repeat);
   int v=contexts[p].amplitude==16?(amplitude?300:-300):(amplitude?44:-44);
   load(&animation,3,numbers[i].input,amplitude?300:-300);
   int counter=0,steps=repeat>1?repeat+2:3;
   for(int step=0;step<steps;++step){
    storage.quake=777;frame(3+counter+1);
    assert(storage.quake==777 && animation.quakeframe.cnt==counter);
    frame(3+counter);assert(storage.quake==((counter%2 || v>0)?v:-v));
    counter=repeat-counter>1?counter+1:0;
    assert(animation.quakeframe.cnt==counter);
   }
  }
  // The event counter advances outside the level-presence guard.
  load(&animation,3,4,-5);level=NULL;frame(3);assert(animation.quakeframe.cnt==1);
  frame(4);assert(animation.quakeframe.cnt==2);level=&storage;
  // A new level starts without any old private quake value.
  memset(&storage,0,sizeof(storage));assert(storage.quake==0 && storage.quaketime==0);
  for(int blocked=0;blocked<2;++blocked){
   actor.modeldata.noquake=blocked;storage.quake=77;impact();assert(storage.quake==(blocked?77:4));
  }
  const unsigned clocks[]={0,1,24,25,199,200,UINT32_MAX-8,UINT32_MAX-7,UINT32_MAX};
  const int quakes[]={-32768,-300,-128,-5,-3,-1,0,1,3,5,127,128,300,32768};
  for(unsigned c=0;c<sizeof(clocks)/sizeof(clocks[0]);++c)
   for(unsigned q=0;q<sizeof(quakes)/sizeof(quakes[0]);++q){
    time=clocks[c];int quake=quakes[q];
    for(int rocking=0;rocking<=4;++rocking){
     storage.quake=quake;storage.rocking=rocking;gfx_y_offset=53;draw();
     unsigned index=(clocks[c]/(GAME_SPEED/8))&31;
     const int *table=rocking==1?expected_rockoffssine:rocking==2?expected_rockoffsshake:expected_rockoffsrumble;
     int expected=rocking>=1 && rocking<=3?quake-4-table[index]:
       rocking==0 && clocks[c]?(quake>=0?quake-4:quake+4):53;
     assert(gfx_y_offset==expected);
    }
    for(int due=0;due<2;++due){
     storage.quake=quake;storage.quaketime=due?clocks[c]:clocks[c]+1;
     unsigned old_deadline=storage.quaketime;int changes=quake && clocks[c]>=old_deadline;
     decay();int half=quake>=0?quake/2:-((-quake)/2);
     assert(storage.quake==(changes?half:quake));
     assert(storage.quaketime==(changes?clocks[c]+GAME_SPEED/25:old_deadline));
    }
   }
  // Release a populated level, then repeat the call with no level.
  storage.pos=17;storage.waiting=1;storage.advancetime=27;storage.quake=-7;storage.quaketime=31;
  storage.name=malloc(6);assert(storage.name);memcpy(storage.name,"level",6);
  level=&storage;advancex=12.5f;advancey=-3.5f;time=77;cleanup_step=level_cleanup_calls=0;
  unload_level();assert(!level && !storage.name && level_cleanup_calls==1 && cleanup_step==4);
  assert(advancex==0 && advancey==0 && time==0 && gfx_y_offset==0);
  advancex=12.5f;advancey=-3.5f;time=77;cleanup_step=0;
  unload_level();assert(!level && level_cleanup_calls==1 && cleanup_step==4);
  assert(advancex==0 && advancey==0 && time==0 && gfx_y_offset==0);
 }
 printf("quake contexts: %zu\n",sizeof(contexts)/sizeof(contexts[0]));
 return 0;
}
'''.replace('@ARRAYS@', arrays).replace('@EXPECTED_TABLES@', expected_tables).replace(
        '@INITIALIZER@', initializer).replace('@LOADER@', loader).replace('@EVENT@', event).replace(
        '@GRAVITY@', gravity).replace('@ROCKING@', rocking).replace('@DECAY@', decay).replace(
        '@NUMBERS@', numbers).replace('@CONTEXTS@', contexts).replace(
        '@UNLOAD@', function(core, 'unload_level'))


def render_camera_render_origin(engine, rows):
    """Run the actual normal/mirrored queue calls; queue storage is a provider."""
    source = function((engine / 'openbor.c').read_text(), 'display_ents')
    calls = [line.strip() for line in source.splitlines()
             if 'spriteq_add_sprite((int)(e->x' in line and 'e->bound?' in line]
    if len(calls) != 2:
        raise ValueError('Exactly two native entity-origin queue calls required')
    adjustment = re.search(r'const int x_offset\s*=[^;]+;', source)[0]
    header = (engine / 'openbor.h').read_text()
    constants = '\n'.join(re.search(r'^#define\s+' + name + r'\b[^\n]*', header, re.M)[0]
                          for name in ('MIRROR_Z', 'PANEL_Z', 'MAX_ENTS'))
    contexts = ','.join('{%d,%d,%d}' % (
        row['revision'], row['offset_without_level'], row['graphics_adjustment']) for row in rows)
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
@CONSTANTS@
static uint32_t obor_profile_build;
typedef struct entity {float x,z,a;int sortid;struct entity *bound;} entity;
static int PLAYER_MIN_Z=160;
static struct {int unused;} storage,*level;
static float advancex;
static int gfx_x_offset,gfx_y_offset;
static struct {int x,y,z,frame,sort;void *method;} queued[2];
static unsigned queue_size;
static void spriteq_add_sprite(int x,int y,int z,int frame,void *method,int sort) {
 assert(queue_size<2);
 queued[queue_size].x=x;queued[queue_size].y=y;queued[queue_size].z=z;
 queued[queue_size].frame=frame;queued[queue_size].method=method;queued[queue_size++].sort=sort;
}
static void draw(entity *e,int z,int f,void *drawmethod) {
 @ADJUSTMENT@
 @NORMAL@
 @MIRRORED@
}
int main(void) {
 const struct {unsigned revision;int no_level,adjustment;} contexts[]={@CONTEXTS@};
 const float offsets[]={0,19.75f,-19.75f};
 entity parent={0,0,0,17,NULL},actor={45.5f,68.75f,9.25f,31,NULL};
 int method;
 for(unsigned p=0;p<sizeof(contexts)/sizeof(contexts[0]);++p){
  obor_profile_build=contexts[p].revision;
  for(unsigned present=0;present<2;++present)for(unsigned bound=0;bound<2;++bound)
   for(unsigned o=0;o<sizeof(offsets)/sizeof(offsets[0]);++o)
    for(int adjustment=-7;adjustment<=7;adjustment+=7){
     level=present?&storage:NULL;actor.bound=bound?&parent:NULL;
     advancex=offsets[o];gfx_x_offset=adjustment;gfx_y_offset=-3;queue_size=0;
     draw(&actor,13,5,&method);
     const int x=(int)(actor.x-((present||contexts[p].no_level)?offsets[o]:0)
                      +(contexts[p].adjustment?adjustment:0));
     const int sort=bound?parent.sortid-1:actor.sortid;
     assert(queue_size==2);
     for(unsigned mirror=0;mirror<2;++mirror){
      assert(queued[mirror].x==x);
      assert(queued[mirror].y==(int)((mirror?2*MIRROR_Z-actor.z:actor.z)-actor.a-3));
      assert(queued[mirror].z==(mirror?2*PANEL_Z-13:13));
      assert(queued[mirror].sort==(mirror?MAX_ENTS-sort:sort));
      assert(queued[mirror].frame==5 && queued[mirror].method==&method);
     }
    }
 }
 printf("entity camera origins: %zu contexts\n",sizeof(contexts)/sizeof(contexts[0]));
}
'''.replace('@CONSTANTS@', constants).replace('@ADJUSTMENT@', adjustment).replace(
        '@NORMAL@', calls[0]).replace('@MIRRORED@', calls[1]).replace('@CONTEXTS@', contexts)


def render_camera_options(engine, rows):
    """Render command and property contracts with actual variants and lists."""
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utility = (engine / 'source/utils.c').read_text()
    commands = (engine / 'source/gamelib/commands.c').read_text()
    from test_historical_player import switch_cases
    loader = function(core, 'load_level')
    # Give only the outer selector a lexical name; returned case bytes stay exact.
    loader = loader.replace('switch(cmd)', 'switch(obor_camera_command)', 1)
    _, cases = switch_cases(loader, 'load_level', 'obor_camera_command')
    default = re.search(r'level->scrollspeed\s*=\s*1\s*;', function(core, 'load_level'))
    if default is None:
        raise ValueError('Actual camera speed initializer required')
    names = ['prepareList', 'getCommandlistCommand', 'getLevelCommand',
             'createLevelCommandList', 'freeCommandList']
    command_bodies = '\n'.join(function(commands, name) + '\n#undef LIST_ADD' for name in names)
    checks = '\n'.join('check(%d,%d,%d,%d);' % (
        row['revision'], row['command'], row['setter'], row['getter']) for row in rows)
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
#include "ScriptVariant.h"
#include "commands.h"
#undef printf
#define stricmp strcasecmp
uint32_t obor_profile_build;
static struct {float bgspeed,scrollspeed;int cameraxoffset,camerazoffset,rocking;} storage,*level=&storage;
static char cache[4][64],diagnostic[256];
static int collected;
CHAR *StrCache_Get(int index){assert(index>=0 && index<4);return cache[index];}
void StrCache_Collect(int index){assert(index==2);collected++;}
int StrCache_Pop(void){abort();}
static int logged(const char *format,...){
 va_list ap;va_start(ap,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,ap);va_end(ap);
 assert(n>=0 && n<(int)sizeof(diagnostic));return n;
}
@VARIANTS@
@UTILITIES@
@COMMANDS@
#define printf logged
@PROPERTIES@
#undef printf
static List *levelcmdlist;
static float provided_number;
#define GET_FLOAT_ARG(index) (assert((index)==1),provided_number)
static int level_option(char *name,float number){
 levelCommands cmd=getLevelCommand(levelcmdlist,name);provided_number=number;
 switch(cmd){case CMD_LEVEL_SCROLLSPEED:@SPEED_CASE@
 default:return 0;}
 return 1;
}
static void initial_speed(void){@INITIALIZER@}
static ScriptVariant property,value,result,*args[2],*out;
static void call_setup(const char *name){
 memset(&property,0,sizeof(property));memset(&value,0,sizeof(value));memset(&result,0,sizeof(result));
 assert(strlen(name)<sizeof(cache[0]));strcpy(cache[0],name);strcpy(cache[1],"not-a-number");
 strcpy(cache[2],"old-result");
 property.vt=VT_STR;property.strVal=0;value.vt=VT_DECIMAL;value.dblVal=6.75;
 result.vt=VT_STR;result.strVal=2;args[0]=&property;args[1]=&value;out=&result;
 collected=0;diagnostic[0]=0;
}
static void read_property(const char *name,int supported,int decimal,double expected){
 call_setup(name);ScriptVariant before=property;
 HRESULT status=openbor_getlevelproperty(args,&out,1);
 assert(!memcmp(&before,&property,sizeof(property)));
 if(supported){
  assert(status==S_OK && out==&result && collected==1 && !diagnostic[0]);
  assert(result.vt==(decimal?VT_DECIMAL:VT_INTEGER));
  assert(decimal?result.dblVal==expected:result.lVal==(LONG)expected);
 }else{
  char expected_message[256];snprintf(expected_message,sizeof(expected_message),
   "Property name '%s' is not supported by function getlevelproperty.\n",name);
  assert(status==E_FAIL && !out && !collected && result.vt==VT_STR && result.strVal==2);
  assert(!strcmp(diagnostic,expected_message));
 }
}
static void check(unsigned revision,int command,int setter,int getter){
 obor_profile_build=revision;assert(sizeof(LONG)==4);
 memset(&storage,0,sizeof(storage));initial_speed();assert(level->scrollspeed==1);
 levelcmdlist=createLevelCommandList();assert(levelcmdlist);
 char lower[]="scrollspeed",upper[]="SCROLLSPEED",known[]="bgspeed";
 assert(getLevelCommand(levelcmdlist,known)==CMD_LEVEL_BGSPEED);
 assert(level_option(lower,1.25f)==command && level->scrollspeed==(command?1.25f:1));
 assert(level_option(upper,2.5f)==command && level->scrollspeed==(command?2.5f:1));
 freeCommandList(levelcmdlist);levelcmdlist=NULL;
 storage.bgspeed=2.75f;storage.cameraxoffset=11;storage.camerazoffset=-5;storage.scrollspeed=1.25f;
 read_property("bgspeed",1,0,2);read_property("cameraxoffset",1,0,11);read_property("camerazoffset",1,0,-5);
 read_property("scrollspeed",getter,1,1.25);read_property("SCROLLSPEED",getter,1,1.25);
 read_property("unknown",0,0,0);read_property("",0,0,0);
 for(int bad_value=0;bad_value<2;bad_value++){
  storage.scrollspeed=1.25f;call_setup("scrollspeed");
  if(bad_value){value.vt=VT_STR;value.strVal=1;}
  ScriptVariant name_before=property,value_before=value;
  assert(openbor_changelevelproperty(args,&out,2)==S_OK && out==&result && result.vt==VT_INTEGER);
  assert(result.lVal==(!setter || !bad_value) && collected==1 && !diagnostic[0]);
  assert(storage.scrollspeed==(setter && !bad_value?6:1.25f));
  assert(!memcmp(&name_before,&property,sizeof(property)) && !memcmp(&value_before,&value,sizeof(value)));
 }
 storage.scrollspeed=1.25f;call_setup("SCROLLSPEED");
 assert(openbor_changelevelproperty(args,&out,2)==S_OK && out==&result && result.lVal==1 && storage.scrollspeed==1.25f);
 const char *names[]={"bgspeed","cameraxoffset","camerazoffset","rock","unknown"};
 for(unsigned i=0;i<sizeof(names)/sizeof(*names);i++){
  storage.bgspeed=2.75f;storage.cameraxoffset=11;storage.camerazoffset=-5;storage.rocking=0;
  call_setup(names[i]);value.dblVal=-6.75;
  assert(openbor_changelevelproperty(args,&out,2)==S_OK && out==&result && result.lVal==1 && collected==1);
  assert(storage.bgspeed==(i==0?-6:2.75f) && storage.cameraxoffset==(i==1?-6:11) &&
   storage.camerazoffset==(i==2?-6:-5) && storage.rocking==(i==3?-6:0));
 }
 call_setup("scrollspeed");property.vt=VT_INTEGER;property.lVal=0;
 assert(openbor_getlevelproperty(args,&out,1)==E_FAIL && !out && !collected);
 assert(!strcmp(diagnostic,"Function getlevelproperty must have a string property name.\n"));
 call_setup("scrollspeed");property.vt=VT_INTEGER;
 assert(openbor_changelevelproperty(args,&out,2)==E_FAIL && !out && !collected);
 call_setup("scrollspeed");
 assert(openbor_changelevelproperty(args,&out,1)==E_FAIL && !out && !collected);
}
int main(void){@CHECKS@ puts("camera_options=1");return 0;}
'''.replace('@VARIANTS@', '\n'.join(function(variants, n) for n in [
        'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue'])).replace(
        '@UTILITIES@', '\n'.join(function(utility, n) for n in ['lc', 'searchList'])).replace(
        '@COMMANDS@', command_bodies).replace('@PROPERTIES@',
        '\n'.join(function(script, n) for n in ['openbor_getlevelproperty', 'openbor_changelevelproperty'])).replace(
        '@SPEED_CASE@', cases['CMD_LEVEL_SCROLLSPEED']['body']).replace(
        '@INITIALIZER@', default[0]).replace('@CHECKS@', checks)
