"""Render native vault routines, callers, model name and action namespaces.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re

from test_historical_player import function, rename_identifiers, switch_cases


def vault_program(root, data):
    engine = root / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    first = source.index('enum _axis_enum')
    declarations = source[first:source.index('HRESULT openbor_getanimationproperty(', first)]
    callbacks = []
    symbols = set()
    for name in ('openbor_changeentityproperty',):
        body, cases = switch_cases(source, name, 'propind', outermost=True)
        prefix = body[:body.index('switch(propind)')]
        plain = re.sub(r'//[^\n]*|/\*.*?\*/', '', prefix, flags=re.S)
        for table in re.findall(r'static const void\s*\*\s*\w+\[\]\s*=\s*\{([^}]+)\}', plain):
            symbols.update(re.findall(r'\b\w+\b', table))
        tail = '\nreturn S_OK;\n'
        if name == 'openbor_changeentityproperty':
            tail += 'changeentityproperty_error:return E_FAIL;\n'
        callbacks.append(prefix + 'switch(propind){case _ep_takeaction:' +
                         cases['_ep_takeaction']['body'] + 'default:' + cases['default']['body'] +
                         '}\n' + tail + '}\n')
    stubs = '\n'.join('void %s(void){action_identity=%d;}' % (name, i+1)
                      for i, name in enumerate(sorted(symbols - {'common_vault'})))
    lines = source.splitlines(keepends=True)
    first = next(i for i, line in enumerate(lines) if line.startswith('#define MAPSTRINGS('))
    last = first
    while lines[last].rstrip().endswith('\\'):
        last += 1
    macros = ''.join(line for line in lines if line.startswith('#define _is_not_')) + ''.join(lines[first:last+1])
    translator = function(core, 'translate_ani_id')
    arrays = sorted(set(re.findall(r'\b(anim\w+)\[', translator)))
    contexts = []
    for row in data['sources']:
        contexts.append('{%du,%d,%d,%d,%d,%d,{%s},{%s}}' % (
            row['revision'], row['functions_enabled'], row['model_command'],
            row['native_vault'], row['storage_count'], len(row['action_names']),
            ','.join(json.dumps(name) for name in row['action_names']),
            ','.join(row['action_functions'])))
    flags = lambda items: '|'.join('FLAG_' + name for name in items) or '0'
    available_names = sorted({name for row in data['player_cases'] for name in row['available']})
    masks = {name: 1 << i for i, name in enumerate(available_names)}
    player_cases = []
    for row in data['player_cases']:
        player_cases.append('{%s,%s,%d,%d,%d,%d,%d,%d,%d,%d,%s}' % (
            flags(row['keys']), flags(row['play']), sum(masks[n] for n in row['available']),
            row['legacy_action'], row['modern_action'], row['which'], row['special'],
            row['base_delta'], row['link'], row['guard'], flags(row['remaining'])))
    values = dict(DECLARATIONS=declarations, CALLBACKS='\n'.join(callbacks), MACROS=macros,
        STUBS=stubs, CONTEXTS=',\n'.join(contexts),
        FUNCTIONS='\n'.join(rename_identifiers(function(core, name), {'time': 'fixture_game_clock'})
            for name in ('ent_set_anim', 'obor_classic_vault_animation', 'adjust_base',
                         'dovault', 'common_vault', 'common_grab_check', 'player_grab_check')),
        TRANSLATOR=translator,
        ARRAYS='\n'.join('static int *' + name + ';' for name in arrays),
        GRAB_ATTACKS=re.search(r'(?m)^int\s+grab_attacks\[[^\]]+\]\[[^\]]+\]\s*=\s*\{.*?^\};', core, re.S)[0],
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
        SEARCH=function(utils, 'searchList'),
        ACTIONS='\n'.join('#define ACT_' + name.upper() + ' ' + str(value)
                          for name, value in data['actions'].items()),
        AI_CASES=',\n'.join('{%s}' % ','.join(str(row[name]) for name in
            ('random', 'expired', 'throw', 'grab', 'vault', 'throw_wait',
             'legacy_action', 'modern_action', 'which')) for row in data['ai_cases']),
        PLAYER_CASES=',\n'.join(player_cases),
        AVAILABILITY='\n'.join('if(mask & %du) put_animation(%s);' %
            (masks[name], 'candidate_slot' if name == 'vault' else 'ANI_' + name.upper())
            for name in available_names),
        HEIGHTS=','.join(map(str, data['animation_heights'])),
        FINISH_STATES=','.join(map(str, data['finish_from_vault'])),
        DIRECTIONS=','.join(map(str, data['directions'])), MODEL_HEIGHT=str(data['model_height']),
        SLOT_COUNT=str(max(row['storage_count'] for row in data['sources'])))
    text = Path(__file__).with_name('classic_vault_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native vault control input')
    return text
