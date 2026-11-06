"""Check source-owned projectile arguments and entity-list query domains.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-projectile-caller-contracts.json'


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    parts = dict(FUNCTIONS='\n'.join(function(script, n) for n in
            ('openbor_projectile', 'openbor_getentity')),
        VARIANTS='\n'.join(function(variant, n) for n in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
             'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        CONTEXTS=','.join('{%du,%d,%d,%d,%d,%d}' % (r['revision'],
            r['strict_projectile'], r['projectile_error_null'], r['relative_defaults'],
            r['dynamic_entity_list'], r['fixed_entity_capacity']) for r in data['sources']))
    text = Path(__file__).with_name('projectile_callers_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved projectile caller dependency')
    return text


class ProjectileSelection(unittest.TestCase):
    def test_native_explicit_and_custom_selector_priority(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') /
                                     'profile-projectile-selection-contracts.json')
        rows = data['sources']
        revisions = {r['revision'] for r in rows}
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(revisions), len(rows))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        core = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        selectors = []
        for name in ('knife_spawn', 'bomb_spawn'):
            body = function(core, name)
            end = body.index('if(e==NULL) return NULL;') + len('if(e==NULL) return NULL;')
            selectors.append(body[:end] + '\nreturn e;\n}\n')
        values = dict(FUNCTIONS='\n'.join(selectors),
                      PROFILES=','.join(str(r['revision'])+'u' for r in rows),
                      CASES=',\n'.join('{'+','.join(str(c[k]) for k in data['case_fields'])+'}'
                                        for c in data['cases']))
        text = Path(__file__).with_name('projectile_selection_contract.c.in').read_text()
        for key, value in values.items():
            text = text.replace('@'+key+'@', value)
        self.assertIsNone(re.search(r'@[A-Z_]+@', text))
        actual = [json.loads(line) for line in native_output(text, data).splitlines()]
        self.assertEqual(len(actual), len(rows))
        for row, result in zip(rows, actual):
            with self.subTest(revision=row['revision']):
                self.assertEqual(result, dict(revision=row['revision'], results=data['contracts'][row['contract']]))


class ProjectileCalls(unittest.TestCase):
    def test_native_arguments_defaults_results_and_entity_bounds(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in data['sources']}
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(revisions), len(data['sources']))
        for row in data['sources']:
            self.assertIn(row['entity_oracle'], ('original_source', 'safe_storage_type'))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], projectile_cases=196,
            projectile_guard_cases=1, entity_cases=64, entity_guard_cases=20)
            for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
