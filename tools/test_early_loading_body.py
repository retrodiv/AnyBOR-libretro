#!/usr/bin/env python3
"""Historical loading rendering and argument contracts."""
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 retrodiv <retrodiv@proton.me>
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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-loading-body.json'


class EarlyLoadingBodyTests(unittest.TestCase):
    def test_arguments_cadence_draw_order_and_input(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {r['revision'] for r in rows}
        self.assertEqual(len(rows), len(revisions))
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        pieces = [function(source, n) for n in [
            'inputrefresh', 'fill_s_loadingbar', 'isLoadingScreenTypeBg',
            'isLoadingScreenTypeBar', 'obor_update_loading_legacy', 'update_loading']]
        counter = re.findall(r'^static size_t obor_loading_ticks = 0;$', source, re.M)
        self.assertEqual(len(counter), 1)
        defines = '\n'.join(line for line in source.splitlines() if
                            line.startswith(('#define MIN_INT', '#define MAX_INT', '#define MOVIEBUF_LEN')))
        self.assertEqual(len(defines.splitlines()), 3)
        checks = []
        for index, row in enumerate(rows):
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            checks.append('case %d:check(%d,%d,%d,%d);break;' % (
                index, row['revision'], row['modern'], row['input_mode'], row['throttled']))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "openbor.h"
#undef exit
#undef time
#undef pause
#undef shutdown
@DEFINES@
uint32_t obor_profile_build;
static s_screen pixels,bg,*vscreen=&pixels,*background=&bg;
static s_videomodes videomodes;
static s_barstatus loadingbarstatus;
static s_player player[4];
static s_playercontrols controls[4];
static s_playercontrols *playercontrolpointers[4]={&controls[0],&controls[1],&controls[2],&controls[3]};
static int maxplayers[1]={2},current_set,movieplay,movielog,pause,movieloglen,moviebufptr,movielen;
static unsigned interval,bothkeys,bothnewkeys;
static int queue,draw_queue,polls,expect_poll,expect_x,expect_y,expect_tx,expect_ty,expect_size,expect_value;
static char trace[4096];
static int at;
@COUNTER@
static void event(char c){assert(at+1<(int)sizeof(trace));trace[at++]=c;trace[at]=0;}
void writeToLogFile(const char *format,...){(void)format;abort();}
void sound_update_music(void){event('S');}
void control_update(s_playercontrols **p,int count){assert(p==playercontrolpointers && count==expect_poll);polls++;event('I');}
unsigned timer_getinterval(unsigned freq){assert(freq==GAME_SPEED);event('R');return GAME_SPEED+1;}
void movie_update(s_playercontrols **p){(void)p;abort();}
void movie_save(s_playercontrols **p){(void)p;abort();}
void movie_closefile(void){abort();}
void movie_flushbuf(void){abort();}
void font_printf(int x,int y,int font,int layer,char *format,...){
 assert(x==expect_tx && y==expect_ty && font==2 && layer==0 && !strcmp(format,"Loading..."));queue++;event('T');
}
void bar(int x,int y,int value,int max,s_barstatus *status){
 assert(x==expect_x && y==expect_y && value==expect_value && max==100 && status==&loadingbarstatus && status->sizex==(short)expect_size);queue++;event('B');
}
void putscreen(s_screen *dst,s_screen *src,int x,int y,s_drawmethod *method){assert(dst==vscreen && src==background && !x && !y && !method);event('P');}
void clearscreen(s_screen *s){assert(s==vscreen);event('X');}
void spriteq_clear(void){queue=0;event('C');}
void spriteq_draw(s_screen *s,int only,int minz,int maxz){assert(s==vscreen && !only && minz==MIN_INT && maxz==MAX_INT);draw_queue=queue;event('D');}
int video_copy_screen(s_screen *s){assert(s==vscreen);event('V');return 1;}
unsigned timer_gettick(void){abort();}
void execute_loading_script(int value,int max){(void)value;(void)max;abort();}
@PIECES@
static void check(unsigned revision,int modern,int input_mode,int throttled){
 obor_profile_build=revision;
 s_loadingbar s={0};
 assert(!fill_s_loadingbar(&s,257,70000,80000,90000,100000,110000,65538,0));
 if(modern){
  assert(s.set==(LSTYPE_BACKGROUND|LSTYPE_BAR) && s.bx==(short)70000 && s.by==(short)80000);
  assert(s.bsize==(short)90000 && s.tx==(short)100000 && s.ty==(short)110000 && s.tf==(char)65538 && s.refreshMs==100);
  assert(!fill_s_loadingbar(&s,2,1,2,3,4,5,2,70000) && s.set==LSTYPE_BACKGROUND && s.refreshMs==(short)70000);
  return; /* Modern renderer and callbacks are covered by their own contract. */
 }
 int raw[]={257,70000,80000,90000,100000,110000,65538};
 assert(!memcmp(s.legacy_args,raw,sizeof(raw)));
 assert(!fill_s_loadingbar(&s,-9,70000,80000,90000,100000,110000,2,1));
 assert(s.set==LSTYPE_BAR && s.legacy_args[0]==-9 && s.legacy_args[6]==2);
 videomodes.hShift=7;videomodes.vShift=-3;
 expect_x=70007;expect_y=79997;expect_size=90000;expect_tx=100007;expect_ty=109997;
 expect_poll=input_mode==1?2:1;
 for(int phase=0;phase<2;phase++){
  int count=phase?13:20; /* The second load continues the first load's cadence. */
  for(int j=0;j<count;j++){
   int n=phase?20+j:j;int paint=!throttled || n%16==0;
   background=n%2?NULL:&bg;queue=7;draw_queue=-1;polls=at=0;trace[0]=0;
   memset(player,0,sizeof(player));memset(controls,0,sizeof(controls));
   player[0].keys=4;player[0].playkeys=4;controls[0].keyflags=2;controls[0].newkeyflags=2;
   bothkeys=bothnewkeys=8;interval=999;expect_value=n==15?-1:n==31?100:n;
   update_loading(&s,expect_value,100);
   char want[64]={0};
   if(throttled)strcat(want,"S");
   if(paint){
    strcat(want,background?"TBPDVC":"TBXDVC");
    if(!throttled)strcat(want,"S");
    if(input_mode==1)strcat(want,"IR");else if(input_mode==2)strcat(want,"I");
   }
   assert(!strcmp(trace,want) && polls==(paint && input_mode!=0));
   assert(draw_queue==(paint?9:-1) && queue==(paint?0:7));
   if(paint && input_mode==1){
    assert(player[0].keys==2 && player[0].newkeys==2 && player[0].releasekeys==4 && player[0].playkeys==2);
    assert(bothkeys==2 && bothnewkeys==2 && interval==1);
   }else assert(player[0].keys==4 && bothkeys==8 && bothnewkeys==8 && interval==999);
  }
 }
 assert(obor_loading_ticks==(throttled?33:0));
 if(throttled){
  obor_loading_ticks=SIZE_MAX;queue=7;at=0;trace[0]=0;
  update_loading(&s,expect_value,100);assert(!strcmp(trace,"S") && !obor_loading_ticks && queue==7);
  at=0;trace[0]=0;update_loading(&s,expect_value,100);
  assert(obor_loading_ticks==1 && !strcmp(trace,background?"STBPDVCI":"STBXDVCI"));
 }
}
int main(int argc,char **argv){assert(argc==2);switch(atoi(argv[1])){@CHECKS@default:abort();}puts("early_loading_body=1");return 0;}
'''
        program = program.replace('@DEFINES@', defines).replace('@COUNTER@', counter[0])
        program = program.replace('@PIECES@', '\n'.join(pieces)).replace('@CHECKS@', '\n'.join(checks))
        with tempfile.TemporaryDirectory(prefix='early-loading-body-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                     '-fcommon', '-fsigned-char', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                     '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror', '-Wno-unused-variable',
                     '-Wno-unused-function', '-Wno-sign-compare', '-Wno-error=deprecated-declarations']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib',
                            'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']),
                                                  '-o', str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            runs = []
            for index, row in enumerate(rows):
                run = subprocess.run([str(binary), str(index)], capture_output=True, text=True,
                                     timeout=20, env=sanitizer_environment())
                runs.append(dict(revision=row['revision'], returncode=run.returncode,
                                 stdout=run.stdout, stderr=run.stderr))
                if run.returncode:
                    break
            if os.environ.get('OBOR_LOADING_BODY_OBSERVATIONS'):
                Path(os.environ['OBOR_LOADING_BODY_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=cc, flags=flags, contexts=len(rows), executed=len(runs), runs=runs,
                    probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    scope=fixture['scope'], retirement='TemporaryDirectory removes source/binary'), indent=2) + '\n')
            for run in runs:
                self.assertEqual(run['returncode'], 0, str(run))
                self.assertIn('early_loading_body=1', run['stdout'])
            self.assertEqual(len(runs), len(rows))



    def test_level_loading_callers(self):
        fixture = load_contract_fixture(Path(__file__).parent / 'fixtures/profile-early-level-loading.json')
        rows = fixture['sources']
        revisions = {r['revision'] for r in rows}
        self.assertEqual(len(rows), len(revisions))
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        loader = function(source, 'load_level')
        # Exact active caller regions, without the unrelated full level parser.
        start = loader.index('\n\tgetRamStatus(BYTES);') + len('\n\tgetRamStatus(BYTES);')
        end = loader.index('\n\tmemset(&next, 0, sizeof(s_spawn_entry));', start)
        initial = loader[start:end]
        _, cases = switch_cases(loader.replace('switch(cmd)', 'switch(level_command)', 1), 'load_level', 'level_command')
        command_case = cases['CMD_LEVEL_LOADINGBG']['body']
        progress = loader.rsplit('\t\tpos += getNewLineStart(buf + pos);', 1)[1].split('\n\t}', 1)[0]
        self.assertIn('update_loading(&bgPosi, pos, size)', progress)
        self.assertIn('update_loading(&loadingbg[1], pos, size)', progress)
        macros = []
        for name in ['GET_ARG', 'GET_INT_ARG']:
            found = re.findall(r'(?m)^#define ' + name + r'\(z\)[^\n]*', source)
            self.assertEqual(len(found), 1)
            macros += found
        pieces = [function(source, n) for n in ['ParseArgs', 'findarg', 'obor_legacy_arg',
                  'isNumeric', 'getValidInt', 'fill_s_loadingbar', 'isLoadingScreenTypeBg', 'isLoadingScreenTypeBar']]
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            checks.append('check(%d,%d,%d,%d);' % (row['revision'], row['legacy'],
                                                  row['initial_descriptor'], row['background_arguments']))
        program = r'''
#include <assert.h>
#include <ctype.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#include "commands.h"
#undef exit
#undef time
#undef pause
#undef shutdown
@MACROS@
uint32_t obor_profile_build;
static s_loadingbar loadingbg[2],bgPosi;
static s_screen pixels,*vscreen=&pixels;
static char *custBkgrds;
static char string[4096];
static char trace[128],seen[4096];
static int at,calls,last_value,last_max;
static s_loadingbar *last;
static void event(char c){assert(at+1<(int)sizeof(trace));trace[at++]=c;trace[at]=0;}
void writeToLogFile(const char *format,...){(void)format;}
void load_background(char *path,int tables){assert(!tables && strlen(path)<sizeof(seen));strcpy(seen,path);event('L');}
void load_cached_background(char *path,int tables){assert(!tables && !strcmp(path,"data/bgs/loading2"));event('K');}
void clearscreen(s_screen *screen){assert(screen==vscreen);event('X');}
void spriteq_clear(void){event('C');}
void standard_palette(int immediate){assert(immediate==1);event('P');}
void lifebar_colors(void){event('B');}
void init_colourtable(void){event('T');}
void update_loading(s_loadingbar *s,int value,int max){last=s;last_value=value;last_max=max;calls++;event('U');}
@PIECES@
static void reset(void){at=calls=0;trace[0]=seen[0]=0;last=NULL;last_value=last_max=0;}
static void begin_level(void){@INITIAL@}
static void background_command(char *buf){
 ArgList arglist;char argbuf[MAX_ARG_LEN+1]={0},*filename=(char *)"data/level.txt",*command=(char *)"loadingbg",*errormessage=NULL;
 ParseArgs(&arglist,buf,argbuf);
 switch(CMD_LEVEL_LOADINGBG){case CMD_LEVEL_LOADINGBG:@COMMAND_CASE@ default:abort();}
 return;
lCleanup:abort();
}
static void progress_line(int pos,int size){@PROGRESS@}
static void check(unsigned revision,int legacy,int initial_descriptor,int argument_kind){
 obor_profile_build=revision;
 int modes[]={-1,0,1,2,3,257};
 for(size_t m=0;m<sizeof(modes)/sizeof(modes[0]);m++){
  int mode=modes[m];
  for(int custom=0;custom<2;custom++){
   memset(loadingbg,0,sizeof(loadingbg));
   fill_s_loadingbar(&loadingbg[0],1,17,18,19,20,21,2,100);
   fill_s_loadingbar(&loadingbg[1],mode,2,3,4,5,6,2,100);
   custBkgrds=custom?(char *)"alt/":NULL;reset();begin_level();
   char expected[64]={0};
   if(legacy){
    if(mode>0)strcat(expected,custom?"L":"K");
    else if(mode<0)strcat(expected,"XC");
    if(mode)strcat(expected,"PBT");
   }else{
    if(mode==1 || mode==2 || mode==257)strcat(expected,custom?"LXCP":"KXCP");
    if(mode==1 || mode==3 || mode==257)strcat(expected,"BT");
    strcat(expected,"U");
   }
   assert(!strcmp(trace,expected) && calls==!legacy);
   if(!legacy)assert(last==&loadingbg[initial_descriptor] && last_value==-1 && last_max==1);
   if(custom && (legacy?mode>0:mode==1 || mode==2 || mode==257))assert(!strcmp(seen,"alt/loading2"));
  }
 }
 memset(&bgPosi,0,sizeof(bgPosi));reset();
 background_command((char *)"loadingbg Scene 2 202 303 404 505 2 7 909");
 assert(!strcmp(seen,"Scene") && !strcmp(trace,legacy?"LPBT":"LPBTU"));
 assert(calls==!legacy);
 if(legacy){
  int expected[]={1,2,202,303,404,505,2};assert(!memcmp(bgPosi.legacy_args,expected,sizeof(expected)));
 }else if(argument_kind==1){
  assert(bgPosi.set==(LSTYPE_BACKGROUND|LSTYPE_BAR) && bgPosi.bx==2 && bgPosi.by==202 && bgPosi.bsize==303);
  assert(bgPosi.tx==404 && bgPosi.ty==505 && bgPosi.tf==2 && bgPosi.refreshMs==7);
 }else{
  assert(bgPosi.set==LSTYPE_BACKGROUND && bgPosi.bx==202 && bgPosi.by==303 && bgPosi.bsize==404);
  assert(bgPosi.tx==505 && bgPosi.ty==2 && bgPosi.tf==7 && bgPosi.refreshMs==909);
 }
 if(!legacy)assert(last==&bgPosi && last_value==-1 && last_max==1);
 // A zero local width selects the global descriptor only in the old format.
 for(int local=0;local<4;local++)for(int global=0;global<2;global++){
  memset(&bgPosi,0,sizeof(bgPosi));memset(&loadingbg[1],0,sizeof(loadingbg[1]));
  int width=local&1?27:0,mode=local&2?1:0;
  fill_s_loadingbar(&bgPosi,mode,1,2,width,4,5,2,100);
  fill_s_loadingbar(&loadingbg[1],global?-1:0,6,7,8,9,10,2,100);
  reset();progress_line(37,123);
  int use_local=legacy?width!=0:mode!=0;
  assert(calls==(use_local || global || !legacy));
  if(calls)assert(last==(use_local?&bgPosi:&loadingbg[1]) && last_value==37 && last_max==123 && !strcmp(trace,"U"));
  else assert(!trace[0]);
 }
}
int main(void){@CHECKS@puts("early_level_loading=1");return 0;}
'''
        program = (program.replace('@MACROS@', '\n'.join(macros)).replace('@PIECES@', '\n'.join(pieces))
                   .replace('@INITIAL@', initial).replace('@COMMAND_CASE@', command_case)
                   .replace('@PROGRESS@', progress).replace('@CHECKS@', '\n'.join(checks)))
        with tempfile.TemporaryDirectory(prefix='early-level-loading-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                     '-fcommon', '-fsigned-char', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                     '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror', '-Wno-unused-variable',
                     '-Wno-unused-function', '-Wno-implicit-fallthrough', '-Wno-sign-compare', '-Wno-error=deprecated-declarations']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib',
                            'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']),
                                                  '-o', str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                 env=sanitizer_environment())
            if os.environ.get('OBOR_LEVEL_LOADING_OBSERVATIONS'):
                Path(os.environ['OBOR_LEVEL_LOADING_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=cc, flags=flags, contexts=len(rows), returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr,
                    probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    scope=fixture['scope'], retirement='TemporaryDirectory removes source/binary'), indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_level_loading=1', run.stdout)



    def test_global_defaults_and_persistence(self):
        fixture = load_contract_fixture(Path(__file__).parent / 'fixtures/profile-early-loading-defaults.json')
        rows = fixture['sources']
        revisions = {r['revision'] for r in rows}
        self.assertEqual(len(rows), len(revisions))
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        loader = function(source, 'load_levelorder')
        global_definition = re.findall(r'(?m)^s_loadingbar[\t ]+loadingbg\[2\][^;]*;', source)
        call = re.findall(r'for\(i=0; i<2; i\+\+\) obor_loading_defaults\(&loadingbg\[i\]\);', loader)
        self.assertEqual((len(global_definition), len(call)), (1, 1))
        self.assertLess(loader.index(call[0]), loader.rindex('branch_name[0]'))
        self.assertNotIn('loadingbg', function(source, 'unload_levelorder'))
        _, cases = switch_cases(loader.replace('switch(cmd)', 'switch(order_command)', 1),
                                'load_levelorder', 'order_command')
        dispatch = '\n'.join('case %s:%s' % (n, cases[n]['body']) for n in
                             ['CMD_LEVELORDER_LOADINGBG', 'CMD_LEVELORDER_LOADINGBG2'])
        helpers = '\n'.join(function(source, n) for n in ['ParseArgs', 'findarg', 'obor_legacy_arg',
                           'isNumeric', 'getValidInt', 'fill_s_loadingbar', 'obor_loading_defaults'])
        macros = []
        for name in ['GET_ARG', 'GET_INT_ARG']:
            found = re.findall(r'(?m)^#define ' + name + r'\(z\)[^\n]*', source)
            self.assertEqual(len(found), 1)
            macros += found
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            checks.append('check(%d,%d,%d);' % (row['revision'], row['legacy'], row['implicit_coordinates']))
        program = r'''
#include <assert.h>
#include <ctype.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "openbor.h"
#include "commands.h"
#undef exit
#undef time
#undef pause
#undef shutdown
@MACROS@
uint32_t obor_profile_build;
@GLOBAL@
static s_loadingbar initial[2];
static s_videomodes videomodes;
static char diagnostic[128];
void writeToLogFile(const char *format,...){va_list args;va_start(args,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);assert(n>=0 && n<(int)sizeof(diagnostic));}
@HELPERS@
static void defaults(void){int i;@CALL@}
static void command(char *buf){
 ArgList arglist;char argbuf[MAX_ARG_LEN+1]={0},*filename=(char *)"data/levels.txt",*command=NULL,*errormessage=NULL;
 ParseArgs(&arglist,buf,argbuf);command=GET_ARG(0);
 levelOrderCommands cmd=!strcmp(command,"loadingbg2")?CMD_LEVELORDER_LOADINGBG2:CMD_LEVELORDER_LOADINGBG;
 switch(cmd){@DISPATCH@default:abort();}
 return;
lCleanup:abort();
}
static void check(unsigned revision,int legacy,int implicit){
 obor_profile_build=revision;
 struct geometry {int w,h,x,y;float scale;int expected[5];};
 const struct geometry cases[]={
  {320,240,7,3,1.5f,{-8,228,321,139,117}},
  {1920,1080,-11,-5,0.75f,{10,1068,1921,971,545}},
  {32767,900,13,-17,2.5f,{-14,888,32768,16342,467}}
 };
 for(size_t n=0;n<sizeof(cases)/sizeof(cases[0]);n++){
  memcpy(loadingbg,initial,sizeof(loadingbg));
  videomodes.hRes=cases[n].w;videomodes.vRes=cases[n].h;
  videomodes.hShift=cases[n].x;videomodes.vShift=cases[n].y;videomodes.hScale=cases[n].scale;
  defaults();
  for(int i=0;i<2;i++){
   if(implicit){
    int expected[]={-1,cases[n].expected[0],cases[n].expected[1],cases[n].expected[2],cases[n].expected[3],cases[n].expected[4],0};
    if(memcmp(loadingbg[i].legacy_args,expected,sizeof(expected))){fprintf(stderr,"revision=%u geometry=%zu slot=%d actual=%d,%d,%d,%d,%d,%d,%d expected=%d,%d,%d,%d,%d,%d,%d\n",revision,n,i,loadingbg[i].legacy_args[0],loadingbg[i].legacy_args[1],loadingbg[i].legacy_args[2],loadingbg[i].legacy_args[3],loadingbg[i].legacy_args[4],loadingbg[i].legacy_args[5],loadingbg[i].legacy_args[6],expected[0],expected[1],expected[2],expected[3],expected[4],expected[5],expected[6]);}assert(!memcmp(loadingbg[i].legacy_args,expected,sizeof(expected)));
   }else assert(loadingbg[i].set==LSTYPE_NONE && !loadingbg[i].bx && !loadingbg[i].by && !loadingbg[i].bsize && !loadingbg[i].tx && !loadingbg[i].ty && !loadingbg[i].tf && !loadingbg[i].refreshMs);
  }
  s_loadingbar before[2];memcpy(before,loadingbg,sizeof(before));
  videomodes.hRes=640;videomodes.vRes=480;videomodes.hShift=0;videomodes.vShift=0;videomodes.hScale=3;
  defaults();assert(!memcmp(before,loadingbg,sizeof(before))); /* Stored width prevents recalculation. */
 }
 memcpy(loadingbg,initial,sizeof(loadingbg));
 videomodes.hRes=320;videomodes.vRes=240;videomodes.hShift=7;videomodes.vShift=3;videomodes.hScale=1.5f;
 defaults();s_loadingbar first;memcpy(&first,&loadingbg[0],sizeof(first));
 diagnostic[0]=0;command((char *)"loadingbg2 -2 111 222 0 333 444 3 777");defaults();
 assert(!memcmp(&first,&loadingbg[0],sizeof(first))); /* Other global descriptor persists. */
 if(legacy){
  int expected[]={-2,-8,228,321,139,117,3};assert(!memcmp(loadingbg[1].legacy_args,expected,sizeof(expected)) && !diagnostic[0]);
 }else assert(loadingbg[1].set==LSTYPE_NONE && loadingbg[1].bx==111 && loadingbg[1].by==222 && !loadingbg[1].bsize && loadingbg[1].tx==333 && loadingbg[1].ty==444 && loadingbg[1].tf==3 && loadingbg[1].refreshMs==777 && !strcmp(diagnostic,"invalid loadingbg type -2!\n"));
 diagnostic[0]=0;command((char *)"loadingbg 1 70000 80000 90000 100000 110000 65538 70000");
 if(legacy){int expected[]={1,70000,80000,90000,100000,110000,65538};assert(!memcmp(loadingbg[0].legacy_args,expected,sizeof(expected)));}
 else assert(loadingbg[0].set==(LSTYPE_BACKGROUND|LSTYPE_BAR) && loadingbg[0].bx==(short)70000 && loadingbg[0].by==(short)80000 && loadingbg[0].bsize==(short)90000 && loadingbg[0].tx==(short)100000 && loadingbg[0].ty==(short)110000 && loadingbg[0].tf==(char)65538 && loadingbg[0].refreshMs==(short)70000);
 assert(!diagnostic[0]);
 s_loadingbar before[2];memcpy(before,loadingbg,sizeof(before));defaults();assert(!memcmp(before,loadingbg,sizeof(before)));
 command((char *)"loadingbg -1 10 20 7 40 50 6 0");
 memcpy(before,loadingbg,sizeof(before));defaults();assert(!memcmp(before,loadingbg,sizeof(before))); /* Explicit width is kept. */
 command((char *)"loadingbg 0 10 20 0 40 50 6 0");
 memcpy(before,loadingbg,sizeof(before));defaults();assert(!memcmp(before,loadingbg,sizeof(before))); /* Disabled mode is not implicit. */
 int modes[]={-1,0,1,2,3,4,257,-257};
 for(size_t n=0;n<sizeof(modes)/sizeof(modes[0]);n++){
  char line[256];int count=snprintf(line,sizeof(line),"loadingbg %d 12 23 34 45 56 2 0",modes[n]);assert(count>0 && count<(int)sizeof(line));
  diagnostic[0]=0;command(line);defaults();
  if(legacy){
   int expected[]={modes[n],12,23,34,45,56,2};if(memcmp(loadingbg[0].legacy_args,expected,sizeof(expected)) || diagnostic[0])fprintf(stderr,"revision=%u mode=%d actual=%d,%d,%d,%d,%d,%d,%d expected=%d,%d,%d,%d,%d,%d,%d diagnostic=[%s]\n",revision,expected[0],loadingbg[0].legacy_args[0],loadingbg[0].legacy_args[1],loadingbg[0].legacy_args[2],loadingbg[0].legacy_args[3],loadingbg[0].legacy_args[4],loadingbg[0].legacy_args[5],loadingbg[0].legacy_args[6],expected[0],expected[1],expected[2],expected[3],expected[4],expected[5],expected[6],diagnostic);assert(!memcmp(loadingbg[0].legacy_args,expected,sizeof(expected)) && !diagnostic[0]);
  }else{
   int mode=(char)modes[n];loadingScreenType expected=mode==1?LSTYPE_BACKGROUND|LSTYPE_BAR:mode==2?LSTYPE_BACKGROUND:mode==3?LSTYPE_BAR:LSTYPE_NONE;
   assert(loadingbg[0].set==expected && loadingbg[0].tf==2 && loadingbg[0].refreshMs==100);
   if(mode<0 || mode>3){char warning[128];snprintf(warning,sizeof(warning),"invalid loadingbg type %d!\n",mode);assert(!strcmp(diagnostic,warning));}
   else assert(!diagnostic[0]);
  }
 }
 diagnostic[0]=0;command((char *)"loadingbg -1\n");defaults();
 if(legacy){int expected[]={-1,-8,228,321,139,117,0};if(memcmp(loadingbg[0].legacy_args,expected,sizeof(expected)) || diagnostic[0])fprintf(stderr,"revision=%u mode=%d actual=%d,%d,%d,%d,%d,%d,%d expected=%d,%d,%d,%d,%d,%d,%d diagnostic=[%s]\n",revision,expected[0],loadingbg[0].legacy_args[0],loadingbg[0].legacy_args[1],loadingbg[0].legacy_args[2],loadingbg[0].legacy_args[3],loadingbg[0].legacy_args[4],loadingbg[0].legacy_args[5],loadingbg[0].legacy_args[6],expected[0],expected[1],expected[2],expected[3],expected[4],expected[5],expected[6],diagnostic);assert(!memcmp(loadingbg[0].legacy_args,expected,sizeof(expected)) && !diagnostic[0]);}
 else assert(loadingbg[0].set==LSTYPE_NONE && !loadingbg[0].tf && !loadingbg[0].bx && !loadingbg[0].bsize && loadingbg[0].refreshMs==100 && !strcmp(diagnostic,"invalid loadingbg type -1!\n"));
}
int main(void){memcpy(initial,loadingbg,sizeof(initial));@CHECKS@puts("early_loading_defaults=1");return 0;}
'''
        program = (program.replace('@MACROS@', '\n'.join(macros)).replace('@GLOBAL@', global_definition[0])
                   .replace('@HELPERS@', helpers).replace('@CALL@', call[0]).replace('@DISPATCH@', dispatch)
                   .replace('@CHECKS@', '\n'.join(checks)))
        with tempfile.TemporaryDirectory(prefix='early-loading-defaults-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                     '-fcommon', '-fsigned-char', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                     '-fno-omit-frame-pointer', '-Wall', '-Wextra', '-Werror', '-Wno-unused-variable',
                     '-Wno-unused-function', '-Wno-sign-compare', '-Wno-implicit-fallthrough',
                     '-Wno-error=deprecated-declarations']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib',
                            'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']),
                                                  '-o', str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                 env=sanitizer_environment())
            if os.environ.get('OBOR_LOADING_DEFAULTS_OBSERVATIONS'):
                Path(os.environ['OBOR_LOADING_DEFAULTS_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=cc, flags=flags, contexts=len(rows), returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr,
                    probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    scope=fixture['scope'], retirement='TemporaryDirectory removes source/binary'), indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_loading_defaults=1', run.stdout)


if __name__ == '__main__':
    unittest.main()

