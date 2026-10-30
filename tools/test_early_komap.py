"""Check own-profile KO-map getter signatures and defined return values.

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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-komap.json'


class EarlyKomapTests(unittest.TestCase):
    def test_selector_and_result(self):
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
        descriptor = namespace_descriptor(source, 'obor_property_namespace')
        macro = re.search(r'(?m)^#define MAPSTRINGS\([^\n]+(?:\n[^\n]*)*?\n}', source)
        self.assertIsNotNone(descriptor)
        self.assertIsNotNone(macro)
        pieces = [descriptor, '\n'.join('static const obor_property_namespace *' + name + '(void);' for name in [
            'obor_get_property_namespace', 'obor_set_property_namespace', 'obor_get_aiflag_namespace', 'obor_set_aiflag_namespace']),
            function(source, 'obor_property_index'),
            source[source.index('enum getentityproperty_enum'):source.index('void mapstrings_getentityproperty(')],
            source[source.index('enum changeentityproperty_enum'):source.index('void mapstrings_changeentityproperty(')],
            function((engine / 'source/utils.c').read_text(), 'searchList'), macro[0],
            function(source, 'mapstrings_getentityproperty')]
        pieces += [function(variant, name) for name in ['ScriptVariant_ChangeType', 'ScriptVariant_Clear']]
        pieces.append(selected_dispatch(source, 'openbor_getentityproperty', ['_gep_komap']))
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            checks.append('check(%d,%d,%d,%s,%s);' % (row['revision'], row['property_id'], row['requires_selector'],
                                                    json.dumps(row['named_route']), json.dumps(row['diagnostic'])))
        program = r'''
#include <assert.h>
#include <ctype.h>
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
static char diagnostic[2048];
static int probe_printf(const char *format,...) {va_list ap;va_start(ap,format);int count=vsnprintf(diagnostic,sizeof(diagnostic),format,ap);va_end(ap);assert(count>=0);return count;}
#define printf probe_printf
uint32_t obor_profile_build;
static char *cache[8];
CHAR *StrCache_Get(int index) {assert(index>=0 && index<8 && cache[index]);return cache[index];}
void StrCache_Collect(int index) {(void)index;}
int StrCache_Pop(void) {abort();}
@PIECES@
static ScriptVariant values[3],result,*args[3],*out;
static entity ent;
static void setup(int property,int selector) {
 memset(values,0,sizeof(values));memset(&result,0,sizeof(result));memset(&ent,0,sizeof(ent));
 for(int i=0;i<3;i++) {args[i]=&values[i];values[i].vt=VT_INTEGER;}
 values[0].vt=VT_PTR;values[0].ptrVal=&ent;values[1].lVal=property;values[2].lVal=selector;out=&result;diagnostic[0]=0;
 ent.modeldata.maps.ko=17;ent.modeldata.maps.kotype=-21;
}
static void check(unsigned revision,int property,int selector_required,const char *literal,const char *error) {
 obor_profile_build=revision;
 for(int selector=0;selector<2;selector++) {
  setup(property,selector);assert(openbor_getentityproperty(args,&out,3)==S_OK && out && out->vt==VT_INTEGER && out->lVal==(selector_required && selector?-21:17));
  setup(property,selector);cache[1]=(char*)literal;values[1].vt=VT_STR;values[1].strVal=1;
  mapstrings_getentityproperty(args,3);mapstrings_getentityproperty(args,3);
  assert(openbor_getentityproperty(args,&out,3)==S_OK && out && out->vt==VT_INTEGER && out->lVal==(selector_required && selector?-21:17));
 }
 setup(property,0);assert(openbor_getentityproperty(args,&out,2)==S_OK && out);
 assert(out->vt==(selector_required?VT_EMPTY:VT_INTEGER));if(!selector_required)assert(out->lVal==17);
 setup(property,0);values[2].vt=VT_EMPTY;HRESULT hr=openbor_getentityproperty(args,&out,3);
 if(selector_required)assert(hr==E_FAIL && !strcmp(diagnostic,error));else assert(hr==S_OK && out && out->lVal==17 && !diagnostic[0]);
 const int invalid[]={-1,2,2147483647};
 for(int i=0;i<3;i++) {setup(property,invalid[i]);hr=openbor_getentityproperty(args,&out,3);
  if(selector_required)assert(hr==E_FAIL && out && out->vt==VT_EMPTY);else assert(hr==S_OK && out && out->lVal==17);}
 for(int value=-128;value<=127;value++)for(int selector=0;selector<2;selector++) {
  setup(property,selector);ent.modeldata.maps.ko=value;ent.modeldata.maps.kotype=-value-1;
  assert(openbor_getentityproperty(args,&out,3)==S_OK && out && out->vt==VT_INTEGER && out->lVal==(selector_required && selector?ent.modeldata.maps.kotype:value));
 }
}
int main(void) {@CHECKS@ puts("early_komap=1");return 0;}
'''
        program = program.replace('@PIECES@', '\n'.join(pieces)).replace('@CHECKS@', '\n'.join(checks))
        with tempfile.TemporaryDirectory(prefix='early-komap-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1', '-Dstricmp=strcasecmp',
                     '-fcommon', '-fsigned-char', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                     '-Wall', '-Wextra', '-Werror', '-Wno-unused-variable', '-Wno-unused-function', '-Wno-sign-compare',
                     '-Wno-misleading-indentation', '-Wno-error=deprecated-declarations']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib', 'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20, env=sanitizer_environment())
            if os.environ.get('OBOR_KOMAP_OBSERVATIONS'):
                Path(os.environ['OBOR_KOMAP_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=cc, flags=flags, contexts=len(rows), probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(), binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    returncode=run.returncode, stdout=run.stdout, stderr=run.stderr, scope=fixture['scope'],
                    retirement='TemporaryDirectory removes source/binary'), indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_komap=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
