"""Check source-defined model drawing commands and frame method copies.

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


FIXTURE = Path(__file__).with_name('fixtures') / 'modern-drawing-loading-contracts.json'


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    core = (engine / 'openbor.c').read_text()
    loader = function(core, 'load_cached_model')
    _, cases = switch_cases(core, 'load_cached_model', 'cmd', outermost=True)
    match = re.search(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{', core)
    start = re.search(r'(?m)^\s*if\(obor_profile_build >= \d+ \? \(drawmethod\.config.*', loader)
    if match is None or start is None:
        raise ValueError('Source-owned default and frame method branch required')
    frame = loader[start.start():loader.index('add_frame_data.animation', start.end())].strip()
    fields, seeds = [], []
    for name, kind, value in data['fields']:
        if not re.fullmatch(r'[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*', name) or kind not in ('WORD', 'BYTE', 'FLOAT', 'POINTER'):
            raise ValueError('Bounded typed drawing member required')
        fields.append('{offsetof(s_drawmethod,%s),sizeof(((s_drawmethod*)0)->%s),%s}' %
                      (name, name, 'FIXTURE_' + kind))
        seeds.append('drawmethod.%s=%s;' % (name, '(unsigned char *)&token' if kind == 'POINTER' else value))
    parts = dict(
        DEFAULT=core[match.start():core.index('\n};', match.end()) + 3],
        HELPERS='\n'.join(function(core, n) for n in ('isNumeric', 'getValidInt', 'getValidFloat', 'parsecolor')),
        CASES='\n'.join('case ' + n + ':' + cases[n]['body'] for n in data['commands']),
        FRAME=frame, FIELDS=','.join(fields), SEED='\n'.join(seeds),
        PROFILES=','.join(str(s['revision']) + 'u' for s in data['sources']),
        INPUTS=','.join('{%s,%d,%d,{%s}}' % (row['command'], row['blend_locked'], len(row['args']) + 1,
                        ','.join(json.dumps(s) for s in ['drawmethod'] + row['args'])) for row in data['cases']))
    code = Path(__file__).with_name('modern_drawing_loading_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved model drawing loading contract input')
    return code


class ModernDrawingLoadingContracts(unittest.TestCase):
    def test_model_commands_and_frame_method_copy(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [s['revision'] for s in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=s['revision'], cases=data['contracts'][s['contract']])
                                               for s in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)


if __name__ == '__main__':
    unittest.main()
