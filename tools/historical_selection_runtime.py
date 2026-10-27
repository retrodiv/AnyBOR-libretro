"""Render native duplicate-name decisions and final-player countdowns.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import re
from test_historical_player import function


def render_selection_runtime(engine, fixture):
    source = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()

    def comparison(name):
        body = function(source, name)
        first = body.index('player[i].name,player[x].name')
        start = body.rfind('if(', 0, first) + 2
        if start < 2:
            raise ValueError('Missing native name-comparison condition')
        depth = 0
        for end in range(start, len(body)):
            depth += (body[end] == '(') - (body[end] == ')')
            if not depth:
                return body[start + 1:end]
        raise ValueError('Unclosed native name-comparison condition')

    constants = '\n'.join(re.search(r'(?m)^#define\s+' + name + r'\s+[^\n]+', header)[0]
                          for name in ('GAME_SPEED', 'COUNTER_SPEED', 'TYPE_NONE'))
    checks = '\n'.join('obor_profile_build=%d;check(%d,%d);' % (
        row['revision'], row['names_casefold_full'], row['join_gates_half_counter'])
        for row in fixture['sources'])
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#ifndef PROBE_FOCUS
#define PROBE_FOCUS 0
#endif
#define stricmp strcasecmp
@CONSTANTS@
static uint32_t obor_profile_build;
static unsigned cases;
static int sample,joining_mask,credit_mask;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"selection profile=%u focus=%d sample=%d joining=%d credits=%d line=%d\n",obor_profile_build,PROBE_FOCUS,sample,joining_mask,credit_mask,__LINE__);abort();}}while(0)
typedef struct {int health,mp,nodieblink,type,weaploss[3];} Model;
typedef struct Entity {int playerindex,rush[2];Model modeldata;void (*think)(void),(*takeaction)(void);} Entity;
static struct {char name[32];int lives,credits,joining,spawnhealth,spawnmp,weapnum;Entity *ent;} player[4];
static Entity actor,other,*self=&actor,*firstplayer;
static struct {int setweap,noreset,settime;} room,*level=&room;
static int livescheat,nomaxrushreset[5],timeleft,noshare,credits,nodropen;
static unsigned deaths,kills;
static void execute_pdie_script(int i){assert(i==self->playerindex);++deaths;}
static void kill(Entity *ent){assert(ent==self);++kills;}
static void spawnplayer(int i){(void)i;assert(0);}
static void execute_respawn_script(int i){(void)i;assert(0);}
static void control_rumble(int i,int value){(void)i;(void)value;assert(0);}
static void drop_all_enemies(void){assert(0);}
@DIE@
static int update_duplicate(int i,int x){return (@UPDATE@);}
static int select_duplicate(int i,int x){return (@SELECT@);}
static void check(int full,int join_gate){
    const char *pairs[][2]={{"A","A"},{"A","AB"},{"AB","A"},{"a","A"},
        {"AB","ab"},{"","AB"},{"AB",""},{"A","B"},{"",""},{"A ","A"}};
    const int prefix[]={1,1,0,0,0,1,0,0,1,0};
    const int folded[]={1,0,0,1,1,0,0,0,1,0};
    if(PROBE_FOCUS!=2)for(sample=0;sample<10;++sample)for(int same=0;same<2;++same){
        strcpy(player[0].name,pairs[sample][0]);strcpy(player[1].name,pairs[sample][1]);
        int expected=!same && (full?folded[sample]:prefix[sample]);
        assert(update_duplicate(0,same?0:1)==expected);
        assert(select_duplicate(0,same?0:1)==expected);++cases;
    }
    const int credit_cases[]={0,1,2,4,8,16,31};
    if(PROBE_FOCUS!=1)for(sample=0;sample<4;++sample)
    for(joining_mask=0;joining_mask<16;++joining_mask)
    for(unsigned c=0;c<sizeof(credit_cases)/sizeof(*credit_cases);++c)
    for(noshare=0;noshare<2;++noshare)for(int live=0;live<2;++live){
        credit_mask=credit_cases[c];memset(player,0,sizeof(player));memset(&actor,0,sizeof(actor));
        actor.playerindex=sample;actor.modeldata.health=101;actor.modeldata.mp=52;
        actor.modeldata.nodieblink=live?3:0;actor.modeldata.weaploss[0]=live?4:3;
        actor.rush[1]=9;firstplayer=self;
        for(int i=0;i<4;++i){player[i].joining=(joining_mask>>i)&1;
            player[i].credits=(credit_mask>>i)&1;}
        player[sample].lives=1;player[sample].ent=self;player[sample].weapnum=12;
        if(live)player[(sample+1)%4].ent=&other;
        livescheat=0;nomaxrushreset[4]=1;nomaxrushreset[sample]=7;
        level->setweap=5;credits=(credit_mask>>4)&1;timeleft=12345;deaths=kills=0;
        player_die();
        int no_credit=noshare?(credit_mask&15)==0:!(credit_mask&16);
        int expected=live?12345:no_credit && (!join_gate || !(joining_mask&3))?
            COUNTER_SPEED/2:10*COUNTER_SPEED;
        assert(timeleft==expected && deaths==1 && kills==(unsigned)!live);
        assert(firstplayer==NULL && player[sample].ent==NULL && player[sample].lives==0);
        assert(player[sample].spawnhealth==101 && player[sample].spawnmp==52);
        assert(player[sample].weapnum==(live?12:5) && nomaxrushreset[sample]==0);++cases;
    }
}
int main(void){@CHECKS@
    printf("{\"status\":\"PASS\",\"cases\":%u}\n",cases);return 0;
}
'''.replace('@CONSTANTS@', constants).replace('@DIE@', function(source, 'player_die')).replace(
        '@UPDATE@', comparison('updatestatus')).replace('@SELECT@', comparison('selectplayer')).replace(
        '@CHECKS@', checks)
