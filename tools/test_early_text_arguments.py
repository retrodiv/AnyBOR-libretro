"""Check argument lookup, retained query state and platform arity by profile.

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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-text-arguments.json'


class EarlyTextArgumentTests(unittest.TestCase):
    def test_queries_and_platform_argument_count(self):
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
        cases = fixture['queries']
        self.assertTrue(cases and len(cases) <= 64)
        entries = []
        for case in cases:
            self.assertIsInstance(case['input'], str)
            self.assertLess(len(case['input']), 1024)
            self.assertTrue(type(case['index']) is int and 0 <= case['index'] < 512)
            entries.append('{%s,%d}' % (json.dumps(case['input']), case['index']))
        arrays, checks = [], []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            self.assertEqual(len(row['results']), len(cases))
            self.assertTrue(all(isinstance(value, str) and len(value) <= 511
                                for value in row['results']))
            self.assertIn(row['token_limit'], (0, 16, 18))
            self.assertIs(type(row['shared_result']), bool)
            self.assertIs(type(row['seven_value_sentinel']), bool)
            self.assertIs(type(row['window_command']), bool)
            label = 'results_' + str(row['revision'])
            arrays.append('static const char *%s[]={%s};' %
                          (label, ','.join(map(json.dumps, row['results']))))
            checks.append('check_profile(%d,%d,%d,%d,%d,%s);' % (
                row['revision'], row['token_limit'], row['shared_result'],
                row['seven_value_sentinel'], row['window_command'], label))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE',
                                     ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        header = (engine / 'openbor.h').read_text()
        arglist = re.findall(r'typedef struct ArgList\s*\{[^}]+}\s*ArgList;', header)
        self.assertEqual(len(arglist), 1)
        max_arg = re.findall(r'(?m)^#define\s+MAX_ARG_LEN\s+(\d+)\b', header)
        self.assertEqual(max_arg, [str(fixture['max_arg_len'])])
        macros = []
        for name in ['GET_ARG', 'GET_ARG_LEN', 'GET_ARGP', 'GET_ARGP_LEN', 'GET_ARG2',
                     'GET_FLOAT_ARG']:
            found = re.findall(r'(?m)^[ \t]*#define ' + name + r'\(z\)[^\n]*', source)
            self.assertEqual(len(found), 1, name)
            macros += found
        bodies = '\n'.join(function(source, name) for name in [
            'isNumeric', 'getValidFloat', 'ParseArgs', 'findarg',
            'obor_legacy_arg', 'obor_legacy_arg_len'])
        self.assertEqual(source.count('case CMD_MODEL_PLATFORM:'), 1)
        platform = source.split('case CMD_MODEL_PLATFORM:', 1)[1].split(
            'case CMD_MODEL_DRAWMETHOD:', 1)[0]
        model_prefix = function(source, 'load_cached_model')
        gate = re.findall(r'ParseArgs\(&arglist,buf\+pos,argbuf\);\s*'
                          r'if\([^{}]+\)\{\s*command = GET_ARG\(0\);', model_prefix)
        self.assertEqual(len(gate), 1)
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MAX_ARG_LEN @MAX_ARG_LEN@
@ARGLIST@
uint32_t obor_profile_build;
@MACROS@
@BODIES@
typedef struct {const char *input;size_t index;} query;
static const query queries[]={@QUERIES@};
@ARRAYS@
static void seed(void) {
 ArgList arglist;char line[]="abcdefghijkl\n",out[MAX_ARG_LEN+1]={0};
 ParseArgs(&arglist,line,out);assert(!strcmp(GET_ARG(0),"abcdefghijkl"));
}
static void pointer_query(ArgList *arglist,size_t index,const char *expected) {
 assert(!strcmp(GET_ARGP(index),expected));
 assert(GET_ARGP_LEN(index)==strlen(expected));
}
static void check_query(query q,const char *expected) {
 ArgList arglist,arglist2;char line[1024],out[MAX_ARG_LEN+1]={0},out2[MAX_ARG_LEN+1]={0};
 strcpy(line,q.input);seed();ParseArgs(&arglist,line,out);
 assert(!strcmp(GET_ARG(q.index),expected));
 seed();ParseArgs(&arglist,line,out);assert(GET_ARG_LEN(q.index)==strlen(expected));
 seed();ParseArgs(&arglist,line,out);pointer_query(&arglist,q.index,expected);
 seed();ParseArgs(&arglist2,line,out2);assert(!strcmp(GET_ARG2(q.index),expected));
}
static void aliases(int shared) {
 ArgList arglist,arglist2;char left[]="setting left\n",right[]="setting right\n";
 char out[MAX_ARG_LEN+1]={0},out2[MAX_ARG_LEN+1]={0};
 ParseArgs(&arglist,left,out);ParseArgs(&arglist2,right,out2);
 char *saved=GET_ARG(1);assert(!strcmp(saved,"left"));
 assert(!strcmp(GET_ARG2(1),"right"));assert(!strcmp(saved,shared?"right":"left"));
}
static void platform_values(const char *line,const float expected[8]) {
 ArgList arglist;char input[128],out[MAX_ARG_LEN+1]={0};float platform[8];int i;
 char filename[]="fixture.txt",command[]="platform";
 for(i=0;i<8;i++)platform[i]=-123;
 strcpy(input,line);ParseArgs(&arglist,input,out);
 switch(0) {case 0: @PLATFORM@ }
 for(i=0;i<8;i++)assert(platform[i]==expected[i]);
}
static void bounds(int token_limit) {
 ArgList arglist;char input[MAX_ARG_LEN+1],out[MAX_ARG_LEN+1]={0};
 size_t pos=0;for(size_t i=0;i<250;i++){input[pos++]='x';input[pos++]=' ';}input[pos++]='\n';input[pos]=0;
 ParseArgs(&arglist,input,out);
 if(token_limit)assert(arglist.count==(size_t)token_limit);
 else {
  size_t last=arglist.count-1,missing=arglist.count;
  assert(!strcmp(GET_ARG(last),"x"));assert(!strcmp(GET_ARG(missing),""));
 }
 size_t invalid=(size_t)-1;assert(!strcmp(GET_ARG(invalid),""));
 assert(!strcmp(obor_legacy_arg(NULL,1),""));
 ArgList empty={0};assert(!strcmp(obor_legacy_arg(&empty,1),""));
}
static int model_gate(char *buf) {
 ArgList arglist;char argbuf[MAX_ARG_LEN+1]={0};size_t pos=0;char *command;
 @GATE@ (void)command;return 1;}return 0;
}
static void check_profile(unsigned revision,int token_limit,int shared,int sentinel,int window_command,const char **expected) {
 obor_profile_build=revision;
 for(size_t i=0;i<sizeof(queries)/sizeof(queries[0]);i++)check_query(queries[i],expected[i]);
 aliases(shared);bounds(token_limit);
 const float six[8]={99999,-123,1,2,3,4,5,6};
 const float seven_old[8]={99999,-123,1,2,3,4,5,6};
 const float seven_new[8]={1,2,3,4,5,6,7,0};
 const float eight[8]={1,2,3,4,5,6,7,8};
 platform_values("platform 1 2 3 4 5 6\n",six);
 platform_values("platform 1 2 3 4 5 6 7\n",sentinel?seven_old:seven_new);
 platform_values("platform 1 2 3 4 5 6 7 8\n",eight);
 char full[MAX_ARG_LEN+1];memset(full,'x',MAX_ARG_LEN-1);full[MAX_ARG_LEN-1]='\n';full[MAX_ARG_LEN]=0;
 assert(model_gate(full)==window_command);
 assert(model_gate("name hero\n")==1);assert(model_gate("\n")==0);
}
int main(void) {@CHECKS@ puts("early_text_arguments=1");return 0;}
'''
        replacements = dict(MAX_ARG_LEN=max_arg[0], ARGLIST=arglist[0],
                            MACROS='\n'.join(macros), BODIES=bodies,
                            QUERIES=','.join(entries), ARRAYS='\n'.join(arrays),
                            PLATFORM=platform, GATE=gate[0], CHECKS='\n'.join(checks))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-text-arguments-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(program)
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-Wno-error=deprecated-declarations', '-Wno-implicit-fallthrough',
                '-Wno-sign-compare',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                '-fno-omit-frame-pointer', str(unit), *links, '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=15, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_text_arguments=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
