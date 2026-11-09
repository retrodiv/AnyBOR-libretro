"""Check attack defaults in unsummoning, parent removal and landing damage.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-attack-initialization-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    defaults = []
    for declaration in ('const s_attack emptyattack', 's_axis_principal_float default_model_dropv'):
        match = re.search(r'(?ms)^' + declaration + r'\s*=\s*\{.*?^\};', core)
        if match is None:
            raise ValueError('Complete native attack/default velocity required')
        defaults.append(match[0])
    kill = function(core, 'kill_entity')
    kill, replaced = re.subn(r'^void kill_entity\(', 'void observed_kill_entity(', kill, count=1)
    if replaced != 1:
        raise ValueError('Complete parent-removal caller required')
    parts = dict(DEFAULTS='\n'.join(defaults), FUNCTIONS='\n'.join([
        function(core, 'update_frame'), kill, function(core, 'checkdamageonlanding')]),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=','.join('{' + ','.join(str(v) for v in row) + '}' for row in data['cases']))
    code = Path(__file__).with_name('modern_attack_initialization_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved attack initializer input')
    return code


class ModernAttackInitializationContracts(unittest.TestCase):
    def test_unsummon_parent_removal_and_landing_defaults(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
