"""Check source-specific drawing method selection in script callbacks.

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


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-drawing-primitive-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    source = (engine / 'openborscript.c').read_text()
    core = (engine / 'openbor.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    start = re.search(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{', core)
    if start is None:
        raise ValueError('Source-owned default method required')
    parts = dict(
        DEFAULT=core[start.start():core.index('\n};', start.end()) + 3],
        VARIANT=function(variants, 'ScriptVariant_IntegerValue'),
        CALLBACKS='\n'.join(function(source, name) for name in data['callbacks']),
        ENTRIES=','.join(data['callbacks']),
        PROFILES=','.join(str(s['revision']) + 'u' for s in data['sources']),
        FLAGS=','.join(str(v) for v in data['flags']),
        MASKS=','.join(str(v) + 'u' for v in data['masks']),
        ALPHAS=','.join(str(v) for v in data['alphas']))
    code = Path(__file__).with_name('modern_drawing_primitive_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved drawing callback contract input')
    return code


class ModernDrawingPrimitiveContracts(unittest.TestCase):
    def test_queued_direct_and_screen_method_selection(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [s['revision'] for s in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=s['revision'], cases=data['contracts'][s['contract']])
                                               for s in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
