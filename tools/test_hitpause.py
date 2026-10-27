"""Compare affected profiles with source-declared hit-pause contracts.

Each physical layout and state view is compiled once. Every registered affected
profile and declared original context runs separately with independent values.
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

from historical_hitpause import render_hitpause
from native_sanitizers import sanitizer_environment
from test_historical_player import function

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURE=Path(__file__).parent/'fixtures/hitpause-contracts.json'


def program(engine,layout,mode,cases):
    if (not isinstance(layout,dict) or set(layout)!=
            {'legacy_field','timer_field','selector'} or mode not in ('frame','timer')):
        raise ValueError('Explicit native pause layout and source selector required')
    from re import finditer
    text=(SOURCE/'src/engines'/engine/'openbor.c').read_bytes().decode('utf-8','surrogateescape')
    caller=function(text,'do_attack')
    matches=list(finditer(layout['selector'],caller))
    if len(matches)!=1:
        raise ValueError('Exactly one native hit-pause statement range required')
    code=render_hitpause(matches[0][0],revision=int(engine),
        legacy_field=layout['legacy_field'] if mode=='frame' else None,
        timer_field=layout['timer_field'] if mode=='timer' else None,cases=cases)
    marker='int main(void){'
    if code.count(marker)!=1:
        raise ValueError('One authored native pause entry required')
    return code.replace(marker,'''int main(int argc,char **argv){
 assert(argc==2);char *end=NULL;unsigned long revision=strtoul(argv[1],&end,10);
 assert(end && !*end && revision>0 && revision<=UINT32_MAX);obor_profile_build=(uint32_t)revision;
''')


class HitpauseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads(FIXTURE.read_text());cls.layouts=cls.fixture['layouts']
        cls.contexts={}
        for row in cls.fixture['contexts']:
            key=(row['engine'],row['revision'])
            if key in cls.contexts:
                raise ValueError('Duplicate original pause context')
            cls.contexts[key]=row
        cls.pin=json.loads((SOURCE/'src/pin.json').read_text())
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links=['-Wl,-dead_strip'] if sys.platform=='darwin' else ['-no-pie','-Wl,--gc-sections']
        host=[] if sys.platform=='darwin' else ['-DLINUX=1']
        temporary=tempfile.TemporaryDirectory(prefix='anybor-hitpause-')
        cls.addClassCleanup(temporary.cleanup);work=Path(temporary.name);cls.executables={}
        groups=sorted({(row['engine'],row['mode']) for row in cls.contexts.values()})
        for engine,mode in groups:
            root=SOURCE/'src/engines'/engine
            includes=[root,SOURCE/'src/port/libretro',SOURCE/'src/glue',root/'source',
                      *sorted(p for p in (root/'source').iterdir() if p.is_dir())]
            source=work/(engine+'-'+mode+'.c');executable=source.with_suffix('')
            source.write_bytes(program(engine,cls.layouts[engine],mode,
                cls.fixture['cases'][mode]).encode('utf-8','surrogateescape'))
            compiled=subprocess.run(compiler+['-I'+str(p) for p in includes]+[
                '-std=gnu11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-error=sign-compare','-Wno-error=misleading-indentation',
                '-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter',
                *warnings,'-O1','-g','-DLIBRETRO=1','-DOBOR_ENGINE_BUILD='+engine,
                *host,'-fsigned-char','-ffunction-sections','-fdata-sections',
                '-fsanitize=address,undefined,pointer-overflow','-fno-sanitize-recover=all',
                str(source),*links,'-lm','-o',str(executable)],capture_output=True,text=True,timeout=60)
            if compiled.stdout:sys.stderr.write(compiled.stdout)
            if compiled.stderr:sys.stderr.write(compiled.stderr)
            if compiled.returncode:raise RuntimeError('Native pause compilation failed')
            cls.executables[engine,mode]=executable

    def check_context(self,row):
        observed=subprocess.check_output([str(self.executables[row['engine'],row['mode']]),
            str(row['revision'])],timeout=15,text=True,env=sanitizer_environment())
        self.assertEqual(json.loads(observed),dict(status='PASS',cases=len(self.fixture['cases'][row['mode']])))

    def test_every_affected_profile_has_an_original_contract(self):
        for profile in self.pin['profiles']:
            if profile['engine'] in self.layouts:
                self.assertIn((profile['engine'],int(profile.get('revision',profile['build']))),self.contexts)
        for row in self.contexts.values():
            self.assertIn(row['engine'],self.layouts)
            self.assertIn(row['mode'],('frame','timer'))
            self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_header_sha256'],r'^[0-9a-f]{64}$')
            self.assertRegex(row['source_fragment_sha256'],r'^[0-9a-f]{64}$')

    def test_each_registered_profile_preserves_pause_values(self):
        for profile in self.pin['profiles']:
            if profile['engine'] in self.layouts:
                key=(profile['engine'],int(profile.get('revision',profile['build'])))
                with self.subTest(profile=profile['build']):self.check_context(self.contexts[key])

    def test_each_declared_original_context_preserves_pause_values(self):
        for row in self.contexts.values():
            with self.subTest(engine=row['engine'],revision=row['revision']):self.check_context(row)


if __name__=='__main__':
    unittest.main()
