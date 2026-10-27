"""Check the actual final palette-conversion block of model loading.

Reduced independently populated models represent inherited data; this checks
flags/defaults and the converter result at the call site, not subclass copying,
complete parsing, ownership or rendering.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from test_historical_palette_commands import commands_program
from test_historical_palette_loading import CONTRACTS, SOURCE
from test_historical_player import function


def palette_finish(source):
    method = function(source, 'load_cached_model')
    anchors = list(re.finditer(r'(?m)^[\t ]*// we need to convert 8bit colourmap[^\n]*\n', method))
    if len(anchors) != 1:
        raise ValueError('One final native palette-conversion marker required')
    first = anchors[0].end()
    head = re.match(r'\s*if\s*\(\s*pixelformat\s*==\s*PIXEL_x8\s*\)\s*\{', method[first:])
    if head is None:
        raise ValueError('The final palette block must retain its native format predicate')
    opening = first+head.end()-1
    # The maintained function scanner retains nested braces, comments and
    # literals. Its artificial declaration isolates this exact statement block.
    prefix = 'void palette_scope(void) '
    block = function(prefix+method[opening:], 'palette_scope')[len(prefix):]
    return method[first:opening]+block


def finish_program(components=None, row=None, *, original=False, source_rows=None):
    if components is None:
        game = (SOURCE / 'src/engines/3741/openbor.c').read_text()
        components = {'converter': function(game, 'convert_map_to_palette'),
                      'finish': palette_finish(game)}
    prefix = commands_program({}, contracts=[]) if original else commands_program(contracts=[])
    if prefix.count('int main(') != 1:
        raise ValueError('One authored command-fixture entry point required')
    prefix = prefix.split('int main(', 1)[0]
    fixed = bool(row['fixed_slots']) if original else False
    if original:
        table = 'unsigned char *colourmap[30];' if fixed else 'unsigned char **colourmap;'
        prefix += ('typedef struct {'+table+'unsigned colourmap_capacity;int maps_loaded:8;'
                   'unsigned char *palette;const char *name;} s_model;\n')
    program = r'''
static void fixture_shutdown(int code,const char *format,...) {
 (void)code;(void)format;assert(!"unexpected fatal conversion");abort();
}
#define shutdown fixture_shutdown
@CONVERTER@
static int finalize(s_model *newchar,unsigned char **flags,unsigned *capacity) {
 unsigned char *mapflag=*flags;unsigned mapflag_capacity=*capacity;
 shutdownmessage=NULL;if(0) goto lCleanup;
 @FINISH@
lCleanup:
 *flags=mapflag;*capacity=mapflag_capacity;return shutdownmessage==NULL;
}
static s_model model;
static void initialize(unsigned char **flags,unsigned *capacity) {
 model=(s_model){0};model.name="fixture";model.maps_loaded=3;model.colourmap_capacity=3;
#if !@FIXED@
 model.colourmap=calloc(3,sizeof(*model.colourmap));assert(model.colourmap);
#endif
 model.palette=malloc(PAL_BYTES);assert(model.palette);memset(model.palette,17,PAL_BYTES);
 for(unsigned c=0;c<3;++c) {
  model.colourmap[c]=malloc(256);assert(model.colourmap[c]);
  for(unsigned i=0;i<256;++i) model.colourmap[c][i]=(unsigned char)(i+c+1);
 }
 *flags=NULL;*capacity=0;
#if @ORIGINAL_FIXED@
 *flags=calloc(30,1);assert(*flags);*capacity=30;
#endif
}
static void finish(unsigned char **flags) {
 for(unsigned c=0;c<3;++c) free(model.colourmap[c]);
#if !@FIXED@
 free(model.colourmap);
#endif
 free(model.palette);free(*flags);*flags=NULL;assert(!fail_realloc);
}
static void check(unsigned revision) {
 obor_profile_build=revision;unsigned char *flags=NULL;unsigned capacity=0;
 for(int format=0;format<2;++format) {
  screenformat=format?PIXEL_32:PIXEL_16;pixelformat=PIXEL_x8;
#if @GENERATED@ || @FIXED@
  initialize(&flags,&capacity);
  uintptr_t before[3];for(unsigned c=0;c<3;++c) before[c]=(uintptr_t)model.colourmap[c];
  assert(finalize(&model,&flags,&capacity));
  assert(flags && capacity>=3);
  for(unsigned c=0;c<3;++c) {
   assert(!flags[c] && before[c]==(uintptr_t)model.colourmap[c]);
   for(unsigned i=0;i<256;++i) assert(model.colourmap[c][i]==(unsigned char)(i+c+1));
  }
  finish(&flags);
#endif
  initialize(&flags,&capacity);
  if(!flags) {flags=calloc(3,1);assert(flags);capacity=3;}
  flags[0]=2;flags[2]=255;
  assert(finalize(&model,&flags,&capacity));
  assert(flags[0]==2 && flags[1]==0 && flags[2]==255);
  for(unsigned c=0;c<3;++c) {
   if(c==1) {for(unsigned i=0;i<256;++i) assert(model.colourmap[c][i]==(unsigned char)(i+c+1));}
   else for(unsigned i=0;i<(unsigned)PAL_BYTES;++i) assert(model.colourmap[c][i]==17);
  }
  finish(&flags);
  // A missing base palette returned zero, which the original caller ignored.
  initialize(&flags,&capacity);free(model.palette);model.palette=NULL;
  assert(finalize(&model,&flags,&capacity));finish(&flags);
  // Outside indexed-palette rendering the complete conversion block is skipped.
  initialize(&flags,&capacity);pixelformat=PIXEL_8;
  unsigned char *old_flags=flags;
  assert(finalize(&model,&flags,&capacity));assert(old_flags==flags);finish(&flags);
 }
#if @GENERATED@
 screenformat=PIXEL_32;pixelformat=PIXEL_x8;
 initialize(&flags,&capacity);if(!flags) {flags=calloc(3,1);assert(flags);capacity=3;}
 flags[0]=1;flags[2]=1;free(model.colourmap[2]);model.colourmap[2]=NULL;
 assert(!finalize(&model,&flags,&capacity));assert(strstr(shutdownmessage,"convert"));
 for(unsigned i=0;i<(unsigned)PAL_BYTES;++i) assert(model.colourmap[0][i]==17);
 finish(&flags);
 initialize(&flags,&capacity);fail_realloc=1;
 assert(!finalize(&model,&flags,&capacity));assert(!flags && capacity==0);
 finish(&flags);
 for(int format=-1;format<=5;format+=6) {
  screenformat=PIXEL_32;initialize(&flags,&capacity);screenformat=format;
  assert(!finalize(&model,&flags,&capacity));screenformat=PIXEL_32;finish(&flags);
 }
#endif
}
int main(int argc,char **argv) {@MAIN@ return 0;}
'''
    main = 'assert(argc==2);check((unsigned)strtoul(argv[1],NULL,10));'
    if original:
        main = '(void)argc;(void)argv;'+''.join('check(%d);\n' % x['revision'] for x in source_rows)
        main += 'puts('+json.dumps(json.dumps({'status': 'PASS', 'sources': len(source_rows),
                                              'fixed_flags': fixed}))+');'
    values = {'CONVERTER': components['converter'], 'FINISH': components['finish'],
              'FIXED': str(int(fixed)), 'ORIGINAL_FIXED': str(int(original and fixed)),
              'GENERATED': str(int(not original)), 'MAIN': main}
    return prefix+re.sub(r'@('+'|'.join(values)+r')@', lambda match: values[match[1]], program)


class HistoricalPaletteFinishTests(unittest.TestCase):
    def test_finish_selector_preserves_nested_native_scope_and_refuses_ambiguity(self):
        block = ' if(pixelformat==PIXEL_x8) {if(flag) {text="}";} convert();}'
        marker = '// we need to convert 8bit colourmap into a palette\n'
        source = 'int load_cached_model(void) {\n'+marker+block+'\n}'
        self.assertEqual(palette_finish(source).strip(), block.strip())
        for altered in [source.replace(marker, ''), source.replace(block, block+'\n'+marker+block),
                        source.replace('pixelformat==PIXEL_x8', 'pixelformat==PIXEL_8')]:
            with self.subTest(source=altered), self.assertRaises(ValueError):
                palette_finish(altered)

    def test_loader_conversion_result_and_default_flags_per_profile(self):
        with tempfile.TemporaryDirectory(prefix='anybor-palette-finish-') as temporary:
            work = Path(temporary)
            source, exe = work / 'probe.c', work / 'probe'
            source.write_text(finish_program())
            subprocess.run(shlex.split(os.environ.get('HOST_CC', 'cc'))+[
                '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-unused-variable', '-Wno-unused-function', '-Wno-sign-compare',
                '-g', '-fsanitize=address,undefined', str(source), '-o', str(exe)], check=True, timeout=60)
            for row in CONTRACTS['sources']:
                with self.subTest(profile=row['revision']):
                    subprocess.run([str(exe), str(row['revision'])], check=True,
                                   timeout=20, env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
