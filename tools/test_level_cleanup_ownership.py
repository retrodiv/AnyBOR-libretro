"""Check complete native level cleanup with each registered profile.

Script disposal is observed separately from ownership of level allocations.
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

from historical_level_cleanup import render_level_cleanup
from historical_text_release import render_text_release
from native_sanitizers import sanitizer_environment
from test_historical_player import function

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
CONTRACTS = Path(__file__).parent / 'fixtures/level-cleanup-layouts.json'


class LevelCleanupOwnershipTests(unittest.TestCase):
    def test_base_text_release_and_pointer_reset_per_profile(self):
        fixture = json.loads(CONTRACTS.with_name('text-release-contracts.json').read_text())
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        self.assertEqual(fixture['schema'], 1)
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
        warnings = ['-Wno-error=pragma-pack', '-Wno-error=deprecated-non-prototype',
                    '-Wno-error=single-bit-bitfield-constant-conversion'] if 'clang' in version.lower() else []
        host = [] if sys.platform == 'darwin' else ['-DLINUX=1']
        link = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        for row in fixture['models']:
            with self.subTest(engine=row['engine']), tempfile.TemporaryDirectory(prefix='native-text-release-') as folder:
                required = {int(p.get('revision', p['build'])) for p in pin['profiles']
                            if p['engine'] == row['engine']}
                self.assertTrue(required and required <= set(row['revisions']))
                self.assertEqual(row['revisions'], [s['revision'] for s in row['original_sources']])
                for original in row['original_sources']:
                    self.assertRegex(original['commit'], r'^[0-9a-f]{40}$')
                    self.assertRegex(original['free_level'], r'^[0-9a-f]{64}$')
                root = SOURCE / 'src/engines' / row['engine']
                source = (root / 'openbor.c').read_bytes().decode('utf8', 'surrogateescape')
                helpers = '\n'.join(function(source, name) for name in row['helper_names'])
                options = {k: row[k] for k in ('revisions', 'physical_fixed', 'slots', 'script_fields')}
                program = render_text_release(source=function(source, 'free_level'), helpers=helpers, **options)
                work = Path(folder); code = work / 'probe.c'; executable = work / 'probe'
                code.write_bytes(program.encode('utf8', 'surrogateescape'))
                includes = [root, SOURCE / 'src/port/libretro', SOURCE / 'src/glue', root / 'source',
                            *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
                compiled = subprocess.run(compiler + ['-I' + str(p) for p in includes] + [
                    '-std=gnu11', '-fgnu89-inline', '-Wall', '-Wextra', '-Werror',
                    '-Wno-error=deprecated-declarations', '-Wno-unused-variable', '-Wno-unused-function',
                    '-Wno-unused-parameter', '-O1', '-g', '-fsigned-char', '-fcommon',
                    '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=' + row['engine'],
                    '-ffunction-sections', '-fdata-sections',
                    '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
                    *host, *warnings, str(code), *link, '-lm', '-o', str(executable)],
                    timeout=45, capture_output=True, text=True)
                self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                observed = subprocess.run([str(executable)], env=sanitizer_environment(),
                    text=True, capture_output=True, timeout=15)
                self.assertEqual(observed.returncode, 0, observed.stdout + observed.stderr)
                self.assertEqual(json.loads(observed.stdout), dict(status='PASS',
                    contexts=len(row['revisions']), checks=5 * len(row['revisions'])))

    def test_owned_level_resources_are_released_once_per_profile(self):
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        layouts = json.loads(CONTRACTS.read_text())['engines']
        engines = {row['build'] for row in pin['engines']}
        self.assertEqual(len(layouts), len({row['engine'] for row in layouts}))
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
        warning_flags = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        link_flags = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        host_flags = [] if sys.platform == 'darwin' else ['-DLINUX=1']
        with tempfile.TemporaryDirectory(prefix='anybor-level-cleanup-') as folder:
            work = Path(folder)
            for layout in layouts:
                engine = layout['engine']
                with self.subTest(engine=engine):
                    self.assertIn(engine, engines)
                    revisions = sorted({int(row.get('revision', row['build']))
                                        for row in pin['profiles'] if row['engine'] == engine})
                    self.assertTrue(revisions)
                    root = SOURCE / 'src/engines' / engine
                    source = (root / 'openbor.c').read_bytes().decode('utf-8', 'surrogateescape')
                    stream_options={}
                    facts = json.loads(CONTRACTS.with_name('profile-level-table-cleanup.json').read_text())
                    if engine == '3741':
                        revisions = sorted(set(revisions) | set(facts['boundary_controls']))
                        own = {row['revision']: row for row in facts['sources']}
                        self.assertTrue(set(revisions) <= set(own))
                        stream_options['release_extents'] = {
                            field: [own[r][fact] if own[r]['legacy_fixed_tables'] else 1
                                    for r in revisions]
                            for field, fact in (('palettes', 'palette_extent'),
                                                ('blendings', 'palette_extent'),
                                                ('spawnpoints', 'spawn_extent'))
                        }
                    pixel=(root/'source/gamelib/pixelformat.c').read_text()
                    if 'obor_profile_blend_count('in pixel:
                        stream_options['profile_helpers']=function(pixel,'obor_profile_blend_count')
                    if 'stream_release_before'in layout:
                        script=(root/'openborscript.c').read_text()
                        stream_options['stream_clear']=function(script,'obor_filestream_level_clear')
                    program = render_level_cleanup(function(source, 'free_level'),
                        revision=revisions[0], revisions=revisions,
                        **{key: value for key, value in layout.items() if key != 'engine'},
                        **stream_options)
                    code = work / (engine + '.c')
                    code.write_bytes(program.encode('utf-8', 'surrogateescape'))
                    executable = code.with_suffix('')
                    includes = [root, SOURCE / 'src/port/libretro', SOURCE / 'src/glue',
                                root / 'source', *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
                    compiled = subprocess.run(compiler + ['-I' + str(p) for p in includes] + [
                        '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-Wno-error=deprecated-declarations', '-Wno-unused-variable',
                        '-Wno-unused-function', '-Wno-unused-parameter',
                        '-O1', '-g', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=' + engine,
                        '-fsigned-char', '-ffunction-sections', '-fdata-sections',
                        '-fsanitize=address,undefined,pointer-overflow',
                        '-fno-sanitize-recover=all', *host_flags, *warning_flags,
                        str(code), *link_flags, '-lm', '-o', str(executable)],
                        timeout=45, capture_output=True, text=True)
                    self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                    observed = subprocess.check_output([str(executable)],
                        env=sanitizer_environment(), text=True, timeout=15)
                    self.assertEqual(json.loads(observed), {'status': 'PASS', 'cases': 6 * len(revisions)})


if __name__ == '__main__':
    unittest.main()
