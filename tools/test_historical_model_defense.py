"""Compare native defense commands with explicit own-source profile contracts.

Compile once per engine/expectation group and run every declared revision.
Allocation, complete model loading, subtype defaults and combat callers remain
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

from historical_model_defense import render_model_defense
from native_sanitizers import sanitizer_environment
from test_historical_player import function, switch_cases

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
CONTRACT_PATH = Path(__file__).parent / 'fixtures/profile-model-defense-contracts.json'
PARTS = {'parse_args', 'is_numeric', 'float_reader', 'argument_macros',
         'defense_case', 'default_defense'}


def source_parts(engine):
    root = SOURCE / 'src/engines' / engine
    source = (root / 'openbor.c').read_bytes().decode('utf-8', 'surrogateescape')
    header = (root / 'openbor.h').read_bytes().decode('utf-8', 'surrogateescape')
    method = function(source, 'load_cached_model')
    method = method.replace('switch(cmd)', 'switch(fixture_model_command)', 1)
    method, cases = switch_cases(method, 'load_cached_model', 'fixture_model_command')
    selected = cases['CMD_MODEL_DEFENSE']
    macros = []
    for name in ('GET_ARG', 'GET_FLOAT_ARG'):
        matches = re.findall(r'^#define[ \t]+' + name + r'\(z\)[^\r\n]*',
                             source + '\n' + header, re.M)
        if len(set(matches)) != 1:
            raise ValueError('One native argument macro definition required')
        macros.append(matches[0])
    default = re.search(r'const\s+s_defense\s+default_defense\s*=\s*\{[^}]*\};', source)
    if default is None:
        raise ValueError('Native record default required')
    parts = dict(parse_args=function(source, 'ParseArgs'),
                 is_numeric=function(source, 'isNumeric'),
                 float_reader=function(source, 'getValidFloat'),
                 argument_macros='\n'.join(macros), default_defense=default[0],
                 defense_case=method[selected['label_start']:selected['end']])
    helpers = '\n'.join(function(source, name) for name in (
        'obor_model_defense_legacy', 'obor_attack_base', 'obor_attack_special',
        'obor_attack_name_available') if re.search(
            r'(?m)^(?:static[ \t]+)?[^\n;{}]*\b' + name + r'\([^;{}]*\)\s*\{', source))
    return parts, helpers


def program(engine, rows, contracts):
    if (not isinstance(rows, list) or not rows or
            any(not isinstance(row, dict) or not {'engine', 'contract', 'revision'} <= set(row)
                or type(row['revision']) is not int or not 0 < row['revision'] <= 0xffffffff
                for row in rows)):
        raise ValueError('Explicit native defense contract rows required')
    first = rows[0]
    if (first['engine'] != engine or first['contract'] not in contracts or
            any((row['engine'], row['contract']) != (engine, first['contract']) for row in rows)
            or [row['revision'] for row in rows] != sorted({row['revision'] for row in rows})):
        raise ValueError('One engine/expectation group with unique sorted revisions required')
    parts, helpers = source_parts(engine)
    options = dict(contracts[first['contract']])
    options['representation'] = 'record'  # The physical source supplies its actual record type.
    code = render_model_defense(parts, revision=first['revision'], helpers=helpers, **options)
    marker = 'int main(void) {'
    if code.count(marker) != 1:
        raise ValueError('One authored defense entry required')
    entry = '''int main(int argc,char **argv) {
 const uint32_t revisions[]={@REVISIONS@};
 assert(argc==2);obor_profile_build=(uint32_t)atoi(argv[1]);unsigned matched=0;
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i)
  if(revisions[i]==obor_profile_build)++matched;
 assert(matched==1);
'''.replace('@REVISIONS@', ','.join(str(row['revision']) for row in rows))
    return code.replace(marker, entry)


class ModelDefenseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = json.loads(CONTRACT_PATH.read_text())
        cls.rows, cls.contracts = fixture['sources'], fixture['contracts']
        cls.groups, cls.executables = {}, {}
        for row in cls.rows:
            cls.groups.setdefault((row['engine'], row['contract']), []).append(row)
        temporary = tempfile.TemporaryDirectory(prefix='anybor-model-defense-')
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
                '-Wno-error=sign-compare', '-Wno-error=implicit-fallthrough',
                '-Wno-unused-variable', '-Wno-unused-function', '-Wno-unused-parameter',
                *warnings, '-O1', '-g', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=' + key[0],
                *host_flags, '-fsigned-char', '-ffunction-sections', '-fdata-sections',
                '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
                str(code), *links, '-lm', '-o', str(executable)],
                capture_output=True, text=True, timeout=60)
            if compiled.stdout:
                sys.stderr.write(compiled.stdout)
            if compiled.stderr:
                sys.stderr.write(compiled.stderr)
            if compiled.returncode:
                raise RuntimeError('Native defense command compilation failed')
            cls.executables[key] = executable

    def test_registered_profiles_have_own_source_contracts(self):
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
            self.assertEqual(set(row['source_parts_sha256']), PARTS)
            for digest in row['source_parts_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')

    def test_native_commands_for_each_profile_and_boundary_context(self):
        for key, rows in self.groups.items():
            options = self.contracts[key[1]]
            count = len(options['cases'])
            expected = {'status': 'PASS', 'cases': count,
                        'checks': count * (options['attack_types'] + 1) * 7}
            for row in rows:
                with self.subTest(engine=row['engine'], revision=row['revision']):
                    observed = subprocess.check_output([str(self.executables[key]), str(row['revision'])],
                        timeout=15, text=True, env=sanitizer_environment())
                    self.assertEqual(json.loads(observed), expected)


if __name__ == '__main__':
    unittest.main()
