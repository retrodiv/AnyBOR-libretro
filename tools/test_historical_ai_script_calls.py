"""Check historical script AI arguments, results and ordered entity writes.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-ai-script-caller-contracts.json'
CALLBACKS = ('openbor_adjustwalkanimation', 'openbor_finditem', 'openbor_pickup',
             'openbor_aicheckjump', 'openbor_aicheckpathblocked',
             'openbor_testmove', 'openbor_setidle')


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    available = function(script, 'obor_script_function_available')
    symbols = set(re.findall(r'\(void\*\)\s*(\w+)', available))
    if not set(CALLBACKS[:5]) <= symbols:
        raise ValueError('Complete AI script availability predicates required')
    parts = dict(FUNCTIONS='\n'.join(function(script, n) for n in CALLBACKS),
        VARIANTS='\n'.join(function(variant, n) for n in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType',
             'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        AVAILABILITY=available,
        STUBS='\n'.join('HRESULT '+n+'(ScriptVariant **a, ScriptVariant **b, int c)'
                        '{(void)a;(void)b;(void)c;abort();}'
                        for n in sorted(symbols-set(CALLBACKS))),
        CALLBACKS=','.join(CALLBACKS),
        CONTEXTS=','.join('{%du,{%s},%d,%d,%d}' % (r['revision'],
            ','.join(str(v) for v in r['available']), r['target_second'],
            r['find_returns'], r['idle_destination']) for r in data['sources']))
    text = Path(__file__).with_name('ai_script_callers_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved AI script caller dependency')
    return text


class AIScriptCalls(unittest.TestCase):
    def test_native_argument_routing_return_values_and_write_order(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in data['sources']}
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(revisions), len(data['sources']))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        expected = []
        for r in data['sources']:
            counts = (25, 18, 45, 6, 6, 36, 50)
            expected.append(dict(revision=r['revision'], cases=sum(
                n for n, active in zip(counts, r['available']) if active), availability=6))
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
