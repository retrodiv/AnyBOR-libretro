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
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

from historical_bitmap_dimensions import render_bitmap_dimensions
from make_fixture import chunk, png
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


DIRECT_PNG_PROBE = r'''
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "types.h"
#include "screen.h"
#include "packfile.h"
#undef printf
#undef assert
#include <assert.h>

uint32_t obor_profile_build;
static FILE *member;
static unsigned opens, closes;
int loadscreen32(char *filename, char *packfile, s_screen **screen);

void *checkAlloc(void *ptr, size_t size, const char *func, const char *file, int line)
{
    (void)size; (void)func; (void)file; (void)line;
    return ptr;
}
void exitIfFalse(int value, const char *condition, const char *func, const char *file, int line)
{
    if(value) return;
    fprintf(stderr, "%s:%d %s: %s\n", file, line, func, condition);
    abort();
}

int openpackfile(const char *filename, const char *packfile)
{
    assert(!member && !strcmp(packfile, "direct-image-control"));
    ++opens;
    member = fopen(filename, "rb");
    return member ? 0 : -1;
}
int seekpackfile(int handle, int offset, int whence)
{
    assert(handle == 0 && member);
    return fseek(member, offset, whence) ? -1 : (int)ftell(member);
}
int readpackfile(int handle, void *buffer, int length)
{
    assert(handle == 0 && member && length >= 0);
    return (int)fread(buffer, 1, length, member);
}
int closepackfile(int handle)
{
    assert(handle == 0 && member);
    ++closes;
    int result = fclose(member);
    member = NULL;
    return result;
}
int main(int argc, char **argv)
{
    assert(argc == 4);
    obor_profile_build = (uint32_t)strtoul(argv[1], NULL, 10);
    const unsigned pixel_bytes = (unsigned)strtoul(argv[3], NULL, 10);
    s_screen *screen = allocscreen(4, 1, PIXEL_32);
    assert(screen && loadscreen32(argv[2], "direct-image-control", &screen));
    assert(screen->pixelformat == PIXEL_32 && pixel_bytes <= (unsigned)screen->width * 4);
    const unsigned char *data = (const unsigned char *)screen + offsetof(s_screen, data);
    printf("%d %d %u %u", screen->width, screen->height, opens, closes);
    for(int row = 0; row < screen->height; ++row)
        for(unsigned i = 0; i < pixel_bytes; ++i)
            printf(" %u", data[(size_t)row * screen->width * 4u + i]);
    puts("");
    assert(!member);
    freescreen(&screen);
    assert(!screen);
    return 0;
}
'''


def direct_png(width, color, pixels):
    raw = b''.join(b'\0' + bytes(row) for row in pixels)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, len(pixels), 8, color, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


class DirectBackgroundPngTests(unittest.TestCase):
    def test_classic_direct_png_pixels_and_member_paths(self):
        compiler, flags, links = native_context('4086')
        engine = SOURCE / 'src/engines/4086/source'
        with tempfile.TemporaryDirectory(prefix='anybor-direct-png-') as directory:
            work = Path(directory)
            probe = work / 'direct.c'
            probe.write_text(DIRECT_PNG_PROBE)
            binary = work / 'direct'
            units = [engine / name for name in ('gamelib/loadimg.c', 'gamelib/screen.c',
                                               'gamelib/pixelformat.c', 'pnglib/pngdec.c')]
            compile_checked(compiler + flags + [str(probe), *map(str, units), *links, '-o', str(binary)])
            for revision in (4097, 4107):
                for width, color in ((4, 2), (4, 0), (4, 4), (5, 2)):
                    with self.subTest(revision=revision, width=width, color=color):
                        self.check_pixels(binary, work, revision, width, color)

    def check_pixels(self, binary, work, revision, width, color):
        path = work / 'background.png'
        components = {2: 3, 0: 1, 4: 2}[color]
        rows = [list(range(start, start + width * components)) for start in (9, 51)]
        path.write_bytes(direct_png(width, color, rows))
        legacy_gray = revision == 4097 and color in (0, 4)
        expected = []
        for row in rows:
            for index in range(0, len(row), components):
                pixel = row[index:index + components]
                if color == 2:
                    expected.extend([*pixel, 255])
                elif legacy_gray:
                    expected.extend(pixel if color == 4 else [pixel[0], 255])
                else:
                    expected.extend([pixel[0]] * 3 + [pixel[1] if color == 4 else 255])
            if legacy_gray:
                expected.extend([0] * (width * 2))
        for argument, openings in ((path, 1), (path.with_suffix(''), 2)):
            output = subprocess.check_output([str(binary), str(revision), str(argument), str(width * 4)],
                                             text=True, timeout=10, env=sanitizer_environment())
            self.assertEqual(list(map(int, output.split())), [width, len(rows), openings, 1, *expected])


if __name__ == '__main__':
    unittest.main()
