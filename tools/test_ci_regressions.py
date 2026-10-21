"""Ensure the macOS regression block reports every failed command.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import unittest

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))


class RegressionCollectionTests(unittest.TestCase):
    def run_block(self, failed):
        workflow = (ROOT/'.github/workflows/ci.yml').read_text()
        job = workflow.split('\n  macos-regressions:\n', 1)[1]
        block = job.split('      - name: Exercise native runtime regressions\n', 1)[1].split('      - ', 1)[0]
        self.assertIn('shell: bash', block)
        script = block.split('        run: |\n', 1)[1]
        lines = [line[10:] for line in script.splitlines()]
        commands = [i for i, line in enumerate(lines) if line.startswith('run_check python3 ')]
        self.assertGreater(len(commands), 10)
        # Execute the actual control structure with small stand-ins. The first
        # failure must not prevent a second failure or the final observation.
        for number, index in enumerate(commands):
            code = 'print("observed %d"); raise SystemExit(%d)' % (number, 1 if number in failed else 0)
            lines[index] = 'run_check ' + shlex.join([sys.executable, '-c', code])
        result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', '\n'.join(lines)],
                                capture_output=True, text=True, timeout=20)
        for number in range(len(commands)):
            self.assertIn('observed %d\n' % number, result.stdout)
        return result

    @unittest.skipUnless(shutil.which('bash'), 'Needs the workflow Bash interpreter')
    def test_collects_multiple_failures_and_finishes_unsuccessfully(self):
        result = self.run_block({0, 2})
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('Failed regression commands (2):', result.stdout)

    @unittest.skipUnless(shutil.which('bash'), 'Needs the workflow Bash interpreter')
    def test_succeeds_only_when_every_command_succeeds(self):
        result = self.run_block(set())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('Failed regression commands', result.stdout)


if __name__ == '__main__':
    unittest.main()
