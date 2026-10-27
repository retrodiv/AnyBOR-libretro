"""Compare colourtable getter results with each original source contract.

The fixture retains callback entry/exit, variant conversion and the native map
helper. It models table allocation extents, including the signed count width;
numeric mapper stubs and reduced layouts do not prove complete model loading.
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
from test_historical_player import function, rename_identifiers, switch_cases

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
CONTRACTS = load_contract_fixture(Path(__file__).parent /
    'fixtures/profile-colourtable-read-contracts.json')


def storage_program():
    """Exercise actual growth/loading/owned-free branches with bitmap I/O stubs."""
    engine = SOURCE / 'src/engines/3741'
    source = (engine / 'openbor.c').read_text()
    header = (engine / 'openbor.h').read_text()
    method = function(source, 'load_cached_model')
    # The loader has another switch(cmd) for animation commands. Isolate the
    # first switch's selector; selected case bodies remain byte-for-byte native.
    method = method.replace('switch(cmd)', 'switch(fixture_model_commands)', 1)
    _, cases = switch_cases(method, 'load_cached_model', 'fixture_model_commands')
    selected = '\n'.join('case '+key+':'+cases[key]['body'] for key in
                         ('CMD_MODEL_REMAP', 'CMD_MODEL_ALTERNATEPAL'))
    free_model = function(source, 'free_model')
    if 'obor_colourmap_owner_find' in free_model:
        cleanup = re.search(r'(?ms)^[\t ]*if\(obor_colourmap_owner_find\(model\)\)\n.*?'
                            r'(?=\n\tprintf\("\."\);)', free_model)
    else:
        cleanup = re.search(r'(?ms)\bif\(hasFreetype\(model, MF_COLOURMAP\)\)\s*\{.*?^\t\}', free_model)
    macro = re.search(r'(?m)^#define[\t ]+__realloc\([^\n]*\n(?:[^\n]*\\\n)*[^\n]*', header)
    if cleanup is None or macro is None:
        raise ValueError('Own allocation and owned-free source regions required')
    functions = '\n'.join(function(source, name) for name in
        ('obor_colourmap_reserve', 'obor_mapflag_reserve', 'load_colourmap', 'hasFreetype'))
    program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
typedef enum {MF_NONE=0,MF_COLOURMAP=2} ModelFreetype;
typedef struct {unsigned char **colourmap;unsigned colourmap_capacity;
 int maps_loaded:8;unsigned char *palette;ModelFreetype freetypes;} s_model;
typedef struct {int width,height;unsigned char data[4];} s_bitmap;
enum {PIXEL_8=1,PIXEL_x8=2,CMD_MODEL_REMAP=1,CMD_MODEL_ALTERNATEPAL=2};
#define MAX_COLOUR_MAPS 30
#define MAX_PAL_SIZE 1024
#define PAL_BYTES 1024
#define stricmp strcasecmp
static uint32_t obor_profile_build=3741;
static const char *packfile="fixture";
static char *arguments[]={NULL,"first","second"};
static unsigned char *mapflag;
static unsigned int mapflag_capacity;
static int pixelformat=PIXEL_x8,fail_next_realloc;
static const char *shutdownmessage;
static void *fixture_realloc(void *p,size_t bytes) {
 if(fail_next_realloc) {fail_next_realloc=0;return NULL;}return realloc(p,bytes);
}
#define realloc fixture_realloc
static s_bitmap *loadbitmap(char *name,const char *pak,int format) {
 (void)pak;assert(format==PIXEL_8);
 if(!strcmp(name,"missing")) return NULL;
 s_bitmap *bitmap=malloc(sizeof(*bitmap));assert(bitmap);bitmap->width=bitmap->height=2;
 for(int i=0;i<4;++i) bitmap->data[i]=(unsigned char)(i+(!strcmp(name,"second")));
 return bitmap;
}
static void freebitmap(s_bitmap *bitmap) {free(bitmap);}
static int loadimagepalette(char *name,const char *pak,unsigned char *palette) {
 (void)pak;if(!strcmp(name,"missing")) return 0;memset(palette,17,PAL_BYTES);return 1;
}
static int quiet_printf(const char *format,...) {(void)format;return 0;}
#define printf quiet_printf
#define GET_ARG(n) arguments[n]
@REALLOC@
@STORAGE@
@FUNCTIONS@
static int command(s_model *newchar,int cmd) {
 char *value=NULL,*value2=NULL,*command="fixture";
 int errorVal=0;shutdownmessage=NULL;
 switch(cmd) {@CASES@ default:abort();}
 return 1;
lCleanup:
 assert(shutdownmessage);return 0;
}
static void owned_free(s_model *model) {int i;@FREE@}
static void reset(s_model *model) {*model=(s_model){0};model->freetypes=MF_COLOURMAP;mapflag=NULL;mapflag_capacity=0;}
static void finish(s_model *model) {
 owned_free(model);assert(!model->colourmap && !model->colourmap_capacity && !model->maps_loaded);
 free(model->palette);model->palette=NULL;free(mapflag);mapflag=NULL;mapflag_capacity=0;
}
int main(void) {
 for(int route=CMD_MODEL_REMAP;route<=CMD_MODEL_ALTERNATEPAL;++route) {
  s_model model;reset(&model);
  for(int i=0;i<128;++i) {
   assert(command(&model,route));assert(model.colourmap_capacity==(unsigned)i+1);
   assert(model.maps_loaded==(i<127?i+1:-128));assert(model.colourmap[i]);
   if(route==CMD_MODEL_REMAP) {for(int j=0;j<=i;++j) assert(mapflag[j]==1);assert(model.colourmap[i][0]==1);}
   else {assert(mapflag[i]==0);assert(model.colourmap[i][0]==17);}
   if(i==2) {
    unsigned char **before=model.colourmap;unsigned capacity=model.colourmap_capacity;
    fail_next_realloc=1;assert(!obor_colourmap_reserve(&model,capacity+1));
    assert(model.colourmap==before && model.colourmap_capacity==capacity);
   }
  }
  unsigned char **before=model.colourmap;assert(!command(&model,route));
  assert(model.colourmap==before && model.colourmap_capacity==128 && model.maps_loaded==-128);
  s_model borrowed=model;borrowed.freetypes=MF_NONE;owned_free(&borrowed);
  assert(borrowed.colourmap==model.colourmap && borrowed.colourmap_capacity==128);
  finish(&model);
 }
 // Same-image failure once wrote mapflag[-1]. Keep the original refusal and
 // exercise the defined cleanup route without touching a negative index.
 s_model model;reset(&model);arguments[2]="first";assert(!command(&model,CMD_MODEL_REMAP));
 assert(!model.maps_loaded && !model.colourmap_capacity);finish(&model);arguments[2]="second";
 // The source loader's negative bitmap error remains observable. Its newly
 // initialized null table slot is owned and can be released safely.
 reset(&model);arguments[2]="missing";assert(command(&model,CMD_MODEL_REMAP));
 assert(model.maps_loaded==1 && model.colourmap_capacity==1 && !model.colourmap[0]);finish(&model);
 return 0;
}
'''
    from test_historical_palette_loading import colourmap_storage_support
    insertions = {'REALLOC': macro[0], 'STORAGE': colourmap_storage_support(source),
                  'FUNCTIONS': functions, 'CASES': selected, 'FREE': cleanup[0]}
    return re.sub(r'@('+'|'.join(insertions)+r')@', lambda m: insertions[m[1]], program)


def colourtable_entry(source, name='openbor_getentityproperty'):
    method, cases = switch_cases(source, 'openbor_getentityproperty', 'propind')
    for label, row in sorted(cases.items(), key=lambda item: item[1]['label_start'], reverse=True):
        if label not in ('_ep_colourtable', 'default'):
            method = method[:row['label_start']] + method[row['end']:]
    return rename_identifiers(method, {'openbor_getentityproperty': name})


def colourtable_program(components=None, common=None, contracts=None, *, original=False):
    rows = CONTRACTS['sources'] if contracts is None else contracts
    if components is None:
        engine = SOURCE / 'src/engines/3741'
        components = {'entries': colourtable_entry((engine / 'openborscript.c').read_text()),
            'invoke': 'return openbor_getentityproperty(args,output,count);',
            'translation': 'static int obor_entity_get_property_native(int property) {return property;}'}
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        common = {name: function(variants, name) for name in
                  ('ScriptVariant_ChangeType', 'ScriptVariant_Clear')}
        common['model_get_colourmap'] = function((engine / 'openbor.c').read_text(), 'model_get_colourmap')
    if common is None:
        raise ValueError('Explicit source conversions and map helper required')
    contracts_c = ','.join('{%d,%d}' % (row['revision'],
        {'fixed_table': 0, 'dynamic_table': 1, 'helper': 2}[row['getter_mode']]) for row in rows)
    program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int32_t LONG,HRESULT;
typedef double DOUBLE;
typedef void VOID;
typedef enum {VT_EMPTY=0,VT_INTEGER=1,VT_DECIMAL=2,VT_PTR=5,VT_STR=6} VARTYPE;
typedef struct {union {LONG lVal;DOUBLE dblVal;void *ptrVal;int strVal;};VARTYPE vt;} ScriptVariant;
typedef struct {int marker;} s_sprite,s_attack;
typedef struct {unsigned char **colourmap;int maps_loaded:8;
 unsigned char *palette;unsigned colourmap_capacity;} s_model;
typedef struct {s_model modeldata;} entity;
enum {_ep_colourtable};
#define MAX_COLOUR_MAPS 30
#define S_OK 0
#define E_FAIL (-1)
static uint32_t obor_profile_build;
static unsigned char palette[1],colours[128];
static entity subject;
static int StrCache_Pop(void) {abort();}
static void StrCache_Collect(int index) {(void)index;abort();}
static int quiet_printf(const char *format,...) {(void)format;return 0;}
#define printf quiet_printf
@CONVERSIONS@
@MAP_HELPER@
static void mapstrings_getentityproperty(ScriptVariant **args,int count) {(void)args;(void)count;}
@TRANSLATION@
@ENTRIES@
static HRESULT invoke(ScriptVariant **args,ScriptVariant **output,int count) {@INVOKE@}
struct contract {int revision,mode;};
static const struct contract contracts[]={@CONTRACTS@};
static void query(const struct contract *c,LONG index,unsigned extent,int count) {
 unsigned which=(unsigned)index+1u;
 unsigned char *expected=NULL;
 int defined=1;
 if(count<3) defined=0;
 else if(c->mode==2) {
  // The original signed LONG addition itself is undefined at INT32_MAX.
  if(index==INT32_MAX) defined=0;
  if(which==0 || which>(unsigned)subject.modeldata.maps_loaded) expected=palette;
  else if(which>extent || !subject.modeldata.colourmap) defined=0;
  else expected=subject.modeldata.colourmap[which-1];
 } else if(index<0 || (unsigned)index>=extent) defined=0;
 else expected=subject.modeldata.colourmap[index];
#if !@GENERATED@
 if(!defined) return;
#else
 if(!defined && !(c->mode==2 && (which==0 || which>(unsigned)subject.modeldata.maps_loaded)))
  expected=NULL;
#endif
 ScriptVariant values[3]={{.vt=VT_PTR,.ptrVal=&subject},
  {.vt=VT_INTEGER,.lVal=_ep_colourtable},{.vt=VT_INTEGER,.lVal=index}},*args[3];
 for(int i=0;i<3;++i) args[i]=&values[i];
 ScriptVariant result={.vt=VT_INTEGER,.lVal=999},*output=&result;
 assert(invoke(args,&output,count)==S_OK);assert(output==&result);
 if(count<3) assert(result.vt==VT_EMPTY);
 else {assert(result.vt==VT_PTR);assert(result.ptrVal==expected);}
}
static void check(const struct contract *c) {
 obor_profile_build=c->revision;
 int loaded[]={0,1,3,30,31,127,128};
 for(unsigned state=0;state<sizeof(loaded)/sizeof(*loaded);++state) {
  int n=loaded[state];if(c->mode==0 && n>MAX_COLOUR_MAPS) continue;
  unsigned extent=c->mode==0?MAX_COLOUR_MAPS:(unsigned)n;
  subject=(entity){0};subject.modeldata.maps_loaded=n;
  if(n==128) assert(subject.modeldata.maps_loaded==-128);
  subject.modeldata.palette=palette;subject.modeldata.colourmap_capacity=extent;
  subject.modeldata.colourmap=extent?calloc(extent,sizeof(*subject.modeldata.colourmap)):NULL;
  assert(!extent || subject.modeldata.colourmap);
  for(int i=0;i<n;++i) subject.modeldata.colourmap[i]=&colours[i];
  for(LONG index=-2;index<=(LONG)extent+1;++index) query(c,index,extent,3);
  query(c,INT32_MIN,extent,3);query(c,INT32_MAX-1,extent,3);query(c,INT32_MAX,extent,3);
#if @GENERATED@
  query(c,0,extent,2);
#endif
  free(subject.modeldata.colourmap);
 }
#if @GENERATED@
 subject=(entity){0};subject.modeldata.maps_loaded=3;subject.modeldata.palette=palette;
 query(c,0,0,3);query(c,-1,0,3);
#endif
}
int main(int argc,char **argv) {
 assert(argc==2);int revision=atoi(argv[1]),matched=0;
 for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i)
  if(contracts[i].revision==revision) {check(&contracts[i]);++matched;}
 assert(matched==1);return 0;
}
'''
    if original:
        program = program[:program.index('int main(int argc,char **argv)')] + (
            'int main(void) {for(unsigned i=0;i<sizeof(contracts)/sizeof(*contracts);++i)'
            'check(&contracts[i]);puts(' + json.dumps(json.dumps({
                'status': 'PASS', 'sources': len(rows), 'modes': 3})) + ');return 0;}\n')
    insertions = {'CONVERSIONS': '\n'.join(common[name] for name in
        ('ScriptVariant_ChangeType', 'ScriptVariant_Clear')),
        'MAP_HELPER': common['model_get_colourmap'],
        'TRANSLATION': components.get('translation', ''), 'ENTRIES': components['entries'],
        'INVOKE': components['invoke'], 'CONTRACTS': contracts_c, 'GENERATED': str(int(not original))}
    return re.sub(r'@(' + '|'.join(insertions) + r')@', lambda m: insertions[m[1]], program)


class ColourtableReadTests(unittest.TestCase):
    def test_actual_storage_growth_both_loaders_and_owned_cleanup(self):
        with tempfile.TemporaryDirectory(prefix='anybor-colourtable-storage-') as temporary:
            work=Path(temporary);source=work/'probe.c';exe=work/'probe'
            source.write_text(storage_program())
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-unused-variable','-Wno-unused-function','-Wno-sign-compare',
                '-g','-fsanitize=address,undefined',str(source),'-o',str(exe)],check=True,timeout=60)
            subprocess.run([str(exe)],check=True,timeout=20,env=sanitizer_environment())

    def test_registry_covers_each_registered_native_chain_profile(self):
        revisions = [row['revision'] for row in CONTRACTS['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        for row in CONTRACTS['sources']:
            self.assertIn(row['getter_mode'], ('fixed_table', 'dynamic_table', 'helper'))
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['counter_bits'], 8)
            for digest in row['source_hashes'].values():
                if digest is not None:
                    self.assertRegex(digest, r'^[0-9a-f]{64}$')
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        for profile in contract_profiles(Path(__file__).parent / 'fixtures/profile-colourtable-read-contracts.json', pin['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)

    def test_own_source_colourtable_results_and_bounded_reads_per_profile(self):
        with tempfile.TemporaryDirectory(prefix='anybor-colourtable-read-') as temporary:
            work=Path(temporary);source=work/'probe.c';exe=work/'probe'
            source.write_text(colourtable_program())
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-unused-variable','-Wno-unused-function','-Wno-sign-compare',
                '-g','-fsanitize=address,undefined',
                str(source),'-o',str(exe)],check=True,timeout=60)
            for row in CONTRACTS['sources']:
                with self.subTest(profile=row['revision']):
                    subprocess.run([str(exe),str(row['revision'])],check=True,
                        timeout=20,env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
