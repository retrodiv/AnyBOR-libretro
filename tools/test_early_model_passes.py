#!/usr/bin/env python3
"""Historical model-list pass and loading-call contracts."""
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
from native_allocation_policy import bind_named_allocation_support
from test_historical_player import function, switch_cases

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-model-passes.json'


class EarlyModelPassTests(unittest.TestCase):
    def test_music_filename_staging(self):
        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-model-music.json'))
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for row in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(row.get('revision', row['build']))
            if row['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        checks = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIn(row['name_limit'], (0, 127))
            checks.append('check(%d,%d);' % (row['revision'], row['name_limit']))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        _, cases = switch_cases((engine / 'openbor.c').read_text(), 'load_models', 'cmd')
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
uint32_t obor_profile_build;
static char *arguments[3],seen[512];
static int calls;
static long expected_offset;
#define GET_ARG(n) arguments[n]
static int music(char *name,int loop,long offset) {
 assert(name && strlen(name)<sizeof(seen) && loop==1 && offset==expected_offset);
 strcpy(seen,name);++calls;return 1;
}
static void dispatch(void) {
 switch(0) {case 0: @CASE@ default:abort();}
}
static void check(unsigned revision,unsigned limit) {
 static const unsigned lengths[]={0,1,126,127,128,200,500};
 static const char *offsets[]={"0","7","-17","2147483647"};
 char input[512],before[512];obor_profile_build=revision;
 for(unsigned i=0;i<sizeof(lengths)/sizeof(lengths[0]);++i) {
  unsigned length=lengths[i];
  for(unsigned j=0;j<length;++j)input[j]=(char)('a'+j%26);
  input[length]=0;memcpy(before,input,length+1);
  for(unsigned j=0;j<sizeof(offsets)/sizeof(offsets[0]);++j) {
   arguments[0]=(char*)"music";arguments[1]=input;arguments[2]=(char*)offsets[j];
   expected_offset=atol(offsets[j]);calls=0;seen[0]=0;dispatch();
   unsigned wanted=limit && length>limit?limit:length;
   if(calls!=1 || strlen(seen)!=wanted || memcmp(seen,input,wanted)) {
    fprintf(stderr,"Model music mismatch revision=%u length=%u\n",revision,length);abort();
   }
   assert(!memcmp(input,before,length+1));
  }
 }
}
int main(void) {@CHECKS@ puts("early_model_music=1");return 0;}
'''.replace('@CASE@', cases['CMD_MODELSTXT_MUSIC']['body']).replace('@CHECKS@', '\n'.join(checks))
        with tempfile.TemporaryDirectory(prefix='early-model-music-') as name:
            unit, binary = Path(name) / 'probe.c', Path(name) / 'probe'
            unit.write_text(program)
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-Wno-error=deprecated-declarations', '-fsanitize=address,undefined',
                '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', str(unit), *links, '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=10, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_model_music=1', run.stdout)

    def test_complete_loader_passes_and_progress(self):
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
        commands = (engine / 'source/gamelib/commands.c').read_text()
        utility = (engine / 'source/utils.c').read_text()
        helpers = '\n'.join(function(source, n) for n in ['ParseArgs', 'findarg', 'obor_legacy_arg',
            'isNumeric', 'getValidInt', 'obor_lookup_command',
            'obor_cache_input', 'fill_s_loadingbar', 'isLoadingScreenTypeBg', 'isLoadingScreenTypeBar'])
        helpers += '\n' + function(utility, 'lc') + '\n' + function(utility, 'getNewLineStart')
        for name in ['getCommandlistCommand', 'getModelstxtCommand', 'prepareList',
                     'createModelstxtCommandList', 'freeCommandList']:
            helpers += '\n' + function(commands, name) + '\n#undef LIST_ADD\n'
        # The actual globals and default animation tables used by the complete loader.
        start = re.search(r'(?m)^int\s+max_downs\s*=', source)
        last = re.search(r'(?ms)^int\s+follows\[MAX_FOLLOWS\].*?;', source)
        self.assertIsNotNone(start)
        self.assertIsNotNone(last)
        globals_and_tables = source[start.start():last.end()]
        macros = []
        for name in ['GET_ARG', 'GET_INT_ARG']:
            found = re.findall(r'(?m)^#define ' + name + r'\(z\)[^\n]*', source)
            self.assertEqual(len(found), 1)
            macros += found
        pointers = ['animdowns', 'animups', 'animbackwalks', 'animwalks', 'animidles',
                    'animpains', 'animdies', 'animfalls', 'animrises', 'animriseattacks',
                    'animblkpains', 'animattacks', 'animfollows', 'animspecials']
        checks = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['engine'], fixture['engine'])
            checks.append('check(%d,%d,%d);' % (row['revision'], row['passes'] == 2,
                                              row['missing_command_fatal']))
        text = ('load Hero data/hero.txt   \nmusic data/music/menu 7\nmaxidles 2\n'
                'know Helper data/helper.txt\ncolourselect 7\nmaxidles 3\nload Enemy data/enemy.txt\n')
        positions, pos = [], 0
        for line in text.splitlines(keepends=True):
            pos += len(line)
            positions.append(pos)
        program = r'''
#include <assert.h>
#include <ctype.h>
#include <setjmp.h>
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
#undef testpackfile
@MACROS@
uint32_t obor_profile_build;
@GLOBALS@
List *modelstxtcmdlist;
static s_loadingbar loadingbg[2];
static char *custModels,*custBkgrds,*packfile;
static s_screen pixels,*vscreen=&pixels;
static int colourselect,spdirection[4],autoland,nolost,ajspecial,nocost,forcecheatsoff,nodropen;
static int noaircancel,nomaxrushreset[5],mpblock,blockratio,nochipdeath,versusdamage,combodelay;
static unsigned lifescore,credscore,models_cached;
static s_modelcache cache[8];
static int old,expected_fatal,text_live,stopped;
static char *text_pointer;
static const char *input;
static char diagnostic[512];
static jmp_buf stop_target;
typedef struct {char kind;int a,b;} record;
static record events[128];
static int used;
static void event(char kind,int a,int b){assert(used<128);events[used++]=(record){kind,a,b};}
static void checked_free(void *p){if(text_live && p==text_pointer){text_live=0;event('F',0,0);}free(p);}
void writeToLogFile(const char *format,...){
 if(strstr(format,"not understood")){va_list args;va_start(args,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);assert(n>=0 && n<(int)sizeof(diagnostic));}
}
static void test_stop(int code,const char *format,...){
 va_list args;va_start(args,format);int n=vsnprintf(diagnostic,sizeof(diagnostic),format,args);va_end(args);
 assert(code==1 && n>=0 && n<(int)sizeof(diagnostic));stopped=1;longjmp(stop_target,1);
}
void obor_preload_begin(void){event('(',0,0);}
void obor_preload_end(void){event(')',0,0);}
void free_modelcache(void){
 for(unsigned i=0;i<models_cached;i++){free(cache[i].name);free(cache[i].path);}
 memset(cache,0,sizeof(cache));models_cached=0;model_cache=cache;
}
void load_background(char *name,int tables){assert(!tables && !strcmp(name,"data/bgs/loading"));event('G',0,0);}
void clearscreen(s_screen *screen){assert(screen==vscreen);event('X',0,0);}
void spriteq_clear(void){event('Q',0,0);}
void standard_palette(int immediate){assert(immediate==1);event('P',0,0);}
void lifebar_colors(void){event('B',0,0);}
void init_colourtable(void){event('T',0,0);}
int testpackfile(char *name,char *pak){(void)name;(void)pak;abort();}
int buffer_pakfile(char *name,char **buffer,size_t *size){
 assert(!strcmp(name,"data/models.txt") && !text_live);*size=strlen(input);*buffer=strdup(input);assert(*buffer);
 text_pointer=*buffer;text_live=1;event('R',0,0);return 1;
}
int music(char *name,int loop,long offset){
 assert(!strcmp(name,"data/music/menu") && loop==1 && offset==7);
 assert((animidles!=NULL)==old && max_idles==(old?3:MAX_IDLES));event('M',0,7);return 1;
}
void cache_model(char *name,char *path,int flag){
 unsigned i=models_cached;assert(i<3);
 const char *names[]={"Hero","Helper","Enemy"},*paths[]={"data/hero.txt","data/helper.txt","data/enemy.txt"};
 assert(!strcmp(name,names[i]) && !strcmp(path,paths[i]) && flag==(i!=1));
 assert((animidles!=NULL)==old);
 assert(max_idles==(old?3:i==0?MAX_IDLES:i==1?2:3));
 if(old){assert(animidles[MAX_IDLES]==OBOR_PROFILE_BASE_ANIMATIONS);assert(colourselect==(i==2?7:0));}
 cache[i].name=strdup(name);cache[i].path=strdup(path);assert(cache[i].name && cache[i].path);cache[i].loadflag=flag;models_cached++;event('C',i,flag);
}
s_model *load_cached_model(char *name,char *owner,char flag){
 assert(!strcmp(owner,"models.txt") && !flag && text_live==!old && animidles && max_idles==3 && colourselect==7);
 int id=!strcmp(name,"Hero")?0:!strcmp(name,"Enemy")?2:-1;assert(id>=0);event('L',id,0);return NULL;
}
void update_loading(s_loadingbar *s,int value,int max){assert(s==&loadingbg[0]);event('U',value,max);}
@HELPERS@
#define free checked_free
#define shutdown test_stop
@FEEDBACK@
@LOADER@
#undef shutdown
#undef free
static void release_tables(void){@RELEASE@}
static void expect(int *at,char kind,int a,int b){assert(*at<used);record r=events[(*at)++];assert(r.kind==kind && r.a==a && r.b==b);}
static void check(unsigned revision,int two_pass,int fatal){
 obor_profile_build=revision;old=two_pass;expected_fatal=fatal;
 modelstxtcmdlist=createModelstxtCommandList();assert(modelstxtcmdlist);
 int modes[]={0,-1,1,2,3,257};
 for(size_t m=0;m<sizeof(modes)/sizeof(modes[0]);m++){
  used=0;stopped=0;diagnostic[0]=0;colourselect=0;input=@INPUT@;
  memset(loadingbg,0,sizeof(loadingbg));fill_s_loadingbar(&loadingbg[0],modes[m],2,3,4,5,6,1,100);
  if(setjmp(stop_target)==0)assert(load_models()==1);else assert(0);
  assert(!stopped && !diagnostic[0] && !text_live && models_cached==3 && animidles && max_idles==3);
  int at=0;expect(&at,'(',0,0);
  if(old){
   if(modes[m]>0)expect(&at,'G',0,0);
   else if(modes[m]<0){expect(&at,'X',0,0);expect(&at,'Q',0,0);}
   if(modes[m]){expect(&at,'P',0,0);expect(&at,'B',0,0);expect(&at,'T',0,0);}
  }else{
   if(modes[m]==1 || modes[m]==2 || modes[m]==257){expect(&at,'G',0,0);expect(&at,'P',0,0);}
   if(modes[m]==1 || modes[m]==3 || modes[m]==257){expect(&at,'B',0,0);expect(&at,'T',0,0);}
   expect(&at,'U',-1,1);
  }
  expect(&at,'R',0,0);
  const int positions[]={@POSITIONS@};int total=(int)strlen(input);
  for(int line=0;line<7;line++){
   if(line==0)expect(&at,'C',0,1);
   if(line==1)expect(&at,'M',0,7);
   if(line==3)expect(&at,'C',1,0);
   if(line==6)expect(&at,'C',2,1);
   if(old && modes[m])expect(&at,'U',positions[line]/2,total);
  }
  if(old)expect(&at,'F',0,0);
  for(int i=0;i<3;i++){
   if(old && modes[m])expect(&at,'U',total/2+i*total/2/3,total);
   if(i!=1){expect(&at,'L',i,0);if(!old)expect(&at,'U',i==0?1:2,2);}
  }
  if(!old)expect(&at,'F',0,0);
  expect(&at,')',0,0);assert(at==used);
  release_tables();free_modelcache();
 }
 input="mystery 1\n";used=stopped=0;diagnostic[0]=0;memset(loadingbg,0,sizeof(loadingbg));
 if(setjmp(stop_target)==0)assert(load_models()==1);
 assert(stopped==expected_fatal);
 if(old)assert(!strcmp(diagnostic,"Command 'mystery' not understood in file 'data/models.txt'!"));
 else assert(!diagnostic[0] && max_idles==MAX_IDLES); /* Own unknown name maps to enum0/maxidles. */
 if(text_live){free(text_pointer);text_live=0;}
 release_tables();free_modelcache();freeCommandList(modelstxtcmdlist);modelstxtcmdlist=NULL;
}
int main(void){@CHECKS@puts("early_model_passes=1");return 0;}
'''
        replacements = dict(MACROS='\n'.join(macros), GLOBALS=globals_and_tables, HELPERS=helpers,
                            FEEDBACK=function(source, 'obor_profile_file_feedback'),
                            LOADER=function(source, 'load_models'), INPUT=json.dumps(text),
                            POSITIONS=','.join(map(str, positions)), CHECKS='\n'.join(checks),
                            RELEASE=''.join('free(%s);%s=NULL;' % (n, n) for n in pointers))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-model-passes-') as name:
            work = Path(name)
            unit, obj, binary = work / 'probe.c', work / 'list.o', work / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-DSAFEALLOC_H=1',
                     '-fcommon', '-fsigned-char', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                     '-fno-omit-frame-pointer', '-Dstricmp=strcasecmp']
            for include in ['', 'source', 'source/gamelib', 'source/gfxlib', 'source/scriptlib',
                            'source/preprocessorlib', 'source/randlib', 'source/ramlib']:
                flags += ['-I', str(engine / include)]
            flags += ['-I', str(ROOT / 'src/port/libretro'), '-I', str(ROOT / 'src/glue')]
            build = subprocess.run(cc + flags + ['-c', str(engine / 'source/scriptlib/List.c'), '-o', str(obj)],
                                   capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            build = subprocess.run(cc + flags + ['-Wall', '-Wextra', '-Werror', '-Wno-unused-variable',
                '-Wno-unused-function', '-Wno-sign-compare', '-Wno-implicit-fallthrough',
                '-Wno-error=deprecated-declarations', str(unit), str(obj),
                *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30,
                                 env=sanitizer_environment())
            if os.environ.get('OBOR_MODEL_PASSES_OBSERVATIONS'):
                Path(os.environ['OBOR_MODEL_PASSES_OBSERVATIONS']).write_text(json.dumps(dict(
                    compiler=cc, flags=flags, contexts=len(rows), returncode=run.returncode,
                    stdout=run.stdout, stderr=run.stderr,
                    probe_sha256=hashlib.sha256(program.encode()).hexdigest(),
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    scope=fixture['scope'], retirement='TemporaryDirectory removes source/object/binary'), indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_model_passes=1', run.stdout)


if __name__ == '__main__':
    unittest.main()

