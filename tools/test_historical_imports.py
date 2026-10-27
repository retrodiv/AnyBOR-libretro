"""Check native import lifetime and actual compiled script calls by profile.

The complete VM, parser, preprocessor and cache units are linked. Packfile I/O
and native script services use authored providers with real mapping helpers. Allocation
tracking retains the engine arena's final retirement boundary explicitly.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import hashlib
import os
import re
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from native_sanitizers import sanitizer_environment
from test_historical_player import function

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
TOOLS = Path(__file__).parent


class ImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((TOOLS / 'fixtures/profile-import-contracts.json').read_text())
        temporary = tempfile.TemporaryDirectory(prefix='anybor-native-imports-')
        cls.addClassCleanup(temporary.cleanup)
        work = Path(temporary.name)
        cls.executable = work / 'imports'
        engine = SOURCE / 'src/engines/3842'
        script_source = engine / 'openborscript.c'
        script_text = script_source.read_text()
        mapped_header = work / 'native_probe_mapper.h'
        macro_start = script_text.index('#define MAPSTRINGS(')
        macro_end = script_text.index('\n\n', macro_start)
        enum_start = script_text.index('enum playerproperty_enum {')
        enum_end = script_text.index('};', enum_start) + 2
        mapped_header.write_text('\n'.join((
            function((engine / 'source/utils.c').read_text(), 'searchList'),
            script_text[macro_start:macro_end], script_text[enum_start:enum_end],
            *(function(script_text, name) for name in (
                'mapstrings_playerproperty', 'Script_MapStringConstants', 'system_rand')))))
        interpreter_text = (engine / 'source/scriptlib/Interpreter.c').read_text()
        has_opcode_display = 'static int obor_profile_opcode(' in interpreter_text
        has_constant_refresh = 'static HRESULT obor_refresh_constant(' in interpreter_text
        if has_opcode_display:
            with mapped_header.open('a') as stream:
                stream.write('\n' + function(interpreter_text, 'obor_profile_opcode'))
        includes = [work, engine, SOURCE / 'src/port/libretro', SOURCE / 'src/glue', engine / 'source',
                    *sorted(p for p in (engine / 'source').iterdir() if p.is_dir())]
        sources = sorted((engine / 'source/scriptlib').glob('*.c'))
        sources += sorted((engine / 'source/preprocessorlib').glob('*.c'))
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        version = subprocess.check_output(compiler + ['--version'], text=True, timeout=10)
        warnings = ['-Wno-error=pragma-pack'] if 'clang' in version.lower() else []
        if 'clang' not in version.lower():
            # Whole upstream parser units retain diagnostics in paths outside
            # this fixture. Keep the warnings and all runtime sanitizer checks.
            warnings += ['-Wno-error=format-overflow', '-Wno-error=stringop-overflow']
        host = [] if sys.platform == 'darwin' else ['-DLINUX=1', '-no-pie']
        links = ['-Wl,-dead_strip'] if sys.platform == 'darwin' else ['-Wl,--gc-sections']
        header = (engine / 'source/scriptlib/ImportCache.h').read_text()
        cls.command = compiler + ['-I'+str(p) for p in includes] + [
            '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-error=deprecated-declarations',
            '-Wno-error=sign-compare', '-Wno-error=misleading-indentation',
            '-Wno-error=implicit-fallthrough', '-Wno-error=int-to-pointer-cast',
            '-Wno-error=pointer-to-int-cast', '-Wno-unused-variable',
            '-Wno-unused-function', '-Wno-unused-parameter', *warnings,
            '-g', '-fgnu89-inline', '-DLIBRETRO=1', '-DOBOR_ENGINE_BUILD=3842',
            '-fsigned-char', '-ffunction-sections', '-fdata-sections', *host,
            '-fsanitize=address,undefined,pointer-overflow', '-fno-sanitize-recover=all',
            '-DPROBE_HAS_LEGACY_RELEASE='+str(int('ImportCache_Release' in header)),
            '-DPROBE_HAS_OPCODE_DISPLAY='+str(int(has_opcode_display)),
            '-DPROBE_HAS_CONSTANT_REFRESH='+str(int(has_constant_refresh)),
            '-include', str(TOOLS / 'imports_probe_alloc.h'),
            str(TOOLS / 'historical_imports_probe.c'), *map(str, sources),
            *links, '-lm', '-o', str(cls.executable)]
        result = subprocess.run(cls.command, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise RuntimeError('Native import compilation failed:\n'+result.stdout+result.stderr)
        if os.environ.get('OBOR_IMPORT_OBSERVATIONS'):
            inputs = [TOOLS / 'historical_imports_probe.c', TOOLS / 'imports_probe_alloc.h',
                      script_source, engine / 'source/utils.c', mapped_header, *sources]
            for directory in (engine, SOURCE / 'src/port/libretro', SOURCE / 'src/glue'):
                inputs += sorted(directory.rglob('*.h'))
            bindings = [dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                             bytes=p.stat().st_size) for p in dict.fromkeys(inputs)]
            receipt = dict(command=cls.command, compiler=version, sources=bindings,
                binary_sha256=hashlib.sha256(cls.executable.read_bytes()).hexdigest(),
                binary_bytes=cls.executable.stat().st_size,
                header_scope='Conservative header binding; not a claim every header was compiled',
                binary_retirement='TemporaryDirectory cleanup at class completion')
            Path(os.environ['OBOR_IMPORT_OBSERVATIONS']+'.compiler.json').write_text(
                json.dumps(receipt, indent=2)+'\n')

    def grammar_contracts(self):
        fixture = json.loads((TOOLS / 'fixtures/profile-grammar-contracts.json').read_text())
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue({3761, 3769, 3773, *fixture['boundary_controls']} <= revisions)
        for profile in json.loads((SOURCE / 'src/pin.json').read_text())['profiles']:
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for key, boundary in (('switch', 3810), ('string_switch', 3812), ('ternary', 3816),
                                  ('assignment_load_elision', 3818), ('unary_token_folding', 3831),
                                  ('shift', 3833), ('bitwise', 3839)):
                self.assertEqual(row['features'][key], row['revision'] >= boundary)
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        return fixture

    def save_grammar_observations(self, observations):
        if os.environ.get('OBOR_GRAMMAR_OBSERVATIONS'):
            path = Path(os.environ['OBOR_GRAMMAR_OBSERVATIONS'])
            previous = json.loads(path.read_text()) if path.exists() else []
            path.write_text(json.dumps(previous+observations, indent=2)+'\n')

    def test_native_grammar_acceptance_and_values_per_profile(self):
        observations = []
        for row in self.grammar_contracts()['sources']:
            with self.subTest(revision=row['revision']):
                result = subprocess.run([str(self.executable), str(row['revision']),
                    str(int(row['revision'] < 3779)), 'grammar'],
                    capture_output=True, text=True, timeout=20, env=sanitizer_environment())
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                observation = json.loads(result.stdout)
                self.assertEqual(observation['status'], 'PASS')
                self.assertEqual(observation['scenarios'], 26)
                observations.append(dict(revision=row['revision'], mode='grammar', **observation))
        self.save_grammar_observations(observations)

    def test_native_first_and_follow_sets_per_profile(self):
        fixture = self.grammar_contracts()
        engine = SOURCE / 'src/engines/3842/source/scriptlib'
        def enum_names(filename, name):
            text = (engine / filename).read_text()
            body = re.search(r'typedef enum '+name+r'\s*\{(.*?)\}\s*'+name+r';', text, re.S)[1]
            body = re.sub(r'/\*.*?\*/|//[^\n]*', '', body, flags=re.S)
            names = [item.strip() for item in body.split(',') if item.strip()]
            self.assertTrue(all(re.fullmatch(r'[A-Za-z_]\w*', item) for item in names))
            return names
        productions = enum_names('Productions.h', 'PRODUCTION')
        self.assertEqual(productions.pop(), 'error')
        tokens = {name: index for index, name in enumerate(enum_names('Lexer.h', 'MY_TOKEN_TYPE'))}
        table_sources = {row['revision']: row for row in fixture['table_sources']}
        observations = []
        for row in fixture['sources']:
            with self.subTest(revision=row['revision']):
                result = subprocess.run([str(self.executable), str(row['revision']),
                    str(int(row['revision'] < 3779)), 'tables'],
                    capture_output=True, text=True, timeout=20, env=sanitizer_environment())
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                actual = json.loads(result.stdout)
                expected = fixture['tables'][table_sources[row['revision']]['table_sha256']]
                for kind in ('first', 'follow'):
                    self.assertEqual(actual[kind], [[tokens[token] for token in
                        expected[kind].get(name, [])] for name in productions])
                observations.append(dict(revision=row['revision'], mode='grammar_tables', status='PASS',
                                         productions=len(productions), table_sets=2*len(productions)))
        self.save_grammar_observations(observations)

    def test_profiles_have_own_import_contracts(self):
        rows = self.fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue({3761, 3769, 3773, 3778, 3779} <= revisions)
        for profile in json.loads((SOURCE / 'src/pin.json').read_text())['profiles']:
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['legacy_references'], row['revision'] < 3779)
            self.assertEqual(row['imported_function_calls'], row['revision'] >= 3779)
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')

    def test_native_call_completion_reset_reentry_and_refusal_per_profile(self):
        fixture = json.loads((TOOLS / 'fixtures/profile-call-completion-contracts.json').read_text())
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue({3761, 3769, 3773, *fixture['boundary_controls']} <= revisions)
        for profile in json.loads((SOURCE / 'src/pin.json').read_text())['profiles']:
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        observations = []
        for row in rows:
            self.assertEqual(row['call_completion_from_reset'], row['revision'] >= 3834)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            with self.subTest(revision=row['revision']):
                result = subprocess.run([str(self.executable), str(row['revision']),
                    str(int(row['revision'] < 3779)), 'calls'],
                    capture_output=True, text=True, timeout=20, env=sanitizer_environment())
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                observation = json.loads(result.stdout)
                self.assertEqual(observation['scenarios'], 21)
                self.assertEqual(observation['status'], 'PASS')
                observations.append(dict(revision=row['revision'], **observation))
        if os.environ.get('OBOR_CALL_OBSERVATIONS'):
            Path(os.environ['OBOR_CALL_OBSERVATIONS']).write_text(json.dumps(observations, indent=2)+'\n')

    def test_native_mapper_argument_admission_per_profile(self):
        fixture = json.loads((TOOLS / 'fixtures/profile-mapper-argument-contracts.json').read_text())
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue({3761, 3769, 3773, *fixture['boundary_controls']} <= revisions)
        for profile in json.loads((SOURCE / 'src/pin.json').read_text())['profiles']:
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        observations = []
        for row in rows:
            self.assertEqual(row['mapper_argument_limit'], None if row['revision'] < 3828 else 32)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            for count in (0, 1, 32, 33, 64):
                with self.subTest(revision=row['revision'], count=count):
                    result = subprocess.run([str(self.executable), str(row['revision']),
                        str(int(row['revision'] < 3779)), 'mapper', str(count)],
                        capture_output=True, text=True, timeout=20, env=sanitizer_environment())
                    rejected = row['mapper_argument_limit'] is not None and count > row['mapper_argument_limit']
                    if rejected:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn(': paramCount<=32', result.stderr)
                        self.assertNotIn('runtime error:', result.stderr)
                        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)
                    else:
                        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                        self.assertEqual(json.loads(result.stdout)['status'], 'PASS')
                    observations.append(dict(revision=row['revision'], count=count,
                        result='native_limit_refusal' if rejected else 'accepted_return_17'))
        if os.environ.get('OBOR_MAPPER_OBSERVATIONS'):
            Path(os.environ['OBOR_MAPPER_OBSERVATIONS']).write_text(json.dumps(observations, indent=2)+'\n')

    def test_native_compiled_mapper_aliases_per_profile(self):
        fixture = json.loads((TOOLS / 'fixtures/profile-vm-alias-contracts.json').read_text())
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue({3761, 3769, 3773, *fixture['boundary_controls']} <= revisions)
        for profile in json.loads((SOURCE / 'src/pin.json').read_text())['profiles']:
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        observations = []
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertEqual(row['runtime_constant_copy'], row['revision'] < 3831)
            self.assertEqual(row['player_properties'].index('weapon'), row['weapon'])
            self.assertEqual(row['player_properties'].index('name'), row['name'])
            for digest in [row['player_mapper_sha256'], *row['source_sha256'].values()]:
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            with self.subTest(revision=row['revision']):
                result = subprocess.run([str(self.executable), str(row['revision']),
                    str(int(row['revision'] < 3779)), 'aliases', str(row['weapon']), str(row['name'])],
                    capture_output=True, text=True, timeout=20, env=sanitizer_environment())
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                observation = json.loads(result.stdout)
                self.assertEqual(observation['status'], 'PASS')
                self.assertEqual(observation['scenarios'], 10)
                observations.append(dict(revision=row['revision'], **observation))
        if os.environ.get('OBOR_ALIAS_OBSERVATIONS'):
            Path(os.environ['OBOR_ALIAS_OBSERVATIONS']).write_text(json.dumps(observations, indent=2)+'\n')
        # Suppress only the authored compile-pass mapper provider. Runtime
        # mapping still exists, so the compiled-reference check must detect it.
        row = rows[0]
        result = subprocess.run([str(self.executable), str(row['revision']),
            str(int(row['revision'] < 3779)), 'aliases', str(row['weapon']), str(row['name']), 'nomap'],
            capture_output=True, text=True, timeout=20, env=sanitizer_environment())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('args[1]->vt==VT_INTEGER && args[1]->lVal==value', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)

    def test_native_cache_and_compiled_calls_per_profile(self):
        observations = []
        for row in self.fixture['sources']:
            with self.subTest(revision=row['revision']):
                result = subprocess.run([str(self.executable), str(row['revision']),
                    str(int(row['legacy_references']))], capture_output=True, text=True,
                    timeout=20, env=sanitizer_environment())
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                observation = json.loads(result.stdout)
                self.assertEqual(observation['status'], 'PASS')
                self.assertEqual(observation['scenarios'], 11)
                self.assertIsInstance(observation['arena_tail_allocations'], int)
                observations.append(dict(revision=row['revision'], mode='lifecycle', **observation))
        if os.environ.get('OBOR_IMPORT_OBSERVATIONS'):
            Path(os.environ['OBOR_IMPORT_OBSERVATIONS']).write_text(
                json.dumps(observations, indent=2)+'\n')

    def test_native_runtime_error_diagnostics_per_profile(self):
        fixture = json.loads((TOOLS / 'fixtures/profile-vm-step-contracts.json').read_text())
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertTrue({3761, 3769, 3773, *fixture['boundary_controls']} <= revisions)
        for profile in json.loads((SOURCE / 'src/pin.json').read_text())['profiles']:
            if profile['engine'] == '3842':
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        observations = []
        for row in rows:
            self.assertEqual(row['call'], row['opcodes'].index('CALL'))
            self.assertEqual(row['checkarg'], row['opcodes'].index('CHECKARG'))
            self.assertEqual(row['error_opcode_diagnostic'], row['revision'] < 3831)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
            with self.subTest(revision=row['revision']):
                result = subprocess.run([str(self.executable), str(row['revision']),
                    str(int(row['revision'] < 3779)), 'diagnostics', str(row['call']), str(row['checkarg'])],
                    capture_output=True, text=True, timeout=20, env=sanitizer_environment())
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                observation = json.loads(result.stdout)
                self.assertEqual(observation['status'], 'PASS')
                self.assertEqual(observation['scenarios'], 4)
                observations.append(dict(revision=row['revision'], **observation))
        if os.environ.get('OBOR_DIAGNOSTIC_OBSERVATIONS'):
            Path(os.environ['OBOR_DIAGNOSTIC_OBSERVATIONS']).write_text(json.dumps(observations, indent=2)+'\n')

    def test_native_opcode_display_numbers_per_profile(self):
        fixture = json.loads((TOOLS / 'fixtures/profile-vm-step-contracts.json').read_text())
        header = (SOURCE / 'src/engines/3842/source/scriptlib/Instruction.h').read_text()
        enum = re.search(r'typedef enum OpCode\{(.*?)\}OpCode;', header, re.S)[1]
        names = [part.strip() for part in enum.replace('\n', ' ').split(',')]
        observations = []
        for row in fixture['sources']:
            self.assertTrue(set(row['opcodes']) <= set(names))
            values = [row['opcodes'].index(name) if name in row['opcodes'] else -1 for name in names]
            with self.subTest(revision=row['revision']):
                result = subprocess.run([str(self.executable), str(row['revision']),
                    str(int(row['revision'] < 3779)), 'opcodes', ','.join(map(str, values))],
                    capture_output=True, text=True, timeout=20, env=sanitizer_environment())
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                observation = json.loads(result.stdout)
                self.assertEqual(observation['status'], 'PASS')
                self.assertEqual(observation['scenarios'], len(names)+2)
                observations.append(dict(revision=row['revision'], **observation))
        if os.environ.get('OBOR_OPCODE_OBSERVATIONS'):
            Path(os.environ['OBOR_OPCODE_OBSERVATIONS']).write_text(json.dumps(observations, indent=2)+'\n')

    def test_native_repeated_constants_per_profile(self):
        fixture = json.loads((TOOLS / 'fixtures/profile-vm-step-contracts.json').read_text())
        observations = []
        for row in fixture['sources']:
            with self.subTest(revision=row['revision']):
                result = subprocess.run([str(self.executable), str(row['revision']),
                    str(int(row['revision'] < 3779)), 'constants'], capture_output=True,
                    text=True, timeout=20, env=sanitizer_environment())
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                observation = json.loads(result.stdout)
                self.assertEqual(observation['status'], 'PASS')
                self.assertEqual(observation['scenarios'], 6+int(row['revision']<3831))
                observations.append(dict(revision=row['revision'], **observation))
        if os.environ.get('OBOR_CONSTANT_OBSERVATIONS'):
            Path(os.environ['OBOR_CONSTANT_OBSERVATIONS']).write_text(json.dumps(observations, indent=2)+'\n')

    def test_native_resolution_uses_own_precedence(self):
        observations = []
        for row in self.fixture['sources']:
            with self.subTest(revision=row['revision']):
                result = subprocess.run([str(self.executable), str(row['revision']),
                    str(int(row['legacy_references'])), 'precedence'],
                    capture_output=True, text=True, timeout=20, env=sanitizer_environment())
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                observation = json.loads(result.stdout)
                self.assertEqual(observation['status'], 'PASS')
                self.assertEqual(observation['scenarios'], 1)
                observations.append(dict(revision=row['revision'], mode='precedence', **observation))
        if os.environ.get('OBOR_IMPORT_OBSERVATIONS'):
            path = Path(os.environ['OBOR_IMPORT_OBSERVATIONS'])
            previous = json.loads(path.read_text()) if path.exists() else []
            path.write_text(json.dumps(previous+observations, indent=2)+'\n')


if __name__ == '__main__':
    unittest.main()
