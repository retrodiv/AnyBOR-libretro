"""Check complete pit/lifespan, throw and projectile-wall attack callers.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-attack-transition-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    definitions = []
    for declaration in ('const s_attack emptyattack', 's_axis_principal_float default_model_dropv'):
        match = re.search(r'(?ms)^' + declaration + r'\s*=\s*\{.*?^\};', core)
        if match is None:
            raise ValueError('Native attack/default velocity initializer required')
        definitions.append(match[0])
    distance = re.search(r'(?m)^static int DEFAULT_OFFSCREEN_KILL\s*=\s*[^;]+;', core)
    if distance is None:
        raise ValueError('Native offscreen distance default required')
    definitions.append(distance[0])
    parts = dict(DEFAULTS='\n'.join(definitions), FUNCTIONS='\n'.join(function(core, name) for name in (
        'check_lost', 'dothrow', 'projectile_wall_deflect')),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=','.join('{' + ','.join(str(v) for v in row) + '}' for row in data['cases']))
    text = Path(__file__).with_name('modern_attack_transitions_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved attack transition input')
    return text


class ModernAttackTransitionContracts(unittest.TestCase):
    def test_lost_throw_and_wall_attack_payloads(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
