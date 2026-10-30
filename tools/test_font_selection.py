"""Check native font selection, valid wrapping and unavailable indices.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import json
import os
from pathlib import Path
import shlex
import re
import subprocess
import sys
import tempfile
import unittest

from historical_font_selection import render_font_selection
from historical_text_display import render_text_display
from test_historical_player import function
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))


class FontSelectionTests(unittest.TestCase):
    def test_native_text_display_glyphs_and_expiry(self):
        fixture=load_contract_fixture(Path(__file__).with_name('fixtures').joinpath('text-display-contracts.json'))
        pin=json.loads((SOURCE/'src/pin.json').read_text())
        self.assertEqual(fixture['schema'],1)
        cc=shlex.split(os.environ.get('HOST_CC',os.environ.get('CC','cc')))
        version=subprocess.check_output(cc+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack','-Wno-error=deprecated-non-prototype',
                  '-Wno-error=single-bit-bitfield-constant-conversion']if'clang'in version.lower()else[]
        host=[]if sys.platform=='darwin'else['-DLINUX=1']
        link=['-Wl,-dead_strip']if sys.platform=='darwin'else['-no-pie','-Wl,--gc-sections']
        for row in fixture['models']:
            with self.subTest(engine=row['engine']),tempfile.TemporaryDirectory(prefix='native-text-display-')as folder:
                required={int(p.get('revision',p['build']))for p in contract_profiles(fixture, pin['profiles'])if p['engine']==row['engine']}
                covered = [revision for model in fixture['models']
                           if model['engine'] == row['engine']
                           for revision in model['revisions']]
                self.assertEqual(len(covered), len(set(covered)))
                self.assertTrue(required <= set(covered))
                self.assertEqual(row['revisions'],[v['revision']for v in row['original_sources']])
                for ref in row['original_sources']:
                    self.assertRegex(ref['commit'],r'^[0-9a-f]{40}$')
                    for key in ['used_contract','draw','font_printf']:self.assertRegex(ref[key],r'^[0-9a-f]{64}$')
                root=SOURCE/'src/engines'/row['engine']
                native=(root/'openbor.c').read_bytes().decode('utf8','surrogateescape')
                options={k:row[k]for k in ['revisions','physical_fixed','slots','font_tokens','cases']}
                plain=re.search(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{[\s\S]*?\};',native)
                self.assertIsNotNone(plain)
                code=render_text_display(draw=function(native,'draw_textobjs'),plainmethod=plain[0],**options)
                work=Path(folder);src=work/'probe.c';src.write_text(code,errors='surrogateescape');binary=work/'probe'
                includes=[root/'source/gamelib',root,SOURCE/'src/port/libretro',root/'source',
                          *sorted(p for p in(root/'source').iterdir()if p.is_dir())]
                compile_checked(cc+['-std=gnu11','-fgnu89-inline','-Wall','-Wextra','-Werror',
                    '-Wno-error=deprecated-declarations','-Wno-error=misleading-indentation',
                    '-Wno-error=sign-compare','-Wno-unused-variable','-Wno-unused-function',
                    '-Wno-unused-parameter','-Wno-unused-but-set-variable','-Wno-implicit-fallthrough',
                    '-O0','-g','-fsigned-char','-fcommon','-ffunction-sections','-fdata-sections',
                    '-DLIBRETRO=1','-DOBOR_ENGINE_BUILD='+row['engine'],*host,*warnings,
                    '-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all',
                    *['-I'+str(p)for p in includes],str(src),*link,'-lm','-o',str(binary)])
                observed=subprocess.run([str(binary)],capture_output=True,text=True,timeout=15,env=sanitizer_environment())
                self.assertEqual(observed.returncode,0,observed.stdout+observed.stderr)
                self.assertEqual(json.loads(observed.stdout),dict(status='PASS',contexts=len(row['revisions']),
                    checks=len(row['revisions'])*len(row['cases'])))

    def test_each_profile_native_width_dimensions_and_release(self):
        fixture = load_contract_fixture(Path(__file__).with_name('fixtures').joinpath('font-selection-contracts.json'))
        pin = json.loads((SOURCE/'src/pin.json').read_text())
        self.assertEqual(set(fixture['engines']), {e['build'] for e in pin['engines']})
        for contract in fixture['original_contracts']:
            self.assertEqual(contract['slots'], fixture['engines'][contract['engine']]['slots'])
            self.assertIn(contract['revision'], fixture['engines'][contract['engine']]['revisions'])
        cc = shlex.split(os.environ.get('HOST_CC', os.environ.get('CC', 'cc')))
        version = subprocess.check_output(cc+['--version'], text=True, timeout=10)
        extra = ['-Wno-error=pragma-pack', '-Wno-error=deprecated-non-prototype'] if 'clang' in version.lower() else []
        host = [] if sys.platform == 'darwin' else ['-DLINUX=1']
        link = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        for engine, options in fixture['engines'].items():
            with self.subTest(engine=engine), tempfile.TemporaryDirectory(prefix='native-font-selection-') as folder:
                required = {int(p.get('revision', p['build'])) for p in contract_profiles(fixture, pin['profiles']) if p['engine']==engine}
                self.assertTrue(required <= set(options['revisions']))
                root = SOURCE/'src/engines'/engine
                work = Path(folder)
                src = work/'probe.c'
                src.write_text(render_font_selection(**options))
                includes = [root/'source/gamelib', root, SOURCE/'src/port/libretro', root/'source',
                            *sorted(p for p in (root/'source').iterdir() if p.is_dir())]
                executable = work/'probe'
                compile_checked(cc+['-std=gnu11', '-fgnu89-inline', '-Wall', '-Wextra', '-Werror',
                    '-Wno-error=deprecated-declarations', '-Wno-error=misleading-indentation',
                    '-Wno-error=sign-compare', '-Wno-unused-variable', '-Wno-unused-function',
                    '-Wno-unused-parameter', '-Wno-unused-but-set-variable', '-Wno-implicit-fallthrough',
                    '-O0', '-g', '-fsigned-char', '-fcommon', '-ffunction-sections', '-fdata-sections',
                    '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD='+engine, *host, *extra,
                    '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
                    *['-I'+str(p) for p in includes], str(src), *link, '-lm', '-o', str(executable)])
                run = subprocess.run([str(executable)], capture_output=True, text=True,
                                     timeout=15, env=sanitizer_environment())
                self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
                actual = json.loads(run.stdout)
                self.assertEqual(actual['status'], 'PASS')
                self.assertEqual(actual['contexts'], len(options['revisions']))
                self.assertGreater(actual['checks'], 2*options['slots']*actual['contexts'])


    def test_early_font_newline_positions(self):
        fixture = load_contract_fixture(Path(__file__).parent /
                                        'fixtures/profile-early-font-newline.json')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertTrue(set(fixture['boundary_controls']) <= revisions)
        for profile in contract_profiles(fixture, json.loads((SOURCE / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == fixture['engine'] and fixture['range'][0] <= revision <= fixture['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_EARLY_TEXT_ENGINE', SOURCE / 'src/engines' / fixture['engine']))
        text = (engine / 'source/gamelib/font.c').read_text()
        declaration = re.search(r'typedef struct\s*\{[^}]*}\s*s_font;', text)
        self.assertIsNotNone(declaration)
        checks = []
        for row in rows:
            self.assertEqual(row['engine'], fixture['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIn(row['modern'], (0, 1))
            checks.append('check(%d,%d);' % (row['revision'], row['modern']))
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "types.h"
#include "screen.h"
#include "sprite.h"
#define MAX_FONTS 8
#define FONT_LAYER 0x0FFFFFFF
@FONT_TYPE@
static s_font fonts[MAX_FONTS];
static s_sprite glyphs[256];
static char b[256];
uint32_t obor_profile_build;
static struct {int x,y,z,glyph,format;} calls[16];
static int count;
static void observe(int x,int y,int z,s_sprite *sprite,int format) {
 assert(count<16 && sprite>=glyphs && sprite<glyphs+256);
 calls[count].x=x;calls[count].y=y;calls[count].z=z;
 calls[count].glyph=(int)(sprite-glyphs);calls[count].format=format;count++;
}
#define spriteq_add_frame(x,y,z,sprite,method,id) observe(x,y,z,sprite,-1)
#define putsprite_8(x,y,flip,sprite,screen,table,method) observe(x,y,0,sprite,PIXEL_8)
#define putsprite_x8p16(x,y,flip,sprite,screen,table,method) observe(x,y,0,sprite,PIXEL_16)
#define putsprite_x8p32(x,y,flip,sprite,screen,table,method) observe(x,y,0,sprite,PIXEL_32)
@FUNCTIONS@
static void check(unsigned revision,int modern) {
 obor_profile_build=revision;
 for(int height=3;height<=17;height+=14) {
  memset(fonts,0,sizeof(fonts));memset(glyphs,0,sizeof(glyphs));
  for(int i=0;i<256;i++){fonts[0].token[i]=&glyphs[i];fonts[0].token_width[i]=2;}
  fonts[0].font_loaded=1;glyphs[0].height=height;glyphs['\n'].height=99;
  fonts[0].token_width['A']=3;fonts[0].token_width['B']=4;fonts[0].token_width['C']=5;
  fonts[0].token_width['\n']=7;
  count=0;font_printf(10,20,0,5,"%s","A\nB\nC");
  assert(count==5);
  const int glyph[]={ 'A','\n','B','\n','C'},x[]={10,13,20,24,31},lines[]={0,0,1,1,2};
  for(int i=0;i<5;i++)assert(calls[i].glyph==glyph[i] && calls[i].x==x[i] &&
    calls[i].y==20+(modern?height*lines[i]:0) && calls[i].z==FONT_LAYER+5 && calls[i].format==-1);
  const int formats[]={PIXEL_8,PIXEL_16,PIXEL_32};
  for(unsigned k=0;k<sizeof(formats)/sizeof(formats[0]);k++){
   s_screen screen={0};screen.pixelformat=formats[k];count=0;
   screen_printf(&screen,10,20,MAX_FONTS,"%s","A\nB\nC");
   assert(count==3);
   for(int i=0;i<3;i++)assert(calls[i].glyph=="ABC"[i] && calls[i].x==10 &&
      calls[i].y==20+i*(modern?height:10) && calls[i].format==formats[k]);
   count=0;screen_printf(&screen,10,20,-1,"%s","A");assert(!count);
  }
  count=0;font_printf(1,2,-1,0,"%s","A");assert(!count);
  fonts[0].font_loaded=0;font_printf(1,2,0,0,"%s","A");assert(!count);
 }
}
int main(void){@CHECKS@ puts("early_font_newline=1");return 0;}
'''
        for key, value in dict(FONT_TYPE=declaration[0], FUNCTIONS='\n'.join(
                function(text, name) for name in ['font_printf', 'screen_printf']),
                CHECKS='\n'.join(checks)).items():
            program = program.replace('@' + key + '@', value)
        with tempfile.TemporaryDirectory(prefix='early-font-newline-') as folder:
            unit, binary = Path(folder) / 'probe.c', Path(folder) / 'probe'
            unit.write_text(program)
            includes = [engine, engine / 'source', engine / 'source/gamelib',
                        SOURCE / 'src/port/libretro', SOURCE / 'src/glue']
            command = shlex.split(os.environ.get('HOST_CC', 'cc')) + [
                '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-Wno-error=deprecated-declarations', '-fsanitize=address,undefined',
                '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                *['-I' + str(p) for p in includes], str(unit),
                *([] if sys.platform == 'darwin' else ['-no-pie']), '-o', str(binary)]
            build = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10,
                                 env=sanitizer_environment())
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('early_font_newline=1', run.stdout)


if __name__ == '__main__':
    unittest.main()
