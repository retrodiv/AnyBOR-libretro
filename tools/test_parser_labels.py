"""Check native parser missing-label refusal and unchanged valid dispatch.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import unittest

from test_historical_common_think import ROOT, native_output
from test_historical_player import function


HERE = Path(__file__).resolve().parent


def program(engine, profiles):
    parser = (engine / 'source/scriptlib/Parser.c').read_text(encoding='latin1')
    text = (HERE / 'parser_labels_contract.c.in').read_text()
    text = text.replace('@ADDER@', function(parser, 'Parser_AddInstructionViaLabel'))
    return text.replace('@PROFILES@', ','.join(
        str(int(p.get('revision', p['build'].split('-')[0]))) + 'u' for p in profiles))


class ParserLabelTests(unittest.TestCase):
    def test_missing_empty_named_targets_and_error_state_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for engine in pin['engines']:
            build = engine['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == build]
            self.assertTrue(profiles)
            with self.subTest(engine=build):
                result = json.loads(native_output(program(ROOT / 'src/engines' / build, profiles),
                                                  {'engine': build}))
                self.assertEqual(result, dict(status='PASS', profiles=len(profiles),
                                              cases=36 * len(profiles)))


if __name__ == '__main__':
    unittest.main()
