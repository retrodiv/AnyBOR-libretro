"""Compare queued image pixels with each profile's own source.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from historical_sprite_queue import render_sprite_queue
from historical_sprite_map_queue import render_sprite_map_queue
from native_sanitizers import sanitizer_environment
from test_color_blends import compile_checked

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / 'fixtures/sprite-queue-contracts.json'
MAP_FIXTURE = Path(__file__).parent / 'fixtures/sprite-map-queue-contracts.json'
_SHARED_UNITS = {}
_SHARED_TEMP = None


def program(engine, cases, *, native_modes, mapped=False, fixture=None):
    if fixture is None:
        fixture = load_contract_fixture(MAP_FIXTURE if mapped else FIXTURE)
    context = fixture['engines'][engine]
    render = render_sprite_map_queue if mapped else render_sprite_queue
    code = render(queue_source=str(SOURCE / 'src/engines' / engine / 'source/gamelib/spriteq.c'),
        method_api=context['method_api'], expected_capacity=context['expected_capacity'],
        revision=int(engine), clipping=context['clipping'],
        resource_hooks=context['resource_hooks'], assert_refusal=context['assert_refusal'],
        channels=context['channels'], tint=context['tint'], native_modes=native_modes,
        palettes=fixture['palettes'], cases=cases)
    marker = 'int main(void){'
    if code.count(marker) != 1:
        raise ValueError('One sprite queue entry point required')
    return code.replace(marker, '''int main(int argc,char **argv){
 assert(argc==2);char *end=NULL;unsigned long revision=strtoul(argv[1],&end,10);
 assert(end && !*end && revision>0 && revision<=UINT32_MAX);obor_profile_build=(uint32_t)revision;
''')


def compiled_graphics(engine, compiler, flags, root):
    """Reuse identical graphics objects within this immutable-source test run."""
    global _SHARED_TEMP
    key = (engine, tuple(compiler), tuple(flags), str(root))
    if key in _SHARED_UNITS:
        retained = _SHARED_UNITS[key]
        if isinstance(retained, Exception):
            raise RuntimeError('Graphics compilation already failed; inspect the first failure before retrying') from retained
        return retained
    if _SHARED_TEMP is None:
        _SHARED_TEMP = tempfile.TemporaryDirectory(prefix='anybor-queue-graphics-')
        temporary = _SHARED_TEMP
        def cleanup():
            global _SHARED_TEMP
            temporary.cleanup()
            if _SHARED_TEMP is temporary:
                _SHARED_TEMP = None
            _SHARED_UNITS.clear()
        unittest.addModuleCleanup(cleanup)
    work = Path(_SHARED_TEMP.name) / hashlib.sha256(repr(key).encode()).hexdigest()
    work.mkdir()
    provider = work / 'pixelformat.o'
    try:
        compile_checked(compiler + flags + ['-O1', '-c', str(root / 'source/gamelib/pixelformat.c'),
                                           '-o', str(provider)])
        drawing_units = []
        for name in ('transform', 'spritex8p16', 'spritex8p32', 'screen', 'screen16', 'screen32', 'draw', 'draw16', 'draw32'):
            unit = work / (name + '.o')
            compile_checked(compiler + flags + ['-finstrument-functions', '-c',
                str(root / 'source/gamelib' / (name + '.c')), '-o', str(unit)])
            drawing_units.append(str(unit))
    except Exception as error:
        _SHARED_UNITS[key] = error
        raise
    _SHARED_UNITS[key] = str(provider), tuple(drawing_units)
    return _SHARED_UNITS[key]


class SpriteQueueTests(unittest.TestCase):
    MAPPED = False
    FIXTURE_FILE = FIXTURE

    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(cls.FIXTURE_FILE.read_text())
        def release_inputs():
            cls.fixture = cls.contexts = cls.executables = None
        cls.addClassCleanup(release_inputs)
        cls.pin = json.loads((SOURCE / 'src/pin.json').read_text())
        cls.contexts = {}
        for row in cls.fixture['contexts']:
            key = row['engine'], row['revision']
            if key in cls.contexts:
                raise ValueError('Duplicate sprite queue context')
            cls.contexts[key] = row
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
        warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        host = [] if sys.platform == 'darwin' else ['-DLINUX=1']
        temporary = tempfile.TemporaryDirectory(prefix='anybor-sprite-queue-')
        cls.addClassCleanup(temporary.cleanup)
        work = Path(temporary.name)
        cls.executables = {}
        for engine in sorted({row['engine'] for row in cls.contexts.values()}):
            root = SOURCE / 'src/engines' / engine
            includes = [root / 'source/gamelib', root / 'source', root,
                        SOURCE / 'src/glue', SOURCE / 'src/port/libretro']
            flags = ['-I' + str(p) for p in includes] + [
                '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-error=misleading-indentation', '-Wno-error=sign-compare',
                '-Wno-unused-variable', '-Wno-unused-function', '-Wno-unused-parameter',
                '-Wno-implicit-fallthrough', '-Wno-error=unused-value', *warnings,
                '-O0', '-g', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=' + engine, *host,
                '-fsigned-char', '-ffunction-sections', '-fcommon', '-fdata-sections',
                '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all']
            provider, drawing_units = compiled_graphics(engine, compiler, flags, root)
            names = sorted({row['contract'] for row in cls.contexts.values() if row['engine'] == engine})
            for contract in names:
                source = work / (engine + '-' + contract + '.c')
                executable = source.with_suffix('')
                source.write_text(program(engine, cls.fixture['contracts'][contract],
                    native_modes=cls.fixture['reference_options'][contract]['native_modes'],
                    mapped=cls.MAPPED, fixture=cls.fixture))
                compile_checked(compiler + flags + ['-finstrument-functions', str(source), str(provider),
                    *drawing_units, *links, '-lm', '-o', str(executable)])
                cls.executables[engine, contract] = executable

    def affected(self, profile):
        bounds = self.fixture['coverage'].get(profile['engine'])
        return bounds is not None and bounds[0] <= int(profile.get('revision', profile['build'])) <= bounds[1]

    def check_context(self, row):
        observed = json.loads(subprocess.check_output([
            str(self.executables[row['engine'], row['contract']]), str(row['revision'])],
            text=True, timeout=15, env=sanitizer_environment()))
        self.assertEqual(observed, dict(status='PASS', cases=len(self.fixture['contracts'][row['contract']])))

    def test_every_affected_profile_has_own_source_contract(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if self.affected(profile):
                self.assertIn((profile['engine'], int(profile.get('revision', profile['build']))), self.contexts)
        for row in self.contexts.values():
            self.assertIn(row['contract'], self.fixture['contracts'])
            self.assertRegex(row['source_commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(set(row['source_units']), {'sprite', 'spriteq', 'transform', 'spritex8p16', 'spritex8p32', 'screen', 'screen16', 'screen32', 'draw', 'draw16', 'draw32', 'pixelformat'})
            for digest in row['source_units'].values():
                self.assertRegex(digest, r'^[0-9a-f]{40}$')

    def test_each_registered_profile_preserves_sprite_queue_pixels(self):
        for profile in contract_profiles(self.fixture, self.pin['profiles']):
            if self.affected(profile):
                with self.subTest(profile=profile['build']):
                    self.check_context(self.contexts[profile['engine'], int(profile.get('revision', profile['build']))])

    def test_each_original_context_preserves_sprite_queue_pixels(self):
        for row in self.contexts.values():
            with self.subTest(engine=row['engine'], revision=row['revision']):
                self.check_context(row)


class SpriteMapQueueTests(SpriteQueueTests):
    MAPPED = True
    FIXTURE_FILE = MAP_FIXTURE


if __name__ == '__main__':
    unittest.main()
