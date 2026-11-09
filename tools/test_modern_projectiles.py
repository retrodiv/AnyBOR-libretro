"""Check profile-owned projectile speed sources and explosion animation flags.

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
from test_historical_player import function


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-projectile-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    launches = []
    for case in data['launch_cases']:
        values = [str(case[name]) for name in data['launch_fields']]
        vectors = ['{' + ','.join('.' + axis + '=' + str(value)
                                  for axis, value in zip(('x', 'y', 'z'), case[name])) + '}'
                   for name in ('model_speed', 'argument_velocity')]
        launches.append('{' + ','.join(values + vectors) + '}')
    detonations = ['{' + ','.join(str(case[name]) for name in data['detonation_fields']) + '}'
                   for case in data['detonation_cases']]
    parts = dict(FUNCTIONS='\n'.join(function(core, name) for name in
                                   ('knife_spawn', 'bomb_spawn', 'bomb_try_detonate')),
                 LAUNCH_CASES=',\n'.join(launches), DETONATION_CASES=',\n'.join(detonations),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    code = Path(__file__).with_name('modern_projectile_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved projectile contract input')
    return code


class ModernProjectileContracts(unittest.TestCase):
    def test_speed_sources_argument_mutation_and_shared_animation_gravity(self):
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
