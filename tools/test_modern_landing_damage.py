"""Check landing damage eligibility through the native gravity caller.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_early_jump_walkoff import braced_statement
from test_historical_common_think import ROOT, native_output
from test_historical_entity_namespace import entity_namespace
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-landing-damage-contracts.json'
SETTLED_FIXTURE = FIXTURE.with_name('profile-4432-settled-landing-damage.json')
FIELDS_FIXTURE = FIXTURE.with_name('profile-4432-throw-landing-fields.json')
DEFERRED_FIXTURE = FIXTURE.with_name('profile-4432-deferred-landing.json')
FORCE_QUERY_FIXTURE = FIXTURE.with_name('profile-4432-attack-landing-force.json')


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    parts = dict(FUNCTION=function((engine / 'openbor.c').read_text(), 'check_gravity'),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    rows = []
    for row in data['cases']:
        values = [str(v) for v in row]
        if any(re.fullmatch(r'-?[0-9]+|[A-Z][A-Z0-9_]*', v) is None for v in values):
            raise ValueError('Literal or source constant required')
        rows.append('{' + ','.join(values) + '}')
    parts['CASES'] = ','.join(rows)
    code = Path(__file__).with_name('modern_landing_damage_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved landing damage input')
    return code


class ModernLandingDamageContracts(unittest.TestCase):
    def test_4432_attack_landing_force_query(self):
        data = load_contract_fixture(FORCE_QUERY_FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openborscript.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        parts = {
            'CACHE': variant[variant.index('typedef struct'):variant.index('// find an existing constant')],
            'GETTER': '\n'.join(function(source, name) for name in (
                'obor_script_collision_coordinates', 'openbor_get_attack_property')),
            'ROWS': ','.join('{%du,%d}' % (row['revision'], row['force_selector']) for row in rows),
        }
        template = Path(__file__).with_name('attack_landing_force_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)
        output = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_health_cheat_type_and_native_landing_gates(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)

    def test_4432_landing_damage_source_and_settling(self):
        data = load_contract_fixture(SETTLED_FIXTURE)
        rows = data['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        gravity = function(source, 'check_gravity')
        damage = function(source, 'common_takedamage')
        profile_rules = re.search(r'(?m)^    const int opponent_landing[^\n]+\n'
                                  r'    const int live_opponent_landing[^\n]+\n'
                                  r'    const int settled_landing[^\n]+', gravity)[0]
        sections = {
            'GRAVITY': profile_rules + '\n' + braced_statement(
                gravity, 'if(self->damage_on_landing > 0 && !self->dead &&'),
            'CONTINUATION': braced_statement(damage, 'if(self->damage_on_landing)'),
            'FALL': braced_statement(damage, 'if(obor_profile_build >= 4642 && obor_profile_build <= 4750 && attack->obor_landing_hit)'),
            'REVISIONS': ','.join(str(row['revision']) for row in rows),
            'CASES': ',\n'.join('{' + ','.join(str(int(n)) for n in case) + '}' for case in data['cases']),
        }
        code = Path(__file__).with_name('settled_landing_damage_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: sections[match[1]], code)
        actual = [json.loads(line) for line in native_output(
            code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',)).splitlines()]
        expected = [[row['revision'], *case] for row in rows for case in data['contracts'][row['contract']]]
        self.assertEqual(len(actual), len(expected))
        for expect, result in zip(expected, actual):
            with self.subTest(revision=expect[0], case=expect[1]):
                self.assertEqual(result, expect)

    def test_4432_landing_damage_force_and_type_records(self):
        data = load_contract_fixture(FIELDS_FIXTURE)
        rows = data['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        game = (engine / 'openbor.c').read_text(encoding='latin-1')
        script = (engine / 'openborscript.c').read_text(encoding='latin-1')
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin-1')
        get = switch_cases(script, 'openbor_getentityproperty', 'propind')[1]
        change = switch_cases(script, 'openbor_changeentityproperty', 'propind')[1]
        load = function(game, 'load_cached_model')
        common = function(game, 'common_takedamage')
        resets = []
        for i, name in enumerate(('doland', 'arrow_move', 'boomerang_move', 'star_move',
                                  'drop_all_enemies', 'check_gravity')):
            body = function(game, name)
            reset = re.search(r'(?m)^[ \t]*(self|ent_list\[i\])->damage_on_landing = 0;\n'
                              r'[ \t]*\1->damage_on_landing_type = -1;', body)[0]
            resets.append(f'case {i}: {reset}\n    break;')
        sections = dict(
            GET=get['_ep_damage_on_landing']['body'],
            SET=change['_ep_damage_on_landing']['body'],
            VARIANTS='\n'.join(function(variants, name) for name in
                               ('ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
            TYPE=function(game, 'obor_landing_damage_type'),
            DEFAULT=re.search(r'(?ms)^const s_collision_attack emptyattack\s*=\s*\{.*?^\};', game)[0],
            COMMAND=re.search(r'(?ms)^            case CMD_MODEL_DAMAGEONLANDING:.*?^                break;', load)[0],
            COPY=re.search(r'(?m)^            self->damage_on_landing = attack->damage_on_landing;\n'
                           r'            self->damage_on_landing_type = attack->damage_on_landing_type;', common)[0],
            RESET='\n'.join(resets),
            RESET_COUNT=str(len(resets)),
            REVISIONS=','.join(str(row['revision']) for row in rows),
        )
        template = Path(__file__).with_name('throw_landing_fields_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: sections[match[1]], template)
        actual = [json.loads(line) for line in native_output(
            code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',)).splitlines()]
        expected = [[row['revision'], *data['contracts'][row['contract']]] for row in rows]
        self.assertEqual(actual, expected)

    def test_4432_deferred_landing_damage_and_death(self):
        data = load_contract_fixture(DEFERRED_FIXTURE)
        rows = data['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(revisions), len(rows))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        game = (engine / 'openbor.c').read_text(encoding='latin-1')
        script = (engine / 'openborscript.c').read_text(encoding='latin-1')
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin-1')
        getter = switch_cases(script, 'openbor_getentityproperty', 'propind')[1]
        setter = switch_cases(script, 'openbor_changeentityproperty', 'propind')[1]
        self.assertNotIn('_ep_die_on_landing', setter)
        read_type, write_type = re.findall(r'(?ms)^    case _sv_lasthitt:\n(.*?)^        break;', game)
        code = Path(__file__).with_name('deferred_landing_contract.c.in').read_text()
        values = dict(
            GET_LAST_TYPE=read_type,
            SET_LAST_TYPE=write_type,
            NAMESPACE=entity_namespace(script),
            SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
            GET_DIE=getter['_ep_die_on_landing']['body'],
            VARIANTS='\n'.join(function(variant, name) for name in
                               ('ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
            DEFAULT=re.search(r'(?ms)^const s_collision_attack emptyattack\s*=\s*\{.*?^\};', game)[0],
            METHODS='\n'.join(function(game, name) for name in (
                'obor_apply_damage_factor', 'obor_force_damage', 'checkdamage', 'common_takedamage',
                'obor_landing_damage_source', 'obor_apply_pending_landing_damage',
                'obor_check_deferred_landing')),
            GRAVITY_CALL=braced_statement(function(game, 'check_gravity'),
                                          'if(obor_profile_build >= 4665 && obor_profile_build <= 4750)'),
            REVISIONS=',\n'.join('{%d,%d,%d}' % (row['revision'], row['die_ordinal'], row['direction_ordinal'])
                                 for row in rows),
            CASES=',\n'.join('{' + ','.join(str(int(n)) for n in case) + '}' for case in data['cases']),
        )
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], code)
        actual = [json.loads(line) for line in native_output(
            code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',)).splitlines()]
        expected = [[row['revision'], *case] for row in rows for case in data['contracts'][row['contract']]]
        self.assertEqual(len(actual), len(expected))
        for result, reference in zip(actual, expected):
            with self.subTest(revision=reference[0], case=reference[1]):
                self.assertEqual(result, reference)


if __name__ == '__main__':
    unittest.main()
