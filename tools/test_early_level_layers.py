"""Check original layer ratio/repeat assignments and missing-value predicates.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import math
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
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-level-layers.json'
FIELDS = ['xratio', 'zratio', 'xrepeat', 'zrepeat']


def layer_statements(source, member):
    """Retain the actual four assignments and four default statements only."""
    target = re.escape(member)
    assignment = re.compile(r'^\s*' + target + r'\.(xratio|zratio|xrepeat|zrepeat)\s*=')
    default = re.compile(r'^\s*if[^;\r\n]*' + target +
                         r'\.(xratio|zratio|xrepeat|zrepeat)\s*=')
    initial, fallback = [], []
    for line in source.splitlines():
        match = assignment.match(line)
        if match:
            initial.append((match[1], line))
        match = default.match(line)
        if match:
            fallback.append((match[1], line))
    if [name for name, _ in initial] != FIELDS or [name for name, _ in fallback] != FIELDS:
        raise ValueError('Expected exactly four assignments and defaults for ' + member)
    return '\n'.join(line for _, line in initial + fallback)


class EarlyLevelLayerTests(unittest.TestCase):
    def test_ratio_repeat_and_missing_argument_results(self):
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
            self.assertIs(type(case['terminated']), bool)
            self.assertLess(len(case['arguments']), 100)
            cases.append('{%s,%d}' % (json.dumps(case['arguments']), case['terminated']))
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            self.assertEqual(len(row['results']), 3 * len(cases))
            entries = []
            for result in row['results']:
                self.assertEqual(set(result), set(FIELDS + ['warnings']))
                for field in FIELDS[:2]:
                    self.assertTrue(isinstance(result[field], (int, float)) and
                                    math.isfinite(result[field]))
                for field in FIELDS[2:]:
                    self.assertIs(type(result[field]), int)
                self.assertTrue(type(result['warnings']) is int and 0 <= result['warnings'] <= 4)
                entries.append('{%s}' % ','.join(str(result[key]) for key in FIELDS + ['warnings']))
            name = 'results_' + str(row['revision'])
            arrays.append('static const expectation %s[]={%s};' % (name, ','.join(entries)))
            checks.append('check_profile(%d,%s);' % (row['revision'], name))
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE',
                                     ROOT / 'src/engines' / fixture['engine']))
        source = (engine / 'openbor.c').read_text()
        header = (engine / 'openbor.h').read_text()
        arglist = re.findall(r'typedef struct ArgList\s*\{[^}]+}\s*ArgList;', header)
        self.assertEqual(len(arglist), 1)
        max_arg = re.findall(r'(?m)^#define\s+MAX_ARG_LEN\s+(\d+)\b', header)
        self.assertEqual(max_arg, [str(fixture['max_arg_len'])])
        for field, kind in zip(FIELDS, ['float', 'float', 'int', 'int']):
            self.assertEqual(re.findall(r'(?m)^\s*(\w+)\s+' + field + r'\s*;', header),
                             [kind, kind])
        macros = []
        for name in ['GET_ARG', 'GET_INT_ARG', 'GET_FLOAT_ARG']:
            found = re.findall(r'(?m)^#define ' + name + r'\(z\)[^\n]*', source)
            self.assertEqual(len(found), 1)
            macros += found
        bodies = '\n'.join(function(source, name) for name in
                           ['isNumeric', 'getValidInt', 'getValidFloat', 'ParseArgs',
                            'findarg', 'obor_legacy_arg'])
        statements = [layer_statements(source, member) for member in
                      ['level->bglayers[0]', 'level->bglayers[level->numbglayers]',
                       'level->fglayers[level->numfglayers]']]
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MAX_ARG_LEN @MAX_ARG_LEN@
@ARGLIST@
uint32_t obor_profile_build;
static int numeric_warnings;
static int number_warning(const char *format,...) {
 assert(format && format[0]);numeric_warnings++;return 0;
}
#define printf number_warning
@MACROS@
@BODIES@
#undef printf
/* The original four field types are checked separately against each header.
   These providers do not model the full layer record or renderer. */
typedef struct {float xratio,zratio;int xrepeat,zrepeat;} layer_record;
typedef struct {layer_record bglayers[2],fglayers[1];int numbglayers,numfglayers;} level_record;
typedef struct {float xratio,zratio;int xrepeat,zrepeat,warnings;} expectation;
typedef struct {const char *arguments;int terminated;} scenario;
static uint32_t bits(float value) {
 uint32_t result;assert(sizeof(result)==sizeof(value));memcpy(&result,&value,sizeof(result));return result;
}
static int unchanged(layer_record *value) {
 return value->xratio==-4 && value->zratio==-5 && value->xrepeat==-6 && value->zrepeat==-7;
}
static const scenario cases[]={@CASES@};
@ARRAYS@
static void check_case(int kind,scenario test,expectation expected) {
 static const char *commands[]={"background","bglayer","fglayer"};
 char input[256],out[MAX_ARG_LEN+1]={0};ArgList arglist;
 char *command=(char*)commands[kind],filename[]="fixture.txt",*value=NULL;
 int length=snprintf(input,sizeof(input),"%s layer%s%s",command,test.arguments,test.terminated?"\n":"");
 assert(length>=0 && length<(int)sizeof(input));ParseArgs(&arglist,input,out);
 layer_record initial={-4,-5,-6,-7};level_record record={0},*level=&record;
 record.bglayers[0]=record.bglayers[1]=record.fglayers[0]=initial;
 record.numbglayers=1;record.numfglayers=0;numeric_warnings=0;
 switch(kind) {
 case 0: {
 @BACKGROUND@
 } break;
 case 1: {
 @BGLAYER@
 } break;
 case 2: {
 @FGLAYER@
 } break;
 }
 layer_record *actual=kind==2?&record.fglayers[0]:&record.bglayers[kind];
 assert(bits(actual->xratio)==bits(expected.xratio) && bits(actual->zratio)==bits(expected.zratio));
 assert(actual->xrepeat==expected.xrepeat && actual->zrepeat==expected.zrepeat);
 assert(numeric_warnings==expected.warnings);
 if(kind!=0)assert(unchanged(&record.bglayers[0]));
 if(kind!=1)assert(unchanged(&record.bglayers[1]));
 if(kind!=2)assert(unchanged(&record.fglayers[0]));
 (void)value;
}
static void check_profile(unsigned revision,const expectation *expected) {
 obor_profile_build=revision;size_t count=sizeof(cases)/sizeof(cases[0]);
 for(int kind=0;kind<3;kind++)for(size_t i=0;i<count;i++)check_case(kind,cases[i],expected[kind*count+i]);
}
int main(void) {@CHECKS@ puts("early_level_layers=1");return 0;}
'''
        replacements = dict(MAX_ARG_LEN=max_arg[0], ARGLIST=arglist[0],
                            MACROS='\n'.join(macros), BODIES=bodies,
                            BACKGROUND=statements[0], BGLAYER=statements[1],
                            FGLAYER=statements[2], CASES=','.join(cases),
                            ARRAYS='\n'.join(arrays), CHECKS='\n'.join(checks))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-level-layers-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
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
            self.assertIn('early_level_layers=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
