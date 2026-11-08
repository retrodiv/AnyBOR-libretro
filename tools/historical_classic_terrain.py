"""Render native historical terrain mapping, callbacks and table growth controls.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re

from test_historical_player import function, switch_cases


def terrain_program(root, data):
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    first = source.index('enum levelproperty_enum')
    declarations = source[first:source.index('HRESULT openbor_getlevelproperty(', first)]
    callbacks = []
    # The shared extractor accepts a named selector. Restore the exact native
    # expression after using the temporary name solely to split its cases.
    parsed = source.replace('switch(varlist[0]->lVal)', 'switch(terrain_selector)')
    for name in ('openbor_getlevelproperty', 'openbor_changelevelproperty'):
        body, cases = switch_cases(parsed, name, 'terrain_selector', outermost=True)
        prefix = body[:body.index('switch(terrain_selector)')]
        if name == 'openbor_changelevelproperty':
            prefix += '(void)arg; /* Used by the other, unselected level cases. */\n'
        selected = ''.join('case '+key+':'+cases[key]['body'] for key in ('_lp_hole', '_lp_wall'))
        selected += 'default:'+cases['default']['body']
        suffix = body[body.rfind('    return S_OK;'):]
        callbacks.append((prefix+'switch(terrain_selector){'+selected+'}\n'+suffix)
                         .replace('switch(terrain_selector)', 'switch(varlist[0]->lVal)'))
    lines = source.splitlines(keepends=True)
    first = next(i for i, line in enumerate(lines) if line.startswith('#define MAPSTRINGS('))
    last = first
    while lines[last].rstrip().endswith('\\'):
        last += 1
    macros = ''.join(line for line in lines if line.startswith('#define _is_not_')) + ''.join(lines[first:last + 1])
    values = dict(DECLARATIONS=declarations, CALLBACKS='\n'.join(callbacks), MACROS=macros,
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType',
             'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue', 'ScriptVariant_ToString')),
        SEARCH=function(utils, 'searchList'),
        CONTEXTS=','.join('{%du,{%d,%d}}' % (row['revision'], row['old_hole'], row['old_wall'])
                          for row in data['sources']))
    text = Path(__file__).with_name('classic_terrain_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native terrain input')
    return text
