"""Render native import failure and post-reset call controls.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import re

from test_historical_player import function


def program(root, data):
    engine = root / 'src/engines' / data['engine']
    imports = (engine / 'source/scriptlib/ImportCache.c').read_text()
    interpreter = (engine / 'source/scriptlib/Interpreter.c').read_text()
    first = imports.index('struct ImportNode\n')
    record = imports[first:imports.index('};', first) + 2]
    values = dict(RECORD=record, IMPORT=function(imports, 'ImportNode_Init'),
        RESET='\n'.join(function(interpreter, name) for name in
                        ('Interpreter_Reset', 'Interpreter_EvaluateCall')),
        CONTEXTS=','.join('{%du,%d,%d}' % (row['revision'], row['import_diagnostics'],
            row['reset_clears_call']) for row in data['sources']))
    text = Path(__file__).with_name('classic_script_control_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved script control input')
    return text


def animation_registry_program(root, data):
    """Run the native registry and pointer-name lookup with recording services."""
    import json
    source = (root / 'src/engines' / data['engine'] / 'openborscript.c').read_text()
    methods = '\n'.join(function(source, name) for name in
                        ('Script_GetFunctionName', 'Script_LoadSystemFunctions'))
    symbols = sorted(set(re.findall(r'\(\s*void\s*\*\s*\)\s*(\w+)', methods)))
    if not 8 <= len(symbols) <= 512:
        raise ValueError('Bounded complete registry and diagnostic symbols required')
    values = dict(STUBS='\n'.join('static void %s(void) {++calls[%d];}' % (name, i)
                                  for i, name in enumerate(symbols)),
        SYMBOL_COUNT=str(len(symbols)), METHODS=methods,
        CONTEXTS=','.join('{%du,%d,%s,%s,%s}' % (row['revision'], row['registered'],
            json.dumps(row['entity_label']), json.dumps(row['player_label']),
            json.dumps(row['animation_label'])) for row in data['sources']))
    text = Path(__file__).with_name('classic_animation_registry_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved animation registry contract input')
    return text


def dograb_program(root, data):
    """Render the complete native registry, lookup and grab script wrapper."""
    import json
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    methods = '\n'.join(function(source, name) for name in
                        ('Script_GetFunctionName', 'Script_LoadSystemFunctions'))
    symbols = sorted(set(re.findall(r'\(\s*void\s*\*\s*\)\s*(\w+)', methods)))
    if not 8 <= len(symbols) <= 512 or 'openbor_dograb' not in symbols:
        raise ValueError('Bounded complete registry with grab callback required')
    values = dict(STUBS='\n'.join(
            'HRESULT %s(ScriptVariant **a, ScriptVariant **b, int n) '
            '{(void)a;(void)b;(void)n;++unused_calls[%d];return S_OK;}' % (name, i)
            for i, name in enumerate(symbols) if name != 'openbor_dograb'),
        SYMBOL_COUNT=str(len(symbols)), METHODS=methods,
        CALLBACK=function(source, 'openbor_dograb'),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
        CONTEXTS=','.join('{%du,%d,%d,%s}' % (row['revision'], row['registered'],
            row['legacy_return'], json.dumps(row['diagnostic_name'])) for row in data['sources']),
        CASES=','.join('{%d,%d,%s,%d}' % (row['arguments'], row['entities'],
            row['adjust_type'], row['adjust_value']) for row in data['cases']),
        ERROR_TEXT=json.dumps(data['modern_error']))
    text = Path(__file__).with_name('classic_dograb_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved grab script control input')
    return text


def player_properties_program(root, data):
    import json
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    enum = re.search(r'enum playerproperty_enum\s*\{.*?\};', source, re.S)
    if enum is None:
        raise ValueError('Native player property enum required')
    lines = source.splitlines(keepends=True)
    first = next(i for i, line in enumerate(lines) if line.startswith('#define MAPSTRINGS('))
    last = first
    while lines[last].rstrip().endswith('\\'):
        last += 1
    values = dict(ENUM=enum[0], MAP_MACRO=''.join(lines[first:last+1]),
        SEARCH=function(utils, 'searchList'),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue', 'ScriptVariant_ToString')),
        METHODS='\n'.join(function(source, name) for name in
            ('obor_playerproperty_native', 'mapstrings_playerproperty',
             'openbor_getplayerproperty', 'openbor_changeplayerproperty')),
        CONTEXTS=','.join('{%du,%d,{%s}}' % (row['revision'], len(row['properties']),
            ','.join(json.dumps(name) for name in row['properties'])) for row in data['sources']))
    # Every own source must retain its declared API shape; a native default arm
    # is not permission to invent an otherwise absent getter.
    for row in data['sources']:
        if row['settable'] != row['properties'] or row['gettable'] != [
                name for name in row['properties'] if name != 'weapon']:
            raise ValueError('Source player property case inventory needs a separate expectation')
    text = Path(__file__).with_name('classic_player_properties_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved player property input')
    return text


def drawmethod_program(root, data):
    import json
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    main = (engine / 'openbor.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    enum = re.search(r'enum drawmethod_enum\s*\{.*?\};', source, re.S)
    default = re.search(r'(?m)^const s_drawmethod plainmethod\s*=\s*\{.*?^\};', main, re.S)
    if enum is None or default is None:
        raise ValueError('Native drawing property enum and defaults required')
    registry = function(source, 'Script_LoadSystemFunctions')
    if re.search(r'\bopenbor_getdrawmethod\b', registry):
        raise ValueError('Unregistered draw getter requires its own availability review')
    lines = source.splitlines(keepends=True)
    first = next(i for i, line in enumerate(lines) if line.startswith('#define MAPSTRINGS('))
    last = first
    while lines[last].rstrip().endswith('\\'):
        last += 1
    values = dict(ENUM=enum[0], DEFAULT=default[0], MAP_MACRO=''.join(lines[first:last+1]),
        SEARCH=function(utils, 'searchList'),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        METHODS='\n'.join(function(source, name) for name in
            ('obor_drawmethod_property_native', 'mapstrings_drawmethodproperty', 'openbor_changedrawmethod')),
        CONTEXTS=','.join('{%du,%d,{%s}}' % (row['revision'], len(row['properties']),
            ','.join(json.dumps(name) for name in row['properties'])) for row in data['sources']))
    text = Path(__file__).with_name('classic_drawmethod_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native drawmethod input')
    return text
