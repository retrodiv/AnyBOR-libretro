"""Compare complete frame event callers with each profile's source contract.

Physical records and independent expected states are compiled in groups; each
registered affected profile and declared original context executes separately.
Script, spawning and damage implementations remain separate acceptance gates.
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

from historical_frame_events import render_frame_events
from native_sanitizers import sanitizer_environment
from test_historical_player import function

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent/'fixtures/frame-event-contracts.json'


def program(engine, layout, mode, cases):
    if (not isinstance(layout, dict) or set(layout) != {'frame_field', 'timer_field', 'helpers'} or
            not isinstance(mode, str) or not re.fullmatch(r'(?:frame|timer)_[a-z_]+', mode) or
            not isinstance(layout['helpers'], list) or len(layout['helpers']) > 4 or
            any(not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_]\w{0,63}', name)
                for name in layout['helpers'])):
        raise ValueError('Explicit native frame layout, mode and complete helpers required')
    text = (SOURCE/'src/engines'/engine/'openbor.c').read_bytes().decode('utf8', 'surrogateescape')
    code = render_frame_events(function(text, 'update_frame'), revision=int(engine),
        legacy_field=layout['frame_field'] if mode.startswith('frame_') else layout['timer_field'],
        helpers=[function(text, name) for name in layout['helpers']], cases=cases)
    marker = 'int main(void){'
    if code.count(marker) != 1:
        raise ValueError('One bounded native frame entry point required')
    return code.replace(marker, '''int main(int argc,char **argv){
 assert(argc==2);char *end=NULL;unsigned long revision=strtoul(argv[1],&end,10);
 assert(end && !*end && revision>0 && revision<=UINT32_MAX);obor_profile_build=(uint32_t)revision;
''')


class FrameEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text())
        cls.contexts = {}
        for row in cls.fixture['contexts']:
            key = (row['engine'], row['revision'])
            if key in cls.contexts:
                raise ValueError('Duplicate original frame context')
            cls.contexts[key] = row
        cls.pin = json.loads((SOURCE/'src/pin.json').read_text())
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        version = subprocess.check_output(compiler+['--version'], text=True, timeout=10)
        warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        host = [] if sys.platform == 'darwin' else ['-DLINUX=1']
        temporary = tempfile.TemporaryDirectory(prefix='anybor-frame-events-')
        cls.addClassCleanup(temporary.cleanup)
        work = Path(temporary.name)
        cls.executables = {}
        for engine, mode in sorted({(r['engine'], r['mode']) for r in cls.contexts.values()}):
            root = SOURCE/'src/engines'/engine
            includes = [root, SOURCE/'src/port/libretro', SOURCE/'src/glue', root/'source',
                        *sorted(p for p in (root/'source').iterdir() if p.is_dir())]
            source = work/(engine+'-'+mode+'.c')
            executable = source.with_suffix('')
            source.write_bytes(program(engine, cls.fixture['layouts'][engine], mode,
                cls.fixture['cases'][mode]).encode('utf8', 'surrogateescape'))
            compiled = subprocess.run(compiler+['-I'+str(p) for p in includes]+[
                '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-error=sign-compare', '-Wno-error=misleading-indentation',
                '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-parameter',
                *warnings, '-O1', '-g', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD='+engine,
                *host, '-fsigned-char', '-ffunction-sections', '-fdata-sections',
                '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
                str(source), *links, '-lm', '-o', str(executable)],
                capture_output=True, text=True, timeout=60)
            if compiled.stdout:
                sys.stderr.write(compiled.stdout)
            if compiled.stderr:
                sys.stderr.write(compiled.stderr)
            if compiled.returncode:
                raise RuntimeError('Native frame event compilation failed')
            cls.executables[engine, mode] = executable

    def affected(self, profile):
        bounds = self.fixture['coverage'].get(profile['engine'])
        return bounds is not None and bounds[0] <= int(profile.get('revision', profile['build'])) <= bounds[1]

    def check_context(self, row):
        observed = subprocess.check_output([
            str(self.executables[row['engine'], row['mode']]), str(row['revision'])],
            timeout=15, text=True, env=sanitizer_environment())
        self.assertEqual(json.loads(observed), dict(status='PASS',
            cases=len(self.fixture['cases'][row['mode']])))

    def test_every_affected_profile_has_own_source_contract(self):
        for profile in self.pin['profiles']:
            if self.affected(profile):
                self.assertIn((profile['engine'], int(profile.get('revision', profile['build']))), self.contexts)
        for row in self.contexts.values():
            self.assertRegex(row['source_commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_header_sha256'], r'^[0-9a-f]{64}$')
            self.assertRegex(row['source_fragment_sha256'], r'^[0-9a-f]{64}$')
            self.assertIn(row['mode'], self.fixture['cases'])
            self.assertIn(row['engine'], self.fixture['layouts'])

    def test_each_registered_profile_preserves_frame_events(self):
        for profile in self.pin['profiles']:
            if self.affected(profile):
                with self.subTest(profile=profile['build']):
                    self.check_context(self.contexts[profile['engine'], int(profile.get('revision', profile['build']))])

    def test_each_declared_original_context_preserves_frame_events(self):
        for row in self.contexts.values():
            with self.subTest(engine=row['engine'], revision=row['revision']):
                self.check_context(row)


if __name__ == '__main__':
    unittest.main()
