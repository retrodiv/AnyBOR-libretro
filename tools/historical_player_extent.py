"""Render native player defaults and regular input with controlled devices.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re
from test_historical_player import function


def render_player_extent(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    if '#ifndef DISABLE_MOVIE\n#define DISABLE_MOVIE\n#endif' not in source:
        raise ValueError('The source must disable the movie input branch')
    names = ('MAX_PLAYERS', 'MAX_SPECIAL_INPUTS', 'MAX_NAME_LEN', 'GAME_SPEED',
             'FLAG_ESC', 'FLAG_MOVELEFT', 'FLAG_MOVERIGHT', 'FLAG_FORWARD', 'FLAG_BACKWARD')
    constants = '\n'.join(re.search(r'(?m)^#define\s+' + name + r'\s+[^\n]+', header)[0]
                          for name in names)
    declarations = '\n'.join(re.search(r'typedef struct\s*\{[^{}]*\}' + name + ';', header)[0]
                             for name in ('s_set_entry', 's_player'))
    loader = function(source, 'load_levelorder')
    commands = loader[loader.index('case CMD_LEVELORDER_SINGLE:'):
                      loader.index('case CMD_LEVELORDER_NOSAME:')]
    bodies = function(source, 'add_set') + function(source, 'inputrefresh')
    checks = '\n'.join('obor_profile_build=%d;check(%d,%d);' % (
        row['revision'], row['global_player_default'], row['refresh_all_ports'])
        for row in fixture['sources'])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef PROBE_FOCUS
#define PROBE_FOCUS 0
#endif
#define DISABLE_MOVIE 1
@CONSTANTS@
typedef uint32_t u32;
typedef struct {u32 movetime;int direction;} entity;
typedef struct s_level_entry s_level_entry;
@DECLARATIONS@
static uint32_t obor_profile_build;
static unsigned cases,control_calls;
static int argument,current_set,defaultmaxplayers,num_difficulties;
static int pattern,frontend_all,requested,extent;
static u32 interval,time=100,bothkeys,bothnewkeys;
static s_set_entry *levelsets;
static s_player player[MAX_PLAYERS];
static entity entities[MAX_PLAYERS];
typedef struct {u32 keyflags,newkeyflags;} Control;
static Control controls[MAX_PLAYERS],*playercontrolpointers[MAX_PLAYERS];
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"player extent profile=%u focus=%d extent=%d pattern=%d all=%d line=%d\n",obor_profile_build,PROBE_FOCUS,extent,pattern,frontend_all,__LINE__);abort();}}while(0)
static u32 incoming_new(void){return pattern==0?0:pattern==1?FLAG_MOVELEFT:pattern==2?FLAG_MOVERIGHT:0x100u;}
static void control_update(Control **ports,int count){
    ++control_calls;requested=count;assert(count>=0 && count<=MAX_PLAYERS);
    for(int i=0;i<(frontend_all?MAX_PLAYERS:count);++i){
        ports[i]->keyflags=0x10cu;ports[i]->newkeyflags=incoming_new();}
}
static u32 timer_getinterval(int speed){
    assert(speed==GAME_SPEED);return pattern==0?GAME_SPEED+1:pattern==1?GAME_SPEED/4+1:pattern==2?3:0;
}
@BODIES@
enum {CMD_LEVELORDER_SINGLE,CMD_LEVELORDER_MAXPLAYERS};
#define GET_INT_ARG(i) ((void)(i),argument)
static void command(s_set_entry *set,int cmd){switch(cmd){@COMMANDS@}}
static void defaults(int global){
    defaultmaxplayers=3;num_difficulties=0;levelsets=NULL;
    s_set_entry *first=add_set();assert(first && first->maxplayers==(global?3:2));
    free(levelsets);levelsets=NULL;++cases;
    for(int cmd=0;cmd<2;++cmd)for(argument=0;argument<5;++argument){
        defaultmaxplayers=2;num_difficulties=0;
        command(NULL,cmd);int configured=cmd?argument:1;
        assert(defaultmaxplayers==(global?configured:2));
        first=add_set();assert(first && first->maxplayers==(global?configured:2));
        command(first,cmd);assert(first->maxplayers==configured);
        s_set_entry *second=add_set();assert(second && second->maxplayers==(global?configured:2));
        assert(num_difficulties==2 && levelsets[0].maxplayers==configured);
        free(levelsets);levelsets=NULL;++cases;
    }
}
static void inputs(int all){
    s_set_entry selected={0};levelsets=&selected;current_set=0;
    for(extent=0;extent<=MAX_PLAYERS;++extent)
    for(frontend_all=0;frontend_all<2;++frontend_all)
    for(pattern=0;pattern<4;++pattern){
        selected.maxplayers=extent;memset(player,0,sizeof(player));memset(entities,0,sizeof(entities));
        for(int i=0;i<MAX_PLAYERS;++i){
            playercontrolpointers[i]=&controls[i];controls[i]=(Control){0,0};
            player[i].keys=player[i].playkeys=0x8000u;player[i].newkeys=0x4000u;
            player[i].releasekeys=0x2000u;player[i].combostep=2;
            for(int j=0;j<MAX_SPECIAL_INPUTS;++j){player[i].combokey[j]=0x55;player[i].inputtime[j]=5;}
            if(pattern==1 || pattern==2){player[i].ent=&entities[i];
                entities[i].movetime=pattern==1?99:1000;entities[i].direction=i&1;}
        }
        s_player before[MAX_PLAYERS];memcpy(before,player,sizeof(player));
        control_calls=0;requested=-1;bothkeys=bothnewkeys=0xffffffffu;inputrefresh();
        int count=all?MAX_PLAYERS:extent;assert(control_calls==1 && requested==count);
        assert(interval==(pattern==0?1u:pattern==1?GAME_SPEED/4:pattern==2?3u:0u));
        assert(bothkeys==(count?0x10cu:0));assert(bothnewkeys==(count?incoming_new():0));
        for(int i=0;i<MAX_PLAYERS;++i){
            if(i>=count){assert(!memcmp(&player[i],&before[i],sizeof(s_player)));
                if(player[i].ent){assert(entities[i].movetime==(pattern==1?99u:1000u));}
                continue;
            }
            assert(player[i].keys==0x10cu && player[i].newkeys==incoming_new());
            assert(player[i].playkeys==incoming_new() && player[i].releasekeys==0x8000u);
            assert(player[i].combostep==(pattern==0?2:pattern==1?1:3));
            if(pattern){
                int index=pattern==1?0:2;u32 key=incoming_new();
                if(pattern==1)key|=(i&1)?FLAG_BACKWARD:FLAG_FORWARD;
                if(pattern==2)key|=(i&1)?FLAG_FORWARD:FLAG_BACKWARD;
                assert(player[i].combokey[index]==key && player[i].inputtime[index]==time);
                if(player[i].ent)assert(entities[i].movetime==time+GAME_SPEED/4);
            }
            for(int j=0;j<MAX_SPECIAL_INPUTS;++j){
                if(pattern && j==(pattern==1?0:2))continue;
                assert(player[i].combokey[j]==(pattern==1?0u:0x55u));
                assert(player[i].inputtime[j]==(pattern==1?0u:5u));
            }
        }
        ++cases;
    }
    levelsets=NULL;
}
static void check(int global,int all){
    if(PROBE_FOCUS!=2)defaults(global);
    if(PROBE_FOCUS!=1)inputs(all);
}
int main(void){@CHECKS@
    printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''.replace('@CONSTANTS@', constants).replace('@DECLARATIONS@', declarations).replace(
        '@BODIES@', bodies).replace('@COMMANDS@', commands).replace('@CHECKS@', checks)
