"""Check native command-table growth and semantic release ownership.

Retained native helpers run only on valid owned or fixed shared storage.
Allocator and extent providers are bounded; loader fidelity remains covered by
the retained command-loading contracts. Stop providers replace only the API
defined by that engine, so an incorrect helper call remains a compile error.
This is not whole-model lifetime proof.
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
FIXTURE = HERE / 'fixtures/command-table-native-baseline.json'


def release_region(core):
    text = function(core, 'free_model')
    matches = list(re.finditer(r'if\s*\(hasFreetype\(model,\s*MF_SPECIAL\)\s*&&\s*model->special\)\s*'
        r'(?:\{[^{}]*\}|free\(model->special\);\s*model->special\s*=\s*NULL;)', text))
    if len(matches) != 1:
        raise ValueError('One native command-table release region required')
    return matches[0][0]


def program(engine, profiles, *, wrong_owner=False, omit_owner=False):
    core = (engine / 'openbor.c').read_text(encoding='latin1')
    baseline = load_contract_fixture(FIXTURE)['engines'][engine.name]
    native = function(core, 'alloc_specials')
    boolean = native.startswith('static bool')
    legacy = 'obor_profile_build < 3711' in native
    if release_region(core) != baseline['table_release']:
        raise ValueError('Native release policy must remain unchanged')
    if wrong_owner:
        line = 'owns = (newchar->freetypes & MF_SPECIAL) != 0;'
        if native.count(line) != 1:
            raise ValueError('One ownership decision required')
        native = native.replace(line, 'owns = 1;', 1)
    if omit_owner:
        line = 'newchar->freetypes |= MF_SPECIAL;'
        if native.count(line) != 1:
            raise ValueError('One new ownership publication required')
        native = native.replace(line, '(void)0;', 1)
    stops = {name: provider for name, provider in
             (('shutdown', 'fixture_stop_legacy'), ('borShutdown', 'fixture_stop_modern'))
             if re.search(r'(?m)^void\s+' + name + r'\s*\(', core)}
    declaration = re.findall(r'(?m)^(?:static\s+const\s+char\s*\*\s*E_OUT_OF_MEMORY|char\s+E_OUT_OF_MEMORY\[\])[^;]*;', core)
    if len(declaration) != 1:
        raise ValueError('One native allocation diagnostic required')
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        LEGACY=str(int(legacy)), BOOLEAN=str(int(boolean)), DIAGNOSTIC=declaration[0],
        ROUTINES='\n'.join([function(core, 'hasFreetype'),
            rename_identifiers(native, stops),
            rename_identifiers(baseline['alloc_specials'], dict(stops, alloc_specials='original_alloc_specials'))]),
        RELEASE=baseline['table_release'],
        CALL='return original ? original_alloc_specials(model) : alloc_specials(model);' if boolean else
             'if(original) original_alloc_specials(model); else alloc_specials(model); return 1;',
        PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u' for p in profiles))
    text = (HERE / 'command_table_ownership.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    return text


class CommandTableOwnershipTests(unittest.TestCase):
    def test_native_owned_shared_and_refusal_contracts_in_each_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        data = load_contract_fixture(FIXTURE)
        native_helpers = set()
        for row in pin['engines']:
            core = (ROOT / 'src/engines' / row['build'] / 'openbor.c').read_text(encoding='latin1')
            if re.search(r'(?m)^(?:static bool|void) alloc_specials\(', core):
                native_helpers.add(row['build'])
        self.assertEqual(set(data['engines']), native_helpers)
        for build in data['engines']:
            profiles = [p for p in pin['profiles'] if p['engine'] == build]
            engine = ROOT / 'src/engines' / build
            with self.subTest(engine=build):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['profiles'], len(profiles))
                self.assertEqual(value['status'], 'PASS')
                self.assertGreaterEqual(value['cases'], 10*len(profiles))

    def negative(self, *, wrong_owner=False, omit_owner=False):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines/3842'
        profile = next(p for p in pin['profiles'] if p['engine'] == engine.name)
        text = '#define NEGATIVE_ONLY 1\n'+program(engine, [profile], wrong_owner=wrong_owner, omit_owner=omit_owner)
        result = run_native(engine, text)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)
        return result.stderr

    def test_borrowed_table_cannot_use_another_models_reservation(self):
        self.assertIn('table owner', self.negative(wrong_owner=True))

    def test_new_table_requires_its_own_release_flag(self):
        self.assertIn('live_count()==0', self.negative(omit_owner=True))


if __name__ == '__main__':
    unittest.main()
