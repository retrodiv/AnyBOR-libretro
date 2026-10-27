"""Compare native AI attack commands against own-source profile oracles.

Compile once per physical source/expectation group and run each revision fresh.
The complete model loader and native shutdown implementation remain separate.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from contract_fixtures import load_contract_fixture, contract_profiles
import json
import os
import re
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from historical_aiattack_command import render_aiattack_command
from native_sanitizers import sanitizer_environment
from test_historical_player import function

SOURCE = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
CONTRACT_PATH = Path(__file__).parent / 'fixtures/profile-aiattack-command-contracts.json'


def source_parts(engine):
    root = SOURCE / 'src/engines' / engine
    source, header = [(root / name).read_bytes().decode('utf-8', 'surrogateescape')
                      for name in ('openbor.c', 'openbor.h')]
    macros = []
    for name in ('GET_ARG', 'GET_ARGP'):
        matches = [match for text in (source, header) for match in
                   re.finditer(r'^#define[ \t]+' + name + r'\(z\)[^\r\n]*', text, re.M)]
        if len(matches) != 1:
            raise ValueError('One native argument macro definition required')
        macros.append(matches[0])
    command = re.search(r'^\s*case CMD_MODEL_AIATTACK:[\s\S]*?break;', source, re.M)
    if not all(macros) or command is None:
        raise ValueError('Native command and argument macro definitions required')
    return dict(parse_args=function(source, 'ParseArgs'),
                argument_macros='\n'.join(match[0] for match in macros),
                command_case=command[0], loader=function(source, 'lcmHandleCommandAiattack'))


def program(engine, rows, contracts):
    if (not isinstance(rows, list) or not rows or
            any(not isinstance(row, dict) or not {'engine', 'contract', 'revision'} <= set(row)
                or type(row['revision']) is not int or not 0 < row['revision'] <= 0xffffffff
                for row in rows)):
        raise ValueError('Explicit native AI command contract rows required')
    first = rows[0]
    if (first['engine'] != engine or first['contract'] not in contracts or
            any((row['engine'], row['contract']) != (engine, first['contract']) for row in rows)
            or [row['revision'] for row in rows] != sorted({row['revision'] for row in rows})):
        raise ValueError('One engine/expectation group with unique sorted revisions required')
    code = render_aiattack_command(source_parts(engine), revision=first['revision'],
        **contracts[first['contract']])
    marker = 'int main(void) {'
    if code.count(marker) != 1:
        raise ValueError('One authored AI-command entry required')
    entry = '''int main(int argc,char **argv) {
 const uint32_t revisions[]={@REVISIONS@};
 assert(argc==2);obor_profile_build=(uint32_t)atoi(argv[1]);unsigned matched=0;
 for(unsigned i=0;i<sizeof(revisions)/sizeof(*revisions);++i)
  if(revisions[i]==obor_profile_build)++matched;
 assert(matched==1);
'''.replace('@REVISIONS@', ','.join(str(row['revision']) for row in rows))
    return code.replace(marker, entry)


class AiattackCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = load_contract_fixture(CONTRACT_PATH)
        cls.rows, cls.contracts = fixture['sources'], fixture['contracts']
        cls.coverage = fixture['covered_profile_ranges']
        cls.groups, cls.executables = {}, {}
        for row in cls.rows:
            cls.groups.setdefault((row['engine'], row['contract']), []).append(row)
        temporary = tempfile.TemporaryDirectory(prefix='anybor-aiattack-command-')
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
                raise RuntimeError('Native AI command compilation failed')
            cls.executables[key] = executable

    def test_registered_profiles_have_own_source_contracts(self):
        by_revision = {row['revision']: row for row in self.rows}
        self.assertEqual(len(by_revision), len(self.rows))
        pin = json.loads((SOURCE / 'src/pin.json').read_text())
        for profile in contract_profiles(Path(__file__).parent / 'fixtures/profile-aiattack-command-contracts.json', pin['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if any(profile['engine'] == span['engine'] and span['first'] <= revision <= span['last']
                   for span in self.coverage):
                self.assertEqual(by_revision[revision]['engine'], profile['engine'])
        for row in self.rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertIsInstance(row['loader_source'], bool)
            self.assertEqual(set(row['source_parts_sha256']), {'parse_args', 'argument_macros', 'command_case', 'loader'})
            for digest in row['source_parts_sha256'].values():
                if digest is not None:
                    self.assertRegex(digest, r'^[0-9a-f]{64}$')

    def test_native_aiattack_command_for_each_profile_and_boundary_context(self):
        for key, rows in self.groups.items():
            expected = dict(status='PASS', cases=len(self.contracts[key[1]]['cases']))
            for row in rows:
                with self.subTest(engine=row['engine'], revision=row['revision']):
                    observed = subprocess.check_output([str(self.executables[key]), str(row['revision'])],
                        timeout=15, text=True, env=sanitizer_environment())
                    self.assertEqual(json.loads(observed), expected)


if __name__ == '__main__':
    unittest.main()
