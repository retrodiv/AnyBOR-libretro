"""Render complete native attack filtering and OTG script conversions.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import re

from historical_classic_attack_cancellation import cancellation_program
from test_historical_player import function


def otg_program(root, data, contact_data):
    names = [row['name'] for row in contact_data['cases']]
    selected = names.index(data['contact_case_name'])
    if contact_data['cases'][selected]['decisions'] != [[1, -1]]:
        raise ValueError('One confirmed native contact control required')
    prefix = cancellation_program(root, contact_data)
    prefix = prefix[:prefix.index('int main(void)')]
    engine = root / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    load = function(core, 'load_cached_model')
    start = load.index('case CMD_MODEL_OTG:')
    directive = load[start:load.index('case CMD_MODEL_JUGGLECOST:', start)]
    getter = function(script, 'openbor_getentityproperty')
    start = getter.index('case _ep_attack_otg:')
    getter = getter[start:getter.index('case _ep_attack_pause:', start)]
    setter = function(script, 'openbor_changeattackproperty')
    start = setter.index('case _ep_attack_otg:')
    setter = setter[start:setter.index('case _ep_attack_seal:', start)]
    rows = []
    for row in data['inputs']:
        rows.append('{%s,%d,{%s},{%s},%sLL,%sLL,%sLL}' % (
            repr(float(row['value'])), row['stored'],
            ','.join(map(str, row['signed_hits'])), ','.join(map(str, row['enum_hits'])),
            row['getter32'], row['signed_getter64'], row['enum_getter64']))
    parts = dict(PREFIX=prefix, CONTACT_CASE=str(selected), DIRECTIVE=directive,
        DEFAULT=re.search(r'const s_attack emptyattack\s*=\s*\{.*?\n\};', core, re.S)[0],
        HELPERS='\n'.join(function(core, name) for name in ('isNumeric', 'getValidInt')),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_DecimalValue', 'ScriptVariant_IntegerValue', 'ScriptVariant_ChangeType')),
        GETTER=getter, SETTER=setter, INPUTS=',\n'.join(rows),
        HIT_TRACE=','.join(map(str, data['hit_trace'])),
        CONTEXTS=',\n'.join('{%du,%d}' % (row['revision'], row['signed_otg'])
                             for row in data['sources']))
    text = Path(__file__).with_name('classic_otg_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native OTG input')
    return text
