"""Check fixed remap flags with native records, loader and command body.

Bitmap I/O and allocation refusal are bounded providers. Full parsing, palette
decoding and model destruction retain their separate controls.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from test_historical_player import function, rename_identifiers, switch_cases
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


def fixed_families(pin):
    result = []
    for row in pin['engines']:
        engine = ROOT / 'src/engines' / row['build']
        loader = function((engine / 'openbor.c').read_text(encoding='latin1'), 'load_cached_model')
        if re.search(r'unsigned char\s+mapflag\[MAX_COLOUR_MAPS\]', loader):
            result.append(row)
    if not result:
        raise ValueError('No native fixed remap flag table found')
    return result


def program(engine, profiles, *, remove_guard=False):
    source = (engine / 'openbor.c').read_text(encoding='latin1')
    header = (engine / 'openbor.h').read_text(encoding='latin1')
    loader = function(source, 'load_cached_model')
    loader = loader.replace('switch(cmd)', 'switch(fixture_model_command)', 1)
    _, cases = switch_cases(loader, 'load_cached_model', 'fixture_model_command')
    case = cases['CMD_MODEL_REMAP']['body']
    guard = 'if(newchar->maps_loaded > 0 && newchar->maps_loaded <= MAX_COLOUR_MAPS)'
    if case.count(guard) != 1:
        raise ValueError('One fixed remap table guard required')
    if remove_guard:
        case = case.replace(guard, '(void)0;', 1)
    macro = re.search(r'(?m)^#define OBOR_MODEL_ERROR\([^\n]*\n[^\n]+', source)
    storage = re.findall(r'(?m)^\s*char legacy_model_error\[[^\n;]+;', loader)
    limit = re.search(r'(?m)^#define\s+MAX_COLOUR_MAPS\s+([0-9]+)\b', header)
    if macro is None or len(storage) != 1 or limit is None:
        raise ValueError('Native diagnostic storage/macro and fixed extent required')
    parts = dict(
        MODEL_ERROR=function(source, 'obor_model_error')+'\n'+macro[0],
        LOADER=rename_identifiers(function(source, 'load_colourmap'),
                                  {'load_colourmap': 'native_load_colourmap'}),
        CASE=case, ERROR_STORAGE=storage[0],
        PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u'
                          for p in profiles))
    text = (HERE / 'remap_flag_bounds.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    return text, (int(limit[1])+1)*6+3


class RemapFlagBoundsTests(unittest.TestCase):
    def test_refusal_flags_diagnostics_and_success_in_every_fixed_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for row in fixed_families(pin):
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
            engine = ROOT / 'src/engines' / row['build']
            with self.subTest(engine=row['build']):
                text, cases = program(engine, profiles)
                result = run_native(engine, text)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                self.assertEqual(json.loads(result.stdout),
                                 dict(profiles=len(profiles), cases=cases*len(profiles)))

    def test_missing_flag_guard_is_detected(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        row = fixed_families(pin)[0]
        engine = ROOT / 'src/engines' / row['build']
        profile = next(p for p in pin['profiles'] if p['engine'] == row['build'])
        text, _ = program(engine, [profile], remove_guard=True)
        # Extra physical backing bounds this control; the logical flag-table
        # sentinel must reject the old write independently of a crash.
        result = run_native(engine, text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('remap flag contract', result.stderr)


if __name__ == '__main__':
    unittest.main()
