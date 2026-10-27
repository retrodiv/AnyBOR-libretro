"""Check native sprite cache sharing and partial ownership for every profile.

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

from historical_sprite_nodes import render_sprite_nodes
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked
from test_historical_player import function

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURE=Path(__file__).parent/'fixtures/sprite-node-contracts.json'


def profile_program(code):
    marker='int main(void){'
    if code.count(marker)!=1:raise ValueError('One bounded sprite-node entry point required')
    return code.replace(marker,'''int main(int argc,char **argv){
 CHECK(argc==2,"profile argument");char *end=NULL;unsigned long revision=strtoul(argv[1],&end,10);
 CHECK(end && !*end && revision>0 && revision<=UINT32_MAX,"profile revision");
 obor_profile_build=(uint32_t)revision;
''')


class SpriteNodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads(FIXTURE.read_text())
        cls.pin=json.loads((SOURCE/'src/pin.json').read_text())
        cls.contexts={(row['engine'],row['revision']):row for row in cls.fixture['contexts']}
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack']if'clang'in version.lower()else[]
        links=['-Wl,-dead_strip']if sys.platform=='darwin'else['-no-pie','-Wl,--gc-sections']
        host=[]if sys.platform=='darwin'else['-DLINUX=1']
        temporary=tempfile.TemporaryDirectory(prefix='anybor-sprite-nodes-')
        cls.addClassCleanup(temporary.cleanup);work=Path(temporary.name);cls.executables={}
        for engine,context in cls.fixture['engines'].items():
            root=SOURCE/'src/engines'/engine
            includes=[root/'source/gamelib',root/'source',root,SOURCE/'src/glue',SOURCE/'src/port/libretro']
            flags=['-I'+str(path)for path in includes]+[
                '-std=gnu11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-error=misleading-indentation','-Wno-error=sign-compare',
                '-Wno-unused-variable','-Wno-unused-function','-Wno-unused-parameter',*warnings,
                '-O0','-g','-DLIBRETRO=1','-DOBOR_ENGINE_BUILD='+engine,*host,'-fsigned-char','-fcommon',
                '-ffunction-sections','-fdata-sections','-fsanitize=address,undefined,pointer-overflow',
                '-fno-sanitize-recover=all']
            text=(root/'openbor.c').read_bytes().decode('utf8',errors='surrogateescape')
            code=render_sprite_nodes(loader=function(text,'loadsprite'),cleanup=function(text,'freesprites'),
                cache=function(text,'cachesprite')if context['node_cache']else '',revision=int(engine),
                node_cache=context['node_cache'],clipped_metadata=context['clipped_metadata'],
                count_type=context['count_type'],mode='all')
            source=work/(engine+'.c');source.write_text(profile_program(code));binary=source.with_suffix('')
            compile_checked(compiler+flags+[str(source),*links,'-o',str(binary)])
            cls.executables[engine]=binary

    def check_context(self,engine,revision):
        output=subprocess.check_output([str(self.executables[engine]),str(revision)],
            text=True,timeout=15,env=sanitizer_environment())
        self.assertEqual(json.loads(output),dict(status='PASS',
            cases=18 if self.fixture['engines'][engine]['node_cache']else 9))

    def test_registered_profiles_and_sources_have_explicit_contexts(self):
        self.assertEqual(len(self.contexts),len(self.fixture['contexts']))
        for profile in self.pin['profiles']:self.assertIn(profile['engine'],self.fixture['engines'])
        for row in self.fixture['contexts']:
            self.assertIn(row['engine'],self.fixture['engines'])
            self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')
            for value in row['source_functions'].values():self.assertRegex(value,r'^[0-9a-f]{64}$')

    def test_each_registered_profile_preserves_cache_identity_and_ownership(self):
        for profile in self.pin['profiles']:
            with self.subTest(profile=profile['build']):
                self.check_context(profile['engine'],int(profile.get('revision',profile['build'])))

    def test_each_declared_context_preserves_cache_identity_and_ownership(self):
        for row in self.fixture['contexts']:
            with self.subTest(engine=row['engine'],revision=row['revision']):
                self.check_context(row['engine'],row['revision'])


if __name__=='__main__':unittest.main()
