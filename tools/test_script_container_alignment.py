"""Check script slot access and ownership at declared record alignments.

Each physical tree is compiled once and each registered profile runs fresh.
Script callbacks are observed; linked actor/script units have separate checks.
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

from historical_script_containers import NAMES, render_script_containers
from native_sanitizers import sanitizer_environment
from test_historical_player import function

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
LAYOUTS=Path(__file__).parent/'fixtures/script-container-layouts.json'


def program(engine,layout):
    if (not isinstance(layout,dict) or layout.get('engine')!=engine or
            not {'pointer_container','members','member_count_definition'}<=set(layout)):
        raise ValueError('One explicit native engine container layout required')
    source=(SOURCE/'src/engines'/engine/'openbor.c').read_bytes().decode('utf-8','surrogateescape')
    parts={name:function(source,name) for name in NAMES}
    helper=layout.get('offset_function')
    support=function(source,helper) if helper else ''
    orders=[dict(revision=row['source_revision'],members=row['native_member_order'])
            for row in layout.get('storage_extensions',[])]
    code=render_script_containers(parts,revision=int(engine),
        pointer_container=layout['pointer_container'],members=layout['members'],
        member_count_definition=layout['member_count_definition'],
        offsets=[0,1],null_arguments=True,member_orders=orders,support=support)
    marker='int main(void){'
    if code.count(marker)!=1:
        raise ValueError('One authored script container entry required')
    return code.replace(marker,'''int main(int argc,char **argv){
 assert(argc==2);obor_profile_build=(uint32_t)atoi(argv[1]);assert(obor_profile_build>0);
''')


class ScriptContainerAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture=json.loads(LAYOUTS.read_text());cls.layouts={row['engine']:row for row in fixture['engines']}
        cls.contexts=fixture['contexts']
        if len(cls.layouts)!=len(fixture['engines']):
            raise ValueError('Duplicate native container layout')
        cls.pin=json.loads((SOURCE/'src/pin.json').read_text())
        temporary=tempfile.TemporaryDirectory(prefix='anybor-script-containers-')
        cls.addClassCleanup(temporary.cleanup);work=Path(temporary.name)
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links=['-Wl,-dead_strip'] if sys.platform=='darwin' else ['-no-pie','-Wl,--gc-sections']
        host_flags=[] if sys.platform=='darwin' else ['-DLINUX=1']
        cls.executables={}
        for engine,layout in cls.layouts.items():
            root=SOURCE/'src/engines'/engine
            includes=[root,SOURCE/'src/port/libretro',SOURCE/'src/glue',root/'source',
                      *sorted(p for p in (root/'source').iterdir() if p.is_dir())]
            code=work/(engine+'.c');exe=code.with_suffix('')
            code.write_bytes(program(engine,layout).encode('utf-8','surrogateescape'))
            result=subprocess.run(compiler+['-I'+str(p) for p in includes]+[
                '-std=gnu11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-error=sign-compare','-Wno-error=misleading-indentation',
                '-Wno-unused-variable','-Wno-unused-function','-Wno-unused-parameter',
                *warnings,'-O1','-g','-DLIBRETRO=1','-DOBOR_ENGINE_BUILD='+engine,
                *host_flags,'-fsigned-char','-ffunction-sections','-fdata-sections',
                '-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all',
                str(code),*links,'-lm','-o',str(exe)],capture_output=True,text=True,timeout=60)
            if result.stdout:sys.stderr.write(result.stdout)
            if result.stderr:sys.stderr.write(result.stderr)
            if result.returncode:raise RuntimeError('Native script container compilation failed')
            cls.executables[engine]=exe

    def test_all_engines_and_profiles_have_source_layouts(self):
        self.assertEqual(set(self.layouts),{row['build'] for row in self.pin['engines']})
        for profile in self.pin['profiles']:
            self.assertIn(profile['engine'],self.layouts)
        for row in self.layouts.values():
            self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_header_sha256'],r'^[0-9a-f]{64}$')
            self.assertEqual(set(row['source_functions_sha256']),set(NAMES))
        keys={(row['engine'],row['revision']) for row in self.contexts}
        self.assertEqual(len(keys),len(self.contexts))
        for row in self.contexts:
            self.assertIn(row['engine'],self.layouts)
            self.assertIs(type(row['revision']),int)
            self.assertGreater(row['revision'],0)
            self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')

    def test_each_registered_profile_preserves_slots_callbacks_and_cleanup(self):
        for profile in self.pin['profiles']:
            revision=int(profile.get('revision',profile['build']))
            with self.subTest(profile=profile['build'],revision=revision):
                observed=subprocess.check_output([str(self.executables[profile['engine']]),str(revision)],
                    timeout=15,text=True,env=sanitizer_environment())
                self.assertEqual(json.loads(observed),dict(status='PASS',cases=6))

    def test_each_declared_source_context_has_stable_slot_access(self):
        for row in self.contexts:
            with self.subTest(engine=row['engine'],revision=row['revision']):
                observed=subprocess.check_output([str(self.executables[row['engine']]),str(row['revision'])],
                    timeout=15,text=True,env=sanitizer_environment())
                self.assertEqual(json.loads(observed),dict(status='PASS',cases=6))


if __name__=='__main__':
    unittest.main()
