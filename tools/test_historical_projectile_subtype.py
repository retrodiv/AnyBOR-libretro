"""Observe model directives, initialization and script subtypes on native routes.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_model_defaults import program as model_program
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-projectile-subtype-contracts.json'
COMMANDS = ('CMD_MODEL_ONAF', 'CMD_MODEL_BOOMERANG', 'CMD_MODEL_BOMB', 'CMD_MODEL_PLAYBOMB')


def native_program(data):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openbor.c').read_text(encoding='latin1')
    script = (engine / 'openborscript.c').read_text(encoding='latin1')
    loader = function(source, 'load_cached_model')
    damage = loader[loader.index('    if(newchar->candamage < 0)'):]
    from_enemy = damage.index('        case TYPE_ENEMY:')
    to_player = damage.index('        case TYPE_PLAYER:', from_enemy)
    wrappers = 'static void default_enemy_damage(s_model *newchar)\n{\n' + (
        '    switch(newchar->type)\n    {\n' + damage[from_enemy:to_player] +
        '    default: abort();\n    }\n}\n')

    _, arms = switch_cases(script, 'openbor_getentityproperty', 'propind', outermost=True)
    wrappers += ('static LONG read_subtype(entity *ent)\n{\n'
                 '    ScriptVariant result = {0}, *output = &result;\n'
                 '    ScriptVariant **pretvar = &output;\n'
                 '    switch(0)\n    {\n    case 0:' + arms['_ep_subtype']['body'] +
                 '    }\n    if(result.vt != VT_INTEGER) abort();\n    return result.lVal;\n}\n')

    mapper = function(script, 'mapstrings_transconst')
    start = mapper.index('        IICMPCONST(COMPATIBLEVERSION)')
    subtype_start = mapper.index('        ICMPCONST(SUBTYPE_NONE)')
    subtype_end = mapper.index('        ICMPCONST(AIMOVE1_NORMAL)', subtype_start)
    completion = mapper.index('        else\n        {\n            found = FALSE;', subtype_end)
    macros_begin = script.index('#define IICMPCONST(')
    macros_end = script.index('#define ICMPSCONSTA(', macros_begin)
    functions = '\n'.join((
        function(source, 'obor_level_spawn_count'),        '#pragma GCC diagnostic push\n'
        '#pragma GCC diagnostic ignored "-Wimplicit-fallthrough"\n' +
        function(source, 'ent_default_init') + '#pragma GCC diagnostic pop\n',
        function(script, 'obor_profile_subtype_value'),
        wrappers,
        script[macros_begin:macros_end],
        mapper[:start] + '        IICMPCONST(TYPE_ENEMY)\n' +
        mapper[subtype_start:subtype_end] + mapper[completion:],
        function(script, 'openbor_transconst'),
    ))
    template = Path(__file__).with_name('projectile_subtype_contract.c.in').read_text()
    return template.replace('@FUNCTIONS@', functions).replace(
        '@PROFILES@', ','.join(str(row['revision']) for row in data['sources']))


class ProjectileSubtypeContracts(unittest.TestCase):
    def setUp(self):
        self.data = load_contract_fixture(FIXTURE)
        self.rows = self.data['sources']
        revisions = [row['revision'] for row in self.rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(self.data, self.data['expected_revisions']))

    def test_projectile_model_commands(self):
        actual = [json.loads(line) for line in native_output(
            model_program(self.data, COMMANDS), self.data).splitlines()]
        expected = [dict(revision=row['revision'], **entry)
                    for row in self.rows for entry in self.data['contracts'][row['contract']]['model']]
        self.assertEqual(len(actual), len(expected))
        for result, reference in zip(actual, expected):
            with self.subTest(revision=reference['revision'], case=reference):
                self.assertEqual(result, reference)

    def test_script_subtypes_and_entity_defaults(self):
        actual = [json.loads(line) for line in native_output(native_program(self.data), self.data).splitlines()]
        self.assertEqual(len(actual), len(self.rows))
        for result, row in zip(actual, self.rows):
            reference = self.data['contracts'][row['contract']]
            with self.subTest(revision=row['revision']):
                self.assertEqual(result['revision'], row['revision'])
                self.assertEqual(result['entities'], reference['entities'])
                self.assertEqual(len(result['script']), len(reference['script']))
                for seen, expected in zip(result['script'], reference['script']):
                    self.assertEqual(len(seen), len(expected))
                    for value, want in zip(seen, expected):
                        if want is not None:
                            self.assertEqual(value, want)


if __name__ == '__main__':
    unittest.main()
