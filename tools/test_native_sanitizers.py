"""Check sanitizer capabilities and prevent private per-test leak overrides.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import ast
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from native_sanitizers import sanitizer_environment


class NativeSanitizerTests(unittest.TestCase):
    def test_apple_and_other_hosts_keep_address_checks_without_leak_requests(self):
        for host in ('darwin', 'win32', 'freebsd'):
            with self.subTest(host=host):
                result = sanitizer_environment({}, platform=host)
                self.assertEqual(result['ASAN_OPTIONS'], 'detect_leaks=0:halt_on_error=1')
                self.assertEqual(result['UBSAN_OPTIONS'], 'halt_on_error=1:print_stacktrace=1')

    def test_linux_keeps_leak_detection_and_overrides_inherited_disabling(self):
        result = sanitizer_environment({'ASAN_OPTIONS': 'detect_leaks=0:halt_on_error=0'}, platform='linux')
        self.assertEqual(result['ASAN_OPTIONS'], 'detect_leaks=1:halt_on_error=1')

    def test_inherited_unsupported_requests_are_replaced_and_other_options_survive(self):
        base = {'KEEP': 'value', 'ASAN_OPTIONS': 'verbosity=1:detect_leaks=1:detect_leaks=1:halt_on_error=0',
                'UBSAN_OPTIONS': 'suppressions=/tmp/authored:halt_on_error=0:print_stacktrace=0'}
        original = dict(base)
        result = sanitizer_environment(base, platform='darwin')
        self.assertEqual(result['ASAN_OPTIONS'], 'verbosity=1:detect_leaks=0:halt_on_error=1')
        self.assertEqual(result['UBSAN_OPTIONS'], 'suppressions=/tmp/authored:halt_on_error=1:print_stacktrace=1')
        self.assertEqual(result['KEEP'], 'value')
        self.assertEqual(base, original)

    def test_default_uses_a_copy_of_the_process_environment(self):
        with patch.dict(os.environ, {'ASAN_OPTIONS': 'detect_leaks=1'}, clear=True):
            result = sanitizer_environment(platform='darwin')
            self.assertEqual(os.environ['ASAN_OPTIONS'], 'detect_leaks=1')
            self.assertEqual(result['ASAN_OPTIONS'], 'detect_leaks=0:halt_on_error=1')

    def test_source_tests_use_the_common_policy_for_explicit_sanitizer_environments(self):
        for path in Path(__file__).parent.glob('*.py'):
            if path.name in ('native_sanitizers.py', Path(__file__).name):
                continue
            tree = ast.parse(path.read_text(), filename=str(path))
            overrides = [node for node in ast.walk(tree)
                         if isinstance(node, ast.keyword) and node.arg == 'ASAN_OPTIONS']
            self.assertFalse(overrides, str(path))


if __name__ == '__main__':
    unittest.main()
