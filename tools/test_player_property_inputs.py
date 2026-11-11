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

from contract_fixtures import load_contract_fixture
from test_historical_player import function, rename_identifiers
from test_model_constructor_ownership import run_native

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))
FIXTURE = HERE / 'fixtures/player-property-native-baseline.json'


def program(engine, profiles, *, reject_last_slot=False):
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
    enums = '\n'.join(re.findall(
        r'enum (?:get|change)?playerproperty_enum\s*\{.*?\};', core, re.S))
    if not enums:
        raise ValueError('Native player namespaces required')
    support = []
    names = ['obor_player_property_native', 'obor_player_get_property_native', 'obor_player_set_property_native',
                 'obor_playerproperty_native',
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
        contexts.append('{%du,%d,%d}' % (
            own['revision'], own['getter_requires_actor'], own['setter_integer_result']))
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        SCRIPT_HEADER='openborscript.h' if (engine / 'openborscript.h').is_file() else 'scriptcommon.h',
        POP_ARGUMENTS='int length' if 'StrCache_Pop(int length)' in header else 'void',
        POP_UNUSED='(void)length;' if 'StrCache_Pop(int length)' in header else '',
        CREATE_SLOT='i=StrCache_Pop((int)strlen(text));' if 'StrCache_Pop(int length)' in header else 'i=StrCache_Pop();',
        ENUMS=enums, MACRO=macro, SUPPORT='\n'.join(support),
        SEARCH=function((engine / 'source/utils.c').read_text(encoding='latin1'), 'searchList'),
        VARIANTS='\n'.join(function(variant, n) for n in conversions),
        METHODS=methods, BASELINE=baseline, CONTEXTS=','.join(contexts),
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
