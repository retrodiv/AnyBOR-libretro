"""Check native pool growth, allocation order and partial cleanup.

Complete native table callers use real entity types and bounded constructor
and allocation providers. Actor construction and the allocator itself have
separate controls; this suite does not stand in for them.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import unittest

from contract_fixtures import load_contract_fixture
from test_historical_player import function, rename_identifiers
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))
FIXTURE = HERE / 'fixtures/entity-pool-native-baseline.json'


def program(engine, profiles, *, omit_tail_initialization=False):
    core = (engine / 'openbor.c').read_text(encoding='latin1')
    native = function(core, 'alloc_ents')
    original = load_contract_fixture(FIXTURE)['engines'][engine.name]['alloc_ents']
    if omit_tail_initialization:
        line = 'memset(ent_list + first, 0, sizeof(*ent_list) * (size_t)MAX_ENTS);'
        if native.count(line) != 1:
            raise ValueError('One native pointer-tail initialization required')
        native = native.replace(line, '(void)0;', 1)
    values = dict(
        CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        DUAL=str(int('ent_stack' in native)),
        ROUTINES='\n'.join([function(core, 'free_ents'), native,
                            rename_identifiers(original, {'alloc_ents': 'original_alloc_ents'})]),
        PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u' for p in profiles))
    text = (HERE / 'entity_pool_growth.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    return text


class EntityPoolGrowthTests(unittest.TestCase):
    def check_engines(self, dual):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        oracle = load_contract_fixture(FIXTURE)
        for build in oracle['engines']:
            if (build != '3842') != dual:
                continue
            profiles = [p for p in pin['profiles'] if p['engine'] == build]
            with self.subTest(engine=build):
                self.assertTrue(profiles)
                engine = ROOT / 'src/engines' / build
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                self.assertGreater(value['checks'], 100*len(profiles))

    def test_single_table_valid_traces_and_defined_refusals(self):
        self.check_engines(False)

    def test_dual_tables_valid_traces_and_defined_refusals(self):
        self.check_engines(True)

    def test_partial_cleanup_requires_initialized_pointer_slots(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines/3842'
        profile = next(p for p in pin['profiles'] if p['engine'] == engine.name)
        text = '#define NEGATIVE_ONLY 1\n'+program(engine, [profile], omit_tail_initialization=True)
        result = run_native(engine, text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('owned entity entry', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
