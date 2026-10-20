"""Check historical combat and runtime contracts using the actual C bodies.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
ENGINE = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines/3842'))


def native(program):
    with tempfile.TemporaryDirectory(prefix='anybor-historical-behavior-') as temp:
        work = Path(temp)
        source = work / 'probe.c'
        source.write_text(program)
        subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
            '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations', '-g',
            '-fsanitize=address,undefined', str(source), '-o', str(work / 'probe')],
            check=True, timeout=60)
        subprocess.run([str(work / 'probe')], check=True, timeout=20, cwd=work,
                       stdout=subprocess.DEVNULL)


class HistoricalBehaviorTests(unittest.TestCase):
    def test_model_clip_frame_and_submission_coordinate_boundary(self):
        source = (ENGINE / 'openbor.c').read_text()
        types = (ENGINE / 'source/gamelib/types.h').read_text()
        records = []
        for name in ('water_transform', 's_drawmethod'):
            end = types.index('}' + name + ';') + len(name) + 2
            start = types.rfind('typedef struct', 0, end)
            records.append(types[start:end])
        helpers = '\n'.join(function(source, name) for name in (
            'obor_model_clip_coordinate', 'obor_model_clip_frame', 'obor_model_clip_screen'))
        start = source.index('if(drawmethod.flag)')
        stop = source.index('else dm.flag = 0;', start) + len('else dm.flag = 0;')
        frame_code = source[start:stop]
        start = source.index('obor_model_clip_screen(drawmethod,', source.index('void display_ents()'))
        stop = source.index('spriteq_add_sprite(', start)
        submission = source[start:source.index(';', stop)+1]
        self.assertEqual(source.count('obor_model_clip_frame(&dm, offset);'), 1)
        self.assertEqual(source.count('obor_model_clip_screen(drawmethod,'), 1)
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
TYPES
static uint32_t obor_profile_build;
HELPERS
static int submitted_x,submitted_y,submissions;
static s_drawmethod submitted_method;
static void spriteq_add_sprite(int x,int y,int z,int f,s_drawmethod *method,int sortid) {
    assert(z==13 && f==17 && sortid==19);
    submitted_x=x;submitted_y=y;submitted_method=*method;++submissions;
}
static s_drawmethod frame(s_drawmethod drawmethod,int x,int y) {
    int offset[2]={x,y};s_drawmethod dm={0};
    FRAME
    return dm;
}
typedef struct { float x,z,a; } entity;
static void submit(s_drawmethod *drawmethod,entity *e,float scrx,float scry) {
    int z=13,f=17,sortid=19;
    SUBMISSION
}
int main(void) {
    const int clips[2][2]={{75,-20},{-20,40}};
    const int offsets[2][2]={{11,-7},{-3,4}};
    const int frame_expected[2][2]={{64,-13},{-17,36}};
    const int screen_expected[2][2]={{79,10},{-24,35}};
    entity positions[2]={{18.75f,30.5f,2.25f},{-2.75f,-1.25f,3.0f}};
    const float cameras[2][2]={{3.5f,4.75f},{5.0f,-2.5f}};
    const int projected[2][2]={{15,23},{-7,-1}};
    const int widths[3]={0,23,-5};
    /* Every requested logical build and every existing pre-3842 profile is
       exercised; this does not register profiles or admit pre-3746 clip syntax. */
    for(uint32_t profile=3666;profile<=3842;++profile) {
        obor_profile_build=profile;
        for(int test=0;test<2;++test) for(unsigned w=0;w<3;++w) {
            s_drawmethod input={0};input.flag=1;input.alpha=3;input.rotate=45;
            input.clipx=clips[test][0];input.clipy=clips[test][1];
            input.clipw=widths[w];input.cliph=31;
            s_drawmethod method=frame(input,offsets[test][0],offsets[test][1]);
            const int *expected=(profile>=3842 && input.clipw)?frame_expected[test]:clips[test];
            assert(method.clipx==expected[0] && method.clipy==expected[1]);
            submissions=0;submit(&method,&positions[test],cameras[test][0],cameras[test][1]);
            expected=(profile>=3842 && input.clipw)?screen_expected[test]:clips[test];
            assert(submissions==1 && submitted_x==projected[test][0] && submitted_y==projected[test][1]);
            assert(submitted_method.clipx==expected[0] && submitted_method.clipy==expected[1]);
            assert(submitted_method.flag==1 && submitted_method.alpha==3 && submitted_method.rotate==45);
            assert(submitted_method.clipw==input.clipw && submitted_method.cliph==31);
        }
        s_drawmethod disabled={0};disabled.clipw=23;
        assert(frame(disabled,11,-7).flag==0);
    }
}
'''.replace('TYPES', '\n'.join(records)).replace('HELPERS', helpers)
   .replace('FRAME', frame_code).replace('SUBMISSION', submission))

    def test_model_clip_integer_extremes_remain_bounded(self):
        source = (ENGINE / 'openbor.c').read_text()
        helpers = '\n'.join(function(source, name) for name in (
            'obor_model_clip_coordinate', 'obor_model_clip_frame', 'obor_model_clip_screen'))
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
typedef struct { int clipx,clipy,clipw; } s_drawmethod;
static uint32_t obor_profile_build;
HELPERS
int main(void) {
    assert(obor_model_clip_coordinate(INT_MIN,1,1)==INT_MIN);
    assert(obor_model_clip_coordinate(INT_MAX,1,0)==INT_MAX);
    assert(obor_model_clip_coordinate(0,INT_MIN,1)==INT_MAX);
    assert(obor_model_clip_coordinate(0,INT_MIN,0)==INT_MIN);
    assert(obor_model_clip_coordinate(0,INT_MAX,1)==-INT_MAX);
    for(uint32_t profile=3666;profile<=3842;++profile) {
        obor_profile_build=profile;
        s_drawmethod method={INT_MAX,INT_MIN,23};int offset[2]={-1,1};
        obor_model_clip_frame(&method,offset);
        obor_model_clip_screen(&method,1,-1);
        assert(method.clipx==INT_MAX && method.clipy==INT_MIN && method.clipw==23);
    }
}
'''.replace('HELPERS', helpers))

    def test_upstream_sdk_deprecations_remain_visible_warnings(self):
        native('int legacy(void) __attribute__((deprecated("SDK API")));\n'
               'int legacy(void) { return 0; }\n'
               'int main(void) { return legacy(); }\n')

    def test_unrelated_probe_warnings_remain_errors(self):
        with self.assertRaises(subprocess.CalledProcessError):
            native('int main(void) { int unused; return 0; }\n')

    def test_unary_numeric_and_unsupported_value_boundary(self):
        source = (ENGINE / 'source/scriptlib/ScriptVariant.c').read_text()
        methods = '\n'.join(function(source, name) for name in ('ScriptVariant_Pos', 'ScriptVariant_Neg'))
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef int32_t LONG;
enum { VT_EMPTY,VT_INTEGER,VT_DECIMAL,VT_STR,VT_PTR };
typedef struct { union { LONG lVal; double dblVal; void *ptrVal; }; int vt; } ScriptVariant;
static uint32_t obor_profile_build;
static int cleared;
static void ScriptVariant_Clear(ScriptVariant *v) { ++cleared;memset(v,0,sizeof(*v)); }
METHODS
int main(void) {
    for(unsigned profile=3780;profile<=3842;++profile) {
        obor_profile_build=profile;
        for(int kind=0;kind<5;++kind) {
            ScriptVariant v={.lVal=7,.vt=kind},before=v;cleared=0;
            if(kind==VT_DECIMAL)v.dblVal=before.dblVal=1.25;
            ScriptVariant_Pos(&v);
            if(profile<3828 && kind!=VT_INTEGER && kind!=VT_DECIMAL)
                assert(v.vt==VT_EMPTY && cleared==1);
            else assert(!memcmp(&v,&before,sizeof(v)) && cleared==0);
            v=before;cleared=0;ScriptVariant_Neg(&v);
            if(kind==VT_INTEGER)assert(v.vt==VT_INTEGER && v.lVal==-7 && cleared==0);
            else if(kind==VT_DECIMAL)assert(v.vt==VT_DECIMAL && v.dblVal==-1.25 && cleared==0);
            else if(profile<3828)assert(v.vt==VT_EMPTY && cleared==1);
            else assert(!memcmp(&v,&before,sizeof(v)) && cleared==0);
        }
        if(profile<3828) {
            ScriptVariant v={.lVal=INT32_MIN,.vt=VT_INTEGER};
            ScriptVariant_Neg(&v);assert(v.lVal==INT32_MIN && v.vt==VT_INTEGER);
            v=(ScriptVariant){.dblVal=0.1,.vt=VT_DECIMAL};
            ScriptVariant_Neg(&v);assert(v.dblVal==-0.1 && v.vt==VT_DECIMAL);
        }
    }
}
'''.replace('METHODS', methods))

    def test_system_property_numeric_and_text_domains(self):
        source = (ENGINE / 'openborscript.c').read_text()
        header = (ENGINE / 'openborscript.h').read_text()
        start = header.index('enum systemvariant_enum')
        enum = header[start:header.index('};', start)+2]
        start = source.index('static const char* svlist[]')
        names = source[start:source.index('};', start)+2]
        methods = '\n'.join(function(source, name) for name in (
            'obor_systemvariant_available', 'obor_systemvariant_native',
            'mapstrings_systemvariant', 'openbor_systemvariant', 'openbor_changesystemvariant'))
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <limits.h>
#include <string.h>
typedef long LONG;
typedef int HRESULT;
#define S_OK 0
#define E_FAIL (-1)
enum { VT_EMPTY,VT_INTEGER,VT_STR };
typedef struct { int vt; LONG lVal; const char *strVal; } ScriptVariant;
static uint32_t obor_profile_build;
static int read_index,write_index;
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) { memset(v,0,sizeof(*v));v->vt=type; }
static void ScriptVariant_Clear(ScriptVariant *v) { memset(v,0,sizeof(*v)); }
#define MAPSTRINGS(VAR,LIST,COUNT,MESSAGE) do { \
 if((VAR)->vt==VT_STR) {for(prop=0;prop<(COUNT);prop++) \
 if(!strcmp((VAR)->strVal,(LIST)[prop])) break; \
 if(prop<(COUNT)) {ScriptVariant_ChangeType(VAR,VT_INTEGER);(VAR)->lVal=prop;} } \
 (void)propname; } while(0)
ENUM
NAMES
static int getsyspropertybyindex(ScriptVariant *v,int index) { read_index=index;v->vt=VT_INTEGER;v->lVal=index;return index>=0 && index<_sv_the_end; }
static int changesyspropertybyindex(int index,ScriptVariant *v) { assert(v->lVal==123);write_index=index;return index>=0 && index<_sv_the_end; }
METHODS
int main(void) {
    assert(sizeof(svlist)/sizeof(*svlist)==_sv_the_end);
    for(unsigned profile=3780;profile<=3842;++profile) {
        obor_profile_build=profile;int logical=0;
        for(int physical=0;physical<_sv_the_end;++physical) {
            int absent=(profile<3783 && (!strcmp(svlist[physical],"scrollmaxx") || !strcmp(svlist[physical],"scrollminx"))) ||
                       (profile<3838 && !strcmp(svlist[physical],"sample_play_id"));
            ScriptVariant arg={VT_STR,0,svlist[physical]},value={VT_INTEGER,123,0},result={0},*out=&result,*args[]={&arg,&value};
            assert(openbor_systemvariant(args,&out,1)==(absent?E_FAIL:S_OK));
            if(absent) { assert(!out);continue; }
            assert(arg.vt==VT_INTEGER && arg.lVal==logical && out==&result && read_index==physical);
            arg=(ScriptVariant){VT_INTEGER,logical,0};out=&result;
            assert(openbor_systemvariant(args,&out,1)==S_OK && read_index==physical);
            arg=(ScriptVariant){VT_STR,0,svlist[physical]};out=&result;
            assert(openbor_changesystemvariant(args,&out,2)==S_OK && write_index==physical && arg.lVal==logical);
            arg=(ScriptVariant){VT_INTEGER,logical,0};out=&result;
            assert(openbor_changesystemvariant(args,&out,2)==S_OK && write_index==physical);
            ++logical;
        }
        for(int index=logical;index<=_sv_the_end;++index) {
            ScriptVariant arg={VT_INTEGER,index,0},result={0},*out=&result,*args[]={&arg};
            assert(openbor_systemvariant(args,&out,1)==E_FAIL && !out);
        }
        assert(obor_systemvariant_native(-1)==_sv_the_end && obor_systemvariant_native(INT_MAX)==_sv_the_end);
    }
}
'''.replace('ENUM', enum).replace('NAMES', names).replace('METHODS', methods))

    def test_entity_weapon_block_orbit_and_sleep_boundaries(self):
        source = (ENGINE / 'openbor.c').read_text()
        methods = '\n'.join(function(source, name) for name in (
            'obor_apply_weapon_model', 'set_weapon', 'set_idle', 'common_block'))
        idle = function(source, 'common_idle_anim')
        start = idle.index('if(obor_profile_build >= 3819 && self->idling)')
        idle_bit = idle[start:idle.index(';', start)+1]
        start = idle.index('else if(validanim(ent,ANI_SLEEP)')
        sleep_check = idle[start:idle.index('{', start)].replace('else if', 'if', 1)
        animate = function(source, 'ent_set_anim')
        start = animate.index('if(obor_profile_build < 3819 && aninum != ANI_SLEEP)')
        animation_time = animate[start:animate.index(';', start)+1]
        update = function(source, 'update_animation')
        start = update.index('if((obor_profile_build >= 3819')
        frame_time = update[start:update.index(';', start)+1]
        wander = function(source, 'common_try_wander')
        start = wander.index('mod = ')
        orbit = wander[start:wander.index('if(dox)', start)]
        initialize = function(source, 'ent_default_init')
        start = initialize.index('if( validanim(e,ANI_SPAWN))')
        spawn_animation = initialize[start:initialize.index('//else set_idle(e);', start)]
        start = initialize.index('if(validanim(e,ANI_SPAWN)', initialize.index('SUBTYPE_NOTGRAB'))
        spawn_action = initialize[start:initialize.index('else', start)]
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
static uint32_t obor_profile_build;
enum { TYPE_PLAYER=1,ANI_SLEEP=2,ANI_BLOCK=3,FLAG_SPECIAL=4,ANI_SPAWN=4,ANI_RESPAWN=5 };
typedef struct entity { struct { int type,weaploss[2],numweapons,*weapon,sleepwait,aggression,holdblock; float speed; } modeldata;
    struct entity *defaultmodel; int playerindex,idling,attacking,inpain,jumping,blocking,animating,
    sleeptime,animnum,sortid,health,pathblocked; void (*takeaction)(void);
} entity;
static entity object,*self=&object;
static struct { int weapnum,keys; } player[1];
static struct { int setweap; } room={2},*level=&room;
static struct { int hRes; } videomodes={320};
static int time=100,model_calls,idle_calls,animation_calls,seen_idle,last_animation,has_spawn,has_respawn;
static int validanim(entity *e,int anim) { assert(e==self);return anim==ANI_SPAWN?has_spawn:(anim==ANI_RESPAWN?has_respawn:1); }
static int common_idle_anim(entity *ent) { assert(ent==self);seen_idle=ent->idling;++idle_calls; IDLE_BIT return 1; }
static void ent_set_anim(entity *ent,int anim,int reset) { assert(ent==self && reset==0);last_animation=anim;++animation_calls; }
static void set_model_ex(entity *ent,char *name,int index,entity *model,int flag) {
    (void)name;(void)index;(void)model;(void)flag;assert(ent==self);++model_calls;ent->modeldata.weaploss[0]=0;
}
METHODS
static void animation_time(entity *ent,int aninum) { ANIMATION_TIME }
static void frame_time(void) { FRAME_TIME }
static int can_sleep(entity *ent) { SLEEP_CHECK { return 1; } return 0; }
static int orbit(void) { int mod; ORBIT return mod; }
static void common_spawn(void) { }
static void initial_spawn(entity *e) { SPAWN_ANIMATION }
static void initial_spawn_action(entity *e) { SPAWN_ACTION }
int main(void) {
    for(unsigned profile=3780;profile<=3842;++profile) {
        obor_profile_build=profile;memset(&object,0,sizeof(object));
        object.modeldata.type=TYPE_PLAYER;object.modeldata.weaploss[0]=3;
        player[0].weapnum=99;model_calls=0;
        set_weapon(&object,7,0);assert(model_calls==1 && player[0].weapnum==(profile<3793?2:7));
        object.idling=0;idle_calls=0;set_idle(&object);
        assert(idle_calls==1 && seen_idle==(profile<3819?0:1));
        assert(object.idling==(profile<3819?1:3));
        object.modeldata.sleepwait=5;object.sleeptime=7;animation_time(&object,ANI_BLOCK);
        assert(object.sleeptime==(profile<3819?105:7));
        object.sleeptime=7;animation_time(&object,ANI_SLEEP);assert(object.sleeptime==7);
        for(int idling=0;idling<=3;++idling)for(int sleep=0;sleep<=1;++sleep) {
            object.idling=idling;object.animnum=sleep?ANI_SLEEP:ANI_BLOCK;object.animating=0;object.sleeptime=7;
            frame_time();
            int changed=profile<3819?0:(profile<3824?(!sleep&&(idling&2)):(!(idling&2)||sleep));
            assert(object.sleeptime==(changed?105:7));
        }
        object.sleeptime=time;object.animating=0;
        assert(can_sleep(&object)==(profile==3824));
        object.animating=1;assert(can_sleep(&object)==(profile<3825));
        object.sleeptime=time-1;object.animating=0;assert(can_sleep(&object)==(profile>=3824));
        object.modeldata.speed=2;
        for(int id=-200;id<=200;id+=100)for(int health=-9;health<=9;++health) {
            object.sortid=id;object.health=health;
            int expected=((int)(time/(320/2.0f))+id/100+health/3)%4;
            if(profile>=3801) { if(expected<0)expected=-expected;if((id/100)%2)expected=3-expected; }
            assert(orbit()==expected);
        }
        object.inpain=1;object.animating=0;object.blocking=1;object.modeldata.type=TYPE_PLAYER;
        object.modeldata.holdblock=2;
        player[0].keys=FLAG_SPECIAL;idle_calls=animation_calls=0;common_block();
        if(profile>=3834)assert(animation_calls==1 && object.inpain==0);
        else if(profile>=3801)assert(animation_calls==0 && idle_calls==0 && object.inpain==1);
        else assert(animation_calls==0 && idle_calls==1);
        for(has_spawn=0;has_spawn<=1;++has_spawn)for(has_respawn=0;has_respawn<=1;++has_respawn) {
            animation_calls=0;initial_spawn(&object);
            int available=has_spawn || (profile>=3787 && has_respawn);
            assert(animation_calls==available);
            if(available)assert(last_animation==(has_spawn?ANI_SPAWN:ANI_RESPAWN));
            object.takeaction=NULL;initial_spawn_action(&object);
            assert(object.takeaction==(available?common_spawn:NULL));
        }
    }
}
'''.replace('METHODS', methods).replace('IDLE_BIT', idle_bit)
           .replace('ANIMATION_TIME', animation_time).replace('FRAME_TIME', frame_time)
           .replace('SLEEP_CHECK', sleep_check).replace('ORBIT', orbit)
           .replace('SPAWN_ANIMATION', spawn_animation).replace('SPAWN_ACTION', spawn_action))

    def test_level_shadow_color_and_saved_model_loading_boundaries(self):
        source = (ENGINE / 'openbor.c').read_text()
        start = source.index('case CMD_LEVEL_SHADOWCOLOR:')
        color = source[start:source.index('case CMD_LEVEL_SHADOWALPHA:', start)]
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint32_t obor_profile_build;
enum { VT_EMPTY,VT_PTR };
typedef struct { int vt; } ScriptVariant;
static struct { void *owner; const char *key; ScriptVariant value; } *global_var_list[1];
static ScriptVariant indexed_var_list[1];
static int max_global_var_index=-1,max_indexed_vars,current_set,models_cached=3;
typedef struct { int unload; } model;
static struct { const char *name; int selectable; model *model; } model_cache[3];
static void getBasePath(char *out,const char *kind,int n) { assert(!strcmp(kind,"Saves") && n==0);strcpy(out,""); }
static void getPakName(char *out,size_t capacity,int n) { assert(n==2 && capacity>10);strcpy(out,"state.s00"); }
static int obor_pak_path_append(char *out,size_t capacity,const char *name) { assert(strlen(out)+strlen(name)<capacity);strcat(out,name);return 1; }
static void borExit(int code) { (void)code;assert(0); }
static void vardump(ScriptVariant *v,char *out) { (void)v;(void)out;assert(0); }
METHOD
static int parsed;
static const char *argument;
static int parsecolor(const char *text) { ++parsed;return strchr(text,'_')?0x123456:atoi(text)+1000; }
#define GET_ARG(n) (argument)
#define GET_INT_ARG(n) (atoi(argument))
enum { CMD_LEVEL_SHADOWCOLOR };
static int color(void) {
    struct { int shadowcolor; } next;
    switch(CMD_LEVEL_SHADOWCOLOR) { COLOR_BODY }
    return next.shadowcolor;
}
int main(void) {
    model loaded={3};
    model_cache[0].name="first";model_cache[0].selectable=1;model_cache[0].model=&loaded;
    model_cache[1].name="cached";model_cache[1].model=NULL;
    model_cache[2].name="third";model_cache[2].model=&loaded;
    for(unsigned profile=3780;profile<=3842;++profile) {
        obor_profile_build=profile;
        parsed=0;argument="17";assert(color()==(profile<3819?17:1017));
        argument="12_34_56";assert(color()==(profile<3819?12:0x123456));
        assert(parsed==(profile<3819?0:2));
        assert(saveScriptFile()==1);
        FILE *file=fopen("state.s00","rb");assert(file);char text[1024]={0};
        assert(fread(text,1,sizeof(text)-1,file)>0);fclose(file);
        assert((strstr(text,"changemodelproperty(\"first\",4,1);")!=NULL)==(profile>=3822));
        assert((strstr(text,"loadmodel(\"first\",3,1);")!=NULL)==(profile>=3822 && profile<3835));
        assert((strstr(text,"loadmodel(\"third\",3,0);")!=NULL)==(profile>=3822 && profile<3835));
        assert(strstr(text,"loadmodel(\"cached\"")==NULL);
    }
    assert(remove("state.s00")==0);
}
'''.replace('METHOD', function(source, 'saveScriptFile')).replace('COLOR_BODY', color))

    def test_dynamic_animation_ids_and_initial_attack_slots(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        constants = header[header.index('#define\t\tATK_NORMAL\t'):header.index('#define     MAX_DOTS')]
        helpers = '\n'.join(function(source, n) for n in ('obor_attack_base', 'obor_attack_special'))
        start = source.index('memcpy(animpains,')
        end = source.index('\n\tif(buf) free(buf);', start)
        initialization = source[start:end]
        script = (ENGINE / 'openborscript.c').read_text()
        start = script.index('#define ICMPSCONSTB(')
        macro = script[start:script.index('void mapstrings_transconst(', start)]
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
static uint32_t obor_profile_build;
CONSTANTS
HELPERS
#define strnicmp strncasecmp
typedef long LONG;
MACRO
static int pains[20],falls[20],rises[20],riseattacks[20],blkpains[20],deaths[20];
static int *animpains,*animfalls,*animrises,*animriseattacks,*animblkpains,*animdies;
static int max_attack_types,maxanim;
static void initialize(void) { int i; INITIALIZATION }
static int lookup(const char *constname) {
    struct { LONG lVal; } v={0};
    if(0) { }
    ICMPSCONSTB(ANI_PAIN,animpains)
    return (int)v.lVal;
}
int main(void) {
    for(int i=0;i<20;++i) pains[i]=falls[i]=rises[i]=riseattacks[i]=blkpains[i]=deaths[i]=100+i;
    for(unsigned profile=3780;profile<=3842;++profile) {
        obor_profile_build=profile;max_attack_types=OBOR_ATTACK_BASE+2;maxanim=500;
        int **tables[]={&animpains,&animfalls,&animrises,&animriseattacks,&animblkpains,&animdies};
        for(unsigned i=0;i<6;++i) { *tables[i]=calloc(max_attack_types+1,sizeof(int));assert(*tables[i]);(*tables[i])[max_attack_types]=12345; }
        initialize();assert(maxanim==512);
        for(unsigned i=0;i<6;++i) {
            assert((*tables[i])[14]==114);
            assert((*tables[i])[15]==(profile<3831?0:115));
            assert((*tables[i])[OBOR_ATTACK_BASE]==500+(int)i*2);
            assert((*tables[i])[max_attack_types]==12345);
        }
        if(profile!=3830) {
            assert(lookup("ANI_PAIN11")==500 && lookup("ANI_PAIN12")==501);
        }
        for(unsigned i=0;i<6;++i)free(*tables[i]);
    }
}
'''.replace('CONSTANTS', constants).replace('HELPERS', helpers)
           .replace('MACRO', macro).replace('INITIALIZATION', initialization))

    def test_environment_damage_keeps_the_selected_type_and_health_contract(self):
        source = (ENGINE / 'openbor.c').read_text()
        start = source.index('if(self->damage_on_landing > 0 && !self->dead)')
        landing = source[start:source.index('// in case landing, set hithead', start)]
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
enum { ATK_LAND=16,ATK_PIT,ATK_LIFESPAN,ATK_TIMEOVER, TYPE_PLAYER=1,
    SCROLL_UP=2,SCROLL_DOWN=4,DEFAULT_OFFSCREEN_KILL=1000,COUNTER_SPEED=400,GAME_SPEED=200 };
#define PIT_DEPTH (-10)
typedef struct { int attack_type,attack_force; float dropv[3]; } s_attack;
typedef struct entity { float x,z,a,lifespancountdown; int health,damage_on_landing,damagetype,dead;
    struct { int offscreenkill,type; } modeldata;
    struct { float factor; } defense[20];
    void (*takedamage)(struct entity *,s_attack *);
} entity;
static uint32_t obor_profile_build;
static entity object,*self=&object;
static struct { int scrolldir,type,settime; } storage,*level=&storage;
static struct { int hRes,vRes; } videomodes={320,240};
static struct { entity *ent; } player[4];
static struct { int effectvol; } savedata;
static int max_attack_types,level_completed,endgame,SAMPLE_TIMEOVER=-1,timeleft,showtimeover;
static int damage_calls,kind,force,previous_health,killed;
static float advancex,advancey,default_model_dropv[3];
static s_attack emptyattack;
static int is_frozen(entity *e) { assert(e==self);return 0; }
static void kill(entity *e) { assert(e==self);++killed; }
static void player_die(void) { ++killed; }
static void damage(entity *e,s_attack *a) { assert(e==self);++damage_calls;kind=a->attack_type;force=a->attack_force;previous_health=e->health; }
static void sound_play_sample(int id,int priority,int left,int right,int speed) { (void)id;(void)priority;(void)left;(void)right;(void)speed;assert(0); }
LOST
TIMEOVER
static void land(void) { s_attack attack; LANDING }
static void reset(void) {
    memset(&object,0,sizeof(object));object.health=40;object.takedamage=damage;
    object.damagetype=3;object.lifespancountdown=100;
    object.defense[ATK_LAND].factor=0.25f;damage_calls=killed=0;
}
int main(void) {
    for(unsigned profile=3780;profile<=3842;++profile) {
        obor_profile_build=profile;max_attack_types=profile<3830?16:20;
        reset();object.damage_on_landing=8;land();
        assert(damage_calls==1 && kind==(profile<3830?3:ATK_LAND) && force==8);
        reset();object.takedamage=0;object.damage_on_landing=8;land();
        assert(object.health==(profile<3830?32:38) && object.damage_on_landing==0);
        for(int expired=0;expired<2;++expired) {
            reset();if(expired)object.lifespancountdown=-1;else object.a=-11;
            check_lost();assert(damage_calls==1 && force==40);
            assert(kind==(profile<3830?max_attack_types:(expired?ATK_LIFESPAN:ATK_PIT)));
            assert(previous_health==(profile<3830?0:40));
            reset();object.takedamage=0;if(expired)object.lifespancountdown=-1;else object.a=-11;
            check_lost();assert(killed==1 && damage_calls==0);
        }
        reset();player[0].ent=&object;level_completed=0;level->type=0;
        time_over();assert(damage_calls==1 && kind==(profile<3830?max_attack_types:ATK_TIMEOVER));
    }
}
'''.replace('LOST', function(source, 'check_lost'))
           .replace('TIMEOVER\n', function(source, 'time_over') + '\n')
           .replace('LANDING', landing))

    def test_camera_mean_extremes_span_and_integer_truncation(self):
        source = (ENGINE / 'openbor.c').read_text()
        start = source.index('case CMD_LEVEL_SCROLLZ:')
        scroll_parser = source[start:source.index('case CMD_LEVEL_BLOCKADE:', start)]
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
enum { TYPE_ENEMY=1,TYPE_ENDLEVEL=2,TYPE_ITEM=4,TYPE_OBSTACLE=8,
       SCROLL_RIGHT=2,SCROLL_DOWN=4,SCROLL_LEFT=8,SCROLL_UP=16,
       SCROLL_OUTWARD=32,SCROLL_INWARD=64,SCROLL_BACK=128,
       COUNTER_SPEED=400,GAME_SPEED=200 };
typedef struct { float x,z,a; int dead; } entity;
static uint32_t obor_profile_build;
static struct { entity *ent; } player[4];
typedef struct { int at,musicfade,musicoffset,wait,groupmin,groupmax,nojoin,scrollminz,scrollmaxz,
    scrollminx,scrollmaxx,blockade,palette,light[2],shadowcolor,shadowalpha; char music[128]; } spawn;
static struct { int advancetime,numspawns,type,pos,waiting,noreset,settime,scrolldir,width,
    cameraxoffset,camerazoffset,rocking; float scrollspeed; spawn *spawnpoints; } room,*level=&room;
static struct { int maxplayers; } levelsets[1];
static struct { int hRes,vRes; } videomodes={320,240};
static struct { int musicvol; } savedata;
static int current_set,current_spawn,groupmin,groupmax,level_completed,freezeall,time,
    timeleft,go_time,musicoffset,musicloop,nojoin,light[2],shadowcolor,shadowalpha,panel_height=5000,cameratype;
static char musicname[128];
static float advancex,advancey,scrolldx,scrolldy,scrollminx,scrollmaxx,scrollminz,scrollmaxz,blockade,musicfade[2];
static int entity_count=9999;
static int findent(int type) { (void)type;return 1; }
static int count_ents(int type) { (void)type;return entity_count; }
static void change_system_palette(int n) { (void)n;assert(0); }
static void smartspawn(spawn *s) { (void)s;assert(0); }
METHOD
enum { CMD_LEVEL_SCROLLZ,CMD_LEVEL_SCROLLX };
static spawn next;
#define GET_INT_ARG(n) ((n)==1?low:high)
static void parse_scroll(int code,int low,int high) { switch(code) { SCROLL_PARSER } }
static int close_enough(float a,float b) { return a-b<0.001f && b-a<0.001f; }
int main(void) {
    entity ent[3]={{1000.5f,600.5f,10,0},{1001.5f,601.5f,20,0},{1200.5f,720.5f,40,0}};
    for(int i=0;i<3;++i)player[i].ent=ent+i;
    levelsets[0].maxplayers=3;room.width=5000;room.scrollspeed=10000;
    room.cameraxoffset=7;room.camerazoffset=13;scrollmaxx=scrollmaxz=5000;
    const int directions[]={SCROLL_RIGHT,SCROLL_LEFT,SCROLL_OUTWARD,SCROLL_INWARD};
    for(unsigned profile=3780;profile<=3842;++profile) {
        obor_profile_build=profile;
        for(unsigned d=0;d<4;++d)for(cameratype=0;cameratype<=1;++cameratype) {
            room.scrolldir=directions[d]|SCROLL_BACK;room.advancetime=0;room.waiting=0;time=1;
            advancex=advancey=500;level_completed=0;update_scroller();
            const float x=profile<3837?(1000+1001+1200)/3.0f-160+7:1100.5f-160+7;
            float z;
            if(profile<3837) {
                if(d<2)z=cameratype?(590+581+680)/3.0f-120+13:(600+601+720)/3.0f-120+13;
                else z=(600+601+720)/3.0f-120+(d==2?7:13);
            } else z=cameratype&&d<2?(581.5f+720.5f)/2-120+13:660.5f-120+13;
            assert(close_enough(advancex,x) && close_enough(advancey,z));
            assert(close_enough(scrolldx,x-500) && close_enough(scrolldy,z-500));
        }
        /* The later contract holds the camera when players exceed the viewport. */
        ent[2].x=2000.5f;room.scrolldir=SCROLL_RIGHT;advancex=500;advancey=500;
        update_scroller();assert(close_enough(advancex,profile<3837?(1000+1001+2000)/3.0f-160+7:500));
        ent[2].x=1200.5f;
        parse_scroll(CMD_LEVEL_SCROLLX,1000,1300);
        assert(profile<3783 ? next.scrollminz==1000 && next.scrollminx==0 :
               (next.scrollminx&0x7fffffff)==1000 && next.scrollminz==0);
        room.spawnpoints=&next;room.numspawns=1;current_spawn=0;groupmin=groupmax=1;entity_count=0;
        room.scrolldir=SCROLL_RIGHT;advancex=advancey=500;scrollminx=scrollminz=0;scrollmaxx=scrollmaxz=5000;cameratype=0;
        update_scroller();assert(current_spawn==1);
        assert(profile<3783 ? scrollminz==1000 && scrollminx==0 && advancey==1000 :
               scrollminx==1000 && scrollminz==0 && advancex==1000);
        room.numspawns=0;entity_count=9999;groupmin=0;scrollminx=scrollminz=0;scrollmaxx=scrollmaxz=5000;
        parse_scroll(CMD_LEVEL_SCROLLZ,-3,0);
        assert(profile<3783 ? next.scrollminz==0 && next.scrollmaxz==0 : (next.scrollminz&0x80000000)!=0);
        for(int i=0;i<3;++i)player[i].ent=NULL;
        advancex=500;advancey=500;update_scroller();
        assert(advancex==500 && advancey==500);
        for(int i=0;i<3;++i)player[i].ent=ent+i;
    }
}
'''.replace('METHOD', function(source, 'update_scroller')).replace('SCROLL_PARSER', scroll_parser))

    def test_attack_tables_suffixes_and_defense_all_boundaries(self):
        source = (ENGINE / 'openbor.c').read_text()
        header = (ENGINE / 'openbor.h').read_text()
        constants = header[header.index('#define\t\tATK_NORMAL\t'):header.index('#define     MAX_DOTS')]
        helpers = '\n'.join(function(source, name) for name in (
            'obor_attack_base', 'obor_attack_special', 'obor_attack_name_available'))
        start = source.index('case CMD_MODEL_DEFENSE:')
        cases = source[start:source.index('case CMD_MODEL_HEIGHT:', start)]
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
static uint32_t obor_profile_build;
CONSTANTS
HELPERS
#define stricmp strcasecmp
#define starts_with(a,b) (!strncasecmp(a,b,sizeof(b)-1))
#define get_tail_number(n,a,b) n=atoi((a)+sizeof(b)-1); if(n<1)n=1
#define GET_ARG(n) (args[n])
#define GET_FLOAT_ARG(n) ((float)atof(args[n]))
enum { CMD_MODEL_DEFENSE, CMD_MODEL_OFFENSE, SUBTYPE_BIKER };
typedef struct { float factor,pain,knockdown,blockpower,blockthreshold,blockratio,blocktype; } s_defense;
static const s_defense default_defense={1,0,0,0,0,0,0};
typedef struct { int subtype; s_defense *defense; float *offense_factors; } model;
static model data,*newchar=&data;
static int max_attack_types, warnings;
static void writeToLogFile(const char *format,...) { (void)format; ++warnings; }
static void parse(int code,const char *name) {
    const char *args[]={"command",name,"0.25","0","0","0","0","0","0"};
    struct { int count; } arglist={9};
    const char *value,*filename="synthetic",*command="command";
    s_defense defense; int i,tempInt; float tempFloat;
    switch(code) { CASES default: assert(0); }
}
int main(void) {
    const unsigned profiles[]={3780,3783,3789,3793,3797,3805,3814,3818,
        3822,3824,3829,3830,3831,3837,3839,3842};
    const char *names[]={"normal","normal1","normal2","normal10","normal11",
        "normal12","normal2147483647","item","land","pit","lifespan","timeover","ALL"};
    for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p) {
        obor_profile_build=profiles[p];
        assert(OBOR_ATTACK_BASE==(profiles[p]<3830?16:20));
        assert(OBOR_ATTACK_SPECIAL==(profiles[p]<3831?6:10));
        for(int extension=0;extension<2;++extension) {
            max_attack_types=OBOR_ATTACK_BASE+(extension?2:0);
            data.defense=calloc(max_attack_types+1,sizeof(*data.defense));
            data.offense_factors=calloc(max_attack_types+1,sizeof(*data.offense_factors));
            assert(data.defense && data.offense_factors);
            for(unsigned n=0;n<sizeof(names)/sizeof(*names);++n) {
                memset(data.defense,0,(max_attack_types+1)*sizeof(*data.defense));
                memset(data.offense_factors,0,(max_attack_types+1)*sizeof(*data.offense_factors));
                data.defense[max_attack_types].factor=123;
                data.offense_factors[max_attack_types]=123;
                warnings=0; parse(CMD_MODEL_DEFENSE,names[n]); parse(CMD_MODEL_OFFENSE,names[n]);
                assert(data.defense[max_attack_types].factor==123 && data.offense_factors[max_attack_types]==123);
                if(n==0) assert(data.defense[ATK_NORMAL].factor==0.25f);
                if(n==1) {
                    if(profiles[p]>=3831) assert(data.defense[ATK_NORMAL].factor==0.25f);
                    else { assert(data.defense[ATK_NORMAL].factor==0); assert(data.defense[16].factor==(max_attack_types>16?0.25f:123)); }
                }
                if(n==2) assert(data.defense[ATK_NORMAL2].factor==0.25f);
                if(n==4 || n==5) {
                    int index=(n==4?11:12)+(profiles[p]<3831?6:10)-1;
                    assert(warnings==(index>=max_attack_types?2:0));
                    if(index<max_attack_types) assert(data.defense[index].factor==0.25f && data.offense_factors[index]==0.25f);
                }
                if(n==6) assert(warnings==2);
                if(n==7) assert(data.defense[ATK_ITEM].factor==(profiles[p]>=3831?0.25f:0));
                if(n>=8 && n<=11 && profiles[p]<3831) assert(data.defense[0].factor==0);
                if(n==12) {
                    for(int i=0;i<max_attack_types;++i) {
                        int environmental=i==ATK_PIT || i==ATK_LIFESPAN || i==ATK_TIMEOVER;
                        assert(data.defense[i].factor==((profiles[p]>=3830 && environmental)?0:0.25f));
                        assert(data.offense_factors[i]==((profiles[p]>=3831 && environmental)?0:0.25f));
                    }
                }
            }
            free(data.defense);free(data.offense_factors);
        }
    }
}
'''.replace('CONSTANTS', constants).replace('HELPERS', helpers).replace('CASES', cases))

    def test_playsample_void_integer_results_invalid_ids_and_conversion(self):
        source = (ENGINE / 'openborscript.c').read_text()
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef long LONG;
typedef int HRESULT;
enum { VT_EMPTY, VT_INTEGER, VT_STR };
typedef struct { int vt; LONG lVal; } ScriptVariant;
#define S_OK 0
#define E_FAIL (-1)
#define FAILED(x) ((x)<0)
static uint32_t obor_profile_build;
static struct { int effectvol; } savedata={64};
static int calls,looped;
static HRESULT ScriptVariant_IntegerValue(ScriptVariant *v,LONG *out) { if(v->vt!=VT_INTEGER)return E_FAIL;*out=v->lVal;return S_OK; }
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) { memset(v,0,sizeof(*v));v->vt=type; }
static int sound_play_sample(int id,unsigned priority,int l,int r,unsigned speed) { (void)priority;(void)l;(void)r;(void)speed;++calls;return id<0?-1:7; }
static int sound_loop_sample(int id,unsigned priority,int l,int r,unsigned speed) { ++looped;return sound_play_sample(id,priority,l,r,speed); }
METHOD
int main(void) {
    for(unsigned profile=3780;profile<=3842;++profile) {
        obor_profile_build=profile;
        for(int id=-1;id<=1;++id) for(int loop=0;loop<=1;++loop) {
            ScriptVariant values[6]={{VT_INTEGER,id},{VT_INTEGER,0},{VT_INTEGER,64},
                {VT_INTEGER,64},{VT_INTEGER,100},{VT_INTEGER,loop}};
            ScriptVariant result={0},*out=&result,*args[6];
            for(int i=0;i<6;++i)args[i]=values+i;
            calls=looped=0;int status=openbor_playsample(args,&out,6);
            if(profile<3838) {
                assert(!out);
                assert(status==(id<0?E_FAIL:S_OK));
                assert(calls==(id<0?0:1));
            } else {
                assert(status==S_OK && out==&result && result.vt==VT_INTEGER);
                assert(result.lVal==(id<0?-1:7) && calls==1);
            }
            assert(looped==(calls&&loop?1:0));
            out=&result;values[2].vt=VT_STR;calls=0;
            assert(openbor_playsample(args,&out,6)==E_FAIL && !out && !calls);
        }
    }
}
'''.replace('METHOD', function(source, 'openbor_playsample')))

    def test_nested_interpreter_and_exit_registration_boundaries(self):
        source = (ENGINE / 'openborscript.c').read_text()
        model_source = (ENGINE / 'openbor.c').read_text()
        cmd_helpers = '\n'.join(function(model_source, name) for name in (
            'obor_animation_cmd_grouped', 'obor_animation_cmd_returns'))
        registration = function(source, 'Script_LoadSystemFunctions')
        match = re.search(r'if\(obor_profile_build >= 3834\)\s*List_InsertAfter\([^;]*system_exit[^;]*;', registration)
        self.assertIsNotNone(match)
        native(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdarg.h>
#define FALSE 0
#define SUCCEEDED(x) ((x)>=0)
static uint32_t obor_profile_build;
typedef struct { int bReset,cursor; struct { const char *name; } theSymbolTable; } Interpreter;
typedef struct { Interpreter *pinterpreter; const char *comment; } Script;
static Script *pcurrentscript;
static int no_cmd_compatible,no_nested_script,executions;
CMD_HELPERS
static void Interpreter_Reset(Interpreter *v) { v->cursor=0;v->bReset=1; }
static int Interpreter_EvaluateImmediate(Interpreter *v) { assert(v->cursor==0);v->cursor=9;v->bReset=1;++executions;return 0; }
static void shutdown(int code,const char *format,...) { (void)code;(void)format;assert(0); }
static void system_exit(void) { }
static int theFunctionList,registrations;
static void List_InsertAfter(int *list,void *func,const char *name) { assert(list==&theFunctionList && func==(void*)system_exit && !strcmp(name,"exit"));++registrations; }
METHOD
static void register_exit(void) { REGISTRATION }
int main(void) {
    Script outer={0},script={0}; Interpreter interpreter;
    script.pinterpreter=&interpreter;
    for(unsigned profile=3780;profile<=3842;++profile) {
        obor_profile_build=profile;registrations=0;register_exit();
        assert(registrations==(profile>=3834));
        for(int nested=0;nested<=1;++nested) for(int compatible=0;compatible<=1;++compatible)
        for(int blocked=0;blocked<=1;++blocked) {
            interpreter=(Interpreter){nested,41,{"synthetic"}};
            no_cmd_compatible=compatible;no_nested_script=blocked;executions=0;
            pcurrentscript=&outer;
            assert(Script_Execute(&script)==1 && pcurrentscript==&outer);
            if(profile>=3806 && nested && blocked) assert(executions==0 && interpreter.cursor==41);
            else if(nested && ((profile>=3813 && profile<3836) || (profile>=3836 && compatible)))
                assert(executions==1 && interpreter.cursor==41 && interpreter.bReset==1);
            else assert(executions==1 && interpreter.cursor==9 && interpreter.bReset==!(profile>=3836 && nested));
            assert(obor_animation_cmd_grouped()==(profile>=3813 && (profile<3823 || compatible)));
            assert(obor_animation_cmd_returns()==(profile<3823 || compatible));
        }
    }
}
'''.replace('METHOD', function(source, 'Script_Execute')).replace('REGISTRATION', match.group())
           .replace('CMD_HELPERS', cmd_helpers))


if __name__ == '__main__':
    unittest.main()
