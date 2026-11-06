"""Check source-owned timer compensation during entity freezing.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import native_output

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-frozen-timer-contracts.json'


def program(data):
    fields = data['fields']
    if (not 1 <= len(fields) <= 32 or len(set(fields)) != len(fields) or
            not all(re.fullmatch(r'[A-Za-z_]\w*', name) for name in fields)):
        raise ValueError('Explicit bounded timer fields required')
    parts = dict(WIDTH=str(len(fields)),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']),
                 CASES=',\n'.join('{{%s},%d,%d}' % (
                     ','.join(str(value) + 'u' for value in case['timers']),
                     case['textbox'], case['smartbomber']) for case in data['cases']),
                 INIT='\n'.join('actor.%s = cases[c].timers[%d];' % (name, i)
                                for i, name in enumerate(fields)),
                 READ='\n'.join('printf("%s%%u", (unsigned)actor.%s);' %
                                (',' if i else '', name) for i, name in enumerate(fields)))
    text = Path(__file__).with_name('frozen_timers_contract.c.in').read_text()
    for name, value in parts.items():
        text = text.replace('@' + name + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native frozen-timer dependency')
    return text


class FrozenTimerContracts(unittest.TestCase):
    def test_native_header_macro_matches_each_source_profile(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        for case in data['cases']:
            self.assertEqual(len(case['timers']), len(data['fields']))
            self.assertTrue(all(type(value) is int and 0 <= value <= 0xffffffff
                                for value in case['timers']))
            self.assertIn(case['textbox'], (0, 1))
            self.assertIn(case['smartbomber'], (0, 1))
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        expected = [(row, i, values) for row in data['sources'] for i, values in
                    enumerate(data['contracts'][row['contract']])]
        self.assertEqual(len(actual), len(expected))
        for result, (row, i, values) in zip(actual, expected):
            with self.subTest(profile=row['revision'], case=data['cases'][i]['name']):
                self.assertEqual(result, dict(revision=row['revision'], case=i, timers=values))


if __name__ == '__main__':
    unittest.main()
