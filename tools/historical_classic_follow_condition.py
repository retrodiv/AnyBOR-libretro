"""Render native follow-up loading, signedness gates and dispatch.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import re

from test_historical_player import function


def follow_program(root, data):
    core = (root / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    load = function(core, 'load_cached_model')
    start = load.index('case CMD_MODEL_FOLLOWANIM:')
    directives = load[start:load.index('case CMD_MODEL_COUNTERFRAME:', start)]
    attack = function(core, 'do_attack')
    start = attack.index('//if #055')
    stop = attack.index('//end of if #055', start) + len('//end of if #055')
    defaults = []
    for field in ('animation', 'condition'):
        found = re.findall(r'(?m)^\s*(newanim->followup\.' + field + r'\s*=\s*[^;]+;)', load)
        if len(found) < 2:
            raise ValueError('Native follow default and parser assignment required')
        defaults.append(found[0])
    cases = []
    fields = ('condition', 'hostile', 'healthy', 'blocked', 'grab', 'follow',
              'counter_ready', 'valid_follow', 'attackone')
    expected = ('grab_calls', 'current_follow', 'animation_changes', 'attackone', 'animnum')
    for row in data['cases']:
        values = [str(row[key]) for key in fields]
        for group in ('signed', 'enum'):
            values.append('{%s}' % ','.join(str(row[group][key]) for key in expected))
        cases.append('{%s}' % ','.join(values))
    parts = dict(DIRECTIVES=directives, FOLLOW=attack[start:stop],
        DEFAULTS='\n'.join(defaults),
        HELPERS='\n'.join(function(core, name) for name in
            ('isNumeric', 'getValidInt', 'diff', 'inair')),
        MAX_FOLLOWS=str(data['max_follows']),
        CONTEXTS=',\n'.join('{%du,%d}' % (row['revision'], row['signed_condition'])
                             for row in data['sources']),
        CASES=',\n'.join(cases))
    text = Path(__file__).with_name('classic_follow_condition_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native follow-condition input')
    return text
