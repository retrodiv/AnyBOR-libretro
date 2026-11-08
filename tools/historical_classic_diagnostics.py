"""Render native property mapping and diagnostic rejection guards.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re

from test_historical_player import function, switch_cases


def diagnostics_program(root, data):
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    first = source.index('enum _axis_enum')
    declarations = source[first:source.index('HRESULT openbor_getanimationproperty(', first)]
    entries = []
    for name, labels in (
            ('openbor_getentityproperty', ['dot', 'edelay', 'energycost', 'icon', 'knockdowncount', 'staydown']),
            ('openbor_changeentityproperty', ['knockdowncount', 'spritea', 'staydown'])):
        body, cases = switch_cases(source, name, 'propind', outermost=True)
        prefix = body[:body.index('switch(propind)')]
        # These static action tables are unused by the selected error paths.
        # Their implementations and valid property bodies are outside this probe.
        prefix = re.sub(r'static const void\s*\*\s*\w+\[\]\s*=\s*'
                        r'(?://[^\n]*\n\s*)?\{.*?\};', '', prefix, flags=re.S)
        selected = []
        setter = name == 'openbor_changeentityproperty'
        for label in labels:
            text = cases['_ep_' + label]['body']
            needle = ('if(varlist[2]->vt != VT_INTEGER)' if setter or label == 'energycost'
                      else 'if(arg->vt != VT_INTEGER)')
            first = text.index(needle)
            brace = text.index('{', first)
            heading = 'void diagnostic_guard(void) '
            compound = function(heading + text[brace:], 'diagnostic_guard')[len(heading):].rstrip('\n')
            guard = text[first:brace] + compound
            arg_index = 3 if label == 'dot' else 2
            argument = 'arg=varlist[%d];\n' % arg_index if 'if(arg->' in needle else ''
            selected.append('case _ep_' + label + ':{' + argument + guard + '\nabort();}\n')
        entry = prefix + 'switch(propind){\n' + ''.join(selected) + 'default:abort();}\n'
        if setter:
            entry += 'changeentityproperty_error:return E_FAIL;\n'
        entries.append(entry + '}\n')
    lines = source.splitlines(keepends=True)
    first = next(i for i, line in enumerate(lines) if line.startswith('#define MAPSTRINGS('))
    last = first
    while lines[last].rstrip().endswith('\\'):
        last += 1
    macros = ''.join(line for line in lines if line.startswith('#define _is_not_')) + ''.join(lines[first:last + 1])
    rows = []
    for row in data['sources']:
        cases = ','.join('{%d,%d,%d,%s,%s}' % (case['property_id'], case['arg_index'],
            case['setter'], json.dumps(case['property']), json.dumps(case['stdout'])) for case in row['cases'])
        rows.append('{%du,{%s}}' % (row['revision'], cases))
    values = dict(DECLARATIONS=declarations, ENTRIES='\n'.join(entries), MACROS=macros,
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        SEARCH=function(utils, 'searchList'), CONTEXTS=','.join(rows))
    text = Path(__file__).with_name('classic_diagnostics_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native diagnostic input')
    return text
