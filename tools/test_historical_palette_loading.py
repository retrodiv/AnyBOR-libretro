"""Compare colourmap loading with each profile's own source contract.

Actual loader functions run with reduced models and deterministic bitmap I/O.
This checks slot selection, limits, mapping bytes and failure side effects;
model command parsing, palette conversion and complete lifecycle are separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from test_historical_player import function, rename_identifiers

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
CONTRACTS = load_contract_fixture(Path(__file__).parent /
    'fixtures/profile-palette-loading-contracts.json')


def colourmap_storage_support(source):
    if 'obor_colourmap_table_reserve' not in source and 'obor_colourmap_find' not in source:
        return ''
    header = SOURCE / 'src/port/libretro/obor_colourmap_storage.h'
    if not header.is_file():
        raise ValueError('The tested engine requires its bound colourmap storage header')
    return '#include '+json.dumps(str(header.resolve()))+'\n'


def loading_checks(row, model_type, loader, *, generated, managed=False):
    revision = row['revision']
    fixed = bool(row['fixed_slots'])
    extent = 'model->colourmap_capacity' if generated else '30' if fixed else '(unsigned char)model->maps_loaded'
    free_table = 'free(model->colourmap);' if generated or not fixed else ''
    cleanup = 'for(unsigned i=0;i<extent;++i) free(model->colourmap[i]);'+free_table
    if managed:
        cleanup = 'if(!obor_colourmap_owner_release(model)) {'+cleanup+'}'
    hole_free = ('assert(obor_colourmap_replace(model.colourmap,1,NULL));' if managed else
                 'free(model.colourmap[1]);model.colourmap[1]=NULL;')
    text = r'''
static void finish_@REV@(@MODEL@ *model) {
 unsigned extent=@EXTENT@;
 @CLEANUP@
 *model=(@MODEL@){0};assert(live_bitmaps==0);
}
static void check_@REV@(void) {
 obor_profile_build=@REV@;
 @MODEL@ model={0};
 for(int i=0;i<31;++i) {
  int result=@LOAD@(&model,"first","second");
  if(@FIXED@ && i==30) {assert(result==-1 && model.maps_loaded==30);break;}
  assert(result==1 && model.maps_loaded==i+1);
  unsigned char *map=model.colourmap[i];assert(map);
  for(unsigned j=0;j<256;++j) {
   unsigned expected=j==0?7:j==1?8:j==3?9:j==4?10:j;
   assert(map[j]==expected);
  }
 }
 finish_@REV@(&model);
 // The fixed loader searches the first empty slot and assigns k+1, even if
 // that decreases the counter. Dynamic loaders append after existing holes.
 for(int i=0;i<3;++i) assert(@LOAD@(&model,"first","second")==1);
 @HOLE_FREE@
 unsigned char *third=model.colourmap[2];
 assert(@LOAD@(&model,"first","second")==1);
 assert(model.maps_loaded==(@FIXED@?2:4));
 assert(model.colourmap[2]==third);
 assert(@FIXED@?model.colourmap[1]!=NULL:
     model.colourmap[1]==NULL && model.colourmap[3]!=NULL);
 finish_@REV@(&model);
 // Each refusal is observed from both an empty model and an existing map.
 for(int seeded=0;seeded<=1;++seeded) for(int failure=0;failure<4;++failure) {
  if(seeded) assert(@LOAD@(&model,"first","second")==1);
  unsigned char *before=seeded?model.colourmap[0]:NULL;
  fail_map_malloc=failure==1;
  const char *first=failure==2?"missing":"first";
  const char *second=failure==3?"missing":failure==0?"FIRST":"second";
  assert(@LOAD@(&model,(char*)first,(char*)second)==
     (failure==0?0:failure==1?-2:failure==2?-3:-4));
  assert(fail_map_malloc==0);
  assert(model.maps_loaded==seeded+(!@FIXED@ && failure!=0));
  if(seeded) assert(model.colourmap[0]==before);
  if(!@FIXED@ && failure!=0) assert(model.colourmap[seeded]==NULL);
  assert(live_bitmaps==0);
  // A successful retry fills the fixed slot or appends after the failed slot.
  assert(@LOAD@(&model,"first","second")==1);
  assert(model.maps_loaded==seeded+1+(!@FIXED@ && failure!=0));
  finish_@REV@(&model);
 }
}
'''
    values = {'REV': str(revision), 'MODEL': model_type, 'EXTENT': extent,
              'CLEANUP': cleanup, 'HOLE_FREE': hole_free, 'LOAD': loader, 'FIXED': str(int(fixed))}
    return re.sub(r'@('+'|'.join(values)+r')@', lambda m: values[m[1]], text)


def bitmap_fixture():
    return r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdio.h>
#define MAX_COLOUR_MAPS 30
#define MAX_PAL_SIZE 1024
#define PIXEL_8 1
#define stricmp strcasecmp
static uint32_t obor_profile_build;
static unsigned live_bitmaps;
static int fail_map_malloc;
static const char *packfile="fixture";
typedef struct {int width,height;unsigned char data[6];} s_bitmap;
static s_bitmap *loadbitmap(char *name,const char *pak,int format) {
 (void)pak;assert(format==PIXEL_8);
 if(!strcmp(name,"missing")) return NULL;
 s_bitmap *bitmap=malloc(sizeof(*bitmap));assert(bitmap);++live_bitmaps;
 if(!strcmp(name,"first")) {
  bitmap->width=3;bitmap->height=2;
  memcpy(bitmap->data,(unsigned char[]){0,1,2,3,4,255},6);
 } else {
  bitmap->width=2;bitmap->height=2;
  memcpy(bitmap->data,(unsigned char[]){7,8,9,10,11,12},6);
 }
 return bitmap;
}
static void freebitmap(s_bitmap *bitmap) {assert(bitmap);--live_bitmaps;free(bitmap);}
static void *fixture_malloc(size_t bytes) {
 if(fail_map_malloc) {fail_map_malloc=0;return NULL;}return malloc(bytes);
}
#define malloc fixture_malloc
'''


def loading_program(components=None, contracts=None, *, allocation_macro=''):
    rows = CONTRACTS['sources'] if contracts is None else contracts
    generated = components is None
    source = bitmap_fixture()
    if generated:
        engine = SOURCE / 'src/engines/3741'
        text = (engine / 'openbor.c').read_text()
        source += colourmap_storage_support(text)
        source += ('typedef struct {unsigned char **colourmap;unsigned colourmap_capacity;'
                   'int maps_loaded:8;} s_model;\n')
        source += '\n'.join(function(text, name) for name in
                            ('obor_colourmap_reserve', 'load_colourmap'))
        for row in rows:
            source += loading_checks(row, 's_model', 'load_colourmap', generated=True,
                                     managed='obor_colourmap_owner_find' in text)
    else:
        source += allocation_macro + '\n'
        for row in rows:
            revision = row['revision']
            model = 'model_'+str(revision)
            loader = 'loader_'+str(revision)
            table = 'unsigned char *colourmap[30];' if row['fixed_slots'] else 'unsigned char **colourmap;'
            source += 'typedef struct {'+table+'int maps_loaded:8;} '+model+';\n'
            source += rename_identifiers(components[revision], {'s_model': model, 'load_colourmap': loader})
            source += loading_checks(row, model, loader, generated=False)
    source += 'int main(int argc,char **argv) {\n'
    if generated:
        source += 'assert(argc==2);int revision=atoi(argv[1]);switch(revision) {\n'
        source += ''.join('case %d:check_%d();break;\n' % (row['revision'], row['revision']) for row in rows)
        source += 'default:abort();}\n'
    else:
        source += '(void)argc;(void)argv;\n'
        source += ''.join('check_%d();\n' % row['revision'] for row in rows)
        source += 'puts('+json.dumps(json.dumps({'status': 'PASS', 'sources': len(rows), 'loader_families': 2}))+');\n'
    return source+'return 0;}\n'


class HistoricalPaletteLoadingTests(unittest.TestCase):
    def test_loader_registry_covers_each_registered_profile(self):
        rows = CONTRACTS['sources']
        self.assertEqual(len({x['revision'] for x in rows}), len(rows))
        for row in rows:
            self.assertIn(row['fixed_slots'], (0, 30))
            self.assertEqual(row['max_palette_bytes'], 1024)
            for key in ('load_colourmap_sha256', 'remap_command_sha256', 'alternatepal_command_sha256'):
                self.assertRegex(row[key], r'^[0-9a-f]{64}$')
        revisions = {x['revision'] for x in rows}
        for profile in contract_profiles(Path(__file__).parent / 'fixtures/profile-palette-loading-contracts.json', json.loads((SOURCE / 'src/pin.json').read_text())['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)

    def test_original_slot_limits_mapping_and_failure_effects_per_profile(self):
        with tempfile.TemporaryDirectory(prefix='anybor-palette-loader-') as temporary:
            work = Path(temporary)
            probe, exe = work / 'probe.c', work / 'probe'
            probe.write_text(loading_program())
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-unused-variable', '-Wno-unused-function', '-fsigned-char',
                '-g', '-fsanitize=address,undefined', str(probe), '-o', str(exe)], check=True, timeout=60)
            for row in CONTRACTS['sources']:
                with self.subTest(profile=row['revision']):
                    subprocess.run([str(exe), str(row['revision'])], check=True,
                                   timeout=20, env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
