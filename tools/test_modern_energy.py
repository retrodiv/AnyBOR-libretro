"""Check profile-owned energy admission and its non-monotonic seal boundary.

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
from test_historical_player import function


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-energy-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    body = function((engine / 'openbor.c').read_text(), 'check_energy')
    rows = []
    for case in data['cases']:
        values = [str(case[name]) for name in data['case_fields']]
        if any(re.fullmatch(r'-?[0-9]+|[A-Z][A-Z0-9_]*', value) is None
               for value in values):
            raise ValueError('Expected a literal or named source constant')
        rows.append('{' + ','.join(values) + '}')
    parts = dict(FUNCTION=body, CASES=',\n'.join(rows),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    code = Path(__file__).with_name('modern_energy_contract.c.in').read_text()
    for name, value in parts.items():
        code = code.replace('@' + name + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved energy contract input')
    return code


class ModernEnergyContracts(unittest.TestCase):
    def test_original_guard_and_juggle_point_comparisons(self):
        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        eligible = function(source, 'check_blocking_eligible')
        points = braced_statement(eligible,
                                  'if(obor_profile_build >= 7553\n       ? ent->modeldata.profile_guardpoints != 0')
        juggle = re.search(r'(?m)^ +if\((obor_profile_build >= 7553\n'
                           r' +\? attack->jugglecost > target->jugglepoints\n'
                           r' +: [^\n]+)\)$', function(source, 'do_attack'))
        self.assertIsNotNone(juggle)
        code = r'''
#include "openbor.h"
#include <stdlib.h>

uint32_t obor_profile_build;
u32 _time = 20;
int magic_type = 1;
s_global_config global_config;
static entity actor;
entity *self = &actor;

void recursive_damage_update(entity *target) { (void)target; }
int do_energy_charge(entity *target) { (void)target; return 0; }

@UPDATE_HEALTH@

static int has_guard(entity *ent)
{
@GUARD@
    return 1;
}

static int exceeds_juggle_cost(const s_attack *attack, const entity *target)
{
    return @JUGGLE@;
}

int main(void)
{
    static const unsigned builds[] = {7369, 7391, 7420, 7510, 7511, 7533};
    s_attack attack = {0};
    actor.modeldata.guardrate = 2;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        const int signed_points = builds[i] < 7511u;
        actor.modeldata.guardpoints.max = 10;
        actor.modeldata.guardpoints.current = (unsigned int)-4;
        actor.guardtime = 0;
        if (has_guard(&actor) != !signed_points)
        {
            abort();
        }

        update_health();
        if (actor.modeldata.guardpoints.current != (signed_points ? (unsigned int)-2 : 10u) ||
            actor.guardtime != _time + GAME_SPEED)
        {
            abort();
        }

        actor.modeldata.guardpoints.max = (unsigned int)-1;
        actor.modeldata.guardpoints.current = 5;
        actor.guardtime = 0;
        update_health();
        if (actor.modeldata.guardpoints.current != (signed_points ? 5u : 7u))
        {
            abort();
        }

        actor.modeldata.jugglepoints.current = (unsigned int)-2;
        attack.jugglecost = 1;
        if (exceeds_juggle_cost(&attack, &actor) != signed_points)
        {
            abort();
        }
        actor.modeldata.jugglepoints.current = 2;
        attack.jugglecost = -1;
        if (exceeds_juggle_cost(&attack, &actor) != !signed_points)
        {
            abort();
        }
    }
    return 0;
}
'''
        program_code = (code.replace('@UPDATE_HEALTH@', function(source, 'update_health'))
                        .replace('@GUARD@', points).replace('@JUGGLE@', juggle[1]))
        self.assertEqual(native_output(program_code, data, engine_source=engine), '')

    def test_original_infinite_energy_refill(self):
        data = {'engine': '7533'}
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text()
        code = r'''
#include "openbor.h"
#include <stdlib.h>

uint32_t obor_profile_build;
u32 _time;
int magic_type = 1;
s_global_config global_config;
static entity actor;
entity *self = &actor;

void recursive_damage_update(entity *target) { (void)target; }
int do_energy_charge(entity *target) { (void)target; return 0; }

@UPDATE_HEALTH@

int main(void)
{
    static const unsigned builds[] = {7369, 7370, 7371, 7391, 7420, 7533};
    actor.modeldata.mp = 25;
    for (size_t i = 0; i < sizeof(builds) / sizeof(*builds); ++i)
    {
        obor_profile_build = builds[i];
        global_config.cheats = CHEAT_OPTIONS_ENERGY_ACTIVE;
        actor.modeldata.type = TYPE_PLAYER;
        actor.energy_state.mp_current = 7;
        update_health();
        if (actor.energy_state.mp_current != (builds[i] < 7371u ? 7 : 25))
        {
            abort();
        }

        actor.modeldata.type = TYPE_ENEMY;
        actor.energy_state.mp_current = 7;
        update_health();
        if (actor.energy_state.mp_current != 7)
        {
            abort();
        }

        global_config.cheats = 0;
        actor.modeldata.type = TYPE_PLAYER;
        update_health();
        if (actor.energy_state.mp_current != 7)
        {
            abort();
        }
    }
    return 0;
}
'''
        self.assertEqual(native_output(code.replace('@UPDATE_HEALTH@', function(source, 'update_health')),
                                       data, engine_source=engine), '')

    def test_energy_admission_and_both_seal_boundaries(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        for row in data['sources']:
            self.assertEqual(len(data['contracts'][row['contract']]), len(data['cases']))
        actual = json.loads(native_output(program(data), data))
        expected = dict(status='PASS', profiles=[
            dict(revision=row['revision'], results=data['contracts'][row['contract']])
            for row in data['sources']])
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
