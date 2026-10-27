"""Compare native movement/grab caller functions against own-source profile oracles.

Compile once per physical source/expectation group and run each revision fresh.
Geometry, eligibility, random, animation and script implementations remain separate.
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

from historical_ai_movement import FUNCTIONS, render_ai_movement
from native_sanitizers import sanitizer_environment
from test_historical_player import function

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
CONTRACT_PATH = Path(__file__).parent / 'fixtures/profile-ai-movement-contracts.json'


def source_parts(engine):
    source = (SOURCE / 'src/engines' / engine / 'openbor.c').read_bytes().decode(
        'utf-8', 'surrogateescape')
    parts = {name: function(source, name) for name in FUNCTIONS}
    parts['helpers'] = '\n'.join(function(source, name) for name in (
        'obor_scene_counters_active', 'obor_scene_counter_adjust')) if \
        'obor_scene_counters_active' in source else ''
    return parts


def program(engine, rows, contracts):
    if (not isinstance(rows, list) or not rows or
            any(not isinstance(row, dict) or not {'engine', 'contract', 'revision'} <= set(row)
                or type(row['revision']) is not int or not 0 < row['revision'] <= 0xffffffff
                for row in rows)):
        raise ValueError('Explicit native AI movement contract rows required')
    first = rows[0]
    if (first['engine'] != engine or first['contract'] not in contracts or
            any((row['engine'], row['contract']) != (engine, first['contract']) for row in rows)
            or [row['revision'] for row in rows] != sorted({row['revision'] for row in rows})
            or not isinstance(contracts[first['contract']], dict)
            or set(contracts[first['contract']]) != {'game_speed', 'wander', 'adjust', 'move'}):
        raise ValueError('One engine/expectation group with unique sorted revisions required')
    code = render_ai_movement(source_parts(engine), revision=first['revision'],
        native_animation_capacity=True,
        **contracts[first['contract']])
    marker = 'int main(void){'
    if code.count(marker) != 1:
        raise ValueError('One authored ai-movement entry required')
    entry = '''int main(int argc,char **argv) {
 const uint32_t revisions[]={@REVISIONS@};
 assert(argc==2);obor_profile_build=(uint32_t)atoi(argv[1]);unsigned matched=0;
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i)
  if(revisions[i]==obor_profile_build)++matched;
 assert(matched==1);
'''.replace('@REVISIONS@', ','.join(str(row['revision']) for row in rows))
    return code.replace(marker, entry)


class AIMovementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = json.loads(CONTRACT_PATH.read_text())
        cls.rows, cls.contracts = fixture['sources'], fixture['contracts']
        cls.coverage = fixture['covered_profile_ranges']
        cls.groups, cls.executables = {}, {}
        for row in cls.rows:
            cls.groups.setdefault((row['engine'], row['contract']), []).append(row)
        temporary = tempfile.TemporaryDirectory(prefix='anybor-ai-movement-')
        cls.addClassCleanup(temporary.cleanup)
        work = Path(temporary.name)
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
        warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-no-pie', '-Wl,--gc-sections']
        host_flags = [] if sys.platform == 'darwin' else ['-DLINUX=1']
        for index, (key, rows) in enumerate(cls.groups.items()):
            root = SOURCE / 'src/engines' / key[0]
            includes = [root, SOURCE / 'src/port/libretro', SOURCE / 'src/glue', root / 'source',
                        *sorted(p for p in (root / 'source').iterdir() if p.is_dir())]
            code = work / ('contract-%d.c' % index)
            executable = code.with_suffix('')
            code.write_bytes(program(key[0], rows, cls.contracts).encode('utf-8', 'surrogateescape'))
            compiled = subprocess.run(compiler + ['-I' + str(p) for p in includes] + [
                '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-error=sign-compare', '-Wno-error=misleading-indentation',
                '-Wno-error=implicit-fallthrough', '-Wno-unused-variable',
                '-Wno-unused-function', '-Wno-unused-parameter', *warnings,
                '-O1', '-g', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=' + key[0],
                *host_flags, '-fsigned-char', '-ffunction-sections', '-fdata-sections',
                '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
                str(code), *links, '-lm', '-o', str(executable)],
                capture_output=True, text=True, timeout=60)
            if compiled.stdout:
                sys.stderr.write(compiled.stdout)
            if compiled.stderr:
                sys.stderr.write(compiled.stderr)
            if compiled.returncode:
                raise RuntimeError('Native AI movement compilation failed')
            cls.executables[key] = executable

    def test_registered_profiles_have_own_source_contracts(self):
        by_revision = {row['revision']: row for row in self.rows}
        self.assertEqual(len(by_revision), len(self.rows))
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        for profile in pin['profiles']:
            revision = int(profile.get('revision', profile['build']))
            if any(profile['engine'] == span['engine'] and span['first'] <= revision <= span['last']
                   for span in self.coverage):
                self.assertEqual(by_revision[revision]['engine'], profile['engine'])
        for row in self.rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIsInstance(row['helper_available'], bool)
            self.assertEqual(set(row['source_parts_sha256']), set(FUNCTIONS))
            for digest in row['source_parts_sha256'].values():
                if digest is not None:
                    self.assertRegex(digest, r'^[0-9a-f]{64}$')

    def test_native_movement_for_each_profile_and_boundary_context(self):
        for key, rows in self.groups.items():
            expected = dict(status='PASS', **{name:len(self.contracts[key[1]][name])
                for name in ('wander','adjust','move')})
            for row in rows:
                with self.subTest(engine=row['engine'], revision=row['revision']):
                    observed = subprocess.check_output([str(self.executables[key]), str(row['revision'])],
                        timeout=15, text=True, env=sanitizer_environment())
                    self.assertEqual(json.loads(observed), expected)


if __name__ == '__main__':
    unittest.main()
