"""Select only the required target packages and retain bounded APT requests.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import contextlib
import io
import sys
import unittest
from unittest.mock import patch

from ci_packages import PACKAGES, apt_commands, bounded_command, install_packages, main


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

    def test_slow_download_recovers_once_before_offline_install(self):
        import subprocess
        failure = subprocess.CalledProcessError(124, 'apt-get')
        with patch('ci_packages.subprocess.run', side_effect=[None, failure, None, None, None]) as execute, \
                patch('ci_packages.platform.freedesktop_os_release', return_value={'ID':'ubuntu','VERSION_CODENAME':'noble'}), \
                contextlib.redirect_stdout(io.StringIO()):
            install_packages('state-windows')
        commands = [call.args[0] for call in execute.call_args_list]
        self.assertEqual(len(commands), 5)
        self.assertIn('--download-only', commands[1])
        self.assertIn('--download-only', commands[3])
        self.assertIn('--no-download', commands[4])
        self.assertTrue(any(option.startswith('Dir::Etc::sourcelist=') for option in commands[2]))
        self.assertFalse(any(option.startswith('Dir::Etc::sourcelist=') for option in commands[0]))
        self.assertIn('180', commands[1]);self.assertIn('240', commands[3])

    def test_install_failure_is_not_retried_or_disguised_as_a_mirror_failure(self):
        import subprocess
        with patch('ci_packages.subprocess.run', side_effect=[None, None, subprocess.CalledProcessError(100,'dpkg')]) as execute:
            with self.assertRaises(subprocess.CalledProcessError):install_packages('focused')
        self.assertEqual(execute.call_count, 3)

    def test_two_acquisition_failures_stop_without_an_install(self):
        import subprocess
        with patch('ci_packages.subprocess.run', side_effect=subprocess.CalledProcessError(124,'apt-get')) as execute, \
                patch('ci_packages.platform.freedesktop_os_release', return_value={'ID':'ubuntu','VERSION_CODENAME':'noble'}), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(subprocess.CalledProcessError):install_packages('focused')
        self.assertEqual(execute.call_count, 2)
        self.assertTrue(all('install' not in call.args[0] for call in execute.call_args_list))

    def test_root_timeout_encloses_the_package_manager(self):
        self.assertEqual(bounded_command(['sudo','apt-get','update'],60),
                         ['sudo','timeout','--kill-after=5s','60','apt-get','update'])
        self.assertEqual(bounded_command(['apt-get','update'],60),
                         ['timeout','--kill-after=5s','60','apt-get','update'])


if __name__ == '__main__':
    unittest.main()
