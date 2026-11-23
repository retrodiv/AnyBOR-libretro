"""Check source-owned bounding-box and energy-cost query contracts.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-entity-query-contracts.json'


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    entry, cases = switch_cases(source, 'openbor_getentityproperty', 'propind')
    for label, row in sorted(cases.items(), key=lambda item: item[1]['label_start'], reverse=True):
        if label not in ('_ep_bbox', '_ep_energycost', 'default'):
            entry = entry[:row['label_start']] + entry[row['end']:]
    enums = []
    for name in ('entityproperty_enum', 'gep_energycost_enum'):
        matches = re.findall(r'(?m)^enum '+name+r'\s*\{[\s\S]*?^};', source)
        if len(matches) != 1:
            raise ValueError('One native query enum required: '+name)
        enums.append(matches[0])
    parts = dict(ENTRY=entry, ENUMS='\n'.join(enums),
        VARIANTS='\n'.join(function(variant, n) for n in
                           ('ScriptVariant_Clear', 'ScriptVariant_ChangeType')),
        CONTEXTS=','.join('{%du,%d,%d,%s,%s}' % (r['revision'], r['bbox_strict'],
            r['bbox_vulnerable'], json.dumps(r['bbox_diagnostic']),
            json.dumps(r['energy_diagnostic'])) for r in data['sources']))
    text = Path(__file__).with_name('entity_query_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native entity query dependency')
    return text


def delay_program(data):
    from test_historical_entity_complex import complex_program
    from test_historical_entity_returns import scalar_entry
    source = (ROOT / 'src/engines' / data['engine'] / 'openborscript.c').read_text()
    entry, actions = scalar_entry(source, ('_ep_edelay',))
    driver = Path(__file__).with_name('animation_delay_contract.c.in').read_text()
    driver = driver.replace('@LEGACY@', ','.join(str(int(r['factor_argument']==4))
                                               for r in data['sources']))
    return complex_program(components=dict(entries=entry, actions=actions,
        helpers='static int obor_entity_set_property_native(int p){return p;}',
        invoke='return openbor_changeentityproperty(args,result,count);'),
        contracts=[dict(revision=r['revision'], has_result=r['has_result'])
                   for r in data['sources']], driver=driver)


def getter_diagnostic_program(data):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    entry, cases = switch_cases(source, 'openbor_getentityproperty', 'propind', outermost=True)
    retained = {'_ep_' + case['property'] for case in data['cases']} | {'_ep_dropframe', 'default'}
    for label, row in sorted(cases.items(), key=lambda item: item[1]['label_start'], reverse=True):
        if label not in retained:
            entry = entry[:row['label_start']] + entry[row['end']:]
    macro = source[source.index('#define MAPSTRINGS('):].split('\n\n', 1)[0]
    mapper_names = ('mapstrings_entityproperty', 'mapstrings_getentityproperty',
                    'mapstrings_changeentityproperty')
    mappers = [function(source, name) for name in mapper_names]
    mapper_end = max(source.index(mapper) + len(mapper) for mapper in mappers)
    parts = {
        'ENTRY': entry,
        'MAPPERS': macro + '\n' + source[source.index('enum entityproperty_enum'):mapper_end],
        'METHODS': '\n'.join((function((engine / 'source/utils.c').read_text(), 'searchList'),
            *(function(variant, name) for name in ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
                                                   'ScriptVariant_IntegerValue')),
            function(source, 'obor_script_sprite_name_readable'))),
        'REVISIONS': ','.join(f"{row['revision']}u" for row in data['sources']),
        'CASES': ',\n'.join('{%s,%d,{%s},{%s}}' % (json.dumps(row['property']), len(row['arguments']),
            ','.join('VT_EMPTY' if value is None else 'VT_INTEGER' for value in row['arguments']) or '0',
            ','.join(str(value) if value is not None else '0' for value in row['arguments']) or '0')
            for row in data['cases']),
    }
    template = Path(__file__).with_name('entity_getter_diagnostics.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)


class EntityQueryContracts(unittest.TestCase):
    def test_native_source_owned_query_results_and_bounded_indices(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({r['revision'] for r in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len({r['revision'] for r in data['sources']}), len(data['sources']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], oracle_cases=113,
                                      validation_cases=13) for r in data['sources']])

    def test_native_animation_delay_factor_argument(self):
        data = load_contract_fixture(Path(__file__).with_name('fixtures') /
                                     'profile-animation-delay-contracts.json')
        self.assertEqual({r['revision'] for r in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len({r['revision'] for r in data['sources']}), len(data['sources']))
        actual = [json.loads(line) for line in native_output(delay_program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], delay_oracle_cases=6,
                                      delay_validation_cases=5) for r in data['sources']])

    def check_getter_queries(self, fixture):
        data = load_contract_fixture(FIXTURE.with_name(fixture))
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        profiles = json.loads((ROOT / 'src/pin.json').read_text())['profiles']
        for profile in contract_profiles(data, profiles, source_range=data['range']):
            if profile['engine'] == data['engine']:
                self.assertIn(int(profile.get('revision', profile['build'])), revisions)
        actual = iter(native_output(getter_diagnostic_program(data), data,
            extra_cflags=('-fgnu89-inline', '-Wno-error=implicit-fallthrough')).splitlines())
        for row in data['sources']:
            outcomes = data['contracts'][row['contract']]
            self.assertEqual(len(outcomes), len(data['cases']))
            for index, (case, expected) in enumerate(zip(data['cases'], outcomes)):
                returned = json.loads(next(actual))
                returned[5] = bytes.fromhex(returned[5]).decode('ascii')
                self.assertEqual(returned, [row['revision'], index, *expected,
                                           *([None] if len(expected)==4 else [])],
                                 (row['revision'], case['property'], case['arguments']))
        self.assertIsNone(next(actual, None))

    def test_native_getter_diagnostics_and_return_selection(self):
        self.check_getter_queries('profile-entity-getter-diagnostics.json')

    def test_native_early_getter_numeric_selection_and_values(self):
        self.check_getter_queries('profile-entity-getter-selectors.json')


if __name__ == '__main__':
    unittest.main()
