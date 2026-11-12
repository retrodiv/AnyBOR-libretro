#!/usr/bin/env python3
"""Keep source builds usable without the optional artwork authoring library.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))


class LoadingBackgroundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='anybor-artwork-cache-')
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.tool = ROOT / 'tools/embed_loading_background.py'
        self.glue = ROOT / 'src/glue'
        self.output = self.work / 'generated.h'

    def generate_without_pillow(self, tool, glue):
        # Omit site packages even when the test host has Pillow installed.
        return subprocess.run([sys.executable, '-S', str(tool), '--glue', str(glue),
                               '--output', str(self.output), '--allow-cache'],
                              capture_output=True, text=True, timeout=30)

    def test_precomputed_artwork_builds_without_pillow(self):
        result = self.generate_without_pillow(self.tool, self.glue)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Validated precomputed loading backgrounds', result.stdout)
        self.assertEqual(self.output.read_bytes(),
                         (self.glue / 'anybor_loading_background.h').read_bytes())

    def test_changed_master_rejects_stale_artwork(self):
        glue = self.work / 'glue'
        (glue / 'assets').mkdir(parents=True)
        shutil.copy2(self.glue / 'anybor_loading_background.h', glue)
        master = 'assets/OpenBOR_Logo_3200x1800.png'
        shutil.copy2(self.glue / master, glue / master)
        with (glue / master).open('ab') as stream:
            stream.write(b'changed master input')
        result = self.generate_without_pillow(self.tool, glue)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Pillow is required', result.stderr)
        self.assertFalse(self.output.exists())

    def test_changed_generator_rejects_stale_artwork(self):
        tool = self.work / 'changed-generator.py'
        tool.write_bytes(self.tool.read_bytes() + b'\n# changed generator input\n')
        result = self.generate_without_pillow(tool, self.glue)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Pillow is required', result.stderr)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
