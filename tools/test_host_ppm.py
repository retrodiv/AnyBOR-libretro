"""Preserve every captured pixel while writing complete RGB rows.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))


def writer_source():
    source = (ROOT / 'tests/host/libretro_host.c').read_text()
    start = source.index('static void dump_ppm(')
    end = source.index('\n}\n', start) + 3
    return source[start:end]


@unittest.skipUnless(shutil.which('cc'), 'Needs a native C compiler')
class HostPPMTests(unittest.TestCase):
    def test_row_writer_is_byte_identical_for_pixels_padding_and_empty_geometry(self):
        program = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint8_t *g_fb;
static unsigned g_fw, g_fh;
static size_t g_fpitch;
static unsigned write_calls;
static size_t observed_fwrite(const void *data, size_t size, size_t count, FILE *file) {
    ++write_calls;
    return fwrite(data, size, count, file);
}
#define fwrite observed_fwrite
@WRITER@
#undef fwrite
int main(int argc, char **argv) {
    if (argc != 4) return 2;
    g_fw = (unsigned)strtoul(argv[1], NULL, 10);
    g_fh = (unsigned)strtoul(argv[2], NULL, 10);
    g_fpitch = (size_t)g_fw * 4 + (size_t)strtoul(argv[3], NULL, 10);
    g_fb = (uint8_t *)malloc(g_fpitch * (g_fh ? g_fh : 1) + 1);
    if (!g_fb) return 3;
    memset(g_fb, 0x9d, g_fpitch * (g_fh ? g_fh : 1) + 1);
    for (unsigned y = 0; y < g_fh; ++y) {
        uint32_t *row = (uint32_t *)(g_fb + (size_t)y * g_fpitch);
        for (unsigned x = 0; x < g_fw; ++x)
            row[x] = 0xa5000000u | ((x * 31u + y * 19u) & 0xffffffu);
    }
    dump_ppm("observed-", 17);
    free(g_fb);
    return write_calls == g_fh ? 0 : 4;
}
'''.replace('@WRITER@', writer_source())
        compilers = [shlex.split(os.environ.get('HOST_CC', 'cc'))]
        if shutil.which('clang') and compilers[0] != ['clang']:
            compilers.append(['clang'])
        for compiler in compilers:
            with self.subTest(compiler=compiler), tempfile.TemporaryDirectory(prefix='host-ppm-') as temp:
                work = Path(temp)
                src, exe = work / 'probe.c', work / 'probe'
                src.write_text(program)
                subprocess.run([*compiler, '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                                str(src), '-o', str(exe)], check=True, timeout=30)
                for width, height, padding in ((0, 3, 16), (3, 0, 16), (1, 1, 0), (2, 3, 8),
                                                (7, 5, 12), (257, 3, 20), (640, 480, 16), (1280, 720, 0)):
                    subprocess.run([str(exe), str(width), str(height), str(padding)],
                                   cwd=work, check=True, timeout=15)
                    expected = bytearray(('P6\n%d %d\n255\n' % (width, height)).encode())
                    for y in range(height):
                        for x in range(width):
                            pixel = (x * 31 + y * 19) & 0xffffff
                            expected.extend(((pixel >> 16) & 255, (pixel >> 8) & 255, pixel & 255))
                    self.assertEqual((work / 'observed-000017.ppm').read_bytes(), expected)


if __name__ == '__main__':
    unittest.main()
