"""Compare indexed tables and nearest-color results in each source profile.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from historical_palette_luts import render_palette_luts
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURES = Path(__file__).parent / 'fixtures'


def program(engine, expected_path, queries):
    code = render_palette_luts(revision=int(engine), expected_path=str(expected_path), queries=queries)
    marker = 'int main(void){'
    if code.count(marker) != 1:
        raise ValueError('One bounded indexed palette entry point required')
    return code.replace(marker, '''int main(int argc,char **argv){
 assert(argc==2);char *end=NULL;unsigned long revision=strtoul(argv[1],&end,10);
 assert(end && !*end && revision>0 && revision<=UINT32_MAX);obor_profile_build=(uint32_t)revision;
''')


class PaletteLutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_contract_fixture(FIXTURES / 'palette-lut-contracts.json')
        cls.queries = load_contract_fixture(FIXTURES / 'palette-lut-queries.json')
        expected = FIXTURES / 'palette-luts.bin'
        raw = expected.read_bytes()
        if (len(raw) != cls.fixture['reference_bytes'] or
                hashlib.sha256(raw).hexdigest() != cls.fixture['reference_sha256']):
            raise ValueError('Independent indexed palette reference identity differs')
        cls.pin = json.loads((SOURCE / 'src/pin.json').read_text())
        cls.contexts = {}
        for row in cls.fixture['contexts']:
            key = (row['engine'], row['revision'])
            if key in cls.contexts:
                raise ValueError('Duplicate indexed palette context')
            cls.contexts[key] = row
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
        warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        host = [] if sys.platform == 'darwin' else ['-DLINUX=1']
        temporary = tempfile.TemporaryDirectory(prefix='anybor-palette-luts-')
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
                *warnings, '-O1', '-g', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=' + engine,
                *host, '-fsigned-char', '-ffunction-sections', '-fdata-sections',
                '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all']
            unit = work / (engine + '.o')
            source = work / (engine + '.c')
            executable = source.with_suffix('')
            compile_checked(compiler + flags + ['-c', str(root / 'source/gamelib/palette.c'), '-o', str(unit)])
            source.write_text(program(engine, expected, cls.queries))
            compile_checked(compiler + flags + [str(source), str(unit), *links, '-lm', '-o', str(executable)])
            cls.executables[engine] = executable

    def affected(self, profile):
        bounds = self.fixture['coverage'].get(profile['engine'])
        return bounds is not None and bounds[0] <= int(profile.get('revision', profile['build'])) <= bounds[1]

    def check_context(self, row):
        observed = json.loads(subprocess.check_output([
            str(self.executables[row['engine']]), str(row['revision'])], text=True,
            timeout=15, env=sanitizer_environment()))
        self.assertEqual(observed, dict(status='PASS', bytes=self.fixture['table_bytes'], queries=len(self.queries)))

    def test_every_affected_profile_has_own_source_contract(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if self.affected(profile):
                self.assertIn((profile['engine'], int(profile.get('revision', profile['build']))), self.contexts)
        for row in self.contexts.values():
            for field in ('source_commit', 'source_palette_blob'):
                self.assertRegex(row[field], r'^[0-9a-f]{40}$')
            self.assertEqual(len(row['source_fragments']), 7)
            for digest in row['source_fragments'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')

    def test_each_registered_profile_preserves_indexed_tables_and_queries(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if self.affected(profile):
                with self.subTest(profile=profile['build']):
                    self.check_context(self.contexts[profile['engine'], int(profile.get('revision', profile['build']))])

    def test_each_original_context_preserves_indexed_tables_and_queries(self):
        for row in self.contexts.values():
            with self.subTest(engine=row['engine'], revision=row['revision']):
                self.check_context(row)


if __name__ == '__main__':
    unittest.main()
