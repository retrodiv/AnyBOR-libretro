"""Check model name/path staging at level and model-list call sites.

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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-model-callers.json'


class EarlyModelCallersTests(unittest.TestCase):
    def test_level_and_model_list_name_path_calls(self):
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
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source, header = ((engine / name).read_text() for name in ['openbor.c', 'openbor.h'])
        arglist = re.findall(r'typedef struct ArgList\s*\{[^}]+}\s*ArgList;', header)
        macros = re.findall(r'(?m)^#define GET_ARG\(z\)[^\n]*', source)
        constants = re.findall(r'(?m)^#define\s+MAX_ARG_LEN\s+[^\n]*', header)
        self.assertEqual((len(arglist), len(macros), len(constants)), (1, 1, 1))
        loader = function(source, 'load_level')
        _, level_cases = switch_cases(loader.replace('switch(cmd)', 'switch(level_command)', 1),
                                      'load_level', 'level_command')
        _, model_cases = switch_cases(source, 'load_models', 'cmd')
        helpers = '\n'.join(function(source, name) for name in [
            'ParseArgs', 'findarg', 'obor_legacy_arg', 'obor_model_input', 'obor_cache_input'])
        level_names = ['CMD_LEVEL_SPAWN', 'CMD_LEVEL_ITEM', 'CMD_LEVEL_2PITEM', 'CMD_LEVEL_3PITEM',
                       'CMD_LEVEL_4PITEM', 'CMD_LEVEL_WEAPON']
        level_dispatch = '\n'.join('case %s:%s' % (name, level_cases[name]['body']) for name in level_names)
        model_dispatch = '\n'.join('case %s:%s' % (name, model_cases[name]['body']) for name in ['CMD_MODELSTXT_LOAD', 'CMD_MODELSTXT_KNOW'])
        checks = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['function_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            self.assertIs(type(row['level_staged']), bool)
            self.assertIs(type(row['cache_staged']), bool)
            checks.append('check(%d,%d,%d);' % (row['revision'], row['level_staged'], row['cache_staged']))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "commands.h"
@CONSTANTS@
@ARGLIST@
@MACROS@
uint32_t obor_profile_build;
typedef struct {char *name;} s_model;
typedef struct {char *name,*item,*weapon;int index,itemindex,weaponindex,spawntype,spawnplayer_count,itemplayer_count;} s_spawn_entry;
static ArgList *active_args;
static char seen_lookup[MAX_ARG_LEN+1],seen_load[MAX_ARG_LEN+1],seen_name[MAX_ARG_LEN+1],seen_path[MAX_ARG_LEN+1];
static int cache_mode,lookup_calls,load_calls,cache_calls,cache_flag;
static s_model resolved={(char *)"Resolved"};
@HELPERS@
static void remember(char *destination,const char *value) {
 size_t n=strlen(value);assert(n<MAX_ARG_LEN);memcpy(destination,value,n+1);
}
static s_model *findmodel(char *name) {lookup_calls++;remember(seen_lookup,name);return cache_mode==0?&resolved:NULL;}
static s_model *load_cached_model(char *name,char *owner,int flag) {
 load_calls++;assert(!strcmp(owner,"data/level.txt") && !flag);
 remember(seen_load,name);
 char *other=obor_profile_build<3106?obor_legacy_arg(active_args,2):active_args->args[2];
 assert(!strcmp(other,"Sentinel"));assert(!strcmp(name,seen_load));return cache_mode==1?&resolved:NULL;
}
static int get_cached_model_index(char *name) {assert(name==resolved.name);return 7;}
static void cache_model(char *name,char *path,int flag) {cache_calls++;remember(seen_name,name);remember(seen_path,path);cache_flag=flag;}
static s_spawn_entry level_call(levelCommands cmd,char *buf) {
 ArgList arglist;char argbuf[MAX_ARG_LEN+1]={0},*filename=(char *)"data/level.txt";
 s_model *tempmodel=NULL,*cached_model=NULL;int crlf=0;
 s_spawn_entry next={.name=(char *)"Before",.item=(char *)"OldItem",.weapon=(char *)"OldWeapon",.index=5,.itemindex=9,.weaponindex=11};
 ParseArgs(&arglist,buf,argbuf);active_args=&arglist;
 switch(cmd) {@LEVEL_DISPATCH@ default:abort();}
 assert(crlf==(cmd==CMD_LEVEL_SPAWN && cache_mode!=2));active_args=NULL;return next;
}
static int model_call(modelstxtCommands cmd,char *buf) {
 ArgList arglist;char argbuf[MAX_ARG_LEN+1]={0};int modelLoadCount=0;
 ParseArgs(&arglist,buf,argbuf);active_args=&arglist;
 switch(cmd) {@MODEL_DISPATCH@ default:abort();}
 active_args=NULL;return modelLoadCount;
}
static void same_prefix(const char *seen,const char *input,int length) {assert((int)strlen(seen)==length && !memcmp(seen,input,(size_t)length));}
static void check(unsigned revision,int level_staged,int cache_staged) {
 obor_profile_build=revision;
 const int lengths[]={1,40,120,126,127,128,160};
 const levelCommands commands[]={CMD_LEVEL_SPAWN,CMD_LEVEL_ITEM,CMD_LEVEL_2PITEM,CMD_LEVEL_3PITEM,CMD_LEVEL_4PITEM,CMD_LEVEL_WEAPON};
 const char *names[]={"spawn","item","2pitem","3pitem","4pitem","weapon"};
 char value[161],path[161],line[MAX_ARG_LEN+1];
 for(size_t n=0;n<sizeof(lengths)/sizeof(lengths[0]);n++) {
  int length=lengths[n];memset(value,'N',(size_t)length);value[length]=0;memset(path,'P',(size_t)length);path[length]=0;
  for(size_t c=0;c<sizeof(commands)/sizeof(commands[0]);c++)for(int mode=0;mode<3;mode++) {
   int wrote=snprintf(line,sizeof(line),"%s %s Sentinel\n",names[c],value);assert(wrote>0 && (size_t)wrote<sizeof(line));
   cache_mode=mode;lookup_calls=load_calls=0;seen_lookup[0]=seen_load[0]=0;
   s_spawn_entry next=level_call(commands[c],line);
   int wanted=level_staged && length>127?127:length;
   same_prefix(seen_lookup,value,wanted);assert(lookup_calls==1 && load_calls==(mode!=0));
   if(mode) same_prefix(seen_load,value,wanted);
   if(c==0)assert(next.name==(mode==2?NULL:resolved.name) && next.index==(mode==2?-1:7));
   else if(c==5)assert(!strcmp(next.weapon,mode==2?"OldWeapon":"Resolved") && next.weaponindex==(mode==2?11:7));
   else assert(!strcmp(next.item,mode==2?"OldItem":"Resolved") && next.itemindex==(mode==2?9:7));
  }
  for(int load=0;load<2;load++) {
   int wrote=snprintf(line,sizeof(line),"%s %s %s\n",load?"load":"know",value,path);assert(wrote>0 && (size_t)wrote<sizeof(line));
   cache_calls=0;seen_name[0]=seen_path[0]=0;
   assert(model_call(load?CMD_MODELSTXT_LOAD:CMD_MODELSTXT_KNOW,line)==load);
   assert(cache_calls==1 && cache_flag==load);
   int wanted=cache_staged && length>127?127:length;
   same_prefix(seen_name,value,wanted);same_prefix(seen_path,path,wanted);
  }
 }
}
int main(void) {@CHECKS@ puts("early_model_callers=1");return 0;}
'''
        replacements = dict(CONSTANTS=constants[0], ARGLIST=arglist[0], MACROS=macros[0], HELPERS=helpers,
                            LEVEL_DISPATCH=level_dispatch, MODEL_DISPATCH=model_dispatch, CHECKS='\n'.join(checks))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-model-callers-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-implicit-fallthrough', '-Wno-sign-compare', '-Wno-error=deprecated-declarations',
                     '-I' + str(engine / 'source/scriptlib'), '-I' + str(engine / 'source/gamelib')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)],
                                   capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15, env=sanitizer_environment())
            if os.environ.get('OBOR_MODEL_CALLERS_OBSERVATIONS'):
                Path(os.environ['OBOR_MODEL_CALLERS_OBSERVATIONS']).write_text(json.dumps({
                    'compiler': cc, 'flags': flags, 'contexts': len(rows), 'lengths': [1, 40, 120, 126, 127, 128, 160],
                    'probe_sha256': hashlib.sha256(program.encode()).hexdigest(),
                    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                    'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                    'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr,
                    'scope': fixture['scope'], 'retirement': 'TemporaryDirectory removes source/binary',
                }, indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_model_callers=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
