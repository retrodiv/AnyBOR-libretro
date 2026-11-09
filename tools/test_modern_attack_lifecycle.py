"""Check default script attacks and mutable attack lifetime across enemies.

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


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-attack-lifecycle-contracts.json'


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


class ModernAttackLifecycleContracts(unittest.TestCase):
    def test_script_defaults_computed_damage_and_enemy_loop(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(
            revision=row['revision'], **data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
