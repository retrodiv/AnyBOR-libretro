"""Check player input bounds and retained native results with bounded services.

Complete getters/setters and real player records run with the native variants
and property mappers. Cache, weapon and model lookup services are explicit
providers; this does not validate their allocation or lifetime implementations.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_player import function, rename_identifiers
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))
FIXTURE = HERE / 'fixtures/player-property-native-baseline.json'


def program(engine, profiles, *, reject_last_slot=False, history=None, name_capacity=None, player_status=None):
    core = (engine / 'openborscript.c').read_text(encoding='latin1')
    oracle = load_contract_fixture(FIXTURE)
    data = oracle['engines'][engine.name]
    variant_path, = (engine / 'source').rglob('ScriptVariant.c')
    variant = variant_path.read_text(encoding='latin1')
    header = variant_path.with_suffix('.h').read_text(encoding='latin1')
    methods = '\n'.join(function(core, n) for n in
                        ['openbor_getplayerproperty', 'openbor_changeplayerproperty'])
    if reject_last_slot:
        if methods.count('index >= MAX_PLAYERS') != 2:
            raise ValueError('One slot bound in each complete native entry required')
        methods = methods.replace('index >= MAX_PLAYERS', 'index >= MAX_PLAYERS - 1')
    baseline = rename_identifiers(data['getter'] + '\n' + data['setter'], {
        'openbor_getplayerproperty': 'original_get',
        'openbor_changeplayerproperty': 'original_set'})
    if engine.name == '6391':
        # Before 6302 the original getter falls through for an unhandled
        # numeric property and leaves its cleared result available.
        split = baseline.index('HRESULT original_set')
        getter, setter = baseline[:split], baseline[split:]
        getter, defaults = re.subn(r'(?m)(^    default:\r?\n    \{\n)(?=        //printf\("Property name)',
                                   r'\g<1>        if(obor_profile_build && obor_profile_build < 6302) break;\n',
                                   getter)
        if defaults != 1:
            raise ValueError('One frozen getter default required')
        baseline = getter + setter
    if engine.name == '4432' and 'obor_player_property_native(' in core:
        # This older fixture uses the native mapper with the physical enum in
        # its frozen baseline. Its valid calls predate the new numbered probe.
        for assignment in ('prop = arg->lVal;', 'prop = varlist[1]->lVal;'):
            if baseline.count(assignment) != 1:
                raise ValueError('Expected one numbered input in the player baseline')
            baseline = baseline.replace(assignment, assignment + '''
    if(obor_profile_build >= 4283 && obor_profile_build < 4400 && prop >= _pp_numweapons) ++prop;
''')
    enums = '\n'.join(re.findall(
        r'enum (?:get|change)?playerproperty_enum\s*\{.*?\};', core, re.S))
    if not enums:
        raise ValueError('Native player namespaces required')
    if 'obor_playerproperty_order(' in core:
        names_table = re.search(r'(?ms)^static const char \*const obor_playerproperty_names\[\] =.*?^\};', core)[0]
        enums += '\n' + names_table
        for assignment in ('prop = arg->lVal;', 'prop = varlist[1]->lVal;'):
            if baseline.count(assignment) == 1:
                baseline = baseline.replace(assignment, assignment + '\n    prop = obor_playerproperty_native(prop);')
    if 'obor_player_property_index(' in methods:
        legacy = re.search(r'(?ms)^enum\s*\{\s*OBOR_LEGACY_PLAYER_PROPERTY_COUNT\s*=.*?^\};', core)
        if legacy is None:
            raise ValueError('Native legacy player property ordinals required')
        enums += '\n' + legacy[0]
        for assignment in ('prop = arg->lVal;', 'prop = varlist[1]->lVal;'):
            if baseline.count(assignment) == 1:
                baseline = baseline.replace(assignment, assignment + '\n    prop = obor_player_property_index(prop);')
    support = []
    names = ['obor_uses_early_player_properties', 'obor_player_property_native',
                 'obor_player_get_property_native', 'obor_player_set_property_native',
                 'obor_playerproperty_order', 'obor_playerproperty_native',
                 'obor_legacy_player_properties', 'obor_player_property_index',
                 'obor_playerproperty_consumes_value',
                 'mapstrings_playerproperty', 'mapstrings_getplayerproperty',
                 'mapstrings_changeplayerproperty']
    selected = {}
    while True:
        size = len(selected)
        for name in names:
            if name not in selected and re.search(r'\b' + name + r'\(', methods + baseline + ''.join(selected.values())):
                selected[name] = function(core, name)
        if len(selected) == size:
            break
    support = [selected[name] for name in names if name in selected]
    if 'obor_profile_name_limit(' in methods:
        support.append(function((engine / 'openbor.c').read_text(encoding='latin1'),
                                'obor_profile_name_limit'))
    lines = core.splitlines(keepends=True)
    first = next((i for i, line in enumerate(lines) if line.startswith('#define MAPSTRINGS(')), None)
    macro = ''
    if first is not None:
        last = first
        while lines[last].rstrip().endswith('\\'):
            last += 1
        macro = ''.join(lines[first:last + 1])
    elif not any('#define MAPSTRINGS(' in p.read_text(encoding='latin1') for p in (engine / 'source').rglob('scriptcommon.h')):
        raise ValueError('Native mapper macro must come from the unit or its script header')
    conversions = ['ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue']
    if 'ScriptVariant_ToString(' in baseline:
        conversions.append('ScriptVariant_ToString')
    contexts = []
    for profile in profiles:
        own = oracle['profiles'][profile['build']]
        name_limit = own['name_limit'] - ('+' not in own['name_declaration'])
        contexts.append('{%du,%d,%d,%d}' % (
            own['revision'], own['getter_requires_actor'], own['setter_integer_result'], name_limit))
    history_code = ''
    if history:
        contexts = ['{%du,0,0,0}' % row['revision'] for row in history['sources']]
        contracts = []
        numbers = []
        for case in history['contracts']:
            name_literals = ','.join(json.dumps(name) for name in case['names'])
            diagnostics = ','.join(json.dumps(message) for message in case['diagnostics'])
            contracts.append('{%d,%d,{%s},{%s}}' %
                             (len(case['names']), case['weapons'], name_literals, diagnostics))
        for row in history['sources']:
            numbers.append(str(row['contract']))
        history_code = (HERE / 'player_property_history_contract.c.in').read_text()
        history_code = history_code.replace('@PLAYER_CONTRACTS@', ',\n'.join(contracts))
        history_code = history_code.replace('@PLAYER_CONTRACT_IDS@', ','.join(numbers))
    profile_support = ('uint32_t obor_profile_features;\nint obor_lns_players[MAX_PLAYERS];\n'
                       if 'obor_lns_players' in methods else '')
    if engine.name == '4432' and (history or 'models_cached' in methods):
        profile_support += 'int models_cached;\n'
    if engine.name == '4086' and 'models_cached' in methods:
        profile_support += 'unsigned int models_cached;\n'
    profile_calls = methods + '\n'.join(support)
    if ('obor_profile_uses_5134_script_ids(' in profile_calls or
            'obor_profile_has_player_status_property(' in profile_calls):
        profile_support += '#include "source/openborscript/profile_ids.h"\n'
    if name_capacity is not None:
        contexts = ['{%du,0,0,0}' % row['revision'] for row in name_capacity]
        limits = ','.join(str(row['name_bytes']) for row in name_capacity)
        profile_support += ('#define NAME_CAPACITY_CONTRACT 1\n'
                            f'static const size_t expected_name_limits[] = {{{limits}}};\n')
    if player_status is not None:
        contexts = ['{%du,0,0,0}' % row['revision'] for row in player_status]
        records = ',\n'.join('{%d,%d,%d}' % (row['status_ordinal'], row['weapnum_ordinal'], row['weapon_ordinal'])
                              for row in player_status)
        history_code = (HERE / 'player_status_property_contract.c.in').read_text().replace('@ROWS@', records)
        profile_support += '#define PLAYER_STATUS_CONTRACT 1\n'
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        SCRIPT_HEADER='openborscript.h' if (engine / 'openborscript.h').is_file() else 'scriptcommon.h',
        POP_ARGUMENTS='int length' if 'StrCache_Pop(int length)' in header else 'void',
        POP_UNUSED='(void)length;' if 'StrCache_Pop(int length)' in header else '',
        CREATE_SLOT='i=StrCache_Pop((int)strlen(text));' if 'StrCache_Pop(int length)' in header else 'i=StrCache_Pop();',
        ENUMS=enums, MACRO=macro, SUPPORT='\n'.join(support),
        SEARCH=function((engine / 'source/utils.c').read_text(encoding='latin1'), 'searchList'),
        VARIANTS='\n'.join(function(variant, n) for n in conversions),
        METHODS=methods, BASELINE=baseline, CONTEXTS=','.join(contexts),
        PROFILE_SUPPORT=profile_support,
        HISTORY_FLAG='#define PLAYER_PROPERTY_HISTORY 1' if history else '',
        HISTORICAL_CASES=history_code,
        HAS_HISTORY=str(int(engine.name in ['4432', '6391', '7142', '7533'])),
        CONTROL_UNDEF='#undef control_getmappedkeyname\n#undef control_getdevicename\n' if engine.name == '8023' else '',
        MODERN_VIEW=str(int(engine.name == '8023')))
    text = (HERE / 'player_property_inputs.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved player input fixture')
    return text


class PlayerPropertyInputTests(unittest.TestCase):
    def test_6391_transient_player_status(self):
        fixture = load_contract_fixture(HERE / 'fixtures/profile-6391-player-status.json')
        rows = fixture['sources']
        self.assertEqual([row['revision'] for row in rows],
                         sorted(contract_revisions(fixture, fixture['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / fixture['engine']))
        result = run_native(engine, program(engine, [], player_status=rows))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), {'status': 'PASS', 'profiles': len(rows), 'cases': 4 * len(rows)})

    def test_4432_historical_player_name_lengths(self):
        fixture = load_contract_fixture(HERE / 'fixtures/profile-4432-name-capacity-contracts.json')
        engine = ROOT / 'src/engines' / fixture['engine']
        result = run_native(engine, program(engine, [], name_capacity=fixture['sources']))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        total = len(fixture['sources'])
        self.assertEqual(json.loads(result.stdout), {'status': 'PASS', 'profiles': total, 'cases': 3 * total})

    def test_historical_4432_player_properties(self):
        fixture = load_contract_fixture(HERE / 'fixtures/profile-player-property-history-contracts.json')
        self.assertEqual(fixture['engine'], '4432')
        revisions = {row['revision'] for row in fixture['sources']}
        self.assertEqual(len(revisions), len(fixture['sources']))
        self.assertEqual(revisions, contract_revisions(fixture, fixture['expected_revisions']))
        for contract in fixture['contracts']:
            self.assertEqual(len(contract['diagnostics']), 4)
            self.assertIs(type(contract['weapons']), bool)
            self.assertEqual(len(contract['names']), 25 if contract['weapons'] else 24)
            self.assertEqual(contract['names'], sorted(set(contract['names'])))
        engine = ROOT / 'src/engines' / fixture['engine']
        result = run_native(engine, program(engine, [], history=fixture))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        expected = sum(2 * len(fixture['contracts'][row['contract']]['names']) + 17
                       for row in fixture['sources'])
        self.assertEqual(json.loads(result.stdout), {'status': 'PASS', 'profiles': len(revisions), 'cases': expected})
        print(result.stdout.strip(), flush=True)

    def check_family(self, engine_name):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines' / engine_name
        profiles = [p for p in pin['profiles'] if p['engine'] == engine.name]
        self.assertTrue(profiles)
        result = run_native(engine, program(engine, profiles))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['profiles'], len(profiles))
        self.assertEqual(value['status'], 'PASS')
        self.assertGreater(value['cases'], 100 * len(profiles))
        return value

    def test_valid_native_results_and_defined_input_refusals(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        oracle = load_contract_fixture(FIXTURE)
        self.assertEqual(set(oracle['profiles']), {p['build'] for p in pin['profiles']})
        for entry in pin['engines']:
            with self.subTest(engine=entry['build']):
                self.check_family(entry['build'])

    def test_last_fixed_slot_remains_accessible(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        entry = pin['engines'][0]
        engine = ROOT / 'src/engines' / entry['build']
        profile = next(p for p in pin['profiles'] if p['engine'] == engine.name)
        result = run_native(engine, '#define ENDPOINT_ONLY 1\n' +
                            program(engine, [profile], reject_last_slot=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('native_result == original_result', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
