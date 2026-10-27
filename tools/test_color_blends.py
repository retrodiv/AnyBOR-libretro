"""Compare complete color units with each original profile's integer results.

This covers color selection and arithmetic without palette lookup tables.
Rasterization, palette construction, script calls and gameplay are separate.
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

from historical_color_blends import render_color_blend
from native_sanitizers import sanitizer_environment

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURE=Path(__file__).parent/'fixtures/color-blend-contracts.json'


def program(engine,options):
    code=render_color_blend(revision=int(engine),**options)
    marker='int main(void){'
    if code.count(marker)!=1:raise ValueError('One bounded color entry point required')
    return code.replace(marker,'''int main(int argc,char **argv){
 assert(argc==2);char *end=NULL;unsigned long revision=strtoul(argv[1],&end,10);
 assert(end && !*end && revision>0 && revision<=UINT32_MAX);obor_profile_build=(uint32_t)revision;
''')


def compile_checked(command):
    result=subprocess.run(command,capture_output=True,text=True,timeout=90)
    if result.stdout:sys.stderr.write(result.stdout)
    if result.stderr:sys.stderr.write(result.stderr)
    if result.returncode:raise RuntimeError('Native color unit compilation failed')


class ColorBlendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads(FIXTURE.read_text());cls.contexts={}
        for row in cls.fixture['contexts']:
            key=(row['engine'],row['revision'])
            if key in cls.contexts:raise ValueError('Duplicate native color context')
            cls.contexts[key]=row
        cls.pin=json.loads((SOURCE/'src/pin.json').read_text())
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links=['-Wl,-dead_strip'] if sys.platform=='darwin' else ['-no-pie','-Wl,--gc-sections']
        host=[] if sys.platform=='darwin' else ['-DLINUX=1']
        temporary=tempfile.TemporaryDirectory(prefix='anybor-color-blends-')
        cls.addClassCleanup(temporary.cleanup);work=Path(temporary.name);cls.executables={}
        for engine in sorted({row['engine'] for row in cls.contexts.values()}):
            root=SOURCE/'src/engines'/engine
            includes=[root/'source/gamelib',root/'source',root,SOURCE/'src/port/libretro',SOURCE/'src/glue']
            flags=['-I'+str(p) for p in includes]+[
                '-std=gnu11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-error=misleading-indentation','-Wno-error=sign-compare',
                '-Wno-unused-variable','-Wno-unused-function','-Wno-unused-parameter',
                # The original copy routines intentionally cascade switch cases.
                '-Wno-implicit-fallthrough',*warnings,'-O1','-g','-DLIBRETRO=1',
                '-DOBOR_ENGINE_BUILD='+engine,*host,'-fsigned-char','-ffunction-sections',
                '-fdata-sections','-fsanitize=address,undefined,pointer-overflow',
                '-fno-sanitize-recover=all']
            # Compile each complete engine unit once; contract drivers share it.
            unit=work/(engine+'-color.o')
            compile_checked(compiler+flags+['-c',str(root/'source/gamelib/pixelformat.c'),'-o',str(unit)])
            names=sorted({r['contract'] for r in cls.contexts.values() if r['engine']==engine})
            for contract in names:
                source=work/(engine+'-'+contract+'.c');executable=source.with_suffix('')
                source.write_text(program(engine,cls.fixture['contracts'][contract]))
                compile_checked(compiler+flags+[str(source),str(unit),*links,'-lm','-o',str(executable)])
                cls.executables[engine,contract]=executable

    def affected(self,profile):
        bounds=self.fixture['coverage'].get(profile['engine'])
        return bounds is not None and bounds[0]<=int(profile.get('revision',profile['build']))<=bounds[1]

    def check_context(self,row):
        options=self.fixture['contracts'][row['contract']]
        observed=json.loads(subprocess.check_output([
            str(self.executables[row['engine'],row['contract']]),str(row['revision'])],
            text=True,timeout=15,env=sanitizer_environment()))
        expected=dict(status='PASS',cases=len(options['cases']))
        if options.get('table_getter'):expected['table_checks']=19
        self.assertEqual(observed,expected)

    def test_every_affected_profile_has_own_native_contract(self):
        for profile in self.pin['profiles']:
            if self.affected(profile):
                self.assertIn((profile['engine'],int(profile.get('revision',profile['build']))),self.contexts)
        for row in self.contexts.values():
            self.assertIn(row['contract'],self.fixture['contracts'])
            for field in ('source_commit','source_color_blob','source_header_blob'):
                self.assertRegex(row[field],r'^[0-9a-f]{40}$')
            for digest in row['source_fragments'].values():self.assertRegex(digest,r'^[0-9a-f]{64}$')

    def test_each_registered_profile_preserves_color_results(self):
        for profile in self.pin['profiles']:
            if self.affected(profile):
                with self.subTest(profile=profile['build']):
                    self.check_context(self.contexts[profile['engine'],int(profile.get('revision',profile['build']))])

    def test_each_declared_original_context_preserves_color_results(self):
        for row in self.contexts.values():
            with self.subTest(engine=row['engine'],revision=row['revision']):self.check_context(row)


if __name__=='__main__':
    unittest.main()
