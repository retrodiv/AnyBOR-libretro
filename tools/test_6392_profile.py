"""Exercise the reconstructed test profile at its native C boundaries.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
import json
from pathlib import Path
import re
import unittest
from test_historical_player import function
from test_historical_behavior import native

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
ENGINE = Path(os.environ.get('OBOR_6392_ENGINE', ROOT / 'src/engines/6391'))
ABI = Path(os.environ.get('OBOR_PROFILE_ABI_HEADER', ROOT / 'src/glue/obor_abi.h'))


def native_profile(program):
    native(program.replace('#include "obor_abi.h"',
                           '#include ' + json.dumps(ABI.resolve().as_posix())))


class Reconstructed6392Tests(unittest.TestCase):
    def test_airborne_juggle_contract_matches_official_and_both_variants(self):
        source = (ENGINE / 'openbor.c').read_text()
        attack = function(source, 'do_attack')
        start = attack.index('        // If in the air, then check the juggle cost.')
        reject = attack[start:attack.index('        temp = self;', start)]
        debit = re.search(r'if\(inair\(self\)\)\s*\{\s*'
                          r'self->modeldata.jugglepoints.current = '
                          r'self->modeldata.jugglepoints.current - attack->jugglecost;[^}]*\}',
                          attack).group()
        native_profile(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "obor_abi.h"
typedef struct { struct {float y;} position;float base;int falling;
                 struct {struct {int current;} jugglepoints;} modeldata; } entity;
typedef struct {int jugglecost;} s_collision_attack;
static uint32_t obor_profile_build;
@AIR@
static int collide(entity *target,s_collision_attack *attack){
    entity *self=target;
    do { @REJECT@ @DEBIT@ return 1; } while(0);
    return 0;
}
int main(void){
    const char *keys[]={"6391","6391-mod","6392"};
    const unsigned builds[]={6391,6391,6392};
    for(unsigned p=0;p<3;++p){
        assert(keys[p][0]);obor_profile_build=builds[p];
        for(int air=0;air<2;++air)for(int falling=0;falling<2;++falling)
        for(int points=0;points<=4;++points)for(int cost=0;cost<=5;++cost){
            entity target={0};target.position.y=air?3.0f:0.0f;
            target.falling=falling;target.modeldata.jugglepoints.current=points;
            s_collision_attack attack={cost};
            int accepted=collide(&target,&attack);
            assert(accepted==(!air || cost<=points));
            assert(target.modeldata.jugglepoints.current==
                   ((accepted && air)?points-cost:points));
        }
    }
}
'''.replace('@AIR@', function(source, 'diff') + '\n' + function(source, 'inair'))
           .replace('@REJECT@', reject).replace('@DEBIT@', debit))

    def test_four_incoming_ids_toggle_and_independent_history(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        fields = re.search(r'unsigned int attack_id_incoming;\s*'
                           r'unsigned int attack_id_incoming2;\s*'
                           r'unsigned int attack_id_incoming3;\s*'
                           r'unsigned int attack_id_incoming4;', header).group()
        methods = '\n'.join(function(source, n) for n in
                            ('obor_attack_seen', 'obor_remember_attack'))
        attack = function(source, 'do_attack')
        self.assertEqual(attack.count('obor_remember_attack(self, current_attack_id);'), 2)
        self.assertIn('obor_attack_seen(target, current_attack_id, attack->ignore_attack_id)', attack)
        default = re.search(r'int\s+multihitcheat\s*=\s*0;', source).group()
        native_profile(r'''
#include <assert.h>
#include <stdint.h>
#include "obor_abi.h"
#include <string.h>
typedef struct { FIELDS } entity;
static uint32_t obor_profile_build,obor_profile_features;
DEFAULT
METHODS
int main(void) {
    for(unsigned ordinal=6330;ordinal<=6511;++ordinal) {
        unsigned profile=ordinal==6511?6391:ordinal;
        int variant=ordinal==6511;
        int history=(profile==6392 || variant);
        obor_profile_features=history?(OBOR_PROFILE_ATTACK_HISTORY_FOUR|OBOR_PROFILE_SELECTION_ESCAPE_9):0;
        entity a={0},b={0},saved;
        obor_profile_build=profile;multihitcheat=0;
        for(unsigned id=1;id<=8;++id) {
            obor_remember_attack(&a,id);
            assert(a.attack_id_incoming==id);
            for(unsigned old=0;old<=8;++old) {
                int seen=(old==id)||(history && id>=4 && old>=id-3 && old<=id);
                if(id>=4)assert(obor_attack_seen(&a,old,0)==seen);
                assert(!obor_attack_seen(&a,old,1));
            }
        }
        assert(b.attack_id_incoming==0 && !obor_attack_seen(&b,8,0));
        memcpy(&saved,&a,sizeof(a));obor_remember_attack(&a,9);
        memcpy(&a,&saved,sizeof(a));
        assert(obor_attack_seen(&a,8,0) && !obor_attack_seen(&a,9,0));
        assert(obor_attack_seen(&a,5,0)==history);
        multihitcheat=1;
        assert(obor_attack_seen(&a,8,0) && !obor_attack_seen(&a,7,0));
        obor_remember_attack(&a,9);multihitcheat=0;
        assert(obor_attack_seen(&a,6,0)==history);
    }
}
'''.replace('FIELDS', fields).replace('DEFAULT', default).replace('METHODS', methods))

    def test_selection_escape_flags_alias_and_registration(self):
        source = (ENGINE / 'openbor.c').read_text()
        script = (ENGINE / 'openborscript.c').read_text()
        index = (ENGINE / 'source/openborscript/index.c').read_text()
        select = function(source, 'selectplayer')
        start = select.index('        if((bothnewkeys & FLAG_ESC)')
        end = select.index('\n        }', start) + len('\n        }')
        escape = select[start:end]
        registration = re.search(r'    if\(obor_profile_build == 6392\)\s*'
                                 r'List_InsertAfter\(&theFunctionList,\s*'
                                 r'\(void \*\)openbor_backtotitle, "backtotitle"\);', index).group()
        methods = '\n'.join((function(source, 'goto_mainmenu'),
                             function(script, 'openbor_backtotitle'),
                             function(script, 'openbor_gotomainmenu')))
        native_profile(r'''
#include <assert.h>
#include <stdint.h>
#include "obor_abi.h"
#include <stddef.h>
#include <limits.h>
#include <string.h>
typedef int LONG,HRESULT;
typedef struct { int vt;LONG lVal; } ScriptVariant;
#define S_OK 0
#define E_FAIL (-1)
#define FAILED(x) ((x)<0)
#define FLAG_ESC 1
static uint32_t obor_profile_build,obor_profile_features;
static int escape_flag,goto_mainmenu_flag,registered,theFunctionList;
static int ScriptVariant_IntegerValue(ScriptVariant *v,LONG *out) {
    if(v->vt!=1)return E_FAIL;
    *out=v->lVal;return S_OK;
}
METHODS
static void List_InsertAfter(int *list,void *fn,const char *name) {
    assert(list==&theFunctionList && fn==(void *)openbor_backtotitle && !strcmp(name,"backtotitle"));
    ++registered;
}
static void registration(void) { REGISTRATION }
static int selection_step(int bothnewkeys) { int escape=0; @ESCAPE_BLOCK@ return escape; }
int main(void) {
    for(unsigned ordinal=6330;ordinal<=6511;++ordinal) {
        unsigned profile=ordinal==6511?6391:ordinal;
        int variant=ordinal==6511;
        int history=(profile==6392 || variant);
        obor_profile_features=history?(OBOR_PROFILE_ATTACK_HISTORY_FOUR|OBOR_PROFILE_SELECTION_ESCAPE_9):0;
        obor_profile_build=profile;registered=0;registration();
        assert(registered==(profile==6392));
        escape_flag=0;goto_mainmenu_flag=0;
        ScriptVariant arg={1,9},result={0},*out=&result,*args[]={&arg};
        assert(openbor_gotomainmenu(args,&out,1)==S_OK && !out && goto_mainmenu_flag==19);
        assert(selection_step(0)==history);
        assert(escape_flag==0 && !selection_step(0));
        arg.lVal=11;out=&result;
        assert(openbor_gotomainmenu(args,&out,1)==S_OK && !selection_step(0));
        assert(selection_step(FLAG_ESC));
        if(history)assert(escape_flag==0);
        escape_flag=0;arg.lVal=1;out=&result;
        assert(openbor_backtotitle(args,&out,1)==(profile==6392?S_OK:E_FAIL) && !out);
        assert(selection_step(0)==(profile==6392));
        arg.lVal=0;assert(openbor_backtotitle(args,&out,1)==(profile==6392?S_OK:E_FAIL));
        assert(!selection_step(0));
        arg.vt=0;escape_flag=0;
        assert(openbor_backtotitle(args,&out,1)==E_FAIL && !escape_flag);
        assert(openbor_backtotitle(NULL,&out,0)==E_FAIL && !escape_flag);
        assert(openbor_gotomainmenu(NULL,&out,0)==S_OK && goto_mainmenu_flag==1);
        if(history)assert(!escape_flag);
        arg=(ScriptVariant){1,INT_MIN};assert(openbor_gotomainmenu(args,&out,1)==S_OK);
    }
}
'''.replace('METHODS', methods).replace('REGISTRATION', registration).replace('@ESCAPE_BLOCK@', escape))

    def test_cheat_menu_layout_toggle_back_and_forced_off(self):
        source = (ENGINE / 'openbor.c').read_text()
        native_profile(r'''
#include <assert.h>
#include <stdint.h>
#include "obor_abi.h"
#include <stdarg.h>
#include <stddef.h>
#include <string.h>
static uint32_t obor_profile_build,obor_profile_features;
static int cheats,forcecheatsoff,_pause,optionsMenu,bothnewkeys;
static int livescheat,creditscheat,healthcheat,multihitcheat;
static int SAMPLE_BEEP=-1,SAMPLE_BEEP2=-1;
static struct { int effectvol; } savedata;
static void *level;
enum { FLAG_ESC=1,FLAG_MOVEUP=2,FLAG_MOVEDOWN=4,FLAG_MOVELEFT=8,FLAG_MOVERIGHT=16,FLAG_ANYBUTTON=32 };
static int keys[64],cursor,keycount,drawn_multihit,selected_multihit,selected_back,selected_health;
#define Tr(x) (x)
static void _menutextm(int selected,int y,int unused,const char *text) {
    (void)y;(void)unused;
    if(selected && !strcmp(text,"Back"))++selected_back;
}
static void _menutext(int selected,int x,int y,const char *text,...) {
    (void)x;(void)y;
    if(!strncmp(text,"Multihit",8)) {++drawn_multihit;if(selected)++selected_multihit;}
    if(selected && !strncmp(text,"Infinite Health",15))++selected_health;
}
static void update(int ingame,int unused) {
    assert(ingame==(level!=NULL) && !unused && cursor<keycount);
    bothnewkeys=keys[cursor++];
}
static void sound_play_sample(int a,int b,int c,int d,int e) { (void)a;(void)b;(void)c;(void)d;(void)e; }
static void menu_options_video(void) {}
static void menu_options_sound(void) {}
static void menu_options_input(void) {}
static void menu_options_system(void) { cheats=!cheats; }
static void savesettings(void) {}
METHOD
static void begin(void) {
    cursor=keycount=0;drawn_multihit=selected_multihit=selected_back=selected_health=0;
    livescheat=creditscheat=healthcheat=multihitcheat=0;
}
static void key(int k) { assert(keycount<64);keys[keycount++]=k; }
int main(void) {
    const unsigned profiles[]={6330,6391,6392,6412,6510,6391};
    for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
        obor_profile_build=profiles[p];
        int history=(profiles[p]==6392 || p==5);
        obor_profile_features=history?(OBOR_PROFILE_ATTACK_HISTORY_FOUR|OBOR_PROFILE_SELECTION_ESCAPE_9):0;
        for(int paused=0;paused<2;++paused)for(int off=0;off<2;++off) {
            begin();cheats=1;forcecheatsoff=off;_pause=paused;level=paused?&savedata:NULL;
            int back=off?4:(history?8:7);
            for(int i=0;i<back;++i)key(FLAG_MOVEDOWN);
            key(0);key(FLAG_ANYBUTTON);menu_options();
            assert(cursor==keycount && selected_back && !multihitcheat);
            assert((drawn_multihit>0)==(!off && history));
            assert(!optionsMenu && !bothnewkeys && _pause==(paused?2:0));
        }
        begin();cheats=1;forcecheatsoff=0;_pause=0;level=NULL;
        for(int i=0;i<7;++i)key(FLAG_MOVEDOWN);
        key(FLAG_ANYBUTTON);
        if(history)key(FLAG_ESC);
        menu_options();assert(multihitcheat==(history));
        begin();cheats=0;forcecheatsoff=0;
        for(int i=0;i<3;++i)key(FLAG_MOVEDOWN);
        key(FLAG_ANYBUTTON); /* Enable cheats in System Options. */
        key(FLAG_MOVEUP); /* Wrap from Video Options to Back. */
        key(FLAG_ESC);menu_options();assert(cheats && cursor==keycount);
    }
}
'''.replace('METHOD', function(source, 'menu_options')))


if __name__ == '__main__':
    unittest.main()
