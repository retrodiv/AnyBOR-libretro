"""Check fitting native literal prefixes and defined capacity refusal.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import unittest

from test_historical_common_think import ROOT, native_output
from test_historical_player import function


HERE = Path(__file__).resolve().parent
ENGINES = ('3842', '4086', '4432', '6391', '7142', '7533', '8023')


def program(engine, profiles):
    parser = (engine / 'source/scriptlib/Parser.c').read_text(encoding='latin1')
    text = (HERE / 'parser_token_prefix_contract.c.in').read_text()
    text = text.replace('@PREFIX@', function(parser, 'obor_parser_prefix_token'))
    return text.replace('@PROFILES@', ','.join(
        str(int(p.get('revision', p['build'].split('-')[0]))) + 'u' for p in profiles))


class ParserTokenPrefixTests(unittest.TestCase):
    def test_native_token_bytes_and_capacity_boundaries_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for build in ENGINES:
            profiles = [p for p in pin['profiles'] if p['engine'] == build]
            self.assertTrue(profiles)
            with self.subTest(engine=build):
                result = json.loads(native_output(program(ROOT / 'src/engines' / build, profiles),
                                                  {'engine': build}))
                self.assertEqual(result, dict(status='PASS', profiles=len(profiles),
                                              cases=24 * len(profiles)))


if __name__ == '__main__':
    unittest.main()
