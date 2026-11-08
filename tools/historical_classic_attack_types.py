"""Render selected-source attack constants and model defense/offense controls.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import re

from test_historical_player import function


def model_program(root, data):
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openbor.c').read_text()
    load = function(source, 'load_cached_model')
    start = load.index('case CMD_MODEL_DEFENSE:')
    stop = load.index('case CMD_MODEL_HEIGHT:', start)
    directive = load[start:stop]
    if directive.count('#define tempdef(') != 1 or directive.count('#define tempoff(') != 1:
        raise ValueError('Complete native defense and offense directives required')
    names = data['symbols']
    fields = dict(
        HELPERS='\n'.join(function(source, name) for name in
            ('obor_profile_default_defense', 'isNumeric', 'getValidInt', 'getValidFloat')),
        DEFAULT=re.search(r'const s_defense default_defense\s*=\s*\{[^}]*\};', source)[0],
        DIRECTIVES=directive,
        SYMBOLS=','.join(names),
        SYMBOL_COUNT=str(len(names)),
        COMMANDS=','.join('"' + name + '"' for name in data['commands']),
        COMMAND_COUNT=str(len(data['commands'])),
        CONTEXTS=',\n'.join('{%du,{%s},{%s}}' % (row['revision'],
            ','.join(str(row['values'][name]) for name in names),
            ','.join(str(row['model_slots'][name]) for name in data['commands']))
            for row in data['sources']))
    text = Path(__file__).with_name('classic_attack_types_contract.c.in').read_text()
    for key, value in fields.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native attack-type input')
    return text


def response_program(root, data):
    source = (root / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    arrays = []
    for row in data['response_families']:
        match = re.search(r'(?m)^int\s+' + row['array'] + r'\[[^\]]+\]\s*=\s*\{[^}]*\}', source)
        if match is None:
            raise ValueError('Complete native attack response initializer required')
        arrays.extend((match[0] + ';', 'int *' + row['pointer'] + '=' + row['array'] + ';'))
    start = source.index('#define painflags(')
    painflags = source[start:source.index('int set_blockpain(', start)]
    values = dict(ARRAYS='\n'.join(arrays), PAINFLAGS=painflags,
        FUNCTIONS='\n'.join(function(source, row['function']) for row in data['response_families']),
        CONTEXTS=',\n'.join('{%du,{{%s}}}' % (row['revision'],
            '},{'.join(','.join(map(str, row['responses'][f['array']])) for f in data['response_families']))
            for row in data['sources']),
        POINTERS=','.join(row['array'] for row in data['response_families']))
    text = Path(__file__).with_name('classic_attack_responses_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native attack response input')
    return text
