"""Check contained-item player selectors, queue transfer and drop decisions.

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
from test_early_jump_walkoff import continued_macro

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-item-players.json'


class EarlyItemPlayersTests(unittest.TestCase):
    def test_item_player_counts_and_consumers(self):
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
        source = (engine / 'openbor.c').read_text()
        level = function(source, 'load_level')
        level, cases = switch_cases(level.replace('switch(cmd)', 'switch(level_command)', 1),
                                    'load_level', 'level_command')
        labels = ['CMD_LEVEL_ITEM', 'CMD_LEVEL_2PITEM', 'CMD_LEVEL_3PITEM', 'CMD_LEVEL_4PITEM']
        first, last = cases[labels[0]]['label_start'], cases[labels[-1]]['end']
        item = level[first:last]
        self.assertTrue(all(cases[name]['label_start'] < last for name in labels))
        transfer = re.findall(r'e->itemplayer_count\s*=\s*props->itemplayer_count\s*;', function(source, 'smartspawn'))
        self.assertEqual(len(transfer), 1)
        arrays, checks = [], []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['function_sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(len(row['counts']), 4)
            self.assertTrue(all(type(value) is int and 0 <= value <= 3 for value in row['counts']))
            self.assertEqual(len(row['drops']), 4)
            self.assertTrue(all(len(values) == 4 and all(type(value) is bool for value in values)
                                for values in row['drops']))
            name = 'expected_' + str(row['revision'])
            arrays.append('static const expectation %s={%s,{%s}};' % (
                name, '{' + ','.join(map(str, row['counts'])) + '}',
                ','.join('{' + ','.join(str(int(value)) for value in values) + '}' for values in row['drops'])))
            checks.append('check(%d,&%s);' % (row['revision'], name))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "commands.h"
#define LEVEL_MAX_SPAWNS 2
#define TYPE_PLAYER 1
#define TYPE_ENEMY 2
typedef struct {char *name;} model;
typedef struct {int itemplayer_count,itemindex,at;char *item;} s_spawn_entry;
typedef struct entity {int health,dead,nograb,idling,item,itemplayer_count,boss,playerindex;
 struct entity *opponent;struct {int type,score,diesound;} modeldata;} entity;
static struct {int numspawns,bosses;s_spawn_entry spawnpoints[LEVEL_MAX_SPAWNS];} level_data,*level=&level_data;
static struct {int effectvol;} savedata;
static s_spawn_entry next;
static model contained={(char *)"Contained"};
static entity ent,*self=&ent;
static int cache_hit,cache_queries,loads,index_queries,players,drops,score_calls,sound_calls,kill_calls,level_completed;
uint32_t obor_profile_build;
@LEVEL_ERROR@
@LEVEL_ERROR_MACRO@
@MODEL_INPUT@
static model *findmodel(char *name) {assert(!strcmp(name,"Contained"));cache_queries++;return cache_hit?&contained:NULL;}
static model *load_cached_model(char *name,char *filename,int cache) {
 assert(!strcmp(name,"Contained") && !strcmp(filename,"data/level.txt") && cache==0);loads++;return &contained;
}
static int get_cached_model_index(char *name) {assert(name==contained.name);index_queries++;return 1;}
static int count_ents(int type) {assert(type==TYPE_PLAYER);return players;}
static entity *drop_item(entity *e) {assert(e==self && e->item==1);drops++;return NULL;}
static void addscore(int index,int score) {(void)index;(void)score;score_calls++;}
static void sound_play_sample(int a,int b,int c,int d,int e) {(void)a;(void)b;(void)c;(void)d;(void)e;sound_calls++;}
static void kill_all_enemies(void) {kill_calls++;}
@DEATH@
#define GET_ARG(z) ((void)(z),(char *)"Contained")
#define GET_INT_ARG(z) ((void)(z),41)
static void dispatch(levelCommands cmd) {
 model *cached_model=NULL,*tempmodel=NULL;char *filename=(char *)"data/level.txt",*errormessage=NULL;
 @LEVEL_ERROR_STORAGE@
 switch(cmd) {
 @ITEM@
 case CMD_LEVEL_AT: @AT@
 default:abort();
 }
 return;
 lCleanup: assert(!errormessage);
}
static void transfer(s_spawn_entry *props,entity *e) {
 e->item=props->itemindex;
 @TRANSFER@
}
typedef struct {int counts[4],drops[4][4];} expectation;
static const levelCommands commands[]={CMD_LEVEL_ITEM,CMD_LEVEL_2PITEM,CMD_LEVEL_3PITEM,CMD_LEVEL_4PITEM};
@ARRAYS@
static void check(unsigned revision,const expectation *expected) {
 obor_profile_build=revision;
 for(cache_hit=0;cache_hit<2;cache_hit++) for(int command=0;command<4;command++) {
  memset(&next,0,sizeof(next));memset(&level_data,0,sizeof(level_data));
  cache_queries=loads=index_queries=0;
  dispatch(commands[command]);
  assert(next.itemplayer_count==expected->counts[command] && next.item==contained.name && next.itemindex==1);
  assert(cache_queries==1 && loads==!cache_hit && index_queries==1);
  dispatch(CMD_LEVEL_AT);
  assert(level->numspawns==1 && level->spawnpoints[0].at==41);
  assert(next.itemplayer_count==0 && !next.item && !next.itemindex && !next.at);
  for(players=1;players<=4;players++) {
   memset(self,0,sizeof(*self));self->modeldata.diesound=-1;
   transfer(&level->spawnpoints[0],self);assert(self->itemplayer_count==expected->counts[command]);
   drops=score_calls=sound_calls=kill_calls=0;checkdeath();
   assert(drops==expected->drops[command][players-1]);
   assert(self->dead && self->nograb && !self->idling && !score_calls && !sound_calls && !kill_calls);
  }
  // Repeated directives on the same entry must replace the previous selector.
  dispatch(CMD_LEVEL_4PITEM);dispatch(CMD_LEVEL_ITEM);assert(next.itemplayer_count==0);
  dispatch(CMD_LEVEL_2PITEM);assert(next.itemplayer_count==expected->counts[1]);
 }
}
int main(void) {@CHECKS@ puts("early_item_players=1");return 0;}
'''
        replacements = dict(DEATH=function(source, 'checkdeath'), ITEM=item, MODEL_INPUT=function(source, 'obor_model_input'),
                            LEVEL_ERROR=function(source, 'obor_level_error'),
                            LEVEL_ERROR_MACRO=continued_macro(source, 'OBOR_LEVEL_ERROR'),
                            LEVEL_ERROR_STORAGE=re.search(r'char legacy_level_error\[\d+\][^;]*;', level).group(),
                            AT=cases['CMD_LEVEL_AT']['body'], TRANSFER=transfer[0],
                            ARRAYS='\n'.join(arrays), CHECKS='\n'.join(checks))
        for key, value in replacements.items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-item-players-') as name:
            work = Path(name)
            unit, binary = work / 'probe.c', work / 'probe'
            unit.write_text(program)
            cc = shlex.split(os.environ.get('HOST_CC', 'cc'))
            flags = ['-std=gnu99', '-O1', '-g', '-UNDEBUG', '-DUNIT_TEST=1', '-Wall', '-Wextra', '-Werror',
                     '-Wno-error=deprecated-declarations', '-Wno-sign-compare', '-Wno-unused-but-set-variable',
                     '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                     '-I' + str(engine / 'source/scriptlib'), '-I' + str(engine / 'source/gamelib')]
            build = subprocess.run(cc + flags + [str(unit), *([] if sys.platform == 'darwin' else ['-no-pie']),
                                   '-o', str(binary)], capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=15, env=sanitizer_environment())
            if os.environ.get('OBOR_ITEM_PLAYERS_OBSERVATIONS'):
                Path(os.environ['OBOR_ITEM_PLAYERS_OBSERVATIONS']).write_text(json.dumps({
                    'compiler': cc, 'flags': flags, 'contexts': len(rows),
                    'probe_sha256': hashlib.sha256(program.encode()).hexdigest(),
                    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                    'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                    'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr,
                    'retirement': 'TemporaryDirectory removes source/binary',
                }, indent=2) + '\n')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_item_players=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
