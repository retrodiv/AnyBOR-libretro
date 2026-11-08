"""Render native slow-motion update ordering and script field access.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import re

from test_historical_player import function


def slowmotion_program(root, data):
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openbor.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    update = function(source, 'update')
    prefix = update[update.index('{') + 1:update.index('while(time < newtime)')]
    # The following game-step loop shares the enclosing pause arm. Close that
    # arm at the observation boundary without executing the game-step body.
    prefix += '\n}\n'
    initializer = re.search(r'(?m)^s_slow_motion\s+slowmotion\s*=\s*\{.*?\};', source, re.S)
    if initializer is None or prefix.count('execute_keyscripts();') != 1:
        raise ValueError('Native initialized slow-motion record and update prefix required')
    names = ('slowmotion', 'slowmotion_duration')
    def selected_cases(name):
        text = function(source, name)
        cases = []
        for key in names:
            start = text.index('case _sv_' + key + ':')
            end = text.index('\n    case ', start + 1)
            cases.append(text[start:end])
        return '\n'.join(cases)
    rendered_cases = []
    columns = data['columns']
    for row in data['cases']:
        values = [str(row[key]) for key in columns]
        for epoch in ('legacy', 'modern'):
            oracle = row['oracles'].get(epoch)
            if oracle is None:
                values.append('{0,0,0,0,0,{0,0,0,0}}')
            else:
                values.append('{1,%d,%d,%d,%d,{%s}}' %
                    (oracle['toggle'], oracle['duration'], oracle['counter'], oracle['newtime'],
                     ','.join(map(str, oracle['events'] + [0]*(4-len(oracle['events']))))))
        rendered_cases.append('{' + ','.join(values) + '}')
    fields = dict(INITIALIZER=initializer[0], PREFIX=prefix,
        GETTERS=selected_cases('getsyspropertybyindex'),
        SETTERS=selected_cases('changesyspropertybyindex'),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
        CONTEXTS=','.join('{%du,%d}' % (row['revision'], row['unsigned_storage'])
                          for row in data['sources']),
        CASES=',\n'.join(rendered_cases),
        INPUTS=','.join('{%s,%.17g,%d,%d}' %
            (row['type'], row['value'], row['converts'], row['integer'])
            for row in data['script_inputs']))
    text = Path(__file__).with_name('classic_slowmotion_contract.c.in').read_text()
    for key, value in fields.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native slow-motion control input')
    return text
