"""Check native script initialization results and current-script ownership.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import unittest

from test_historical_common_think import ROOT, native_output
from test_historical_player import function


def program(source, profiles, engine):
    code = Path(__file__).with_name('script_initialization_contract.c.in').read_text()
    revisions = ','.join(str(int(p.get('revision', p['build'].split('-')[0]))) + 'u' for p in profiles)
    # Own-source contracts: classic current-script selection, then its removal;
    # the newest family declares a boolean result instead of the stored integer.
    selects = '1' if engine == '3400' else 'obor_profile_build < 3536u' if engine == '3741' else '0'
    return code.replace('@FUNCTION@', function(source, 'Script_IsInitialized')).replace(
        '@PROFILES@', revisions).replace('@SELECTS_CURRENT@', selects).replace(
        '@BOOLEAN_RESULT@', str(int(engine == '8023')))


class ScriptInitializationTests(unittest.TestCase):
    def test_native_values_null_input_and_current_script_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for entry in pin['engines']:
            engine = entry['build']
            source = (ROOT / 'src/engines' / engine / 'openborscript.c').read_text(encoding='latin1')
            profiles = [p for p in pin['profiles'] if p['engine'] == engine]
            self.assertTrue(profiles)
            with self.subTest(engine=engine):
                result = native_output(program(source, profiles, engine), {'engine': engine})
                self.assertEqual(json.loads(result), {'status': 'PASS', 'profiles': len(profiles)})


if __name__ == '__main__':
    unittest.main()
