"""Check historical callback order, local visibility and shared ownership.

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
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-callback-order.json'


class EarlyCallbackOrderTests(unittest.TestCase):
    def test_cleanup_copy_local_visibility_and_reference_lifetime(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertEqual((min(revisions), max(revisions)), tuple(fixture['range']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_SCRIPT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        script = (engine / 'openborscript.c').read_text()
        header = (engine / 'openbor.h').read_text()
        aggregate = re.search(r'typedef struct\s*\{[^{}]*?Script\s*\*\s*animation_script;[^{}]*\}\s*s_scripts\s*;', header)
        self.assertIsNotNone(aggregate)
        slots = re.findall(r'Script\s*\*\s*(\w+)\s*;', aggregate[0])
        self.assertEqual(slots, fixture['slots'])
        enum = re.search(r'enum\s*\{\s*OBOR_CALLBACK_KILL[^}]+\};', core)
        self.assertIsNotNone(enum)
        for name, flag in [('kill', 'KILL'), ('free_ent', 'FREE_ENT'),
                           ('free_model', 'FREE_MODEL'), ('spawn', 'SPAWN'),
                           ('set_model_ex', 'SET_MODEL')]:
            body = function(core, name)
            calls = re.findall(r'obor_profile_callback_scripts\([^;]+;', body)
            self.assertEqual(len(calls), 2 if name == 'spawn' else 1)
            self.assertTrue(all('OBOR_CALLBACK_' + flag in call for call in calls))
        functions = '\n'.join(function(script, name) for name in (
            'Script_Local_Clear', 'Script_Get_Local_Variant', 'Script_Get_Global_Variant',
            'system_maxglobalvarindex', 'obor_script_share_references', 'Script_Clear', 'Script_Copy'))
        functions += function(core, 'obor_profile_callback_scripts')
        checks = []
        operation_names = ['kill', 'free_ent', 'free_model', 'spawn_clear', 'spawn_copy', 'model_copy']
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual([op['operation'] for op in row['operations']], operation_names)
            for digest in row['function_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            for op, record in enumerate(row['operations']):
                self.assertEqual(sorted(record['order']), list(range(len(slots))))
                for pattern, remaining in enumerate(record['remaining']):
                    self.assertEqual(len(remaining), len(set(remaining)))
                    self.assertTrue(all(0 <= i < len(fixture['patterns'][pattern]) for i in remaining))
                    checks.append('check(%d,%d,%d,(int[]){%s},%d,(int[]){%s},%d);' % (
                        row['revision'], op, record['method'], ','.join(map(str, record['order'])),
                        pattern, ','.join(map(str, remaining)) or '-1', len(remaining)))
        patterns = '\n'.join('static const int pattern_%d[]={%s};' % (i, ','.join(map(str, p)))
                             for i, p in enumerate(fixture['patterns']))
        pattern_select = '\n'.join('case %d: owners=pattern_%d; length=sizeof(pattern_%d)/sizeof(int); break;' %
                                   (i, i, i) for i in range(len(fixture['patterns'])))
        program = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openborscript.h"
@AGGREGATE@
@ENUM@
uint32_t obor_profile_build;
Script *pcurrentscript;
s_variantnode **global_var_list;
int max_global_var_index=-1,max_global_vars=16,max_script_vars=2;
static int destroyed,trace[128],trace_count,observe;
static Script dest[64],origin[64],current;
static s_variantnode entries[16],*entry_ptrs[16];
void shutdown(int code,char *message,...) {(void)code;(void)message;abort();}
void ScriptVariant_Clear(ScriptVariant *value) {memset(value,0,sizeof(*value));}
void ScriptVariant_ChangeType(ScriptVariant *value,VARTYPE type) {
 memset(value,0,sizeof(*value));value->vt=type;
}
@FUNCTIONS@
static void destroy_marker(void *value) {
 if(observe) {assert(trace_count<128);trace[trace_count++]=*(int *)value;}
 destroyed++;free(value);
}
static void initialize(Script *script,int marker) {
 int *value=malloc(sizeof(*value));assert(value);*value=marker;
 script->obor_interpreter=obor_script_reference_new(value,destroy_marker);
 assert(script->obor_interpreter);script->pinterpreter=(Interpreter *)value;
 script->initialized=1;script->interpreterowner=1;
 if(!script->vars) script->vars=calloc((size_t)max_script_vars,sizeof(*script->vars));
 assert(script->vars);script->vars[0].vt=VT_INTEGER;script->vars[0].lVal=19;
}
@PATTERNS@
static void check(unsigned revision,int op,int method,const int *order,int pattern,
                  const int *remaining,int remaining_count) {
 const int *owners=NULL;size_t length=0;
 switch(pattern) {@PATTERN_SELECT@ default:abort();}
 s_scripts target={0},source={0};const size_t count=sizeof(target)/sizeof(Script *);
 assert(count<=64 && length<=16);obor_profile_build=revision;
 memset(dest,0,sizeof(dest));memset(origin,0,sizeof(origin));
 destroyed=trace_count=0;observe=1;
 for(size_t i=0;i<count;i++) {
  initialize(dest+i,(int)i);initialize(origin+i,100+(int)i);
  Script *p=dest+i,*q=origin+i;
  memcpy((unsigned char *)&target+i*sizeof(p),&p,sizeof(p));
  memcpy((unsigned char *)&source+i*sizeof(q),&q,sizeof(q));
 }
 memset(entries,0,sizeof(entries));
 for(size_t i=0;i<length;i++) {
  entries[i].owner=owners[i]<0?NULL:dest+owners[i];
  entries[i].key=(char *)"marker";entries[i].value.vt=VT_INTEGER;
  entries[i].value.lVal=(LONG)(1000+i);entry_ptrs[i]=entries+i;
 }
 global_var_list=entry_ptrs;max_global_var_index=(int)length-1;
 memset(&current,0,sizeof(current));current.initialized=1;pcurrentscript=&current;
 int operation=op==0?OBOR_CALLBACK_KILL:op==1?OBOR_CALLBACK_FREE_ENT:
  op==2?OBOR_CALLBACK_FREE_MODEL:op==5?OBOR_CALLBACK_SET_MODEL:OBOR_CALLBACK_SPAWN;
 int copying=op>=4;
 obor_profile_callback_scripts(copying?&source:NULL,&target,method,operation);
 assert(pcurrentscript==&current && trace_count==(int)count && destroyed==(int)count);
 for(size_t i=0;i<count;i++) {
  if(trace[i]!=order[i]) fprintf(stderr,"revision=%u operation=%d position=%zu got=%d expected=%d\n",
                               revision,op,i,trace[i],order[i]);
  assert(trace[i]==order[i]);
 }
 assert(max_global_var_index==remaining_count-1);
 ScriptVariant value,*result=&value;assert(system_maxglobalvarindex(NULL,&result,0)==S_OK);
 assert(value.vt==VT_INTEGER && value.lVal==remaining_count-1);
 for(int i=0;i<remaining_count;i++) assert(entry_ptrs[i]==entries+remaining[i]);
 for(size_t i=0;i<length;i++) if(owners[i]<0) {
  ScriptVariant *global=Script_Get_Global_Variant((char *)"marker");
  assert(global && global->lVal==entries[i].value.lVal);
 }
 observe=0;
 for(size_t i=0;i<count;i++) {
  if(copying) {
   assert(dest[i].initialized && dest[i].obor_interpreter==origin[i].obor_interpreter);
   assert(dest[i].pinterpreter==origin[i].pinterpreter);
   assert(origin[i].obor_interpreter->references==2);
  } else {
   assert(!dest[i].initialized && !dest[i].obor_interpreter && !dest[i].pinterpreter);
   assert((dest[i].vars==NULL)==(method==2));
   initialize(dest+i,200+(int)i);
  }
  pcurrentscript=dest+i;ScriptVariant *local=Script_Get_Local_Variant((char *)"marker");
  ScriptVariant *expected=NULL;
  for(int j=0;j<remaining_count;j++) if(entries[remaining[j]].owner==dest+i) {
   expected=&entries[remaining[j]].value;break;
  }
  assert(local==expected);
 }
 // Reuse keeps the same callback identities; no operation destroys the source.
 // Release parents/children in both orders, using the real safe ownership path.
 max_global_var_index=-1;pcurrentscript=&current;
 for(size_t i=0;i<count;i++) {
  if(copying && (i&1)) {
   Script_Clear(origin+i,2);assert(dest[i].obor_interpreter->references==1);
   Script_Clear(dest+i,2);
  } else {
   Script_Clear(dest+i,2);
   if(copying) assert(origin[i].obor_interpreter->references==1);
   Script_Clear(origin+i,2);
  }
 }
 assert(destroyed==(int)count*(copying?2:3));
 obor_profile_callback_scripts(NULL,NULL,method,operation);
}
int main(void) {@CHECKS@ puts("early_callback_order=1");return 0;}
'''.replace('@AGGREGATE@', aggregate[0]).replace('@ENUM@', enum[0]).replace(
            '@FUNCTIONS@', functions).replace('@PATTERNS@', patterns).replace(
            '@PATTERN_SELECT@', pattern_select).replace('@CHECKS@', '\n'.join(checks))
        with tempfile.TemporaryDirectory(prefix='early-callback-order-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(program)
            includes = [engine, engine / 'source/scriptlib', engine / 'source/preprocessorlib',
                        engine / 'source', engine / 'source/gamelib',
                        ROOT / 'src/port/libretro', ROOT / 'src/glue']
            command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-fcommon', '-Wall', '-Wextra', '-Werror',
                '-DSAFEALLOC_H=1',
                '-Wno-unused-parameter', '-Wno-error=deprecated-declarations',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                '-fno-omit-frame-pointer', *['-I' + str(path) for path in includes], str(unit),
                *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=15, env=sanitizer_environment())
            receipt = os.environ.get('OBOR_CALLBACK_OBSERVATIONS')
            if receipt:
                Path(receipt).write_text(json.dumps({
                    'command': command, 'contexts': len(rows), 'checks': len(checks),
                    'probe_sha256': hashlib.sha256(unit.read_bytes()).hexdigest(),
                    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                    'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr,
                    'temporary_inputs_and_binary': 'retired by TemporaryDirectory',
                }, indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_callback_order=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
