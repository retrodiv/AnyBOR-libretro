"""Check named and numeric takeaction selection at the original insertion.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_entity_namespace import entity_namespace
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-entity-action-name-contracts.json'


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    script = (engine / 'openborscript.c').read_text()
    core = (engine / 'openbor.c').read_text()
    mapper = function(script, 'mapstrings_entityproperty')
    setter = function(script, 'openbor_changeentityproperty')

    def require(pattern, text):
        match = re.search(pattern, text, re.M)
        if not match:
            raise ValueError('Missing native takeaction code: ' + pattern)
        return match[0]

    def arm(text):
        return require(r'^    case _ep_takeaction:\n    \{[\s\S]*?^    \}', text)

    names = require(r'static const char \*proplist_takeaction\[\][^;]*;', mapper)
    actions = require(r'static const void \*actions\[\][^;]*;', setter)
    symbols = [name.strip() for name in actions.split('{', 1)[1].split('}', 1)[0].split(',') if name.strip()]
    if symbols != data['tables']['with_simple']:
        raise ValueError('Native action pointer table must match the authored identities')
    values = {
        'ENUMS': require(r'enum cep_takeaction_enum[^;]*;', script),
        'NAMESPACE': entity_namespace(script),
        'MACRO': require(r'^#define _is_not_supported_by_[^\n]*', script) + '\n' +
                 require(r'^#define MAPSTRINGS[^\n]*(?:\n[^\n]*\\)*\n\}', script),
        'SEARCH': function((engine / 'source/utils.c').read_text(), 'searchList'),
        'VARIANT': function((engine / 'source/scriptlib/ScriptVariant.c').read_text(), 'ScriptVariant_ChangeType'),
        'BOUNDARY': function(script, 'obor_has_simple_animation_action'),
        'SIMPLE_ACTION': function(core, 'common_animation_normal'),
        'MAPPER': mapper[:mapper.index('    static const')] + names + '\n' +
                  mapper[mapper.index('    if(paramCount < 2)'):mapper.index('    switch (ep)')] +
                  '    switch (ep) {\n' + arm(mapper) + '\n    }\n    return 1;\n}',
        'SETTER': setter[:setter.index('    static const')] + actions + '\n' +
                  setter[setter.index('    *pretvar = NULL;\n\n'):setter.index('    switch(propind)')] +
                  '    switch(propind) {\n' + arm(setter) + '\n    }\n' +
                  setter[setter.rindex('    return S_OK;'):],
        'STUBS': '\n'.join(f'static void {name}(void) {{ observed = {i}; }}'
                           for i, name in enumerate(symbols) if name != 'common_animation_normal'),
        'ACTIONS': ','.join('{"%s", %s}' % (name, name) for name in symbols),
        'REVISIONS': ','.join(str(row['revision']) for row in data['sources']),
        'CASES': ',\n'.join('{' + ','.join([str(case[key]) for key in ('argc', 'handle', 'kind', 'number', 'tick')] +
                            [json.dumps(case['text'])]) + '}' for case in data['cases']),
    }
    template = Path(__file__).with_name('entity_action_name_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


class EntityActionNameContracts(unittest.TestCase):
    def test_original_named_and_numeric_action_selection(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        results = iter(native_output(program(data), data).splitlines())
        for row in data['sources']:
            for i, case in enumerate(data['cases']):
                expected = [row['revision'], i, *case['expected'][row['epoch']]]
                self.assertEqual(json.loads(next(results)), expected, (row['revision'], case['name']))
        self.assertIsNone(next(results, None))


if __name__ == '__main__':
    unittest.main()
