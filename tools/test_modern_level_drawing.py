"""Check layer transparency stores and native sprite/screen selection.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_early_jump_walkoff import continued_macro
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-level-drawing-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    source = (engine / 'openbor.c').read_text()
    _, cases = switch_cases(source, 'load_level', 'cmd', outermost=True)
    start = re.search(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{', source)
    if start is None:
        raise ValueError('Source-owned drawing default required')
    commands = '\n'.join('case ' + name + ':' + cases[name]['body'] for name in data['commands'])
    parts = dict(
        DEFAULT=source[start.start():source.index('\n};', start.end()) + 3],
        HELPERS='\n'.join(function(source, n) for n in ('isNumeric', 'getValidInt', 'getValidFloat')),
        LOAD=function(source, 'load_layer'), COMMANDS=commands,
        NAN_MACRO=continued_macro(source, 'NaN'),
        PROFILES=','.join(str(s['revision']) + 'u' for s in data['sources']),
        INPUTS=','.join('{%s,%s,%d,{%s}}' % (row['command'], json.dumps(row['mask']), len(row['args']) + 1,
                         ','.join(json.dumps(s) for s in ['layer'] + row['args'])) for row in data['cases']))
    code = Path(__file__).with_name('modern_level_drawing_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved level drawing contract input')
    return code


class ModernLevelDrawingContracts(unittest.TestCase):
    def test_transparency_storage_and_layer_image_route(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [s['revision'] for s in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=s['revision'], cases=data['contracts'][s['contract']])
                                               for s in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
