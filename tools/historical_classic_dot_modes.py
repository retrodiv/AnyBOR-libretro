"""Render native periodic-damage ticks with literal per-source expectations.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import re

from test_historical_player import function, rename_identifiers


def dot_program(root, data):
    source = (root / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    tick = function(source, 'common_dot')
    if re.search(r'(?:\.|->)\s*time\b|\bfixture_clock\b', tick):
        raise ValueError('Native tick clock must have an unambiguous probe namespace')
    globals_ = []
    for declaration in ('const s_attack emptyattack', 's_axis_f default_model_dropv'):
        match = re.search(r'(?ms)^' + re.escape(declaration) + r'\s*=.*?^\};', source)
        if match is None:
            raise ValueError('Complete native attack and velocity defaults required')
        globals_.append(match[0])
    cases = []
    for row in data['cases']:
        cases.append('{%s}' % ','.join(str(row[key]) for key in data['case_fields']))
    contexts = []
    for row in data['sources']:
        results = data['results'][row['contract']]
        if len(results) != len(cases):
            raise ValueError('Every periodic-damage case needs a source result')
        contexts.append('{%du,{%s}}' % (row['revision'], ','.join('{%s}' %
            ','.join(str(result[key]) for key in data['result_fields']) for result in results)))
    values = dict(GLOBALS='\n'.join(globals_),
        HELPERS='\n'.join(function(source, name) for name in
            ('obor_profile_dot_hits_hp', 'obor_profile_dot_hits_mp')),
        TICK=rename_identifiers(tick, {'time': 'fixture_clock'}),
        CASES=',\n'.join(cases), CONTEXTS=',\n'.join(contexts), CASE_COUNT=str(len(cases)))
    text = Path(__file__).with_name('classic_dot_modes_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native periodic-damage input')
    return text
