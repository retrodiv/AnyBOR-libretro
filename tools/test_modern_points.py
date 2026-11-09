"""Check profile-owned guard and juggle state and arithmetic.

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
from test_historical_player import function, switch_cases


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-points-contracts.json'


def one(pattern, source, label):
    matches = re.findall(pattern, source, re.S)
    if len(matches) != 1:
        raise ValueError('Expected one complete points contract: ' + label)
    return matches[0]


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    labels = ['_ep_guardpoints', '_ep_jugglepoints', '_ep_maxguardpoints',
              '_ep_maxjugglepoints']
    getter = switch_cases(script, 'openbor_getentityproperty', 'propind')[1]
    setter = switch_cases(script, 'openbor_changeentityproperty', 'propind')[1]
    loader = switch_cases(core, 'load_cached_model', 'cmd', outermost=True)[1]
    load_cases = '\n'.join('case ' + key + ':' + loader[key]['body'] for key in
                           ('CMD_MODEL_GUARDPOINTS', 'CMD_MODEL_JUGGLEPOINTS'))
    defaults = one(r'(newchar->jugglepoints = \(s_status_points\).*?)'
                   r'(?=    newchar->mpswitch)', function(core, 'init_model'), 'defaults')
    initialize = one(r'(e->nograb_default = 0;.*?)(?=    switch\(e->modeldata.type\))',
                     function(core, 'ent_default_init'), 'entity initialization')
    recovery = function(core, 'update_health').split('//Damage over time.', 1)[0]
    recovery = recovery[recovery.index('{') + 1:]
    deduction = one(r'(    if\(obor_profile_build >= 7553\).*?)'
                    r'(?=\n\s*/\*\s*\n\s*\* Blocked hit)',
                    function(core, 'set_blocking_action'), 'guard deduction')
    attack = function(core, 'do_attack')
    eligibility = one(r'(        if\(obor_profile_build >= 7553 && '
                      r'obor_profile_build < 7559\).*?)(?=        temp = self;)',
                      attack, 'airborne eligibility')
    consumption = one(r'(            if\(inair\(self\)\)\s*\{\s*'
                      r'if\(obor_profile_build >= 7553\).*?\n            \})',
                      attack, 'juggle deduction')
    resets = []
    for name, actor in [('set_rise', 'iRise'), ('set_riseattack', 'iRiseattack')]:
        statement = one(r'(if\(obor_profile_build >= 7553\)\s*\{\s*' + actor +
                        r'->jugglepoints = [^;]+;\s*\}\s*else\s*\{\s*' + actor +
                        r'->modeldata.jugglepoints.current = [^;]+;\s*\})',
                        function(core, name), name)
        resets.append('static void probe_' + name + '(entity *' + actor + ')\n{\n' +
                      statement + '\n}\n')
    predicates = []
    for name, actor in [('set_pain', 'iPain'), ('checkdamagedrop', 'target_entity'),
                        ('calculate_force_damage', 'target'),
                        ('checkdamageonlanding', 'acting_entity'),
                        ('common_takedamage', 'acting_entity')]:
        expression = one(r'(\(obor_profile_build >= 7553\s*\? .*?'
                         r'guardpoints.current <= 0\))', function(core, name), name)
        predicates.append('static int probe_' + name + '(entity *' + actor + ')\n{\n'
                          'return ' + expression + ';\n}\n')
    pain = one(r'(    if\(\(obor_profile_build >= 7553.*?)(?=    else if\(type == -1)',
               function(core, 'set_pain'), 'guard-break reset')
    helpers = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    parts = dict(DEFAULTS=defaults, INITIALIZE=initialize, LOAD_CASES=load_cases,
                 ELIGIBLE=function(core, 'check_blocking_eligible'),
                 RECOVERY=recovery, GUARD_DEDUCTION=deduction,
                 AIRBORNE_ELIGIBILITY=eligibility, JUGGLE_DEDUCTION=consumption,
                 RESETS='\n'.join(resets), PREDICATES='\n'.join(predicates), PAIN=pain,
                 GET_CASES='\n'.join('case ' + key + ':' + getter[key]['body'] for key in labels),
                 SET_CASES='\n'.join('case ' + key + ':' + setter[key]['body'] for key in labels),
                 VARIANTS='\n'.join(function(helpers, name) for name in
                                    ('ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
                 SCRIPT_CASES=',\n'.join('{' + ','.join(
                     json.dumps(row[key]) if key in ('guard', 'juggle') else str(row[key])
                     for key in data['script_fields']) + '}' for row in data['script_cases']),
                 GUARD_CASES=',\n'.join('{' + ','.join(str(row[key]) for key in
                     data['guard_fields']) + '}' for row in data['guard_cases']),
                 JUGGLE_CASES=',\n'.join('{' + ','.join(str(row[key]) for key in
                     data['juggle_fields']) + '}' for row in data['juggle_cases']))
    code = Path(__file__).with_name('modern_points_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved points contract input')
    return code


class ModernPointsContracts(unittest.TestCase):
    def test_model_entity_state_legacy_access_and_guard_juggle_operations(self):
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
