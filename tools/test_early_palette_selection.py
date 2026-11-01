"""Check source-defined remap palettes and entity default-map selection.

Reduced model/entity providers isolate palette bytes, borrowed pointers and
the spawn initialization window. Image decoding, model ownership and complete
spawn/game execution have separate tests.
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
from test_historical_player import function, switch_cases

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/profile-early-palette-selection.json'


class EarlyPaletteSelectionTests(unittest.TestCase):
    def test_profile_registry_coverage(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        profiles = json.loads((ROOT / 'src/pin.json').read_text())['profiles']
        for profile in contract_profiles(fixture, profiles):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)

    def test_native_remap_default_map_and_spawn_window(self):
        fixture = load_contract_fixture(FIXTURE)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        core = (engine / 'openbor.c').read_text()
        header = (engine / 'openbor.h').read_text()
        limit = re.search(r'(?m)^#define\s+MAX_COLOUR_MAPS\s+(\d+)\b', header)
        self.assertIsNotNone(limit)
        loader = function(core, 'load_cached_model')
        loader = loader.replace('switch(cmd)', 'switch(fixture_model_command)', 1)
        unused, cases = switch_cases(loader, 'load_cached_model', 'fixture_model_command')
        spawn = function(core, 'spawn')
        start = spawn.index('e->nextthink = time + 1;')
        stop = spawn.index('e->lifespancountdown = model->lifespan;', start)
        stop += len('e->lifespancountdown = model->lifespan;')
        self.assertLess(stop, spawn.index('ent_default_init(e);'))
        window = spawn[start:stop]
        self.assertEqual(window.count('ent_set_colourmap(e, 0)'), 1)
        checks = ['check(%d,%d,%d,%d);' % (r['revision'], r['source_palette'],
                  r['default_palette'], r['spawn_default']) for r in fixture['sources']]
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#define MAX_COLOUR_MAPS @LIMIT@
enum {PIXEL_8,PIXEL_x8,PIXEL_16,PIXEL_32=4,CMD_MODEL_REMAP=100};
static const int pixelbytes[]={1,1,2,0,4};
static int screenformat,pixelformat;
#define PAL_BYTES (screenformat==PIXEL_8?768:pixelbytes[screenformat]*256)
typedef struct {unsigned char *palette,*colourmap[MAX_COLOUR_MAPS];int maps_loaded,lifespan;} s_model;
typedef struct {s_model modeldata;unsigned char *colourmap;unsigned map,nextthink;int lifespancountdown;} entity;
static uint32_t obor_profile_build;
static unsigned time=23,allocations,loads,selections;
static int image_ok;
static unsigned char pal[1024],existing[1024],tables[MAX_COLOUR_MAPS];
static char *arguments[]={NULL,"first","second"};
static const char *packfile="fixture.pak",*shutdownmessage;
#define GET_ARG(n) arguments[n]
#define OBOR_MODEL_ERROR(modern,...) (modern)
static int load_colourmap(s_model *model,char *first,char *second){
 assert(!strcmp(first,"first") && !strcmp(second,"second"));
 model->colourmap[model->maps_loaded]=tables;model->maps_loaded++;return 1;
}
static void *obor_profile_malloc_named(const char *name,size_t bytes){
 assert(name && *name && bytes==(size_t)PAL_BYTES);allocations++;
 void *p=calloc(1,bytes);assert(p);return p;
}
static int loadimagepalette(char *name,const char *pak,unsigned char *palette){
 assert(!strcmp(name,"first") && pak==packfile && allocations==1 && palette);
 loads++;if(!image_ok)return 0;memset(palette,17,PAL_BYTES);return 1;
}
static int remap(s_model *newchar,unsigned char *mapflag){
 char *value,*value2;int errorVal;
 switch(CMD_MODEL_REMAP){case CMD_MODEL_REMAP:@REMAP@}
 return 1;
lCleanup:return 0;
}
@SETTER@
static void observed_selection(entity *e,unsigned which){
 assert(which==0 && e->nextthink==time+1 && e->lifespancountdown==0);
 selections++;ent_set_colourmap(e,which);
}
#define ent_set_colourmap observed_selection
static void spawn_window(entity *e,s_model *model){@SPAWN@}
#undef ent_set_colourmap
static void check(unsigned revision,int source_palette,int default_palette,int spawn_default){
 obor_profile_build=revision;memset(pal,29,sizeof(pal));memset(existing,55,sizeof(existing));
 for(screenformat=PIXEL_16;screenformat<=PIXEL_32;screenformat+=2)
 for(int indexed=0;indexed<2;indexed++)for(int prior=0;prior<2;prior++)for(image_ok=0;image_ok<2;image_ok++){
  pixelformat=indexed?PIXEL_x8:PIXEL_8;
  s_model model={0};unsigned char flags[MAX_COLOUR_MAPS]={0};
  model.palette=prior?existing:NULL;allocations=loads=0;shutdownmessage=NULL;
  int create=indexed && !prior;
  int failure=create && source_palette && !image_ok;
  assert(remap(&model,flags)==!failure);
  assert(model.maps_loaded==1 && flags[0]==!failure);
  assert(allocations==(unsigned)create && loads==(unsigned)(create && source_palette));
  if(failure)assert(shutdownmessage && !strcmp(shutdownmessage,"Failed to load palette!"));
  else assert(!shutdownmessage);
  if(create){
   assert(model.palette);
   if(!failure)for(int i=0;i<PAL_BYTES;i++)assert(model.palette[i]==(source_palette?17:29));
   free(model.palette);
  }else assert(model.palette==(prior?existing:NULL));
  for(unsigned i=0;i<sizeof(existing);i++)assert(existing[i]==55);
 }
 const unsigned indices[]={0,1,2,MAX_COLOUR_MAPS,MAX_COLOUR_MAPS+1,UINT_MAX};
 for(int present=0;present<2;present++){
  entity e={0};e.modeldata.palette=present?existing:NULL;e.modeldata.maps_loaded=2;e.modeldata.lifespan=123;
  for(unsigned i=0;i<MAX_COLOUR_MAPS;i++)e.modeldata.colourmap[i]=tables+i;
  for(unsigned i=0;i<sizeof(indices)/sizeof(*indices);i++){
   unsigned requested=indices[i],selected=requested>MAX_COLOUR_MAPS?0:requested;
   e.colourmap=pal;e.map=17;ent_set_colourmap(&e,requested);
   unsigned char *expected=selected?e.modeldata.colourmap[selected-1]:default_palette?e.modeldata.palette:NULL;
   assert(e.map==selected && e.colourmap==expected);
  }
  e.colourmap=NULL;e.map=0;e.nextthink=0;e.lifespancountdown=0;selections=0;
  spawn_window(&e,&e.modeldata);
  assert(selections==(unsigned)spawn_default && e.nextthink==time+1 && e.lifespancountdown==123);
  assert(e.map==0 && e.colourmap==(spawn_default?e.modeldata.palette:NULL));
 }
}
int main(void){@CHECKS@ puts("early_palette_selection=1");return 0;}
'''
        for name, value in {'LIMIT':limit[1], 'REMAP':cases['CMD_MODEL_REMAP']['body'],
                            'SETTER':function(core, 'ent_set_colourmap'), 'SPAWN':window,
                            'CHECKS':'\n'.join(checks)}.items():
            program = program.replace('@' + name + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-palette-selection-') as directory:
            source, binary = Path(directory) / 'probe.c', Path(directory) / 'probe'
            source.write_text(program)
            flags = ['-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-deprecated-declarations',
                     '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
            compiler = shlex.split(os.environ.get('HOST_CC', os.environ.get('CC', 'cc')))
            built = subprocess.run(compiler + flags + [str(source), *([] if sys.platform == 'darwin' else ['-no-pie']),
                                   '-o', str(binary)], capture_output=True, text=True, timeout=45)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30,
                                 env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_palette_selection=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
