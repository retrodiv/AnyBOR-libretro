"""Check sprite and statistics reads against each profile's original callback.

The callback and variant conversions are real source; storage and numeric
mapping are reduced fixtures. Full animation loading and gameplay are separate
contracts. Invalid queries are checked only against the bounded core.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from test_historical_player import function, switch_cases

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
CONTRACT_PATH = Path(__file__).parent / 'fixtures/profile-sprite-stats-read-contracts.json'


def reader_entry(source):
    method, cases = switch_cases(source, 'openbor_getentityproperty', 'propind')
    for label, row in sorted(cases.items(), key=lambda item: item[1]['label_start'], reverse=True):
        if label not in ('_ep_sprite', '_ep_spritea', '_ep_icon', '_ep_stats', 'default'):
            method = method[:row['label_start']] + method[row['end']:]
    return method


def reader_program(components=None, common=None, contracts=None, *, original=False):
    rows = load_contract_fixture(CONTRACT_PATH)['sources'] if contracts is None else contracts
    if components is None:
        source = (SOURCE / 'src/engines/3741/openborscript.c').read_text()
        components = {'entries': reader_entry(source),
            'translation': 'static int obor_entity_get_property_native(int p) {return p;}',
            'helpers': ''}
        variant = (SOURCE / 'src/engines/3741/source/scriptlib/ScriptVariant.c').read_text()
        common = {name: function(variant, name) for name in
            ('ScriptVariant_ChangeType', 'ScriptVariant_Clear')}
    if common is None:
        raise ValueError('Explicit source conversions required')
    program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int32_t LONG;
typedef int HRESULT;
typedef double DOUBLE;
typedef void VOID;
typedef enum {VT_EMPTY=0,VT_INTEGER=1,VT_DECIMAL=2,VT_PTR=5,VT_STR=6} VARTYPE;
typedef struct {union {LONG lVal;DOUBLE dblVal;void *ptrVal;int strVal;};VARTYPE vt;} ScriptVariant;
typedef struct {int centerx,centery;} s_sprite;
typedef struct {int marker;} s_attack;
typedef struct {s_sprite *sprite;char *filename;} s_sprite_list;
typedef struct {int centerx,centery;s_sprite_list *node;} s_sprite_map;
typedef struct {int numframes;int *sprite;} s_animation;
typedef struct {s_animation **animation;int animation_capacity;float stats[20];
 struct {short def,die,get,mphigh,mplow,mpmed,pain,weapon,x,y;} icon;} s_model;
typedef struct {s_model modeldata;s_animation *animation;int animpos;float stats[20];} entity;
enum {_ep_sprite,_ep_spritea,_ep_stats,_ep_icon};
enum {_gep_spritea_centerx,_gep_spritea_centery,_gep_spritea_file,_gep_spritea_sprite};
enum {_gep_icon_def,_gep_icon_die,_gep_icon_get,_gep_icon_mphigh,_gep_icon_mplow,
 _gep_icon_mpmed,_gep_icon_pain,_gep_icon_weapon,_gep_icon_x,_gep_icon_y};
#define S_OK 0
#define E_FAIL (-1)
#define MAX_STR_VAR_LEN 64
#define validanim(e,a) ((a)>=0 && (a)<(e)->modeldata.animation_capacity && \
 (e)->modeldata.animation && (e)->modeldata.animation[a] && \
 (e)->modeldata.animation[a]->numframes)
static s_sprite sprites[5];
static s_sprite_list nodes[5];
static s_sprite_map maps[5],*sprite_map=maps;
static int sprite_map_max_items=5;
static unsigned int sprites_loaded=5;
static char names[5][MAX_STR_VAR_LEN+2],cache[MAX_STR_VAR_LEN+1];
static int frame_ids[2][3]={{0,2,4},{1,3,0}};
static s_animation animations[2]={{3,frame_ids[0]},{2,frame_ids[1]}};
static s_animation *animation_table[2]={&animations[0],&animations[1]};
static entity actor;
static uint32_t obor_profile_build;
static int quiet_printf(const char *format,...) {(void)format;return 0;}
#define printf quiet_printf
static int StrCache_Pop(void) {memset(cache,0,sizeof(cache));return 0;}
static void StrCache_Collect(int index) {assert(index==0);}
static char *StrCache_Get(int index) {assert(index==0);return cache;}
@CONVERSIONS@
static void mapstrings_getentityproperty(ScriptVariant **args,int count) {(void)args;(void)count;}
@TRANSLATION@
@HELPERS@
@ENTRIES@
struct contract {int revision,stats_count,spritea_x_is_y;};
static const struct contract contracts[]={@CONTRACTS@};
static ScriptVariant integer(LONG value) {return (ScriptVariant){.vt=VT_INTEGER,.lVal=value};}
static short *icon_field(int selector) {
 switch(selector) {
  case _gep_icon_def:return &actor.modeldata.icon.def;
  case _gep_icon_die:return &actor.modeldata.icon.die;
  case _gep_icon_get:return &actor.modeldata.icon.get;
  case _gep_icon_mphigh:return &actor.modeldata.icon.mphigh;
  case _gep_icon_mplow:return &actor.modeldata.icon.mplow;
  case _gep_icon_mpmed:return &actor.modeldata.icon.mpmed;
  case _gep_icon_pain:return &actor.modeldata.icon.pain;
  case _gep_icon_weapon:return &actor.modeldata.icon.weapon;
  case _gep_icon_x:return &actor.modeldata.icon.x;
  case _gep_icon_y:return &actor.modeldata.icon.y;
  default:abort();
 }
}
static void reset(void) {
 actor=(entity){.modeldata={.animation=animation_table,.animation_capacity=2},
                 .animation=&animations[0],.animpos=0};
 sprite_map=maps;sprite_map_max_items=5;sprites_loaded=5;
 animations[0]=(s_animation){3,frame_ids[0]};
 animations[1]=(s_animation){2,frame_ids[1]};
 animation_table[0]=&animations[0];animation_table[1]=&animations[1];
 for(int i=0;i<5;++i) {
  snprintf(names[i],sizeof(names[i]),"data/sprites/frame-%d.gif",i);
  nodes[i]=(s_sprite_list){&sprites[i],names[i]};
  maps[i]=(s_sprite_map){10+i,30+i,&nodes[i]};
  sprites[i]=(s_sprite){-1,-1};
 }
 for(int i=0;i<20;++i) {
  actor.modeldata.stats[i]=i==0?0:(float)(i+0.25);
  actor.stats[i]=i==0?0:(float)(-i-0.5);
 }
}
static void run(int property,ScriptVariant selector,ScriptVariant animation,
 ScriptVariant frame,int count,int status,VARTYPE type,DOUBLE number,int sprite_index) {
 ScriptVariant values[5]={{.vt=VT_PTR,.ptrVal=&actor},integer(property),
   selector,animation,frame},*args[5];
 for(int i=0;i<5;++i) args[i]=&values[i];
 ScriptVariant result=integer(999),*output=&result;
 assert(openbor_getentityproperty(args,&output,count)==status);
 assert(output==&result);assert(result.vt==type);
 if(type==VT_INTEGER) assert(result.lVal==(LONG)number);
 if(type==VT_DECIMAL) assert(result.dblVal==number);
 if(type==VT_PTR) assert(result.ptrVal==&sprites[sprite_index]);
 if(type==VT_STR) assert(strcmp(cache,names[sprite_index])==0);
}
static void empty(int property,ScriptVariant selector,ScriptVariant animation,ScriptVariant frame,int count) {
 run(property,selector,animation,frame,count,S_OK,VT_EMPTY,0,0);
}
static void check(const struct contract *c) {
 obor_profile_build=c->revision;reset();
 for(int a=0;a<2;++a) for(int f=0;f<animations[a].numframes;++f) {
  int id=frame_ids[a][f];actor.animation=&animations[a];actor.animpos=f;
  run(_ep_sprite,integer(0),integer(0),integer(0),2,S_OK,VT_PTR,0,id);
  assert(sprites[id].centerx==maps[id].centerx && sprites[id].centery==maps[id].centery);
  for(int p=_gep_spritea_centerx;p<=_gep_spritea_sprite;++p) {
   VARTYPE kind=p==_gep_spritea_file?VT_STR:p==_gep_spritea_sprite?VT_PTR:VT_INTEGER;
   DOUBLE value=p==_gep_spritea_centerx?maps[id].centerx:maps[id].centery;
   run(_ep_spritea,integer(p),integer(a),integer(f),5,S_OK,kind,value,id);
   if(p==_gep_spritea_sprite) {
    assert(sprites[id].centerx==(c->spritea_x_is_y?maps[id].centery:maps[id].centerx));
    assert(sprites[id].centery==maps[id].centery);
   }
  }
  run(_ep_spritea,integer(99),integer(a),integer(f),5,E_FAIL,VT_EMPTY,0,0);
 }
 for(int selector=-1;selector<=2;++selector) for(int i=0;i<c->stats_count;++i) {
  DOUBLE expected=selector==1?actor.stats[i]:actor.modeldata.stats[i];
  run(_ep_stats,integer(selector),integer(i),integer(0),4,S_OK,VT_DECIMAL,expected,0);
 }
 empty(_ep_stats,integer(0),integer(0),integer(0),2);
 empty(_ep_stats,integer(0),integer(0),integer(0),3);
 run(_ep_stats,(ScriptVariant){.vt=VT_DECIMAL,.dblVal=1},integer(0),integer(0),4,E_FAIL,VT_EMPTY,0,0);
 run(_ep_stats,integer(0),(ScriptVariant){.vt=VT_STR,.strVal=0},integer(0),4,E_FAIL,VT_EMPTY,0,0);
 empty(_ep_spritea,integer(0),integer(2),integer(0),5);
 for(int selector=_gep_icon_def;selector<=_gep_icon_y;++selector) {
  for(int id=-2;id<5;++id) {
   *icon_field(selector)=id;
   run(_ep_icon,integer(selector),integer(0),integer(0),3,S_OK,
       id<0?VT_INTEGER:VT_PTR,-1,id);
   if(id>=0) assert(sprites[id].centerx==maps[id].centerx && sprites[id].centery==maps[id].centery);
  }
 }
 run(_ep_icon,integer(99),integer(0),integer(0),3,E_FAIL,VT_EMPTY,0,0);
 run(_ep_icon,(ScriptVariant){.vt=VT_DECIMAL,.dblVal=0},integer(0),integer(0),3,E_FAIL,VT_EMPTY,0,0);
#if @GENERATED@
 /* Invalid queries are defined core behavior, not an oracle for historical UB. */
 empty(_ep_icon,integer(0),integer(0),integer(0),2);
 *icon_field(_gep_icon_def)=sprite_map_max_items;
 empty(_ep_icon,integer(_gep_icon_def),integer(0),integer(0),3);
 *icon_field(_gep_icon_def)=0;
 sprites_loaded=0;
 empty(_ep_icon,integer(_gep_icon_def),integer(0),integer(0),3);
 empty(_ep_sprite,integer(0),integer(0),integer(0),2);
 empty(_ep_spritea,integer(0),integer(0),integer(0),5);
 sprites_loaded=5;
 for(int count=2;count<5;++count) empty(_ep_spritea,integer(0),integer(0),integer(0),count);
 for(int argument=0;argument<3;++argument) {
  ScriptVariant inputs[3]={integer(0),integer(0),integer(0)};
  inputs[argument]=(ScriptVariant){.vt=VT_DECIMAL,.dblVal=0};
  empty(_ep_spritea,inputs[0],inputs[1],inputs[2],5);
 }
 LONG invalid[]={-1,20,INT32_MAX,INT32_MIN};
 for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);++i) {
  empty(_ep_stats,integer(0),integer(invalid[i]),integer(0),4);
  empty(_ep_stats,integer(1),integer(invalid[i]),integer(0),4);
  empty(_ep_spritea,integer(0),integer(invalid[i]),integer(0),5);
  empty(_ep_spritea,integer(0),integer(0),integer(invalid[i]),5);
 }
 empty(_ep_spritea,integer(0),integer(0),integer(3),5);
 actor.animation=NULL;empty(_ep_sprite,integer(0),integer(0),integer(0),2);
 actor.animation=&animations[0];actor.animpos=-1;
 empty(_ep_sprite,integer(0),integer(0),integer(0),2);
 actor.animpos=3;empty(_ep_sprite,integer(0),integer(0),integer(0),2);
 actor.animpos=0;animations[0].sprite=NULL;
 empty(_ep_sprite,integer(0),integer(0),integer(0),2);
 empty(_ep_spritea,integer(0),integer(0),integer(0),5);
 animations[0].sprite=frame_ids[0];
 for(int id=-1;id<=5;id+=6) {
  frame_ids[0][0]=id;
  empty(_ep_sprite,integer(0),integer(0),integer(0),2);
  empty(_ep_spritea,integer(0),integer(0),integer(0),5);
 }
 frame_ids[0][0]=0;maps[0].node=NULL;
 empty(_ep_icon,integer(_gep_icon_def),integer(0),integer(0),3);
 empty(_ep_sprite,integer(0),integer(0),integer(0),2);
 /* Coordinate reads require only a valid map entry. */
 run(_ep_spritea,integer(_gep_spritea_centerx),integer(0),integer(0),5,S_OK,VT_INTEGER,10,0);
 empty(_ep_spritea,integer(_gep_spritea_file),integer(0),integer(0),5);
 empty(_ep_spritea,integer(_gep_spritea_sprite),integer(0),integer(0),5);
 maps[0].node=&nodes[0];nodes[0].sprite=NULL;
 empty(_ep_icon,integer(_gep_icon_def),integer(0),integer(0),3);
 empty(_ep_sprite,integer(0),integer(0),integer(0),2);
 empty(_ep_spritea,integer(_gep_spritea_sprite),integer(0),integer(0),5);
 nodes[0].filename=NULL;
 empty(_ep_spritea,integer(_gep_spritea_file),integer(0),integer(0),5);
 nodes[0].filename=names[0];memset(names[0],'a',MAX_STR_VAR_LEN);
 names[0][MAX_STR_VAR_LEN]=0;
 run(_ep_spritea,integer(_gep_spritea_file),integer(0),integer(0),5,S_OK,VT_STR,0,0);
 names[0][MAX_STR_VAR_LEN]='a';names[0][MAX_STR_VAR_LEN+1]=0;
 empty(_ep_spritea,integer(_gep_spritea_file),integer(0),integer(0),5);
 sprite_map=NULL;empty(_ep_sprite,integer(0),integer(0),integer(0),2);
 empty(_ep_icon,integer(_gep_icon_def),integer(0),integer(0),3);
 empty(_ep_spritea,integer(0),integer(0),integer(0),5);
 actor.modeldata.animation=NULL;empty(_ep_spritea,integer(0),integer(0),integer(0),5);
#endif
}
int main(int argc,char **argv) {
 assert(argc==2);int revision=atoi(argv[1]),matched=0;
 for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i)
  if(contracts[i].revision==revision) {check(&contracts[i]);++matched;}
 assert(matched==1);return 0;
}
'''
    if original:
        observation = {'status': 'PASS', 'sources': len(rows), 'properties': 4}
        program = program[:program.index('int main(int argc,char **argv)')] + (
            'int main(void) {for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i)'
            'check(&contracts[i]);puts(' + json.dumps(json.dumps(observation)) + ');return 0;}\n')
    insertions = {'CONVERSIONS': '\n'.join(common[name] for name in
        ('ScriptVariant_ChangeType', 'ScriptVariant_Clear')),
        'TRANSLATION': components.get('translation', ''),
        'HELPERS': components.get('helpers', ''), 'ENTRIES': components['entries'],
        'GENERATED': str(int(not original)),
        'CONTRACTS': ','.join('{%d,%d,%d}' % (row['revision'], row['stats_count'],
            row['spritea_x_is_y']) for row in rows)}
    return re.sub(r'@(' + '|'.join(insertions) + r')@', lambda m: insertions[m[1]], program)


class SpriteStatsReadTests(unittest.TestCase):
    def test_registry_covers_registered_profiles_and_source_identities(self):
        rows = load_contract_fixture(CONTRACT_PATH)['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        for profile in contract_profiles(Path(__file__).parent / 'fixtures/profile-sprite-stats-read-contracts.json', pin['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertEqual(row['stats_count'], 20)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['getter_hashes'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')

    def test_valid_original_results_and_bounded_queries_per_profile(self):
        rows = load_contract_fixture(CONTRACT_PATH)['sources']
        with tempfile.TemporaryDirectory(prefix='anybor-sprite-stats-read-') as temporary:
            work = Path(temporary); source = work / 'probe.c'; executable = work / 'probe'
            source.write_text(reader_program())
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-unused-variable', '-Wno-unused-function', '-g',
                '-fsanitize=address,undefined', str(source), '-o', str(executable)],
                check=True, timeout=60)
            for row in rows:
                with self.subTest(profile=row['revision']):
                    subprocess.run([str(executable), str(row['revision'])], check=True,
                        timeout=20, env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
