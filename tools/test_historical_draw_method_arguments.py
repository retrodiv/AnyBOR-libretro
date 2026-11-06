"""Check positional drawmethod arguments, retained centers and diagnostics.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-draw-method-argument-contracts.json'


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    core = (engine / 'openbor.c').read_text()
    start = core.index('const s_drawmethod plainmethod = {')
    helper = Path(__file__).with_name('draw_repeat_script_contract.c.in').read_text()
    parts = dict(PLAIN=core[start:core.index('\n};', start)+3],
        HELPERS='\n'.join(function(helper, name) for name in ('same_method', 'method_seed')),
        VARIANT=function(variant, 'ScriptVariant_IntegerValue'),
        FUNCTION=function(source, 'openbor_setdrawmethod'),
        CONTEXTS=','.join('{%du,%d,%s}' % (row['revision'], row['center_arguments'],
            json.dumps(data['diagnostics'][row['diagnostic']])) for row in data['sources']),
        CASES=',\n'.join('{%s}' % ','.join(str(row[k]) for k in data['parameters'])
                           for row in data['cases']))
    text = Path(__file__).with_name('draw_method_argument_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native positional drawmethod dependency')
    return text


class DrawMethodArgumentContracts(unittest.TestCase):
    def test_native_arity_targets_values_centers_and_errors(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({r['revision'] for r in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len({r['revision'] for r in data['sources']}), len(data['sources']))
        rows = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(rows, [dict(revision=r['revision'], cases=len(data['cases']))
                                for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
