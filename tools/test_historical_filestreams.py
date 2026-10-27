"""Check historical stream slot results and capacity for each own-source context.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

from historical_filestreams import extract_storage_helpers, render_create_close
from historical_level_streams import render_level_storage
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked
from test_historical_player import function

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURE=Path(__file__).parent/'fixtures/filestream-contracts.json'


def runtime_profile(code):
    marker='int main(void){'
    if code.count(marker)!=1:raise ValueError('One bounded stream entry point required')
    code=code.replace(marker,'''int main(int argc,char **argv){
 CHECK(argc==2,"profile argument");char *end=NULL;
 unsigned long long selected=strtoull(argv[1],&end,10);
 CHECK(end && !*end && selected>0 && selected<=UINT32_MAX,"profile revision");
''')
    code=code.replace('obor_profile_build=revisions[i];','obor_profile_build=(uint32_t)selected;')
    return code.replace('for(unsigned i=0;i<sizeof(revisions)',
                        '(void)revisions;for(unsigned i=0;i<sizeof(revisions)',1)


class HistoricalFilestreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=json.loads(FIXTURE.read_text())['sources']
        cls.pin=json.loads((SOURCE/'src/pin.json').read_text())
        cls.contexts={row['revision']:row for row in cls.rows}
        temporary=tempfile.TemporaryDirectory(prefix='anybor-filestreams-')
        cls.addClassCleanup(temporary.cleanup);work=Path(temporary.name)
        cls.executables={};cls.keys={}
        for row in cls.rows:
            key=(row['engine'],row['logical_capacity'],row['fixed_capacity'],row['attempts'])
            cls.keys[row['revision']]=key
            if key in cls.executables:continue
            engine=SOURCE/'src/engines'/row['engine']
            script=(engine/'openborscript.c').read_text()
            header=(engine/'openbor.h').read_text()
            record=re.search(r'(?ms)^typedef struct\s*\{[^{}]*\}\s*s_filestream\s*;',header)
            if record is None:raise ValueError('One complete native stream record required')
            helpers=extract_storage_helpers(script,function)
            code=render_create_close(revisions=[row['revision']],record=record[0],
                create=function(script,'openbor_createfilestream'),
                close=function(script,'openbor_closefilestream'),physical_fixed=False,
                fixed_capacity=row['fixed_capacity'],logical_capacity=row['logical_capacity'],
                attempts=row['attempts'],helpers=helpers,checked_storage=bool(helpers),
                buffer_bytes=row['initial_bytes']if helpers else None)
            code=runtime_profile(code)
            source=work/(str(len(cls.executables))+'.c');source.write_text(code);binary=source.with_suffix('')
            compile_checked(shlex.split(os.environ.get('HOST_CC','cc'))+[
                '-std=gnu11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-unused-function','-Wno-unused-parameter','-O0','-g','-fsigned-char',
                '-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all',
                str(source),'-o',str(binary)])
            cls.executables[key]=binary

    def check_context(self,revision):
        row=self.contexts[revision]
        observed=subprocess.check_output([str(self.executables[self.keys[revision]]),str(revision)],
                                        text=True,timeout=15,env=sanitizer_environment())
        self.assertEqual(json.loads(observed),dict(status='PASS',contexts=1,
            cases=row['attempts']+7+(16 if row['engine']in {'3741','3842'}else 0)))

    def test_every_own_source_context_preserves_slot_results(self):
        for row in self.rows:
            with self.subTest(profile=row['revision']):self.check_context(row['revision'])

    def test_registered_affected_profiles_have_own_contracts(self):
        for profile in self.pin['profiles']:
            if profile['engine']in {'3741','3842'}:
                revision=int(profile.get('revision',profile['build']))
                if profile['engine']!='3741'and revision not in self.contexts:continue
                self.assertIn(revision,self.contexts)
                self.assertEqual(profile['engine'],self.contexts[revision]['engine'])
                with self.subTest(profile=profile['build']):self.check_context(revision)

    def test_fixture_sources_and_policies_are_explicit(self):
        self.assertEqual(len(self.rows),len(self.contexts))
        for row in self.rows:
            self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')
            self.assertEqual(set(row['source_sha256']),
                             {'stream-record','openbor_createfilestream','openbor_closefilestream'})
            for value in row['source_sha256'].values():self.assertRegex(value,r'^[0-9a-f]{64}$')
            self.assertEqual(row['logical_capacity'] is not None,row['physical_fixed_original'])
            self.assertGreaterEqual(row['initial_bytes'],4)


class LevelOwnedStreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture=Path(__file__).parent/'fixtures/level-stream-contracts.json'
        cls.rows=json.loads(fixture.read_text())['backends']
        cls.pin=json.loads((SOURCE/'src/pin.json').read_text())
        temporary=tempfile.TemporaryDirectory(prefix='anybor-level-streams-')
        cls.addClassCleanup(temporary.cleanup);work=Path(temporary.name);cls.executables={}
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack','-Wno-error=deprecated-non-prototype']if'clang'in version.lower()else[]
        host=[]if sys.platform=='darwin'else['-DLINUX=1']
        link=['-Wl,-dead_strip']if sys.platform=='darwin'else['-no-pie','-Wl,--gc-sections']
        for row in cls.rows:
            engine=row['engine'];root=SOURCE/'src/engines'/engine
            if engine in cls.executables:raise ValueError('One explicit level backend per engine required')
            script=(root/'openborscript.c').read_text();level=(root/'openbor.c').read_text()
            code=render_level_storage(revisions=row['revisions'],
                creating=function(script,'openbor_createfilestream'),
                releasing=function(level,'free_level'),helpers=extract_storage_helpers(script,function),
                owned_extent=True,**{k:row[k]for k in ['slots','buffer_bytes','header_includes']})
            source=work/(engine+'.c');source.write_text(code);binary=source.with_suffix('')
            includes=[root,SOURCE/'src/port/libretro',root/'source',
                *sorted(p for p in(root/'source').iterdir()if p.is_dir())]
            compile_checked(compiler+['-std=gnu11','-fgnu89-inline','-Wall','-Wextra','-Werror',
                '-Wno-error=deprecated-declarations','-Wno-error=misleading-indentation',
                '-Wno-error=sign-compare','-Wno-unused-variable','-Wno-unused-function',
                '-Wno-unused-parameter','-Wno-unused-but-set-variable','-Wno-implicit-fallthrough',
                '-O0','-g','-fsigned-char','-fcommon','-ffunction-sections','-fdata-sections',
                '-DLIBRETRO=1','-DOBOR_ENGINE_BUILD='+engine,*host,*warnings,
                '-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all',
                *['-I'+str(p)for p in includes],str(source),
                str(root/'source/scriptlib/ScriptVariant.c'),*link,'-lm','-o',str(binary)])
            cls.executables[engine]=binary

    def test_level_owned_creation_refusal_and_argument_release(self):
        for row in self.rows:
            with self.subTest(engine=row['engine']):
                observed=subprocess.check_output([str(self.executables[row['engine']])],
                    text=True,timeout=15,env=sanitizer_environment())
                self.assertEqual(json.loads(observed),dict(status='PASS',
                    contexts=len(row['revisions']),cases=4*len(row['revisions'])))

    def test_each_backend_retains_an_explicit_original_and_registered_control(self):
        self.assertTrue(self.rows)
        for row in self.rows:
            self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')
            self.assertEqual(set(row['source_sha256']),{'openbor_createfilestream','free_level'})
            for digest in row['source_sha256'].values():self.assertRegex(digest,r'^[0-9a-f]{64}$')
            self.assertTrue(any(p['engine']==row['engine']and
                int(p.get('revision',p['build']))in row['revisions']for p in self.pin['profiles']))


if __name__=='__main__':unittest.main()
