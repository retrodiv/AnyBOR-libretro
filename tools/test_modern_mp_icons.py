"""Check profile-owned MP icon loading, caching and HUD selection.

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


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-mp-icon-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE',
                                ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    initialization = function(core, 'init_model')
    initializers = re.findall(r'newchar->icon = \(s_icon\)\{.*?\n    };',
                              initialization, re.S)
    hud = function(core, 'predrawstatus')
    blocks = re.findall(r'(?ms)^            if\s*\(player\[i\]\.ent->modeldata\.mp\).*?'
                        r'(?=^            font_printf)', hud)
    loader = function(core, 'load_cached_model')
    commands = re.findall(r'(?ms)^            case CMD_MODEL_ICONMP\w+:.*?break;', loader)
    if len(initializers) != 1 or len(blocks) != 1 or len(commands) != 5:
        raise ValueError('Expected complete MP initializer, HUD block and five loader cases')
    registry = (engine / 'source/openborscript/commands.c').read_text()
    helpers = '\n'.join(function(registry, name) for name in
                        ('createModelCommandList', 'getCommandlistCommand'))
    helpers += '\n' + function((engine / 'source/utils.c').read_text(), 'lc')
    cases = ['{' + ','.join(str(row[key]) for key in data['hud_fields']) + '}'
             for row in data['hud_cases']]
    parts = dict(INITIALIZER=initializers[0], HUD_BLOCK=blocks[0],
                 LOAD_CASES='\n'.join(commands), REGISTRY=helpers,
                 CACHE=function(core, 'cache_model_sprites'), CASES=',\n'.join(cases),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
                 COMMANDS=','.join(json.dumps(name) for name in data['commands']))
    code = Path(__file__).with_name('modern_mp_icon_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved MP icon contract input')
    return code


class ModernMPIconContracts(unittest.TestCase):
    def test_defaults_command_admission_cache_order_and_hud_thresholds(self):
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
