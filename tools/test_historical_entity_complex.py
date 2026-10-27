"""Check selected complex setter branches and their callback validation.

The fixture uses reduced types, numeric mapper/ID translation stubs and observable engine
action stubs. Own-source contracts cover defined historical calls; malformed
calls exercise generated safety guards only. This is not a gameplay test.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from test_historical_player import function
from test_historical_entity_returns import scalar_entry

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
CONTRACTS = json.loads((Path(__file__).parent /
    'fixtures/profile-entity-complex-contracts.json').read_text())
PROPERTIES = ('_ep_spritea', '_ep_weapon', '_ep_knockdowncount', '_ep_komap',
    '_ep_mpset', '_ep_position', '_ep_running', '_ep_rush_count',
    '_ep_rush_tally', '_ep_velocity', '_ep_takeaction', '_ep_think', '_ep_trymove',
    '_ep_animation', '_ep_animhits', '_ep_combostep', '_ep_edelay', '_ep_energycost',
    '_ep_defaultname', '_ep_dot', '_ep_map', '_ep_model', '_ep_name')


def complex_program(components=None, contracts=None):
    contracts = CONTRACTS['sources'] if contracts is None else contracts
    generated = components is None
    if components is None:
        source = (SOURCE / 'src/engines/3741/openborscript.c').read_text()
        entry, actions = scalar_entry(source, PROPERTIES)
        components = {'entries': entry, 'actions': sorted(actions),
            'helpers': function(source, 'obor_script_sprite_filename'),
            'invoke': 'return openbor_changeentityproperty(args,result,count);'}
        if 'obor_entity_set_property_native(' in entry:
            components['helpers'] += (
                'static int obor_entity_set_property_native(int property) { return property; }\n')
    program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef long LONG;
typedef double DOUBLE;
typedef void VOID;
typedef int HRESULT;
typedef struct {
    union { LONG lVal, strVal; DOUBLE dblVal; void *ptrVal; };
    int vt;
} ScriptVariant;
enum { VT_EMPTY=0,VT_INTEGER=1,VT_DECIMAL=2,VT_PTR=5,VT_STR=6 };
enum { TYPE_ENEMY=1,TYPE_NPC,TYPE_OBSTACLE,TYPE_PLAYER,TYPE_SHOT };
PROPERTIES_ENUM
enum { _cep_spritea_centerx, _cep_spritea_centery, _cep_spritea_file,
       _cep_spritea_sprite };
enum { _cep_knockdowncount_current, _cep_knockdowncount_max,
       _cep_knockdowncount_time };
enum { _cep_ta_the_end=22, _cep_th_the_end=6 };
enum { _cep_energycost_cost, _cep_energycost_disable, _cep_energycost_mponly };
#define S_OK 0
#define E_FAIL (-1)
#define SUCCEEDED(x) ((x)>=0)
#define FAILED(x) ((x)<0)
#define MAX_DOTS 10
typedef struct { int marker; } s_sprite;
typedef struct sprite_list {
    char *filename; s_sprite *sprite; int ref; struct sprite_list *next;
} s_sprite_list;
typedef struct {
    int numframes; int *sprite; int animhits;
    struct { int cost,disable,mponly; } energycost;
} s_animation;
typedef struct {
    float knockdowncount; s_animation **animation; int animation_capacity;
    struct { int ko,kotype; } maps;
    int mp,mpstable,mpstableval,mprate,mpdroprate,chargerate;
    float runspeed,runjumpheight,runjumpdist;
    int runhold,runupdown;
    struct { int mode; float factor; int cap_min,cap_max,range_min,range_max; } edelay;
} s_model;
typedef struct entity {
    s_model modeldata; float knockdowncount; int knockdowntime;
    float x,z,a,xdir,zdir,tossv; int rush[2];
    const void *takeaction,*think,*trymove;
    s_animation *animation; unsigned char combostep[27];
    char name[41]; s_model *defaultmodel; struct entity *weapent;
    uint32_t dot_time[MAX_DOTS];
    int dot[MAX_DOTS],dot_force[MAX_DOTS],dot_rate[MAX_DOTS],dot_atk[MAX_DOTS];
    struct entity *dot_owner[MAX_DOTS];
} entity;
typedef struct { int centerx,centery; s_sprite_list *node; } s_sprite_map;
static s_sprite_map *sprite_map;
int sprite_map_max_items;
unsigned int sprites_loaded;
static uint32_t obor_profile_build;
static int weapon_calls,weapon_value,weapon_optional;
static int animation_calls,animation_id,animation_reset;
static int map_calls,model_calls,model_option;
static unsigned map_value;
static s_model known_model;
static char cached_string[8192];
#define validanim(e,a) ((a)>=0 && (a)<(e)->modeldata.animation_capacity && \
    (e)->modeldata.animation[a] && (e)->modeldata.animation[a]->numframes)
static void ScriptVariant_ChangeType(ScriptVariant *v,int type) {
    memset(v,0,sizeof(*v));v->vt=type;
}
static int ScriptVariant_IntegerValue(ScriptVariant *v,LONG *out) {
    if(v->vt==VT_INTEGER) { *out=v->lVal;return S_OK; }
    if(v->vt==VT_DECIMAL) { *out=(LONG)v->dblVal;return S_OK; }
    return E_FAIL;
}
static int ScriptVariant_DecimalValue(ScriptVariant *v,DOUBLE *out) {
    if(v->vt==VT_INTEGER) { *out=v->lVal;return S_OK; }
    if(v->vt==VT_DECIMAL) { *out=v->dblVal;return S_OK; }
    return E_FAIL;
}
static char *StrCache_Get(LONG index) { assert(index==0);return cached_string; }
static void mapstrings_changeentityproperty(ScriptVariant **args,int count) {
    (void)args;(void)count;
}
static void set_weapon(entity *ent,int value,int optional) {
    assert(ent);++weapon_calls;weapon_value=value;weapon_optional=optional;
}
static void ent_set_anim(entity *ent,int value,int reset) {
    assert(ent);++animation_calls;animation_id=value;animation_reset=reset;
}
static s_model *findmodel(char *name) {
    return !strcmp(name,"known")?&known_model:NULL;
}
static void set_model_ex(entity *ent,char *name,int index,void *unused,int option) {
    assert(ent && !strcmp(name,"known") && index==-1 && unused==NULL);
    ++model_calls;model_option=option;
}
static void ent_set_colourmap(entity *ent,unsigned value) {
    assert(ent);++map_calls;map_value=value;
}
static int quiet_printf(const char *format,...) { (void)format;return 0; }
#define printf quiet_printf
STUBS
HELPERS
ENTRIES
static int invoke(ScriptVariant **args,ScriptVariant **result,int count) { INVOKE }
struct contract { int revision,has_result,action_empty; };
static const struct contract contracts[]={ CONTRACTS };
static void expected_field(entity *e,int property,int index,double value) {
    switch(property) {
        case _ep_komap:
            if(index==0) e->modeldata.maps.ko=(int)value;
            else e->modeldata.maps.kotype=(int)value;
            break;
        case _ep_mpset:
            switch(index) {
                case 0:e->modeldata.mp=(int)value;break;
                case 1:e->modeldata.mpstable=(int)value;break;
                case 2:e->modeldata.mpstableval=(int)value;break;
                case 3:e->modeldata.mprate=(int)value;break;
                case 4:e->modeldata.mpdroprate=(int)value;break;
                case 5:e->modeldata.chargerate=(int)value;break;
                default:abort();
            }
            break;
        case _ep_position:
            if(index==0) e->x=(float)value;
            else if(index==1) e->z=(float)value;
            else e->a=(float)value;
            break;
        case _ep_running:
            switch(index) {
                case 0:e->modeldata.runspeed=(float)value;break;
                case 1:e->modeldata.runjumpheight=(float)value;break;
                case 2:e->modeldata.runjumpdist=(float)value;break;
                case 3:e->modeldata.runhold=(int)value;break;
                case 4:e->modeldata.runupdown=(int)value;break;
                default:abort();
            }
            break;
        case _ep_rush_count:e->rush[0]=(int)value;break;
        case _ep_rush_tally:e->rush[1]=(int)value;break;
        case _ep_velocity:
            if(index==0) e->xdir=(float)value;
            else if(index==1) e->zdir=(float)value;
            else e->tossv=(float)value;
            break;
        case _ep_edelay:
            switch(index) {
                case 0:e->modeldata.edelay.mode=(int)value;break;
                case 1:e->modeldata.edelay.factor=(float)value;break;
                case 2:e->modeldata.edelay.cap_min=(int)value;break;
                case 3:e->modeldata.edelay.cap_max=(int)value;break;
                case 4:e->modeldata.edelay.range_min=(int)value;break;
                case 5:e->modeldata.edelay.range_max=(int)value;break;
                default:abort();
            }
            break;
        default:abort();
    }
}
static void call(const struct contract *c,ScriptVariant *values,int count,
                 int expected_status,int expected_value) {
    // Exactly count pointers: an accidental read past paramCount is detectable.
    ScriptVariant **args=malloc((size_t)count*sizeof(*args));assert(args);
    for(int i=0;i<count;++i) args[i]=&values[i];
    ScriptVariant result={.vt=VT_INTEGER,.lVal=999},*output=&result;
    assert(invoke(args,&output,count)==expected_status);free(args);
    assert((output!=NULL)==(expected_status==S_OK && c->has_result));
    if(output) assert(output==&result && result.vt==VT_INTEGER &&
                      result.lVal==expected_value);
}
static void check_sequences(const struct contract *c) {
    static const struct { int property,width,stop_on_failure; } sequence[]={
        {_ep_komap,2,1}, {_ep_mpset,6,0}, {_ep_position,3,1},
        {_ep_running,5,0}, {_ep_rush_count,1,1}, {_ep_rush_tally,1,1},
        {_ep_velocity,3,1}, {_ep_edelay,6,2}
    };
    for(unsigned p=0;p<sizeof(sequence)/sizeof(*sequence);++p) {
        for(int count=1;count<=sequence[p].width;++count) {
            // The native edelay guards read one argument past short arrays.
            // Only its complete argument list runs in the original oracle.
            if(sequence[p].property==_ep_edelay && !GENERATED && count<6) continue;
            for(int mask=0;mask<(1<<count);++mask) for(int decimal=0;decimal<2;++decimal) {
                entity subject={0},expected={0};ScriptVariant v[8]={0};
                v[0]=(ScriptVariant){.vt=VT_PTR,.ptrVal=&subject};
                v[1]=(ScriptVariant){.vt=VT_INTEGER,.lVal=sequence[p].property};
                int active=0,result=0;
                for(int i=0;i<count;++i) {
                    int good=(mask>>i)&1;double value=17+i+(decimal?0.5:0.0);
                    v[i+2]=(ScriptVariant){.vt=good?(decimal?VT_DECIMAL:VT_INTEGER):VT_EMPTY};
                    if(decimal) v[i+2].dblVal=value;else v[i+2].lVal=(LONG)value;
                    int allowed=!c->has_result || i==0 || active;
                    if(good && allowed) expected_field(&expected,sequence[p].property,i,value);
                    if(i==0) active=result=good;
                    else if(c->has_result && active && !good &&
                            (sequence[p].stop_on_failure==1 ||
                             (sequence[p].stop_on_failure==2 && i>=2)))
                        active=result=0;
                }
                call(c,v,count+2,S_OK,result);
                assert(!memcmp(&subject,&expected,sizeof(subject)));
            }
        }
    }
}
static void check_actions(const struct contract *c) {
    entity subject={0};int marker=0;
    ScriptVariant v[3]={{.vt=VT_PTR,.ptrVal=&subject},
        {.vt=VT_INTEGER,.lVal=_ep_takeaction},{.vt=VT_INTEGER,.lVal=0}};
    for(int think=0;think<2;++think) {
        v[1].lVal=think?_ep_think:_ep_takeaction;
        const void **field=think?&subject.think:&subject.takeaction;
        *field=&marker;v[2]=(ScriptVariant){.vt=VT_INTEGER,.lVal=0};
        call(c,v,3,S_OK,0);
        assert(*field==(think?(const void*)common_think:(const void*)bomb_explode));
        *field=&marker;v[2].lVal=-1;call(c,v,3,S_OK,0);assert(*field==&marker);
        v[2].lVal=think?_cep_th_the_end:_cep_ta_the_end;
        call(c,v,3,S_OK,0);assert(*field==&marker);
        for(int empty=0;empty<2;++empty) {
            *field=&marker;v[2]=(ScriptVariant){.vt=empty?VT_EMPTY:VT_STR};
            int accepted=empty==c->action_empty;
            call(c,v,3,accepted?S_OK:E_FAIL,0);
            assert(*field==((accepted && !think)?NULL:&marker));
        }
    }
    v[1].lVal=_ep_trymove;
    for(int value=-1;value<=3;++value) {
        v[2]=(ScriptVariant){.vt=VT_INTEGER,.lVal=value};call(c,v,3,S_OK,1);
        assert(subject.trymove==(value==1?(const void*)common_trymove:
                               value==2?(const void*)player_trymove:NULL));
    }
    subject.trymove=&marker;v[2].vt=VT_EMPTY;call(c,v,3,S_OK,0);
    assert(subject.trymove==&marker);
    v[2]=(ScriptVariant){.vt=VT_DECIMAL,.dblVal=1.5};call(c,v,3,S_OK,1);
    assert(subject.trymove==(const void*)common_trymove);
}
static void check_animation(const struct contract *c) {
    entity subject={0};s_animation animation={.numframes=1};
    s_animation *animations[]={&animation};subject.animation=&animation;
    subject.modeldata.animation=animations;subject.modeldata.animation_capacity=1;
    ScriptVariant v[6]={{.vt=VT_PTR,.ptrVal=&subject},
        {.vt=VT_INTEGER,.lVal=_ep_animation},{.vt=VT_INTEGER,.lVal=7},
        {.vt=VT_INTEGER,.lVal=8},{.vt=VT_INTEGER,.lVal=17},
        {.vt=VT_EMPTY}};
    animation_calls=0;call(c,v,3,S_OK,1);
    assert(animation_calls==1 && animation_id==7 && animation_reset==1);
    call(c,v,4,S_OK,1);
    assert(animation_calls==2 && animation_id==7 && animation_reset==8);
    v[3].vt=VT_EMPTY;call(c,v,4,S_OK,0);assert(animation_calls==2);
    v[2].vt=VT_EMPTY;call(c,v,3,S_OK,0);assert(animation_calls==2);
    v[1].lVal=_ep_animhits;v[2]=(ScriptVariant){.vt=VT_INTEGER,.lVal=17};
    call(c,v,3,S_OK,1);assert(animation.animhits==17);
    v[2].vt=VT_EMPTY;call(c,v,3,S_OK,0);assert(animation.animhits==17);
#if GENERATED
    subject.animation=NULL;v[2].vt=VT_INTEGER;call(c,v,3,S_OK,0);
    assert(animation.animhits==17);subject.animation=&animation;
#endif
    v[1].lVal=_ep_combostep;v[2]=(ScriptVariant){.vt=VT_INTEGER,.lVal=1};
    v[3]=(ScriptVariant){.vt=VT_INTEGER,.lVal=257};call(c,v,4,S_OK,1);
    assert(subject.combostep[1]==1);
    v[3].vt=VT_EMPTY;call(c,v,4,S_OK,0);assert(subject.combostep[1]==1);
    call(c,v,3,S_OK,0);assert(subject.combostep[1]==1);
#if GENERATED
    v[3].vt=VT_INTEGER;
    for(int index=-1;index<=27;index+=28) {
        v[2].lVal=index;call(c,v,4,S_OK,0);assert(subject.combostep[1]==1);
    }
#endif
    v[1].lVal=_ep_energycost;
    v[2]=(ScriptVariant){.vt=VT_INTEGER,.lVal=_cep_energycost_cost};
    v[3]=(ScriptVariant){.vt=VT_INTEGER,.lVal=0};
    v[4]=(ScriptVariant){.vt=VT_INTEGER,.lVal=17};call(c,v,5,S_OK,1);
    assert(animation.energycost.cost==17);
    v[4].vt=VT_EMPTY;call(c,v,5,S_OK,1);assert(animation.energycost.cost==17);
    v[4]=(ScriptVariant){.vt=VT_INTEGER,.lVal=23};v[3].vt=VT_EMPTY;
    call(c,v,5,c->has_result?S_OK:E_FAIL,1);
    assert(animation.energycost.cost==(c->has_result?23:17));
    v[3]=(ScriptVariant){.vt=VT_INTEGER,.lVal=0};
    for(int property=1;property<3;++property) {
        v[2].lVal=property;call(c,v,5,S_OK,1);
    }
    assert(animation.energycost.disable==23 && animation.energycost.mponly==23);
    call(c,v,4,E_FAIL,0);call(c,v,6,E_FAIL,0);
    v[2].lVal=999;call(c,v,5,E_FAIL,0);
    v[2].vt=VT_EMPTY;call(c,v,5,E_FAIL,0);
#if GENERATED
    v[2]=(ScriptVariant){.vt=VT_INTEGER,.lVal=_cep_energycost_cost};
    for(int index=-1;index<=1;index+=2) {
        v[3].lVal=index;call(c,v,5,E_FAIL,0);
    }
#endif
}
static void expected_dot(entity *ent,int slot,int field,double value) {
    switch(field) {
        case 0:ent->dot_time[slot]=(int)value;break;
        case 1:ent->dot[slot]=(int)value;break;
        case 2:ent->dot_force[slot]=(int)value;break;
        case 3:ent->dot_rate[slot]=(int)value;break;
        case 4:ent->dot_atk[slot]=(int)value;break;
        default:abort();
    }
}
static void check_dot(const struct contract *c) {
    entity owner={0};
    for(int count=1;count<=5;++count) for(int mask=0;mask<(1<<count);++mask) {
        for(int decimal=0;decimal<2;++decimal) for(int with_owner=0;
                with_owner<=(count==5);++with_owner) {
            entity subject={0},expected={0};ScriptVariant v[9]={0};
            v[0]=(ScriptVariant){.vt=VT_PTR,.ptrVal=&subject};
            v[1]=(ScriptVariant){.vt=VT_INTEGER,.lVal=_ep_dot};
            v[2]=(ScriptVariant){.vt=VT_INTEGER,.lVal=1};
            int active=0,result=0;
            for(int field=0;field<count;++field) {
                int good=(mask>>field)&1;double value=17+field+(decimal?0.5:0.0);
                v[field+3]=(ScriptVariant){.vt=good?(decimal?VT_DECIMAL:VT_INTEGER):VT_EMPTY};
                if(decimal) v[field+3].dblVal=value;else v[field+3].lVal=(LONG)value;
                if(good && (!c->has_result || field==0 || active))
                    expected_dot(&expected,1,field,value);
                if(field==0) active=result=good;
                else if(c->has_result && active && !good) active=result=0;
            }
            if(with_owner) {
                v[8]=(ScriptVariant){.vt=VT_PTR,.ptrVal=&owner};
                expected.dot_owner[1]=&owner;
            }
            call(c,v,count+3+with_owner,S_OK,result);
            assert(!memcmp(&subject,&expected,sizeof(subject)));
        }
    }
    entity subject={0};ScriptVariant v[4]={{.vt=VT_PTR,.ptrVal=&subject},
        {.vt=VT_INTEGER,.lVal=_ep_dot},{.vt=VT_EMPTY},
        {.vt=VT_INTEGER,.lVal=17}};
    // Failed index conversion uses the initialized slot zero only in the
    // returning implementation; later implementations skip the operation.
    call(c,v,4,S_OK,1);assert(subject.dot_time[0]==(c->has_result?17u:0u));
    v[2]=(ScriptVariant){.vt=VT_INTEGER,.lVal=MAX_DOTS-1};
    call(c,v,4,S_OK,1);assert(subject.dot_time[MAX_DOTS-1]==17u);
#if GENERATED
    for(int slot=-1;slot<=MAX_DOTS;slot+=MAX_DOTS+1) {
        v[2].lVal=slot;call(c,v,4,S_OK,0);
    }
    v[2].lVal=1;call(c,v,3,S_OK,0);assert(subject.dot_time[1]==0u);
#endif
}
static void check_models(const struct contract *c) {
    entity subject={0},other={0};ScriptVariant v[4]={{.vt=VT_PTR,.ptrVal=&subject},
        {.vt=VT_INTEGER,.lVal=_ep_defaultname},{.vt=VT_STR,.strVal=0},
        {.vt=VT_INTEGER,.lVal=8}};
    strcpy(cached_string,"known");call(c,v,3,S_OK,1);
    assert(subject.defaultmodel==&known_model);
    strcpy(cached_string,"missing");call(c,v,3,E_FAIL,0);
    assert(subject.defaultmodel==&known_model);
    v[2].vt=VT_EMPTY;call(c,v,3,E_FAIL,0);
    v[1].lVal=_ep_model;v[2].vt=VT_STR;strcpy(cached_string,"known");
    model_calls=0;call(c,v,3,S_OK,1);
    assert(model_calls==c->has_result);
    assert(subject.weapent==(c->has_result?&subject:NULL));
    if(c->has_result) assert(model_option==0);
    subject.weapent=NULL;v[3].vt=VT_EMPTY;call(c,v,4,S_OK,0);
    assert(model_calls==c->has_result);
    assert(subject.weapent==(c->has_result?&subject:NULL));
    subject.weapent=&other;v[3]=(ScriptVariant){.vt=VT_INTEGER,.lVal=8};
    call(c,v,4,S_OK,1);assert(model_calls==c->has_result+1 && model_option==8);
    assert(subject.weapent==&other);
    v[2].vt=VT_EMPTY;call(c,v,4,E_FAIL,0);
    v[1].lVal=_ep_name;v[2].vt=VT_STR;call(c,v,3,S_OK,1);
    assert(!strcmp(subject.name,"known"));
    v[2].vt=VT_EMPTY;call(c,v,3,E_FAIL,0);assert(!strcmp(subject.name,"known"));
#if GENERATED
    memset(cached_string,'z',sizeof(cached_string)-1);cached_string[sizeof(cached_string)-1]=0;
    v[2].vt=VT_STR;call(c,v,3,S_OK,1);
    assert(strlen(subject.name)==sizeof(subject.name)-1);
    for(unsigned i=0;i<sizeof(subject.name)-1;++i) assert(subject.name[i]=='z');
#endif
    v[1].lVal=_ep_map;v[2]=(ScriptVariant){.vt=VT_INTEGER,.lVal=4};
    map_calls=0;call(c,v,3,S_OK,1);assert(map_calls==1 && map_value==4u);
    v[2].vt=VT_EMPTY;call(c,v,3,S_OK,0);assert(map_calls==1);
    v[2]=(ScriptVariant){.vt=VT_DECIMAL,.dblVal=4.5};
    call(c,v,3,S_OK,1);assert(map_calls==2 && map_value==4u);
}
static void check(const struct contract *c) {
    obor_profile_build=c->revision;
    entity subject={0};s_sprite image={1},replacement={2};
    int frames[]={0,2};s_animation animation={.numframes=2,.sprite=frames},*animations[]={&animation};
    subject.modeldata.animation=animations;subject.modeldata.animation_capacity=1;
    s_sprite_list node={0};node.filename=malloc(1024);assert(node.filename);
    strcpy(node.filename,"old");node.sprite=&image;
    sprite_map_max_items=3;sprites_loaded=3;
    sprite_map=calloc(3,sizeof(*sprite_map));assert(sprite_map);
    sprite_map[0].node=&node;
    ScriptVariant v[6]={{.vt=VT_PTR,.ptrVal=&subject},
        {.vt=VT_INTEGER,.lVal=_ep_spritea},
        {.vt=VT_INTEGER,.lVal=_cep_spritea_centerx},
        {.vt=VT_INTEGER,.lVal=0},{.vt=VT_INTEGER,.lVal=0},
        {.vt=VT_INTEGER,.lVal=17}};
    call(c,v,6,S_OK,1);assert(sprite_map[0].centerx==17);
    v[5].vt=VT_EMPTY;call(c,v,6,S_OK,0);assert(sprite_map[0].centerx==17);
    v[5]=(ScriptVariant){.vt=VT_INTEGER,.lVal=23};
    v[2].lVal=_cep_spritea_centery;call(c,v,6,S_OK,1);
    assert(sprite_map[0].centery==23);
    v[2].lVal=_cep_spritea_file;strcpy(cached_string,"new.sprite");
    v[5]=(ScriptVariant){.vt=VT_STR,.strVal=0};call(c,v,6,S_OK,1);
    assert(!strcmp(node.filename,cached_string));
    v[5].vt=VT_EMPTY;call(c,v,6,E_FAIL,0);
    v[2].lVal=_cep_spritea_sprite;
    v[5]=(ScriptVariant){.vt=VT_PTR,.ptrVal=&replacement};call(c,v,6,S_OK,1);
    assert(node.sprite==&replacement);
    v[2].lVal=999;call(c,v,6,E_FAIL,0);
    // A centre write needs an allocated map entry, not a live sprite node.
    v[2].lVal=_cep_spritea_centerx;v[4].lVal=1;
    v[5]=(ScriptVariant){.vt=VT_INTEGER,.lVal=37};call(c,v,6,S_OK,1);
    assert(sprite_map[2].centerx==37 && sprite_map[2].node==NULL);
    v[1].lVal=_ep_weapon;v[2]=(ScriptVariant){.vt=VT_INTEGER,.lVal=17};
    weapon_calls=0;call(c,v,3,S_OK,1);
    assert(weapon_calls==1 && weapon_value==17 && weapon_optional==0);
    v[3]=(ScriptVariant){.vt=VT_INTEGER,.lVal=8};call(c,v,4,S_OK,1);
    assert(weapon_calls==2 && weapon_value==17 && weapon_optional==8);
    v[2].vt=VT_EMPTY;call(c,v,4,S_OK,0);assert(weapon_calls==2);
    v[1].lVal=_ep_knockdowncount;
    v[2]=(ScriptVariant){.vt=VT_INTEGER,.lVal=_cep_knockdowncount_current};
    v[3]=(ScriptVariant){.vt=VT_DECIMAL,.dblVal=17.5};call(c,v,4,S_OK,1);
    assert(subject.knockdowncount==17.5f);
    v[3].vt=VT_EMPTY;call(c,v,4,S_OK,0);assert(subject.knockdowncount==17.5f);
    v[2].lVal=_cep_knockdowncount_max;
    v[3]=(ScriptVariant){.vt=VT_DECIMAL,.dblVal=23.5};call(c,v,4,S_OK,1);
    assert(subject.modeldata.knockdowncount==23.5f);
    // Native time uses argument 2 itself, not an absent fourth argument.
    v[2].lVal=_cep_knockdowncount_time;call(c,v,3,S_OK,1);
    assert(subject.knockdowntime==_cep_knockdowncount_time);
    v[2].lVal=999;call(c,v,3,E_FAIL,0);
#if GENERATED
    // The original has undefined reads for these calls; never execute them in
    // the original oracle. Rejection must leave live data unchanged.
    for(int field=0;field<2;++field) {
        v[2].lVal=field;call(c,v,3,S_OK,0);
    }
    assert(subject.knockdowncount==17.5f && subject.modeldata.knockdowncount==23.5f);
    v[1].lVal=_ep_weapon;v[2]=(ScriptVariant){.vt=VT_INTEGER,.lVal=17};
    v[3].vt=VT_EMPTY;call(c,v,4,S_OK,0);assert(weapon_calls==2);
    v[1].lVal=_ep_spritea;
    v[2]=(ScriptVariant){.vt=VT_INTEGER,.lVal=_cep_spritea_centerx};
    v[3]=(ScriptVariant){.vt=VT_INTEGER,.lVal=0};
    v[4]=(ScriptVariant){.vt=VT_INTEGER,.lVal=0};
    v[5]=(ScriptVariant){.vt=VT_INTEGER,.lVal=91};
    for(int count=3;count<6;++count) call(c,v,count,S_OK,0);
    for(int frame=-1;frame<=2;frame+=3) {
        v[4].lVal=frame;call(c,v,6,S_OK,0);
    }
    v[4].lVal=0;
    for(int anim=-1;anim<=1;anim+=2) {
        v[3].lVal=anim;call(c,v,6,S_OK,0);
    }
    v[3].lVal=0;animation.sprite=NULL;call(c,v,6,S_OK,0);animation.sprite=frames;
    for(int index=-1;index<=3;index+=4) {
        frames[0]=index;call(c,v,6,S_OK,0);
    }
    frames[0]=0;s_sprite_map *saved_map=sprite_map;sprite_map=NULL;
    call(c,v,6,S_OK,0);sprite_map=saved_map;
    assert(sprite_map[0].centerx==17 && sprite_map[0].centery==23);
    sprite_map[0].node=NULL;v[2].lVal=_cep_spritea_file;
    v[5]=(ScriptVariant){.vt=VT_STR,.strVal=0};call(c,v,6,S_OK,0);
    v[2].lVal=_cep_spritea_sprite;v[5].vt=VT_PTR;call(c,v,6,S_OK,0);
    sprite_map[0].node=&node;v[2].lVal=_cep_spritea_file;v[5].vt=VT_STR;
    free(node.filename);node.filename=malloc(2);assert(node.filename);
    strcpy(node.filename,"x");memset(cached_string,'z',sizeof(cached_string)-1);
    cached_string[sizeof(cached_string)-1]=0;call(c,v,6,S_OK,1);
    assert(!strcmp(node.filename,cached_string));
#endif
    free(node.filename);free(sprite_map);sprite_map=NULL;
    check_sequences(c);
    check_actions(c);
    check_animation(c);
    check_dot(c);
    check_models(c);
}
int main(int argc,char **argv) {
    assert(argc==2);int revision=atoi(argv[1]),matched=0;
    for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i) {
        if(contracts[i].revision==revision) { check(&contracts[i]);++matched; }
    }
    assert(matched==1);return 0;
}
'''
    if not generated:
        observation = {'status': 'PASS', 'sources': len(contracts),
                       'properties': len(PROPERTIES)}
        program = program[:program.index('int main(int argc,char **argv)')] + (
            'int main(void) {\n'
            'for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i) check(&contracts[i]);\n'
            'puts(' + json.dumps(json.dumps(observation)) + ');return 0;\n}\n')
    values = [('PROPERTIES_ENUM', 'enum { '+','.join(PROPERTIES)+' };'),
        ('STUBS', '\n'.join('static void '+name+'(void) { abort(); }'
               for name in sorted(set(components['actions']) |
                                  {'common_trymove', 'player_trymove'}))),
        ('HELPERS', components['helpers']), ('ENTRIES', components['entries']),
        ('INVOKE', components['invoke']), ('GENERATED', str(int(generated))),
        ('CONTRACTS', '\n'.join('{%d,%d,%d},' %
                              (row['revision'], row['has_result'], row['action_empty'])
                              for row in contracts))]
    for name, value in values:
        program = program.replace(name, value)
    return program


class EntityComplexTests(unittest.TestCase):
    def test_registry_has_own_sources_for_each_registered_profile(self):
        rows = CONTRACTS['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        for profile in pin['profiles']:
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['setter_sha256'], r'^[0-9a-f]{64}$')
            self.assertIs(type(row['has_result']), bool)
            self.assertIs(type(row['action_empty']), bool)
            self.assertEqual(set(row['cases']), set(PROPERTIES))
            for digest in row['cases'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')

    def test_complex_mutations_and_results_per_profile(self):
        with tempfile.TemporaryDirectory(prefix='anybor-entity-complex-') as temporary:
            work = Path(temporary); source = work / 'probe.c'; exe = work / 'probe'
            source.write_text(complex_program())
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-Wno-error=deprecated-declarations', '-Wno-unused-variable',
                '-Wno-unused-const-variable', '-Wno-unused-function', '-g',
                '-fsanitize=address,undefined', str(source), '-o', str(exe)],
                check=True, timeout=60)
            executed = []
            for row in CONTRACTS['sources']:
                with self.subTest(profile=row['revision']):
                    subprocess.run([str(exe), str(row['revision'])], check=True,
                        timeout=20, env=sanitizer_environment())
                    executed.append(row['revision'])
            self.assertEqual(executed, [row['revision'] for row in CONTRACTS['sources']])
            print(json.dumps({'executed_profiles': executed,
                'scope': 'Selected complex branches and entry/exit; reduced types and action stubs'}))


if __name__ == '__main__':
    unittest.main()
