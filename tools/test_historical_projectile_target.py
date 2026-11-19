"""Exercise projectile and target policy through the native callers.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-projectile-target-contracts.json'
CALLERS = ('ent_spawn_ent', 'ent_summon_ent', 'arrow_takedamage', 'check_gravity', 'common_move')


class ProjectileTargetContracts(unittest.TestCase):
    def test_original_projectile_and_target_policy(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text(encoding='latin1')
        functions = '\n'.join(function(source, name) for name in CALLERS)
        template = Path(__file__).with_name('historical_projectile_target_contract.c.in').read_text()
        program = template.replace('@FUNCTIONS@', functions).replace(
            '@PROFILES@', ','.join(str(rev) for rev in revisions))
        observed = [json.loads(line) for line in native_output(program, data).splitlines()]
        expected = [dict(revision=row['revision'], **data['contracts'][row['contract']])
                    for row in data['sources']]
        self.assertEqual(len(observed), len(expected))
        for actual, reference in zip(observed, expected):
            with self.subTest(revision=reference['revision']):
                self.assertEqual(actual, reference)


if __name__ == '__main__':
    unittest.main()
