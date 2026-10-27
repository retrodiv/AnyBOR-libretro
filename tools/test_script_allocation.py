"""Compare fresh-script state against every affected original source contract.

The native fresh record and variant initializer execute in grouped physical
programs. Each registered affected profile and declared source runs separately.
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

from historical_script_allocation import render_script_allocation
from native_sanitizers import sanitizer_environment
from test_historical_player import function

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent/'fixtures/script-allocation-contracts.json'


def program(engine, expected_magic, variable_counts):
    root = SOURCE/'src/engines'/engine
    parts = {name: function((root/file).read_bytes().decode('utf8','surrogateescape'),name)
             for name,file in [('alloc_script','openborscript.c'),
                               ('ScriptVariant_Init','source/scriptlib/ScriptVariant.c')]}
    code = render_script_allocation(parts,revision=int(engine),expected_magic=expected_magic,
                                    variable_counts=variable_counts)
    marker = 'int main(void){'
    if code.count(marker) != 1:
        raise ValueError('One native fresh-script entry point required')
    return code.replace(marker,'''int main(int argc,char **argv){
 assert(argc==2);char *end=NULL;unsigned long revision=strtoul(argv[1],&end,10);
 assert(end && !*end && revision>0 && revision<=UINT32_MAX);obor_profile_build=(uint32_t)revision;
''')


class ScriptAllocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text())
        cls.contexts = {}
        for row in cls.fixture['contexts']:
            key = (row['engine'],row['revision'])
            if key in cls.contexts:
                raise ValueError('Duplicate original fresh-script context')
            cls.contexts[key] = row
        cls.pin = json.loads((SOURCE/'src/pin.json').read_text())
        compiler = shlex.split(os.environ.get('HOST_CC','cc'))
        version = subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links = ['-Wl,-dead_strip'] if sys.platform=='darwin' else ['-no-pie','-Wl,--gc-sections']
        host = [] if sys.platform=='darwin' else ['-DLINUX=1']
        temporary = tempfile.TemporaryDirectory(prefix='anybor-script-allocation-')
        cls.addClassCleanup(temporary.cleanup)
        work = Path(temporary.name)
        cls.executables = {}
        for engine,magic in sorted({(r['engine'],r['expected_magic']) for r in cls.contexts.values()}):
            root = SOURCE/'src/engines'/engine
            includes = [root,SOURCE/'src/port/libretro',SOURCE/'src/glue',root/'source',
                        *sorted(p for p in (root/'source').iterdir() if p.is_dir())]
            source = work/(engine+'-'+str(int(magic))+'.c')
            executable = source.with_suffix('')
            source.write_bytes(program(engine,magic,cls.fixture['variable_counts']).encode('utf8','surrogateescape'))
            compiled = subprocess.run(compiler+['-I'+str(p) for p in includes]+[
                '-std=gnu11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-error=sign-compare','-Wno-error=misleading-indentation',
                '-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter',
                *warnings,'-O1','-g','-DLIBRETRO=1','-DOBOR_ENGINE_BUILD='+engine,
                *host,'-fsigned-char','-ffunction-sections','-fdata-sections',
                '-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all',
                str(source),*links,'-lm','-o',str(executable)],capture_output=True,text=True,timeout=60)
            if compiled.stdout:sys.stderr.write(compiled.stdout)
            if compiled.stderr:sys.stderr.write(compiled.stderr)
            if compiled.returncode:raise RuntimeError('Native fresh-script compilation failed')
            cls.executables[engine,magic] = executable

    def affected(self,profile):
        bounds = self.fixture['coverage'].get(profile['engine'])
        return bounds is not None and bounds[0] <= int(profile.get('revision',profile['build'])) <= bounds[1]

    def check_context(self,row):
        observed = subprocess.check_output([
            str(self.executables[row['engine'],row['expected_magic']]),str(row['revision'])],
            timeout=15,text=True,env=sanitizer_environment())
        self.assertEqual(json.loads(observed),dict(status='PASS',cases=3*len(self.fixture['variable_counts'])))

    def test_every_affected_profile_has_own_native_contract(self):
        for profile in self.pin['profiles']:
            if self.affected(profile):
                self.assertIn((profile['engine'],int(profile.get('revision',profile['build']))),self.contexts)
        for row in self.contexts.values():
            self.assertIs(type(row['expected_magic']),bool)
            self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_header_sha256'],r'^[0-9a-f]{64}$')
            for name in ('alloc_script','ScriptVariant_Init'):
                self.assertRegex(row['source_fragments'][name],r'^[0-9a-f]{64}$')

    def test_each_registered_profile_preserves_fresh_script_state(self):
        for profile in self.pin['profiles']:
            if self.affected(profile):
                with self.subTest(profile=profile['build']):
                    self.check_context(self.contexts[profile['engine'],int(profile.get('revision',profile['build']))])

    def test_each_declared_original_context_preserves_fresh_script_state(self):
        for row in self.contexts.values():
            with self.subTest(engine=row['engine'],revision=row['revision']):self.check_context(row)


if __name__=='__main__':
    unittest.main()
