"""Check blend operation choice and defined dispatch fallback per profile.

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

from historical_screen_dispatch import render_screen_dispatch, screen_dispatch_parts
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/screen-dispatch-contracts.json'


def program(engine, layout, cases):
    root = SOURCE / 'src/engines' / engine
    parts = screen_dispatch_parts((root / 'source/gamelib/screen.c').read_bytes().decode(
        'utf8', 'surrogateescape'), legacy_water=layout['legacy_water'])
    code = render_screen_dispatch(parts, revision=int(engine), cases=cases, **layout)
    marker = 'int main(void){'
    if code.count(marker) != 1:
        raise ValueError('One native dispatch entry point required')
    return code.replace(marker, '''int main(int argc,char **argv){
 assert(argc==2);char *end=NULL;unsigned long revision=strtoul(argv[1],&end,10);
 assert(end && !*end && revision>0 && revision<=UINT32_MAX);obor_profile_build=(uint32_t)revision;
''')


class ScreenDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text())
        cls.pin = json.loads((SOURCE / 'src/pin.json').read_text())
        cls.contexts = {}
        for row in cls.fixture['contexts']:
            key = row['engine'], row['revision']
            if key in cls.contexts: raise ValueError('Duplicate dispatch context')
            cls.contexts[key] = row
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
        warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        host = [] if sys.platform == 'darwin' else ['-DLINUX=1']
        temporary = tempfile.TemporaryDirectory(prefix='anybor-screen-dispatch-')
        cls.addClassCleanup(temporary.cleanup); work = Path(temporary.name); cls.executables = {}
        for engine, metadata in cls.fixture['engines'].items():
            root = SOURCE / 'src/engines' / engine
            includes = [root / 'source/gamelib', root / 'source', root,
                        SOURCE / 'src/glue', SOURCE / 'src/port/libretro']
            flags = ['-I' + str(p) for p in includes] + [
                '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-error=misleading-indentation', '-Wno-error=sign-compare',
                '-Wno-unused-variable', '-Wno-unused-function', '-Wno-unused-parameter',
                '-Wno-unused-but-set-variable', '-Wno-implicit-fallthrough', *warnings,
                '-O0', '-g', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=' + engine, *host,
                '-fsigned-char', '-fcommon', '-ffunction-sections', '-fdata-sections',
                '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all']
            unit = work / (engine + '-pixelformat.o')
            unit_flags = ['-O1' if flag == '-O0' else flag for flag in flags] + metadata['color_unit_flags']
            compile_checked(compiler + unit_flags + ['-c', str(root / 'source/gamelib/pixelformat.c'),
                                                     '-o', str(unit)])
            names = {metadata['default_contract']}
            names.update(row['contract'] for row in cls.contexts.values() if row['engine'] == engine)
            for contract in sorted(names):
                source = work / (engine + '-' + contract + '.c'); executable = source.with_suffix('')
                source.write_text(program(engine, metadata['layout'], cls.fixture['contracts'][contract]))
                compile_checked(compiler + flags + [str(source), str(unit), *links, '-lm', '-o', str(executable)])
                cls.executables[engine, contract] = executable

    def check_context(self, engine, revision, contract):
        observed = json.loads(subprocess.check_output([
            str(self.executables[engine, contract]), str(revision)], text=True,
            timeout=15, env=sanitizer_environment()))
        self.assertEqual(observed, dict(status='PASS', cases=len(self.fixture['contracts'][contract])))

    def test_each_dispatch_engine_has_pinned_source_and_complete_cases(self):
        expected = {row['build']: row for row in self.pin['engines'] if row['build'] not in self.fixture['excluded_engines']}
        self.assertEqual(set(self.fixture['engines']), set(expected))
        for engine, metadata in self.fixture['engines'].items():
            self.assertEqual(metadata['source_commit'], expected[engine]['commit'])
            self.assertRegex(metadata['source_dispatch_blob'], r'^[0-9a-f]{40}$')
        for row in self.contexts.values():
            self.assertIn(row['contract'], self.fixture['contracts'])
            self.assertRegex(row['source_commit'], r'^[0-9a-f]{40}$')

    def test_every_registered_profile_preserves_dispatch_results(self):
        for row in self.pin['profiles']:
            if row['engine'] not in self.fixture['engines']: continue
            revision = int(row.get('revision', row['build']))
            contract = self.contexts.get((row['engine'], revision), {}).get(
                'contract', self.fixture['engines'][row['engine']]['default_contract'])
            with self.subTest(profile=row['build']): self.check_context(row['engine'], revision, contract)

    def test_each_declared_context_preserves_dispatch_results(self):
        for row in self.contexts.values():
            with self.subTest(engine=row['engine'], revision=row['revision']):
                self.check_context(row['engine'], row['revision'], row['contract'])


if __name__ == '__main__':
    unittest.main()
