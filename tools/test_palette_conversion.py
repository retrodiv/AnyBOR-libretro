"""Check native palette conversion and bounded missing-map handling.

Actual converter bodies run with reduced models and source-derived flag/count
types. Fatal allocation callbacks use a controlled jump. This proves converter
results, not complete loaders, subclass ownership or rendering.
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
import sys
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from native_allocation_policy import bind_named_allocation_support
from test_historical_player import function
from test_historical_palette_loading import colourmap_storage_support

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', ROOT))
CONTRACTS = load_contract_fixture(Path(__file__).parent /
    'fixtures/palette-conversion-contracts.json')


def conversion_program(engine, body=None, row=None, *, original=False, source_rows=None):
    row = CONTRACTS['engines'][engine] if row is None else row
    if row['flag_type'] not in ('unsigned char', 'unsigned') or row['counter'] not in ('char8', 'int8', 'int'):
        raise ValueError('Explicit source flag/count representations required')
    if body is None:
        source = (SOURCE / 'src/engines' / engine / 'openbor.c').read_bytes().decode('utf-8', 'surrogateescape')
        body = function(source, 'convert_map_to_palette')
    fixed = row['fixed_table']
    counter = {'char8': 'char maps_loaded:8;', 'int8': 'int maps_loaded:8;',
               'int': 'int maps_loaded;'}[row['counter']]
    table = 'unsigned char *colourmap[30];' if fixed else 'unsigned char **colourmap;'
    formats = '0,1,2,3,4' if row['format_dependent'] else '-1,0,1,2,3,4,5'
    program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <setjmp.h>
@PROFILE@
#define MAX_PAL_SIZE 1024
#define MAX_COLOUR_MAPS 30
#define PIXEL_8 0
#define PIXEL_x8 1
#define PIXEL_16 2
#define PIXEL_32 4
static int screenformat=PIXEL_32;
static int pixelbytes[5]={1,1,2,3,4};
@PALETTE_MACRO@
typedef @FLAG@ fixture_flag;
typedef struct {@TABLE@ @COUNTER@ unsigned colourmap_capacity;
 unsigned char *palette;const char *name;} s_model;
static jmp_buf fatal_jump;
static int fatal_active,fatal_count,fail_after=-1;
static void fixture_fatal(int code,const char *format,...) {
 assert(fatal_active && code==1 && strstr(format,"convert_map_to_palette"));
 ++fatal_count;longjmp(fatal_jump,1);
}
#define shutdown fixture_fatal
#define borShutdown fixture_fatal
static void *fixture_malloc(size_t bytes) {
 if(fail_after==0) {fail_after=-1;return NULL;}
 if(fail_after>0) --fail_after;
 return malloc(bytes);
}
#define malloc fixture_malloc
/* NATIVE ALLOCATION POLICY */
@STORAGE@
@BODY@
static s_model *create(unsigned count,unsigned mask) {
 s_model *model=calloc(1,sizeof(*model));assert(model);model->name="fixture";
 model->maps_loaded=(int)count;model->colourmap_capacity=count;
#if !@FIXED@
 model->colourmap=calloc(count?count:1,sizeof(*model->colourmap));assert(model->colourmap);
#endif
 model->palette=malloc(PAL_BYTES);assert(model->palette);
 for(unsigned i=0;i<(unsigned)PAL_BYTES;++i) model->palette[i]=(unsigned char)(i*29u+11u);
 for(unsigned c=0;c<count;++c) {
  unsigned bytes=(mask&(1u<<c))?256:(unsigned)PAL_BYTES;
  model->colourmap[c]=malloc(bytes);assert(model->colourmap[c]);
  for(unsigned i=0;i<bytes;++i) model->colourmap[c][i]=(unsigned char)(
    mask&(1u<<c)?i%3==0?i:(i*37u+c+5u):i*7u+c+3u);
 }
 return model;
}
static void destroy(s_model *model,unsigned extent) {
 for(unsigned i=0;i<extent;++i) free(model->colourmap[i]);
#if !@FIXED@
 free(model->colourmap);
#endif
 free(model->palette);free(model);
}
static void expected(s_model *model,fixture_flag flags[3],unsigned char output[3][MAX_PAL_SIZE]) {
 unsigned pb=@FORMAT_DEP@?pixelbytes[screenformat]:pixelbytes[PIXEL_32];
 for(unsigned c=0;c<3;++c) {
  memcpy(output[c],flags[c]?model->palette:model->colourmap[c],PAL_BYTES);
  if(!flags[c]) continue;
  for(unsigned i=0;i<256;++i) {
   unsigned selected=model->colourmap[c][i];if(selected==i) continue;
   memcpy(output[c]+i*pb,model->palette+selected*pb,pb);
  }
 }
}
static void check(void) {
 const int formats[]={@FORMATS@};
 for(unsigned f=0;f<sizeof(formats)/sizeof(*formats);++f) {
  screenformat=formats[f];
  for(unsigned mask=0;mask<8;++mask) {
   s_model *model=create(3,mask);fixture_flag flags[3];
   for(unsigned c=0;c<3;++c) flags[c]=mask&(1u<<c)?(fixture_flag)-1:0;
   for(unsigned pass=0;pass<2;++pass) {
    unsigned char output[3][MAX_PAL_SIZE];uintptr_t pointers[3];
    expected(model,flags,output);
    for(unsigned c=0;c<3;++c) pointers[c]=(uintptr_t)model->colourmap[c];
    assert(convert_map_to_palette(model,flags)==1);
    for(unsigned c=0;c<3;++c) {
     assert(!memcmp(model->colourmap[c],output[c],PAL_BYTES));
     assert(flags[c]?((uintptr_t)model->colourmap[c]!=pointers[c]):
        ((uintptr_t)model->colourmap[c]==pointers[c]));
    }
   }
   destroy(model,3);
  }
  // Empty palettes and nonpositive counts do not read flags or map tables.
  s_model *empty=create(0,0);free(empty->palette);empty->palette=NULL;
  empty->maps_loaded=3;assert(convert_map_to_palette(empty,NULL)==0);
  empty->maps_loaded=0;destroy(empty,0);
  for(int count=-1;count<=0;++count) {
   empty=create(0,0);empty->maps_loaded=count;
   assert(convert_map_to_palette(empty,NULL)==1);destroy(empty,0);
  }
  // Unselected slots do not require a map or even a dynamic vector.
  empty=create(0,0);empty->maps_loaded=3;fixture_flag zero[3]={0};
#if !@FIXED@
  free(empty->colourmap);empty->colourmap=NULL;
#endif
  assert(convert_map_to_palette(empty,zero)==1);destroy(empty,0);
  for(int failure=0;failure<3;++failure) {
   s_model *model=create(3,7);fixture_flag flags[3]={(fixture_flag)-1,2,255};
   unsigned char output[3][MAX_PAL_SIZE],before[3][256];expected(model,flags,output);
   for(unsigned c=0;c<3;++c) memcpy(before[c],model->colourmap[c],256);
   fail_after=failure;fatal_active=1;fatal_count=0;
   if(setjmp(fatal_jump)==0) {convert_map_to_palette(model,flags);assert(!"missing fatal allocation callback");}
   assert(fatal_count==1 && fail_after==-1);fatal_active=0;
   for(unsigned c=0;c<3;++c) assert(!memcmp(model->colourmap[c],
     c<(unsigned)failure?output[c]:before[c],c<(unsigned)failure?(size_t)PAL_BYTES:256u));
   destroy(model,3);
  }
 }
#if @GENERATED@
 screenformat=PIXEL_32;
 assert(convert_map_to_palette(NULL,NULL)==0);
 s_model *model=create(1,0);fixture_flag selected[128]={1};
 assert(convert_map_to_palette(model,NULL)==0);destroy(model,1);
 model=create(1,0);free(model->colourmap[0]);model->colourmap[0]=NULL;
 assert(convert_map_to_palette(model,selected)==0);destroy(model,1);
#if !@FIXED@
 model=create(0,0);model->maps_loaded=1;free(model->colourmap);model->colourmap=NULL;
 assert(convert_map_to_palette(model,selected)==0);destroy(model,0);
#endif
#if @CAPACITY@
 model=create(2,0);model->maps_loaded=3;selected[0]=0;selected[2]=1;
 assert(convert_map_to_palette(model,selected)==0);destroy(model,2);
#endif
#if @FIXED@
 model=create(0,0);model->maps_loaded=31;memset(selected,0,sizeof(selected));selected[30]=1;
 assert(convert_map_to_palette(model,selected)==0);destroy(model,0);
#endif
#if @FORMAT_DEP@
 for(int format=-1;format<=5;format+=6) {
  model=create(0,0);screenformat=format;
  assert(convert_map_to_palette(model,NULL)==0);screenformat=PIXEL_32;destroy(model,0);
 }
#endif
#endif
}
int main(int argc,char **argv) {@MAIN@ return 0;}
'''
    main = '(void)argc;(void)argv;check();'
    if original:
        if source_rows is not None:
            main = '(void)argc;(void)argv;'+''.join(
                'check(); /* source %d */\n' % item['revision'] for item in source_rows)
        main += 'puts('+json.dumps(json.dumps({'status': 'PASS', 'engine': engine,
                                             'fixed_table': bool(fixed),
                                             'sources': len(source_rows) if source_rows is not None else 1}))+');'
    else:
        main = ('assert(argc==2 && atoi(argv[1])>0);'
                'obor_profile_build=(uint32_t)strtoul(argv[1],NULL,10);check();')
    values = {'STORAGE': colourmap_storage_support(body),
              'PROFILE': '' if original else 'static uint32_t obor_profile_build;',
              'PALETTE_MACRO': row['palette_macro'], 'FLAG': row['flag_type'],
              'TABLE': table, 'COUNTER': counter, 'BODY': body, 'FIXED': str(int(fixed)),
              'FORMAT_DEP': str(int(row['format_dependent'])), 'FORMATS': formats,
              'CAPACITY': str(int(engine == '3741')), 'GENERATED': str(int(not original)), 'MAIN': main}
    program = re.sub(r'@('+'|'.join(values)+r')@', lambda match: values[match[1]], program)
    if original:
        return program.replace('/* NATIVE ALLOCATION POLICY */', '')
    return bind_named_allocation_support(program, SOURCE / 'src/engines' / engine,
                                         marker='/* NATIVE ALLOCATION POLICY */')


class PaletteConversionTests(unittest.TestCase):
    def test_registry_covers_native_engines_and_source_profiles(self):
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        self.assertEqual(set(CONTRACTS['engines']), {x['build'] for x in pin['engines']})
        for row in list(CONTRACTS['engines'].values())+CONTRACTS['sources']:
            self.assertRegex(row['function_sha256'], r'^[0-9a-f]{64}$')
            self.assertIn(row['counter'], ('char8', 'int8', 'int'))
        revisions = {x['revision'] for x in CONTRACTS['sources']}
        for profile in contract_profiles(Path(__file__).parent / 'fixtures/palette-conversion-contracts.json', pin['profiles']):
            if profile['engine'] == '3741':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)

    def test_converter_bytes_errors_and_bounds_for_each_registered_profile(self):
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        with tempfile.TemporaryDirectory(prefix='anybor-palette-convert-') as temporary:
            work = Path(temporary)
            for engine in CONTRACTS['engines']:
                with self.subTest(engine=engine):
                    source, exe = work / (engine+'.c'), work / engine
                    source.write_bytes(conversion_program(engine).encode('utf-8', 'surrogateescape'))
                    subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc'))+[
                        '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                        '-Wno-unused-variable', '-Wno-unused-function', '-Wno-sign-compare', '-fsigned-char',
                        '-g', '-fsanitize=address,undefined',
                        *(['-no-pie'] if sys.platform.startswith('linux') else []),
                        str(source), '-o', str(exe)], check=True, timeout=60)
                    cases = {x['build']: int(x.get('revision', x['build'])) for x in contract_profiles(Path(__file__).parent / 'fixtures/palette-conversion-contracts.json', pin['profiles'])
                             if x['engine'] == engine}
                    for row in CONTRACTS['sources']:
                        if row['engine'] == engine and str(row['revision']) not in cases:
                            cases['source-'+str(row['revision'])] = row['revision']
                    for revision in cases.values():
                        subprocess.run([str(exe), str(revision)], check=True,
                                       timeout=20, env=sanitizer_environment())
                    print(json.dumps({'engine': engine, 'executed': cases,
                                      'scope': 'Converter body; native model representation and source controls'}))


if __name__ == '__main__':
    unittest.main()
