"""Check per-model weapon history and historical level flag/join outcomes.

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
from test_early_jump_walkoff import continued_macro

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-model-level-state.json'


def c_array(value):
    if isinstance(value, list):
        return '{' + ','.join(c_array(item) for item in value) + '}'
    if type(value) is not int:
        raise AssertionError('Integer contract oracle required')
    return str(value)


class EarlyModelLevelStateTests(unittest.TestCase):
    def test_weapon_history_and_level_flags(self):
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
        self.assertEqual(len(arglist), 1)
        macros, constants = [], []
        for name in ['GET_ARG', 'GET_ARGP', 'GET_INT_ARG']:
            found = re.findall(r'(?m)^#define ' + name + r'\(z\)[^\n]*', source)
            self.assertEqual(len(found), 1)
            macros += found
        for name in ['MAX_ARG_LEN', 'MAX_WEAPONS', 'LEVEL_MAX_SPAWNS']:
            found = re.findall(r'(?m)^#define\s+' + name + r'\s+[^\n]+', header)
            self.assertEqual(len(found), 1)
            constants += found
        fields = []
        for name, pattern in [('nojoin', r'char\s+nojoin:8;'), ('nospecial', r'int\s+nospecial;'), ('nohurt', r'int\s+nohurt;')]:
            found = re.findall(r'(?m)^\s*' + pattern, header)
            self.assertEqual(len(found), 1, name)
            fields += found
        model = function(source, 'load_cached_model')
        state = re.findall(r'\bint weapon_last\s*=\s*0;', model)
        self.assertEqual(len(state), 1)
        loop = re.search(r'while\(pos\s*<\s*size\)', model)
        self.assertIsNotNone(loop)
        self.assertLess(model.index(state[0]), loop.start())
        self.assertEqual(model.count('weapon_last'), 2)
        _, model_cases = switch_cases(model.replace('switch(cmd)', 'switch(model_command)', 1), 'load_cached_model', 'model_command')
        level = function(source, 'load_level')
        _, level_cases = switch_cases(level.replace('switch(cmd)', 'switch(level_command)', 1), 'load_level', 'level_command')
        consumer = []
        for name in ('obor_update_scroller_legacy', 'update_scroller'):
            found = re.findall(r'(?m)^\s*nojoin\s*=\s*\([^\n;]*\.nojoin\s*==\s*1\);', function(source, name))
            self.assertEqual(len(found), 1, name)
            consumer += found
        helpers = '\n'.join(function(source, name) for name in ['ParseArgs', 'findarg', 'obor_legacy_arg', 'isNumeric', 'getValidInt', 'lcmHandleCommandWeapons'])
        arrays, checks = [], []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['function_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            self.assertIn(row['canjoin_marker'], [-1, 1])
            self.assertIs(type(row['retain_weapon_slot']), bool)
            self.assertEqual(len(row['weapon_results']), len(fixture['weapon_cases']))
            self.assertTrue(all(len(result) == fixture['weapons_limit'] for result in row['weapon_results']))
            self.assertEqual(len(row['type_results']), len(fixture['type_cases']))
            self.assertTrue(all(len(result) == 3 for result in row['type_results']))
            suffix = str(row['revision'])
            arrays += ['static const int weapons_' + suffix + '[][MAX_WEAPONS]=' + c_array(row['weapon_results']) + ';',
                       'static const int types_' + suffix + '[][3]=' + c_array(row['type_results']) + ';']
            checks.append('check(%d,%d,%d,weapons_%s,types_%s);' % (row['revision'], row['retain_weapon_slot'], row['canjoin_marker'], suffix, suffix))
        program = r'''
#include <assert.h>
#include <ctype.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "commands.h"
@CONSTANTS@
@ARGLIST@
@MACROS@
uint32_t obor_profile_build;
@LEVEL_ERROR@
@LEVEL_ERROR_MACRO@
typedef struct {int (*weapon)[MAX_WEAPONS];int ownweapons;} s_model;
typedef struct {int index,at;@JOIN_FIELD@} s_spawn_entry;
static struct {int type;@LEVEL_FIELDS@ int numspawns;s_spawn_entry spawnpoints[LEVEL_MAX_SPAWNS];} level_data,*level=&level_data;
static s_spawn_entry next;
static int nojoin,current_spawn;
static int get_cached_model_index(char *name) {
 if(!strcmp(name,"Alpha"))return 7;
 if(!strcmp(name,"Beta"))return 9;
 if(!strcmp(name,"Gamma"))return 13;
 assert(!strcmp(name,"Missing"));return -1;
}
@HELPERS@
typedef struct {s_model model;int last;} parser_context;
static void initialize(parser_context *ctx) {@STATE@ memset(ctx,0,sizeof(*ctx));ctx->last=weapon_last;}
static void weapon_line(parser_context *ctx,const char *text) {
 ArgList arglist;char argbuf[MAX_ARG_LEN+1]={0},line[MAX_ARG_LEN+1];
 assert(strlen(text)<sizeof(line));strcpy(line,text);ParseArgs(&arglist,line,argbuf);
 s_model *newchar=&ctx->model;int weapon_last=ctx->last;
 switch(CMD_MODEL_WEAPONS) {case CMD_MODEL_WEAPONS:@WEAPON_CASE@ default:abort();}
 ctx->last=weapon_last;
}
static void level_line(levelCommands cmd,const char *text) {
 char *filename=(char *)"data/level.txt",*command;
 ArgList arglist;char argbuf[MAX_ARG_LEN+1]={0},line[MAX_ARG_LEN+1],*errormessage=NULL;
 @LEVEL_ERROR_STORAGE@
 assert(strlen(text)<sizeof(line));strcpy(line,text);ParseArgs(&arglist,line,argbuf);command=GET_ARG(0);
 switch(cmd) {
 case CMD_LEVEL_TYPE:@TYPE_CASE@
 case CMD_LEVEL_NOJOIN:@NOJOIN_CASE@
 case CMD_LEVEL_CANJOIN:@CANJOIN_CASE@
 case CMD_LEVEL_AT:@AT_CASE@
 default:abort();
 }
 return;
lCleanup:assert(errormessage);abort();
}
static void consume(unsigned route) {switch(route) {@CONSUMER@ default:abort();}}
static const char *weapon_cases[]={@WEAPON_CASES@};
static const char *type_cases[]={@TYPE_CASES@};
@ARRAYS@
static void all_slots(parser_context *ctx,int value) {for(int i=0;i<MAX_WEAPONS;i++)assert((*ctx->model.weapon)[i]==value);}
static void check(unsigned revision,int retain,int marker,const int (*weapons)[MAX_WEAPONS],const int (*types)[3]) {
 obor_profile_build=revision;assert(MAX_WEAPONS==@LIMIT@);
 parser_context a,b;initialize(&a);initialize(&b);
 weapon_line(&b,"weapons\n");all_slots(&b,-1);assert(b.model.ownweapons);
 weapon_line(&b,"weapons Gamma Alpha Beta\n");
 for(size_t i=0;i<sizeof(weapon_cases)/sizeof(weapon_cases[0]);i++) {
  int (*previous)[MAX_WEAPONS]=a.model.weapon;
  weapon_line(&a,weapon_cases[i]);assert(a.model.ownweapons && (!previous || previous==a.model.weapon));
  for(int slot=0;slot<MAX_WEAPONS;slot++)assert((*a.model.weapon)[slot]==weapons[i][slot]);
  if(i==2) {weapon_line(&b,"weapons\n");all_slots(&b,retain?9:13);}
 }
 free(a.model.weapon);free(b.model.weapon);
 memset(level,0,sizeof(*level));
 for(size_t i=0;i<sizeof(type_cases)/sizeof(type_cases[0]);i++) {
  level_line(CMD_LEVEL_TYPE,type_cases[i]);
  assert(level->type==types[i][0] && level->nospecial==types[i][1] && level->nohurt==types[i][2]);
 }
 memset(level,0,sizeof(*level));level_line(CMD_LEVEL_TYPE,"type 0\n");
 assert(!level->type && !level->nospecial && !level->nohurt);
 const levelCommands commands[]={CMD_LEVEL_NOJOIN,CMD_LEVEL_CANJOIN};
 const char *lines[]={"nojoin\n","canjoin\n"};
 for(int i=0;i<2;i++) {
  next.index=23;next.at=90;level_line(commands[i],lines[i]);
  int expected=i?marker:1;
  assert(next.nojoin==(char)expected && !next.index && !next.at);
  level_line(CMD_LEVEL_AT,"at 123\n");assert(level->numspawns==i+1 && !next.nojoin && !next.at);
  current_spawn=i;assert(level->spawnpoints[i].at==123 && level->spawnpoints[i].nojoin==(char)expected);
  for(unsigned route=0;route<2;route++) {nojoin=9;consume(route);assert(nojoin==(expected==1));}
 }
}
int main(void) {@CHECKS@ puts("early_model_level_state=1");return 0;}
'''
        replacements = dict(CONSTANTS='\n'.join(constants), ARGLIST=arglist[0], MACROS='\n'.join(macros),
                            LEVEL_ERROR=function(source, 'obor_level_error'),
                            LEVEL_ERROR_MACRO=continued_macro(source, 'OBOR_LEVEL_ERROR'),
                            LEVEL_ERROR_STORAGE=re.search(r'char legacy_level_error\[\d+\][^;]*;', level).group(),
                            JOIN_FIELD=fields[0], LEVEL_FIELDS='\n'.join(fields[1:]), HELPERS=helpers,
                            STATE=state[0], WEAPON_CASE=model_cases['CMD_MODEL_WEAPONS']['body'],
                            TYPE_CASE=level_cases['CMD_LEVEL_TYPE']['body'], NOJOIN_CASE=level_cases['CMD_LEVEL_NOJOIN']['body'],
                            CANJOIN_CASE=level_cases['CMD_LEVEL_CANJOIN']['body'], AT_CASE=level_cases['CMD_LEVEL_AT']['body'],
                            CONSUMER=''.join('case %d: %s break;' % (i, body) for i, body in enumerate(consumer)),
                            WEAPON_CASES=','.join(map(json.dumps, fixture['weapon_cases'])),
                            TYPE_CASES=','.join(map(json.dumps, fixture['type_cases'])), ARRAYS='\n'.join(arrays),
                            LIMIT=str(fixture['weapons_limit']), CHECKS='\n'.join(checks))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-model-level-state-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(bind_named_allocation_support(program, engine))
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-Dstricmp=strcasecmp',
                     '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                     '-Wall', '-Wextra', '-Werror', '-Wno-implicit-fallthrough', '-Wno-sign-compare',
                     '-Wno-error=deprecated-declarations', '-I' + str(engine / 'source/scriptlib'),
                     '-I' + str(engine / 'source/gamelib')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)],
                                   capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15, env=sanitizer_environment())
            if os.environ.get('OBOR_MODEL_LEVEL_STATE_OBSERVATIONS'):
                Path(os.environ['OBOR_MODEL_LEVEL_STATE_OBSERVATIONS']).write_text(json.dumps({
                    'compiler': cc, 'flags': flags, 'contexts': len(rows),
                    'weapon_cases': len(fixture['weapon_cases']), 'type_cases': len(fixture['type_cases']),
                    'probe_sha256': hashlib.sha256(program.encode()).hexdigest(),
                    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                    'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                    'header_sha256': hashlib.sha256(header.encode()).hexdigest(),
                    'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr,
                    'scope': fixture['scope'], 'retirement': 'TemporaryDirectory removes source/binary',
                }, indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_model_level_state=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
