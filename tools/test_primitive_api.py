"""Compare primitive script transport with each original profile contract.

Typed services observe calls; queue, pixel and VM contracts remain separate.
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

from historical_primitive_api import OPERATIONS,render_primitive_api
from native_sanitizers import sanitizer_environment
from test_historical_player import function

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURE=Path(__file__).parent/'fixtures/primitive-api-contracts.json'


def program(engine,layout,cases):
    if (not isinstance(layout,dict) or set(layout)!={'method_arguments','signed_bitflags'} or
            any(type(value) is not bool for value in layout.values())):
        raise ValueError('Explicit physical primitive signature and flag representation required')
    root=SOURCE/'src/engines'/engine
    text=(root/'openborscript.c').read_bytes().decode('utf8','surrogateescape')
    parts={'openbor_'+name:function(text,'openbor_'+name) for name in OPERATIONS}
    parts['ScriptVariant_IntegerValue']=function((root/'source/scriptlib/ScriptVariant.c').read_bytes().decode(
        'utf8','surrogateescape'),'ScriptVariant_IntegerValue')
    code=render_primitive_api(parts,revision=int(engine),cases=cases,**layout)
    marker='int main(void){'
    if code.count(marker)!=1:raise ValueError('One bounded primitive entry point required')
    return code.replace(marker,'''int main(int argc,char **argv){
 assert(argc==2);char *end=NULL;unsigned long revision=strtoul(argv[1],&end,10);
 assert(end && !*end && revision>0 && revision<=UINT32_MAX);obor_profile_build=(uint32_t)revision;
''')


class PrimitiveAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=load_contract_fixture(FIXTURE);cls.contexts={}
        for row in cls.fixture['contexts']:
            key=(row['engine'],row['revision'])
            if key in cls.contexts:raise ValueError('Duplicate native primitive context')
            cls.contexts[key]=row
        cls.pin=json.loads((SOURCE/'src/pin.json').read_text())
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links=['-Wl,-dead_strip'] if sys.platform=='darwin' else ['-no-pie','-Wl,--gc-sections']
        host=[] if sys.platform=='darwin' else ['-DLINUX=1']
        temporary=tempfile.TemporaryDirectory(prefix='anybor-primitive-api-')
        cls.addClassCleanup(temporary.cleanup);work=Path(temporary.name);cls.executables={}
        for engine,contract in sorted({(r['engine'],r['contract']) for r in cls.contexts.values()}):
            root=SOURCE/'src/engines'/engine
            includes=[root,SOURCE/'src/port/libretro',SOURCE/'src/glue',root/'source',
                      *sorted(p for p in (root/'source').iterdir() if p.is_dir())]
            source=work/(engine+'-'+contract+'.c');executable=source.with_suffix('')
            source.write_bytes(program(engine,cls.fixture['layouts'][engine],
                cls.fixture['cases'][contract]).encode('utf8','surrogateescape'))
            compiled=subprocess.run(compiler+['-I'+str(p) for p in includes]+[
                '-std=gnu11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-error=sign-compare','-Wno-error=misleading-indentation',
                '-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter',*warnings,
                '-O1','-g','-DLIBRETRO=1','-DOBOR_ENGINE_BUILD='+engine,*host,'-fsigned-char',
                '-ffunction-sections','-fdata-sections','-fsanitize=address,undefined,pointer-overflow',
                '-fno-sanitize-recover=all',str(source),*links,'-lm','-o',str(executable)],
                capture_output=True,text=True,timeout=60)
            if compiled.stdout:sys.stderr.write(compiled.stdout)
            if compiled.stderr:sys.stderr.write(compiled.stderr)
            if compiled.returncode:raise RuntimeError('Native primitive API compilation failed')
            cls.executables[engine,contract]=executable

    def affected(self,profile):
        bounds=self.fixture['coverage'].get(profile['engine'])
        return bounds is not None and bounds[0]<=int(profile.get('revision',profile['build']))<=bounds[1]

    def check_context(self,row):
        observed=subprocess.check_output([str(self.executables[row['engine'],row['contract']]),
            str(row['revision'])],text=True,timeout=15,env=sanitizer_environment())
        self.assertEqual(json.loads(observed),dict(status='PASS',cases=len(self.fixture['cases'][row['contract']])))

    def test_every_affected_profile_has_own_native_contract(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if self.affected(profile):
                self.assertIn((profile['engine'],int(profile.get('revision',profile['build']))),self.contexts)
        for row in self.contexts.values():
            self.assertIn(row['contract'],self.fixture['cases'])
            self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_header_sha256'],r'^[0-9a-f]{64}$')
            self.assertRegex(row['source_integer_reader_sha256'],r'^[0-9a-f]{64}$')
            for name in OPERATIONS:self.assertRegex(row['source_fragments']['openbor_'+name],r'^[0-9a-f]{64}$')

    def test_each_registered_profile_preserves_primitive_calls(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if self.affected(profile):
                with self.subTest(profile=profile['build']):
                    self.check_context(self.contexts[profile['engine'],int(profile.get('revision',profile['build']))])

    def test_each_declared_original_context_preserves_primitive_calls(self):
        for row in self.contexts.values():
            with self.subTest(engine=row['engine'],revision=row['revision']):self.check_context(row)


if __name__=='__main__':
    unittest.main()
