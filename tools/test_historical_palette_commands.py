"""Check native model remap/alternatepal command bodies for each profile.

The selected bodies and loaders execute with reduced models and deterministic
bitmap/palette I/O. Fixed flags use an equivalent zeroed heap array in the
source fixture. Subclass ownership, conversion and full parsing are separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from test_historical_behavior import native
from test_historical_palette_loading import CONTRACTS, SOURCE, bitmap_fixture, colourmap_storage_support
from test_historical_player import function, rename_identifiers, switch_cases


def model_palette_cases(source):
    method = function(source, 'load_cached_model')
    method = method.replace('switch(cmd)', 'switch(fixture_model_command)', 1)
    _, cases = switch_cases(method, 'load_cached_model', 'fixture_model_command')
    return '\n'.join('case '+name+':'+cases[name]['body'] for name in
                     ('CMD_MODEL_REMAP', 'CMD_MODEL_ALTERNATEPAL'))


def command_checks(row, model, invoke, *, generated, managed=False):
    revision = row['revision']
    fixed = bool(row['fixed_slots'])
    init_flags = 'flags=calloc(30,1);assert(flags);capacity=30;' if fixed and not generated else ''
    extent = 'model->colourmap_capacity' if generated else '30' if fixed else 'extent'
    free_vector = 'free(model->colourmap);' if generated or not fixed else ''
    cleanup = 'for(unsigned i=0;i<'+extent+';++i) free(model->colourmap[i]);'+free_vector
    if managed:
        cleanup = 'if(!obor_colourmap_owner_release(model)) {'+cleanup+'}'
    hole_free = ('assert(obor_colourmap_replace(model.colourmap,1,NULL));' if managed else
                 'free(model.colourmap[1]);model.colourmap[1]=NULL;')
    text = r'''
static void finish_@REV@(@MODEL@ *model,unsigned char **flags,unsigned extent) {
 (void)extent;
 @CLEANUP@
 free(model->palette);free(*flags);*flags=NULL;*model=(@MODEL@){0};
 assert(live_bitmaps==0 && fail_map_malloc==0 && fail_realloc==0);
}
static void check_@REV@(void) {
 obor_profile_build=@REV@;@MODEL@ model={0};unsigned char *flags=NULL;unsigned capacity=0;
 for(screenformat=PIXEL_16;screenformat<=PIXEL_32;screenformat+=2) {
  pixelformat=PIXEL_x8;
  for(int route=CMD_MODEL_REMAP;route<=CMD_MODEL_ALTERNATEPAL;++route) {
   @INIT_FLAGS@
   arguments[1]="first";arguments[2]="second";
   for(int i=0;i<31;++i) {
    assert(@CALL@(&model,route,&flags,&capacity));
    unsigned count=@FIXED@ && i==30?30:(unsigned)i+1;
    assert(model.maps_loaded==(int)count);
    assert(flags && flags[count-1]==(route==CMD_MODEL_REMAP));
    if(!(@FIXED@ && i==30)) {
     assert(model.colourmap[i]);
     assert(model.colourmap[i][0]==(route==CMD_MODEL_REMAP?7:17));
     if(route==CMD_MODEL_ALTERNATEPAL)
      for(unsigned j=0;j<(unsigned)PAL_BYTES;++j) assert(model.colourmap[i][j]==17);
    }
    assert((model.palette!=NULL)==(route==CMD_MODEL_REMAP));
   }
   finish_@REV@(&model,&flags,(unsigned char)model.maps_loaded);capacity=0;
  }
 }
 screenformat=PIXEL_32;
 // Alternate palettes are ignored outside palette-indexed rendering.
 pixelformat=PIXEL_8;@INIT_FLAGS@
 assert(@CALL@(&model,CMD_MODEL_ALTERNATEPAL,&flags,&capacity));
 assert(model.maps_loaded==0 && !model.palette);
 finish_@REV@(&model,&flags,0);capacity=0;
 // Negative remap errors retain the native command's !errorVal behavior.
 // Seed a map so the fixed original's flag index is defined.
 for(int failure=0;failure<3;++failure) {
  @INIT_FLAGS@
  arguments[1]="first";arguments[2]="second";
  assert(@CALL@(&model,CMD_MODEL_REMAP,&flags,&capacity));
  if(failure==0) arguments[2]="FIRST";
  if(failure==1) arguments[1]="missing";
  if(failure==2) arguments[2]="missing";
  assert(@CALL@(&model,CMD_MODEL_REMAP,&flags,&capacity)==(failure!=0));
  unsigned count=1+(!@FIXED@ && failure!=0);
  assert(model.maps_loaded==(int)count && flags[count-1]==1);
  if(count==2) assert(model.colourmap[1]==NULL);
  finish_@REV@(&model,&flags,count);capacity=0;
 }
 // Palette-image refusal leaves an allocated slot before incrementing count.
 pixelformat=PIXEL_x8;@INIT_FLAGS@;arguments[1]="missing";arguments[2]="second";
 assert(!@CALL@(&model,CMD_MODEL_ALTERNATEPAL,&flags,&capacity));
 assert(model.maps_loaded==0 && model.colourmap[0]);
 finish_@REV@(&model,&flags,1);capacity=0;
 // A fixed-table hole can lower the count. The following append must retain
 // later flags and have room for its actual slot, not merely old_count+1.
 @INIT_FLAGS@;arguments[1]="first";arguments[2]="second";
 for(int i=0;i<3;++i) assert(@CALL@(&model,CMD_MODEL_REMAP,&flags,&capacity));
 @HOLE_FREE@
 assert(@CALL@(&model,CMD_MODEL_REMAP,&flags,&capacity));
 assert(model.maps_loaded==(@FIXED@?2:4));
 assert(@CALL@(&model,CMD_MODEL_REMAP,&flags,&capacity));
 assert(model.maps_loaded==(@FIXED@?4:5));
 assert(flags[2]==1 && flags[@FIXED@?3:4]==1);
 finish_@REV@(&model,&flags,@FIXED@?4:5);capacity=0;
 @CORE_ONLY@
}
'''
    core_only = r'''
 pixelformat=PIXEL_x8;arguments[1]="first";arguments[2]="second";
 fail_realloc=1;
 assert(!@CALL@(&model,CMD_MODEL_ALTERNATEPAL,&flags,&capacity));
 assert(!model.maps_loaded && !model.colourmap);
 finish_@REV@(&model,&flags,0);capacity=0;
 fail_map_malloc=1;
 assert(!@CALL@(&model,CMD_MODEL_ALTERNATEPAL,&flags,&capacity));
 assert(!model.maps_loaded && !model.colourmap[0]);
 finish_@REV@(&model,&flags,0);capacity=0;
 // Original fixed same-image calls at count zero wrote before the flag array.
 arguments[2]="FIRST";
 assert(!@CALL@(&model,CMD_MODEL_REMAP,&flags,&capacity));
 assert(model.maps_loaded==0);
 finish_@REV@(&model,&flags,0);
''' if generated else ''
    values = {'REV': str(revision), 'MODEL': model, 'CALL': invoke,
              'FIXED': str(int(fixed)), 'CLEANUP': cleanup, 'HOLE_FREE': hole_free,
              'INIT_FLAGS': init_flags, 'CORE_ONLY': core_only}
    # Expand the inserted core-only fragment through the same placeholders.
    text = text.replace('@CORE_ONLY@', core_only)
    return re.sub(r'@('+'|'.join(values)+r')@', lambda m: values[m[1]], text)


def commands_program(components=None, contracts=None, *, allocation_macro=''):
    rows = CONTRACTS['sources'] if contracts is None else contracts
    generated = components is None
    source = bitmap_fixture().replace('#define PIXEL_8 1', '#define PIXEL_8 0')
    source += r'''
#define PIXEL_x8 1
#define PIXEL_16 2
#define PIXEL_32 4
static int screenformat=PIXEL_32,pixelformat=PIXEL_x8;
static const int pixelbytes[5]={1,1,2,0,4};
#define PAL_BYTES (screenformat==PIXEL_8?768:pixelbytes[screenformat]*256)
static char *arguments[]={NULL,"first","second"};
#define GET_ARG(n) arguments[n]
enum {CMD_MODEL_REMAP=1,CMD_MODEL_ALTERNATEPAL=2};
static const char *shutdownmessage;
static int fail_realloc;
static void *fixture_realloc(void *p,size_t bytes) {
 if(fail_realloc) {fail_realloc=0;return NULL;}return realloc(p,bytes);
}
#define realloc fixture_realloc
static int loadimagepalette(char *name,const char *pak,unsigned char *palette) {
 (void)pak;if(!strcmp(name,"missing")) return 0;
 assert(palette);memset(palette,17,PAL_BYTES);return 1;
}
static int quiet_printf(const char *format,...) {(void)format;return 0;}
#define printf quiet_printf
'''
    if generated:
        engine = SOURCE / 'src/engines/3741'
        game = (engine / 'openbor.c').read_text()
        header = (engine / 'openbor.h').read_text()
        macro = re.search(r'(?m)^#define[\t ]+__realloc\([^\n]*\n(?:[^\n]*\\\n)*[^\n]*', header)
        if macro is None:
            raise ValueError('Native allocation macro required')
        source += macro[0]+'\n'
        source += colourmap_storage_support(game)
        components = {row['revision']: {'loader': function(game, 'load_colourmap'),
                      'cases': model_palette_cases(game)} for row in rows}
        helpers = ['obor_colourmap_reserve']
        if re.search(r'\bobor_mapflag_reserve\(', game):
            helpers.append('obor_mapflag_reserve')
        source += ('typedef struct {unsigned char **colourmap;unsigned colourmap_capacity;'
                   'int maps_loaded:8;unsigned char *palette;const char *name;} s_model;\n')
        source += '\n'.join(function(game, name) for name in helpers)
        source += function(game, 'load_colourmap')
    else:
        source += allocation_macro+'\n'
    for row in rows:
        revision = row['revision']
        model = 's_model' if generated else 'model_'+str(revision)
        invoke = 'command_'+str(revision)
        if not generated:
            table = 'unsigned char *colourmap[30];' if row['fixed_slots'] else 'unsigned char **colourmap;'
            source += 'typedef struct {'+table+'int maps_loaded:8;unsigned char *palette;} '+model+';\n'
            loader = 'loader_'+str(revision)
            source += rename_identifiers(components[revision]['loader'], {'s_model': model, 'load_colourmap': loader})
        else:
            loader = 'load_colourmap'
        cases = rename_identifiers(components[revision]['cases'], {'load_colourmap': loader})
        source += (f'static int {invoke}({model} *newchar,int cmd,unsigned char **flags,unsigned *capacity) {{\n'
                   'unsigned char *mapflag=*flags;unsigned mapflag_capacity=*capacity;\n'
                   'char *value=NULL,*value2=NULL,*command="fixture";int errorVal=0;shutdownmessage=NULL;\n'
                   'switch(cmd) {'+cases+'default:abort();}\n'
                   'lCleanup:*flags=mapflag;*capacity=mapflag_capacity;return shutdownmessage==NULL;\n}\n')
        source += command_checks(row, model, invoke, generated=generated,
                                 managed=generated and 'obor_colourmap_owner_find' in game)
    source += 'int main(int argc,char **argv) {\n'
    if generated:
        source += 'assert(argc==2);switch(atoi(argv[1])) {\n'
        source += ''.join('case %d:check_%d();break;\n' % (x['revision'], x['revision']) for x in rows)
        source += 'default:abort();}\n'
    else:
        source += '(void)argc;(void)argv;\n'+''.join('check_%d();\n' % x['revision'] for x in rows)
        source += 'puts('+json.dumps(json.dumps({'status': 'PASS', 'sources': len(rows), 'command_families': 2}))+');\n'
    return source+'return 0;}\n'


class HistoricalPaletteCommandTests(unittest.TestCase):
    def test_remap_refusal_and_warning_match_each_source_profile(self):
        fixture=load_contract_fixture(Path(__file__).parent /
            'fixtures/profile-remap-error-contracts.json')
        rows=fixture['sources'];revisions={row['revision'] for row in rows}
        self.assertEqual(len(rows),len(revisions))
        self.assertTrue(set(fixture['boundary_controls'])<=revisions)
        for row in rows:
            self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
            self.assertIs(type(row['fatal_remap_error']),bool)
            for digest in row['source_sha256'].values():self.assertRegex(digest,r'^[0-9a-f]{64}$')
        root=SOURCE/'src/engines/3842';game=(root/'openbor.c').read_text()
        header=(root/'openbor.h').read_text()
        macro=re.search(r'(?m)^#define[\t ]+__realloc\([^\n]*\n(?:[^\n]*\\\n)*[^\n]*',header)
        self.assertIsNotNone(macro)
        method=function(game,'load_cached_model').replace('switch(cmd)','switch(fixture_model_command)',1)
        _,cases=switch_cases(method,'load_cached_model','fixture_model_command')
        loader=rename_identifiers(function(game,'load_colourmap'),{'load_colourmap':'native_load_colourmap'})
        code=bitmap_fixture().replace('#define PIXEL_8 1','#define PIXEL_8 0')+r'''
#include <stdarg.h>
#define PIXEL_x8 1
#define PIXEL_16 2
#define PIXEL_32 4
static int screenformat,pixelformat;
#define PAL_BYTES (screenformat*256)
typedef struct {unsigned char **colourmap;int maps_loaded;unsigned char *palette;} s_model;
@MACRO@
@LOADER@
static int forced_capacity_error,forced_palette_error,palette_calls;
static char *arguments[3];
#define GET_ARG(n) arguments[n]
enum {CMD_MODEL_REMAP=1};
static int load_colourmap(s_model *model,char *first,char *second) {
 if(forced_capacity_error)return -1;
 return native_load_colourmap(model,first,second);
}
static int loadimagepalette(char *name,const char *pak,unsigned char *palette) {
 (void)name;(void)pak;assert(palette);++palette_calls;
 if(forced_palette_error)return 0;
 memset(palette,17,PAL_BYTES);return 1;
}
static char diagnostic[512];static const char *shutdownmessage;
static int report(const char *format,...) {
 va_list args;va_start(args,format);int count=vsnprintf(diagnostic,sizeof(diagnostic),format,args);
 va_end(args);assert(count>=0 && count<(int)sizeof(diagnostic));return count;
}
#define printf report
static int command(s_model *newchar,unsigned char **flags) {
 unsigned char *mapflag=*flags;char *value=NULL,*value2=NULL;int errorVal=0;
 shutdownmessage=NULL;diagnostic[0]=0;palette_calls=0;
 switch(CMD_MODEL_REMAP){case CMD_MODEL_REMAP:@CASE@ default:abort();}
lCleanup:
 *flags=mapflag;return shutdownmessage==NULL;
}
#undef printf
static unsigned test_case;
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Remap command revision=%u case=%u line=%d\n",obor_profile_build,test_case,__LINE__);abort();}}while(0)
static const char *errors[]={@ERRORS@};
static void check(int fatal_errors,int seeded,int has_palette,int format,int colour_mode,
                  int result,int palette_error) {
 ++test_case;screenformat=format;pixelformat=colour_mode;s_model model={0};
 if(seeded)assert(native_load_colourmap(&model,"first","second")==1);
 unsigned char *flags=calloc((size_t)seeded+1,1);assert(flags);if(seeded)flags[0]=84;
 unsigned char *original_palette=NULL;
 if(has_palette){model.palette=malloc(PAL_BYTES);assert(model.palette);memset(model.palette,33,PAL_BYTES);original_palette=model.palette;}
 arguments[1]=result==-3?"missing":"first";
 arguments[2]=result==-4?"missing":result==0?"FIRST":"second";
 forced_capacity_error=result==-1;fail_map_malloc=result==-2;forced_palette_error=palette_error;
 int palette_failure=result==1 && colour_mode==PIXEL_x8 && !has_palette && palette_error;
 int accepted=command(&model,&flags);
 assert(accepted==!(palette_failure || (fatal_errors && result<=0)));
 assert(model.maps_loaded==seeded+(result==1 || result<=-2));
 assert(palette_calls==(result==1 && colour_mode==PIXEL_x8 && !has_palette));
 if(result<=0) {
  if(fatal_errors)assert(shutdownmessage && !strcmp(shutdownmessage,errors[-result]) && !diagnostic[0]);
  else {char expected[512];snprintf(expected,sizeof(expected),"Warning: %s\n",errors[-result]);assert(!shutdownmessage && !strcmp(diagnostic,expected));}
 } else if(palette_failure)assert(shutdownmessage && !strcmp(shutdownmessage,"Failed to load palette!") && !diagnostic[0]);
 else assert(!shutdownmessage && !diagnostic[0]);
 assert(flags[seeded]==(result==1 && !palette_failure));
 if(seeded)assert(flags[0]==84);
 assert(!!model.palette==(has_palette || (result==1 && colour_mode==PIXEL_x8)));
 if(has_palette)assert(model.palette==original_palette && model.palette[0]==33);
 else if(model.palette && !palette_failure)assert(model.palette[0]==17);
 if(result==1)assert(model.colourmap[seeded] && model.colourmap[seeded][0]==7);
 for(int i=0;i<model.maps_loaded;++i)free(model.colourmap[i]);
 free(model.colourmap);free(model.palette);free(flags);
 assert(live_bitmaps==0 && fail_map_malloc==0);
}
int main(void) {
 const struct {unsigned revision;int fatal_errors;} profiles[]={@PROFILES@};
 for(unsigned p=0;p<sizeof(profiles)/sizeof(*profiles);++p){
  obor_profile_build=profiles[p].revision;test_case=0;
  for(int seed=0;seed<2;++seed)for(int palette=0;palette<2;++palette)
  for(int format=PIXEL_16;format<=PIXEL_32;format+=2)for(int mode=PIXEL_8;mode<=PIXEL_x8;++mode)
  for(int result=-4;result<=1;++result)for(int failure=0;failure<2;++failure)
   check(profiles[p].fatal_errors,seed,palette,format,mode,result,failure);
 }
 return 0;
}
'''
        code=code.replace('@MACRO@',macro[0]).replace('@LOADER@',loader).replace(
            '@CASE@',cases['CMD_MODEL_REMAP']['body']).replace('@ERRORS@',
            ','.join(map(json.dumps,fixture['error_messages']))).replace('@PROFILES@',
            ','.join('{%d,%d}'%(row['revision'],row['fatal_remap_error']) for row in rows))
        native(code,extra_flags=['-Wno-unused-variable','-Wno-unused-function'])

    def test_original_command_results_flags_and_limits_per_profile(self):
        with tempfile.TemporaryDirectory(prefix='anybor-palette-commands-') as temporary:
            work = Path(temporary)
            source, exe = work / 'probe.c', work / 'probe'
            source.write_text(commands_program())
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-unused-variable', '-Wno-unused-function', '-Wno-sign-compare',
                '-g', '-fsanitize=address,undefined', str(source), '-o', str(exe)], check=True, timeout=60)
            for row in CONTRACTS['sources']:
                with self.subTest(profile=row['revision']):
                    subprocess.run([str(exe), str(row['revision'])], check=True,
                                   timeout=20, env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
