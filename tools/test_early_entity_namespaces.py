"""Check historical entity names, numeric IDs and selected getter/setter results.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from native_sanitizers import sanitizer_environment
from test_historical_player import function, switch_cases

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-entity-namespaces.json'
GET = ['antigrab', 'animal', 'blockodds', 'escapecount', 'escapehits', 'grabforce', 'grabbing',
       'health', 'score', 'thold', 'pain_time', 'nolife', 'type', 'map', 'mapcount', 'mapdefault', 'maps', 'aiflag',
       'guardpoints', 'maxguardpoints', 'jugglepoints', 'maxjugglepoints', 'detect', 'stealth']
SET = ['antigrab', 'blockodds', 'escapecount', 'escapehits', 'grabforce', 'health', 'score', 'thold', 'pain_time',
       'nolife', 'type', 'think', 'aiflag']


def namespace_descriptor(source, name):
    """Extract one flat anonymous typedef without crossing another type."""
    if not isinstance(name, str) or len(name) > 63 or not re.fullmatch(r'[A-Za-z_]\w*', name):
        raise AssertionError('A bounded C type name is required')
    matches = list(re.finditer(r'\btypedef\s+struct\s*\{[^{}]*\}\s*' + re.escape(name) + r'\s*;', source))
    if len(matches) != 1:
        raise AssertionError('Exactly one flat namespace descriptor is required')
    return matches[0][0]


def selected_dispatch(source, name, labels):
    method, cases = switch_cases(source, name, 'propind')
    prefix = re.split(r'\bswitch\s*\(propind\)', method, maxsplit=1)[0]
    body = '\n'.join('case ' + label + ':' + cases[label]['body'] for label in labels)
    if name == 'openbor_getentityproperty':
        return prefix + 'switch(propind){\n' + body + '\ndefault:*pretvar=NULL;return E_FAIL;}return S_OK;}\n'
    return prefix + 'switch(propind){\n' + body + '\ndefault:goto changeentityproperty_error;}\nreturn S_OK;\nchangeentityproperty_error:*pretvar=NULL;return E_FAIL;}\n'


class EarlyEntityNamespaceTests(unittest.TestCase):
    def test_descriptor_type_boundary(self):
        first = 'typedef struct { const char *const *names; int count; } other_namespace;'
        wanted = 'typedef struct { const char *const *names; int count; } wanted_namespace;'
        self.assertEqual(namespace_descriptor(first + wanted, 'wanted_namespace'), wanted)
        for source in [first, wanted + wanted]:
            with self.assertRaises(AssertionError):
                namespace_descriptor(source, 'wanted_namespace')
        with self.assertRaises(AssertionError):
            namespace_descriptor(wanted, 'invalid type')

    def test_named_numeric_and_repeated_mapping_queries(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        self.assertEqual(len(rows), len({row['revision'] for row in rows}))
        revisions = {row['revision'] for row in rows}
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openborscript.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        enum_get = source[source.index('enum getentityproperty_enum'):source.index('void mapstrings_getentityproperty(')]
        enum_set = source[source.index('enum changeentityproperty_enum'):source.index('void mapstrings_changeentityproperty(')]
        descriptor = namespace_descriptor(source, 'obor_property_namespace')
        self.assertIsNotNone(descriptor)
        macro = re.search(r'(?m)^#define MAPSTRINGS\([^\n]+(?:\n[^\n]*)*?\n}', source)
        self.assertIsNotNone(macro)
        pieces = [descriptor, '\n'.join('static const obor_property_namespace *' + name + '(void);' for name in [
            'obor_get_property_namespace', 'obor_set_property_namespace', 'obor_get_aiflag_namespace', 'obor_set_aiflag_namespace']),
            function(source, 'obor_property_index'), enum_get, enum_set,
            function((engine / 'source/utils.c').read_text(), 'searchList'), macro[0],
            function(source, 'mapstrings_getentityproperty'), function(source, 'mapstrings_changeentityproperty')]
        pieces += [function(variant, name) for name in ['ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue']]
        pieces += [selected_dispatch(source, 'openbor_getentityproperty', ['_gep_' + name for name in GET]),
                   selected_dispatch(source, 'openbor_changeentityproperty', ['_cep_' + name for name in SET])]
        arrays, checks = [], []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            suffix = str(row['revision'])
            for kind in ['get', 'change', 'aiflag', 'set_aiflag']:
                ns = row['namespaces'][kind]
                self.assertTrue(ns['cases'] and ns['names'])
                ids = [label if label != '_gep_staydownatk' else '-1' for label in ns['cases']]
                arrays += ['static const int ids_' + kind + suffix + '[]={' + ','.join(ids) + '};',
                           'static const char *names_' + kind + suffix + '[]={' + ','.join(map(json.dumps, ns['names'])) + '};']
            self.assertIn(row['point_bits'], [16, 32])
            self.assertIn(row['stealth_bits'], [8, 16])
            checks.append('check(%d,%d,%d,%d,%s);' % (row['revision'], row['animal_handler'],
                          row['point_bits'], row['stealth_bits'], ','.join(
                'ids_%s%s,%d,names_%s%s,%d' % (kind, suffix, len(row['namespaces'][kind]['cases']),
                                             kind, suffix, len(row['namespaces'][kind]['names']))
                for kind in ['get', 'change', 'aiflag', 'set_aiflag'])))
        program = r'''
#include <assert.h>
#include <ctype.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#undef exit
#undef time
#undef kill
#undef pause
#undef shutdown
#undef printf
uint32_t obor_profile_build;
static char *cache[4096];
CHAR *StrCache_Get(int index) {assert(index>=0 && index<4096 && cache[index]);return cache[index];}
void StrCache_Collect(int index) {assert(index>=0 && index<4096);}
int StrCache_Pop(void) {abort();}
void common_think(void) {}
void player_think(void) {}
void steam_think(void) {}
void steamer_think(void) {}
void text_think(void) {}
void trap_think(void) {}
@PIECES@
@ARRAYS@
static entity e,other;
static s_model shared;
static int point_bits,stealth_bits,antigrab_entity;
static ScriptVariant values[4],result,*args[4],*out;
static void input(int numeric,int index,const char *name,int subnumeric,int subindex,const char *subname) {
 memset(values,0,sizeof(values));memset(&result,0,sizeof(result));out=&result;
 for(int i=0;i<4;i++)args[i]=&values[i];
 values[0].vt=VT_PTR;values[0].ptrVal=&e;
 values[1].vt=numeric?VT_INTEGER:VT_STR;
 if(numeric)values[1].lVal=index;else {cache[1000]=(char*)name;values[1].strVal=1000;}
 values[2].vt=subnumeric?VT_INTEGER:VT_STR;
 if(subnumeric)values[2].lVal=subindex;else {cache[1001]=(char*)subname;values[2].strVal=1001;}
 values[3].vt=VT_INTEGER;values[3].lVal=1;
}
static int written_flag(int id) {
 switch(id) {
 @FLAG_FIELDS@
 default:abort();
 }
}
static int get_id(void) {return obor_property_index(obor_get_property_namespace(),values[1].lVal,_gep_the_end);}
static int set_id(void) {return obor_property_index(obor_set_property_namespace(),values[1].lVal,_cep_the_end);}
static int get_flag(void) {return obor_property_index(obor_get_aiflag_namespace(),values[2].lVal,_gep_aiflag_the_end);}
static int set_flag(void) {return obor_property_index(obor_set_aiflag_namespace(),values[2].lVal,_cep_aiflag_the_end);}
static int ordinal(const int *ids,int count,int target) {for(int i=0;i<count;i++)if(ids[i]==target)return i;return -1;}
static void init_entity(void) {
 memset(&e,0,sizeof(e));memset(&shared,0,sizeof(shared));shared.grabforce=3;shared.antigrab=5;e.model=&shared;e.modeldata.antigrab=31;e.modeldata.health=64;e.health=39;e.modeldata.animal=7;e.modeldata.blockodds=8;e.escapecount=9;
 e.modeldata.escapehits=10;e.modeldata.grabforce=11;e.grabbing=&other;e.modeldata.score=12;
 e.modeldata.thold=13;e.pain_time=14;e.modeldata.nolife=15;e.modeldata.type=16;
 e.modeldata.maps_loaded=2;e.modeldata.colourmap[0]=(void*)1;e.modeldata.colourmap[1]=(void*)2;
 e.colourmap=(void*)2;e.map=17;e.dead=1;e.jumpid=1;e.jumping=1;e.idling=1;e.drop=1;
 e.attacking=1;e.getting=1;e.turning=1;e.charging=1;e.blocking=1;e.falling=1;e.running=1;
 e.inpain=1;e.invincible=1;e.freezetime=1;e.blink=1;e.animating=1;e.frozen=1;e.autokill=1;e.toexplode=1;e.projectile=1;
 e.dying=18;e.per2=19;e.per1=20;e.modeldata.maps.frozen=21;e.modeldata.maps.hide_end=22;
 e.modeldata.maps.hide_start=23;e.modeldata.maps.ko=24;e.modeldata.maps.kotype=25;e.maptime=26;
 e.modeldata.guardpoints.current=obor_model_points_value(65535,obor_profile_build);
 e.modeldata.guardpoints.maximum=obor_model_points_value(32768,obor_profile_build);
 e.modeldata.jugglepoints.current=obor_model_points_value(65536,obor_profile_build);
 e.modeldata.jugglepoints.maximum=obor_model_points_value(2147483647,obor_profile_build);
 e.modeldata.stealth.detect=obor_stealth_value(255,obor_profile_build);
 e.modeldata.stealth.hide=obor_stealth_value(128,obor_profile_build);
}
static int integer_get(int id) {
 switch(id) {
 case _gep_animal:return 7;case _gep_blockodds:return 8;case _gep_escapecount:return 9;
 case _gep_escapehits:return 10;case _gep_grabforce:return 11;case _gep_health:return 39;
 case _gep_score:return 12;case _gep_thold:return 13;case _gep_pain_time:return 14;
 case _gep_nolife:return 15;case _gep_type:return 16;case _gep_map:return 2;
 case _gep_mapcount:return 3;case _gep_mapdefault:return 17;default:return -1;
 }
}
static void getter_result(int target,int animal) {
 /* Expected results come from the original field domains, independently of the store helpers. */
 int domain_expected=0,domain_query=1;
 switch(target) {
 case _gep_guardpoints:domain_expected=point_bits==32?65535:-1;break;
 case _gep_maxguardpoints:domain_expected=point_bits==32?32768:-32768;break;
 case _gep_jugglepoints:domain_expected=point_bits==32?65536:0;break;
 case _gep_maxjugglepoints:domain_expected=point_bits==32?2147483647:-1;break;
 case _gep_detect:domain_expected=stealth_bits==16?255:-1;break;
 case _gep_stealth:domain_expected=stealth_bits==16?128:-128;break;
 default:domain_query=0;break;
 }
 if(domain_query) {
  assert(openbor_getentityproperty(args,&out,3)==S_OK && out==&result && out->vt==VT_INTEGER);
  assert(out->lVal==domain_expected);return;
 }
 int expected=integer_get(target);
 if(target==_gep_animal && !animal) {assert(openbor_getentityproperty(args,&out,3)==E_FAIL && !out);return;}
 if(expected>=0) {assert(openbor_getentityproperty(args,&out,3)==S_OK);assert(out==&result && out->vt==VT_INTEGER && out->lVal==expected);}
 else if(target==_gep_antigrab) {assert(openbor_getentityproperty(args,&out,3)==S_OK && out && out->vt==VT_DECIMAL && out->dblVal==31.0);}
 else if(target==_gep_maps) {values[2].lVal=_gep_maps_time;assert(openbor_getentityproperty(args,&out,3)==S_OK && out && out->vt==VT_INTEGER && out->lVal==26);}
 else if(target==_gep_grabbing) {assert(openbor_getentityproperty(args,&out,3)==S_OK && out->vt==VT_PTR && out->ptrVal==&other);}
}
static void setter_result(int target) {
 /* Values fit every original representation; field-width deltas are a separate contract. */
 if(target==_cep_antigrab || target==_cep_blockodds || target==_cep_escapecount || target==_cep_escapehits || target==_cep_grabforce ||
    target==_cep_health || target==_cep_score || target==_cep_thold || target==_cep_pain_time ||
    target==_cep_nolife || target==_cep_type) {
  if(target==_cep_grabforce)values[2].lVal=27;
  assert(openbor_changeentityproperty(args,&out,3)==S_OK && out==&result && out->vt==VT_INTEGER);
  if(target==_cep_antigrab) {if(antigrab_entity)assert(shared.antigrab==5 && e.modeldata.antigrab==11);else assert(shared.antigrab==11 && e.modeldata.antigrab==31);}
  if(target==_cep_health)assert(e.health==11);
  if(target==_cep_pain_time)assert(e.pain_time==11);
  if(target==_cep_blockodds)assert(e.modeldata.blockodds==11);
  if(target==_cep_escapehits)assert(e.modeldata.escapehits==11 && e.escapecount==9);
  if(target==_cep_escapecount)assert(e.escapecount==11 && e.modeldata.escapehits==10);
  if(target==_cep_grabforce) {if(obor_profile_build<3394)assert(shared.grabforce==27 && e.modeldata.grabforce==11);else assert(shared.grabforce==3 && e.modeldata.grabforce==27);}
  if(target==_cep_score)assert(e.modeldata.score==11);
  if(target==_cep_thold)assert(e.modeldata.thold==11);
  if(target==_cep_nolife)assert(e.modeldata.nolife==11);
  if(target==_cep_type)assert(e.modeldata.type==11);
  int returns_one=target==_cep_blockodds || target==_cep_escapecount || target==_cep_escapehits || target==_cep_health || target==_cep_score || target==_cep_thold;
  assert(out->lVal==returns_one);
  if(target!=_cep_type) {
   init_entity();values[2].vt=VT_DECIMAL;values[2].dblVal=27.75;result.vt=VT_EMPTY;out=&result;
   assert(openbor_changeentityproperty(args,&out,3)==S_OK && out && out->lVal==returns_one);
   entity before; s_model before_model;init_entity();memcpy(&before,&e,sizeof(e));memcpy(&before_model,&shared,sizeof(shared));
   values[2].vt=VT_EMPTY;result.vt=VT_EMPTY;out=&result;
   assert(openbor_changeentityproperty(args,&out,3)==S_OK && out && out->vt==VT_INTEGER && !out->lVal);
   assert(!memcmp(&before,&e,sizeof(e)) && !memcmp(&before_model,&shared,sizeof(shared)));
  }
 }
}
static void namespace_queries(int setter,const int *ids,int count,const char *const *names,int name_count,int animal) {
 for(int i=0;i<count;i++) {
  input(1,i,NULL,1,11,NULL);init_entity();
  if(setter)mapstrings_changeentityproperty(args,3);else mapstrings_getentityproperty(args,3);
  assert(values[1].vt==VT_INTEGER && values[1].lVal==i && (setter?set_id():get_id())==ids[i]);
  if(setter)setter_result(ids[i]);else getter_result(ids[i],animal);
 }
 for(int i=0;i<name_count && i<count;i++) {
  for(int pass=0;pass<3;pass++) {
   input(0,0,names[i],1,11,NULL);init_entity();
   for(int repeat=0;repeat<=pass;repeat++) {if(setter)mapstrings_changeentityproperty(args,3);else mapstrings_getentityproperty(args,3);}
   assert(values[1].vt==VT_INTEGER && values[1].lVal==i && (setter?set_id():get_id())==ids[i]);
   if(setter)setter_result(ids[i]);else getter_result(ids[i],animal);
  }
 }
 for(int i=0;i<3;i++) {
  int invalid[]={-1,count,2147483647};input(1,invalid[i],NULL,1,0,NULL);
  if(setter) {assert(set_id()==-1);assert(openbor_changeentityproperty(args,&out,3)==E_FAIL && !out);}
  else {assert(get_id()==-1);assert(openbor_getentityproperty(args,&out,3)==E_FAIL && !out);}
 }
}
static int has_name(const char *const *names,int count,const char *name) {for(int i=0;i<count;i++)if(!strcmp(names[i],name))return 1;return 0;}
static void unavailable(int setter,const char *const *own,int count,const char *const *physical,int nphysical,int property) {
 for(int i=0;i<nphysical;i++)if(!has_name(own,count,physical[i])) {
  input(property<0?0:1,property,physical[i],property<0?1:0,11,physical[i]);init_entity();
  if(setter)mapstrings_changeentityproperty(args,property<0?3:4);else mapstrings_getentityproperty(args,3);
  assert(values[property<0?1:2].vt==VT_STR);
  if(setter)assert(openbor_changeentityproperty(args,&out,property<0?3:4)==E_FAIL && !out);
  else assert(openbor_getentityproperty(args,&out,3)==E_FAIL);
 }
}
static void flags(int setter,int property,const int *ids,int count,const char *const *names,int name_count) {
 assert(property>=0 && count==name_count);
 for(int i=0;i<count;i++)for(int named=0;named<2;named++) {
  input(1,property,NULL,!named,i,names[i]);init_entity();
  if(setter)mapstrings_changeentityproperty(args,4);else mapstrings_getentityproperty(args,3);
  assert(values[2].vt==VT_INTEGER && values[2].lVal==i && (setter?set_flag():get_flag())==ids[i]);
  if(setter) {memset(&e,0,sizeof(e));assert(openbor_changeentityproperty(args,&out,4)==S_OK && out && out->vt==VT_INTEGER && !out->lVal);assert(written_flag(ids[i])==1);
   int sum=@FLAG_SUM@;assert(sum==1);}
  else {assert(openbor_getentityproperty(args,&out,3)==S_OK && out && out->vt==VT_INTEGER && out->lVal==(ids[i]==_gep_aiflag_pain_time?14:1));}
 }
 for(int i=0;i<2;i++) {
  input(1,property,NULL,1,i?-1:count,NULL);
  if(setter)assert(openbor_changeentityproperty(args,&out,4)==E_FAIL && !out);
  else assert(openbor_getentityproperty(args,&out,3)==E_FAIL);
 }
}
static void check(unsigned revision,int animal,int own_point_bits,int own_stealth_bits,
 const int *get,int ng,const char *const *gn,int ngn,const int *set,int ns,const char *const *sn,int nsn,
 const int *af,int na,const char *const *an,int nan,const int *sf,int nf,const char *const *fn,int nfn) {
 obor_profile_build=revision;
 point_bits=own_point_bits;stealth_bits=own_stealth_bits;
 antigrab_entity=ordinal(get,ng,_gep_antigrab)>=0;
 namespace_queries(0,get,ng,gn,ngn,animal);namespace_queries(1,set,ns,sn,nsn,animal);
 unavailable(0,gn,ngn,names_get3400,@NGET@,-1);unavailable(1,sn,nsn,names_change3400,@NSET@,-1);
 unavailable(0,an,nan,names_aiflag3400,@NAF@,ordinal(get,ng,_gep_aiflag));
 unavailable(1,fn,nfn,names_set_aiflag3400,@NSF@,ordinal(set,ns,_cep_aiflag));
 flags(0,ordinal(get,ng,_gep_aiflag),af,na,an,nan);flags(1,ordinal(set,ns,_cep_aiflag),sf,nf,fn,nfn);
 /* The original getter warns but uses the shared 32-bit union value after a failed name search. */
 int health=ordinal(get,ng,_gep_health);input(0,0,"unknown-property",1,0,NULL);cache[health]=(char*)"unknown-property";values[1].strVal=health;init_entity();
 assert(openbor_getentityproperty(args,&out,2)==S_OK && out && out->vt==VT_INTEGER && out->lVal==39);
 input(0,0,"unknown-property",1,11,NULL);assert(openbor_changeentityproperty(args,&out,3)==E_FAIL && !out);
 int maps=ordinal(get,ng,_gep_maps);
 if(maps>=0) {
  input(1,maps,NULL,1,0,NULL);assert(openbor_getentityproperty(args,&out,2)==E_FAIL);
  const char *sub[]={"count","current","dying","dying_critical","dying_low","frozen","hide_end","hide_start","ko","kotype","table","time"};
  const int val[]={3,2,18,19,20,21,22,23,24,25,0,26};
  for(int i=0;i<12;i++) {input(0,0,gn[maps],0,0,sub[i]);init_entity();assert(openbor_getentityproperty(args,&out,3)==S_OK && out);
   if(i==10)assert(out->vt==VT_PTR && out->ptrVal==e.colourmap);else assert(out->vt==VT_INTEGER && out->lVal==val[i]);}
 }
 input(1,maps,NULL,0,0,"default");if(maps>=0)assert(openbor_getentityproperty(args,&out,3)==E_FAIL);
 int think_id=ordinal(set,ns,_cep_think);
 if(think_id>=0) {
  const char *names[]={"common_think","player_think","steam_think","steamer_think","text_think","trap_think"};
  void (*expected[])(void)={common_think,player_think,steam_think,steamer_think,text_think,trap_think};
  for(int i=0;i<6;i++)for(int named=0;named<2;named++) {input(1,think_id,NULL,!named,i,names[i]);assert(openbor_changeentityproperty(args,&out,3)==S_OK && out && out->lVal==0 && e.think==expected[i]);}
  input(1,think_id,NULL,0,0,"unknown-think");e.think=common_think;assert(openbor_changeentityproperty(args,&out,3)==S_OK && out && !out->lVal && e.think==common_think);
  input(1,think_id,NULL,1,-1,NULL);e.think=common_think;assert(openbor_changeentityproperty(args,&out,3)==S_OK && out && !out->lVal && e.think==common_think);
  input(1,think_id,NULL,1,6,NULL);assert(openbor_changeentityproperty(args,&out,3)==S_OK && out && !out->lVal && e.think==common_think);
  input(1,think_id,NULL,1,0,NULL);values[2].vt=VT_EMPTY;assert(openbor_changeentityproperty(args,&out,3)==E_FAIL && !out);
 }
 int type_id=ordinal(set,ns,_cep_type);
 if(type_id>=0) {input(1,type_id,NULL,1,0,NULL);values[2].vt=VT_DECIMAL;values[2].dblVal=2.5;assert(openbor_changeentityproperty(args,&out,3)==E_FAIL && !out);
 }
}
int main(void) {assert(sizeof(LONG)==4 && sizeof(values[0].strVal)==4);@CHECKS@ puts("early_entity_namespaces=1");return 0;}
'''
        fields = re.findall(r'\b_cep_aiflag_(\w+)', enum_set.split('enum cep_aiflag_enum', 1)[1].split('};', 1)[0])
        self.assertEqual(fields.pop(), 'the_end')
        for key, value in dict(PIECES='\n'.join(pieces), ARRAYS='\n'.join(arrays), CHECKS='\n'.join(checks),
                               FLAG_FIELDS='\n'.join('case _cep_aiflag_' + field + ':return e.' + field + ';' for field in fields),
                               FLAG_SUM='+'.join('e.' + field for field in fields),
                               **{key: str(len(next(row for row in rows if row['revision'] == 3400)['namespaces'][kind]['names'])) for key, kind in [('NGET','get'),('NSET','change'),('NAF','aiflag'),('NSF','set_aiflag')]}).items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-entity-namespaces-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                     '-Dstricmp=strcasecmp', '-fcommon', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                     '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror', '-Wno-unused-variable',
                     '-Wno-unused-function', '-Wno-sign-compare', '-Wno-error=deprecated-declarations']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib', 'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)],
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20, env=sanitizer_environment())
            if os.environ.get('OBOR_ENTITY_NAMESPACE_OBSERVATIONS'):
                Path(os.environ['OBOR_ENTITY_NAMESPACE_OBSERVATIONS']).write_text(json.dumps({
                    'compiler': cc, 'flags': flags, 'contexts': len(rows), 'probe_sha256': hashlib.sha256(program.encode()).hexdigest(),
                    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                    'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr, 'scope': fixture['scope'],
                    'retirement': 'TemporaryDirectory removes source/binary'}, indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_entity_namespaces=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
