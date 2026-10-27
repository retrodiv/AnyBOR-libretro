"""Check stream owners at global shutdown for registered and own-source cases.

Unrelated VM resources are empty. Caller order, level release and the complete
interpreter have separate contracts.
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

from historical_stream_shutdown import render_shutdown
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked
from test_filestream_transfer import runtime_profile
from test_historical_player import function

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURE=Path(__file__).parent/'fixtures/stream-shutdown-contracts.json'


class StreamShutdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=load_contract_fixture(FIXTURE)['sources']
        cls.pin=json.loads((SOURCE/'src/pin.json').read_text())
        temporary=tempfile.TemporaryDirectory(prefix='anybor-stream-shutdown-')
        cls.addClassCleanup(temporary.cleanup);work=Path(temporary.name);cls.executables={}
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack']if'clang'in version.lower()else[]
        host=[]if sys.platform=='darwin'else['-DLINUX=1']
        link=['-Wl,-dead_strip']if sys.platform=='darwin'else['-no-pie','-Wl,--gc-sections']
        for engine in sorted({row['engine']for row in cls.rows}):
            root=SOURCE/'src/engines'/engine
            program=render_shutdown(revisions=[int(engine)],
                shutdown=function((root/'openborscript.c').read_text(),'Script_Global_Clear'),
                slots=50,physical_fixed=False,release_streams=True)
            source=work/(engine+'.c');source.write_text(runtime_profile(program));binary=source.with_suffix('')
            includes=[root,SOURCE/'src/port/libretro',root/'source',
                      *sorted(p for p in(root/'source').iterdir()if p.is_dir())]
            compile_checked(compiler+['-std=gnu11','-fgnu89-inline','-Wall','-Wextra','-Werror',
                '-Wno-error=deprecated-declarations','-Wno-unused-variable','-Wno-unused-function',
                '-Wno-unused-parameter','-O0','-g','-fsigned-char','-fcommon',
                '-ffunction-sections','-fdata-sections','-DLIBRETRO=1',
                '-DOBOR_ENGINE_BUILD='+engine,'-fsanitize=address,undefined,pointer-overflow',
                '-fno-sanitize-recover=all',*host,*warnings,*['-I'+str(p)for p in includes],
                str(source),*link,'-lm','-o',str(binary)])
            cls.executables[engine]=binary

    def check_context(self,engine,revision):
        observed=subprocess.check_output([str(self.executables[engine]),str(revision)],
                                        text=True,timeout=15,env=sanitizer_environment())
        self.assertEqual(json.loads(observed),dict(status='PASS',contexts=1,cases=4))

    def test_every_own_source_context_retires_owned_stream_storage(self):
        for row in self.rows:
            with self.subTest(profile=row['revision']):self.check_context(row['engine'],row['revision'])

    def test_registered_affected_profiles_retain_bounded_shutdown(self):
        for profile in contract_profiles(Path(__file__).parent / 'fixtures/stream-shutdown-contracts.json', self.pin['profiles']):
            if profile['engine']in self.executables:
                with self.subTest(profile=profile['build']):
                    self.check_context(profile['engine'],int(profile.get('revision',profile['build'])))

    def test_each_original_record_and_release_policy_is_explicit(self):
        self.assertEqual(len(self.rows),len({r['revision']for r in self.rows}))
        for row in self.rows:
            self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')
            self.assertEqual(set(row['source_sha256']),
                             {'Script_Global_Clear','stream-record','native-record-packing'})
            for digest in row['source_sha256'].values():self.assertRegex(digest,r'^[0-9a-f]{64}$')
            self.assertEqual(row['original_record_pack'],4)
            self.assertIs(type(row['original_releases_streams']),bool)
            self.assertEqual(row['original_fixed_slots']is None,row['original_releases_streams'])


if __name__=='__main__':unittest.main()
