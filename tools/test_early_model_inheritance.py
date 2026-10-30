"""Check subclass availability, inherited callbacks and compile-call policy.

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
from native_allocation_policy import bind_named_allocation_support
from test_historical_player import function, switch_cases

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-model-inheritance.json'


class EarlyModelInheritanceTests(unittest.TestCase):
    def test_subclass_lookup_copy_lifetime_and_animation_compile(self):
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
        core, header, script = ((engine / name).read_text() for name in ['openbor.c', 'openbor.h', 'openborscript.c'])
        aggregate = re.findall(r'typedef struct\s*\{[^{}]*?Script\s*\*\s*animation_script;[^{}]*}\s*s_scripts\s*;', header)
        freetype = re.findall(r'typedef enum\s*\{[^{}]*}\s*ModelFreetype;', header)
        self.assertEqual((len(aggregate), len(freetype)), (1, 1))
        method = function(core, 'load_cached_model')
        method, cases = switch_cases(method.replace('switch(cmd)', 'switch(model_command)', 1),
                                     'load_cached_model', 'model_command')
        compile_call = re.findall(r'if\([^\n]*!newchar->isSubclassed\)\s*Script_Compile\(newchar->scripts.animation_script\);', method)
        self.assertEqual(len(compile_call), 1)
        commands = (engine / 'source/gamelib/commands.c').read_text()
        bodies = function(core, 'obor_lookup_command') + function((engine / 'source/utils.c').read_text(), 'lc')
        for name in ['getCommandlistCommand', 'getModelCommand', 'prepareList', 'createModelCommandList', 'freeCommandList']:
            bodies += '\n' + function(commands, name) + '\n#undef LIST_ADD\n'
        bodies += function(core, 'obor_profile_model_command')
        script_functions = '\n'.join(function(script, name) for name in [
            'Script_Local_Clear', 'obor_script_share_references', 'Script_Clear', 'Script_Copy', 'alloc_script'])
        script_functions += '\n' + '\n'.join(function(core, name) for name in [
            'alloc_all_scripts', 'copy_all_scripts', 'clear_all_scripts', 'free_all_scripts', 'hasFreetype'])
        checks = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['function_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            self.assertIs(type(row['supported']), bool)
            self.assertIs(type(row['compile_subclass']), bool)
            self.assertIn(row['unsupported_outcome'], [1, 2])
            checks.append('check(%d,%d,%d,%d);' % (row['revision'], row['supported'],
                                                row['compile_subclass'], row['unsupported_outcome']))
        program = r'''
#include <assert.h>
#include <ctype.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openborscript.h"
#include "commands.h"
#undef printf
@AGGREGATE@
@FREETYPE@
typedef struct {char *name;int index,health;void *palette;ModelFreetype freetypes;s_scripts scripts;int isSubclassed;} s_model;
uint32_t obor_profile_build;
Script *pcurrentscript;
s_variantnode **global_var_list;
int max_global_var_index=-1,max_global_vars=128,max_script_vars=2;
static int created,destroyed,outcome,compiled;
static char diagnostic[256];
static jmp_buf stopped;
static s_model *parent;
static s_variantnode entries[65],*entry_ptrs[65];
void shutdown(int code,char *message,...) {(void)code;(void)message;abort();}
void ScriptVariant_Clear(ScriptVariant *value) {memset(value,0,sizeof(*value));}
void ScriptVariant_Init(ScriptVariant *value) {memset(value,0,sizeof(*value));}
void ScriptVariant_ChangeType(ScriptVariant *value,VARTYPE type) {memset(value,0,sizeof(*value));value->vt=type;}
int Script_Compile(Script *value) {assert(value);compiled++;return 1;}
@SCRIPT_FUNCTIONS@
@LOOKUP_FUNCTIONS@
static s_model *findmodel(char *name) {return !strcmp(name,"Base")?parent:NULL;}
static void destroy_marker(void *value) {destroyed++;free(value);}
static void initialize(Script *script,int marker) {
 int *value=malloc(sizeof(*value));assert(value);*value=marker;created++;
 script->obor_interpreter=obor_script_reference_new(value,destroy_marker);assert(script->obor_interpreter);
 script->pinterpreter=(Interpreter *)value;script->initialized=1;script->interpreterowner=1;
 script->vars[0].vt=VT_INTEGER;script->vars[0].lVal=marker;
}
static int warning(const char *format,...) {
 va_list args;va_start(args,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);
 assert(n>=0 && (size_t)n<sizeof(diagnostic));outcome=1;return n;
}
static void stop_request(int code,const char *format,...) {
 va_list args;va_start(args,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);
 assert(code==1 && n>=0 && (size_t)n<sizeof(diagnostic));outcome=2;longjmp(stopped,1);
}
#define printf warning
#define shutdown stop_request
@FEEDBACK@
static void dispatch(List *list,s_model *newchar,char *target_name,int upper) {
 char text[16],*command=text,*filename=(char *)"data/child.txt",*shutdownmessage=NULL;
 strcpy(text,upper?"SUBCLASS":"subclass");
 modelCommands cmd=obor_profile_model_command(list,command);
 s_model *tempmodel=NULL;s_scripts tempscripts;
#define GET_ARG(z) ((void)(z),target_name)
 switch(cmd) {
 case CMD_MODEL_SUBCLASS:@CASE@
 default:@DEFAULT@
 }
#undef GET_ARG
 return;
 lCleanup:
 assert(shutdownmessage && !strcmp(shutdownmessage,"tried to subclass a non-existing/not previously loaded model!"));
 outcome=3;
}
#undef shutdown
#undef printf
static void compile_animation(s_model *newchar) {@COMPILE@}
static Script *slot(s_scripts *scripts,size_t index) {Script *p;memcpy(&p,(char *)scripts+index*sizeof(p),sizeof(p));return p;}
static void release_model_scripts(s_model *model) {
 clear_all_scripts(&model->scripts,2);free_all_scripts(&model->scripts);
 for(size_t i=0;i<sizeof(s_scripts)/sizeof(Script *);i++)assert(!slot(&model->scripts,i));
}
static void check(unsigned revision,int supported,int compile_subclass,int unsupported) {
 obor_profile_build=revision;
 List *list=createModelCommandList();assert(list);
 const size_t count=sizeof(s_scripts)/sizeof(Script *);assert(count>0 && count<=64);
 for(volatile int upper=0;upper<2;upper++) for(volatile int missing=0;missing<2;missing++)
 for(volatile int child_ready=0;child_ready<2;child_ready++) for(volatile int sparse=0;sparse<2;sparse++)
 for(volatile int parent_first=0;parent_first<2;parent_first++) {
  s_model base={0},child={0};parent=&base;created=destroyed=outcome=compiled=0;diagnostic[0]=0;
  base.name=(char *)"Base";base.index=7;base.health=71;base.palette=(void *)&base;
  child.name=(char *)"Child";child.index=3;child.health=31;child.palette=(void *)&child;
  base.freetypes=child.freetypes=(ModelFreetype)0x1FFFF;
  alloc_all_scripts(&base.scripts);alloc_all_scripts(&child.scripts);
  Script *original_child[64];
  for(size_t i=0;i<count;i++) {
   original_child[i]=slot(&child.scripts,i);
   if(!sparse || !(i&1))initialize(slot(&base.scripts,i),100+(int)i);
   if(child_ready)initialize(original_child[i],200+(int)i);
  }
  memset(entries,0,sizeof(entries));
  for(size_t i=0;i<(child_ready?count:0);i++) {
   entries[i].owner=original_child[i];entries[i].key=(char *)"local";
   entries[i].value.vt=VT_INTEGER;entries[i].value.lVal=300+(int)i;entry_ptrs[i]=entries+i;
  }
  size_t global=child_ready?count:0;
  entries[global].key=(char *)"global";entries[global].value.vt=VT_INTEGER;
  entries[global].value.lVal=999;entry_ptrs[global]=entries+global;
  global_var_list=entry_ptrs;max_global_var_index=(int)global;
  if(!setjmp(stopped))dispatch(list,&child,missing?(char *)"Missing":(char *)"Base",upper);
  assert(outcome==(!supported?unsupported:missing?3:0));
  int copied=supported&&!missing;
  assert(child.isSubclassed==copied);
  assert(child.health==(copied?71:31) && child.index==(copied?7:3));
  assert(child.palette==(copied?(void *)&base:(void *)&child));
  if(copied)assert(hasFreetype(&child,MF_SCRIPTS) && !hasFreetype(&child,MF_PALETTE));
  for(size_t i=0;i<count;i++) {
   Script *p=slot(&base.scripts,i),*q=slot(&child.scripts,i);assert(q==original_child[i] && p!=q);
   int from_parent=copied&&p->initialized;
   assert(q->initialized==(from_parent||child_ready));
   if(from_parent) {
    assert(q->pinterpreter==p->pinterpreter && q->obor_interpreter==p->obor_interpreter);
    assert(p->obor_interpreter->references==2 && q->vars!=p->vars);
    assert(q->vars[0].vt==VT_EMPTY);
   } else if(q->initialized)assert(q->obor_interpreter->references==1);
   int present=0;
   for(int j=0;j<=max_global_var_index;j++)present+=global_var_list[j]->owner==q;
   int expected_local=child_ready&&!from_parent;
   assert(present==expected_local);
  }
  if(outcome!=2 && outcome!=3)compile_animation(&child);
  assert(compiled==((outcome==2 || outcome==3)?0:copied?compile_subclass:1));
  if(parent_first) {release_model_scripts(&base);release_model_scripts(&child);}
  else {release_model_scripts(&child);release_model_scripts(&base);}
  assert(destroyed==created && pcurrentscript==NULL && max_global_var_index==0);
  assert(global_var_list[0]->owner==NULL && global_var_list[0]->value.lVal==999);
  global_var_list=NULL;max_global_var_index=-1;
 }
 freeCommandList(list);
}
int main(void) {@CHECKS@ puts("early_model_inheritance=1");return 0;}
'''
        replacements = dict(AGGREGATE=aggregate[0], FREETYPE=freetype[0], SCRIPT_FUNCTIONS=script_functions,
                            LOOKUP_FUNCTIONS=bodies, FEEDBACK=function(core, 'obor_profile_file_feedback'),
                            CASE=cases['CMD_MODEL_SUBCLASS']['body'], DEFAULT=cases['default']['body'],
                            COMPILE=compile_call[0], CHECKS='\n'.join(checks))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-model-inheritance-') as name:
            work = Path(name)
            unit, obj, binary = work / 'probe.c', work / 'list.o', work / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            includes = [engine, engine / 'source/scriptlib', engine / 'source/preprocessorlib', engine / 'source',
                        engine / 'source/gamelib', ROOT / 'src/port/libretro', ROOT / 'src/glue']
            flags = ['-std=gnu99', '-O1', '-g', '-fcommon', '-UNDEBUG', '-DSAFEALLOC_H=1', '-Dstricmp=strcasecmp',
                     '-Dstrnicmp=strncasecmp', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                     '-fno-omit-frame-pointer', *['-I' + str(path) for path in includes]]
            build = subprocess.run(cc + flags + ['-DUNIT_TEST=1', '-c', str(engine / 'source/scriptlib/List.c'), '-o', str(obj)],
                                   capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            build = subprocess.run(cc + flags + ['-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter', '-Wno-sign-compare',
                                   '-Wno-error=deprecated-declarations', str(unit), str(obj),
                                   *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)],
                                   capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15, env=sanitizer_environment())
            if os.environ.get('OBOR_MODEL_INHERITANCE_OBSERVATIONS'):
                Path(os.environ['OBOR_MODEL_INHERITANCE_OBSERVATIONS']).write_text(json.dumps({
                    'compiler': cc, 'flags': flags, 'contexts': len(rows),
                    'probe_sha256': hashlib.sha256(program.encode()).hexdigest(),
                    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                    'source_sha256': hashlib.sha256(core.encode()).hexdigest(),
                    'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr,
                    'retirement': 'TemporaryDirectory removes source/object/binary',
                }, indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_model_inheritance=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
