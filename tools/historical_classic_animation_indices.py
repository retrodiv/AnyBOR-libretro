"""Render native animation constants and indexed model-vector controls.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re

from test_historical_player import function


def animation_index_program(root, data):
    engine = root / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    commands = (engine / 'source/gamelib/commands.h').read_text()
    # Annotate the original parser's intentional fallthrough for host -Werror;
    # retain its statements, expressions and control flow.
    parser = function(core, 'ParseArgs').replace('done = 1;', 'done = 1; /* fall through */')
    families = data['families']
    settings = list(dict.fromkeys(row['command'] for row in families))
    arrays = []
    for row in families:
        name = row['array']
        arrays.append(re.search(r'(?m)^int\s+' + name +
            r'\[[^\]]+\]\s*=\s*\{[^}]*\}', core)[0] + ';')
        arrays.append('static int *' + row['pointer'] + ';')
    start = script.index('#define IICMPCONST(')
    macros = script[start:script.index('static int obor_classic_constant(', start)]
    rows = []
    for row in data['sources']:
        values = ','.join(str(row['values'].get(name, -1)) for name in data['names'])
        native_ids = ','.join(str(row['native_ids'].get(name, -1)) for name in data['names'])
        vectors = ','.join('{' + ','.join(map(str, row['arrays'][f['pointer']])) + '}'
                           for f in families)
        dynamic = ','.join(str(int(row['dynamic_constants'][f['pointer']])) for f in families)
        rows.append('{%du,%d,%d,{%s},{%s},{%s},{%s}}' %
                    (row['revision'], row['public_count'], row['storage_count'], values, native_ids, vectors, dynamic))
    limits = list(dict.fromkeys(row['limit'] for row in families))
    fields = dict(ENUM=re.search(r'typedef enum\s*\{[^}]+\}\s*modelstxtCommands;', commands)[0],
        ARRAYS='\n'.join(arrays), LIMITS='static int ' + ','.join(limits + ['max_animations']) + ';',
        FUNCTIONS=parser + '\n' + '\n'.join(function(core, name) for name in
            ('isNumeric', 'getValidInt', 'load_model_constants')),
        LINES=function(utils, 'getNewLineStart'), MACROS=macros,
        MAPPER=function(script, 'obor_classic_constant') + '\n' + function(script, 'mapstrings_transconst'),
        ENTRY=function(script, 'openbor_transconst'),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType',
             'ScriptVariant_Copy', 'ScriptVariant_ToString')),
        GLOBALS='\n'.join('int %s;' % name for name in re.findall(
            r'(?m)^extern int\s+([A-Z_][A-Z_0-9]*)\s*;', script)),
        CONTEXTS=',\n'.join(rows), NAMES=','.join(json.dumps(name) for name in data['names']),
        NAME_COUNT=str(len(data['names'])), FAMILY_COUNT=str(len(families)), SETTING_COUNT=str(len(settings)),
        DEFAULTS=','.join(f['default'] for f in families),
        SETTINGS=','.join(json.dumps(name) for name in settings),
        COMMANDS=','.join('CMD_MODELSTXT_' + name.upper() for name in settings),
        DEFAULT_SETTINGS=','.join(next(f['default'] for f in families if f['command'] == name)
                                  for name in settings),
        CONFIGURATIONS=','.join('{' + ','.join(str(c.get(name, 0)) for name in settings) + '}'
                               for c in data['configurations']),
        FAMILY_SETTINGS=','.join(str(settings.index(f['command'])) for f in families),
        POINTERS=','.join('&' + f['pointer'] for f in families),
        LENGTHS=';'.join('lengths[%d]=%s' % (i, f['limit']) for i, f in enumerate(families)) + ';',
        PREFIXES=','.join(json.dumps(f['prefix']) for f in families))
    text = Path(__file__).with_name('classic_animation_indices_contract.c.in').read_text()
    for key, value in fields.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native animation-index input')
    return text
