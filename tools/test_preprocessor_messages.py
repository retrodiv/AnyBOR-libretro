"""Check native compiler messages with bounded formatting and exact fitting text.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from test_historical_common_think import ROOT, native_output
from test_historical_player import function


HERE = Path(__file__).resolve().parent


def program(engine, profiles):
    source = (engine / 'source/preprocessorlib/pp_parser.c').read_text(encoding='latin1')
    error, warning = (function(source, n) for n in ('pp_error', 'pp_warning'))
    capacities = [int(re.search(r'char\s+buf\[(\d+)\]', f)[1]) for f in (error, warning)]
    if capacities[0] != capacities[1] or not 32 <= capacities[0] <= 8192:
        raise ValueError('Shared bounded native message capacity required')
    text = (HERE / 'preprocessor_messages_contract.c.in').read_text()
    parts = dict(ERROR=error, WARNING=warning, CAPACITY=str(capacities[0]),
                 PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0]))) + 'u'
                                   for p in profiles))
    for name, value in parts.items():
        text = text.replace('@' + name + '@', value)
    return text


class PreprocessorMessageTests(unittest.TestCase):
    def test_fitting_text_and_bounded_long_diagnostics_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for engine in pin['engines']:
            build = engine['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == build]
            self.assertTrue(profiles)
            with self.subTest(engine=build):
                result = json.loads(native_output(program(ROOT / 'src/engines' / build, profiles),
                                                  {'engine': build}))
                self.assertEqual(result, dict(status='PASS', profiles=len(profiles),
                                              cases=24 * len(profiles)))


if __name__ == '__main__':
    unittest.main()
