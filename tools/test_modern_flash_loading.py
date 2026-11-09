"""Check flash defaults, authored commands and legacy property access.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, rename_identifiers, switch_cases


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-flash-loading-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    collision = (engine / 'source/openborscript/collision_attack.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    declarations = []
    for name in ('emptyattack', 'empty_body', 'global_config'):
        match = re.search(r'(?m)^(?:const )?\w+ ' + name + r'\s*=\s*\{', core)
        if not match:
            raise ValueError('Missing native default object ' + name)
        declarations.append(core[match.start():core.index('\n};', match.end()) + 3])
    _, model = switch_cases(core, 'load_cached_model', 'cmd', outermost=True)
    _, global_cases = switch_cases(core, 'load_models', 'cmd')
    _, attack_get = switch_cases(collision, 'openbor_get_attack_property', 'property')
    _, attack_set = switch_cases(collision, 'openbor_set_attack_property', 'property')
    _, entity_get = switch_cases(script, 'openbor_getentityproperty', 'propind')
    # The selected outer body contains exactly one nested flash switch.
    # Give the existing extractor a complete function containing that body.
    flash = 'void selected_flash(void) {' + entity_get['_ep_flash']['body'] + '}\n'
    _, entity_cases = switch_cases(flash, 'selected_flash', 'ltemp')
    entity_names = ('_ep_flash_block', '_ep_flash_def')
    enum = re.findall(r'enum gep_flash_enum\s*\{[^}]+\};', script)
    if len(enum) != 1:
        raise ValueError('Expected one source-owned legacy flash enumeration')
    setter = function(collision, 'openbor_set_attack_property')
    arg_value = re.findall(r'^[ \t]*#define ARG_VALUE[^\n]+', setter, re.M)
    if len(arg_value) != 1:
        raise ValueError('Expected one collision setter value-argument definition')
    callers = []
    for name in ('do_passive_block', 'try_counter_action', 'do_attack'):
        selected = re.findall(r'^[ \t]*spawn_attack_flash\([^;]+;', function(core, name), re.M)
        if len(selected) != 1:
            raise ValueError('Expected one flash call in ' + name)
        callers.append(rename_identifiers(selected[0], {'spawn_attack_flash': 'record_flash_call'}))
    parts = dict(
        DEFAULTS='\n'.join(declarations),
        HELPERS='\n'.join(function(core, name) for name in
                           ('obor_profile_global_flash_layer_adjust',
                            'obor_profile_global_flash_layer_source',
                            'obor_profile_global_flash_z_source', 'isNumeric', 'getValidInt')),
        VARIANTS='\n'.join(function(variants, name) for name in
                            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
                             'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        MODEL_CASES='\n'.join('case ' + n + ':' + model[n]['body'] for n in data['model_commands']),
        GLOBAL_CASES='\n'.join('case ' + n + ':' + global_cases[n]['body'] for n in data['global_commands']),
        GET_CASES='\n'.join('case ' + n + ':' + attack_get[n]['body'] for n in data['attack_properties']),
        SET_CASES='\n'.join('case ' + n + ':' + attack_set[n]['body'] for n in data['attack_properties']),
        ARG_VALUE=arg_value[0], ENTITY_ENUM=enum[0],
        ENTITY_CASES='\n'.join('case ' + n + ':' + entity_cases[n]['body'] for n in entity_names),
        CALLERS='\n'.join('case ' + str(i) + ': ' + call + ' break;' for i, call in enumerate(callers)),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=',\n'.join('{' + row[0] + ',' + json.dumps(row[1]) + ',' + str(row[2]) + '}'
                         for row in data['cases']))
    code = Path(__file__).with_name('modern_flash_loading_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved flash loading contract input')
    # The original script header declares this cross-unit object without
    # const; retain the definition's qualifier in the combined probe.
    return rename_identifiers(code, {'emptyattack': 'fixture_empty_attack'})


class ModernFlashLoadingContracts(unittest.TestCase):
    def test_defaults_commands_legacy_properties_and_call_arguments(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[
            dict(revision=row['revision'], **data['contracts'][row['contract']])
            for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
