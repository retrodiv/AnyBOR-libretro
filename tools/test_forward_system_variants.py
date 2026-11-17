"""Execute source-defined system-variable namespaces and selected result bodies.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-system-variants-contracts.json'


def program(data, engine):
    source = (engine / 'openborscript.c').read_text()
    core = (engine / 'openbor.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    first = source.index('static const char *svlist[]')
    declaration = source[first:source.index('// ===== openborvariant', first)]
    methods = '\n'.join(function(source, name) for name in
        ('obor_profile_systemvariant_order', 'obor_systemvariant_available',
         'obor_systemvariant_native', 'mapstrings_systemvariant',
         'openbor_systemvariant', 'openbor_changesystemvariant'))
    selected = ('_sv_cheats', '_sv_numholes', '_sv_numlayers', '_sv_numwalls')
    callbacks = []
    for name in ('getsyspropertybyindex', 'changesyspropertybyindex'):
        body, cases = switch_cases(core, name, 'index', outermost=True)
        arms = selected if name == 'getsyspropertybyindex' else ()
        callback = (body[:body.index('switch(index)')] + 'switch(index){' +
            ''.join('case '+key+':'+cases[key]['body'] for key in arms) +
            'default:'+cases['default']['body'] + '}\nreturn 1;\n}\n')
        callbacks.append(rename_identifiers(callback, {name:'probe_'+name}))
    dispatcher = function(source, 'Script_GetStringMapFunction')
    owned = {'openbor_systemvariant', 'openbor_changesystemvariant', 'mapstrings_systemvariant'}
    stubs = sorted(set(re.findall(r'\(void\s*\*\)\s*(\w+)', dispatcher))-owned)
    dispatcher = rename_identifiers(dispatcher, {name:'probe_symbol_'+name for name in stubs})
    rows = []
    for row in data['sources']:
        if (len(row['properties']) != len(row['symbols']) or
                any(not re.fullmatch(r'_sv_\w+', name) for name in row['symbols']) or
                len(row['lookup_indices']) != len(data['query_names'])):
            raise ValueError('Complete independent native namespace and lookup observations required')
        rows.append('{%du,%d,{%s},{%s}}' % (row['revision'], len(row['symbols']),
            ','.join(row['symbols']), ','.join(map(str,row['lookup_indices']))))
    values = dict(DECLARATION=declaration, METHODS=methods,
        FIELDS='\n'.join(callbacks), CHEATS=function(core, 'is_cheat_actived'),
        SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
        DISPATCH=dispatcher,
        STUBS='\n'.join('static void probe_symbol_%s(void){++unused_calls;}' % name for name in stubs),
        CONTEXTS=','.join(rows), QUERY_COUNT=str(len(data['query_names'])),
        QUERIES=','.join(json.dumps(name) for name in data['query_names']),
        VARIANTS='\n'.join(function(variant,name) for name in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')))
    text = Path(__file__).with_name('forward_system_variants_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native system-variable contract input')
    return text


class ForwardSystemVariantTests(unittest.TestCase):
    def test_native_names_cached_indices_results_and_read_only_properties(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_SYSTEM_VARIANTS_ENGINE', ROOT / 'src/engines' / data['engine']))
        actual = [json.loads(line) for line in native_output(program(data, engine), data, engine_source=engine).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], status='PASS') for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
