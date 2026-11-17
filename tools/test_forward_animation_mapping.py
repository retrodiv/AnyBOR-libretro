"""Check historical animation selectors, diagnostics and compiler bindings.

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

FIXTURE = Path(__file__).with_name('fixtures')/'profile-forward-animation-mapping-contracts.json'


def program(data, engine):
    script = (engine/'openborscript.c').read_text()
    variants = (engine/'source/scriptlib/ScriptVariant.c').read_text()
    methods = '\n'.join(function(script, name) for name in
        ('Script_GetFunctionName', 'Script_GetStringMapFunction', 'Script_LoadSystemFunctions'))
    selected = {'openbor_getanimationproperty', 'openbor_changeanimationproperty',
                'mapstrings_animationproperty'}
    symbols = set(re.findall(r'\(\s*void\s*\*\s*\)\s*(\w+)', methods))
    if not selected <= symbols or not 8 <= len(symbols) <= 512:
        raise ValueError('Complete bounded native registry and preconversion required')
    unused = {name:'unselected_'+name for name in symbols-selected}
    layouts = list(data['layouts'])
    cases, spans = [], []
    types = {'ptr':'VT_PTR', 'int':'VT_INTEGER', 'str':'VT_STR'}

    def value(row, key):
        kind, payload = row
        if kind not in types or (kind == 'ptr' and payload != 0):
            raise ValueError('Bounded typed mapping input required')
        return '{%s,%d,%s,%d}' % (types[kind], payload if kind == 'int' else 0,
            json.dumps(payload) if kind == 'str' else 'NULL', key)

    for name in layouts:
        first = len(cases)
        for row in data['layouts'][name]['cases']:
            args, expected = row['args'], row['expected']
            if not 2 <= len(args) <= 6 or len(expected) != len(args):
                raise ValueError('Bounded complete mapping case required')
            keys = row.get('string_keys', list(range(1, len(args)+1)))
            if len(keys) != len(args) or any(type(k) is not int or not 0 <= k < 8 for k in keys):
                raise ValueError('Bounded string-cache key required')
            cases.append('{%d,%d,%s,{%s},{%s}}' % (len(args), row['result'],
                json.dumps(row['message']), ','.join(value(v,k) for v,k in zip(args,keys)),
                ','.join(value(v,k) for v,k in zip(expected,keys))))
        spans.append('{%d,%d}' % (first,len(cases)))
    macro_start = script.index('#define MAPSTRINGS(')
    old_start = script.index('typedef enum animationprop_enum')
    new_start = script.index('/* Native animation property bodies',old_start)
    new_end = script.index('static int obor_forward_mapstrings_animationproperty(',new_start)
    pieces = dict(
        HEADER='#include '+json.dumps(str(engine/'openbor.h')),
        LIST='#include '+json.dumps(str(engine/'source/scriptlib/List.c')),
        NAMESPACES=script[old_start:new_end],
        MACRO=script[macro_start:script.index('\n\n',macro_start)],
        SEARCH=function((engine/'source/utils.c').read_text(),'searchList'),
        VARIANTS='\n'.join(function(variants,name) for name in
            ('ScriptVariant_Init','ScriptVariant_Clear','ScriptVariant_ChangeType')),
        APIS='\n'.join(function(script,name) for name in
            ('obor_forward_mapstrings_animationproperty','mapstrings_animationproperty')),
        STUBS='\n'.join('static void '+name+'(void){}' for name in sorted(unused.values())),
        METHODS=rename_identifiers(methods,unused),
        CONTEXTS=','.join('{%d,%d,%d,%d,%s}' % (r['revision'],layouts.index(r['layout']),
            r['change_binding'],r['setter_name'],json.dumps(r['get_reverse'])) for r in data['sources']),
        CASES=',\n'.join(cases), SPANS=','.join(spans))
    text = Path(__file__).with_name('forward_animation_mapping_contract.c.in').read_text()
    for key, value in pieces.items():
        text = text.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@',text):
        raise ValueError('Unresolved native animation mapping input')
    return text


class ForwardAnimationMappingTests(unittest.TestCase):
    def test_native_selectors_diagnostics_and_compiler_bindings(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in data['sources']}
        self.assertEqual(len(revisions),len(data['sources']))
        self.assertEqual((min(revisions),max(revisions)),tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for row in data['sources']:
            self.assertEqual(row['engine'],data['engine'])
            self.assertIn(row['layout'],data['layouts'])
            self.assertIn(row['change_binding'],(0,1,2))
            self.assertIs(type(row['setter_name']),bool)
            self.assertRegex(row['commit'],r'^[0-9a-f]{40}$')
        for profile in contract_profiles(data,json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision',profile['build']))
            if profile['engine']==data['engine'] and data['range'][0]<=revision<=data['range'][1]:
                self.assertIn(revision,revisions)
        engine = Path(os.environ.get('OBOR_ANIMATION_MAPPING_ENGINE',ROOT/'src/engines'/data['engine']))
        actual = [json.loads(line) for line in native_output(program(data,engine),data).splitlines()]
        self.assertEqual(actual,[dict(revision=r['revision'],status='PASS') for r in data['sources']])


if __name__=='__main__':
    unittest.main()
