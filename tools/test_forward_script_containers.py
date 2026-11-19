"""Check native array edits, named-size selection and ownership boundaries.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-script-containers-contracts.json'


def program(data, engine):
    script = (engine / 'openborscript.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    methods = '\n'.join(function(script, name) for name in
                        ('Script_GetFunctionName', 'Script_LoadSystemFunctions'))
    selected = {'openbor_add', 'openbor_delete', 'openbor_size'}
    symbols = set(re.findall(r'\(\s*void\s*\*\s*\)\s*(\w+)', methods))
    if not selected <= symbols or not 8 <= len(symbols) <= 512:
        raise ValueError('Complete bounded native registry required')
    unused = {name: 'unselected_' + name for name in symbols - selected}
    methods = rename_identifiers(methods, unused)
    edits = []
    for case in data['edit_cases']:
        initial = case['initial'] + [0] * (8-len(case['initial']))
        expected = []
        for mode in ('integer', 'string'):
            values = case['expected'][mode]
            padded = values + [[0, 0]] * (8-len(values))
            expected.append('{' + ','.join('{%d,%d}' % tuple(value) for value in padded) + '}')
        edits.append('{%d,%d,%d,%d,%d,%d,%d,{%s},{%s}}' %
            (case['operation'], len(case['initial']), case['index'], case['alias'],
             case['empty'], case['success'], len(case['expected']['integer']),
             ','.join(map(str, initial)), ','.join(expected)))
    parts = dict(
        HEADER='#include ' + json.dumps(str(engine / 'openbor.h')),
        LIST='#include ' + json.dumps(str(engine / 'source/scriptlib/List.c')),
        VARIANTS='\n'.join(function(variants, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType',
             'ScriptVariant_Copy', 'ScriptVariant_IntegerValue')),
        INITIALIZE='\n'.join(function(script, name) for name in
            ('clear_named_var_list', 'Varlist_Init', 'Varlist_Clear',
             'Varlist_GetByName', 'Varlist_SetByName')),
        EDITS='\n'.join(function(script, name) for name in
            ('Varlist_AddByIndex', 'Varlist_DeleteByIndex', 'Varlist_DeleteByName')),
        APIS='\n'.join(function(script, name) for name in
            ('openbor_size', 'openbor_add', 'openbor_delete')),
        STUBS='\n'.join('static void '+name+'(void){}' for name in sorted(unused.values())),
        METHODS=methods,
        CONTEXTS=','.join('{%d,%d}' % (r['revision'], r['array_edits']) for r in data['sources']),
        CASES=',\n'.join(edits),
        ADD_ERROR=json.dumps(data['diagnostics']['add']),
        DELETE_ERROR=json.dumps(data['diagnostics']['delete']),
        SIZE_ERROR=json.dumps(data['diagnostics']['size']))
    text = Path(__file__).with_name('forward_script_containers_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native container input')
    return text


class ForwardScriptContainerTests(unittest.TestCase):
    def test_4432_native_progress_and_script_services(self):
        fixture = load_contract_fixture(Path(__file__).with_name('fixtures') /
            'profile-progress-script-services-contracts.json')
        self.assertEqual(fixture['engine'], '4432')
        rows = fixture['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertEqual(revisions, contract_revisions(fixture, fixture['expected_revisions']))
        engine = ROOT / 'src/engines' / fixture['engine']
        core = (engine / 'openbor.c').read_text(encoding='latin1')
        script = (engine / 'openborscript.c').read_text(encoding='latin1')
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin1')
        contexts = []
        for row in rows:
            self.assertIs(type(row['gif_early']), bool)
            self.assertIs(type(row['named_add']), bool)
            contexts.append('{%du,%s,%s,%s,%d,%d}' %
                (row['revision'], *(json.dumps(row[name]) for name in ('model', 'level', 'shutdown')),
                 row['gif_early'], row['named_add']))
        parts = dict(
            MODEL=re.search(r'(?m)^\s*(printf\([^;]+;)\s*return models_loaded', function(core, 'free_model'))[1],
            LEVEL=re.search(r'while\(temp\);\s*(printf\([^;]+;\s*getRamStatus\(BYTES\);)',
                            function(core, 'unload_level'))[1],
            SHUTDOWN=re.search(r'if\s*\(startup_done\)\s*\{\s*unload_level\(\);\s*\}\s*'
                               r'if\(!disablelog\)\s*\{\s*printf\([^;]+;\s*\}', function(core, 'shutdown'))[0],
            VARIANTS='\n'.join(function(variant, name) for name in
                ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType',
                 'ScriptVariant_Copy', 'ScriptVariant_IntegerValue')),
            CONTAINERS='\n'.join(function(script, name) for name in
                ('clear_named_var_list', 'Varlist_Init', 'Varlist_Clear',
                 'Varlist_GetByName', 'Varlist_SetByName', 'Varlist_AddByIndex')),
            APIS='\n'.join(function(script, name) for name in ('openbor_playgif', 'openbor_add')),
            CONTEXTS=',\n'.join(contexts))
        template = Path(__file__).with_name('progress_script_services_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda item: parts[item[1]], template)
        actual = json.loads(native_output(code, fixture, extra_cflags=('-fgnu89-inline',)))
        self.assertEqual(actual, {'contexts': len(rows), 'checks': 14 * len(rows)})
        print(json.dumps(actual, separators=(',', ':')), flush=True)

    def test_native_edits_registry_size_and_owned_values(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for row in data['sources']:
            self.assertEqual(row['engine'], data['engine'])
            self.assertIs(type(row['array_edits']), bool)
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
        for profile in contract_profiles(data, json.loads((ROOT/'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_SCRIPT_CONTAINERS_ENGINE',
                                     ROOT/'src/engines'/data['engine']))
        actual = [json.loads(line) for line in native_output(program(data, engine), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], status='PASS') for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
