"""Check native registry identities, reverse names, mapping and menu routes.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-registry-ui-contracts.json'


def program(data, engine):
    script = (engine / 'openborscript.c').read_text()
    core = (engine / 'openbor.c').read_text()
    methods = '\n'.join(function(script, name) for name in
        ('Script_GetFunctionName', 'Script_GetStringMapFunction', 'Script_LoadSystemFunctions'))
    symbols = sorted(set(re.findall(r'\(\s*void\s*\*\s*\)\s*(\w+)', methods)))
    targets = data['targets']
    selected = {'openbor_options', 'openbor_hallfame'}
    if (not selected <= set(symbols) or not 8 <= len(symbols) <= 512 or
            len(targets) != 6 or len(set(targets)) != 6 or not set(targets) <= set(symbols)):
        raise ValueError('Complete bounded native registry with six explicit roles required')
    renamed = {name:'probe_'+name for name in symbols if name not in selected}
    mappers = list(dict.fromkeys(name for row in data['sources'] for name in row['mappers'] if name))
    if any(not re.fullmatch(r'mapstrings_\w+', name) or name not in renamed for name in mappers):
        raise ValueError('Native source-selected mapper identities required')
    rows = []
    for row in data['sources']:
        if any(len(row[key]) != 6 for key in ('bindings', 'reverse', 'mappers')):
            raise ValueError('Complete source role observations required')
        if any(type(v) is not int or not -1 <= v < 6 for v in row['bindings']):
            raise ValueError('Bounded source callback binding required')
        rows.append('{%du,{%s},{%s},{%s},%d}' % (row['revision'],
            ','.join(map(str,row['bindings'])), ','.join(json.dumps(v) for v in row['reverse']),
            ','.join(str(mappers.index(v)) if v else '-1' for v in row['mappers']),
            row['cheat_options']))
    values = dict(LIST=(engine / 'source/scriptlib/List.c').read_text(),
        STUBS='\n'.join('static void %s(void){++unexpected[%d];abort();}' % (renamed[name],i)
            for i,name in enumerate(renamed)), SYMBOL_COUNT=str(len(renamed)),
        METHODS=rename_identifiers(methods,renamed), CHEAT=function(core,'is_cheat_actived'),
        CALLBACKS='\n'.join(function(script,name) for name in ('openbor_options','openbor_hallfame')),
        TARGETS=','.join('(void*)'+renamed.get(name,name) for name in targets),
        MAPPERS=','.join('(void*)'+renamed[name] for name in mappers),
        LABELS=','.join(json.dumps(v) for v in data['labels']), CONTEXTS=','.join(rows))
    code = Path(__file__).with_name('forward_registry_ui_contract.c.in').read_text()
    for key,value in values.items():
        code = code.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@',code):
        raise ValueError('Unresolved registry/menu dependency')
    return code


class ForwardRegistryUITests(unittest.TestCase):
    def test_native_binding_reverse_mapping_and_custom_menu_routes(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions),len(data['sources']))
        self.assertEqual((min(revisions),max(revisions)),tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for profile in contract_profiles(data,json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision',profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision,revisions)
        engine = Path(os.environ.get('OBOR_REGISTRY_UI_ENGINE',ROOT / 'src/engines' / data['engine']))
        actual = [json.loads(line) for line in native_output(program(data,engine),data,engine_source=engine).splitlines()]
        self.assertEqual(actual,[dict(revision=row['revision'],status='PASS') for row in data['sources']])


if __name__ == '__main__':
    unittest.main()
