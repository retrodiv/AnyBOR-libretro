"""Check native frame-entry validation before delegated frame processing.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from test_draw_method_bounds import diagnostic_profiles, program as draw_program
from test_historical_player import function
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


def program(engine, profiles, *, release=False, remove_guard=False):
    source = (engine / 'openbor.c').read_text(encoding='latin1')
    native = function(source, 'update_frame')
    if '//important!' not in native:
        raise ValueError('Native frame-context entry marker required')
    prefix, _ = native.split('//important!', 1)
    signature = re.search(r'update_frame\(entity\s*\*\s*ent, (int|unsigned int|uint64_t) f\)', prefix)
    if signature is None:
        raise ValueError('Actual bounded native frame argument type required')
    if remove_guard:
        if prefix.count('f < 0 || ') != 1:
            raise ValueError('One explicit signed frame-input guard required')
        prefix = prefix.replace('f < 0 || ', '', 1)
    defaults = ''
    if 'emptyattack' in prefix:
        matches = re.findall(r'(?ms)^const s_attack emptyattack\s*=\s*\{.*?^\};', source)
        if len(matches) != 1:
            raise ValueError('Actual native default attack initializer required')
        defaults = matches[0]
    # Reuse native records, assertion providers and controlled port exit from
    # the drawing fixture. Its case/main driver is replaced by this entry probe.
    code = draw_program(engine, profiles, release=release)
    marker = 'int main(void) {'
    if code.count(marker) != 1:
        raise ValueError('One bounded drawing-fixture entry point required')
    code = code[:code.index(marker)]
    code += '\n'+defaults+'\n'+'''
entity *self;
static entity subject,other;
static unsigned entered;
static uint64_t entered_frame;
'''
    # Only the native preamble executes here. The entry observer replaces the
    # frame processing that follows it; whole-caller suites remain separate.
    code += prefix + '\n++entered;entered_frame=(uint64_t)f;\n}\n'
    values = dict(TYPE=signature[1],
                  LARGE='UINT64_MAX' if signature[1] == 'uint64_t' else
                        'UINT_MAX' if signature[1] == 'unsigned int' else 'INT_MAX')
    driver = (HERE / 'frame_input_bounds.c.in').read_text()
    for key, value in values.items():
        driver = driver.replace('@'+key+'@', value)
    return code + driver


class FrameInputBoundsTests(unittest.TestCase):
    def test_frame_entry_in_each_profile_and_assertion_mode(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for row in pin['engines']:
            profiles = [p for p in diagnostic_profiles(pin) if p['engine'] == row['build']]
            engine = ROOT / 'src/engines' / row['build']
            for release in (False, True):
                with self.subTest(engine=row['build'], release=release):
                    result = run_native(engine, program(engine, profiles, release=release))
                    self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                    self.assertEqual(json.loads(result.stdout),
                                     dict(profiles=len(profiles), cases=12*len(profiles)))

    def test_missing_signed_input_guard_is_detected(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            frame = function((engine / 'openbor.c').read_text(encoding='latin1'), 'update_frame')
            if 'f < 0 || ' in frame.split('//important!')[0]:
                profile = next(p for p in diagnostic_profiles(pin) if p['engine'] == row['build'])
                result = run_native(engine, program(engine, [profile], release=True, remove_guard=True))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('frame input contract', result.stderr)
                return
        self.fail('No native signed frame-entry guard found')


if __name__ == '__main__':
    unittest.main()
