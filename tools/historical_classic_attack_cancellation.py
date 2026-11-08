"""Render the complete native attack caller with controlled contact decisions.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import re

from test_historical_player import function, rename_identifiers


def cancellation_program(root, data):
    source = (root / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    caller = function(source, 'do_attack')
    if caller.count('execute_ondoattack_script(') != 2:
        raise ValueError('Complete attacker/defender callback sequence required')
    if re.search(r'\bfixture_clock\b', caller):
        raise ValueError('Probe clock must not collide with a native identifier')
    clocked = rename_identifiers(caller, {'time': 'fixture_clock'})
    # The native rush record also has a member named time. Members keep their
    # original name; only the engine's global clock needs a probe namespace.
    clocked = re.sub(r'((?:\.|->)\s*)fixture_clock\b', r'\1time', clocked)
    cases = []
    for case in data['cases']:
        decisions = case['decisions']
        if (not isinstance(decisions, list) or not 1 <= len(decisions) <= 2 or
                any(not isinstance(pair, list) or len(pair) != 2 or
                    any(type(value) is not int or value not in (-1, 0, 1) for value in pair)
                    for pair in decisions)):
            raise ValueError('One or two bounded contacts with explicit callback decisions required')
        cases.append('{%d,{{%s}}}' % (len(decisions),
            '},{'.join(','.join(map(str, pair)) for pair in decisions)))
    rows = []
    for row in data['sources']:
        expected = []
        for result in data['results'][row['contract']]:
            expected.append('{%d,{%s},%d,%d,%d,%d,%d,{%s},%d}' % (
                result['context'], ','.join(map(str, result['hit_ids'])),
                result['hits'], result['rush'], result['summary'], result['last_hit'],
                result['combo'], ','.join(map(str, result['trace'])), len(result['trace'])))
        if len(expected) != len(cases):
            raise ValueError('Each native contact case needs an independent result')
        rows.append('{%du,%d,{%s}}' % (row['revision'], row['normal_type'], ','.join(expected)))
    text = Path(__file__).with_name('classic_attack_cancellation_contract.c.in').read_text()
    values = dict(CALLER=clocked,
                  CASES=',\n'.join(cases), CONTEXTS=',\n'.join(rows), CASE_COUNT=str(len(cases)))
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native cancellation input')
    return text
