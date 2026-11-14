"""Compile the complete path implementation with incomplete Linux headers.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from runtime_evidence import record_process

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
PORT = Path(os.environ.get('OBOR_TEST_PORT', ROOT / 'src/port/libretro'))
VALUES = {
    'XFS_SUPER_MAGIC': 0x58465342,
    'F2FS_SUPER_MAGIC': 0xF2F52010,
    'OVERLAYFS_SUPER_MAGIC': 0x794C7630,
    'FUSE_SUPER_MAGIC': 0x65735546,
}
# The other filesystem identifiers used by the complete translation unit.
BASE = {
    'EXT2_SUPER_MAGIC': 0xEF53,
    'TMPFS_MAGIC': 0x01021994,
    'BTRFS_SUPER_MAGIC': 0x9123683E,
    'MSDOS_SUPER_MAGIC': 0x4D44,
    'PROC_SUPER_MAGIC': 0x9FA0,
}


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux kernel headers')
class LinuxHeaderCompatibilityTests(unittest.TestCase):
    def compile_with_header(self, supplied, expected):
        source = PORT / 'anybor_paths.c'
        with tempfile.TemporaryDirectory(prefix='linux-header-compat-') as temporary:
            work = Path(temporary)
            header = work / 'linux/magic.h'
            header.parent.mkdir()
            header.write_text(''.join(
                '#define %s 0x%x\n' % pair
                for pair in {**BASE, **supplied}.items()))
            probe = work / 'probe.c'
            # Include the actual, unmodified unit rather than an extracted body.
            probe.write_text('#include "anybor_paths.c"\n' + ''.join(
                '_Static_assert(%s == 0x%x, "%s");\n' % (name, value, name)
                for name, value in expected.items()))
            compiler = shlex.split(os.environ.get('CC', 'cc'))
            result = subprocess.run(
                [*compiler, '-std=c11', '-Wall', '-Wextra', '-Werror',
                 '-I', str(work), '-I', str(PORT), '-c', str(probe),
                 '-o', str(work / 'probe.o')],
                capture_output=True, text=True, timeout=60)
            record_process('linux-header-compat', self._testMethodName, result,
                           dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                                compiler=compiler, supplied=supplied, expected=expected))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((work / 'probe.o').is_file())

    def test_all_missing_constants_have_kernel_values(self):
        self.compile_with_header({}, VALUES)

    def test_each_constant_can_be_missing_independently(self):
        for absent in VALUES:
            with self.subTest(absent=absent):
                self.compile_with_header(
                    {name: value for name, value in VALUES.items() if name != absent},
                    VALUES)

    def test_existing_header_definitions_are_preserved(self):
        # Distinct sentinels also catch an unconditional replacement by the
        # expected kernel values, independently of redefinition warnings.
        sentinels = {name: 0x12340000 + index for index, name in enumerate(VALUES)}
        self.compile_with_header(sentinels, sentinels)


if __name__ == '__main__':
    unittest.main()
