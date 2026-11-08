"""Render native text-property namespaces and complete valid callback controls.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import json
import re
from test_historical_player import function


def text_property_program(root, data):
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    first = source.index('enum gtop_enum')
    declarations = source[first:source.index('HRESULT openbor_gettextobjproperty(', first)]
    fields = {'font':0, 'text':1, 'time':2, 'x':3, 'y':4, 'z':5}
    values = dict(DECLARATIONS=declarations,
        CALLBACKS='\n'.join(function(source,name) for name in
            ('openbor_gettextobjproperty','openbor_changetextobjproperty')),
        VARIANTS='\n'.join(function(variant,name) for name in
            ('ScriptVariant_Clear','ScriptVariant_ChangeType','ScriptVariant_IntegerValue')),
        SEARCH=function(utils,'searchList'),
        CONTEXTS=','.join('{%du,%d,{%s},%d,{%s}}' % (row['revision'],len(row['properties']),
            ','.join(json.dumps(name) for name in row['properties']), len(row['fields']),
            ','.join(str(fields[name]) for name in row['fields'])) for row in data['sources']))
    text = Path(__file__).with_name('classic_text_property_contract.c.in').read_text()
    for key,value in values.items():
        text=text.replace('@'+key+'@',value)
    if re.search(r'@[A-Z_]+@',text):
        raise ValueError('Unresolved native text-property input')
    return text
