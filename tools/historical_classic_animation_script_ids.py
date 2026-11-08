"""Render native script animation-ID boundaries and their internal-ID controls.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import re

from test_historical_player import function, rename_identifiers, switch_cases


def script_id_program(root, data):
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    core = (engine / 'openbor.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    first = source.index('enum _axis_enum')
    declarations = source[first:source.index('HRESULT openbor_getanimationproperty(', first)]
    get_names = ('animation', 'animnum', 'animationid', 'animvalid', 'attack',
                 'vulnerable', 'bbox', 'dropframe', 'energycost', 'landframe',
                 'range', 'spritea', 'nextanim')
    set_names = ('animation', 'energycost', 'spritea', 'nextanim')
    callbacks = []
    unused = set()
    for name, selected in (('openbor_getentityproperty', get_names),
                           ('openbor_changeentityproperty', set_names)):
        body, cases = switch_cases(source, name, 'propind', outermost=True)
        prefix = body[:body.index('switch(propind)')]
        # These unselected address lists are not exercised by an ID query.
        # Refuse unexpected execution instead of linking unrelated engine AI.
        scanned = re.sub(r'//[^\n]*|/\*.*?\*/', '', prefix, flags=re.S)
        for table in re.findall(r'static const void \*\w+\[\][^=]*=\s*\{([^}]+)\}', scanned):
            unused.update(re.findall(r'\b\w+\b', re.sub(r'//[^\n]*', '', table)))
        prefix = rename_identifiers(prefix, {n: 'unselected_' + n for n in unused})
        tail = '\nreturn S_OK;\n'
        if name == 'openbor_changeentityproperty':
            tail += 'changeentityproperty_error:\nreturn E_FAIL;\n'
        callbacks.append(prefix + 'switch(propind){\n' + ''.join(
            'case _ep_' + n + ':' + cases['_ep_' + n]['body'] for n in selected) +
            'default:' + cases['default']['body'] + '}\n' + tail + '}\n')
    lines = source.splitlines(keepends=True)
    first = next(i for i, line in enumerate(lines) if line.startswith('#define MAPSTRINGS('))
    last = first
    while lines[last].rstrip().endswith('\\'):
        last += 1
    macros = ''.join(line for line in lines if line.startswith('#define _is_not_')) + ''.join(lines[first:last+1])
    rows = []
    extra = data['script_id_controls']['extra_dynamic_ids']
    maximum = max(row['storage_count'] for row in data['sources']) + extra
    for row in data['sources']:
        slots = {}
        for name, value in row['values'].items():
            if name == 'MAX_ANIS' or not name.startswith('ANI_'):
                continue
            native = row['native_ids'][name]
            if value in slots and slots[value] != native:
                raise ValueError('Original aliases require the same native identity')
            slots[value] = native
        if set(slots) != set(range(row['public_count'])):
            raise ValueError('Every original static animation slot needs an identity')
        native = [slots[i] for i in range(row['public_count'])]
        native += [row['storage_count'] + i for i in range(extra)]
        rows.append('{%du,%d,%d,{%s}}' % (row['revision'], row['public_count'] + extra,
                    row['storage_count'] + extra, ','.join(map(str, native))))
    _, system = switch_cases(core, 'getsyspropertybyindex', 'index', outermost=True)
    values = dict(DECLARATIONS=declarations, MACROS=macros,
        STUBS='\n'.join('static void unselected_' + n + '(void){abort();}' for n in sorted(unused)),
        CALLBACKS='\n'.join(callbacks),
        FUNCTIONS='\n'.join(rename_identifiers(function(source, name), {'time': 'fixture_game_clock'})
            for name in ('openbor_findtarget', 'openbor_checkrange', 'openbor_performattack',
                         'openbor_setidle', 'openbor_bindentity')),
        CORE='\n'.join(function(core, name) for name in ('ent_set_anim', 'execute_animation_script')),
        SCRIPT_INIT=function(source, 'Script_IsInitialized'),
        MAXIMUM=system['_sv_maxanimations']['body'],
        VARIANTS='\n'.join(function(variants, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType',
             'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        SEARCH=function(utils, 'searchList'), CONTEXTS=',\n'.join(rows),
        SLOT_COUNT=str(maximum), CLOCK=str(data['script_id_controls']['clock']))
    text = Path(__file__).with_name('classic_animation_script_ids_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native script animation-ID control input')
    return text
