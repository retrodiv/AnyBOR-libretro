"""Check legacy drawing setters and getters across flag representations.

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


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-legacy-drawing-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    script = (engine / 'openborscript.c').read_text()
    core = (engine / 'openbor.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    declaration = re.search(r'(?ms)^enum(?: drawmethod_enum)?\s*\{\s*_dm_alpha,.*?^\};', script)
    start = re.search(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{', core)
    if declaration is None or start is None:
        raise ValueError('Native legacy enum and default drawing record required')
    parts = dict(
        DEFAULT=core[start.start():core.index('\n};', start.end()) + 3],
        ENUM=declaration[0],
        VARIANTS='\n'.join(function(variants, n) for n in ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
                                                       'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        API='\n'.join(function(script, n) for n in ('mapstrings_drawmethodproperty',
                      'openbor_changedrawmethod', 'openbor_getdrawmethod', 'openbor_setdrawmethod')),
        SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
        PROFILES=','.join(str(s['revision']) + 'u' for s in data['sources']),
        NAMES=','.join(json.dumps(n) for n in data['names']),
        VALUES=','.join('{%d,%s}' % (kind, value) for kind, value in data['values']),
        SEED=','.join(str(v) for v in data['seed']),
        POSITIONAL=','.join('{%d,{%s}}' % (row['count'], ','.join(str(v) for v in row['values']))
                            for row in data['positional']))
    code = Path(__file__).with_name('modern_legacy_drawing_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved legacy drawing contract input')
    return code


class ModernLegacyDrawingContracts(unittest.TestCase):
    def test_named_and_positional_flag_roundtrips(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [s['revision'] for s in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=s['revision'], **data['contracts'][s['contract']])
                                               for s in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
