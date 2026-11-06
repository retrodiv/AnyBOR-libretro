"""Check historical texture tags, cursor dispatch and graphical constructors.

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

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function
from test_early_system_callbacks import block
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked
from test_historical_hud_schedule import native_declarations

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-texture-dispatch-contracts.json'


def sources(data):
    engine = ROOT / 'src/engines' / data['engine']
    return engine, {name: (engine / name).read_text() for name in
        ('openbor.c', 'openborscript.c', 'source/gamelib/types.h',
         'source/gamelib/transform.c', 'source/gamelib/screen.c',
         'source/gamelib/sprite.c', 'source/scriptlib/ScriptVariant.c')}


def fill(template, parts):
    text = Path(__file__).with_name(template).read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native texture dependency')
    return text


def common_parts(data, text):
    header = text['source/gamelib/types.h']
    # The preceding control has no retained tag. Keep it executable so its
    # real magic dispatch, rather than a compile error, can reject the oracle.
    retained = bool(re.search(r'gfx_type\s+type\s*;', header))
    return dict(CONTEXTS=','.join('{%du,%d}' % (row['revision'], row['declared_tag'])
                for row in data['sources']),
        TAG_SET='entry->type=(gfx_type)kind;' if retained else '(void)entry;(void)kind;',
        TAG_GET='return (int)entry->type;' if retained else '(void)entry;return -1;',
        VARIANTS='\n'.join(function(text['source/scriptlib/ScriptVariant.c'], name) for name in
                          ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')))


def pipeline_program(data):
    _, text = sources(data)
    transform = text['source/gamelib/transform.c']
    global_start = transform.index('static transpixelfunc pfp;')
    global_end = transform.index('/**', global_start)
    parts = common_parts(data, text)
    parts['CONTEXTS'] = ','.join('{%du,%d,%d}' %
        (row['revision'], row['declared_tag'], row['water_bulk']) for row in data['sources'])
    water = function(transform, 'gfx_draw_water')
    choices = list(re.finditer(r'if\([^\n]*\bpixelformat==PIXEL_8\b', water))
    if len(choices) != 1:
        raise ValueError('One native indexed water-copy condition required')
    start = choices[0].start()
    first = block(water, start)
    second = block(water, start+len(first))
    parts.update(GLOBALS=transform[global_start:global_end], FUNCTIONS='\n'.join(function(transform, name)
        for name in ('draw_pixel_gfx', 'src_seek', 'src_line_inc', 'src_line_dec',
                     'src_inc', 'src_dec', 'init_gfx_global_draw_stuff', 'write_pixel', 'dest_seek',
                     'dest_inc', 'copy_pixel_block')), WATER=first+second)
    return fill('texture_dispatch_contract.c.in', parts)


def constructor_program(data):
    engine, text = sources(data)
    screen = function(text['source/gamelib/screen.c'], '_putscreen')
    end = screen.index('if(!table && alpha<=0')
    # This window includes all changed screen construction branches. The
    # unchanged final copying/blending paths retain their separate controls.
    screen = screen[:end]+'(void)table;(void)alpha;(void)transbg;\n}\n'
    sprite_header = (engine / 'source/gamelib/sprite.h').read_text()
    traps = []
    for name, kind in (('putsprite_8', 'PIXEL_8'), ('putsprite_x8p16', 'PIXEL_16'),
                       ('putsprite_x8p32', 'PIXEL_32')):
        match = re.search(r'(?m)^void '+name+r'\([^;]*\);', sprite_header)
        if match is None:
            raise ValueError('Exact native sprite backend declaration required')
        traps.append(match[0][:-1]+'{++fast_calls;fast_kind='+kind+';}')
    parts = common_parts(data, text)
    level = function(text['openbor.c'], 'load_level')
    background = block(level, level.index('if(cmd==CMD_LEVEL_BACKGROUND){'))
    draw = function(text['openbor.c'], 'draw_scrolled_bg')
    start = re.search(r'if\((?:obor_gfx_entry_type\(&layer->gfx\)==gfx_screen|'
                      r'layer->gfx.screen->magic==screen_magic)\)', draw)
    if start is None:
        raise ValueError('Native graphical layer dispatch required')
    first = block(draw, start.start())
    second = block(draw, start.start()+len(first))
    parts['CONTEXTS'] = ','.join('{%du,%d,%d}' % (row['revision'],row['declared_tag'],
                            row['sprite_water_slow']) for row in data['sources'])
    parts.update(FUNCTIONS='\n'.join((screen,
        function(text['source/gamelib/sprite.c'], 'putsprite_ex'),
        function(text['openborscript.c'], 'openbor_settexture'),
        function(text['openbor.c'], 'load_layer'))), TRAPS='\n'.join(traps),
                 BACKGROUND=background, QUEUE=first+second)
    return fill('texture_constructor_contract.c.in', parts)


class TransformLoopContracts(unittest.TestCase):
    def test_native_rotation_and_water_pixels_match_each_own_source(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') /
                                     'profile-transform-loop-contracts.json')
        rows = data['sources']
        revisions = {r['revision'] for r in rows}
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        patterns = []
        for bits in (8, 16, 32):
            row = data['patterns'][str(bits)]
            self.assertEqual(len(row['source']), 16)
            self.assertEqual(len(row['before']), 64)
            patterns.append('{'+str(bits)+','+','.join('{'+','.join(str(v)+'u' for v in row[k])+'}'
                                                     for k in ('source', 'before'))+'}')
        values = dict(PATTERNS=','.join(patterns),
                      PROFILES=','.join(str(r['revision'])+'u' for r in rows),
                      CASES=',\n'.join('{'+','.join(str(c[k]) for k in data['case_fields'])+'}'
                                        for c in data['cases']))
        text = Path(__file__).with_name('transform_loop_contract.c.in').read_text()
        for key, value in values.items():
            text = text.replace('@'+key+'@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        engine = ROOT / 'src/engines' / data['engine']
        includes = [engine / 'source/gamelib', engine / 'source', engine,
                    ROOT / 'src/glue', ROOT / 'src/port/libretro']
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
        warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        host = [] if sys.platform == 'darwin' else ['-DLINUX=1']
        flags = ['-I'+str(p) for p in includes] + [
            '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
            '-Wno-error=misleading-indentation', '-Wno-error=sign-compare',
            '-Wno-unused-variable', '-Wno-unused-function', '-Wno-unused-parameter',
            '-Wno-implicit-fallthrough', '-Wno-error=unused-value', *warnings,
            '-O0', '-g', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD='+data['engine'], *host,
            '-fsigned-char', '-ffunction-sections', '-fcommon', '-fdata-sections',
            '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all']
        with tempfile.TemporaryDirectory(prefix='anybor-transform-loop-') as folder:
            work = Path(folder)
            unit, provider, executable = work / 'probe.c', work / 'pixels.o', work / 'probe'
            unit.write_text(text)
            compile_checked(compiler + flags + ['-O1', '-c', str(engine/'source/gamelib/pixelformat.c'),
                                                '-o', str(provider)])
            compile_checked(compiler + flags + [str(unit), str(provider), *links, '-lm', '-o', str(executable)])
            output = subprocess.check_output([str(executable)], text=True, timeout=30,
                                             env=sanitizer_environment())
        actual = [json.loads(line) for line in output.splitlines()]
        self.assertEqual(len(actual), len(rows))
        for row, result in zip(rows, actual):
            with self.subTest(revision=row['revision']):
                self.assertEqual(result, dict(revision=row['revision'], pixels=data['contracts'][row['contract']]))


class BackgroundPaletteContracts(unittest.TestCase):
    def test_native_background_neon_palette_and_service_order(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') /
                                     'profile-background-neon-contracts.json')
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = ROOT / 'src/engines' / data['engine']
        core = (engine / 'openbor.c').read_text()
        declarations = native_declarations(core)
        pixels = (engine / 'source/gamelib/pixelformat.c').read_text()
        matches = re.findall(r'(?m)^int pixelbytes[^\n]*', pixels)
        self.assertEqual(len(matches), 1)
        text = fill('background_neon_contract.c.in', dict(DECLARATIONS=declarations,
            NATIVE=function(core, 'load_background'), PIXEL_BYTES=matches[0],
            CONTEXTS=','.join('{%d,%d}' % (row['revision'],row['copy_neon'])
                              for row in data['sources'])))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        self.assertEqual(actual, [dict(revision=r, cases=12, status='PASS') for r in revisions])


class TextureDispatchContracts(unittest.TestCase):
    def test_native_setup_dispatch_cursor_and_pixel_writes(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({r['revision'] for r in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len({r['revision'] for r in data['sources']}), len(data['sources']))
        actual = [json.loads(line) for line in native_output(pipeline_program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], declared=r['declared_tag'])
                                  for r in data['sources']])

    def test_native_screen_sprite_script_and_layer_construction(self):
        data = load_contract_fixture(FIXTURE)
        actual = [json.loads(line) for line in native_output(constructor_program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], declared=r['declared_tag'])
                                  for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
