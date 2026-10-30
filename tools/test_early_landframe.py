"""Check own landframe getter signatures and argument handling.

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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-landframe.json'


class EarlyLandframeTests(unittest.TestCase):
    def test_getter_signatures(self):
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
        pieces += [selected_dispatch(source, 'openbor_getentityproperty', ['_gep_landframe'])]
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertEqual(row['frame_width'], 16)
            self.assertEqual(row['entity_width'], 32 if row['modern'] else 16)
            self.assertRegex(row['error_c'], r'^"(?:[^"\\]|\\.)*"$')
            checks.append('check(%d,%d,%d,%s,%s);' % (row['revision'], row['modern'], row['getter_id'],
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


static entity ent;
static s_anim animations[2],*animptrs[2];
static ScriptVariant values[4],result,*args[4],*out;
static void setup(int property,int selector,int index){
 memset(values,0,sizeof(values));memset(&result,0,sizeof(result));memset(&ent,0,sizeof(ent));memset(animations,0,sizeof(animations));
 for(int i=0;i<4;i++){args[i]=&values[i];values[i].vt=VT_INTEGER;}
 values[0].vt=VT_PTR;values[0].ptrVal=&ent;values[1].lVal=property;values[2].lVal=selector;values[3].lVal=index;out=&result;diagnostic[0]=0;
 ent.modeldata.animation=animptrs;ent.modeldata.animation_capacity=2;
 for(int i=0;i<2;i++){animptrs[i]=&animations[i];animations[i].numframes=1;animations[i].landframe.frame=i?23:-7;animations[i].landframe.ent=40001+i;}
}
static void text(int at,const char *s){strcpy(cache[700+at],s);values[at].vt=VT_STR;values[at].strVal=700+at;}
static void integer_result(int count,int value){assert(openbor_getentityproperty(args,&out,count)==S_OK && out && out->vt==VT_INTEGER && out->lVal==value);}
static void empty_result(int count){assert(openbor_getentityproperty(args,&out,count)==S_OK && out && out->vt==VT_EMPTY);}
static void check(unsigned revision,int modern,int getid,const char *getname,const char *error){
 obor_profile_build=revision;
 setup(getid,0,1);args[2]=NULL;if(modern)empty_result(2);else integer_result(2,-7);
 setup(getid,1,1);args[3]=NULL;if(modern)empty_result(3);else integer_result(3,23);
 for(int index=0;index<2;index++)for(int selector=0;selector<2;selector++){
  setup(getid,selector,index);
  integer_result(4,modern?(selector==_gep_landframe_ent?40001+index:(index?23:-7)):-7);
 }
 const char *names[]={"ent","frame"};
 for(int selector=0;selector<2;selector++){
  setup(getid,0,1);text(1,getname);text(2,names[selector]);mapstrings_getentityproperty(args,4);mapstrings_getentityproperty(args,4);
  if(modern){assert(values[2].vt==VT_INTEGER && values[2].lVal==selector);integer_result(4,selector==_gep_landframe_ent?40002:23);}
  else {assert(values[2].vt==VT_STR);integer_result(4,-7);}
 }
 setup(getid,0,0);values[2].vt=VT_EMPTY;if(modern)assert(openbor_getentityproperty(args,&out,4)==E_FAIL && out && out->vt==VT_EMPTY && !strcmp(diagnostic,error));else integer_result(4,-7);
 setup(getid,0,0);values[3].vt=VT_DECIMAL;values[3].dblVal=1.5;if(modern)assert(openbor_getentityproperty(args,&out,4)==E_FAIL && out && !strcmp(diagnostic,error));else integer_result(4,-7);
 setup(getid,0,1);values[2].vt=VT_EMPTY;if(modern)empty_result(3);else integer_result(3,-7);
 setup(getid,0,0);animations[0].numframes=0;if(modern)empty_result(4);else integer_result(4,-7);
 setup(getid,0,0);animations[0].numframes=-1;integer_result(4,modern?40001:-7);
 setup(getid,-1,0);if(modern)assert(openbor_getentityproperty(args,&out,4)==E_FAIL && out && out->vt==VT_EMPTY);else integer_result(4,-7);
 setup(getid,-1,0);animptrs[0]=NULL;if(modern)empty_result(4);else assert(openbor_getentityproperty(args,&out,2)==E_FAIL && out && out->vt==VT_EMPTY);
 for(int bad=-1;bad<=2;bad+=3){
  setup(getid,0,bad);if(modern)empty_result(4);else {values[2].lVal=bad;assert(openbor_getentityproperty(args,&out,3)==E_FAIL && out && out->vt==VT_EMPTY);}
 }
 setup(getid,0,0);ent.modeldata.animation=NULL;if(modern)empty_result(4);else assert(openbor_getentityproperty(args,&out,2)==E_FAIL && out && out->vt==VT_EMPTY);
}
int main(void){@CHECKS@ puts("early_landframe=1");return 0;}

'''
        program = program.replace('@PIECES@', '\n'.join(pieces)).replace('@CHECKS@', '\n'.join(checks))
        with tempfile.TemporaryDirectory(prefix='early-landframe-') as name:
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
            if os.environ.get('OBOR_LANDFRAME_OBSERVATIONS'):
                Path(os.environ['OBOR_LANDFRAME_OBSERVATIONS']).write_text(json.dumps(dict(compiler=cc,flags=flags,
                    contexts=len(rows),probe_sha256=hashlib.sha256(program.encode()).hexdigest(),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),returncode=run.returncode,stdout=run.stdout,stderr=run.stderr,
                    scope=fixture['scope'],retirement='TemporaryDirectory removes source/binary'),indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_landframe=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
