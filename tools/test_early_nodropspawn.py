"""Check command availability and the historical ordinary-entity drop window.

The actual command/list units and drop/inair bodies run. Fixed RNG/animation
providers isolate the changed window; full entity initialization is separate.
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
from test_historical_player import function, switch_cases

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-nodropspawn.json'


class EarlyNoDropSpawnTests(unittest.TestCase):
    def test_registry_and_own_source_controls(self):
        fixture = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for row in fixture['sources']:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)

    def test_command_dispatch_height_action_and_random_consumption(self):
        fixture = load_contract_fixture(FIXTURE)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        default = function(core, 'ent_default_init')
        first = default.index('dodrop = ')
        last = default.index('\n\t\t\tbreak;\n\t\t// define trap type', first)
        window = default[first:last]
        window = window[:window.rindex('}')]
        unused, cases = switch_cases(core, 'load_models', 'cmd')
        checks = '\n'.join('check(%d,%d,%d);' % (r['revision'], r['nodropspawn'], r['command_count'])
                           for r in fixture['sources'])
        code = r'''
#include <assert.h>
#include <ctype.h>
#include <math.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "commands.h"
#undef printf
uint32_t obor_profile_build;
void writeToLogFile(const char *format,...){(void)format;}
void borShutdown(int status,char *format,...){(void)status;(void)format;abort();}
void exitIfFalse(int value,const char *condition,const char *name,const char *file,int line){
 (void)condition;(void)name;(void)file;(void)line;assert(value);
}
void abortIfFalse(int value,const char *condition,const char *name,const char *file,int line){exitIfFalse(value,condition,name,file,line);}
void obor_port_assert(int value,const char *condition,const char *name,const char *file,int line){exitIfFalse(value,condition,name,file,line);}
void borExit(int reset){(void)reset;abort();}
@LOWER@
enum {SUBTYPE_ARROW=9,SCROLL_UP=1,SCROLL_DOWN=2,SCROLL_LEFT=3,SCROLL_RIGHT=4,ANI_JUMP=7};
typedef struct {float x,a,base;struct {int subtype;} modeldata;int (*takeaction)(void);} entity;
static struct {int scrolldir;} level_data,*level=&level_data;
static struct {int hRes,vRes;} videomodes={320,240};
static int advancex=100,nodropspawn,jump_available,animations,random_calls;
static float randf(float maximum){assert(maximum==40);random_calls++;return 13;}
static int common_drop(void){abort();}
static int original_action(void){abort();}
static int validanim(entity *e,int animation){assert(e && animation==ANI_JUMP);return jump_available;}
static void ent_set_anim(entity *e,int animation,int reset){assert(e && animation==ANI_JUMP && !reset);animations++;}
@DIFF@
@INAIR@
static void drop_window(entity *e){int dodrop;@WINDOW@}
static void accept_command(modelstxtCommands cmd){switch(cmd){case CMD_MODELSTXT_NODROPSPAWN:@CASE@default:abort();}}
static void check(unsigned revision,int modern,int command_count){
 obor_profile_build=revision;List *commands=createModelstxtCommandList();assert(commands);
 assert(List_GetSize(commands)==command_count);
 const char *spellings[]={"nodropspawn","NoDropSpawn","NODROPSPAWN"};
 for(unsigned i=0;i<3;i++){
  char text[32];strcpy(text,spellings[i]);nodropspawn=0;
  modelstxtCommands command=getModelstxtCommand(commands,text);
  assert(command==(modern?CMD_MODELSTXT_NODROPSPAWN:0));assert(!strcmp(text,"nodropspawn"));
  if(command){accept_command(command);assert(nodropspawn==1);}
  else assert(!nodropspawn);
 }
 char unknown[]="nodropspaw",know[]="know",older[]="nodropen";
 assert(!getModelstxtCommand(commands,unknown));
 assert(getModelstxtCommand(commands,know)==CMD_MODELSTXT_KNOW);
 assert(getModelstxtCommand(commands,older)==CMD_MODELSTXT_NODROPEN);
 freeCommandList(commands);
 const float xs[]={70,71,100,449,450,700};
 const float heights[]={-1,0,0.05f,0.1f,0.125f,253};
 const float bases[]={-2,0,0.1f,2,500};
 for(nodropspawn=0;nodropspawn<2;nodropspawn++)for(jump_available=0;jump_available<2;jump_available++)
 for(int scroll=SCROLL_UP;scroll<=SCROLL_RIGHT;scroll++)
 for(unsigned x=0;x<sizeof(xs)/sizeof(*xs);x++)
 for(unsigned a=0;a<sizeof(heights)/sizeof(*heights);a++)
 for(unsigned base=0;base<sizeof(bases)/sizeof(*bases);base++){
  entity e={0};e.x=xs[x];e.a=heights[a];e.base=bases[base];e.takeaction=original_action;
  level->scrolldir=scroll;animations=random_calls=0;
  int lift=(scroll==SCROLL_UP || scroll==SCROLL_DOWN ||
            (xs[x]>70 && xs[x]<450 && heights[a]==0)) && (!modern || !nodropspawn);
  float height=heights[a]+(lift?253:0);
  int drops=modern?(fabsf(height-bases[base])>=0.1):lift;
  drop_window(&e);
  assert(e.a==height && random_calls==lift);
  assert(e.takeaction==(drops?common_drop:original_action));
  assert(animations==(drops && jump_available));
 }
}
int main(void){@CHECKS@puts("early_nodropspawn=1");return 0;}
'''
        values = dict(LOWER=function((engine / 'source/utils.c').read_text(), 'lc'),
                      DIFF=function(core, 'diff'), INAIR=function(core, 'inair'),
                      WINDOW=window, CASE=cases['CMD_MODELSTXT_NODROPSPAWN']['body'], CHECKS=checks)
        for key, value in values.items():
            code = code.replace('@' + key + '@', value)
        code = bind_named_allocation_support(code, engine)
        with tempfile.TemporaryDirectory(prefix='early-nodropspawn-') as directory:
            source, binary = Path(directory) / 'probe.c', Path(directory) / 'probe'
            source.write_text(code)
            compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
            includes = [engine, engine / 'source', ROOT / 'src/port/libretro',
                        *sorted(p for p in (engine / 'source').iterdir() if p.is_dir())]
            flags = ['-std=gnu11', '-O0', '-g', '-fcommon', '-fsigned-char',
                     '-fno-omit-frame-pointer', '-ffunction-sections', '-fdata-sections',
                     '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=' + fixture['engine'],
                     '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
                     *['-I' + str(p) for p in includes]]
            objects = []
            for i, unit in enumerate(('source/scriptlib/List.c', 'source/gamelib/commands.c')):
                obj = Path(directory) / ('native-%d.o' % i)
                compile_checked(compiler + flags + ['-Wno-deprecated-declarations', '-c', str(engine / unit), '-o', str(obj)])
                objects.append(str(obj))
            warnings = ['-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                        '-Wno-error=sign-compare']  # Native lc uses a signed cursor and size_t length.
            if sys.platform == 'darwin':
                warnings.append('-Wno-error=pragma-pack')
            links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
            compile_checked(compiler + flags + warnings + [str(source), *objects, *links, '-lm', '-o', str(binary)])
            output = subprocess.check_output([str(binary)], text=True, timeout=30,
                                             env=sanitizer_environment())
            self.assertIn('early_nodropspawn=1', output)


if __name__ == '__main__':
    unittest.main()
