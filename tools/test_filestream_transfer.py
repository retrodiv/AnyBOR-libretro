"""Check native-header stream outputs for each registered and own-source case.

The owned-byte provider isolates transfer from archive parsing, filesystem
paths, VM dispatch and gameplay.
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

from historical_filestream_transfer import render_pak_open
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked
from test_historical_player import function

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURES=Path(__file__).parent/'fixtures'


def runtime_profile(code):
    markers=['int main(void){','obor_profile_build=revisions[n];','for(unsigned n=0;n<sizeof(revisions)']
    if any(code.count(marker)!=1 for marker in markers):
        raise ValueError('One bounded transfer entry point and profile loop required')
    return code.replace(markers[0],'''int main(int argc,char **argv){
 CHECK(argc==2,"profile argument");char *end=NULL;
 unsigned long long selected=strtoull(argv[1],&end,10);
 CHECK(end && !*end && selected>0 && selected<=UINT32_MAX,"profile revision");
''').replace(markers[1],'obor_profile_build=(uint32_t)selected;').replace(
        markers[2],'(void)revisions;'+markers[2])


class FilestreamTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layouts=load_contract_fixture(FIXTURES/'filestream-transfer-layouts.json')['engines']
        cls.pin=json.loads((SOURCE/'src/pin.json').read_text())
        cls.own=load_contract_fixture(FIXTURES/'filestream-contracts.json')['sources']
        temporary=tempfile.TemporaryDirectory(prefix='anybor-stream-transfer-')
        cls.addClassCleanup(temporary.cleanup);work=Path(temporary.name);cls.executables={}
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack']if'clang'in version.lower()else[]
        host=[]if sys.platform=='darwin'else['-DLINUX=1']
        link=['-Wl,-dead_strip']if sys.platform=='darwin'else['-no-pie','-Wl,--gc-sections']
        for engine,layout in cls.layouts.items():
            root=SOURCE/'src/engines'/engine;script=(root/'openborscript.c').read_text()
            helpers=extract_storage_helpers(script,function)
            program=render_pak_open(revisions=[int(engine)],
                opening=function(script,'openbor_openfilestream'),helpers=helpers,
                payload=[97,0,98,10],**{key:layout[key]for key in
                    ['header_includes','level_streams','provider_const_name','owned_extent']})
            source=work/(engine+'.c');source.write_bytes(runtime_profile(program).encode('utf-8','surrogateescape'))
            binary=source.with_suffix('');includes=[root,SOURCE/'src/port/libretro',root/'source',
                *sorted(p for p in(root/'source').iterdir()if p.is_dir())]
            compile_checked(compiler+['-std=gnu11','-fgnu89-inline','-Wall','-Wextra','-Werror',
                '-Wno-error=deprecated-declarations','-Wno-unused-variable','-Wno-unused-function',
                '-Wno-unused-parameter','-Wno-unused-but-set-variable','-O0','-g','-fsigned-char',
                '-fcommon','-ffunction-sections','-fdata-sections','-DLIBRETRO=1',
                '-DOBOR_ENGINE_BUILD='+engine,'-fsanitize=address,undefined,pointer-overflow',
                '-fno-sanitize-recover=all',*host,*warnings,*['-I'+str(p)for p in includes],
                str(source),*link,'-lm','-o',str(binary)])
            cls.executables[engine]=binary

    def check_context(self,engine,revision):
        result=subprocess.check_output([str(self.executables[engine]),str(revision)],
                                       text=True,timeout=15,env=sanitizer_environment())
        layout=self.layouts[engine]
        self.assertEqual(json.loads(result),dict(status='PASS',contexts=1,cases=3,
            **{key:layout[key]for key in ['record_bytes','buffer_offset','size_offset']}))

    def test_every_registered_profile_preserves_native_transfer(self):
        for profile in contract_profiles(Path(__file__).parent / 'fixtures/filestream-contracts.json', self.pin['profiles']):
            with self.subTest(profile=profile['build']):
                self.check_context(profile['engine'],int(profile.get('revision',profile['build'])))

    def test_every_own_source_context_preserves_native_transfer(self):
        for row in self.own:
            with self.subTest(profile=row['revision']):self.check_context(row['engine'],row['revision'])

    def test_native_engine_registry_is_complete(self):
        self.assertEqual(set(self.layouts),{row['build']for row in self.pin['engines']})


if __name__=='__main__':unittest.main()
