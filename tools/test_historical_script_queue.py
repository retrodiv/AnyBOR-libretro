"""Check queue script availability, arguments and signed limit constants.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_input_constants import program as constant_program
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-queue-script-contracts.json'


def queue_program(data):
    engine = ROOT / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    callbacks = ('openbor_drawspriteq', 'openbor_clearspriteq')
    availability = function(source, 'obor_script_function_available')
    symbols = set(re.findall(r'\(void\*\)\s*(\w+)', availability))
    if not set(callbacks) <= symbols or not 2 <= len(symbols) <= 512:
        raise ValueError('Bounded native queue availability dependencies required')
    parts = dict(FUNCTIONS='\n'.join(function(source, name) for name in callbacks),
        VARIANT=function(variant, 'ScriptVariant_IntegerValue'),
        AVAILABILITY=availability,
        STUBS='\n'.join('static void '+name+'(void){}' for name in sorted(symbols-set(callbacks))),
        CONTEXTS=','.join('{%du,%d}' % (r['revision'], r['available']) for r in data['sources']),
        CASES=',\n'.join('{%s}' % ','.join(str(r[k]) for k in data['queue_parameters'])
                           for r in data['queue_cases']))
    text = Path(__file__).with_name('script_queue_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native queue dependency')
    return text


class ScriptQueueContracts(unittest.TestCase):
    def fixture(self):
        data = load_contract_fixture(FIXTURE)
        self.assertEqual({r['revision'] for r in data['sources']},
                         contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len({r['revision'] for r in data['sources']}), len(data['sources']))
        return data

    def test_signed_constants_direct_and_precompiled(self):
        data = self.fixture()
        actual = [json.loads(line) for line in native_output(constant_program(data), data).splitlines()]
        expected = [dict(revision=r['revision'], case=i, **value) for r in data['sources']
                    for i, value in enumerate(data['contracts'][r['contract']])]
        self.assertEqual(actual, expected)

    def test_queue_availability_targets_defaults_and_arguments(self):
        data = self.fixture()
        actual = [json.loads(line) for line in native_output(queue_program(data), data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], available=r['available'],
            cases=len(data['queue_cases']) if r['available'] else 0) for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
