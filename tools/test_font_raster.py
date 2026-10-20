"""Keep each historical font profile bound to its own original raster oracle.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import hashlib
import os
from pathlib import Path
import re
import sys
import unittest
import font_raster_probe as probe

ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', Path(__file__).resolve().parents[1]))
ENGINE = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT/'src/engines/3842'))
FIXTURE = Path(__file__).with_name('font-raster-contracts.json')


class FontRasterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # These sources currently have one profile-independent font path. Do
        # not silently reuse its result if a later change adds profile gates.
        files = [ENGINE/'source/gamelib'/name for name in probe.UNITS]
        files += [ENGINE/'source/gamelib/screen.c', ENGINE/'source/gamelib/font.c']
        for source in files:
            if re.search(r'\bobor_(?:profile\w*|active_profile\w*)\b', source.read_text()):
                raise AssertionError('Profile-aware raster code needs per-profile probe execution: ' + str(source))
        cls.actual = probe.run(ENGINE, ROOT/'src/port/libretro')
        cls.blank = probe.run(ENGINE, ROOT/'src/port/libretro', blank_zero=True, dimensions=[[1, 1]])
        cls.palette = probe.run(ENGINE, ROOT/'src/port/libretro', palette_validation=True)
        cls.digest = probe.matrix_digest(cls.actual['rows'])
        cls.count = len(cls.actual['rows'])
        # Keep only the digest after parsing the byte-derived observations.
        cls.actual = {k: v for k, v in cls.actual.items() if k != 'rows'}
        cls.profiles = {row['build']: row for row in json.loads((ROOT/'src/pin.json').read_text())['profiles']}

    def test_blank_first_glyph_keeps_truecolor_palettes_safe(self):
        result = self.blank
        self.assertFalse(result['null_offset_oracle_exception'])
        self.assertTrue(result['sanitizers_enabled'])
        nonempty_formats = set()
        for key, row in result['rows'].items():
            if not key.startswith('RASTER '):
                continue
            fields = key.split()
            background = hashlib.sha256(b'\x6d'*row['bytes']).hexdigest()
            if fields[4] == '0':
                self.assertEqual(row['sha256'], background, key)
            elif row['sha256'] != background:
                nonempty_formats.add(int(fields[2]))
        self.assertEqual(nonempty_formats, {0, 2, 4})


def profile_test(contract):
    def check(self):
        self.test_blank_first_glyph_keeps_truecolor_palettes_safe()
        self.assertTrue(self.palette['sanitizers_enabled'])
        self.assertFalse(self.palette['null_offset_oracle_exception'])
        self.assertEqual(len(self.palette['rows']), 18)
        self.assertIn(contract['profile'], self.profiles)
        self.assertEqual(sys.byteorder, 'little', 'Raster byte oracle targets little-endian output')
        self.assertEqual(self.profiles[contract['profile']]['engine'], contract['engine'])
        self.assertFalse(self.actual['null_offset_oracle_exception'])
        self.assertTrue(self.actual['sanitizers_enabled'])
        self.assertEqual(self.count, contract['observations'])
        self.assertEqual(self.digest, contract['matrix_sha256'], contract['source_reference'])
    return check


if FIXTURE.is_file():
    for _contract in json.loads(FIXTURE.read_text())['profiles']:
        setattr(FontRasterTests, 'test_profile_' + _contract['profile'], profile_test(_contract))
else:
    def missing_contract(self):
        self.fail('Missing own-source font raster contracts')
    FontRasterTests.test_missing_contract = missing_contract


if __name__ == '__main__':
    unittest.main()
