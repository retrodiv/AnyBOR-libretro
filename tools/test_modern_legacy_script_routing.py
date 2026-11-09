"""Check runtime entity-property names and legacy projectile flag targets.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-legacy-script-routing-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    core = (engine / 'openbor.c').read_text()
    enums = re.findall(r'(?ms)^enum[ \t]+\w+[ \t]*(?://[^\n]*)?\s*\{[^}]*^};', source)
    names = [re.search(r'static const char\s*\*\s*' + name + r'\[\]\s*=\s*\{[^}]+\};', source, re.S)
             for name in ('eplist', 'eplist_aiflag', 'eplist_edgerange')]
    default = re.search(r'(?ms)^const s_projectile projectile_default_config\s*=\s*\{.*?^};', core)
    if any(match is None for match in names) or default is None or not enums:
        raise ValueError('Complete native legacy names/enums/default required')
    body, cases = switch_cases(source, 'openbor_getentityproperty', 'propind', outermost=True)
    getter = (body[:body.index('switch(propind)')] + 'switch(propind){' + ''.join(
        'case ' + key + ':' + cases[key]['body'] for key in ('_ep_a', '_ep_y', '_ep_health')) +
        'default:' + cases['default']['body'] + '}\nreturn S_OK;\n}\n')
    parts = dict(ENUMS='\n'.join(enums), NAMES='\n'.join(match[0] for match in names), DEFAULT=default[0], GETTER=getter,
        VARIANTS='\n'.join(function(variant, n) for n in ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
            'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
        MAPPER=function(source, 'mapstrings_entityproperty'), PROJECTILE=function(source, 'openbor_projectile'),
        PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
        CASES=','.join('{' + ','.join(str(n) for n in row) + '}' for row in data['projectile_cases']))
    code = Path(__file__).with_name('modern_legacy_script_routing_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved legacy routing input')
    return code


class ModernLegacyScriptRoutingContracts(unittest.TestCase):
    def test_runtime_names_and_projectile_prime_recipient(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({row['revision'] for row in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', flags=[1,16,2,8,4], profiles=[
            dict(revision=row['revision'], **data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
