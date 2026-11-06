"""Check reset, bounded call dispatch and clear-entry state by source profile.

The real reset/call/immediate/clear functions run with deterministic instruction
and lifecycle providers. This is not complete bytecode or gameplay execution.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from historical_script_lifecycle import render
from native_sanitizers import sanitizer_environment
from test_historical_player import function
from test_historical_script_ownership import source_parts

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-interpreter-reset-contracts.json'


def rows():
    fixture = load_contract_fixture(FIXTURE)
    data = fixture['sources']
    revisions = [row['revision'] for row in data]
    if len(set(revisions)) != len(data) or set(revisions) != contract_revisions(fixture, fixture['expected_revisions']):
        raise ValueError('Own-source reset coverage differs')
    if not set(fixture['boundary_controls']) <= set(revisions):
        raise ValueError('Both reset boundary controls are required')
    for row in data:
        if row['engine'] != '3741' or type(row['revision']) is not int or row['revision'] <= 0:
            raise ValueError('An explicit profile and physical family are required')
        if not re.fullmatch(r'[0-9a-f]{40}', row['commit']) or any(
                not re.fullmatch(r'[0-9a-f]{64}', value) for value in row['source_sha256'].values()):
            raise ValueError('Bound original source identities are required')
        for key in ('clear_reset','reset_flag_present','call_reset_gate','immediate_clears_flag','allocation_magic'):
            if type(row[key]) is not bool:
                raise ValueError('Explicit own-source reset expectations required')
    return data


def interpreter_program(data):
    code = (ROOT / 'src/engines/3741/source/scriptlib/Interpreter.c').read_text()
    functions = '\n'.join(function(code, name) for name in (
        'Interpreter_Reset', 'Interpreter_EvaluateCall', 'Interpreter_EvaluateImmediate'))
    cases = ','.join('{%d,%d,%d,%d}' % (row['revision'], row['reset_flag_present'], row['call_reset_gate'], row['immediate_clears_flag']) for row in data)
    template = Path(__file__).with_name('interpreter_reset_contract.c.in').read_text()
    return template.replace('@FUNCTIONS@', functions).replace('@CASES@', cases)


def clear_program(data):
    parts, options = source_parts()
    code = render(parts, **options)
    marker = 'owner->magic==(1?script_magic:0)'
    if code.count(marker) != 1:
        raise ValueError('The allocation oracle insertion must be unique')
    code = code.replace(marker, 'owner->magic==(fixture_expected_magic?script_magic:0)')
    marker = 'int main(void) {'
    if code.count(marker) != 1:
        raise ValueError('The candidate clear harness must have one main')
    cases = ','.join('{%d,%d,%d}' % (row['revision'], row['clear_reset'], row['allocation_magic']) for row in data)
    return code[:code.index(marker)] + '''
int main(void) {
 const struct {uint32_t revision;int reset,magic;} cases[]={@CASES@};
 for(unsigned i=0;i<sizeof(cases)/sizeof(*cases);++i) {
  obor_profile_build=cases[i].revision;
  expected_reset_before_clear=cases[i].reset;fixture_expected_magic=cases[i].magic;
  direct_checks();container_checks();
 }
 return 0;
}
'''.replace('@CASES@', cases)


class InterpreterResetContracts(unittest.TestCase):
    def run_program(self, program, native_headers):
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
            'clang' in Path(word).name for word in compiler) else []
        library = ROOT / 'src/engines/3741/source/scriptlib'
        includes = [library, library.parent, library.parent / 'gamelib',
                    library.parent / 'preprocessorlib'] if native_headers else []
        with tempfile.TemporaryDirectory(prefix='anybor-interpreter-reset-') as temporary:
            source = Path(temporary) / 'contract.c'
            executable = Path(temporary) / 'contract'
            source.write_text(program)
            subprocess.run(compiler + warnings + ['-std=gnu99','-fsigned-char','-Wall','-Wextra','-Werror',
                '-Wno-unused-variable','-Wno-unused-function','-Wno-error=deprecated-declarations',
                '-DOBOR_ENGINE_BUILD=3741','-fsanitize=address,undefined','-g',
                *('-I'+str(path) for path in includes),str(source),'-o',str(executable)],
                check=True,timeout=45)
            subprocess.run([str(executable)],check=True,timeout=20,env=sanitizer_environment())

    def test_reset_call_and_immediate_functions_by_profile(self):
        self.run_program(interpreter_program(rows()), True)

    def test_clear_entry_resets_and_preserves_own_caller_state(self):
        self.run_program(clear_program(rows()), False)


if __name__ == '__main__':
    unittest.main()
