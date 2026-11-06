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
        cls.contracts = json.loads(FIXTURE.read_text())['profiles']
        cls.profiles = {row['build']: row for row in json.loads((ROOT/'src/pin.json').read_text())['profiles']}
        files = [ENGINE/'source/gamelib'/name for name in probe.UNITS]
        files += [ENGINE/'source/gamelib/screen.c', ENGINE/'source/gamelib/font.c']
        aware = any(re.search(r'\bobor_(?:profile\w*|active_profile\w*)\b', source.read_text())
                    for source in files)
        cls.results = {}
        if aware:
            revisions = [int(cls.profiles[row['profile']].get('revision', row['profile']))
                         for row in cls.contracts]
            actual = probe.run_profiles(ENGINE, ROOT/'src/port/libretro', revisions)
            blank = probe.run_profiles(ENGINE, ROOT/'src/port/libretro', revisions,
                                       blank_zero=True, dimensions=[[1,1]])
            palette = probe.run_profiles(ENGINE, ROOT/'src/port/libretro', revisions,
                                         palette_validation=True)
            ownership = probe.run_profiles(ENGINE, ROOT/'src/port/libretro', revisions,
                ownership_validation=True, blank_zero=True)
            for contract, revision in zip(cls.contracts, revisions):
                def context(batch):
                    return dict(batch['profiles'][str(revision)],
                        sanitizers_enabled=batch['sanitizers_enabled'],
                        null_offset_oracle_exception=batch['null_offset_oracle_exception'])
                observed = context(actual)
                cls.results[contract['profile']] = dict(actual=observed, blank=context(blank),
                    palette=context(palette), ownership=context(ownership),
                    digest=observed['matrix_sha256'], count=observed['observations'])
        else:
            actual = probe.run(ENGINE, ROOT/'src/port/libretro')
            blank = probe.run(ENGINE, ROOT/'src/port/libretro', blank_zero=True, dimensions=[[1,1]])
            palette = probe.run(ENGINE, ROOT/'src/port/libretro', palette_validation=True)
            shared = dict(actual={k:v for k,v in actual.items() if k!='rows'},
                blank=blank,palette=palette,digest=probe.matrix_digest(actual['rows']),count=len(actual['rows']))
            cls.results = {row['profile']:shared for row in cls.contracts}

    def assert_blank(self, result):
        self.assertFalse(result['null_offset_oracle_exception'])
        self.assertTrue(result['sanitizers_enabled'])
        if 'nonbackground_formats_by_image' in result:
            self.assertEqual(result['nonbackground_formats_by_image'].get('0', []), [])
            self.assertEqual(result['nonbackground_formats_by_image'].get('1', []), [0,2,4])
            return
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

    def test_blank_first_glyph_keeps_truecolor_palettes_safe(self):
        for profile, result in self.results.items():
            with self.subTest(profile=profile):
                self.assert_blank(result['blank'])


def profile_test(contract):
    def check(self):
        data = self.results[contract['profile']]
        self.assert_blank(data['blank'])
        self.assertTrue(data['palette']['sanitizers_enabled'])
        self.assertFalse(data['palette']['null_offset_oracle_exception'])
        self.assertEqual(data['palette'].get('observations',len(data['palette'].get('rows',{}))),18)
        if 'ownership' in data:
            self.assertTrue(data['ownership']['sanitizers_enabled'])
            self.assertFalse(data['ownership']['null_offset_oracle_exception'])
            self.assertEqual(data['ownership']['observations'],15)
        self.assertIn(contract['profile'], self.profiles)
        self.assertEqual(sys.byteorder, 'little', 'Raster byte oracle targets little-endian output')
        self.assertEqual(self.profiles[contract['profile']]['engine'], contract['engine'])
        self.assertFalse(data['actual']['null_offset_oracle_exception'])
        self.assertTrue(data['actual']['sanitizers_enabled'])
        self.assertEqual(data['count'], contract['observations'])
        self.assertEqual(data['digest'], contract['matrix_sha256'], contract['source_reference'])
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
