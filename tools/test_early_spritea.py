"""Check own spritea availability and valid metadata operations.

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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-spritea.json'


class EarlySpriteaTests(unittest.TestCase):
    def test_availability_and_valid_results(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openborscript.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        macro = re.search(r'(?m)^#define MAPSTRINGS\([^\n]+(?:\n[^\n]*)*?\n}', source)
        self.assertIsNotNone(macro)
        pieces = [namespace_descriptor(source, 'obor_property_namespace'),
                  '\n'.join('static const obor_property_namespace *' + name + '(void);' for name in [
                      'obor_get_property_namespace', 'obor_set_property_namespace', 'obor_get_aiflag_namespace', 'obor_set_aiflag_namespace']),
                  function(source, 'obor_property_index'),
                  source[source.index('enum getentityproperty_enum'):source.index('void mapstrings_getentityproperty(')],
                  source[source.index('enum changeentityproperty_enum'):source.index('void mapstrings_changeentityproperty(')],
                  function((engine / 'source/utils.c').read_text(), 'searchList'), macro[0],
                  function(source, 'mapstrings_getentityproperty'), function(source, 'mapstrings_changeentityproperty')]
        pieces += [function(variant, name) for name in ['ScriptVariant_ChangeType', 'ScriptVariant_Clear',
                                                       'ScriptVariant_DecimalValue', 'ScriptVariant_IntegerValue']]
        pieces += [selected_dispatch(source, 'openbor_getentityproperty', ['_gep_spritea']),
                   selected_dispatch(source, 'openbor_changeentityproperty', ['_cep_spritea'])]
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['set_error_c'], r'^"(?:[^"\\]|\\.)*"$')
            checks.append('check(%d,%d,%d,%d,%s,%s,%s);' % (row['revision'], row['present'], row['getter_id'], row['setter_id'],
                json.dumps(row['getter_literal']), json.dumps(row['setter_literal']), row['set_error_c']))
        program = r'''
#include <assert.h>
#include <ctype.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
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
static char diagnostic[4096],cache[1024][128];
CHAR *StrCache_Get(int index){assert(index>=0 && index<1024);return cache[index];}
void StrCache_Collect(int index){(void)index;}
int StrCache_Pop(void){return 900;}
static int probe_printf(const char *format,...){va_list ap;va_start(ap,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,ap);va_end(ap);return n;}
#define printf probe_printf
@PIECES@

static entity ent;
static s_anim animation,*animptrs[1];
static s_sprite sprites[2];
static s_sprite_map entries[2];
static int frame_indices[2];
static char filename[8];
static ScriptVariant values[6],result,*args[6],*out;
static void setup(int property,int selector){
 memset(values,0,sizeof(values));memset(&result,0,sizeof(result));memset(&ent,0,sizeof(ent));memset(&animation,0,sizeof(animation));memset(entries,0,sizeof(entries));memset(sprites,0,sizeof(sprites));
 for(int i=0;i<6;i++){args[i]=&values[i];values[i].vt=VT_INTEGER;}
 values[0].vt=VT_PTR;values[0].ptrVal=&ent;values[1].lVal=property;values[2].lVal=selector;values[3].lVal=0;values[4].lVal=1;values[5].lVal=71;out=&result;diagnostic[0]=0;
 ent.modeldata.animation=animptrs;ent.modeldata.animation_capacity=1;animptrs[0]=&animation;animation.numframes=2;animation.sprite=frame_indices;frame_indices[0]=0;frame_indices[1]=1;
 sprite_map=entries;strcpy(filename,"old.bmp");
 for(int i=0;i<2;i++){entries[i].filename=filename;entries[i].centerx=11+i;entries[i].centery=21+i;entries[i].ofsx=31+i;entries[i].ofsy=41+i;entries[i].sprite=&sprites[i];}
}
static void text(int at,const char *value){strcpy(cache[700+at],value);values[at].vt=VT_STR;values[at].strVal=700+at;}
static void getter_result(int selector){
 assert(openbor_getentityproperty(args,&out,5)==S_OK && out);
 switch(selector){
 case _gep_spritea_centerx:assert(out->vt==VT_INTEGER && out->lVal==12);break;
 case _gep_spritea_centery:assert(out->vt==VT_INTEGER && out->lVal==22);break;
 case _gep_spritea_file:assert(out->vt==VT_STR && !strcmp(StrCache_Get(out->strVal),"old.bmp"));break;
 case _gep_spritea_offsetx:assert(out->vt==VT_INTEGER && out->lVal==32);break;
 case _gep_spritea_offsety:assert(out->vt==VT_INTEGER && out->lVal==42);break;
 case _gep_spritea_sprite:assert(out->vt==VT_PTR && out->ptrVal==&sprites[1] && sprites[1].centerx==22 && sprites[1].centery==22);break;
 default:abort();
 }
}
static void check(unsigned revision,int present,int getid,int setid,const char *getname,const char *setname,const char *seterror){
 obor_profile_build=revision;
 if(!present){
  setup(0,0);text(1,"spritea");assert(openbor_getentityproperty(args,&out,5)==E_FAIL && !out);
  setup(0,0);text(1,"spritea");assert(openbor_changeentityproperty(args,&out,6)==E_FAIL && !out);
  return;
 }
 const char *names[]={"centerx","centery","file","offsetx","offsety","sprite"};
 for(int selector=0;selector<6;selector++)for(int named=0;named<2;named++){
  setup(getid,selector);if(named){text(1,getname);text(2,names[selector]);mapstrings_getentityproperty(args,5);mapstrings_getentityproperty(args,5);assert(values[2].vt==VT_INTEGER && values[2].lVal==selector);}getter_result(selector);
  setup(setid,selector);
  if(selector==_cep_spritea_file)text(5,"new");
  if(selector==_cep_spritea_sprite){values[5].vt=VT_PTR;values[5].ptrVal=&sprites[0];}
  if(named){text(1,setname);text(2,names[selector]);mapstrings_changeentityproperty(args,6);mapstrings_changeentityproperty(args,6);assert(values[2].vt==VT_INTEGER && values[2].lVal==selector);}
  assert(openbor_changeentityproperty(args,&out,6)==S_OK && out && out->vt==VT_INTEGER && out->lVal==1);
  switch(selector){
  case _cep_spritea_centerx:assert(entries[1].centerx==71 && entries[0].centerx==11);break;
  case _cep_spritea_centery:assert(entries[1].centery==71);break;
  case _cep_spritea_file:assert(!strcmp(entries[1].filename,"new") && entries[0].filename==entries[1].filename && !strcmp(entries[0].filename,"new"));break;
  case _cep_spritea_offsetx:assert(entries[1].ofsx==71);break;
  case _cep_spritea_offsety:assert(entries[1].ofsy==selector);break;
  case _cep_spritea_sprite:assert(entries[1].sprite==&sprites[0]);break;
  }
 }
 setup(getid,_gep_spritea_centerx);entries[1].sprite=NULL;getter_result(_gep_spritea_centerx);
 setup(getid,6);assert(openbor_getentityproperty(args,&out,5)==E_FAIL && out && out->vt==VT_EMPTY);
 setup(setid,6);assert(openbor_changeentityproperty(args,&out,6)==E_FAIL && !out && !strcmp(diagnostic,"Unknown Sprite Array subproperty.\n"));
 setup(setid,0);values[2].vt=VT_EMPTY;assert(openbor_changeentityproperty(args,&out,6)==E_FAIL && !out && !strcmp(diagnostic,seterror));
 setup(setid,_cep_spritea_file);assert(openbor_changeentityproperty(args,&out,6)==E_FAIL && !out && !strcmp(diagnostic,"You must provide a string value for file name.\n"));
 for(int selector=0;selector<6;selector++)if(selector==0 || selector==1 || selector==3 || selector==4){
  setup(setid,selector);values[5].vt=VT_EMPTY;assert(openbor_changeentityproperty(args,&out,6)==S_OK && out && out->vt==VT_INTEGER && out->lVal==(selector==4));
  if(selector==4)assert(entries[1].ofsy==4);else assert(entries[1].centerx==12 && entries[1].centery==22 && entries[1].ofsx==32);
 }
}
int main(void){@CHECKS@ puts("early_spritea=1");return 0;}

'''
        program = program.replace('@PIECES@', '\n'.join(pieces)).replace('@CHECKS@', '\n'.join(checks))
        with tempfile.TemporaryDirectory(prefix='early-spritea-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1', '-Dstricmp=strcasecmp',
                     '-fcommon', '-fsigned-char', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                     '-Wall', '-Wextra', '-Werror', '-Wno-unused-variable', '-Wno-unused-function', '-Wno-sign-compare',
                     '-Wno-misleading-indentation', '-Wno-implicit-fallthrough', '-Wno-error=deprecated-declarations']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib', 'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20, env=sanitizer_environment())
            if os.environ.get('OBOR_SPRITEA_OBSERVATIONS'):
                Path(os.environ['OBOR_SPRITEA_OBSERVATIONS']).write_text(json.dumps(dict(compiler=cc,flags=flags,
                    contexts=len(rows),probe_sha256=hashlib.sha256(program.encode()).hexdigest(),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),returncode=run.returncode,stdout=run.stdout,stderr=run.stderr,
                    scope=fixture['scope'],retirement='TemporaryDirectory removes source/binary'),indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_spritea=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
