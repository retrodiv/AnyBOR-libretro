"""Keep native array bytes while bounding constructor inputs and allocation.

Native record/variant/List types are used. Allocations above a small fixed test
budget are refused without reserving them. Full constructors of other objects,
nested callback teardown and list cursor ownership are separate controls.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest
from contract_fixtures import load_contract_fixture
from native_allocation_policy import bind_named_allocation_support
from test_historical_player import function, rename_identifiers
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))
FIXTURE = HERE / 'fixtures/script-array-native-baseline.json'


def program(engine, profiles, *, excess_slot=False):
    oracle = load_contract_fixture(FIXTURE)
    data = oracle['engines'][engine.name]
    source = (engine / 'openborscript.c').read_text(encoding='latin1')
    modern = data['varlist_init'] is not None
    path, = (engine / 'source').rglob('ScriptVariant.c')
    variant = path.read_text(encoding='latin1')
    header = path.with_suffix('.h').read_text(encoding='latin1')
    support = 'int StrCache_Pop(%s){%s abort();}\n' % (
        'int length' if 'StrCache_Pop(int length)' in header else 'void',
        '(void)length;' if 'StrCache_Pop(int length)' in header else '')
    support += 'void StrCache_Collect(int index){(void)index;abort();}\n'
    support += '\n'.join(function(variant, n) for n in (
        'ScriptVariant_Init', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue'))
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        SCRIPT_HEADER='openborscript.h' if (engine / 'openborscript.h').is_file() else 'scriptcommon.h',
        VARIANT_SUPPORT=support, MODERN=str(int(modern)),
        BEFORE_INIT=rename_identifiers(data['varlist_init'], {'Varlist_Init':'before_init'}) if modern else '',
        AFTER_INIT=function(source, 'Varlist_Init') if modern else '',
        OWNER_REGISTRATION=('void obor_varlist_register(Varlist *value)'
                            '{assert(value && value->magic==varlist_magic);}'
                            if 'obor_varlist_register(array);' in source else ''),
        BEFORE_ARRAY=rename_identifiers(data['array'], {'openbor_array':'before_array', 'Varlist_Init':'before_init'}),
        AFTER_ARRAY=function(source, 'openbor_array'),
        RAW_OFFSET='(obor_profile_build>=3429u?1u:0u)' if engine.name=='3400' else '1u',
        PROFILES=','.join(str(oracle['profiles'][p['build']]['revision'])+'u' for p in profiles))
    text = (HERE / 'script_array_storage.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    if modern:
        # These loop controls survive a modeled controlled engine stop.
        text = text.replace('for(int mode=0;', 'for(volatile int mode=0;')
        text = text.replace('for(unsigned fail=2;', 'for(volatile unsigned fail=2;')
    if excess_slot:
        request = 'calloc((size_t)size + 1, sizeof(*varlist->vars))'
        if text.count(request) != 1:
            raise ValueError('One current checked variable-list allocation required')
        text = text.replace(request, 'calloc((size_t)size + 2, sizeof(*varlist->vars))', 1)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native script array input')
    return bind_named_allocation_support(text, engine)


class ScriptArrayStorageTests(unittest.TestCase):
    def test_native_array_bytes_allocations_and_defined_refusals_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        self.assertEqual(set(load_contract_fixture(FIXTURE)['profiles']), {p['build'] for p in pin['profiles']})
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            profiles = [p for p in pin['profiles'] if p['engine']==engine.name]
            with self.subTest(engine=engine.name):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                self.assertGreaterEqual(value['cases'], 24*len(profiles))

    def test_valid_native_allocation_extent_is_retained(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        oracle = load_contract_fixture(FIXTURE)
        key = next(k for k, v in oracle['engines'].items() if v['varlist_init'])
        engine = ROOT / 'src/engines' / key
        profile = next(p for p in pin['profiles'] if p['engine']==key)
        result = run_native(engine, program(engine, [profile], excess_slot=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('!memcmp(&before,&after,sizeof(before))', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__=='__main__':
    unittest.main()
