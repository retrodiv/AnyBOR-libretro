"""Check text-number results, diagnostics and lifespan rounding by profile.

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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-text-numbers.json'


class EarlyTextNumberTests(unittest.TestCase):
    def test_level_settime_value_and_diagnostic_count(self):
        fixture = load_contract_fixture(FIXTURE.with_name('profile-early-level-settime.json'))
        rows, values = fixture['sources'], fixture['values']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        self.assertTrue(1 <= len(values) <= 32)
        self.assertTrue(all(isinstance(value, str) and len(value) < 32 for value in values))
        for profile in contract_profiles(fixture, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        entries = []
        for row in rows:
            self.assertEqual(len(row['result']), len(values))
            self.assertEqual(len(row['warnings']), len(values))
            self.assertTrue(all(type(v) is int and 0 <= v <= 100 for v in row['result']))
            self.assertTrue(all(type(v) is int and 0 <= v <= 3 for v in row['warnings']))
            entries.append('{%d,{%s},{%s}}' % (
                row['revision'], ','.join(map(str, row['result'])), ','.join(map(str, row['warnings']))))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        source, header = (engine / 'openbor.c').read_text(), (engine / 'openbor.h').read_text()
        arglist = re.findall(r'typedef struct ArgList\s*\{[^}]+}\s*ArgList;', header)
        self.assertEqual(len(arglist), 1)
        max_arg = re.findall(r'(?m)^#define\s+MAX_ARG_LEN\s+(\d+)\b', header)
        self.assertEqual(len(max_arg), 1)
        macros = []
        for name in ['GET_ARG', 'GET_INT_ARG']:
            found = re.findall(r'(?m)^#define ' + name + r'\(z\)[^\n]*', source)
            self.assertEqual(len(found), 1)
            macros += found
        body = function(source, 'load_level').split('case CMD_LEVEL_SETTIME:', 1)[1]
        body = body.split('case CMD_LEVEL_SETWEAP:', 1)[0]
        bodies = '\n'.join(function(source, n) for n in
                           ['isNumeric', 'getValidInt', 'findarg', 'obor_legacy_arg', 'ParseArgs'])
        program = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#define MAX_ARG_LEN @MAX_ARG_LEN@
@ARGLIST@
uint32_t obor_profile_build;
static int warning_count;
static const char *active_value;
static int numeric_warning(const char *format,...) {
 char actual[512],expected[512];va_list ap;va_start(ap,format);
 int length=vsnprintf(actual,sizeof(actual),format,ap);va_end(ap);
 assert(length>=0 && length<(int)sizeof(actual));
 snprintf(expected,sizeof(expected),@WARNING_FORMAT@,"fixture.txt","settime",active_value);
 assert(!strcmp(actual,expected));++warning_count;return length;
}
#define printf numeric_warning
@MACROS@
@BODIES@
#undef printf
static const char *values[]={@VALUES@};
struct expectation {uint32_t revision;int result[@COUNT@],warnings[@COUNT@];};
static const struct expectation contexts[]={@CONTEXTS@};
int main(void) {
 for(unsigned r=0;r<sizeof(contexts)/sizeof(*contexts);++r) {
  const struct expectation *ctx=&contexts[r];obor_profile_build=ctx->revision;
  for(unsigned i=0;i<@COUNT@;++i) {
   ArgList arglist;char argbuf[MAX_ARG_LEN+1],line[MAX_ARG_LEN+1];ptrdiff_t pos=0;
   char filename[]="fixture.txt",command[]="settime",*buf=line;
   struct {int settime;} storage={73},*level=&storage;
   snprintf(line,sizeof(line),"settime %s\n",values[i]);ParseArgs(&arglist,line,argbuf);
   warning_count=0;active_value=values[i];
   switch(0) {case 0:@CASE@}
   assert(level->settime==ctx->result[i]&&warning_count==ctx->warnings[i]);
  }
 }
 puts("early_level_settime=1");return 0;
}
'''
        replacements = dict(MAX_ARG_LEN=max_arg[0], ARGLIST=arglist[0],
                            WARNING_FORMAT=json.dumps(fixture['warning_format']),
                            MACROS='\n'.join(macros), BODIES=bodies, CASE=body,
                            VALUES=','.join(map(json.dumps, values)), COUNT=str(len(values)),
                            CONTEXTS=','.join(entries))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-level-settime-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(program)
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-fsanitize=address,undefined',
                '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                '-Wno-deprecated-declarations', str(unit), *links, '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=15, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_level_settime=1', run.stdout)

    def test_numeric_callers_and_original_diagnostics(self):
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
        values = fixture['values']
        self.assertTrue(values and all(isinstance(value, str) and len(value) < 32 for value in values))
        arrays, checks = [], []
        fields = ['integer', 'float_bits', 'integer_warnings', 'float_warnings',
                  'model_flag', 'model_warnings', 'helper_float_bits', 'helper_warnings',
                  'lifespan_bits', 'lifespan_warnings']
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            self.assertEqual(len(row['cases']), len(values))
            entries = []
            for case in row['cases']:
                self.assertEqual(set(case), set(fields))
                for name in fields:
                    value = case[name]
                    if name.startswith('helper_') and not row['helper_available']:
                        self.assertIsNone(value)
                    elif name.endswith('_bits'):
                        self.assertIs(type(value), int)
                        self.assertTrue(0 <= value <= 0xffffffff)
                    elif name.endswith('_warnings'):
                        self.assertIn(value, (0, 1))
                    else:
                        self.assertIs(type(value), int)
                entries.append('{' + ','.join(str(case[name] or 0) for name in fields) + '}')
            label = 'cases_' + str(row['revision'])
            arrays.append('static const expectation %s[]={%s};' % (label, ','.join(entries)))
            checks.append('check_profile(%d,%d,%s);' % (
                row['revision'], row['helper_available'], label))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE',
                                     ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        header = (engine / 'openbor.h').read_text()
        arglist = re.findall(r'typedef struct ArgList\s*\{[^}]+}\s*ArgList;', header)
        self.assertEqual(len(arglist), 1)
        self.assertRegex(header, r'\bfloat\s+lifespan\s*;')
        max_name = re.findall(r'(?m)^#define\s+MAX_NAME_LEN\s+(\d+)\b', header)
        self.assertEqual(len(max_name), 1)
        speed = re.findall(r'(?m)^#define\s+GAME_SPEED\s+(\d+)\b', header)
        self.assertEqual(speed, [str(fixture['game_speed'])])
        macros = []
        for name in ['GET_ARG', 'GET_ARG_LEN', 'GET_ARGP', 'GET_ARGP_LEN',
                     'GET_INT_ARG', 'GET_FLOAT_ARG', 'GET_INT_ARGP', 'GET_FLOAT_ARGP',
                     'GET_MODEL_LOAD_FLAG']:
            found = re.findall(r'(?m)^#define ' + name + r'\(z\)[^\n]*', source)
            self.assertEqual(len(found), 1, name)
            macros += found
        names = ['isNumeric', 'getValidInt', 'getValidFloat', 'ParseArgs', 'findarg']
        # A parser restoration may supply these accessors without changing
        # the numeric cases' short, terminated input lines.
        names += [name for name in ('obor_legacy_arg', 'obor_legacy_arg_len')
                  if re.search(r'\b' + name + r'\s*\(', source)]
        names += [name for name in ('obor_model_input',)
                  if re.search(r'\b' + name + r'\s*\(', source)]
        bodies = '\n'.join(function(source, name) for name in names)
        lifespan = re.findall(r'\bnewchar->lifespan\s*=(?=[^;]*\bGAME_SPEED\b)[^;]+;', source)
        self.assertEqual(len(lifespan), 1)
        self.assertEqual(source.count('case CMD_MODEL_LOAD:'), 1)
        model_case = source.split('case CMD_MODEL_LOAD:', 1)[1].split('case CMD_MODEL_SCORE:', 1)[0]
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <limits.h>
#define MAX_ARG_LEN @MAX_ARG_LEN@
#define MAX_NAME_LEN @MAX_NAME_LEN@
#define GAME_SPEED @GAME_SPEED@
@ARGLIST@
uint32_t obor_profile_build;
static int warning_count, loaded_flag, load_calls;
static const char *warning_value,*warning_command;
static int number_warning(const char *format,...) {
 char actual[1024],expected[1024];va_list ap;va_start(ap,format);
 int result=vsnprintf(actual,sizeof(actual),format,ap);va_end(ap);
 assert(result>=0 && result<(int)sizeof(actual));
 snprintf(expected,sizeof(expected),@WARNING_FORMAT@,"fixture.txt",warning_command,warning_value);
 assert(!strcmp(actual,expected));warning_count++;return result;
}
#define printf number_warning
@MACROS@
@BODIES@
#undef printf
typedef struct {float lifespan;} model;
static model *findmodel(const char *name) {assert(!strcmp(name,"model"));return NULL;}
static model *load_cached_model(const char *name,const char *owner,int flag) {
 assert(!strcmp(name,"model") && !strcmp(owner,"owner"));
 loaded_flag=flag;load_calls++;return NULL;
}
static void update_model_loadflag(model *value,int flag) {
 (void)value;(void)flag;assert(!"Existing-model lifecycle is a separate contract");
}
static uint32_t bits(float value) {uint32_t result;memcpy(&result,&value,sizeof(result));return result;}
typedef struct {
 int integer;uint32_t real;int integer_warnings,float_warnings;
 int model_flag,model_warnings;uint32_t helper;int helper_warnings;
 uint32_t lifespan;int lifespan_warnings;
} expectation;
static void pointer_values(ArgList *arglist,expectation e) {
 char filename[]="fixture.txt",command[]="setting";warning_command=command;
 warning_count=0;assert(GET_INT_ARGP(1)==e.integer && warning_count==e.integer_warnings);
 warning_count=0;float value=GET_FLOAT_ARGP(1);assert(bits(value)==e.real && warning_count==e.float_warnings);
 assert(sizeof(GET_FLOAT_ARGP(1))==sizeof(float));
}
static void check_value(const char *input,expectation e,int helper_available) {
 ArgList arglist;char line[MAX_ARG_LEN+1],output[MAX_ARG_LEN+1];
 char filename[]="fixture.txt",command[]="setting";warning_value=input;warning_command=command;
 int length=snprintf(line,sizeof(line),"setting %s\n",input);assert(length>0 && length<MAX_ARG_LEN);
 ParseArgs(&arglist,line,output);
 assert(GET_ARG_LEN(1)==strlen(input));
 warning_count=0;assert(GET_INT_ARG(1)==e.integer && warning_count==e.integer_warnings);
 warning_count=0;float value=GET_FLOAT_ARG(1);assert(bits(value)==e.real && warning_count==e.float_warnings);
 assert(sizeof(GET_FLOAT_ARG(1))==sizeof(float));pointer_values(&arglist,e);
 if(helper_available) {
  warning_command=command;warning_count=0;value=getValidFloat(GET_ARG(1),filename,command);
  assert(bits(value)==e.helper && warning_count==e.helper_warnings);
 }
 warning_count=0;assert(getValidInt(NULL,filename,command)==0);
 assert(getValidFloat(NULL,filename,command)==0 && !warning_count);
}
static void check_model(const char *input,expectation e) {
 ArgList arglist;char line[MAX_ARG_LEN+1],output[MAX_ARG_LEN+1];
 char filename[]="fixture.txt",command[]="load",*value,*name="owner";model *tempmodel;
 warning_value=input;warning_command=command;warning_count=load_calls=0;loaded_flag=12345;
 snprintf(line,sizeof(line),"load model %s\n",input);ParseArgs(&arglist,line,output);
 switch(0) {case 0: @MODEL_CASE@ }
 assert(load_calls==1 && loaded_flag==e.model_flag && warning_count==e.model_warnings);
}
static void check_lifespan(const char *input,expectation e) {
 ArgList arglist;char line[MAX_ARG_LEN+1],output[MAX_ARG_LEN+1];
 char filename[]="fixture.txt",command[]="lifespan";model value={0},*newchar=&value;
 warning_value=input;warning_command=command;warning_count=0;
 snprintf(line,sizeof(line),"lifespan %s\n",input);ParseArgs(&arglist,line,output);
 @LIFESPAN@
 assert(bits(value.lifespan)==e.lifespan && warning_count==e.lifespan_warnings);
}
static const char *values[]={@VALUES@};
@ARRAYS@
static void check_profile(unsigned revision,int helper_available,const expectation *expected) {
 obor_profile_build=revision;
 for(size_t i=0;i<sizeof(values)/sizeof(values[0]);i++) {
  check_value(values[i],expected[i],helper_available);
  check_model(values[i],expected[i]);check_lifespan(values[i],expected[i]);
 }
}
int main(void) {@CHECKS@ puts("early_text_numbers=1");return 0;}
'''
        max_arg = re.findall(r'(?m)^#define\s+MAX_ARG_LEN\s+(\d+)\b', header)
        self.assertEqual(len(max_arg), 1)
        replacements = dict(MAX_ARG_LEN=max_arg[0], MAX_NAME_LEN=max_name[0],
                            GAME_SPEED=speed[0], ARGLIST=arglist[0],
                            WARNING_FORMAT=json.dumps(fixture['warning_format']),
                            MACROS='\n'.join(macros), BODIES=bodies, MODEL_CASE=model_case,
                            LIFESPAN=lifespan[0], VALUES=','.join(map(json.dumps, values)),
                            ARRAYS='\n'.join(arrays), CHECKS='\n'.join(checks))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-text-numbers-') as name:
            work = Path(name)
            unit = work / 'probe.c'
            binary = work / 'probe'
            unit.write_text(program)
            links = [] if sys.platform == 'darwin' else ['-no-pie']
            command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-Wno-error=deprecated-declarations', '-Wno-implicit-fallthrough',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                '-fno-omit-frame-pointer', str(unit), *links, '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=15, env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_text_numbers=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
