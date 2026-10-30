"""Check music lookahead, offsets and cursor restoration against own sources.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-level-music.json'


class EarlyLevelMusicTests(unittest.TestCase):
    def test_music_case_and_original_lookahead(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        self.assertEqual((min(revisions), max(revisions)), tuple(fixture['range']))
        profiles = json.loads((ROOT / 'src/pin.json').read_text())['profiles']
        for profile in contract_profiles(fixture, profiles):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        cases, arrays, checks = [], [], []
        for case in fixture['cases']:
            self.assertTrue(len(case['prefix']) + len(case['input']) < 256)
            self.assertIn(case['fade'], (0, 0.5))
            self.assertIn(case['immediate'], (0, 1))
            cases.append('{%s,%s,%s,%d}' % (json.dumps(case['prefix']),
                         json.dumps(case['input']), str(case['fade']), case['immediate']))
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')
            self.assertRegex(row['load_level_sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(len(row['routes']), len(cases))
            self.assertTrue(all(type(route) is int and route in (1, 2, 3)
                                for route in row['routes']))
            name = 'routes_' + str(row['revision'])
            arrays.append('static const int %s[]={%s};' %
                          (name, ','.join(map(str, row['routes']))))
            checks.append('check_profile(%d,%s);' % (row['revision'], name))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE',
                                     ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        header = (engine / 'openbor.h').read_text()
        arglist = re.findall(r'typedef struct ArgList\s*\{[^}]+}\s*ArgList;', header)
        self.assertEqual(len(arglist), 1)
        max_arg = re.findall(r'(?m)^#define\s+MAX_ARG_LEN\s+(\d+)\b', header)
        self.assertEqual(max_arg, [str(fixture['max_arg_len'])])
        macros = re.findall(r'(?m)^#define GET_ARG\(z\)[^\n]*', source)
        self.assertEqual(len(macros), 1)
        self.assertEqual(source.count('case CMD_LEVEL_MUSIC:'), 1)
        music_case = source.split('case CMD_LEVEL_MUSIC:', 1)[1].split(
            'case CMD_LEVEL_ALLOWSELECT:', 1)[0]
        bodies = '\n'.join(function(source, name) for name in
                           ['ParseArgs', 'findarg', 'obor_legacy_arg'])
        bodies += '\n' + function((engine / 'source/utils.c').read_text(), 'getNewLineStart')
        program = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MAX_ARG_LEN @MAX_ARG_LEN@
@ARGLIST@
uint32_t obor_profile_build;
@MACROS@
@BODIES@
typedef enum {CMD_LEVEL_NONE=0,CMD_LEVEL_MUSIC=1,CMD_LEVEL_AT=2} levelCommands;
/* Deterministic providers isolate the caller from namespace and audio devices. */
static levelCommands getLevelCommand(void *registry,char *command) {
 assert(registry && command);
 if(!strcmp(command,"at"))return CMD_LEVEL_AT;
 if(!strcmp(command,"music"))return CMD_LEVEL_MUSIC;
 return CMD_LEVEL_NONE;
}
static int played;
static void music(char *path,int repeat,uint32_t offset) {
 assert(!strcmp(path,"track.ogg") && repeat==1 && offset==17);played++;
}
typedef struct {float musicfade;char music[128];uint32_t musicoffset;int untouched;} s_spawn_entry;
typedef struct {const char *prefix,*input;float fade;int immediate;} scenario;
static const scenario cases[]={@CASES@};
@ARRAYS@
static void check_case(scenario test,int route) {
 ArgList arglist,arglist2;char argbuf[MAX_ARG_LEN+1]={0},argbuf2[MAX_ARG_LEN+1]={0};
 char buf[256],string[128]={0},musicPath[128]="original.ogg",*command,*value;
 int written=snprintf(buf,sizeof(buf),"%s%s",test.prefix,test.input);
 assert(written>=0 && written<(int)sizeof(buf));
 size_t size=strlen(buf);ptrdiff_t pos=(ptrdiff_t)strlen(test.prefix),oldpos=-1;
 ptrdiff_t original_pos=pos;uint32_t musicOffset=0;
 int registry=1,loadingmusic=test.immediate;void *levelcmdlist=&registry;
 levelCommands cmd2=CMD_LEVEL_NONE;
 s_spawn_entry next={0};next.musicfade=test.fade;strcpy(next.music,"pending");
 next.musicoffset=91;next.untouched=123;played=0;
 ParseArgs(&arglist,buf+pos,argbuf);
 switch(0) {case 0: @MUSIC_CASE@ }
 assert(pos==original_pos);
 if(route==1) {
  assert(!played && !strcmp(musicPath,"original.ogg"));
  assert(!strcmp(next.music,"track.ogg") && next.musicoffset==17);
  assert(next.musicfade==test.fade && next.untouched==(test.fade?123:0));
 } else {
  assert(!strcmp(next.music,"pending") && next.musicoffset==91);
  assert(next.musicfade==test.fade && next.untouched==123);
  if(route==2)assert(!played && !strcmp(musicPath,"track.ogg"));
  else assert(route==3 && played==1 && !musicPath[0]);
 }
}
static void check_profile(unsigned revision,const int *routes) {
 obor_profile_build=revision;
 for(size_t i=0;i<sizeof(cases)/sizeof(cases[0]);i++)check_case(cases[i],routes[i]);
}
int main(void) {@CHECKS@ puts("early_level_music=1");return 0;}
'''
        replacements = dict(MAX_ARG_LEN=max_arg[0], ARGLIST=arglist[0],
                            MACROS=macros[0], BODIES=bodies, MUSIC_CASE=music_case,
                            CASES=','.join(cases), ARRAYS='\n'.join(arrays),
                            CHECKS='\n'.join(checks))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-level-music-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(program)
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-Wno-error=deprecated-declarations', '-Wno-implicit-fallthrough',
                '-Wno-sign-compare', '-fsanitize=address,undefined',
                '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                str(unit), *links, '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=15, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_level_music=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
