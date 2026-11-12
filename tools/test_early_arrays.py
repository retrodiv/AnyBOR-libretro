"""Check historical array registration, values, storage and bounded indices.

The actual variant and heap-list units provide copying and ownership. These
checks isolate the native API; they do not execute a whole script/game.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from native_allocation_policy import bind_named_allocation_support
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-arrays.json'


def array_windows(script):
    names = function(script, 'Script_GetFunctionName')
    first = names.index('\telse if (obor_profile_build >= 3428')
    last = names.index('\telse if (functionRef==((void*)openbor_allocscreen))', first)
    reverse = 'if(0) return NULL;\n' + names[first:last] + '\nreturn NULL;'
    loader = function(script, 'Script_LoadSystemFunctions')
    first = loader.index('    if(obor_profile_build >= 3428)')
    last = loader.index('\tList_InsertAfter(&theFunctionList,', first + 1)
    return reverse, loader[first:last]


class EarlyArrayTests(unittest.TestCase):
    def test_registry_and_source_controls(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            for value in row['source_sha256'].values():
                self.assertRegex(value, r'^[0-9a-f]{64}$')
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)

    def test_values_layout_registration_and_release(self):
        fixture = load_contract_fixture(FIXTURE)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        script = (engine / 'openborscript.c').read_text()
        reverse, registration = array_windows(script)
        bodies = '\n'.join(function(script, name) for name in
                           ('obor_array_capacity', 'openbor_array', 'openbor_size', 'openbor_get', 'openbor_set'))
        checks = '\n'.join('check(%d,%d,%d);' % (row['revision'], row['array'], row['size_header'])
                           for row in fixture['sources'])
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ScriptVariant.h"
#include "List.h"
#include "anybor_script_storage.h"
uint32_t obor_profile_build;
static List scriptheap,theFunctionList;
static char diagnostic[512];
void writeToLogFile(const char *format,...){
 va_list args;va_start(args,format);vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);
}
static void *owned;
static size_t owned_bytes;
static int refuse_allocation;
static void *array_alloc(size_t bytes){
 assert(!owned);if(refuse_allocation)return NULL;
 owned=malloc(bytes);owned_bytes=owned?bytes:0;return owned;
}
size_t obor_allocation_size(const void *p){return p==owned?owned_bytes:0;}
#define malloc array_alloc
@BODIES@
#undef malloc
static const char *reverse_name(void *functionRef){@REVERSE@}
static void register_arrays(void){@REGISTER@}
@FREE@
static HRESULT invoke(HRESULT (*api)(ScriptVariant**,ScriptVariant**,int),
                      ScriptVariant **args,int count,ScriptVariant *value,int null_return){
 ScriptVariant *result=value;HRESULT status=api(args,&result,count);
 assert(null_return?(result==NULL):(result==value));return status;
}
static void check(unsigned revision,int enabled,int header){
 obor_profile_build=revision;List_Init(&scriptheap);List_Init(&theFunctionList);
 StrCache_Clear();register_arrays();
 assert(List_GetSize(&theFunctionList)==(enabled?3+header:0));
 void *apis[]={(void*)openbor_array,(void*)openbor_get,(void*)openbor_set,(void*)openbor_size};
 const char *names[]={"array","get","set","size"};
 for(unsigned i=0;i<4;i++){
  int present=enabled && (i!=3 || header);
  assert(List_FindByName(&theFunctionList,names[i])==present);
  if(present)assert(List_Retrieve(&theFunctionList)==apis[i]);
  const char *name=reverse_name(apis[i]);
  assert(present?(name && !strcmp(name,names[i])):name==NULL);
 }
 ScriptVariant length={0},handle={0},index={0},value={0},result={0};
 ScriptVariant *args[]={&length,&index,&value};
 length.vt=VT_INTEGER;length.lVal=4;
 if(!enabled){
  assert(invoke(openbor_array,args,1,&handle,1)==E_FAIL);
 }else{
  for(int fractional=0;fractional<2;fractional++){
   length.vt=fractional?VT_DECIMAL:VT_INTEGER;
   if(fractional)length.dblVal=4.75;else length.lVal=4;
   assert(invoke(openbor_array,args,1,&handle,0)==S_OK);
   assert(handle.vt==VT_PTR && handle.ptrVal==owned);
   assert(owned_bytes==(4u+(unsigned)header)*sizeof(ScriptVariant));
   ScriptVariant *slots=owned;
   Node *heap_cursor=scriptheap.current;
   if(header)assert(slots[0].vt==VT_INTEGER && slots[0].lVal==4);
   for(int i=0;i<4;i++)assert(slots[i+header].vt==VT_EMPTY);
   args[0]=&handle;index.vt=VT_INTEGER;
   for(int i=0;i<4;i++){
    index.lVal=i;result.vt=VT_EMPTY;
    assert(invoke(openbor_get,args,2,&result,0)==S_OK && result.vt==VT_EMPTY);
    value.vt=VT_INTEGER;value.lVal=30+i;
    assert(invoke(openbor_set,args,3,&result,1)==S_OK);
    assert(slots[i+header].vt==VT_INTEGER && slots[i+header].lVal==30+i);
    assert(invoke(openbor_get,args,2,&result,0)==S_OK && result.lVal==30+i);
   }
   index.vt=VT_DECIMAL;index.dblVal=2.75;value.vt=VT_DECIMAL;value.dblVal=12.5;
   assert(invoke(openbor_set,args,3,&result,1)==S_OK);
   assert(invoke(openbor_get,args,2,&result,0)==S_OK && result.vt==VT_DECIMAL && result.dblVal==12.5);
   index.vt=VT_INTEGER;index.lVal=3;
   ScriptVariant_ChangeType(&value,VT_STR);strcpy(StrCache_Get(value.strVal),"array string");
   assert(invoke(openbor_set,args,3,&result,1)==S_OK);
   assert(invoke(openbor_get,args,2,&result,0)==S_OK && result.vt==VT_STR);
   assert(!strcmp(StrCache_Get(result.strVal),"array string"));
   assert(slots[3+header].strVal!=value.strVal && slots[3+header].strVal!=result.strVal);
   ScriptVariant_Clear(&result);ScriptVariant_Clear(&value);
   value.vt=VT_PTR;value.ptrVal=&handle;
   assert(invoke(openbor_set,args,3,&result,1)==S_OK);
   assert(invoke(openbor_get,args,2,&result,0)==S_OK && result.vt==VT_PTR && result.ptrVal==&handle);
   if(header){assert(invoke(openbor_size,args,1,&result,0)==S_OK && result.vt==VT_INTEGER && result.lVal==4);}
   else assert(invoke(openbor_size,args,1,&result,1)==E_FAIL);
   const LONG invalid[]={-1,4,100};
   for(unsigned i=0;i<3;i++){
    index.lVal=invalid[i];
    assert(invoke(openbor_get,args,2,&result,1)==E_FAIL);
    assert(!strncmp(diagnostic,header?"Array bound out of range:":"Function requires",header?25:17));
    assert(invoke(openbor_set,args,3,&result,1)==E_FAIL);
   }
   index.lVal=0;index.vt=VT_EMPTY;
   assert(invoke(openbor_get,args,2,&result,1)==E_FAIL);
   index.vt=VT_INTEGER;
   assert(invoke(openbor_get,args,1,&result,1)==E_FAIL);
   assert(invoke(openbor_set,args,2,&result,1)==E_FAIL);
   assert(scriptheap.current==heap_cursor);
   void *released=owned;
   assert(invoke(system_free,args,1,&result,1)==S_OK);
   owned=NULL;owned_bytes=0;assert(!List_GetNodeByValue(&scriptheap,released));
   assert(invoke(openbor_get,args,2,&result,1)==E_FAIL);
   assert(invoke(system_free,args,1,&result,1)==E_FAIL);
   args[0]=&length;
  }
  length.vt=VT_INTEGER;length.lVal=0;
  assert(invoke(openbor_array,args,1,&handle,1)==E_FAIL);
  length.lVal=-1;assert(invoke(openbor_array,args,1,&handle,1)==E_FAIL);
  length.lVal=4;refuse_allocation=1;
  assert(invoke(openbor_array,args,1,&handle,1)==E_FAIL);refuse_allocation=0;
  assert(invoke(openbor_array,args,0,&handle,1)==E_FAIL);
  handle.vt=VT_PTR;handle.ptrVal=NULL;args[0]=&handle;
  assert(invoke(openbor_get,args,2,&result,1)==E_FAIL);
  assert(invoke(openbor_set,args,3,&result,1)==E_FAIL);
  assert(invoke(openbor_size,args,1,&result,1)==E_FAIL);
 }
 ScriptVariant_Clear(&result);List_Clear(&theFunctionList);List_Clear(&scriptheap);StrCache_Clear();
}
int main(void){@CHECKS@puts("early_arrays=1");return 0;}
'''
        for key, value in dict(BODIES=bodies, REVERSE=reverse, REGISTER=registration,
                               FREE=function(script, 'system_free'), CHECKS=checks).items():
            code = code.replace('@' + key + '@', value)
        code = bind_named_allocation_support(code, engine)
        with tempfile.TemporaryDirectory(prefix='early-arrays-') as directory:
            work = Path(directory)
            source, binary = work / 'probe.c', work / 'probe'
            source.write_text(code)
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu11', '-Wall', '-Wextra', '-Werror',
                     '-Wno-error=deprecated-declarations', '-Wno-unused-parameter',
                     '-Wno-unused-variable', '-Wno-unused-function',
                     '-O0', '-g', '-fcommon', '-fsigned-char', '-ffunction-sections', '-fdata-sections',
                     '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
                     '-I' + str(engine / 'source/scriptlib'), '-I' + str(engine / 'source'),
                     *['-I' + str(p) for p in sorted((engine / 'source').iterdir()) if p.is_dir()],
                     '-I' + str(ROOT / 'src/port/libretro')]
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            objects = []
            # Keep upstream-unit warning policy distinct from the authored probe.
            for name in ('List', 'ScriptVariant'):
                obj = work / (name + '.o')
                compile_checked(compiler + flags + ['-Wno-error=sign-compare',
                    '-Wno-error=misleading-indentation', '-Wno-unused-but-set-variable',
                    '-c', str(engine / ('source/scriptlib/' + name + '.c')), '-o', str(obj)])
                objects.append(str(obj))
            compile_checked(compiler + flags + [str(source), *objects, *links, '-lm', '-o', str(binary)])
            output = subprocess.check_output([str(binary)], text=True, timeout=30,
                                             env=sanitizer_environment())
            self.assertIn('early_arrays=1', output)


if __name__ == '__main__':
    unittest.main()
