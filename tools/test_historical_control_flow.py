"""Check loop compiler labels and grammar membership against own-source contracts.

Token/expression/body providers expose the actual iteration compiler's trace;
this does not execute the VM or establish complete script compilation.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from native_sanitizers import sanitizer_environment
from test_historical_player import function

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).with_name('fixtures') / 'profile-parser-control-flow.json'


def program(rows):
    library = ROOT / 'src/engines/3741/source/scriptlib'
    code = (library / 'Parser.c').read_text()
    implementation = function(code, 'Parser_Iter_stmt')
    jumps = function(code, 'Parser_Jump_stmt')
    source = Path(__file__).with_name('parser_control_flow_contract.c.in').read_text()
    cases = ',\n'.join('{'+','.join(str(int(row[key])) for key in (
        'revision', 'continue_supported', 'while_false_repeats',
        'while_continue_resolved', 'first_continue_entries', 'follow_continue_entries'))+'}' for row in rows)
    return source.replace('@ITERATION@', implementation).replace('@JUMPS@', jumps).replace('@CASES@', cases)


class HistoricalControlFlow(unittest.TestCase):
    def test_own_profile_loop_targets_and_continue_grammar(self):
        fixture = load_contract_fixture(FIXTURE)
        rows = fixture['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(len(set(revisions)), len(rows))
        self.assertEqual(set(revisions), contract_revisions(fixture, fixture['expected_revisions']))
        self.assertTrue(set(fixture['boundary_controls']) <= set(revisions))
        for row in rows:
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for digest in row['source_sha256'].values():
                self.assertRegex(digest, r'^[0-9a-f]{64}$')
        library = ROOT / 'src/engines/3741/source/scriptlib'
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        warnings = ['-Wno-pragma-pack'] if sys.platform == 'darwin' or any(
            'clang' in Path(word).name for word in compiler) else []
        with tempfile.TemporaryDirectory(prefix='anybor-control-flow-') as temporary:
            source = Path(temporary) / 'contract.c'
            executable = Path(temporary) / 'contract'
            source.write_text(program(rows))
            subprocess.run(compiler + warnings + ['-DOBOR_ENGINE_BUILD=3741', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                '-Wno-unused-variable', '-Wno-error=deprecated-declarations',
                '-Wno-error=sign-compare',
                '-Wno-unknown-pragmas', '-Wno-unused-parameter',
                '-fsanitize=address,undefined', '-g', '-fno-omit-frame-pointer',
                *('-I'+str(path) for path in (library, library.parent,
                    library.parent / 'gamelib', library.parent / 'preprocessorlib')),
                str(source), str(library / 'List.c'), str(library / 'Stack.c'),
                '-o', str(executable)], check=True, timeout=45)
            subprocess.run([str(executable)], check=True, timeout=15,
                           env=sanitizer_environment())


if __name__ == '__main__':
    unittest.main()
