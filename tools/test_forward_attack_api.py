"""Check native shared-attack edits and the profile API removal boundary.

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
from test_historical_player import function, rename_identifiers

FIXTURE = Path(__file__).with_name('fixtures')/'profile-forward-attack-api-contracts.json'


def program(data, engine):
    script = (engine/'openborscript.c').read_text()
    variants = (engine/'source/scriptlib/ScriptVariant.c').read_text()
    methods = '\n'.join(function(script, name) for name in
        ('Script_GetFunctionName', 'Script_GetStringMapFunction', 'Script_LoadSystemFunctions'))
    selected = {'openbor_changeattackproperty', 'mapstrings_attackproperty'}
    symbols = set(re.findall(r'\(\s*void\s*\*\s*\)\s*(\w+)', methods))
    if not selected <= symbols or not 8 <= len(symbols) <= 512:
        raise ValueError('Complete bounded native registry and preconversion required')
    unused = {name:'unselected_'+name for name in symbols-selected}
    edits = []
    for row in data['properties']:
        if row['field'] is not None and not re.fullmatch(r'[a-z_]+(?:\.[xyz])?', row['field']):
            raise ValueError('Explicit bounded native field required')
        change = ('want = emptyattack;' if row['reset'] else
                  'want.'+row['field']+' = '+str(row['expected'])+';' if row['field'] else '')
        edits.append('case %d: %s break;' % (row['index'], change))
    macro_start = script.index('#define MAPSTRINGS(')
    pieces = dict(
        HEADER='#include '+json.dumps(str(engine/'openbor.h')),
        LIST='#include '+json.dumps(str(engine/'source/scriptlib/List.c')),
        ENUM=re.search(r'(?ms)^enum gep_attack_enum\s*\{.*?^\};', script)[0],
        NAMES=re.search(r'(?ms)^static const char \*eplist_attack\[\]\s*=\s*\{.*?^\};', script)[0],
        MACRO=script[macro_start:script.index('\n\n', macro_start)],
        SEARCH=function((engine/'source/utils.c').read_text(), 'searchList'),
        VARIANTS='\n'.join(function(variants, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType',
             'ScriptVariant_DecimalValue')),
        APIS='\n'.join(function(script, name) for name in
            ('mapstrings_attackproperty', 'openbor_changeattackproperty')),
        STUBS='\n'.join('static void '+name+'(void){}' for name in sorted(unused.values())),
        METHODS=rename_identifiers(methods, unused),
        CONTEXTS=','.join('{%d,%d}' % (r['revision'], r['attack_setter']) for r in data['sources']),
        PROPERTIES=','.join('{%s,%d}' % (json.dumps(r['name']), r['success']) for r in data['properties']),
        EXPECTED='\n'.join(edits),
        PARTIAL=','.join('{%d,%d,%d,{%s}}' % (r['count'], r['bad'], r['success'],
                      ','.join(map(str,r['expected']))) for r in data['dropv_cases']))
    text = Path(__file__).with_name('forward_attack_api_contract.c.in').read_text()
    for key, value in pieces.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native attack API contract input')
    return text


class ForwardAttackAPITests(unittest.TestCase):
    def test_native_registry_shared_state_and_partial_edits(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions),max(revisions)),tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for row in data['sources']:
            self.assertEqual(row['engine'],data['engine'])
            self.assertIs(type(row['attack_setter']),bool)
            self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
        for profile in contract_profiles(data,json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision',profile['build']))
            if profile['engine']==data['engine'] and data['range'][0]<=revision<=data['range'][1]:
                self.assertIn(revision,revisions)
        engine = Path(os.environ.get('OBOR_ATTACK_API_ENGINE',ROOT/'src/engines'/data['engine']))
        actual = [json.loads(line) for line in native_output(program(data,engine),data).splitlines()]
        self.assertEqual(actual,[dict(revision=r['revision'],status='PASS') for r in data['sources']])


if __name__=='__main__':
    unittest.main()
