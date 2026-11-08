"""Render native entity namespace, call-prefix and selected field controls.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re

from test_historical_player import function, rename_identifiers, switch_cases


def namespace_program(root, data):
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    first = source.index('enum _axis_enum')
    declarations = source[first:source.index('HRESULT openbor_getanimationproperty(', first)]
    dispatcher = function(source, 'Script_GetStringMapFunction')
    references = set(re.findall(r'\(void\s*\*\)\s*(\w+)', dispatcher))
    methods = {}
    actions = set()
    for key, name in (('GET', 'openbor_getentityproperty'), ('SET', 'openbor_changeentityproperty')):
        body, cases = switch_cases(source, name, 'propind', outermost=True)
        prefix = body[:body.index('switch(propind)')]
        pointer_lists = re.sub(r'//[^\n]*|/\*.*?\*/', '', prefix, flags=re.S)
        for array in re.findall(r'static const void\s*\*\s*\w+\[\]\s*=\s*\{(.*?)\};', pointer_lists, re.S):
            array = re.sub(r'//[^\n]*|/\*.*?\*/', '', array, flags=re.S)
            actions.update(re.findall(r'\b[A-Za-z_]\w*\b', array))
        selected = ''.join('case ' + label + ':' + cases[label]['body'] for label in
            ('_ep_a', '_ep_y', '_ep_health', '_ep_x', '_ep_z', '_ep_zdir') if label in cases)
        selected += 'default:' + cases['default']['body']
        suffix = '\nreturn S_OK;\n'
        if key == 'SET':
            suffix += 'changeentityproperty_error:return E_FAIL;\n'
        methods[key + '_ENTRY'] = prefix + 'last_property=propind;\n' + suffix + '}\n'
        methods[key + '_FIELDS'] = prefix + 'last_property=propind;\nswitch(propind){\n' + selected + '}\n' + suffix + '}\n'
    owned = set(re.findall(r'(?m)^(?:static\s+)?(?:int|void)\s+(mapstrings_\w+)\s*\(', declarations))
    query_names = {'openbor_getentityproperty', 'openbor_changeentityproperty'}
    stub_names = sorted((references - owned - query_names) | actions)
    replacements = {name: 'probe_symbol_' + name for name in stub_names}
    replacements.update(openbor_getentityproperty='probe_get_entry',
                        openbor_changeentityproperty='probe_set_entry')
    prefixes = []
    for key, text in methods.items():
        names = dict(replacements)
        old = 'openbor_getentityproperty' if key.startswith('GET') else 'openbor_changeentityproperty'
        names[old] = 'probe_' + key.lower()
        prefixes.append(rename_identifiers(text, names))
    lines = source.splitlines(keepends=True)
    first = next(i for i, line in enumerate(lines) if line.startswith('#define MAPSTRINGS('))
    last = first
    while lines[last].rstrip().endswith('\\'):
        last += 1
    macros = ''.join(line for line in lines if line.startswith('#define _is_not_')) + ''.join(lines[first:last + 1])
    rows = []
    for row in data['sources']:
        queries = ','.join('{%d,%d,%d}' % (row['properties'].index(q['name']), q['getter'], q['setter'])
                           for q in row['queries'])
        rows.append('{%du,%d,{%s},{%s},%s,%s,%d,{%s}}' % (row['revision'], len(row['properties']),
            ','.join(json.dumps(n) for n in row['properties']), ','.join(map(str, row['native_ids'])),
            json.dumps(row['mapper_warning']), json.dumps(row['callback_warning']), len(row['queries']), queries))
    values = dict(DECLARATIONS=declarations, PREFIXES='\n'.join(prefixes),
        DISPATCH=rename_identifiers(dispatcher, replacements),
        STUBS='\n'.join('static void probe_symbol_%s(void){++stub_calls[%d];}' % (name, i)
                         for i, name in enumerate(stub_names)),
        STUB_COUNT=str(len(stub_names)), MACROS=macros, CONTEXTS=','.join(rows),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        SEARCH=function(utils, 'searchList'))
    text = Path(__file__).with_name('classic_entity_namespace_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native entity namespace input')
    return text


def dropv_program(root, data):
    """Keep the complete mapper and attack-query case in the native call route."""
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    first = source.index('enum _axis_enum')
    declarations = source[first:source.index('HRESULT openbor_getanimationproperty(', first)]
    body, cases = switch_cases(source, 'openbor_getentityproperty', 'propind', outermost=True)
    getter = (body[:body.index('switch(propind)')] + 'switch(propind){case _ep_attack:' +
              cases['_ep_attack']['body'] + 'default:' + cases['default']['body'] +
              '}\nreturn S_OK;\n}\n')
    lines = source.splitlines(keepends=True)
    first = next(i for i, line in enumerate(lines) if line.startswith('#define MAPSTRINGS('))
    last = first
    while lines[last].rstrip().endswith('\\'):
        last += 1
    macros = ''.join(line for line in lines if line.startswith('#define _is_not_')) + ''.join(lines[first:last + 1])
    rows = ','.join('{%du,%d,%d,%d}' % (row['revision'], row['attack_property'],
                    row['dropv_property'], row['axis_names']) for row in data['sources'])
    values = dict(DECLARATIONS=declarations, GETTER=getter, MACROS=macros, CONTEXTS=rows,
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        SEARCH=function(utils, 'searchList'))
    text = Path(__file__).with_name('classic_dropv_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native dropv input')
    return text


def removed_constants_program(root, data):
    """Exercise native constant mapping/copy/diagnostics with physical variants."""
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    mapper = function(source, 'mapstrings_transconst')
    start = source.index('#define IICMPCONST(')
    macros = source[start:source.index('static int obor_classic_constant(', start)]
    arrays = sorted(set(re.findall(r'ICMPSCONST[AB]\(\s*\w+,\s*(\w+)\)', mapper)))
    names = list(data['sources'][0]['constants'])
    values = dict(MACROS=macros,
        MAPPER=function(source, 'obor_classic_constant') + '\n' + mapper,
        ENTRY=function(source, 'openbor_transconst'),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType',
             'ScriptVariant_Copy', 'ScriptVariant_ToString')),
        ARRAYS='\n'.join('static int %s[1];' % name for name in arrays),
        GLOBALS='\n'.join('int %s;' % name for name in re.findall(
            r'(?m)^extern int\s+([A-Z_][A-Z_0-9]*)\s*;', source)),
        NAMES=','.join(json.dumps(name) for name in names),
        CONTEXTS=','.join('{%du,{%s}}' % (row['revision'], ','.join(
            str(row['constants'][name] if row['constants'][name] is not None else -1)
            for name in names)) for row in data['sources']))
    text = Path(__file__).with_name('classic_removed_constants_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native removed-constant input')
    return text


def animation_height_program(root, data):
    """Run the original parser directives and selected native entity getter."""
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    core = (engine / 'openbor.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    first = source.index('enum _axis_enum')
    declarations = source[first:source.index('HRESULT openbor_getanimationproperty(', first)]
    body, cases = switch_cases(source, 'openbor_getentityproperty', 'propind', outermost=True)
    getter = (body[:body.index('switch(propind)')] + 'switch(propind){case _ep_animheight:' +
              cases['_ep_animheight']['body'] + 'default:' + cases['default']['body'] +
              '}\nreturn S_OK;\n}\n')
    _, loading = switch_cases(core, 'load_cached_model', 'cmd', outermost=True)
    lines = source.splitlines(keepends=True)
    first = next(i for i, line in enumerate(lines) if line.startswith('#define MAPSTRINGS('))
    last = first
    while lines[last].rstrip().endswith('\\'):
        last += 1
    macros = ''.join(line for line in lines if line.startswith('#define _is_not_')) + ''.join(lines[first:last + 1])
    values = dict(DECLARATIONS=declarations, GETTER=getter, MACROS=macros,
        DIRECTIVES=''.join('case '+key+':'+loading[key]['body'] for key in
                           ('CMD_MODEL_HEIGHT', 'CMD_MODEL_ANIMHEIGHT')),
        NUMBERS='\n'.join(function(core, name) for name in ('isNumeric', 'getValidInt')),
        VARIANTS='\n'.join(function(variant, name) for name in ('ScriptVariant_Clear', 'ScriptVariant_ChangeType')),
        SEARCH=function(utils, 'searchList'),
        CONTEXTS=','.join('{%du,%d,%d}' % (row['revision'], row['property'], row['read_loaded_height'])
                          for row in data['sources']),
        HEIGHTS=','.join(map(str, data['heights'])), WIDTHS=','.join(map(str, data['widths'])))
    text = Path(__file__).with_name('classic_animation_height_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native animation-height input')
    return text


def staydown_program(root, data):
    """Run the complete native mapper and selected attack getter route."""
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    first = source.index('enum _axis_enum')
    declarations = source[first:source.index('HRESULT openbor_getanimationproperty(', first)]
    body, cases = switch_cases(source, 'openbor_getentityproperty', 'propind', outermost=True)
    getter = (body[:body.index('switch(propind)')] + 'switch(propind){case _ep_attack:' +
              cases['_ep_attack']['body'] + 'default:' + cases['default']['body'] +
              '}\nreturn S_OK;\n}\n')
    lines = source.splitlines(keepends=True)
    first = next(i for i, line in enumerate(lines) if line.startswith('#define MAPSTRINGS('))
    last = first
    while lines[last].rstrip().endswith('\\'):
        last += 1
    macros = ''.join(line for line in lines if line.startswith('#define _is_not_')) + ''.join(lines[first:last + 1])
    modes = {'address': 0, 'signed_pointer': 1, 'unsigned_pointer': 2, 'integer': 3}
    rows = ','.join('{%du,%d,%d,%d,%d}' % (row['revision'], row['attack_property'],
                    row['staydown_property'], modes[row['mode']], row['idle_animation']) for row in data['sources'])
    values = dict(DECLARATIONS=declarations, GETTER=getter, MACROS=macros, CONTEXTS=rows,
        INPUTS=','.join('UINT32_C(%d)' % value for value in data['input_bits']),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        SEARCH=function(utils, 'searchList'))
    text = Path(__file__).with_name('classic_staydown_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native attack staydown input')
    return text
