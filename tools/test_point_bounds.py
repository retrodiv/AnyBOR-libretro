"""Check valid point pixels and ignored frame-edge queries per profile.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from historical_point_bounds import render_point_bounds
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/point-bounds-contracts.json'


def program(engine, entries, cases):
    code = render_point_bounds(revision=int(engine), entries=entries, cases=cases)
    marker = 'int main(void){'
    if code.count(marker) != 1:
        raise ValueError('One native point entry point required')
    return code.replace(marker, '''int main(int argc,char **argv){
 assert(argc==2);char *end=NULL;unsigned long revision=strtoul(argv[1],&end,10);
 assert(end && !*end && revision>0 && revision<=UINT32_MAX);obor_profile_build=(uint32_t)revision;
''')


class PointBoundsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text())
        cls.pin = json.loads((SOURCE / 'src/pin.json').read_text())
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
        warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        host = [] if sys.platform == 'darwin' else ['-DLINUX=1']
        temporary = tempfile.TemporaryDirectory(prefix='anybor-point-bounds-')
        cls.addClassCleanup(temporary.cleanup)
        work = Path(temporary.name)
        cls.executables = {}
        for engine, metadata in cls.fixture['engines'].items():
            root = SOURCE / 'src/engines' / engine
            includes = [root / 'source/gamelib', root / 'source', root,
                        SOURCE / 'src/glue', SOURCE / 'src/port/libretro']
            flags = ['-I' + str(p) for p in includes] + [
                '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-error=misleading-indentation', '-Wno-error=sign-compare',
                '-Wno-unused-variable', '-Wno-unused-function', '-Wno-unused-parameter',
                '-Wno-implicit-fallthrough', *warnings, '-O0', '-g', '-DLIBRETRO=1',
                '-DOBOR_ENGINE_BUILD=' + engine, *host, '-fsigned-char', '-fcommon', '-ffunction-sections',
                '-fdata-sections', '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all']
            units = []
            for name in ('pixelformat', 'draw', 'draw16', 'draw32'):
                unit = work / (engine + '-' + name + '.o')
                compile_checked(compiler + flags + ['-c', str(root / 'source/gamelib' / (name + '.c')), '-o', str(unit)])
                units.append(str(unit))
            source = work / (engine + '.c')
            executable = source.with_suffix('')
            source.write_text(program(engine, metadata['entries'], cls.fixture['cases']))
            compile_checked(compiler + flags + [str(source), *units, *links, '-lm', '-o', str(executable)])
            cls.executables[engine] = executable

    def check_context(self, engine, revision):
        observed = json.loads(subprocess.check_output([str(self.executables[engine]), str(revision)],
                              text=True, timeout=15, env=sanitizer_environment()))
        self.assertEqual(observed, dict(status='PASS', cases=len(self.fixture['cases'])))

    def test_every_physical_engine_has_pinned_entries(self):
        self.assertEqual(set(self.fixture['engines']), {row['build'] for row in self.pin['engines']})
        for row in self.pin['engines']:
            self.assertEqual(row['commit'], self.fixture['engines'][row['build']]['source_commit'])

    def test_every_registered_profile_preserves_points(self):
        for row in self.pin['profiles']:
            with self.subTest(profile=row['build']):
                self.check_context(row['engine'], int(row.get('revision', row['build'])))

    def test_every_declared_source_context_preserves_points(self):
        for row in self.fixture['contexts']:
            with self.subTest(engine=row['engine'], revision=row['revision']):
                self.check_context(row['engine'], row['revision'])


if __name__ == '__main__':
    unittest.main()
