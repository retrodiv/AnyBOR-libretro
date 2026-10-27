"""Select only the required target packages and retain bounded APT requests.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import contextlib
import io
import sys
import unittest
from unittest.mock import patch

from ci_packages import PACKAGES, apt_commands, main


class CIPackagesTests(unittest.TestCase):
    def test_cross_toolchains_are_exclusive_to_their_consumers(self):
        for role, packages in PACKAGES.items():
            with self.subTest(role=role):
                self.assertEqual(len(packages), len(set(packages)))
                self.assertEqual(any('aarch64-linux-gnu' in p for p in packages), role == 'linux-aarch64')
                self.assertEqual(any('riscv64-linux-gnu' in p for p in packages), role == 'linux-riscv64')
                self.assertEqual(any('mingw' in p for p in packages), role in ('windows-x86_64', 'state-windows'))
                self.assertEqual('ffmpeg' in packages, role == 'state-linux')
                self.assertEqual('wine' in packages, role in ('windows-x86_64', 'state-windows'))
                self.assertEqual('libpng-dev' in packages, role == 'focused')
        self.assertIn('nasm', PACKAGES['linux-x86_64'])
        self.assertIn('nasm', PACKAGES['windows-x86_64'])
        self.assertIn('qemu-user', PACKAGES['linux-riscv64'])

    def test_every_apt_command_uses_network_retries_timeouts_and_lock_limit(self):
        for role in PACKAGES:
            commands = apt_commands(role)
            self.assertEqual(len(commands), 2)
            for cmd in commands:
                self.assertEqual(cmd[:2], ['sudo', 'apt-get'])
                for option in ('Acquire::Retries=3', 'Acquire::http::Timeout=30',
                               'Acquire::https::Timeout=30', 'DPkg::Lock::Timeout=60'):
                    self.assertIn(option, cmd)
            self.assertEqual(commands[0][-1], 'update')
            self.assertIn('--no-install-recommends', commands[1])
            self.assertEqual(commands[1][-len(PACKAGES[role]):], list(PACKAGES[role]))
            self.assertEqual(apt_commands(role, root=True)[0][0], 'apt-get')
        with self.assertRaises(ValueError):
            apt_commands('unknown')

    def test_default_only_prints_commands_without_installing_on_the_host(self):
        with patch.object(sys, 'argv', ['ci_packages.py', '--role', 'linux-aarch64']), \
                patch('ci_packages.subprocess.run') as execute, contextlib.redirect_stdout(io.StringIO()):
            main()
            execute.assert_not_called()

    def test_explicit_install_preserves_failure_and_does_not_run_later_commands(self):
        import subprocess
        with patch.object(sys, 'argv', ['ci_packages.py', '--role', 'focused', '--install']), \
                patch('ci_packages.subprocess.run', side_effect=subprocess.CalledProcessError(100, 'apt-get')) as execute, \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(subprocess.CalledProcessError):
                main()
            self.assertEqual(execute.call_count, 1)


if __name__ == '__main__':
    unittest.main()
