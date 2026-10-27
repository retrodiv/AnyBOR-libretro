"""Compare native file results and bounded stream owner cleanup per profile.

Complete native variant code supplies conversions and string ownership. Fixture
directories stand in for frontend naming; archives and game execution are absent.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import json
from historical_filestreams import extract_storage_helpers
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from historical_stream_filesystem import render_filesystem
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked
from test_filestream_transfer import runtime_profile
from test_historical_player import function

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURE=Path(__file__).parent/'fixtures/stream-filesystem-contracts.json'


class StreamFilesystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=load_contract_fixture(FIXTURE);cls.rows=cls.fixture['sources']
        cls.pin=json.loads((SOURCE/'src/pin.json').read_text())
        temporary=tempfile.TemporaryDirectory(prefix='abfs-')
        cls.addClassCleanup(temporary.cleanup);cls.work=Path(temporary.name);cls.executables={}
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack','-Wno-error=deprecated-non-prototype']if'clang'in version.lower()else[]
        host=[]if sys.platform=='darwin'else['-DLINUX=1']
        link=['-Wl,-dead_strip']if sys.platform=='darwin'else['-no-pie','-Wl,--gc-sections']
        for engine,options in cls.fixture['engines'].items():
            root=SOURCE/'src/engines'/engine
            script=(root/'openborscript.c').read_bytes().decode('utf-8','surrogateescape')
            helpers=extract_storage_helpers(script,function)
            program=render_filesystem(revisions=[int(engine)],
                opening=function(script,'openbor_openfilestream'),
                saving=function(script,'openbor_savefilestream'),helpers=helpers,**options)
            source=cls.work/(engine+'.c')
            source.write_bytes(runtime_profile(program).encode('utf-8','surrogateescape'))
            binary=source.with_suffix('');includes=[root,SOURCE/'src/port/libretro',root/'source',
                *sorted(p for p in(root/'source').iterdir()if p.is_dir())]
            compile_checked(compiler+['-std=gnu11','-fgnu89-inline','-Wall','-Wextra','-Werror',
                '-Wno-error=deprecated-declarations','-Wno-unused-variable','-Wno-unused-function',
                '-Wno-error=misleading-indentation','-Wno-error=sign-compare','-Wno-implicit-fallthrough',
                '-Wno-unused-parameter','-Wno-unused-but-set-variable','-O0','-g','-fsigned-char',
                '-fcommon','-ffunction-sections','-fdata-sections','-DLIBRETRO=1',
                '-DOBOR_ENGINE_BUILD='+engine,'-fsanitize=address,undefined,pointer-overflow',
                '-fno-sanitize-recover=all',*host,*warnings,*['-I'+str(p)for p in includes],
                str(source),str(root/'source/scriptlib/ScriptVariant.c'),*link,'-lm','-o',str(binary)])
            cls.executables[engine]=binary

    def check_context(self,engine,revision):
        with tempfile.TemporaryDirectory(prefix='case-',dir=self.work)as scratch:
            environment=dict(sanitizer_environment(),TMPDIR=scratch)
            observed=subprocess.check_output([str(self.executables[engine]),str(revision)],
                                            text=True,timeout=15,env=environment)
        options=self.fixture['engines'][engine]
        self.assertEqual(json.loads(observed),dict(status='PASS',contexts=1,
            cases=len(options['cases'])+1+int(options['check_allocation_refusal'])))

    def test_every_own_source_context_preserves_native_file_behavior(self):
        for row in self.rows:
            with self.subTest(profile=row['revision']):self.check_context(row['engine'],row['revision'])

    def test_every_registered_affected_profile_closes_its_owned_files(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if profile['engine']in self.executables:
                with self.subTest(profile=profile['build']):
                    self.check_context(profile['engine'],int(profile.get('revision',profile['build'])))

    def test_source_and_policy_coverage_is_explicit(self):
        self.assertEqual(len(self.rows),len({r['revision']for r in self.rows}))
        self.assertEqual(set(self.executables)|set(self.fixture['unaffected_native_owner_engines']),
                         {r['build']for r in self.pin['engines']})
        for row in self.rows:
            self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')
            self.assertEqual(set(row['source_sha256']),
                {'openbor_openfilestream','openbor_savefilestream','ScriptVariant.c','ScriptVariant.h','depends.h'})
            for digest in row['source_sha256'].values():self.assertRegex(digest,r'^[0-9a-f]{64}$')
        for options in self.fixture['engines'].values():
            self.assertTrue(options['open_closes_file']);self.assertTrue(options['check_allocation_refusal'])


if __name__=='__main__':unittest.main()
