"""Check own system IDs and update callback windows with actual source cases.

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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-system-callbacks.json'
CASES = ['effectvol', 'musicvol', 'soundvol', 'current_scene', 'in_level', 'in_gameoverscreen',
         'in_menuscreen', 'in_titlescreen', 'in_halloffamescreen', 'pause', 'game_paused']


def block(text, start):
    opening = text.index('{', start)
    depth = 1
    end = opening + 1
    while depth and end < len(text):
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    if depth:
        raise AssertionError('Missing source block closure')
    return text[start:end]


class EarlySystemCallbackTests(unittest.TestCase):
    def test_names_results_and_callback_windows(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        script = (engine / 'openborscript.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        method, cases = switch_cases(core, 'getsyspropertybyindex', 'index')
        getter = re.split(r'\bswitch\s*\(index\)', method, maxsplit=1)[0]
        getter += 'switch(index){' + '\n'.join('case _e_' + name + ':' + cases['_e_' + name]['body'] for name in CASES)
        getter += 'default:return 0;}return 1;}'
        ns_start = script.index('/* Own script-visible system IDs')
        ns_end = script.index('void mapstrings_systemvariant(', ns_start)
        macro = re.search(r'(?m)^#define MAPSTRINGS\([^\n]+(?:\n[^\n]*)*?\n}', script)
        self.assertIsNotNone(macro)
        pieces = [script[ns_start:ns_end], function((engine / 'source/utils.c').read_text(), 'searchList'), macro[0],
                  function(script, 'mapstrings_systemvariant'), getter, function(script, 'openbor_systemvariant')]
        pieces += [function(variant, name) for name in ['ScriptVariant_ChangeType', 'ScriptVariant_Clear']]
        # These are source windows, not a replacement implementation of update().
        update = function(core, 'update')
        pause_at = update.index('if(!pause)')
        prefix = update[update.index('{') + 1:pause_at]
        paused = update[update.index('{', pause_at) + 1:update.index('if((level_completed', pause_at)]
        entities = re.findall(r'(?m)^\s*if[^\n]*update_ents\(\);', update)
        post = re.search(r'if[^\n]*\n\s*\{\s*execute_updatedscripts\(\);', update)
        clearing = re.search(r'(if[^\n]*)\n\s*\{\s*clearscreen\(vscreen\);', update)
        self.assertEqual(len(entities), 1)
        self.assertIsNotNone(post)
        self.assertIsNotNone(clearing)
        window = 'static void callback_window(int ingame){' + prefix + 'if(!pause){' + paused + entities[0] + '}'
        window += block(update, post.start()) + clearing[1] + '{probe_clear();}}'
        setting = function(core, 'load_script_setting')
        option = re.search(r'(?m)^\s*else if[^\n]*"alwaysupdate"[^\n]*', setting)
        self.assertIsNotNone(option)
        branch = block(setting, option.start())
        command = 'static int set_alwaysupdate(char *command,int supplied){if(0){}' + branch + 'else return 0;return 1;}'
        arrays, checks = [], []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            suffix = str(row['revision'])
            self.assertEqual(row['engine'], fixture['engine'])
            for key in ['canonical_ids', 'named_indices']:
                arrays.append('static const int ' + key + suffix + '[]={' + ','.join(map(str, row[key])) + '};')
            arrays.append('static const char *names' + suffix + '[]={' + ','.join(map(json.dumps, row['names'])) + '};')
            flags = [row[key] for key in ['in_level_inverted', 'alwaysupdate_available', 'update_outside_pause',
                                         'entity_nonzero_ingame', 'global_updated_initialized', 'clear_non_gameplay']]
            checks.append('check(%d,%d,canonical_ids%s,named_indices%s,names%s,%s);' % (
                row['revision'], len(row['names']), suffix, suffix, suffix, ','.join(str(int(x)) for x in flags)))
        canonical = fixture['canonical_names']
        ids = [canonical.index(name) for name in CASES]
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
#undef pause
#undef shutdown
#undef printf
#define time probe_time
#define pause probe_pause
#define inputrefresh probe_inputrefresh
#define execute_keyscripts probe_keyscripts
#define update_ents probe_entities
uint32_t obor_profile_build;
static char diagnostic[1024],cache[1024][256],trace[128];
static int next_cache,trace_at,mutate_pause;
static int pause,alwaysupdate,selectScreen,gameOver,menuScreen,titleScreen,hallOfFame;
static unsigned time,newtime;
static char *currentScene;
static s_level instance,*level;
static Script update_script,updated_script,sentinel;
Script *pcurrentscript;
CHAR *StrCache_Get(int index){assert(index>=0 && index<1024);return cache[index];}
void StrCache_Collect(int index){(void)index;}
int StrCache_Pop(void){assert(++next_cache<700);return next_cache;}
static int probe_printf(const char *format,...){va_list ap;va_start(ap,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,ap);va_end(ap);return n;}
#define printf probe_printf
static void event(char c){assert(trace_at+1<(int)sizeof(trace));trace[trace_at++]=c;trace[trace_at]=0;}
int Script_Execute(Script *s){assert(pcurrentscript==s);if(s==&update_script){event('U');if(mutate_pause)pause=1;}else if(s==&updated_script)event('D');else if(s==&instance.update_script)event('u');else if(s==&instance.updated_script)event('d');else abort();return S_OK;}
static void probe_inputrefresh(void){event('I');}
static void probe_keyscripts(void){event('K');}
static void probe_entities(void){event('E');}
static void probe_clear(void){event('C');}
void font_printf(int x,int y,int which,int z,char *format,...){(void)x;(void)y;(void)which;(void)z;assert(!strcmp(format,"visible"));event('T');}
@VARIANTS@
@PIECES@
@CALLBACKS@
#define GET_INT_ARG(index) supplied
@COMMAND@
#undef GET_INT_ARG
@WINDOW@
@ARRAYS@
static ScriptVariant input,result,*args[]={&input},*out;
static void setup(void){memset(&input,0,sizeof(input));memset(&result,0,sizeof(result));input.vt=VT_INTEGER;out=&result;next_cache=0;diagnostic[0]=0;}
static void expected_event(char *s,int *n,char c){s[(*n)++]=c;s[*n]=0;}
static void check(unsigned revision,int count,const int *ids,const int *resolved,const char *const *names,int inverted,int supports_always,int outside_pause,int broad_entities,int global_updated,int clear_non_gameplay){
 obor_profile_build=revision;savedata.effectvol=20;savedata.musicvol=30;savedata.soundvol=40;
 gameOver=2;menuScreen=3;titleScreen=4;hallOfFame=5;currentScene=(char*)"scene/name";pause=6;level=&instance;
 const int selected[]={@IDS@};const int expected[]={20,30,40,0,1,2,3,4,5,6,6};
 for(int i=0;i<count;i++){
  assert(obor_system_property_index(i)==ids[i]);
  setup();strcpy(cache[700],names[i]);input.vt=VT_STR;input.strVal=700;mapstrings_systemvariant(args,1);mapstrings_systemvariant(args,1);
  if(resolved[i]<0){assert(input.vt==VT_STR);assert(openbor_systemvariant(args,&out,1)==E_FAIL && !out);}
  else assert(input.vt==VT_INTEGER && input.lVal==resolved[i]);
  for(int k=0;k<11;k++)if(ids[i]==selected[k]){
   setup();input.lVal=i;assert(openbor_systemvariant(args,&out,1)==S_OK && out);
   if(k==3)assert(out->vt==VT_STR && !strcmp(StrCache_Get(out->strVal),currentScene));
   else assert(out->vt==VT_INTEGER && out->lVal==(k==4?(inverted?0:1):expected[k]));
   if(k==4){level=NULL;setup();input.lVal=i;assert(openbor_systemvariant(args,&out,1)==S_OK && out && out->lVal==inverted);level=&instance;}
   if(k==3){currentScene=NULL;setup();input.lVal=i;assert(openbor_systemvariant(args,&out,1)==E_FAIL && !out);currentScene=(char*)"scene/name";}
  }
 }
 assert(obor_system_property_index(-1)==-1 && obor_system_property_index(count)==(count==@CANONICAL_COUNT@?count:-1));
 setup();assert(openbor_systemvariant(args,&out,0)==E_FAIL && !out);
 alwaysupdate=0;assert(set_alwaysupdate((char*)"AlwaysUpdate",7)==supports_always && alwaysupdate==(supports_always?7:0));
 memset(&instance,0,sizeof(instance));instance.textobjs[0].text=(char*)"visible";
 update_script.initialized=updated_script.initialized=instance.update_script.initialized=instance.updated_script.initialized=1;time=0;
 for(int mode=0;mode<3;mode++)for(int initial_pause=0;initial_pause<2;initial_pause++)for(int always=0;always<2;always++)for(int select=0;select<2;select++)for(int mutate=0;mutate<2;mutate++){
  pause=initial_pause;alwaysupdate=always;selectScreen=select;mutate_pause=mutate;trace[0]=0;trace_at=0;pcurrentscript=&sentinel;level=&instance;
  callback_window(mode);assert(pcurrentscript==&sentinel);
  char expected_trace[128]="";int n=0;expected_event(expected_trace,&n,'I');
  int fires=outside_pause?((!initial_pause && mode==1)||always):(!initial_pause &&(mode==1||(supports_always && always)));
  if(fires){expected_event(expected_trace,&n,'U');expected_event(expected_trace,&n,'u');}
  int body=outside_pause?!(initial_pause||(fires && mutate)):!initial_pause;
  if(body &&(mode==1||select))expected_event(expected_trace,&n,'K');
  if(body &&((broad_entities?mode!=0:mode==1)||select))expected_event(expected_trace,&n,'E');
  if(mode==1||(supports_always && always)){if(global_updated)expected_event(expected_trace,&n,'D');expected_event(expected_trace,&n,'d');expected_event(expected_trace,&n,'T');}
  if(clear_non_gameplay?mode!=1:mode==0)expected_event(expected_trace,&n,'C');
  assert(!strcmp(trace,expected_trace));
 }
 level=NULL;draw_textobjs();level=&instance;instance.textobjs[0].text=NULL;
}
int main(void){@CHECKS@ puts("early_system_callbacks=1");return 0;}
'''
        substitutions = dict(VARIANTS='\n'.join(pieces[-2:]), PIECES='\n'.join(pieces[:-2]),
                             CALLBACKS='\n'.join([function(script, 'Script_IsInitialized'), function(core, 'execute_updatescripts'),
                                                  function(core, 'execute_updatedscripts'), function(core, 'draw_textobjs')]),
                             COMMAND=command, WINDOW=window, ARRAYS='\n'.join(arrays), CHECKS='\n'.join(checks),
                             IDS=','.join(map(str, ids)), CANONICAL_COUNT=str(len(canonical)))
        for key, value in substitutions.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-system-callbacks-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1', '-Dstricmp=strcasecmp',
                     '-fcommon', '-fsigned-char', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                     '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter', '-Wno-unused-variable', '-Wno-unused-function', '-Wno-sign-compare',
                     '-Wno-misleading-indentation', '-Wno-error=deprecated-declarations']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib', 'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20, env=sanitizer_environment())
            if os.environ.get('OBOR_SYSTEM_CALLBACK_OBSERVATIONS'):
                Path(os.environ['OBOR_SYSTEM_CALLBACK_OBSERVATIONS']).write_text(json.dumps(dict(compiler=cc,flags=flags,
                    contexts=len(rows),probe_sha256=hashlib.sha256(program.encode()).hexdigest(),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    core_sha256=hashlib.sha256(core.encode()).hexdigest(),script_sha256=hashlib.sha256(script.encode()).hexdigest(),
                    returncode=run.returncode,stdout=run.stdout,stderr=run.stderr,scope=fixture['scope'],retirement='TemporaryDirectory removes source/binary'),indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_system_callbacks=1', run.stdout)

    def test_missing_file_result_and_diagnostic(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        script = (engine / 'openborscript.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        pieces = [function(variant, name) for name in
                  ['ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue']]
        pieces += [function(script, 'openbor_openfilestream')]
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertIn(row['missing_file_failure'], (0, 1))
            checks.append('check(%d,%d);' % (row['revision'], row['missing_file_failure']))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include "openbor.h"
#undef exit
#undef time
#undef pause
#undef shutdown
#undef printf
uint32_t obor_profile_build;
static s_level instance,*level=&instance;
static int collections,paks,exists_checks;
static char diagnostic[256];
CHAR *StrCache_Get(int index){assert(index==0);return "absent.txt";}
void StrCache_Collect(int index){assert(index==1);collections++;}
int StrCache_Pop(void){abort();}
static int probe_printf(const char *format,...){va_list ap;va_start(ap,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,ap);va_end(ap);return n;}
static void probe_base(char *out,char *kind,int create){assert(!strcmp(kind,"Saves") && !create);strcpy(out,"/fixture");}
static int probe_exists(const char *path){assert(!strcmp(path,"/fixture/absent.txt"));exists_checks++;return 0;}
static int probe_archive(char *name,char **buffer,size_t *size){assert(!strcmp(name,"absent.txt") && !*buffer && *size==71);paks++;return 0;}
#define printf probe_printf
#define getBasePath probe_base
#define fileExists probe_exists
#define buffer_pakfile probe_archive
@PIECES@
static void check(unsigned revision,int old_failure){
 obor_profile_build=revision;
 for(int initial=0;initial<2;initial++)for(int location=-1;location<=2;location++){
  ScriptVariant name={0},where={0},result={0},*out=&result,*args[]={&name,&where};
  name.vt=VT_STR;name.strVal=0;where.vt=VT_INTEGER;where.lVal=location;
  result.vt=initial?VT_STR:VT_INTEGER;if(initial)result.strVal=1;else result.lVal=123;
  memset(level,0,sizeof(*level));level->filestreams[0].pos=9;level->filestreams[0].size=71;
  collections=paks=exists_checks=0;diagnostic[0]=0;
  HRESULT status=openbor_openfilestream(args,&out,2);
  assert(collections==initial && !level->numfilestreams && !level->filestreams[0].buf && level->filestreams[0].pos==9 && level->filestreams[0].size==71);
  if(location){
   assert(exists_checks==1 && !paks && out==&result);
   if(old_failure)assert(status==E_FAIL && result.vt==VT_EMPTY && !strcmp(diagnostic,"Openfilestream - file specified does not exist.\n"));
   else assert(status==S_OK && result.vt==VT_INTEGER && result.lVal==-1 && !diagnostic[0]);
  }else assert(!exists_checks && paks==1 && status==E_FAIL && !out && result.vt==VT_EMPTY && !strcmp(diagnostic,"Invalid filename used in openfilestream.\n"));
  ScriptVariant_Clear(&result);assert(collections==initial);
 }
}
int main(void){@CHECKS@ puts("early_stream_missing=1");return 0;}
'''
        program = program.replace('@PIECES@', '\n'.join(pieces)).replace('@CHECKS@', '\n'.join(checks))
        with tempfile.TemporaryDirectory(prefix='early-stream-missing-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                     '-fcommon', '-fsigned-char', '-fsanitize=address,undefined',
                     '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror',
                     '-Wno-unused-parameter', '-Wno-unused-variable', '-Wno-unused-function',
                     '-Wno-sign-compare', '-Wno-misleading-indentation', '-Wno-error=deprecated-declarations']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib',
                            'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']),
                                                 '-o', str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                 env=sanitizer_environment())
            if os.environ.get('OBOR_STREAM_MISSING_OBSERVATIONS'):
                Path(os.environ['OBOR_STREAM_MISSING_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=cc, flags=flags, contexts=len(rows), probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    script_sha256=hashlib.sha256(script.encode()).hexdigest(), returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr,
                    scope='Missing save-file return/tag/diagnostic and unchanged archive refusal; no real filesystem or successful read acceptance.',
                    retirement='TemporaryDirectory removes source/binary'), indent=2)+'\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_stream_missing=1', run.stdout)



if __name__ == '__main__':
    unittest.main()
