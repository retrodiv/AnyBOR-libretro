"""Preserve native script damage results and define health endpoints.

Whole entry functions, native records and conversions use bounded attack,
defense and kill observers. Full combat and object lifetime are separate.
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
FIXTURE = HERE / 'fixtures/script-health-native-baseline.json'


def program(engine, profiles, *, wrong_threshold=False):
    oracle = load_contract_fixture(FIXTURE)
    data = oracle['engines'][engine.name]
    source = (engine / 'openborscript.c').read_text(encoding='latin1')
    entry = function(source, 'openbor_damageentity')
    if wrong_threshold:
        threshold = 'if(ent->' + data['health'] + ' <= 0)'
        if entry.count(threshold) != 1:
            raise ValueError('One native direct-health threshold required')
        entry = entry.replace(threshold, threshold.replace('<=', '<'), 1)
    variant, = (engine / 'source').rglob('ScriptVariant.c')
    variants = variant.read_text(encoding='latin1')
    header = variant.with_suffix('.h').read_text(encoding='latin1')
    attack_type, = re.findall(r'\b(s_\w+)\s+(?:atk|attack)\s*(?:=[^;]*)?;', data['entry'])
    default, = re.findall(r'(?ms)^(?:const\s+)?(?:s_attack|s_collision_attack)\s+emptyattack\s*=\s*\{.*?^\};',
                         (engine / 'openbor.c').read_text(encoding='latin1'))
    # Native script declarations expose mutable extern storage. Preserve the
    # complete engine initializer as a bounded provider in this translation unit.
    default = re.sub(r'^const\s+', '', default)
    helper = function(source, 'obor_script_damageentity') if data['wide_existing_helper_unchanged'] else ''
    legacy = data['amount'] == 'force'
    boundary = re.search(r'if\(obor_profile_build >= (\d+)\)', data['entry'])
    shared_before = re.search(r'else if\(obor_profile_build < (\d+)\)', data['entry'])
    has_shared = 'atk = attack;' in data['entry'] or bool(helper)
    default_force = '17' if has_shared else '0'
    if shared_before:
        default_force = '(obor_profile_build<%su?17:0)' % shared_before[1]
    if legacy:
        default_force = '(obor_profile_build<%su?1:%s)' % (boundary[1], default_force) if boundary else '1'
    callback_call = re.search(r'(?:self|ent)->takedamage\(([^;]*)\)', entry)
    if callback_call is None:
        raise ValueError('A native damage callback required')
    args = callback_call[1].split(',')
    if args[0].strip() == 'ent':
        callback = 'entity *victim,entity *other,fixture_attack *value,int reset,const s_defense *defense'
        assertions = 'assert(victim==&target && reset==0 && defense==&defense_value);'
    else:
        callback = 'entity *other,fixture_attack *value'
        assertions = 'assert(self==&target);'
        if len(args) >= 3:
            callback += ',int reset'
            assertions += 'assert(reset==0);'
        if len(args) == 4:
            callback += ',s_defense *defense'
            assertions += 'assert(defense==&defense_value);'
    if 'KILL_ENTITY_TRIGGER_SCRIPT_DAMAGEENTITY' in entry:
        kill_provider = 'void kill_entity(entity *ent,e_kill_entity_trigger reason){assert(ent==&target && reason==KILL_ENTITY_TRIGGER_SCRIPT_DAMAGEENTITY);++kills;}'
    elif 'kill_entity(ent)' in entry:
        kill_provider = 'void kill_entity(entity *ent){assert(ent==&target);++kills;}'
    else:
        kill_provider = 'void kill(entity *ent){assert(ent==&target);++kills;}'
    defense = ''
    if 'defense_find_current_object' in entry:
        if args[0].strip() == 'ent':
            defense = 'const s_defense *defense_find_current_object(const entity *ent,const s_body *body,attack_type_t type)'
        else:
            defense = 's_defense *defense_find_current_object(entity *ent,s_body *body,e_attack_types type)'
        defense += '{assert(ent==&target && !body);defense_type=(int)type;++defenses;return &defense_value;}'
    attack_limit = ''
    if 'obor_attack_valid' in entry:
        limit, = re.findall(r'(?m)^int[ \t]+max_attack_types[ \t]*=[^;]*;',
                           (engine / 'openbor.c').read_text(encoding='latin1'))
        attack_limit = '\n' + limit
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
        SCRIPT_HEADER='openborscript.h' if (engine / 'openborscript.h').is_file() else 'scriptcommon.h',
        POP_ARGUMENTS='int length' if 'StrCache_Pop(int length)' in header else 'void',
        POP_UNUSED='(void)length;' if 'StrCache_Pop(int length)' in header else '',
        ATTACK_TYPE=attack_type, DEFAULT=default,
        CONVERSIONS='\n'.join(function(variants, n) for n in
                             ('ScriptVariant_ChangeType', 'ScriptVariant_Clear', 'ScriptVariant_IntegerValue')),
        CALLBACK_ARGUMENTS=callback, CALLBACK_CHECKS=assertions,
        KILL_PROVIDER=kill_provider, DEFENSE_PROVIDER=defense,
        DEFENSE_DECL='static s_defense defense_value;' if defense else '',
        IDS_HEADER='#include "source/openborscript/profile_ids.h"' if
            (engine / 'source/openborscript/profile_ids.h').is_file() else '',
        NATIVE_ATTACK_LIMIT=attack_limit,
        HELPER=helper, ORIGINAL=rename_identifiers(data['entry'], {'openbor_damageentity': 'before_damage'}),
        ENTRY=entry, HEALTH=data['health'], DEFAULT_FORCE=default_force,
        PROFILES=','.join(str(oracle['profiles'][p['build']]['revision'])+'u' for p in profiles))
    text = (HERE / 'script_health_arithmetic.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved script health input')
    return text


class ScriptHealthArithmeticTests(unittest.TestCase):
    def test_native_defined_results_endpoints_and_callback_order_by_profile(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        self.assertEqual(set(load_contract_fixture(FIXTURE)['profiles']), {p['build'] for p in pin['profiles']})
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
            with self.subTest(engine=row['build']):
                result = run_native(engine, program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                self.assertEqual(value['cases'], 168 * len(profiles))

    def test_wrong_zero_health_threshold_is_detected(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines' / pin['engines'][0]['build']
        profile = next(p for p in pin['profiles'] if p['engine'] == engine.name)
        result = run_native(engine, '#define THRESHOLD_ONLY 1\n' + program(engine, [profile], wrong_threshold=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('actual.kills == expected.kills', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
