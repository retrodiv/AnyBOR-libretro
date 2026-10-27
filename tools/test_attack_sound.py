"""Compare native attack sound defaults and commands for each profile.

Sample loading is observed; audio decoding and complete model lifecycle are
separate contracts. Each native record/expectation view compiles once.
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

from historical_attack_sound import render_attack_sound
from native_sanitizers import sanitizer_environment
from test_historical_player import function

SOURCE=Path(os.environ.get('OBOR_TEST_SOURCE',Path(__file__).resolve().parents[1]))
FIXTURE=Path(__file__).parent/'fixtures/attack-sound-contracts.json'


def source_parts(text,header=''):
    parts={'parse_args':function(text,'ParseArgs')}
    patterns={
        'argument_macro':r'(?m)^[ \t]*#define[ \t]+GET_ARG\(z\)[^\n]*',
        'attack_default':r'(?m)^[ \t]*attack\s*=\s*emptyattack;[ \t]*\r?\n[ \t]*attack\.hitsound\s*=[^;\n]+;',
        'hitfx_case':r'(?ms)^[ \t]*case CMD_MODEL_HITFX:.*?(?=^[ \t]*case CMD_MODEL_HITFLASH:)',
    }
    for name,pattern in patterns.items():
        matches=re.findall(pattern,text+'\n'+header if name=='argument_macro' else text)
        if len(matches)!=1:raise ValueError('One complete native sound fragment required: '+name)
        parts[name]=matches[0]
    companions={}
    for name,command,next_command in [('diesound_case','DIESOUND','ICON'),
            ('sound_case','SOUND','HITFX'),('blockfx_case','BLOCKFX','FASTATTACK')]:
        matches=re.findall(r'(?ms)^[ \t]*case CMD_MODEL_'+command+
            r':.*?(?=^[ \t]*case CMD_MODEL_'+next_command+r':)',text)
        if len(matches)>1:raise ValueError('Ambiguous native sample command: '+name)
        if matches:companions[name]=matches[0]
    if len(companions) not in (0,3):raise ValueError('Complete native companion command set required')
    parts.update(companions)
    return parts


def program(engine,cases,sample_log=0):
    root=SOURCE/'src/engines'/engine
    text=(root/'openbor.c').read_bytes().decode('utf8','surrogateescape')
    header=(root/'openbor.h').read_bytes().decode('utf8','surrogateescape')
    code=render_attack_sound(source_parts(text,header),revision=int(engine),cases=cases,sample_log=sample_log)
    marker='int main(void){'
    if code.count(marker)!=1:raise ValueError('One bounded native sound entry required')
    return code.replace(marker,'''int main(int argc,char **argv){
 assert(argc==2);char *end=NULL;unsigned long revision=strtoul(argv[1],&end,10);
 assert(end && !*end && revision>0 && revision<=UINT32_MAX);obor_profile_build=(uint32_t)revision;
''')


class AttackSoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads(FIXTURE.read_text());cls.contexts={}
        for row in cls.fixture['contexts']:
            key=(row['engine'],row['revision'])
            if key in cls.contexts:raise ValueError('Duplicate original attack sound context')
            cls.contexts[key]=row
        cls.pin=json.loads((SOURCE/'src/pin.json').read_text())
        compiler=shlex.split(os.environ.get('HOST_CC','cc'))
        version=subprocess.check_output(compiler+['--version'],text=True,timeout=10)
        warnings=['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links=['-Wl,-dead_strip'] if sys.platform=='darwin' else ['-no-pie','-Wl,--gc-sections']
        host=[] if sys.platform=='darwin' else ['-DLINUX=1']
        temporary=tempfile.TemporaryDirectory(prefix='anybor-attack-sound-')
        cls.addClassCleanup(temporary.cleanup);work=Path(temporary.name);cls.executables={}
        for engine,mode,sample_log in sorted({(r['engine'],r['mode'],r['sample_log']) for r in cls.contexts.values()}):
            root=SOURCE/'src/engines'/engine
            includes=[root,SOURCE/'src/port/libretro',SOURCE/'src/glue',root/'source',
                      *sorted(p for p in (root/'source').iterdir() if p.is_dir())]
            source=work/(engine+'-'+mode+'-'+str(sample_log)+'.c');executable=source.with_suffix('')
            source.write_bytes(program(engine,cls.fixture['cases'][mode],sample_log).encode('utf8','surrogateescape'))
            compiled=subprocess.run(compiler+['-I'+str(p) for p in includes]+[
                '-std=gnu11','-Wall','-Wextra','-Werror','-Wno-error=deprecated-declarations',
                '-Wno-error=sign-compare','-Wno-error=misleading-indentation',
                '-Wno-error=implicit-fallthrough','-Wno-unused-function','-Wno-unused-variable',
                '-Wno-unused-parameter',*warnings,'-O1','-g','-DLIBRETRO=1',
                '-DOBOR_ENGINE_BUILD='+engine,*host,'-fsigned-char',
                '-ffunction-sections','-fdata-sections','-fsanitize=address,undefined,pointer-overflow',
                '-fno-sanitize-recover=all',str(source),*links,'-lm','-o',str(executable)],
                capture_output=True,text=True,timeout=60)
            if compiled.stdout:sys.stderr.write(compiled.stdout)
            if compiled.stderr:sys.stderr.write(compiled.stderr)
            if compiled.returncode:raise RuntimeError('Native attack sound compilation failed')
            cls.executables[engine,mode,sample_log]=executable

    def affected(self,profile):
        bounds=self.fixture['coverage'].get(profile['engine'])
        return bounds is not None and bounds[0]<=int(profile.get('revision',profile['build']))<=bounds[1]

    def check_context(self,row):
        observed=subprocess.check_output([str(self.executables[row['engine'],row['mode'],row['sample_log']]),
            str(row['revision'])],timeout=15,text=True,env=sanitizer_environment())
        self.assertEqual(json.loads(observed),dict(status='PASS',cases=len(self.fixture['cases'][row['mode']])))

    def test_every_affected_profile_has_own_native_contract(self):
        for profile in self.pin['profiles']:
            if self.affected(profile):
                self.assertIn((profile['engine'],int(profile.get('revision',profile['build']))),self.contexts)
        for row in self.contexts.values():
            self.assertIn(row['mode'],self.fixture['cases'])
            self.assertRegex(row['source_commit'],r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_header_sha256'],r'^[0-9a-f]{64}$')
            self.assertIn(row['sample_log'],(0,1))
            for name in ('parse_args','argument_macro','attack_default','hitfx_case','diesound_case','sound_case','blockfx_case'):
                self.assertRegex(row['source_fragments'][name],r'^[0-9a-f]{64}$')

    def test_each_registered_profile_preserves_attack_sound_loading(self):
        for profile in self.pin['profiles']:
            if self.affected(profile):
                with self.subTest(profile=profile['build']):
                    self.check_context(self.contexts[profile['engine'],int(profile.get('revision',profile['build']))])

    def test_each_declared_original_context_preserves_attack_sound_loading(self):
        for row in self.contexts.values():
            with self.subTest(engine=row['engine'],revision=row['revision']):self.check_context(row)


if __name__=='__main__':
    unittest.main()
