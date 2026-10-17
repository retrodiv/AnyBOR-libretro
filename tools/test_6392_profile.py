"""Exercise the reconstructed test profile at its native C boundaries.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import re
import unittest
from test_historical_player import function
from test_historical_behavior import native

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
ENGINE = Path(os.environ.get('OBOR_6392_ENGINE', ROOT / 'src/engines/6391'))


class Reconstructed6392Tests(unittest.TestCase):
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
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef struct { FIELDS } entity;
static uint32_t obor_profile_build;
DEFAULT
METHODS
int main(void) {
    for(unsigned profile=6330;profile<=6510;++profile) {
        entity a={0},b={0},saved;
        obor_profile_build=profile;multihitcheat=0;
        for(unsigned id=1;id<=8;++id) {
            obor_remember_attack(&a,id);
            assert(a.attack_id_incoming==id);
            for(unsigned old=0;old<=8;++old) {
                int seen=(old==id)||(profile==6392 && id>=4 && old>=id-3 && old<=id);
                if(id>=4)assert(obor_attack_seen(&a,old,0)==seen);
                assert(!obor_attack_seen(&a,old,1));
            }
        }
        assert(b.attack_id_incoming==0 && !obor_attack_seen(&b,8,0));
        memcpy(&saved,&a,sizeof(a));obor_remember_attack(&a,9);
        memcpy(&a,&saved,sizeof(a));
        assert(obor_attack_seen(&a,8,0) && !obor_attack_seen(&a,9,0));
        assert(obor_attack_seen(&a,5,0)==(profile==6392));
        multihitcheat=1;
        assert(obor_attack_seen(&a,8,0) && !obor_attack_seen(&a,7,0));
        obor_remember_attack(&a,9);multihitcheat=0;
        assert(obor_attack_seen(&a,6,0)==(profile==6392));
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
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <limits.h>
#include <string.h>
typedef int LONG,HRESULT;
typedef struct { int vt;LONG lVal; } ScriptVariant;
#define S_OK 0
#define E_FAIL (-1)
#define FAILED(x) ((x)<0)
#define FLAG_ESC 1
static uint32_t obor_profile_build;
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
static int selection_step(int bothnewkeys) { int escape=0; ESCAPE return escape; }
int main(void) {
    for(unsigned profile=6330;profile<=6510;++profile) {
        obor_profile_build=profile;registered=0;registration();
        assert(registered==(profile==6392));
        escape_flag=0;goto_mainmenu_flag=0;
        ScriptVariant arg={1,9},result={0},*out=&result,*args[]={&arg};
        assert(openbor_gotomainmenu(args,&out,1)==S_OK && !out && goto_mainmenu_flag==19);
        assert(selection_step(0)==(profile==6392));
        assert(escape_flag==0 && !selection_step(0));
        arg.lVal=11;out=&result;
        assert(openbor_gotomainmenu(args,&out,1)==S_OK && !selection_step(0));
        assert(selection_step(FLAG_ESC));
        if(profile==6392)assert(escape_flag==0);
        escape_flag=0;arg.lVal=1;out=&result;
        assert(openbor_backtotitle(args,&out,1)==(profile==6392?S_OK:E_FAIL) && !out);
        assert(selection_step(0)==(profile==6392));
        arg.lVal=0;assert(openbor_backtotitle(args,&out,1)==(profile==6392?S_OK:E_FAIL));
        assert(!selection_step(0));
        arg.vt=0;escape_flag=0;
        assert(openbor_backtotitle(args,&out,1)==E_FAIL && !escape_flag);
        assert(openbor_backtotitle(NULL,&out,0)==E_FAIL && !escape_flag);
        assert(openbor_gotomainmenu(NULL,&out,0)==S_OK && goto_mainmenu_flag==1);
        if(profile==6392)assert(!escape_flag);
        arg=(ScriptVariant){1,INT_MIN};assert(openbor_gotomainmenu(args,&out,1)==S_OK);
    }
}
'''.replace('METHODS', methods).replace('REGISTRATION', registration).replace('ESCAPE', escape))

    def test_cheat_menu_layout_toggle_back_and_forced_off(self):
        source = (ENGINE / 'openbor.c').read_text()
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stddef.h>
#include <string.h>
static uint32_t obor_profile_build;
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
    const unsigned profiles[]={6330,6391,6392,6412,6510};
    for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
        obor_profile_build=profiles[p];
        for(int paused=0;paused<2;++paused)for(int off=0;off<2;++off) {
            begin();cheats=1;forcecheatsoff=off;_pause=paused;level=paused?&savedata:NULL;
            int back=off?4:(profiles[p]==6392?8:7);
            for(int i=0;i<back;++i)key(FLAG_MOVEDOWN);
            key(0);key(FLAG_ANYBUTTON);menu_options();
            assert(cursor==keycount && selected_back && !multihitcheat);
            assert((drawn_multihit>0)==(!off && profiles[p]==6392));
            assert(!optionsMenu && !bothnewkeys && _pause==(paused?2:0));
        }
        begin();cheats=1;forcecheatsoff=0;_pause=0;level=NULL;
        for(int i=0;i<7;++i)key(FLAG_MOVEDOWN);
        key(FLAG_ANYBUTTON);
        if(profiles[p]==6392)key(FLAG_ESC);
        menu_options();assert(multihitcheat==(profiles[p]==6392));
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
