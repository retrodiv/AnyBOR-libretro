"""Check native debug-menu input against original-source observations.

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

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-debug-menu-input-contracts.json'
CONTRACTS = ('enum', 'integer', 'explicit')
FIELDS = ('updates', 'second_selection', 'saves', 'sounds', 'performance')


def fixture_data():
    data = load_contract_fixture(FIXTURE)
    rows = data['sources']
    revisions = [r['revision'] for r in rows]
    if (data['engine'] != '4432' or len(set(revisions)) != len(rows) or
            set(revisions) != contract_revisions(data, data['expected_revisions']) or
            not set(data['boundary_controls']) <= set(revisions) or
            len(data['first_keys']) != 4 or
            any(type(k) is not int or not 0 <= k <= 0xffffffff for k in data['first_keys']) or
            set(data['contracts']) != set(CONTRACTS)):
        raise ValueError('Explicit own-source input contexts and boundary controls required')
    for row in rows:
        if (row['engine'] != data['engine'] or row['contract'] not in CONTRACTS or
                not re.fullmatch('[0-9a-f]{40}', row['commit']) or
                not re.fullmatch('[0-9a-f]{64}', row['source_sha256']['openbor.c'])):
            raise ValueError('Bound original menu source and independent observations required')
    for cases in data['contracts'].values():
        if (len(cases) != 4 or any(set(c) != set(FIELDS) or
                any(type(c[k]) is not int for k in FIELDS) for c in cases)):
            raise ValueError('One explicit result per input scenario required')
    return data


def program(data):
    engine = ROOT / 'src/engines' / data['engine']
    header = (engine / 'openbor.h').read_text()
    end = header.index('} e_key_def;') + len('} e_key_def;')
    start = header.rfind('typedef enum', 0, end)
    if start < 0:
        raise ValueError('Native input flag declaration missing')
    values = dict(FLAGS=header[start:end],
        FUNCTION=function((engine / 'openbor.c').read_text(), 'menu_options_debug'),
        KEYS=','.join(str(k) + 'u' for k in data['first_keys']),
        PROFILES=','.join('{%du,%du,%du}' % (r['revision'], CONTRACTS.index(r['contract']),
                         r['contract'] != 'explicit') for r in data['sources']),
        EXPECTED=','.join('{' + ','.join('{' + ','.join(str(c[k]) for k in FIELDS) + '}'
                         for c in data['contracts'][key]) + '}' for key in CONTRACTS))
    text = Path(__file__).with_name('debug_menu_input_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native menu dependency')
    return text


class DebugMenuInputContracts(unittest.TestCase):
    def test_native_selector_combinations_audio_and_interior_action(self):
        data = fixture_data()
        count = len(data['sources']) * 4 + sum(r['contract'] != 'explicit' for r in data['sources'])
        actual = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(actual, [dict(status='PASS', contexts=len(data['sources']), cases=count)])


if __name__ == '__main__':
    unittest.main()
