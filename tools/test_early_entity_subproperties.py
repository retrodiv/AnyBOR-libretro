"""Check own flash/icon/staydown forms, continuations and related value domains.

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
from test_early_entity_namespaces import namespace_descriptor, selected_dispatch
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-entity-subproperties.json'


class EarlyEntitySubpropertiesTests(unittest.TestCase):
    def test_forms_results_continuations_and_storage(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        edelay = load_contract_fixture(FIXTURE.with_name('profile-early-edelay-feedback.json'))
        edelay_rows = edelay['sources']
        edelay_revisions = {row['revision'] for row in edelay_rows}
        self.assertEqual(len(edelay_rows), len(edelay_revisions))
        self.assertTrue(set(edelay['boundary_controls']) <= edelay_revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        for profile in contract_profiles(edelay, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == edelay['engine'] and edelay['range'][0] <= revision <= edelay['range'][1]:
                self.assertIn(revision, edelay_revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openborscript.c').read_text()
        model = (engine / 'openbor.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        enum_get = source[source.index('enum getentityproperty_enum'):source.index('void mapstrings_getentityproperty(')]
        enum_set = source[source.index('enum changeentityproperty_enum'):source.index('void mapstrings_changeentityproperty(')]
        descriptor = namespace_descriptor(source, 'obor_property_namespace')
        macro = re.search(r'(?m)^#define MAPSTRINGS\([^\n]+(?:\n[^\n]*)*?\n}', source)
        self.assertIsNotNone(descriptor)
        self.assertIsNotNone(macro)
        pieces = [descriptor, '\n'.join('static const obor_property_namespace *' + name + '(void);' for name in [
            'obor_get_property_namespace', 'obor_set_property_namespace', 'obor_get_aiflag_namespace', 'obor_set_aiflag_namespace']),
            function(source, 'obor_property_index'), function(source, 'obor_icon_sprite_index'), function(source, 'obor_old_staydown'),
            enum_get, enum_set, function((engine / 'source/utils.c').read_text(), 'searchList'), macro[0],
            function(source, 'mapstrings_getentityproperty'), function(source, 'mapstrings_changeentityproperty')]
        pieces += [function(variant, name) for name in ['ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue']]
        pieces += [selected_dispatch(source, 'openbor_getentityproperty', ['_gep_' + x for x in ['flash', 'icon', 'staydown', 'gfxshadow', 'stealth', 'detect', 'edelay']]),
                   selected_dispatch(source, 'openbor_changeentityproperty', ['_cep_' + x for x in ['staydown', 'stealth', 'detect']])]
        loader = function(model, 'load_cached_model')
        start = loader.index('case CMD_MODEL_ICON:')
        icon_cases = loader[start:loader.index('case CMD_MODEL_PARROW:', start)]
        start = loader.index('case CMD_MODEL_STEALTH:')
        stealth_case = loader[start:loader.index('case CMD_MODEL_JUGGLEPOINTS:', start)]
        arrays, checks = [], []
        edelay_checks = []
        for row in edelay_rows:
            self.assertEqual(row['engine'], edelay['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIs(type(row['getter_id']), int)
            self.assertTrue(0 <= row['getter_id'] < 1024)
            self.assertIsInstance(row['diagnostic'], str)
            self.assertLess(len(row['diagnostic']), 4096)
            self.assertIs(type(row['branch_control']), bool)
            edelay_checks.append('check_edelay(%d,%d,%s,%d);' % (
                row['revision'], row['getter_id'], json.dumps(row['diagnostic']), row['branch_control']))
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            suffix = str(row['revision'])
            for key in ['flash_names', 'icon_names', 'staydown_names']:
                arrays.append('static const char *' + key + suffix + '[]={' + ','.join(map(json.dumps, row[key] or [''])) + '};')
            arrays.append('static const char *roots' + suffix + '[]={' + ','.join(map(json.dumps, row['root_names'])) + '};')
            checks.append('check(%d,%d,%d,%d,%d,%s,%s,%s,%s);' % (row['revision'], row['legacy_get'], row['positional_set'], row['icon_bits'], row['stealth_bits'],
                ','.join(map(str, [row['getter_ids'][key] for key in ['flash', 'icon', 'staydown', 'stealth', 'detect']] + [row['setter_ids'][key] for key in ['staydown', 'stealth', 'detect']])),
                'roots' + suffix, 'flash_names' + suffix + ',icon_names' + suffix + ',staydown_names' + suffix,
                ','.join(json.dumps(row['diagnostics'][key]) for key in ['flash', 'icon', 'staydown', 'set_staydown_type', 'set_staydown_unknown'])))
        program = r'''
#include <assert.h>
#include <ctype.h>
#include <math.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#include "commands.h"
#undef exit
#undef time
#undef kill
#undef pause
#undef shutdown
#undef printf
static char diagnostic[8192];
static int probe_printf(const char *format,...) {va_list ap;va_start(ap,format);int count=vsnprintf(diagnostic+strlen(diagnostic),sizeof(diagnostic)-strlen(diagnostic),format,ap);va_end(ap);assert(count>=0);return count;}
#define printf probe_printf
uint32_t obor_profile_build;
int sprite_map_max_items;
static char *cache[4096];
CHAR *StrCache_Get(int index) {assert(index>=0 && index<4096 && cache[index]);return cache[index];}
void StrCache_Collect(int index) {assert(index>=0 && index<4096);}
int StrCache_Pop(void) {abort();}
@PIECES@
@ARRAYS@
static ScriptVariant values[6],result,*args[6],*out;
static entity e;
static s_sprite sprites[13];
static int next_sprite;
int loadsprite(char *name,int x,int y,int format) {assert(!strcmp(name,"asset") && !x && !y && !format);return next_sprite;}
static void setup(int property,int value,int fourth) {
 memset(values,0,sizeof(values));memset(&result,0,sizeof(result));memset(&e,0,sizeof(e));
 for(int i=0;i<6;i++) {args[i]=&values[i];values[i].vt=VT_INTEGER;}
 values[0].vt=VT_PTR;values[0].ptrVal=&e;values[1].lVal=property;values[2].lVal=value;values[3].lVal=fourth;out=&result;diagnostic[0]=0;
 e.modeldata.flash=21;e.modeldata.noatflash=22;e.modeldata.bflash=23;
 e.modeldata.icon.def=0;e.modeldata.icon.die=1;e.modeldata.icon.get=2;e.modeldata.icon.mphigh=3;e.modeldata.icon.mpmed=4;e.modeldata.icon.mplow=5;
 e.modeldata.icon.pain=6;e.modeldata.icon.weapon=7;e.modeldata.icon.x=8;e.modeldata.icon.y=9;
 e.staydown.rise=5;e.staydown.riseattack=6;e.staydown.riseattack_stall=7;e.modeldata.gfxshadow=97;e.modeldata.stealth.hide=8;e.modeldata.stealth.detect=9;
}
static void text(int at,const char *value) {cache[1000+at]=(char*)value;values[at].vt=VT_STR;values[at].strVal=1000+at;}
static int original_icon(int value,int bits) {return bits==32?value:(short)value;}
static int original_stealth(int value,int bits) {return bits==16?(short)value:(signed char)value;}
/* Duplicate-icon loading is outside these successful-value checks. */
static char *unexpected_model_error(const char *old,const char *modern,...) {
 (void)old;(void)modern;abort();
}
#define OBOR_MODEL_ERROR unexpected_model_error
#define GET_ARG(index) ((char *)"asset")
#define GET_INT_ARG(index) input[index]
static void model_line(int cmd,int value) {
 s_model *newchar=&e.modeldata;char *value_name=NULL,*shutdownmessage=NULL;char *filename="fixture";int pixelformat=0,input[]={0,value,value};
 /* The source cases call their filename variable value. */
 (void)value_name;
 switch(cmd) {@ICON_CASES@ @STEALTH_CASE@ default:abort();}
 return;
lCleanup:assert(shutdownmessage);abort();
}
#undef GET_ARG
#undef GET_INT_ARG
#undef OBOR_MODEL_ERROR
static void icon_result(int index) {
 assert(openbor_getentityproperty(args,&out,3)==S_OK && out);
 if(index<0)assert(out->vt==VT_INTEGER && out->lVal==-1);
 else {assert(out->vt==VT_PTR && out->ptrVal==sprite_map[index].sprite);
  assert(sprite_map[index].sprite->centerx==sprite_map[index].centerx && sprite_map[index].sprite->centery==sprite_map[index].centery);}
}
static void check(unsigned revision,int old,int positional,int icon_bits,int stealth_bits,int flash,int icon,int stay,int stealth,int detect,int setstay,int setstealth,int setdetect,
 const char *const *roots,const char *const *flash_names,const char *const *icon_names,const char *const *stay_names,const char *flash_diag,const char *icon_diag,const char *stay_diag,const char *set_diag,const char *set_unknown) {
 obor_profile_build=revision;
 for(int selector=-1;selector<=3;selector++) {
  setup(flash,selector,0);HRESULT hr=openbor_getentityproperty(args,&out,3);
  if(!old && (selector<0 || selector>=3))assert(hr==E_FAIL && out && out->vt==VT_EMPTY);
  else {const int before[]={21,22,23},after[]={23,21,22};int i=old?(selector==1?1:selector==2?2:0):selector;
   assert(hr==S_OK && out && out->vt==VT_INTEGER && out->lVal==(old?before[i]:after[i]));}
 }
 for(int i=0;i<3;i++)if(!old) {setup(flash,0,0);text(1,roots[0]);text(2,flash_names[i]);mapstrings_getentityproperty(args,3);mapstrings_getentityproperty(args,3);
  const int expected[]={23,21,22};assert(openbor_getentityproperty(args,&out,3)==S_OK && out && out->lVal==expected[i]);}
 setup(flash,0,0);values[2].vt=VT_EMPTY;assert(openbor_getentityproperty(args,&out,3)==E_FAIL && !strcmp(diagnostic,flash_diag));
 setup(flash,0,0);assert(openbor_getentityproperty(args,&out,2)==E_FAIL);
 for(int selector=-1;selector<=10;selector++) {
  setup(icon,selector,0);int index=selector;
  if(old && (selector<0 || selector>9))index=0;
  else if(!old && selector==4)index=5;else if(!old && selector==5)index=4;
  if(!old && (selector<0 || selector>9))assert(openbor_getentityproperty(args,&out,3)==E_FAIL);
  else icon_result(index);
 }
 if(!old)for(int i=0;i<10;i++) {setup(icon,0,0);text(1,roots[1]);text(2,icon_names[i]);mapstrings_getentityproperty(args,3);mapstrings_getentityproperty(args,3);icon_result(i==4?5:i==5?4:i);}
 setup(icon,0,0);values[2].vt=VT_EMPTY;assert(openbor_getentityproperty(args,&out,3)==E_FAIL && !strcmp(diagnostic,icon_diag));
 setup(icon,0,0);assert(openbor_getentityproperty(args,&out,2)==S_OK && out && out->vt==VT_EMPTY);
 const int large[]={32767,32768,40000,-1};
 for(int at=0;at<4;at++) {setup(icon,old?0:_gep_icon_def,0);e.modeldata.icon.def=-1;next_sprite=large[at];model_line(CMD_MODEL_ICON,large[at]);int expected=original_icon(large[at],icon_bits);
  assert(e.modeldata.icon.def==expected && e.modeldata.icon.pain==expected && e.modeldata.icon.die==expected && e.modeldata.icon.get==expected);icon_result(expected);}
 setup(icon,0,0);e.modeldata.icon.def=sprite_map_max_items;assert(openbor_getentityproperty(args,&out,3)==E_FAIL && out && out->vt==VT_EMPTY);
 setup(icon,0,0);s_sprite_map *saved=sprite_map;sprite_map=NULL;assert(openbor_getentityproperty(args,&out,3)==E_FAIL);sprite_map=saved;
 setup(icon,0,0);s_sprite *saved_sprite=sprite_map[0].sprite;sprite_map[0].sprite=NULL;assert(openbor_getentityproperty(args,&out,3)==E_FAIL);sprite_map[0].sprite=saved_sprite;
 for(int selector=0;selector<3;selector++) {
  setup(stay,selector,selector);HRESULT hr=openbor_getentityproperty(args,&out,old?4:3);
  if(!old && positional && selector==2)assert(hr==E_FAIL);
  else assert(hr==S_OK && out && out->vt==VT_INTEGER && out->lVal==(old?97:selector+5));
 }
 if(!old)for(int i=0;i<(positional?2:3);i++) {setup(stay,0,0);text(1,roots[2]);text(2,stay_names[i]);mapstrings_getentityproperty(args,3);mapstrings_getentityproperty(args,3);assert(openbor_getentityproperty(args,&out,3)==S_OK && out && out->lVal==i+5);}
 setup(stay,0,0);values[old?3:2].vt=VT_EMPTY;assert(openbor_getentityproperty(args,&out,old?4:3)==E_FAIL && !strcmp(diagnostic,stay_diag));
 setup(stay,0,-1);if(old)assert(openbor_getentityproperty(args,&out,4)==E_FAIL);
 setup(stay,0,0);assert(openbor_getentityproperty(args,&out,old?3:2)==S_OK && out && out->vt==VT_EMPTY);
 if(positional) {
  for(int mask=0;mask<4;mask++) {setup(setstay,11,12);if(!(mask&1))values[2].vt=VT_EMPTY;if(!(mask&2))values[3].vt=VT_EMPTY;
   assert(openbor_changeentityproperty(args,&out,4)==S_OK && out && out->vt==VT_INTEGER && out->lVal==(mask&1?1:0));
   assert(e.staydown.rise==(mask&1?11:5) && e.staydown.riseattack==(mask==3?12:6) && e.staydown.riseattack_stall==7 && e.modeldata.stealth.hide==(mask&1?11:8));}
  setup(setstay,11,12);assert(openbor_changeentityproperty(args,&out,3)==S_OK && out && out->lVal==1 && e.staydown.rise==11 && e.staydown.riseattack==6 && e.modeldata.stealth.hide==11);
  setup(setstay,0,12);text(2,"rise");assert(openbor_changeentityproperty(args,&out,4)==S_OK && out && !out->lVal && e.staydown.rise==5 && e.modeldata.stealth.hide==8);
 } else {
  const char *names[]={"rise","riseattack","riseattack_stall"};
  for(int i=0;i<3;i++) {setup(setstay,i,11);text(2,names[i]);assert(openbor_changeentityproperty(args,&out,4)==S_OK && out && !out->lVal);assert(e.staydown.rise==(i==0?11:5) && e.staydown.riseattack==(i==1?11:6) && e.staydown.riseattack_stall==(i==2?11:7) && e.modeldata.stealth.hide==8);}
  setup(setstay,0,11);assert(openbor_changeentityproperty(args,&out,3)==S_OK && out && !out->lVal && e.staydown.rise==5);
  setup(setstay,-1,11);assert(openbor_changeentityproperty(args,&out,4)==E_FAIL && !out && !strcmp(diagnostic,set_unknown));
 }
 setup(setstay,0,11);values[2].vt=VT_EMPTY;HRESULT typed_set=openbor_changeentityproperty(args,&out,4);
 if(positional)assert(typed_set==S_OK && out && !out->lVal && !diagnostic[0]);else assert(typed_set==E_FAIL && !out && !strcmp(diagnostic,set_diag));
 const int value_set[]={-2147483648,-32769,-32768,-129,-128,-1,0,127,128,255,256,32767,32768,2147483647};
 const int icon_cmd[]={CMD_MODEL_ICONPAIN,CMD_MODEL_ICONDIE,CMD_MODEL_ICONGET,CMD_MODEL_ICONW,CMD_MODEL_ICONMPHIGH,CMD_MODEL_ICONMPHALF,CMD_MODEL_ICONMPLOW};
 for(size_t at=0;at<sizeof(value_set)/sizeof(value_set[0]);at++) {
  int v=value_set[at],iv=original_icon(v,icon_bits),sv=original_stealth(v,stealth_bits);setup(setstay,positional?v:0,v);
  assert(openbor_changeentityproperty(args,&out,4)==S_OK && out && out->lVal==(positional?1:0) && e.staydown.rise==v && e.modeldata.stealth.hide==(positional?sv:8));
  unsigned int original[3]={(unsigned int)v,0,0};assert(sizeof(original)==sizeof(e.staydown));assert(!memcmp(original,&e.staydown.rise,sizeof(original[0])));
  for(int selector=0;selector<(old?3:positional?2:3);selector++) {setup(stay,selector,selector);e.staydown.rise=v;e.staydown.riseattack=v;e.staydown.riseattack_stall=v;int original_read=(int)(unsigned int)v;assert(openbor_getentityproperty(args,&out,old?4:3)==S_OK && out && out->lVal==(old?97:original_read));}
  setup(setstealth,v,0);assert(openbor_changeentityproperty(args,&out,3)==S_OK && out && !out->lVal && e.modeldata.stealth.hide==sv);
  values[1].lVal=stealth;assert(openbor_getentityproperty(args,&out,2)==S_OK && out && out->lVal==sv);
  setup(setdetect,v,0);assert(openbor_changeentityproperty(args,&out,3)==S_OK && out && !out->lVal && e.modeldata.stealth.detect==sv);
  values[1].lVal=detect;assert(openbor_getentityproperty(args,&out,2)==S_OK && out && out->lVal==sv);
  setup(stay,0,0);model_line(CMD_MODEL_STEALTH,v);assert(e.modeldata.stealth.hide==sv && e.modeldata.stealth.detect==sv);
  for(int i=0;i<7;i++) {setup(icon,0,0);next_sprite=v;model_line(icon_cmd[i],v);
   const int actual[]={e.modeldata.icon.pain,e.modeldata.icon.die,e.modeldata.icon.get,e.modeldata.icon.weapon,e.modeldata.icon.mphigh,e.modeldata.icon.mpmed,e.modeldata.icon.mplow};assert(actual[i]==iv);}

 }
}
static void check_edelay(unsigned revision,int property,const char *expected,int branch_control) {
 obor_profile_build=revision;
 /* Unselectable boundary revisions have no registered namespace: enter the
  * actual branch through the physical selector, without inventing a profile. */
 if(branch_control) {assert(!obor_get_property_namespace());property=_gep_edelay;}
 const int selectors[]={_gep_edelay_cap_max,_gep_edelay_cap_min,_gep_edelay_factor,
                        _gep_edelay_mode,_gep_edelay_range_max,_gep_edelay_range_min};
 for(int at=0;at<6;++at) {
  setup(property,selectors[at],0);
  e.modeldata.edelay.cap_max=12;e.modeldata.edelay.cap_min=-13;e.modeldata.edelay.factor=1.25f;
  e.modeldata.edelay.mode=14;e.modeldata.edelay.range_max=15;e.modeldata.edelay.range_min=-16;
  HRESULT hr=openbor_getentityproperty(args,&out,3);
  if(hr!=S_OK || !out || out->vt!=VT_INTEGER || diagnostic[0])
   fprintf(stderr,"edelay revision=%u property=%d selector=%d hr=%d tag=%d diagnostic=%s\n",revision,property,selectors[at],hr,out?(int)out->vt:-1,diagnostic);
  assert(hr==S_OK && out && out->vt==VT_INTEGER && !diagnostic[0]);
  /* Retain the original factor result's integer tag and double union member. */
  if(at==2)assert(out->dblVal==1.25);
  else {const int values[]={12,-13,0,14,15,-16};assert(out->lVal==values[at]);}
 }
 const int invalid_types[]={VT_EMPTY,VT_DECIMAL,VT_PTR};
 for(unsigned i=0;i<sizeof(invalid_types)/sizeof(*invalid_types);++i) {
  setup(property,0,0);values[2].vt=invalid_types[i];
  assert(openbor_getentityproperty(args,&out,3)==E_FAIL && out && out->vt==VT_EMPTY);
  assert(!strcmp(diagnostic,expected));
 }
 setup(property,0,0);text(2,"mode");e.modeldata.edelay.mode=29;
 assert(openbor_getentityproperty(args,&out,3)==S_OK && out && out->vt==VT_INTEGER && out->lVal==29 && !diagnostic[0]);
}
int main(void) {
 assert(sizeof(int)==4 && sizeof(unsigned int)==4 && sizeof(short)==2 && CHAR_BIT==8);
 sprite_map_max_items=40001;sprite_map=calloc((size_t)sprite_map_max_items,sizeof(*sprite_map));assert(sprite_map);
 for(int i=0;i<13;i++) {int index=i<10?i:i==10?32767:i==11?32768:40000;sprite_map[index].sprite=&sprites[i];sprite_map[index].centerx=30+i;sprite_map[index].centery=-20-i;}
 @CHECKS@
 @EDELAY_CHECKS@
 free(sprite_map);sprite_map=NULL;puts("early_entity_subproperties=1");return 0;
}
'''
        # Keep the actual loader's filename variable without shadowing the numeric provider.
        icon_cases = icon_cases.replace('value = GET_ARG(1);', 'value_name = GET_ARG(1);').replace('loadsprite(value,', 'loadsprite(value_name,')
        for key, value in dict(PIECES='\n'.join(pieces), ARRAYS='\n'.join(arrays), CHECKS='\n'.join(checks),
                               EDELAY_CHECKS='\n'.join(edelay_checks),
                               ICON_CASES=icon_cases, STEALTH_CASE=stealth_case).items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-entity-subproperties-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1', '-Dstricmp=strcasecmp',
                     '-fcommon', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                     '-Wall', '-Wextra', '-Werror', '-Wno-unused-variable', '-Wno-unused-function', '-Wno-sign-compare',
                     '-Wno-misleading-indentation', '-Wno-error=deprecated-declarations']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib', 'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)],
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20, env=sanitizer_environment())
            if os.environ.get('OBOR_SUBPROPERTY_OBSERVATIONS'):
                Path(os.environ['OBOR_SUBPROPERTY_OBSERVATIONS']).write_text(json.dumps({
                    'compiler': cc, 'flags': flags, 'contexts': len(rows), 'edelay_contexts': len(edelay_rows),
                    'edelay_cases_per_context': 10, 'probe_sha256': hashlib.sha256(program.encode()).hexdigest(),
                    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                    'header_sha256': hashlib.sha256((engine / 'openbor.h').read_bytes()).hexdigest(),
                    'model_source_sha256': hashlib.sha256(model.encode()).hexdigest(), 'returncode': run.returncode,
                    'stdout': run.stdout, 'stderr': run.stderr, 'scope': fixture['scope'], 'retirement': 'TemporaryDirectory removes source/binary'}, indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_entity_subproperties=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
