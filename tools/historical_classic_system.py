"""Render native system-variable namespaces and selected last-hit field controls.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re

from test_historical_player import function, rename_identifiers, switch_cases


def system_program(root, data):
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    core = (engine / 'openbor.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    first = source.index('static const char *svlist[]')
    declaration = source[first:source.index('// ===== openborvariant', first)]
    methods = '\n'.join(function(source, name) for name in
        ('obor_systemvariant_available', 'obor_systemvariant_native', 'mapstrings_systemvariant',
         'openbor_systemvariant', 'openbor_changesystemvariant'))
    selected = ('_sv_lasthita', '_sv_lasthity', '_sv_lasthitc', '_sv_lasthitt', '_sv_lasthitx', '_sv_lasthitz')
    callbacks = []
    for name in ('getsyspropertybyindex', 'changesyspropertybyindex'):
        body, cases = switch_cases(core, name, 'index', outermost=True)
        callback = (body[:body.index('switch(index)')] + 'switch(index){' +
            ''.join('case '+key+':'+cases[key]['body'] for key in selected) +
            'default:'+cases['default']['body'] + '}\nreturn 1;\n}\n')
        callbacks.append(rename_identifiers(callback, {name:'probe_'+name}))
    dispatcher = function(source, 'Script_GetStringMapFunction')
    owned = {'openbor_systemvariant', 'openbor_changesystemvariant', 'mapstrings_systemvariant'}
    stubs = sorted(set(re.findall(r'\(void\s*\*\)\s*(\w+)', dispatcher))-owned)
    dispatcher = rename_identifiers(dispatcher, {name:'probe_symbol_'+name for name in stubs})
    rows = []
    for row in data['sources']:
        rows.append('{%du,%d,{%s},{%s},%d,{%s}}' % (row['revision'], len(row['properties']),
            ','.join(json.dumps(name) for name in row['properties']),
            ','.join(map(str,row['native_ids'])), len(row['queries']),
            ','.join(str(row['properties'].index(name)) for name in row['queries'])))
    values = dict(DECLARATION=declaration, METHODS=methods, FIELDS='\n'.join(callbacks),
        DISPATCH=dispatcher, STUBS='\n'.join('static void probe_symbol_%s(void){++unused_calls;}' % name for name in stubs),
        CONTEXTS=','.join(rows), VARIANTS='\n'.join(function(variant,name) for name in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')))
    text = Path(__file__).with_name('classic_system_variant_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native system-variable input')
    return text
