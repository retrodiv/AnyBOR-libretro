"""Compare blend-table factory and ownership contracts for each source profile.

Providers observe calls and return owned tokens; no LUT or pixels are generated.
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

from historical_blend_tables import blend_table_parts,render_blend_tables
from native_sanitizers import sanitizer_environment

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURE=Path(__file__).parent/'fixtures/blend-table-contracts.json'


def program(engine,modes,layout,cases):
    if not isinstance(layout,dict) or set(layout)!={'dynamic_level_palettes'} or type(layout['dynamic_level_palettes']) is not bool:
        raise ValueError('Explicit physical palette storage required')
    root=SOURCE/'src/engines'/engine
    def text(name):return (root/name).read_bytes().decode('utf8','surrogateescape')
    parts=blend_table_parts(text('openbor.c'),text('source/gamelib/pixelformat.c'))
    code=render_blend_tables(parts,revision=int(engine),native_modes=modes,cases=cases,**layout)
    marker='int main(void){'
    if code.count(marker)!=1:raise ValueError('One bounded blend-table entry point required')
    return code.replace(marker,'''int main(int argc,char **argv){
 assert(argc==2);char *end=NULL;unsigned long revision=strtoul(argv[1],&end,10);
 assert(end && !*end && revision>0 && revision<=UINT32_MAX);obor_profile_build=(uint32_t)revision;
''')


class BlendTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=load_contract_fixture(FIXTURE);cls.contexts={}
        for row in cls.fixture['contexts']:
            key=(row['engine'],row['revision'])
            if key in cls.contexts:raise ValueError('Duplicate native blend-table context')
            cls.contexts[key]=row
        cls.pin=json.loads((SOURCE/'src/pin.json').read_text())
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links=['-Wl,-dead_strip'] if sys.platform=='darwin' else ['-no-pie','-Wl,--gc-sections']
        host=[] if sys.platform=='darwin' else ['-DLINUX=1']
        temporary=tempfile.TemporaryDirectory(prefix='anybor-blend-tables-')
        cls.addClassCleanup(temporary.cleanup);work=Path(temporary.name);cls.executables={}
        for engine,contract in sorted({(r['engine'],r['contract']) for r in cls.contexts.values()}):
            root=SOURCE/'src/engines'/engine
            includes=[root,SOURCE/'src/port/libretro',SOURCE/'src/glue',root/'source',
                      *sorted(p for p in (root/'source').iterdir() if p.is_dir())]
            source=work/(engine+'-'+contract+'.c');executable=source.with_suffix('')
            source.write_bytes(program(engine,int(contract),cls.fixture['layouts'][engine],cls.fixture['contracts'][contract]).encode('utf8','surrogateescape'))
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
            if compiled.returncode:raise RuntimeError('Native blend-table compilation failed')
            cls.executables[engine,contract]=executable

    def affected(self,profile):
        bounds=self.fixture['coverage'].get(profile['engine'])
        return bounds is not None and bounds[0]<=int(profile.get('revision',profile['build']))<=bounds[1]

    def check_context(self,row):
        observed=subprocess.check_output([str(self.executables[row['engine'],row['contract']]),
            str(row['revision'])],text=True,timeout=15,env=sanitizer_environment())
        self.assertEqual(json.loads(observed),dict(status='PASS',cases=len(self.fixture['contracts'][row['contract']])))

    def test_every_affected_profile_has_own_native_contract(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if self.affected(profile):
                self.assertIn((profile['engine'],int(profile.get('revision',profile['build']))),self.contexts)
        for row in self.contexts.values():
            self.assertIn(row['contract'],self.fixture['contracts'])
            self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_header_blob'],r'^[0-9a-f]{40}$')
            self.assertIn(row['native_palette_storage'],('embedded','dynamic'))
            for digest in row['source_palette_declarations'].values():self.assertRegex(digest,r'^[0-9a-f]{64}$')
            for digest in row['source_fragments'].values():self.assertRegex(digest,r'^[0-9a-f]{64}$')

    def test_each_registered_profile_preserves_blend_tables(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if self.affected(profile):
                with self.subTest(profile=profile['build']):
                    self.check_context(self.contexts[profile['engine'],int(profile.get('revision',profile['build']))])

    def test_each_declared_original_context_preserves_blend_tables(self):
        for row in self.contexts.values():
            with self.subTest(engine=row['engine'],revision=row['revision']):self.check_context(row)


if __name__=='__main__':
    unittest.main()
