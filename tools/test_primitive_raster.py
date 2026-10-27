"""Compare primitive pixels through each profile's complete drawing units.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from historical_primitive_raster import render_primitive_raster
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/primitive-raster-contracts.json'


def program(engine, cases):
    code = render_primitive_raster(revision=int(engine), method_api=True,
                                   channels=True, tint=True, cases=cases)
    marker = 'int main(void){'
    if code.count(marker) != 1:
        raise ValueError('One native primitive raster entry point required')
    return code.replace(marker, '''int main(int argc,char **argv){
 assert(argc==2);char *end=NULL;unsigned long revision=strtoul(argv[1],&end,10);
 assert(end && !*end && revision>0 && revision<=UINT32_MAX);obor_profile_build=(uint32_t)revision;
''')


class PrimitiveRasterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_contract_fixture(FIXTURE)
        cls.pin = json.loads((SOURCE / 'src/pin.json').read_text())
        cls.contexts = {}
        for row in cls.fixture['contexts']:
            key = row['engine'], row['revision']
            if key in cls.contexts:
                raise ValueError('Duplicate primitive raster context')
            cls.contexts[key] = row
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
        warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        host = [] if sys.platform == 'darwin' else ['-DLINUX=1']
        temporary = tempfile.TemporaryDirectory(prefix='anybor-primitive-raster-')
        cls.addClassCleanup(temporary.cleanup)
        work = Path(temporary.name)
        cls.executables = {}
        for engine in sorted({row['engine'] for row in cls.contexts.values()}):
            root = SOURCE / 'src/engines' / engine
            includes = [root / 'source/gamelib', root / 'source', root,
                        SOURCE / 'src/glue', SOURCE / 'src/port/libretro']
            flags = ['-I' + str(p) for p in includes] + [
                '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-error=misleading-indentation', '-Wno-error=sign-compare',
                '-Wno-unused-variable', '-Wno-unused-function', '-Wno-unused-parameter',
                '-Wno-implicit-fallthrough', *warnings, '-O1', '-g', '-DLIBRETRO=1',
                '-DOBOR_ENGINE_BUILD=' + engine, *host, '-fsigned-char', '-ffunction-sections',
                '-fdata-sections', '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all']
            units = []
            for name in ('pixelformat', 'draw', 'draw16', 'draw32'):
                unit = work / (engine + '-' + name + '.o')
                compile_checked(compiler + flags + ['-c', str(root / 'source/gamelib' / (name + '.c')), '-o', str(unit)])
                units.append(str(unit))
            names = sorted({row['contract'] for row in cls.contexts.values() if row['engine'] == engine})
            for contract in names:
                source = work / (engine + '-' + contract + '.c')
                executable = source.with_suffix('')
                source.write_text(program(engine, cls.fixture['contracts'][contract]))
                compile_checked(compiler + flags + [str(source), *units, *links, '-lm', '-o', str(executable)])
                cls.executables[engine, contract] = executable

    def affected(self, profile):
        bounds = self.fixture['coverage'].get(profile['engine'])
        return bounds is not None and bounds[0] <= int(profile.get('revision', profile['build'])) <= bounds[1]

    def check_context(self, row):
        observed = json.loads(subprocess.check_output([
            str(self.executables[row['engine'], row['contract']]), str(row['revision'])],
            text=True, timeout=15, env=sanitizer_environment()))
        self.assertEqual(observed, dict(status='PASS', cases=len(self.fixture['contracts'][row['contract']])))

    def test_every_affected_profile_has_own_source_contract(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if self.affected(profile):
                self.assertIn((profile['engine'], int(profile.get('revision', profile['build']))), self.contexts)
        for row in self.contexts.values():
            self.assertIn(row['contract'], self.fixture['contracts'])
            self.assertRegex(row['source_commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(set(row['source_units']), {'pixelformat', 'draw', 'draw16', 'draw32'})
            for digest in row['source_units'].values():
                self.assertRegex(digest, r'^[0-9a-f]{40}$')

    def test_each_registered_profile_preserves_primitive_pixels(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if self.affected(profile):
                with self.subTest(profile=profile['build']):
                    self.check_context(self.contexts[profile['engine'], int(profile.get('revision', profile['build']))])

    def test_each_original_context_preserves_primitive_pixels(self):
        for row in self.contexts.values():
            with self.subTest(engine=row['engine'], revision=row['revision']):
                self.check_context(row)


if __name__ == '__main__':
    unittest.main()
