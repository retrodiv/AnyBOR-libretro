"""Check native PNG writer ownership and unchanged RGB rows.

The real pinned public PNG headers declare bounded service providers. They do
not encode PNG files; codec bytes and filesystem behavior have separate tests.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from test_historical_common_think import ROOT, native_output
from test_historical_player import function


HERE = Path(__file__).resolve().parent


def program(source, profiles):
    code = (HERE / 'png_writer_ownership_contract.c.in').read_text()
    return code.replace('@SAVEPNG@', function(source, 'savepng')).replace(
        '@PROFILES@', ','.join(str(int(p.get('revision', p['build'].split('-')[0]))) + 'u'
                              for p in profiles))


class PngWriterOwnershipTests(unittest.TestCase):
    def test_native_resources_and_rgb_rows_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        dependency = ROOT / 'src/deps/libpng'
        with tempfile.TemporaryDirectory(prefix='anybor-png-public-headers-') as temporary:
            headers = Path(temporary)
            # Use only preserved public headers/configuration, never an
            # undeclared installed host PNG SDK.
            for name, original in (('fixture_png.h', 'png.h'), ('pngconf.h', 'pngconf.h'),
                                   ('pnglibconf.h', 'scripts/pnglibconf.h.prebuilt')):
                shutil.copyfile(dependency / original, headers / name)
            for entry in pin['engines']:
                engine = entry['build']
                source = (ROOT / 'src/engines' / engine / 'source/pnglib/savepng.c').read_text(encoding='latin1')
                profiles = [p for p in pin['profiles'] if p['engine'] == engine]
                self.assertTrue(profiles)
                with self.subTest(engine=engine):
                    result = native_output(program(source, profiles), {'engine': engine},
                                           extra_includes=[headers])
                    self.assertEqual(json.loads(result), dict(status='PASS', profiles=len(profiles),
                                                             cases=20 * len(profiles)))


if __name__ == '__main__':
    unittest.main()
