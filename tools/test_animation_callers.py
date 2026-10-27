"""Compare complete historical animation callers per affected profile.

Each physical layout and expected behavior is compiled once. Every registered
affected profile and declared original context executes separately. Target
selection and frame services remain explicit observations.
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

from historical_animation_transitions import render_animation_transition
from historical_idle_animation import render_idle_animation
from native_sanitizers import sanitizer_environment
from test_historical_player import function

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent/'fixtures/animation-caller-contracts.json'


def program(engine, family, options):
    if family not in ('transition', 'idle'):
        raise ValueError('Explicit complete animation caller family required')
    text = (SOURCE/'src/engines'/engine/'openbor.c').read_bytes().decode('utf8', 'surrogateescape')
    transition = function(text, 'ent_set_anim')
    if family == 'transition':
        code = render_animation_transition(transition, **options)
    else:
        idle = function(text, 'common_idle_anim')
        if 'common_anim_series(' in idle:
            idle = function(text, 'common_anim_series') + idle
        code = render_idle_animation(dict(ent_set_anim=transition, common_idle_anim=idle), **options)
    marker = 'int main(void){'
    if code.count(marker) != 1:
        raise ValueError('One bounded native caller entry point required')
    return code.replace(marker, '''int main(int argc,char **argv){
 assert(argc==2);char *end=NULL;unsigned long revision=strtoul(argv[1],&end,10);
 assert(end && !*end && revision>0 && revision<=UINT32_MAX);obor_profile_build=(uint32_t)revision;
''')


class AnimationCallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_contract_fixture(FIXTURE)
        cls.contexts = {}
        for row in cls.fixture['contexts']:
            key = (row['engine'], row['revision'])
            if key in cls.contexts:
                raise ValueError('Duplicate original animation caller context')
            cls.contexts[key] = row
        cls.pin = json.loads((SOURCE/'src/pin.json').read_text())
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        version = subprocess.check_output(compiler+['--version'], text=True, timeout=10)
        warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        host = [] if sys.platform == 'darwin' else ['-DLINUX=1']
        temporary = tempfile.TemporaryDirectory(prefix='anybor-animation-callers-')
        cls.addClassCleanup(temporary.cleanup)
        work = Path(temporary.name)
        cls.executables = {}
        groups = {(row['engine'], family, row[family]) for row in cls.contexts.values()
                  for family in ('transition', 'idle')}
        for engine, family, mode in sorted(groups):
            root = SOURCE/'src/engines'/engine
            includes = [root, SOURCE/'src/port/libretro', SOURCE/'src/glue', root/'source',
                        *sorted(p for p in (root/'source').iterdir() if p.is_dir())]
            source = work/(engine+'-'+family+'-'+mode+'.c')
            executable = source.with_suffix('')
            options = cls.fixture['options'][family][mode] | cls.fixture['layouts'][engine]
            options['revision'] = int(engine)
            if mode.startswith('frame'):
                options['legacy_field'] = cls.fixture['legacy_fields'][engine]
            source.write_bytes(program(engine, family, options).encode('utf8', 'surrogateescape'))
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
                raise RuntimeError('Native animation caller compilation failed')
            cls.executables[engine, family, mode] = executable

    def affected(self, profile):
        engine = profile['engine']
        bounds = self.fixture['coverage'].get(engine)
        if bounds is None:
            return False
        revision = int(profile.get('revision', profile['build']))
        return bounds[0] <= revision <= bounds[1]

    def check_context(self, row):
        for family in ('transition', 'idle'):
            mode = row[family]
            observed = subprocess.check_output([
                str(self.executables[row['engine'], family, mode]), str(row['revision'])],
                timeout=15, text=True, env=sanitizer_environment())
            self.assertEqual(json.loads(observed), dict(status='PASS',
                cases=len(self.fixture['options'][family][mode]['cases'])))

    def test_every_affected_profile_has_own_source_contracts(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if self.affected(profile):
                self.assertIn((profile['engine'], int(profile.get('revision', profile['build']))),
                              self.contexts)
        for row in self.contexts.values():
            self.assertRegex(row['source_commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_header_sha256'], r'^[0-9a-f]{64}$')
            for family in ('transition', 'idle'):
                self.assertIn(row[family], self.fixture['options'][family])
                self.assertRegex(row['source_fragments'][family], r'^[0-9a-f]{64}$')

    def test_each_registered_profile_preserves_caller_behavior(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if self.affected(profile):
                key = (profile['engine'], int(profile.get('revision', profile['build'])))
                with self.subTest(profile=profile['build']):
                    self.check_context(self.contexts[key])

    def test_each_declared_original_context_preserves_caller_behavior(self):
        for row in self.contexts.values():
            with self.subTest(engine=row['engine'], revision=row['revision']):
                self.check_context(row)


if __name__ == '__main__':
    unittest.main()
