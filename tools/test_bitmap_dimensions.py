"""Check each historical profile's native indexed image dimensions and pixels.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

from historical_bitmap_dimensions import render_bitmap_dimensions
from make_fixture import png
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/bitmap-dimension-contracts.json'


def fixture_palette(byte_count):
    rgb = list(bytes([0, 0, 0, 80, 230, 140, 240, 240, 240, 25, 45, 80]) + bytes(252*3))
    if byte_count == 768:
        return rgb
    if byte_count == 1024:
        return [value for i in range(0, 768, 3) for value in (*rgb[i:i+3], 0)]
    raise ValueError('Explicit RGB or RGB0 palette layout required')


def native_context(engine):
    compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
    version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
    png_compile, png_link = [], ['-lpng', '-lz']
    pkg = shutil.which('pkg-config')
    if pkg:
        png_compile = shlex.split(subprocess.check_output([pkg, '--cflags', 'libpng'], text=True, timeout=10))
        png_link = shlex.split(subprocess.check_output([pkg, '--libs', 'libpng'], text=True, timeout=10))
    elif sys.platform == 'darwin':
        prefix = subprocess.check_output(['brew', '--prefix', 'libpng'], text=True, timeout=10).strip()
        png_compile = ['-I' + str(Path(prefix) / 'include')]
        png_link = ['-L' + str(Path(prefix) / 'lib'), '-lpng', '-lz']
    root = SOURCE / 'src/engines' / engine
    includes = [root/'source/gamelib', root/'source', root, root/'source/pnglib',
                SOURCE/'src/glue', SOURCE/'src/port/libretro']
    flags = ['-I'+str(path) for path in includes if path.is_dir()] + png_compile + [
        '-std=gnu11', '-fgnu89-inline', '-Wall', '-Wextra', '-Werror',
        '-Wno-error=deprecated-declarations', '-Wno-error=misleading-indentation',
        '-Wno-error=sign-compare', '-Wno-unused-variable', '-Wno-unused-function',
        '-Wno-unused-parameter', '-Wno-implicit-fallthrough', '-O0', '-g',
        '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD='+engine, '-fsigned-char', '-fcommon',
        '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined,pointer-overflow',
        '-fno-sanitize-recover=all']
    if 'clang' in version.lower():
        flags += ['-Wno-error=pragma-pack']
    if sys.platform != 'darwin':
        flags += ['-DLINUX=1']
    links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
    # Later native decoders call zlib directly, independently of libpng's
    # transitive shared-library dependencies reported by pkg-config.
    links += ['-fsanitize=address,undefined,pointer-overflow', *png_link, '-lz', '-lm']
    return compiler, flags, links


def compile_image_units(engine, compiler, flags, work, *, include_loader):
    objects = []
    names = ['bitmap', 'pixelformat'] + (['loadimg'] if include_loader else [])
    for name in names:
        target = work / (engine+'-'+name+'.o')
        optimize = ['-O1'] if name == 'pixelformat' else []
        compile_checked(compiler + flags + optimize + ['-c',
            str(SOURCE/'src/engines'/engine/'source/gamelib'/(name+'.c')), '-o', str(target)])
        objects.append(str(target))
    return objects


def profile_program(code):
    marker = 'int main(void){'
    if code.count(marker) != 1:
        raise ValueError('One bounded image observation entry point required')
    return code.replace(marker, '''int main(int argc,char **argv){
 assert(argc==2);char *end=NULL;unsigned long revision=strtoul(argv[1],&end,10);
 assert(end && !*end && revision>0 && revision<=UINT32_MAX);obor_profile_build=(uint32_t)revision;
''')


class BitmapDimensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_contract_fixture(FIXTURE)
        cls.pin = json.loads((SOURCE/'src/pin.json').read_text())
        cls.contexts = {(row['engine'], row['revision']): row for row in cls.fixture['contexts']}
        temporary = tempfile.TemporaryDirectory(prefix='anybor-image-dimensions-')
        cls.addClassCleanup(temporary.cleanup)
        work = Path(temporary.name)
        images = []
        for width, height in cls.fixture['sizes']:
            path = work / ('image-%dx%d.png' % (width, height))
            path.write_bytes(png(width, height, lambda x, y: (x+2*y)%3+1))
            images.append(dict(path=str(path), width=width, height=height))
        cls.executables = {}
        for engine, context in cls.fixture['engines'].items():
            compiler, flags, links = native_context(engine)
            objects = compile_image_units(engine, compiler, flags, work, include_loader=True)
            caps = {row['axis_limit'] for row in cls.fixture['contexts'] if row['engine'] == engine}
            for cap in sorted(caps):
                cases = [row | dict(expected_width=min(row['width'], cap) if cap else row['width'],
                                    expected_height=min(row['height'], cap) if cap else row['height'])
                         for row in images]
                options = {key: context[key] for key in ('resource_hooks', 'magic_field', 'screen_format_variable')}
                code = render_bitmap_dimensions(revision=int(engine), cases=cases,
                    palette=fixture_palette(context['palette_bytes']), **options)
                source = work / (engine+'-'+str(cap)+'.c')
                source.write_text(profile_program(code))
                executable = source.with_suffix('')
                compile_checked(compiler+flags+[str(source), *objects, *links, '-o', str(executable)])
                cls.executables[engine, cap] = executable

    def check_context(self, engine, revision):
        row = self.contexts[engine, revision]
        output = subprocess.check_output([str(self.executables[engine, row['axis_limit']]), str(revision)],
                                        text=True, timeout=15, env=sanitizer_environment())
        self.assertEqual(json.loads(output), dict(status='PASS', cases=2*len(self.fixture['sizes'])))

    def test_registered_profiles_have_own_source_contexts(self):
        self.assertEqual(len(self.contexts), len(self.fixture['contexts']))
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if profile['engine'] in self.fixture['engines']:
                self.assertIn((profile['engine'], int(profile.get('revision', profile['build']))), self.contexts)
        for row in self.fixture['contexts']:
            self.assertRegex(row['source_commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_function_sha256'], r'^[0-9a-f]{64}$')

    def test_each_registered_historical_profile(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if profile['engine'] in self.fixture['engines']:
                with self.subTest(profile=profile['build']):
                    self.check_context(profile['engine'], int(profile.get('revision', profile['build'])))

    def test_each_own_source_context(self):
        for row in self.fixture['contexts']:
            with self.subTest(engine=row['engine'], revision=row['revision']):
                self.check_context(row['engine'], row['revision'])


if __name__ == '__main__':
    unittest.main()
