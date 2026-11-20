"""Check default script attacks and mutable attack lifetime across enemies.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, contract_revisions, load_contract_fixture
from test_early_jump_walkoff import braced_statement
from test_historical_common_think import ROOT, native_output
from test_historical_player import function


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-attack-lifecycle-contracts.json'
WEAPON_FIXTURE = FIXTURE.with_name('profile-rejoin-enemy-weapon-contracts.json')
SCRIPT_QUERY_FIXTURE = FIXTURE.with_name('profile-4432-script-damage-and-empty.json')
LAST_PLAYER_FIXTURE = FIXTURE.with_name('profile-4432-last-player-timer.json')
GROUND_SPECIAL_FIXTURE = FIXTURE.with_name('profile-ground-special.json')


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    default = re.search(r'(?ms)^const s_attack emptyattack\s*=\s*\{.*?^\};', core)
    if default is None:
        raise ValueError('Complete default attack initializer required')
    parts = dict(DEFAULT=default[0], FUNCTIONS='\n'.join([
        function(script, 'openbor_damageentity'), function(script, 'openbor_getcomputeddamage'),
        function(core, 'drop_all_enemies')]),
        VARIANTS='\n'.join(function(variant, name) for name in (
            'ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=','.join('{' + ','.join(str(case[k]) for k in data['parameters']) + '}'
                       for case in data['cases']),
        LOOP_CASES=','.join('{' + ','.join(str(v) for v in case) + '}'
                            for case in data['loop_cases']))
    text = Path(__file__).with_name('modern_attack_lifecycle_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved attack lifecycle contract input')
    return text


def rejoin_weapon_program(data, engine):
    source = (engine / 'openbor.c').read_text()
    declarations = dict(
        FUNCTION=function(source, 'drop_all_enemies'),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=',\n'.join('{%d,%d}' % (case['weapon_loss'], case['blocked']) for case in data['cases']),
    )
    text = Path(__file__).with_name('rejoin_enemy_weapon_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: declarations[match[1]], text)


class ModernAttackLifecycleContracts(unittest.TestCase):
    def check_ground_special(self, physical):
        data = load_contract_fixture(GROUND_SPECIAL_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == physical]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][physical])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / physical))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        think = function(source, 'player_think')
        values = {
            'SPECIAL': function(source, 'check_special'),
            'DROP_ALL': function(source, 'drop_all_enemies'),
            'DEFAULT': re.search(r'(?ms)^const s_collision_attack emptyattack\s*=\s*\{.*?^\};', source)[0],
            'GRAB': braced_statement(think, 'if(self->grabbing && '),
            'CHAIN': braced_statement(think, 'else if(perform_atchain())').removeprefix('else '),
            'ROWS': ','.join('{%du,%d}' % (row['revision'], row['cantfire_blocks']) for row in rows),
        }
        template = Path(__file__).with_name('ground_special_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda token: values[token[1]], template)
        output = native_output(code, {'engine': physical}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_ground_special(self):
        self.check_ground_special('4432')

    def test_6391_ground_special(self):
        self.check_ground_special('6391')

    def test_4432_last_player_continue_timer(self):
        data = load_contract_fixture(LAST_PLAYER_FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and 4510 <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        program_text = Path(__file__).with_name('last_player_timer_contract.c.in').read_text()
        program_text = program_text.replace('@PLAYER_DIE@', function(source, 'player_die'))
        program_text = program_text.replace('@ROWS@', ',\n'.join('{%d,%d}' % (
            row['revision'], row['all_slots']) for row in data['sources']))
        actual = native_output(program_text, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in actual.splitlines()], revisions)

    def test_script_defaults_computed_damage_and_enemy_loop(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(
            revision=row['revision'], **data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)

    def test_4432_rejoin_falls_respect_weapon_loss_mode(self):
        data = load_contract_fixture(WEAPON_FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = ROOT / 'src/engines' / data['engine']
        expected = [dict(revision=row['revision'],
                         cases=[case[row['contract']] for case in data['cases']])
                    for row in data['sources']]
        output = native_output(rejoin_weapon_program(data, engine), data,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([json.loads(line) for line in output.splitlines()], expected)

    def test_4432_computed_damage_and_empty_results(self):
        data = load_contract_fixture(SCRIPT_QUERY_FIXTURE)
        rows = data['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        for profile in contract_profiles(data, pin['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and 4510 <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        core = (engine / 'openbor.c').read_text()
        script = (engine / 'openborscript.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        reverse = function(script, 'Script_GetFunctionName')
        reverse = braced_statement(reverse, 'if (obor_has_computed_damage() &&')
        registration = braced_statement(function(script, 'Script_LoadSystemFunctions'),
                                        'if(obor_has_computed_damage())')
        self.assertIn('return "getcomputeddamage";', reverse)
        self.assertIn('(void *)openbor_getcomputeddamage, "getcomputeddamage"', registration)
        replacements = dict(
            DEFAULT=re.search(r'(?ms)^const s_collision_attack emptyattack\s*=\s*\{.*?^\};', core)[0],
            VARIANTS='\n'.join(function(variant, name) for name in
                               ('ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
            CORE='\n'.join(function(core, name) for name in ('obor_apply_damage_factor', 'obor_force_damage')),
            QUERIES='\n'.join(function(script, name) for name in
                              ('obor_has_computed_damage', 'system_isempty',
                               'obor_computed_damage_actor', 'openbor_getcomputeddamage')),
            REVERSE=reverse,
            REGISTRATION=registration,
            ROWS=',\n'.join('{%d,%d,%d}' % (row['revision'], row['computed'], row['empty_result'])
                            for row in rows),
        )
        code = Path(__file__).with_name('script_damage_and_empty_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: replacements[match[1]], code)
        results = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in results.splitlines()], [row['revision'] for row in rows])


if __name__ == '__main__':
    unittest.main()
