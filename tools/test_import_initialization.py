"""Check native import construction, refusal diagnostics and owned cleanup.

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
ENGINES = ('3400', '3741', '3842', '4086', '4432', '6391', '7142', '7533', '8023')


def program(engine, profiles):
    source = (engine / 'source/scriptlib/ImportCache.c').read_text(encoding='latin1')
    declaration = re.search(r'(?ms)^struct ImportNode\s*\{.*?^\};', source)
    has_functions = declaration is not None
    text = (HERE / 'import_initialization_contract.c.in').read_text()
    parts = dict(NODE=declaration[0] if has_functions else '',
                 HAS_FUNCTIONS=str(int(has_functions)),
                 EARLY_REFUSAL=str(int(engine.name not in ('3400', '3741', '3842'))),
                 ENGINE=engine.name, INIT=function(source, 'ImportNode_Init'),
                 PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0]))) + 'u'
                                   for p in profiles))
    for name, value in parts.items():
        text = text.replace('@' + name + '@', value)
    return text


class ImportInitializationTests(unittest.TestCase):
    def test_native_success_and_refusal_preserve_owners_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for build in ENGINES:
            profiles = [p for p in pin['profiles'] if p['engine'] == build]
            self.assertTrue(profiles)
            with self.subTest(engine=build):
                result = json.loads(native_output(program(ROOT / 'src/engines' / build, profiles),
                                                  {'engine': build}))
                self.assertEqual(result, dict(status='PASS', profiles=len(profiles),
                                              cases=10 * len(profiles)))


if __name__ == '__main__':
    unittest.main()
