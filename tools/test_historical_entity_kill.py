"""Observe native retirement callbacks around the historical live-entity guard.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-entity-kill-contracts.json'


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    revisions = [row['revision'] for row in data['sources']]
    if (data['engine'] != '4432' or len(set(revisions)) != len(revisions) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions)):
        raise ValueError('Own retirement sources and boundary controls required')
    for row in data['sources']:
        if (row['engine'] != data['engine'] or row['callback_before_guard'] not in (0, 1) or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not all(re.fullmatch('[0-9a-f]{64}', value) for value in row['source_sha256'].values())):
            raise ValueError('Complete original retirement observations required')
    return data


def expected(context, case):
    callback = int(not case['null'] and not case['missing_scripts'] and
                   (context['callback_before_guard'] or case['active']))
    executed = callback * case['initialized']
    exists = case['mutation'] if executed and case['mutation'] >= 0 else case['active']
    teardown = int(not case['null'] and (exists if context['callback_before_guard'] else case['active']))
    kept = 1 - teardown
    return ([callback, executed, teardown, executed * 2,
             0 if teardown else exists, 0 if teardown else 29, 10 - teardown] +
            [kept] * 13 + [teardown, kept, teardown] + [kept] * 5 + [1, 1])


def program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    text = Path(__file__).with_name('entity_kill_contract.c.in').read_text()
    values = dict(FUNCTIONS='\n'.join(function(source, name) for name in
                  ('execute_onkill_script', 'ent_unlink', 'kill')),
                  CONTEXTS=','.join(str(row['revision']) for row in data['sources']),
                  CASES=','.join('{%d,%d,%d,%d,%d,%d}' %
                      (c['active'], c['initialized'], c['mutation'], c['player'], c['null'], c['missing_scripts'])
                      for c in data['cases']))
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native retirement dependency')
    return text


class EntityKillContracts(unittest.TestCase):
    def test_callback_state_and_guard_continuation(self):
        data = fixture_data()
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(len(actual), len(data['sources']) * len(data['cases']))
        for result, (context, case) in zip(actual, ((r, c) for r in data['sources'] for c in data['cases'])):
            with self.subTest(revision=context['revision'], case=case):
                self.assertEqual(result['revision'], context['revision'])
                self.assertEqual(result['values'], expected(context, case))


if __name__ == '__main__':
    unittest.main()
