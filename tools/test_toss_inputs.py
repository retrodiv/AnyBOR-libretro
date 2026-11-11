"""Validate toss arguments while retaining native nullable/error/default rules.

Complete native entries, variants and real entity records run with an observing
toss callback. Generic pointer tags are not entity provenance or lifetime proof;
those concerns remain separate from this argument-representation control.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture
from test_historical_player import function, rename_identifiers
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))
FIXTURE = HERE / 'fixtures/toss-native-baseline.json'


def program(engine, profiles, *, reject_actor=False):
    core = (engine / 'openborscript.c').read_text(encoding='latin1')
    variant_path, = (engine / 'source').rglob('ScriptVariant.c')
    variants = variant_path.read_text(encoding='latin1')
    header = variant_path.with_suffix('.h').read_text(encoding='latin1')
    oracle = load_contract_fixture(FIXTURE)
    data = oracle['engines'][engine.name]
    entry = function(core, 'openbor_tossentity')
    tag = 'varlist[0]->vt == VT_PTR'
    if entry.count(tag) != 1:
        raise ValueError('One native handle representation check required')
    if reject_actor:
        entry = entry.replace(tag, '(' + tag + ' && !varlist[0]->ptrVal)', 1)
    context = []
    for p in profiles:
        row = oracle['profiles'][p['build']]
        context.append('{%du,%d,%d}' % (row['revision'], row['null_handle_is_nonfatal_false'],
                                       row['failed_numeric_conversion_is_nonfatal_false']))
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        SCRIPT_HEADER='openborscript.h' if (engine / 'openborscript.h').is_file() else 'scriptcommon.h',
        POP_ARGUMENTS='int length' if 'StrCache_Pop(int length)' in header else 'void',
        POP_UNUSED='(void)length;' if 'StrCache_Pop(int length)' in header else '',
        CONVERSIONS='\n'.join(function(variants, n) for n in
            ['ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_DecimalValue']),
        ORIGINAL_DECIMAL=rename_identifiers(data['decimal'], {'ScriptVariant_DecimalValue': 'original_decimal'}),
        ORIGINAL_TOSS=rename_identifiers(data['toss'], {
            'openbor_tossentity': 'original_toss', 'ScriptVariant_DecimalValue': 'original_decimal'}),
        NULL_FACTORY=function(core, 'system_NULL'), ENTRY=entry,
        VX='velocity.x' if 'ent->velocity.x' in entry else 'xdir',
        VZ='velocity.z' if 'ent->velocity.z' in entry else 'zdir',
        HAS_WIDE=str(int('VT_INTEGER64' in function(variants, 'ScriptVariant_DecimalValue'))),
        CONTEXTS=','.join(context))
    text = (HERE / 'toss_inputs.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved toss fixture input')
    return text


class TossInputTests(unittest.TestCase):
    def test_nullable_handles_conversions_results_and_missing_cells_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        oracle = load_contract_fixture(FIXTURE)
        self.assertEqual(set(oracle['profiles']), {p['build'] for p in pin['profiles']})
        for entry in pin['engines']:
            engine = ROOT / 'src/engines' / entry['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == engine.name]
            with self.subTest(engine=engine.name):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                per_profile = 386 + 2 * int('VT_INTEGER64' in oracle['engines'][engine.name]['decimal'])
                self.assertEqual(value['cases'], per_profile * len(profiles))

    def test_genuine_typed_actor_is_not_refused(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        entry = pin['engines'][0]
        engine = ROOT / 'src/engines' / entry['build']
        profile = next(p for p in pin['profiles'] if p['engine'] == engine.name)
        result = run_native(engine, '#define ACTOR_ONLY 1\n' + program(engine, [profile], reject_actor=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('actual.result.lVal == expected.result.lVal', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
