"""Check native walking, grab restoration and per-axis binding transitions.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-entity-state-contracts.json'


def program(data, engine):
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    enum = re.search(r'enum aiflag_enum\s*\{[^}]*\};', script)
    if enum is None:
        raise ValueError('Native AI flag enumeration required')
    walking = {}
    for key, name in [('GET_WALKING', 'openbor_getentityproperty'),
                      ('SET_WALKING', 'openbor_changeentityproperty')]:
        _, outer = switch_cases(script, name, 'propind', outermost=True)
        view = 'int walking_view(void) {\n' + outer['_ep_aiflag']['body'] + '\n}'
        # The setter's selector is an expression. Only this temporary read view
        # renames that expression so the maintained case parser can select it.
        selector = 'switch(varlist[2]->lVal)' if key == 'SET_WALKING' else 'switch(ltemp)'
        if view.count(selector) != 1:
            raise ValueError('One native AI-flag selector required')
        view = view.replace(selector, 'switch(walking_flag)')
        _, cases = switch_cases(view, 'walking_view', 'walking_flag')
        walking[key] = cases['_ep_aiflag_walking']['body']
    values = dict(
        HEADER='#include ' + json.dumps(str(engine / 'openbor.h')),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType',
             'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        FLAGS=enum[0], **walking,
        CORE='\n'.join(rename_identifiers(function(core, name), {'time': 'fixture_time'})
            for name in ('diff', 'inair', 'ent_set_anim', 'common_anim_series',
                         'ent_default_init', 'set_rise', 'set_riseattack', 'adjust_bind')),
        SCRIPT='\n'.join(rename_identifiers(function(script, name), {'time': 'fixture_time'})
                           for name in ('openbor_bindentity', 'openbor_setidle')),
        CONTEXTS=','.join('{%d,%d,%d,%d}' % (row['revision'], row['walking'],
                              row['grab_defaults'], row['partial_bind']) for row in data['sources']),
        DEFAULT_CASES=','.join('{%s,%s,%d}' % (row['type'], row['subtype'], row['nograb'])
                               for row in data['default_cases']),
        BIND_CASES=','.join('{%d,%d,%d,%d,%d,%d,%d,%d,{%s},{%s}}' %
            (row['count'], row['actor'], row['target'], row['empty'], row['bad'],
             row['initial_flags'], row['direction'], row['parent_direction'],
             ','.join(map(str, row['legacy'])), ','.join(map(str, row['partial'])))
            for row in data['bind_cases']))
    text = Path(__file__).with_name('forward_entity_state_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native entity-state input')
    return text


class ForwardEntityStateTests(unittest.TestCase):
    def test_native_transitions_defaults_and_binding_partial_results(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        for row in data['sources']:
            self.assertEqual(row['engine'], data['engine'])
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            for name in ('walking', 'grab_defaults', 'partial_bind'):
                self.assertIs(type(row[name]), bool)
        engine = Path(os.environ.get('OBOR_ENTITY_STATE_ENGINE',
                                     ROOT / 'src/engines' / data['engine']))
        actual = [json.loads(line) for line in native_output(program(data, engine), data).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], status='PASS')
                                  for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
