"""Preserve native legacy stream text results and bounded string ownership.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from historical_filestreams import extract_storage_helpers
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from historical_stream_text import PARTS, render_text
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked
from test_filestream_transfer import runtime_profile
from test_historical_player import function

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURE=Path(__file__).parent/'fixtures/stream-text-contracts.json'


class StreamTextTests(unittest.TestCase):
    fixture_path=FIXTURE
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads(cls.fixture_path.read_text());cls.rows=cls.fixture['sources']
        cls.pin=json.loads((SOURCE/'src/pin.json').read_text())
        temporary=tempfile.TemporaryDirectory(prefix='abtxt-')
        cls.addClassCleanup(temporary.cleanup);work=Path(temporary.name);cls.executables={}
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack','-Wno-error=deprecated-non-prototype']if'clang'in version.lower()else[]
        host=[]if sys.platform=='darwin'else['-DLINUX=1']
        link=['-Wl,-dead_strip']if sys.platform=='darwin'else['-no-pie','-Wl,--gc-sections']
        for group,settings in cls.fixture['engines'].items():
            options=dict(settings);engine=options.pop('engine',group)
            argument_mode=options.pop('argument_mode',False)
            save_errors=options.pop('save_errors',False)
            root=SOURCE/'src/engines'/engine
            script=(root/'openborscript.c').read_bytes().decode('utf-8','surrogateescape')
            helpers=extract_storage_helpers(script,function)
            if argument_mode:
                options['argument_reader']=function(script,'openbor_getfilestreamargument')
                options['argument_parser']=function((root/'openbor.c').read_text(),'findarg')
            if save_errors:
                options['saving']=function(script,'openbor_savefilestream')
            program=render_text(revisions=[int(engine)],
                callbacks={n:function(script,n)for n in PARTS},helpers=helpers,**options)
            source=work/(group+'.c')
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
            cls.executables[group]=binary

    def check_context(self,engine,revision):
        observed=subprocess.check_output([str(self.executables[engine]),str(revision)],
                                        text=True,timeout=15,env=sanitizer_environment())
        count=sum(len(c['steps'])for c in self.fixture['engines'][engine]['cases'])
        self.assertEqual(json.loads(observed),dict(status='PASS',contexts=1,checks=count))

    def test_every_own_source_context_keeps_native_valid_results(self):
        for row in self.rows:
            with self.subTest(profile=row['revision']):self.check_context(row['engine'],row['revision'])

    def test_every_registered_legacy_profile_has_bounded_text_results(self):
        for profile in self.pin['profiles']:
            if profile['engine']in self.executables:
                with self.subTest(profile=profile['build']):
                    self.check_context(profile['engine'],int(profile.get('revision',profile['build'])))

    def test_source_and_distinct_api_coverage_are_explicit(self):
        self.assertEqual(len(self.rows),len({r['revision']for r in self.rows}))
        self.assertEqual(set(self.executables)|set(self.fixture['other_api_engines']),
                         {r['build']for r in self.pin['engines']})
        for row in self.rows:
            self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')
            self.assertEqual(set(row['callbacks']),set(PARTS))
            for digest in row['callbacks'].values():self.assertRegex(digest,r'^[0-9a-f]{64}$')



class StreamArgumentTests(StreamTextTests):
    fixture_path=Path(__file__).parent/'fixtures/stream-argument-contracts.json'

    @staticmethod
    def group(engine,revision):
        return engine+('-prefix'if revision<3831 else'-whole')

    def test_every_own_source_context_keeps_native_valid_results(self):
        for row in self.rows:
            with self.subTest(profile=row['revision']):
                self.check_context(self.group(row['engine'],row['revision']),row['revision'])

    def test_every_registered_legacy_profile_has_bounded_text_results(self):
        for profile in self.pin['profiles']:
            if profile['engine']in {'3400','3741','3842'}:
                revision=int(profile.get('revision',profile['build']))
                with self.subTest(profile=profile['build']):
                    self.check_context(self.group(profile['engine'],revision),revision)

    def test_source_and_distinct_api_coverage_are_explicit(self):
        self.assertEqual(len(self.rows),len({row['revision']for row in self.rows}))
        self.assertEqual({row['engine']for row in self.rows}|set(self.fixture['other_api_engines']),
                         {row['build']for row in self.pin['engines']})
        for row in self.rows:
            self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
            for key in ['reader_sha256','parser_sha256']:
                self.assertRegex(row[key],r'^[0-9a-f]{64}$')
            self.assertEqual(row['comment_prefix'],row['revision']<3831)
            for digest in row['variant_sha256'].values():
                self.assertRegex(digest,r'^[0-9a-f]{64}$')
            self.assertEqual(set(row['error_callback_sha256']),
                {'openbor_getfilestreamargument','openbor_setfilestreamposition',
                 'openbor_filestreamappend','openbor_savefilestream'})
            for digest in row['error_callback_sha256'].values():
                self.assertRegex(digest,r'^[0-9a-f]{64}$')


if __name__=='__main__':unittest.main()
