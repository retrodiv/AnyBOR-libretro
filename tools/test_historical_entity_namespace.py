"""Check historical entity property selectors through native dispatch.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-entity-namespace-contracts.json'


def declaration(source, pattern):
    match = re.search(pattern, source, re.M)
    if not match:
        raise ValueError('Missing native entity namespace declaration: ' + pattern)
    return match[0]


def entity_namespace(script):
    declarations = (
        r'^enum entityproperty_enum[^;]*;',
        r'^static const char \*eplist\[\][^;]*;',
        r'^static const struct \{[^\n]+\} obor_entity_property_additions\[\][\s\S]*?^};',
    )
    helpers = ('obor_entity_property_uses_history', 'obor_resolve_entity_property',
               'obor_entity_property_name', 'obor_map_entity_property_name')
    return '\n'.join([declaration(script, pattern) for pattern in declarations] +
                     [function(script, name) for name in helpers])


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    script = (engine / 'openborscript.c').read_text()
    mapper = function(script, 'mapstrings_entityproperty')
    getter = function(script, 'openbor_getentityproperty')
    setter = function(script, 'openbor_changeentityproperty')
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    methods = ('ScriptVariant_ChangeType', 'ScriptVariant_Clear')
    branches = '\n'.join(f'    case {item}: observed = {item}; break;'
                         for item in data['physical_selectors'])
    getter_failure = 'default: *pretvar = NULL; return E_FAIL;'
    setter_failure = 'default: goto changeentityproperty_error;'
    values = {
        'NAMESPACE': entity_namespace(script),
        'SEARCH': function((engine / 'source/utils.c').read_text(), 'searchList'),
        'VARIANTS': '\n'.join(function(variants, name) for name in methods),
        'MAPPER': mapper[:mapper.index('    static const')] +
                  mapper[mapper.index('    if(paramCount < 2)'):mapper.index('    switch (ep)')] +
                  '    (void)eps;\n    observed = ep;\n    return 1;\n}',
        'GETTER': getter[:getter.index('    switch(propind)')] +
                  f'    switch(propind) {{\n{branches}\n{getter_failure}\n    }}\n    return S_OK;\n}}',
        'SETTER': setter[:setter.index('    static const')] +
                  setter[setter.index('    *pretvar = NULL;\n\n'):setter.index('    switch(propind)')] +
                  f'    switch(propind) {{\n{branches}\n{setter_failure}\n    }}\n' +
                  setter[setter.rindex('    return S_OK;'):],
        'REVISIONS': ','.join(str(row['revision']) for row in data['sources']),
        'QUERIES': ',\n'.join('{%d,%d,%s}' % (query['missing'], query['ordinal'],
                                               json.dumps(query['name']) if query['name'] is not None else 'NULL')
                              for query in data['queries']),
    }
    template = Path(__file__).with_name('entity_namespace_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


def expected(table, query, slots):
    """Use the original source table's admitted names and numeric selectors."""
    name = query['name']
    named = name is not None
    ordinal = table['lookup'].get(name.lower(), -1) if named else query['ordinal']
    converted = int(named and ordinal >= 0)
    missing_name = int(named and not converted)
    raw = 0 if missing_name else ordinal
    selector = table['physical'][raw] if 0 <= raw < len(table['physical']) else None
    route = slots.get(selector, -1)
    if query['missing']:
        # Observe the existing defense exception before executing property bodies.
        permitted = selector == '_ep_defense' and not missing_name
        if permitted:
            return [[0, 1, raw, route, 0, converted | 2, 0]]
        return [[-1, int(not named), 0 if named else query['ordinal'], -1, 0, 0, 1]]
    mapper = [1 - missing_name, int(not missing_name), raw, route if not missing_name else -1,
              missing_name, converted, 0]
    getter = [0 if route >= 0 else -1, int(not missing_name), raw, route,
              2 * missing_name, converted | 2, int(route < 0)]
    setter = [0 if route >= 0 and not missing_name else -1, int(not missing_name), raw,
              route if not missing_name else -1, missing_name, converted, 1]
    return [mapper, getter, setter]


class EntityNamespaceContracts(unittest.TestCase):
    def test_native_entity_property_name_and_ordinal_dispatch(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        slots = {name: index for index, name in enumerate(data['physical_selectors'])}
        results = iter(native_output(program(data), data).splitlines())
        for row in data['sources']:
            table = data['tables'][row['table']]
            for index, query in enumerate(data['queries']):
                want = [row['revision'], index, *expected(table, query, slots)]
                self.assertEqual(json.loads(next(results)), want, (row['revision'], query))
        self.assertIsNone(next(results, None))


if __name__ == '__main__':
    unittest.main()
