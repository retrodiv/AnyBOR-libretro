"""Check own DOT getter results, continuation and argument handling.

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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-dot.json'


class EarlyDotTests(unittest.TestCase):
    def test_getter_results_and_continuation(self):
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
        pieces += [selected_dispatch(source, 'openbor_getentityproperty', ['_gep_dot', '_gep_dropframe'])]
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertEqual(row['max_dots'], 10)
            self.assertRegex(row['error_c'], r'^"(?:[^"\\]|\\.)*"$')
            checks.append('check(%d,%d,%d,%d,%s,%s);' % (row['revision'], row['modern'], row['getter_id'], row['dropframe_id'],
                json.dumps(row['getter_literal']), row['error_c']))
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
int StrCache_Pop(void){abort();}
static int probe_printf(const char *format,...){va_list ap;va_start(ap,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,ap);va_end(ap);return n;}
#define printf probe_printf
@PIECES@

static entity ent,owner;
static s_anim animations[2],*animptrs[2];
static ScriptVariant values[4],result,*args[4],*out;
static void setup(int property,int index,int selector){
 memset(values,0,sizeof(values));memset(&result,0,sizeof(result));memset(&ent,0,sizeof(ent));memset(animations,0,sizeof(animations));
 for(int i=0;i<4;i++){args[i]=&values[i];values[i].vt=VT_INTEGER;}
 values[0].vt=VT_PTR;values[0].ptrVal=&ent;values[1].lVal=property;values[2].lVal=index;values[3].lVal=selector;out=&result;diagnostic[0]=0;
 ent.modeldata.blockback=5;ent.modeldata.animation=animptrs;ent.modeldata.animation_capacity=2;
 for(int i=0;i<2;i++){animptrs[i]=&animations[i];animations[i].dropframe=17+12*i;}
 for(int i=0;i<MAX_DOTS;i++){ent.dot_time[i]=100+i;ent.dot[i]=-20-i;ent.dot_force[i]=30+i;ent.dot_rate[i]=40+i;ent.dot_atk[i]=50+i;ent.dot_owner[i]=i%2?&owner:NULL;}
}
static void text(int at,const char *s){strcpy(cache[700+at],s);values[at].vt=VT_STR;values[at].strVal=700+at;}
static void result_for(int modern,int index,int selector,int count,int blockback){
 assert(openbor_getentityproperty(args,&out,count)==S_OK && out);
 assert(ent.modeldata.blockback==blockback);
 if(modern){assert(out->vt==VT_INTEGER && out->lVal==17);return;}
 if(selector==_gep_dot_owner){assert(out->vt==VT_PTR && out->ptrVal==ent.dot_owner[index]);return;}
 LONG want=0;
 switch(selector){case _gep_dot_force:want=ent.dot_force[index];break;case _gep_dot_mode:want=ent.dot[index];break;
 case _gep_dot_rate:want=ent.dot_rate[index];break;case _gep_dot_time:want=ent.dot_time[index];break;case _gep_dot_type:want=ent.dot_atk[index];break;default:abort();}
 assert(out->vt==VT_INTEGER && out->lVal==want);
}
static void check(unsigned revision,int modern,int getid,int dropid,const char *getname,const char *error){
 obor_profile_build=revision;
 for(int count=2;count<4;count++){setup(getid,1,0);args[count]=NULL;assert(openbor_getentityproperty(args,&out,count)==S_OK && out && out->vt==VT_EMPTY && ent.modeldata.blockback==5);}
 for(int selector=0;selector<_gep_dot_the_end;selector++)for(int index=0;index<MAX_DOTS;index++){
  setup(getid,index,selector);result_for(modern,index,selector,4,modern?5:index);
 }
 const char *names[]={"force","mode","owner","rate","time","type"};
 for(int mapped=0;mapped<_gep_dot_the_end;mapped++){
  setup(getid,0,_gep_dot_type);text(1,getname);text(2,names[mapped]);
  mapstrings_getentityproperty(args,4);mapstrings_getentityproperty(args,4);
  assert(values[2].vt==VT_INTEGER && values[2].lVal==mapped);
  result_for(modern,mapped,_gep_dot_type,4,modern?5:mapped);
 }
 setup(getid,0,_gep_dot_force);values[2].vt=VT_EMPTY;result_for(modern,0,_gep_dot_force,4,5);
 setup(getid,0,_gep_dot_force);values[2].vt=VT_DECIMAL;values[2].dblVal=2.75;result_for(modern,2,_gep_dot_force,4,modern?5:2);
 setup(getid,0,0);values[3].vt=VT_EMPTY;
 assert(openbor_getentityproperty(args,&out,4)==E_FAIL && out && out->vt==VT_EMPTY && !strcmp(diagnostic,error) && ent.modeldata.blockback==5);
 setup(getid,0,0);text(3,"force");assert(openbor_getentityproperty(args,&out,4)==E_FAIL && out && out->vt==VT_EMPTY && !diagnostic[0]);
 for(int selector=-1;selector<=_gep_dot_the_end;selector+=_gep_dot_the_end+1){
  setup(getid,-1,selector);assert(openbor_getentityproperty(args,&out,4)==S_OK && out);
  assert(modern?(out->vt==VT_INTEGER && out->lVal==17 && ent.modeldata.blockback==5):(out->vt==VT_EMPTY && ent.modeldata.blockback==-1));
 }
 for(int selector=0;selector<_gep_dot_the_end;selector++)for(int side=0;side<2;side++){
  setup(getid,side?MAX_DOTS:-1,selector);assert(openbor_getentityproperty(args,&out,4)==E_FAIL && out && out->vt==VT_EMPTY && ent.modeldata.blockback==5);
 }
 setup(getid,0,_gep_dot_force);ent.modeldata.animation=NULL;ent.modeldata.animation_capacity=0;
 if(modern)assert(openbor_getentityproperty(args,&out,4)==E_FAIL && out);else result_for(0,0,_gep_dot_force,4,0);
 for(int count=2;count<=4;count++)for(int which=0;which<2;which++){
  setup(dropid,which,0);if(count==2)args[2]=NULL;
  assert(openbor_getentityproperty(args,&out,count)==S_OK && out && out->vt==VT_INTEGER && out->lVal==(count==3?17+12*which:17));
 }
 for(int bad=-1;bad<=2;bad+=3){setup(dropid,bad,0);assert(openbor_getentityproperty(args,&out,3)==E_FAIL && out && out->vt==VT_EMPTY);}
 setup(dropid,0,0);animptrs[0]=NULL;assert(openbor_getentityproperty(args,&out,2)==E_FAIL && out);
}
int main(void){@CHECKS@ puts("early_dot=1");return 0;}

'''
        program = program.replace('@PIECES@', '\n'.join(pieces)).replace('@CHECKS@', '\n'.join(checks))
        with tempfile.TemporaryDirectory(prefix='early-dot-') as name:
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
            if os.environ.get('OBOR_DOT_OBSERVATIONS'):
                Path(os.environ['OBOR_DOT_OBSERVATIONS']).write_text(json.dumps(dict(compiler=cc,flags=flags,
                    contexts=len(rows),probe_sha256=hashlib.sha256(program.encode()).hexdigest(),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),returncode=run.returncode,stdout=run.stdout,stderr=run.stderr,
                    scope=fixture['scope'],retirement='TemporaryDirectory removes source/binary'),indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_dot=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
