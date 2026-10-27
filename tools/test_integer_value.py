"""Preserve valid native integer conversions and defined refused inputs.

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

from historical_integer_value import render_integer_value
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked
from test_filestream_transfer import runtime_profile

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURE=Path(__file__).parent/'fixtures/integer-value-contracts.json'


class IntegerValueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=load_contract_fixture(FIXTURE)
        cls.pin=json.loads((SOURCE/'src/pin.json').read_text())
        temporary=tempfile.TemporaryDirectory(prefix='ab-integer-')
        cls.addClassCleanup(temporary.cleanup);work=Path(temporary.name);cls.executables={}
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack','-Wno-error=deprecated-non-prototype']if'clang'in version.lower()else[]
        host=[]if sys.platform=='darwin'else['-DLINUX=1']
        link=['-Wl,-dead_strip']if sys.platform=='darwin'else['-no-pie','-Wl,--gc-sections']
        for item in cls.pin['engines']:
            engine=item['build'];root=SOURCE/'src/engines'/engine
            program=render_integer_value([int(engine)],cls.fixture['cases'])
            source=work/(engine+'.c');source.write_text(runtime_profile(program))
            binary=source.with_suffix('')
            includes=[root/'source/scriptlib',root,SOURCE/'src/port/libretro',root/'source',
                      *sorted(p for p in(root/'source').iterdir()if p.is_dir())]
            compile_checked(compiler+['-std=gnu11','-fgnu89-inline','-Wall','-Wextra','-Werror',
                '-Wno-error=deprecated-declarations','-Wno-unused-variable','-Wno-unused-function',
                '-Wno-error=misleading-indentation','-Wno-error=sign-compare','-Wno-implicit-fallthrough',
                '-Wno-unused-parameter','-Wno-unused-but-set-variable','-O0','-g','-fsigned-char',
                '-fcommon','-ffunction-sections','-fdata-sections','-DLIBRETRO=1',
                '-DOBOR_ENGINE_BUILD='+engine,
                '-fsanitize=address,undefined,pointer-overflow,float-cast-overflow',
                '-fno-sanitize-recover=all',*host,*warnings,*['-I'+str(p)for p in includes],
                str(source),str(root/'source/scriptlib/ScriptVariant.c'),*link,'-lm','-o',str(binary)])
            cls.executables[engine]=binary

    def check_context(self,engine,revision):
        result=subprocess.check_output([str(self.executables[engine]),str(revision)],
            text=True,timeout=15,env=sanitizer_environment())
        self.assertEqual(json.loads(result),dict(status='PASS',contexts=1,
                                                checks=len(self.fixture['cases'])))

    def test_every_registered_profile_preserves_conversion(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            with self.subTest(profile=profile['build']):
                self.check_context(profile['engine'],int(profile.get('revision',profile['build'])))

    def test_every_own_source_context_preserves_conversion(self):
        for row in self.fixture['sources']:
            with self.subTest(profile=row['revision']):
                self.check_context(row['engine'],row['revision'])

    def test_source_coverage_and_width_contract_are_explicit(self):
        self.assertEqual(set(self.executables),{e['build']for e in self.pin['engines']})
        rows=self.fixture['sources']
        self.assertEqual(len(rows),len({r['revision']for r in rows}))
        for row in rows:
            self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')
            self.assertRegex(row['integer_value_sha256'],r'^[0-9a-f]{64}$')
            for digest in row['variant_sha256'].values():
                self.assertRegex(digest,r'^[0-9a-f]{64}$')


if __name__=='__main__':unittest.main()
