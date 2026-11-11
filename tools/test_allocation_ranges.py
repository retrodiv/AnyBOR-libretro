"""Check live allocation ranges using the complete pinned allocator.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import tempfile
import unittest

from native_sanitizers import sanitizer_environment


HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


@unittest.skipUnless(sys.platform.startswith('linux') and platform.machine() in ('x86_64', 'AMD64'),
                     'The real-arena sanitizer fixture requires Linux x86-64')
class AllocationRangeTests(unittest.TestCase):
    def run_allocator(self, native):
        port = ROOT / 'src/port/libretro'
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        self.assertEqual(hashlib.sha256((port / 'dlmalloc.inc').read_bytes()).hexdigest(),
                         pin['deps']['dlmalloc']['sha256'])
        compiler = shlex.split(os.environ.get('HOST_CC', 'cc'))
        with tempfile.TemporaryDirectory(prefix='allocation-ranges-') as name:
            work = Path(name)
            source, binary = work / 'probe.c', work / 'probe'
            source.write_bytes((HERE / 'allocation_ranges_contract.c.in').read_bytes())
            flags = ['-fsanitize=undefined', '-DOBOR_TEST_NATIVE_ARENA=1'] if native else [
                '-fsanitize=address,undefined']
            command = compiler + ['-std=gnu99', '-O1', '-g', '-pthread',
                '-ffunction-sections', '-fdata-sections', '-fno-sanitize-recover=all',
                *flags, '-I' + str(port), '-I' + str(ROOT / 'src/glue'),
                str(source), '-Wl,--gc-sections', '-o', str(binary)]
            subprocess.run(command, check=True, timeout=60)
            result = subprocess.check_output([str(binary)], text=True, timeout=30,
                                             env=sanitizer_environment())
            self.assertEqual(result.strip(), 'PASS allocation ranges: ' + ('native' if native else 'asan-fixture'))

    def test_native_arena_and_previous_contains_contract(self):
        self.run_allocator(True)

    def test_real_allocator_with_address_and_undefined_sanitizers(self):
        self.run_allocator(False)


if __name__ == '__main__':
    unittest.main()
