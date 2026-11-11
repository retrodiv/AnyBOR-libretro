"""Compare bounded text conversion with each native formatter's valid output.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import unittest

from test_historical_common_think import ROOT, native_output
from test_historical_player import function


HERE = Path(__file__).resolve().parent
ENGINES = ('6391', '7142', '7533')


def program(engine, profiles):
    script = (engine / 'openborscript.c').read_text(encoding='latin1')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin1')
    original = function(variant, 'ScriptVariant_ToString').replace(
        'ScriptVariant_ToString(', 'fixture_original_format(', 1)
    code = (HERE / 'text_object_values_contract.c.in').read_text()
    parts = dict(STORE=function(script, 'obor_textobj_store'),
                 FORMAT=function(script, 'obor_textobj_format'), ORIGINAL=original,
                 PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0]))) + 'u'
                                   for p in profiles))
    for name, value in parts.items():
        code = code.replace('@' + name + '@', value)
    return code


class NativeTextValueTests(unittest.TestCase):
    def test_fitting_formats_padding_and_defined_refusal_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for build in ENGINES:
            profiles = [p for p in pin['profiles'] if p['engine'] == build]
            self.assertTrue(profiles)
            with self.subTest(engine=build):
                output = native_output(program(ROOT / 'src/engines' / build, profiles),
                                       {'engine': build})
                self.assertEqual(json.loads(output), dict(status='PASS', profiles=len(profiles),
                                                          cases=25 * len(profiles)))


if __name__ == '__main__':
    unittest.main()
