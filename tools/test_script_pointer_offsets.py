"""Check native positional drawing arguments without intermediate array overflow.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import unittest

from test_historical_common_think import ROOT, native_output
from test_historical_player import function


def program(source, profiles):
    code = Path(__file__).with_name('script_pointer_offsets_contract.c.in').read_text()
    setter = function(source, 'openbor_setdrawmethod')
    has_centers = 'LONG value[14];' in setter
    functions = function(source, 'openbor_drawspritetoscreen')
    if has_centers:
        functions += '\n' + setter
    return code.replace('@FUNCTION@', functions).replace('@HAS_CENTERS@', str(int(has_centers))).replace(
        '@PROFILES@', ','.join(str(int(p.get('revision', p['build'].split('-')[0]))) + 'u'
                              for p in profiles))


class ScriptPointerOffsets(unittest.TestCase):
    def test_native_drawing_arguments_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        covered = 0
        for engine in pin['engines']:
            name = str(engine['build'])
            source = (ROOT / 'src/engines' / name / 'openborscript.c').read_text(encoding='latin1')
            with self.subTest(engine=name):
                profiles = [p for p in pin['profiles'] if str(p['engine']) == name]
                self.assertTrue(profiles)
                result = native_output(program(source, profiles), {'engine': name})
                self.assertEqual(json.loads(result), {'status': 'PASS', 'profiles': len(profiles)})
                covered += 1
        self.assertEqual(covered, len(pin['engines']))


if __name__ == '__main__':
    unittest.main()
