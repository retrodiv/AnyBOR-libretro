"""Check own knockdowncount results, fallthrough writes and argument handling.

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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-knockdown.json'


class EarlyKnockdownTests(unittest.TestCase):
    def test_getter_and_setter_results(self):
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
        pieces += [selected_dispatch(source, 'openbor_getentityproperty', ['_gep_knockdowncount']),
                   selected_dispatch(source, 'openbor_changeentityproperty', ['_cep_knockdowncount'])]
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            for key in ['get_error_c', 'set_error_c']:
                self.assertRegex(row[key], r'^"(?:[^"\\]|\\.)*"$')
            checks.append('check(%d,%d,%d,%d,%s,%s,%s,%s);' % (row['revision'], row['modern'], row['getter_id'], row['setter_id'],
                json.dumps(row['getter_literal']), json.dumps(row['setter_literal']), row['get_error_c'], row['set_error_c']))
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
static ScriptVariant values[4],result,*args[4],*out;
static void setup(int property,int selector){memset(values,0,sizeof(values));memset(&result,0,sizeof(result));memset(&ent,0,sizeof(ent));for(int i=0;i<4;i++){args[i]=&values[i];values[i].vt=VT_INTEGER;}values[0].vt=VT_PTR;values[0].ptrVal=&ent;values[1].lVal=property;values[2].lVal=selector;values[3].vt=VT_DECIMAL;values[3].dblVal=2.75;out=&result;diagnostic[0]=0;ent.knockdowncount=3.5;ent.modeldata.knockdowncount=8.25;ent.knockdowntime=19;}
static void text(int at,const char *s){strcpy(cache[700+at],s);values[at].vt=VT_STR;values[at].strVal=700+at;}
static void decimal_result(int modern,int count){assert(openbor_getentityproperty(args,&out,count)==S_OK && out && out->vt==VT_DECIMAL && out->dblVal==(modern?8.25:3.5));}
static void check(unsigned revision,int modern,int getid,int setid,const char *getname,const char *setname,const char *geterror,const char *seterror){
 obor_profile_build=revision;
 setup(getid,0);args[2]=NULL;decimal_result(modern,2);
 for(int selector=-1;selector<=3;selector++){
  setup(getid,selector);
  if(!modern || selector==0 || selector==1)decimal_result(modern,3);
  else assert(openbor_getentityproperty(args,&out,3)==E_FAIL && out && out->vt==VT_EMPTY);
 }
 const char *names[]={"current","max","time"};
 for(int i=0;i<3;i++){
  setup(getid,0);text(1,getname);text(2,names[i]);mapstrings_getentityproperty(args,3);mapstrings_getentityproperty(args,3);
  if(!modern){assert(values[2].vt==VT_STR);decimal_result(0,3);}
  else if(i<2){assert(values[2].vt==VT_INTEGER && values[2].lVal==i);decimal_result(1,3);}
  else assert(openbor_getentityproperty(args,&out,3)==E_FAIL && out && out->vt==VT_EMPTY);
 }
 setup(getid,0);values[2].vt=VT_EMPTY;
 if(modern)assert(openbor_getentityproperty(args,&out,3)==E_FAIL && out && out->vt==VT_EMPTY && !strcmp(diagnostic,geterror));else decimal_result(0,3);
 setup(getid,2);ent.knockdowncount=INFINITY;
 if(modern)assert(openbor_getentityproperty(args,&out,3)==E_FAIL && out && out->vt==VT_EMPTY);
 else assert(openbor_getentityproperty(args,&out,3)==S_OK && out && out->vt==VT_DECIMAL && isinf(out->dblVal));
 if(setid<0){setup(0,0);text(1,"knockdowncount");assert(openbor_changeentityproperty(args,&out,4)==E_FAIL && !out && ent.knockdowncount==3.5 && ent.modeldata.knockdowncount==8.25 && ent.knockdowntime==19);return;}
 for(int selector=0;selector<3;selector++)for(int supplied=0;supplied<2;supplied++)for(int named=0;named<2;named++){
  setup(setid,selector);if(!supplied)values[3].vt=VT_EMPTY;
  if(named){text(1,setname);text(2,names[selector]);mapstrings_changeentityproperty(args,4);mapstrings_changeentityproperty(args,4);}
  assert(openbor_changeentityproperty(args,&out,4)==E_FAIL && !out && !strcmp(diagnostic,"Unknown knockdowncount subproperty.\n"));
  assert(ent.knockdowncount==(selector==0 && supplied?2.75:3.5));
  assert(ent.modeldata.knockdowncount==(selector<=1 && supplied?2.75:8.25));
  assert(ent.knockdowntime==(unsigned)selector);
 }
 setup(setid,0);values[2].vt=VT_EMPTY;assert(openbor_changeentityproperty(args,&out,4)==E_FAIL && !out && !strcmp(diagnostic,seterror) && ent.knockdowntime==19);
 for(int selector=-1;selector<=3;selector++)if(selector<0 || selector>2){setup(setid,selector);assert(openbor_changeentityproperty(args,&out,4)==E_FAIL && !out && ent.knockdowncount==3.5 && ent.modeldata.knockdowncount==8.25 && ent.knockdowntime==19 && !strcmp(diagnostic,"Unknown knockdowncount subproperty.\n"));}
 for(int selector=0;selector<3;selector++){
  setup(setid,selector);args[3]=NULL;assert(openbor_changeentityproperty(args,&out,3)==E_FAIL && !out);
  assert(ent.knockdowncount==3.5 && ent.modeldata.knockdowncount==8.25 && ent.knockdowntime==(selector==2?2:19));
 }
}
int main(void){@CHECKS@ puts("early_knockdown=1");return 0;}
'''
        program = program.replace('@PIECES@', '\n'.join(pieces)).replace('@CHECKS@', '\n'.join(checks))
        with tempfile.TemporaryDirectory(prefix='early-knockdown-') as name:
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
            if os.environ.get('OBOR_KNOCKDOWN_OBSERVATIONS'):
                Path(os.environ['OBOR_KNOCKDOWN_OBSERVATIONS']).write_text(json.dumps(dict(compiler=cc,flags=flags,
                    contexts=len(rows),probe_sha256=hashlib.sha256(program.encode()).hexdigest(),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),returncode=run.returncode,stdout=run.stdout,stderr=run.stderr,
                    scope=fixture['scope'],retirement='TemporaryDirectory removes source/binary'),indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_knockdown=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
