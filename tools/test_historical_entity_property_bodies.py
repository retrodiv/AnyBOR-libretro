"""Exercise selected native entity properties through their historical dispatch.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_entity_namespace import declaration, entity_namespace
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-entity-property-body-contracts.json'


def program(data, *, destinations=False):
    engine = ROOT / 'src/engines' / data['engine']
    script = (engine / 'openborscript.c').read_text()
    header = (engine / 'openbor.h').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    mapper, mapped = switch_cases(script, 'mapstrings_entityproperty', 'ep', outermost=True)
    getter, get = switch_cases(script, 'openbor_getentityproperty', 'propind', outermost=True)
    setter, put = switch_cases(script, 'openbor_changeentityproperty', 'propind', outermost=True)
    methods = ('ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue',
               'ScriptVariant_DecimalValue')

    def arms(cases, labels):
        return '\n'.join(f'case {name}:' + cases[name]['body'] for name in labels)

    values = {
        'NAMESPACE': entity_namespace(script),
        'MAPS_ENUM': declaration(script, r'^enum gep_maps_enum[^;]*;'),
        'SEARCH': function((engine / 'source/utils.c').read_text(), 'searchList'),
        'MACROS': declaration(script, r'^#define _is_not_a_known_subproperty_of_[^\n]*') + '\n' +
                  declaration(script, r'^#define MAPSTRINGS[^\n]*(?:\n[^\n]*\\)*\n\}'),
        'VARIANTS': '\n'.join((
            declaration(header, r'^typedef enum\s*\{[^{}]*\bSUBTYPE_NONE\b[^{}]*\}\s*e_entity_type_sub;'),
            *(function(variants, name) for name in methods),
            function(script, 'obor_profile_subtype_value'),
        )),
        'MAPPER': mapper[:mapper.index('    static const')] +
                  declaration(mapper, r'    static const char \*proplist_maps\[\][^;]*;') + '\n' +
                  mapper[mapper.index('    if(paramCount < 2)'):mapper.index('    switch (ep)')] +
                  '    switch (ep) {\n' + arms(mapped, ['_ep_maps']) + '\n    }\n    return 1;\n}',
        'GETTER': getter[:getter.index('    switch(propind)')] + '    switch(propind) {\n' +
                  arms(get, data['body_labels']['get']) + '\n    default: *pretvar = NULL; return E_FAIL;\n' +
                  '    }\n    return S_OK;\n}',
        'SETTER': setter[:setter.index('    static const')] +
                  setter[setter.index('    *pretvar = NULL;\n\n'):setter.index('    switch(propind)')] +
                  '    switch(propind) {\n' + arms(put, data['body_labels']['set']) +
                  '\n    default: goto changeentityproperty_error;\n    }\n' + setter[setter.rindex('    return S_OK;'):],
    }
    template = Path(__file__).with_name('entity_property_body_contract.c.in').read_text()
    if destinations:
        template = template.split('/* Property observations */', 1)[0]
        template += Path(__file__).with_name('entity_destination_contract.c.in').read_text()
        values['DESTINATION_CONTEXTS'] = ',\n'.join(
            '{%du,%d,{%d,%d}}' % (row['revision'], row['fractional'], *row['ordinals'])
            for row in data['sources'])
    else:
        contexts = []
        for row in data['sources']:
            table = data['contracts'][row['contract']]
            contexts.append('{%d,{%s},{%s}}' % (
                row['revision'], ','.join(map(str, table['ordinals'])),
                ','.join(json.dumps(name) if name else 'NULL' for name in table['names'])))
        values.update(
            CONTEXTS=',\n'.join(contexts), PROPERTY_COUNT=str(len(data['properties'])),
            CASES=',\n'.join('{%d,%d,%d,%d,%d,%d,%.17g,%d,%.17g,%s}' % (
                row['property'], row['set'], row['named'], row['argc'], row['target'],
                row['third'][0], row['third'][1], row['fourth'][0], row['fourth'][1],
                json.dumps(row['text'])) for row in data['cases']))
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


class EntityPropertyBodyContracts(unittest.TestCase):
    def test_native_entity_destination_coordinates(self):
        fixture = FIXTURE.with_name('profile-4432-entity-destination-contracts.json')
        data = load_contract_fixture(fixture)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for profile in contract_profiles(data, pin['profiles'], source_range=data['range']):
            if profile['engine'] == data['engine']:
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        for row in data['sources']:
            self.assertEqual(row['engine'], data['engine'])
            self.assertIs(type(row['fractional']), bool)
            self.assertEqual(len(row['ordinals']), 2)
            if '_contract_boundaries' not in data:
                self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
                self.assertEqual(len(row['source_sha256']), 3)
        result = json.loads(native_output(program(data, destinations=True), data))
        self.assertEqual(result, {'contexts': len(revisions), 'checks': 56 * len(revisions)})

    def test_native_getter_and_setter_effects(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        results = iter(native_output(program(data), data).splitlines())
        for row in data['sources']:
            outcomes = data['contracts'][row['contract']]['outcomes']
            self.assertEqual(len(outcomes), len(data['cases']))
            for i, expected in enumerate(outcomes):
                self.assertEqual(json.loads(next(results)), [row['revision'], i, *expected],
                                 (row['revision'], data['cases'][i]['name']))
        self.assertIsNone(next(results, None))


if __name__ == '__main__':
    unittest.main()
