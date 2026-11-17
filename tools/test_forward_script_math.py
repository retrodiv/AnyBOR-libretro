"""Check native script math availability, angle units and numeric oddities.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import math
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-script-math-contracts.json'
NAMES = ('sin', 'ssin', 'cos', 'scos', 'sqrt', 'pow', 'asin', 'acos', 'atan')


def program(data, engine):
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    methods = '\n'.join(function(source, name) for name in
                        ('Script_GetFunctionName', 'Script_LoadSystemFunctions'))
    symbols = set(re.findall(r'\(\s*void\s*\*\s*\)\s*(\w+)', methods))
    callbacks = {'math_' + name for name in NAMES}
    if not callbacks <= symbols or not 9 <= len(symbols) <= 512:
        raise ValueError('Complete bounded registry and native math symbols required')
    tables = []
    for name in ('sin', 'cos'):
        match = re.search(r'(?m)^float ' + name + r'_table\[\][\s\S]*?^};', utils)
        if match is None:
            raise ValueError('Native integer-angle lookup table required')
        tables.append(match[0])
    pieces = dict(
        MATH_UNIT='#include ' + json.dumps(str(engine / 'source/omath.c')),
        STUBS='\n'.join('static void '+name+'(void){}' for name in sorted(symbols-callbacks)),
        VARIANTS='\n'.join(function(variant, name) for name in
                           ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
                            'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        NUMERIC='\n'.join(tables) + '\n' + function(utils, 'invsqrt') + '\n' +
                '\n'.join(function(source, 'math_' + name) for name in NAMES),
        METHODS=methods,
        CALLBACKS=','.join('math_' + name for name in NAMES),
        NAMES=','.join(json.dumps(name) for name in NAMES),
        CONTEXTS=','.join('{%d,%d,%d}' %
                         (row['revision'], row['available'], row['degrees'])
                         for row in data['sources']),
        CASES=','.join('{%d,%s,%s,%d}' % (NAMES.index(row['name']), row['a'],
                        row.get('b', '0x0p+0'), row['integer']) for row in data['cases']))
    text = Path(__file__).with_name('forward_script_math_contract.c.in').read_text()
    for key, value in pieces.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native mathematical API dependency')
    return text


class ForwardScriptMathTests(unittest.TestCase):
    def test_native_registry_conversions_units_and_results(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for profile in contract_profiles(data, pin['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        for row in data['sources']:
            self.assertEqual(row['engine'], data['engine'])
            self.assertIs(type(row['available']), bool)
            self.assertIs(type(row['degrees']), bool)
            self.assertFalse(row['degrees'] and not row['available'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['source_sha256'], r'^[0-9a-f]{64}$')
        engine = Path(os.environ.get('OBOR_SCRIPT_MATH_ENGINE',
                                     ROOT / 'src/engines' / data['engine']))
        output = native_output(program(data, engine), data, extra_includes=(engine / 'source',),
                               libraries=('m',))
        actual = [json.loads(line) for line in output.splitlines()]
        expected = []
        for row in data['sources']:
            for index, case in enumerate(data['cases']):
                if case['name'] not in ('sin', 'cos', 'sqrt') and not row['available']:
                    continue
                expected.append((row['revision'], index,
                                 case['degrees' if row['degrees'] else 'radians']))
        self.assertEqual(len(actual), len(expected))
        for result, (revision, index, value) in zip(actual, expected):
            with self.subTest(revision=revision, case=data['cases'][index]):
                self.assertEqual((result['revision'], result['case']), (revision, index))
                observed = float.fromhex(result['value'])
                if value == 'nan':
                    self.assertTrue(math.isnan(observed))
                else:
                    wanted = float.fromhex(value)
                    self.assertTrue(math.isclose(observed, wanted, rel_tol=2e-14, abs_tol=5e-14),
                                    (observed, wanted))
                    if wanted == 0:
                        self.assertEqual(math.copysign(1, observed), math.copysign(1, wanted))


if __name__ == '__main__':
    unittest.main()
