"""Check declared profiles' native combat factor and damage-exemption contracts.

Compile once per engine/contract group, then execute every declared revision.
Callbacks observe payloads; blocking, complete callers and model loading are
separate contracts.
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

from historical_combat_factors import render_combat_factors
from native_sanitizers import sanitizer_environment
from test_historical_player import function

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
CONTRACT_PATH = Path(__file__).parent / 'fixtures/profile-combat-factor-contracts.json'
FUNCTIONS = ('checkdamage', 'checkdamagedrop', 'checkdamageflip', 'common_dot')
GROUP_FIELDS = ('engine', 'factor_target', 'configurable_drop', 'projectile_factors', 'attack_types')


def source_parts(engine):
    source = (SOURCE / 'src/engines' / engine / 'openbor.c').read_bytes().decode('utf-8', 'surrogateescape')
    parts = {name: function(source, name) for name in FUNCTIONS}
    helpers = ''
    names = ('obor_combat_defense', 'obor_combat_offense')
    present = [bool(re.search(r'(?m)^static[^\n]*\b' + name + r'\(', source)) for name in names]
    if any(present):
        if not all(present):
            raise ValueError('Both native combat reader helpers are required')
        default = re.search(r'const\s+s_defense\s+default_defense\s*=\s*\{[^}]*\};', source)
        if default is None:
            raise ValueError('Native default defense record required')
        helpers = default[0] + '\n' + ''.join(function(source, name) for name in names)
    return parts, helpers


def program(engine, rows):
    if (not isinstance(rows, list) or not rows or
            any(not isinstance(row, dict) or not set(GROUP_FIELDS) <= set(row) or
                type(row.get('revision')) is not int or not 0 < row['revision'] <= 0xffffffff
                for row in rows)):
        raise ValueError('Explicit native combat contract rows required')
    first = rows[0]
    if (first['engine'] != engine or
            any(tuple(row[key] for key in GROUP_FIELDS) != tuple(first[key] for key in GROUP_FIELDS)
                for row in rows) or
            [row['revision'] for row in rows] != sorted({row['revision'] for row in rows})):
        raise ValueError('One engine/contract group with unique sorted revisions required')
    parts, helpers = source_parts(engine)
    code = render_combat_factors(parts, revision=first['revision'], representation='record',
        factor_target=first['factor_target'], configurable_drop=first['configurable_drop'],
        projectile_factors=first['projectile_factors'], attack_types=first['attack_types'],
        dot_loop='exclusive', helpers=helpers)
    marker = 'int main(void) {'
    if code.count(marker) != 1:
        raise ValueError('One authored combat entry required')
    entry = '''int main(int argc,char **argv) {
 const uint32_t revisions[]={@REVISIONS@};
 assert(argc==2);obor_profile_build=(uint32_t)atoi(argv[1]);unsigned matched=0;
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i)
  if(revisions[i]==obor_profile_build)++matched;
 assert(matched==1);
'''.replace('@REVISIONS@', ','.join(str(row['revision']) for row in rows))
    return code.replace(marker, entry)


class CombatFactorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads(CONTRACT_PATH.read_text())['sources']
        cls.groups = {}
        for row in cls.rows:
            cls.groups.setdefault(tuple(row[key] for key in GROUP_FIELDS), []).append(row)
        cls.executables = {}
        temporary = tempfile.TemporaryDirectory(prefix='anybor-combat-factors-')
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
            code.write_bytes(program(key[0], rows).encode('utf-8', 'surrogateescape'))
            compiled = subprocess.run(compiler + ['-I' + str(p) for p in includes] + [
                '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
                '-Wno-error=sign-compare', '-Wno-unused-variable', '-Wno-unused-function',
                '-Wno-unused-parameter', *warnings, '-O1', '-g', '-DLIBRETRO=1',
                '-DOBOR_ENGINE_BUILD=' + key[0], *host_flags, '-fsigned-char',
                '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined,pointer-overflow',
                '-fno-sanitize-recover=all', str(code), *links, '-lm', '-o', str(executable)],
                capture_output=True, text=True, timeout=60)
            if compiled.stdout:
                sys.stderr.write(compiled.stdout)
            if compiled.stderr:
                sys.stderr.write(compiled.stderr)
            if compiled.returncode:
                raise RuntimeError('Native combat contract compilation failed')
            cls.executables[key] = executable

    def test_registered_profiles_and_boundary_controls_have_own_source_contracts(self):
        by_revision = {row['revision']: row for row in self.rows}
        self.assertEqual(len(by_revision), len(self.rows))
        engines = {row['engine'] for row in self.rows}
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        for profile in pin['profiles']:
            if profile['engine'] in engines:
                row = by_revision[int(profile.get('revision', profile['build']))]
                self.assertEqual(row['engine'], profile['engine'])
        for row in self.rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(set(row['source_sha256']), set(FUNCTIONS))
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        for before, after, field, old, new in (
                (3680, 3682, 'configurable_drop', False, True),
                (3709, 3710, 'factor_target', 'model', 'entity'),
                (3830, 3831, 'projectile_factors', False, True)):
            self.assertEqual(by_revision[before][field], old)
            self.assertEqual(by_revision[after][field], new)

    def test_native_combat_results_for_every_profile_and_boundary_context(self):
        for key, rows in self.groups.items():
            for row in rows:
                with self.subTest(engine=row['engine'], revision=row['revision']):
                    observed = subprocess.check_output([str(self.executables[key]), str(row['revision'])],
                        timeout=15, text=True, env=sanitizer_environment())
                    self.assertEqual(json.loads(observed),
                                     {'status': 'PASS', 'cases': 1104 * row['attack_types']})


if __name__ == '__main__':
    unittest.main()
