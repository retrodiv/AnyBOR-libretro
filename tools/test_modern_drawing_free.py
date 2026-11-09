"""Check historical free-drawmethod availability and valid ownership.

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
from test_historical_player import function, rename_identifiers


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-drawing-free-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    index = (engine / 'source/openborscript/index.c').read_text()
    core = (engine / 'openbor.c').read_text()
    draw = (engine / 'source/openborscript/drawmethod.c').read_text()
    names = function(index, 'Script_GetFunctionName')
    others = set(re.findall(r'\(\s*\(\s*void\s*\*\s*\)\s*(\w+)\s*\)', names)) - {'openbor_free_drawmethod'}
    providers = {n: 'fixture_other_' + str(i) for i, n in enumerate(sorted(others))}
    names = rename_identifiers(names, providers)
    selected = re.findall(r'if\(obor_profile_build < \d+\)\s*\{\s*List_InsertAfter\s*\(\s*&theFunctionList\s*,\s*\(void\s*\*\)\s*openbor_free_drawmethod\s*,\s*"free_drawmethod"\s*\)\s*;\s*\}',
                          function(index, 'Script_LoadSystemFunctions'))
    start = re.search(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{', core)
    if len(selected) != 1 or start is None:
        raise ValueError('Native conditional registration and default record required')
    parts = dict(
        DEFAULT=core[start.start():core.index('\n};', start.end()) + 3],
        FREE=rename_identifiers(function(draw, 'openbor_free_drawmethod'), {'free': 'fixture_free'}),
        PROVIDERS='\n'.join('static void %s(void) { marker=%d; }' % (name, i + 10)
                            for i, name in enumerate(providers.values())),
        GETNAME=names,
        REGISTER=rename_identifiers(selected[0], {'List_InsertAfter': 'fixture_register', 'theFunctionList': 'fixture_list'}),
        PROFILES=','.join(str(s['revision']) + 'u' for s in data['sources']))
    code = Path(__file__).with_name('modern_drawing_free_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved drawing free contract input')
    return code


class ModernDrawingFreeContracts(unittest.TestCase):
    def test_source_availability_default_ownership_and_release(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [s['revision'] for s in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=s['revision'], **data['contracts'][s['contract']])
                                               for s in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
