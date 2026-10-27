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
