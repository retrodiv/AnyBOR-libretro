"""Check source-defined native script contracts on later historical profiles.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases
from test_historical_script_registry import program
import test_historical_tolerance as _text_contracts


FIXTURE = Path(__file__).with_name('fixtures') / 'profile-late-script-registry-contracts.json'
ATTACK_FIXTURE = Path(__file__).with_name('fixtures') / 'profile-late-attack-contracts.json'
QUERY_FIXTURE = Path(__file__).with_name('fixtures') / 'profile-late-query-error-contracts.json'
DAMAGE_FIXTURE = Path(__file__).with_name('fixtures') / 'profile-late-damage-effects-contracts.json'


def registry_program(data):
    code, symbols = program(data)
    source = (ROOT / 'src/engines' / data['engine'] / 'openborscript.c').read_text()
    method = function(source, 'Script_GetStringMapFunction')
    refs = set(re.findall(r'\(void\s*\*\)\s*([A-Za-z_]\w*)', method))
    stubs = '\n'.join('static void ' + name + '(void) {}' for name in sorted(refs - set(symbols)))
    code = code.replace('static void unknown_function(void)', stubs + '\nstatic void unknown_function(void)')
    code = code.replace('int main(void) {', method + '\nint main(void) {')
    previous = r'printf("],\"unknown\":\"%s\"}\n",Script_GetFunctionName((void*)unknown_function));'
    updated = (r'printf("],\"unknown\":\"%s\",\"attack_mapper\":%d}\n",'
               'Script_GetFunctionName((void*)unknown_function),'
               'Script_GetStringMapFunction((void*)openbor_changeattackproperty)=='
               '(void*)mapstrings_attackproperty);')
    if code.count(previous) != 1:
        raise ValueError('One registry observation boundary required')
    return code.replace(previous, updated), symbols


def attack_program(data):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    enums = []
    for name in ('entityproperty_enum', 'gep_attack_enum'):
        matches = re.findall(r'(?m)^enum ' + name + r'\s*\{[\s\S]*?^};', source)
        if len(matches) != 1:
            raise ValueError('One native attack enum required: ' + name)
        enums.append(matches[0])
    table = re.findall(r'(?m)^static const char\* eplist_attack\[\]\s*=\s*\{[\s\S]*?^};', source)
    if len(table) != 1:
        raise ValueError('One native attack-name table required')
    attack_state = re.findall(r'(?m)^static s_attack obor_script_attack[^;]*;', source)
    if len(attack_state) != 1:
        raise ValueError('One native shared attack declaration required')
    mapper = function(source, 'mapstrings_entityproperty')
    old_table = re.findall(r'static const char\* proplist_attack\[\]\s*=\s*\{[\s\S]*?\};', mapper)
    if len(old_table) != 1:
        raise ValueError('One legacy attack-name table required')
    # Extract the complete native attack-mapping branch. Other parent
    # properties and the surrounding VM are providers for this contract.
    parsed = mapper.replace('switch (varlist[1]->lVal)', 'switch (parent)')
    _, mapping_cases = switch_cases(parsed, 'mapstrings_entityproperty', 'parent')
    entity_mapper = ('void mapstrings_entityproperty(ScriptVariant **varlist,int paramCount) {\n'
        'char *propname;int prop;\n' + old_table[0] + '\n'
        'if(paramCount<3){return;}\nswitch(varlist[1]->lVal){case _ep_attack:\n' +
        mapping_cases['_ep_attack']['body'] + '\n}}\n'
        '#define mapstrings_getentityproperty mapstrings_entityproperty\n')
    getter, cases = switch_cases(source, 'openbor_getentityproperty', 'propind')
    for label, row in sorted(cases.items(), key=lambda item: item[1]['label_start'], reverse=True):
        if label not in ('_ep_attack', 'default'):
            getter = getter[:row['label_start']] + getter[row['end']:]
    arrays, contexts = [], []
    for row in data['sources']:
        key = str(row['revision'])
        arrays.append('static const char *const names_' + key + '[]={' +
                      ','.join(json.dumps(name) for name in row['names']) + '};')
        for kind in ('get', 'put'):
            fields = []
            for field in row[kind]:
                if not re.fullmatch(r'[A-Za-z_]\w*', field['field']):
                    raise ValueError('A native attack field required')
                value_kind = field.get('kind', 'VT_INTEGER')
                if value_kind not in ('VT_INTEGER', 'VT_DECIMAL', 'VT_PTR'):
                    raise ValueError('A native attack value kind required')
                fields.append('{%s,offsetof(s_attack,%s),%d,%s}' % (
                    json.dumps(field['name']), field['field'],
                    int(field.get('floating', value_kind == 'VT_DECIMAL')), value_kind))
            arrays.append('static const struct field ' + kind + '_' + key + '[]={' +
                          ','.join(fields or ['{NULL,0,0,0}']) + '};')
        damage = row['damage']
        contexts.append('{%du,%d,%d,names_%s,%d,%d,get_%s,put_%s,%d,%d,%d,%d,%d}' % (
            row['revision'], row['setter'], len(row['names']), key,
            len(row['get']), len(row['put']), key, key,
            damage['shared_short'], damage['null_target_error'], damage['null_other_fallback'],
            damage['callback_returned'], damage['validate_optional_before_direct']))
    macro = source[source.index('#define MAPSTRINGS('):]
    parts = dict(VARIANTS='\n'.join(function(variants, name) for name in
                     ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_DecimalValue',
                      'ScriptVariant_IntegerValue')),
        LOOKUP=function((engine / 'source/utils.c').read_text(), 'searchList'),
        MACRO=macro[:macro.index('\n\n')], ENUMS='\n'.join(enums), TABLE=table[0],
        ATTACK_STATE=attack_state[0],
        NATIVE_ID=function(source, 'obor_attack_property_native'),
        MAPPER=function(source, 'mapstrings_attackproperty'), ENTITY_MAPPER=entity_mapper,
        SETTER=function(source, 'openbor_changeattackproperty'), GETTER=getter,
        DAMAGE_HELPER=function(source, 'obor_script_damageentity'),
        DAMAGE_ENTRY=function(source, 'openbor_damageentity'),
        CONTEXTS='\n'.join(arrays) + '\nstatic const struct context contexts[]={' +
                 ','.join(contexts) + '};')
    code = Path(__file__).with_name('late_attack_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved late attack contract dependency')
    return code


def query_error_program(data):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    entry, cases = switch_cases(source, 'openbor_getentityproperty', 'propind')
    selected = {row['property'] for row in data['cases']} | {'_ep_dropframe'}
    if not selected <= set(cases):
        raise ValueError('All declared entity-query cases must exist')
    for label, row in sorted(cases.items(), key=lambda item: item[1]['label_start'], reverse=True):
        if label not in selected and label != 'default':
            entry = entry[:row['label_start']] + entry[row['end']:]
    region = source[source.index('enum entityproperty_enum'):source.index('HRESULT openbor_getentityproperty(')]
    enums = re.findall(r'(?m)^enum [A-Za-z_]\w*\s*\{[\s\S]*?^};', region)
    if not 8 <= len(enums) <= 64:
        raise ValueError('Bounded native entity-query enums required')

    def selector(value):
        if type(value) is int:
            return str(value)
        if isinstance(value, str) and re.fullmatch(r'_ep_\w+', value):
            return value
        raise ValueError('A numeric or named native selector is required')

    queries = []
    for case in data['cases']:
        arguments = []
        for index in range(2, 7):
            kind, value = case['args'].get(str(index), ['VT_INTEGER', 0])
            if kind not in ('VT_INTEGER', 'VT_EMPTY', 'VT_STR'):
                raise ValueError('A declared query argument kind is required')
            arguments.append('{%s,%s}' % (kind, selector(value)))
        queries.append('{%s,%d,{%s}}' % (selector(case['property']), case['argc'], ','.join(arguments)))
    contracts = []
    for key, rows in data['contracts'].items():
        if not re.fullmatch(r'[0-9a-f]{16}', key) or len(rows) != len(data['cases']):
            raise ValueError('A complete source-bound query oracle is required')
        contracts.append('static const struct expected oracle_' + key + '[]={' +
            ','.join('{%d,%d,%s,%s,%s}' % (row['ok'], row['present'], row['kind'],
                json.dumps(row['value']), json.dumps(row['diagnostic'])) for row in rows) + '};')
    parts = dict(ENUMS='\n'.join(enums),
        VARIANTS='\n'.join(function(variants, name) for name in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
        NATIVE_ID=function(source, 'obor_attack_property_native'), GETTER=entry,
        CASES=','.join(queries), CONTRACTS='\n'.join(contracts),
        CONTEXTS=','.join('{%du,oracle_%s}' % (row['revision'], row['contract']) for row in data['sources']))
    code = Path(__file__).with_name('late_query_error_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved query-error contract dependency')
    return code


class LaterScriptContracts(unittest.TestCase):
    def test_damage_owner_and_driver_attacker_per_profile(self):
        data=load_contract_fixture(DAMAGE_FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data,data['expected_revisions']))
        source=(ROOT/'src/engines'/data['engine']/'openbor.c').read_text()
        parts={'SET_OPPONENT':function(source,'set_opponent'),
               'EFFECTS':function(source,'checkdamageeffects'),
               'BIKER':function(source,'biker_takedamage'),
               'CONTEXTS':','.join('{%du,%d,%d}'%(row['revision'],row['dot_owner_fallback'],
                   row['driver_attacker_forwarded']) for row in data['sources'])}
        code=Path(__file__).with_name('late_damage_effects_contract.c.in').read_text()
        for name,value in parts.items():code=code.replace('@'+name+'@',value)
        self.assertEqual(json.loads(native_output(code,data)),
                         {'status':'PASS','contexts':len(data['sources']),
                          'cases':len(data['sources'])*54})

    def test_entity_query_results_and_exact_diagnostics(self):
        data = load_contract_fixture(QUERY_FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(query_error_program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], cases=len(data['cases']))
                                  for row in data['sources']])

    def test_complete_registry_order_and_reverse_names(self):
        data = load_contract_fixture(FIXTURE)
        code, symbols = registry_program(data)
        actual = [json.loads(line) for line in native_output(code, data).splitlines()]
        self.assertEqual(len(actual), len(data['sources']))
        for result, row in zip(actual, data['sources']):
            expected = data['contracts'][row['contract']]
            reverse = {item['symbol']: item['name'] for item in reversed(expected['reverse'])}
            with self.subTest(profile=row['revision']):
                self.assertEqual(result, dict(revision=row['revision'],
                    register=[[item['symbol'], item['name']] for item in expected['register']],
                    reverse=[reverse.get(name, expected['unknown']) for name in symbols],
                    unknown=expected['unknown'], attack_mapper=int(row['attack_mapper'])))

    def test_attack_fields_ordinals_shared_state_and_partial_results(self):
        data = load_contract_fixture(ATTACK_FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        actual = [json.loads(line) for line in native_output(attack_program(data), data).splitlines()]
        self.assertEqual([row['revision'] for row in actual],
                         [row['revision'] for row in data['sources']])
        self.assertTrue(all(row['cases'] >= 30 for row in actual))

    def test_textured_triangle_function_contracts(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        code, symbols = program(data)
        actual = [json.loads(line) for line in native_output(code, data).splitlines()]
        self.assertEqual(len(actual), len(data['sources']))
        selected = {'openbor_settexture', 'openbor_setvertex', 'openbor_trianglelist'}
        self.assertTrue(selected <= set(symbols))
        for result, row in zip(actual, data['sources']):
            expected = data['contracts'][row['contract']]
            reverse = {item['symbol']: item['name'] for item in reversed(expected['reverse'])}
            with self.subTest(profile=row['revision']):
                self.assertEqual(result['revision'], row['revision'])
                self.assertEqual([item for item in result['register'] if item[0] in selected],
                                 [[item['symbol'], item['name']] for item in expected['register']
                                  if item['symbol'] in selected])
                self.assertEqual(result['unknown'], expected['unknown'])
                for name in selected:
                    self.assertEqual(result['reverse'][symbols.index(name)],
                                     reverse.get(name, expected['unknown']))


class LaterTextLifetimeContracts(_text_contracts.NativeTextReturnTests):
    fixture_name='profile-late-text-lifetime-contracts.json'
    scope_marker='omitted text lifetime'

    def test_source_defined_and_stability_cases_are_distinguished(self):
        for row in self.fixture['models']:
            for original in row['original_sources']:
                self.assertIs(type(original['omitted_time_defined']),bool)
                self.assertEqual(original['source_case_indices'],
                                 [0,1] if original['omitted_time_defined'] else [0])
                self.assertEqual(original['stability_case_indices'],
                                 [] if original['omitted_time_defined'] else [1])


if __name__ == '__main__':
    unittest.main()
