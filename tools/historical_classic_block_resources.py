"""Render native block-resource arithmetic and numeric defense storage.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import re

from test_historical_player import function


def block_program(root, data):
    engine = root / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    attack = function(core, 'do_attack')
    start = attack.index('if(didblock && !level->nohurt)')
    resource = attack[start:attack.index('if(!didblock)', start)]
    load = function(core, 'load_cached_model')
    start = load.index('case CMD_MODEL_DEFENSE:')
    directives = load[start:load.index('case CMD_MODEL_HEIGHT:', start)]
    setter = function(script, 'openbor_changeentityproperty')
    start = setter.index('case _ep_defense:')
    setter = setter[start:setter.index('case _ep_detect:', start)]
    getter = function(script, 'openbor_getentityproperty')
    start = getter.index('case _ep_defense_blocktype:')
    getter = getter[start:getter.index('case _ep_defense_knockdown:', start)]
    cases = []
    for row in data['cases']:
        values = [repr(float(row['blocktype'])), str(row['mpblock']),
                  str(row['initial_mp']), str(row['initial_health']),
                  str(row['attack_force']), repr(float(row['ratio'])),
                  str(row['global_ratio']), str(row['didblock']),
                  str(row['nohurt']), str(row['nochipdeath'])]
        for group in ('old', 'later'):
            expected = row[group]
            values.append('{%s}' % ','.join(str(expected[key]) for key in
                ('health', 'mp', 'remaining_force', 'fatal_calls')))
        cases.append('{%s}' % ','.join(values))
    parts = dict(RESOURCE=resource, SETTER=setter, GETTER=getter,
        DIRECTIVES=directives,
        DEFAULT=re.search(r'const s_defense default_defense\s*=\s*\{[^}]*\};', core)[0],
        HELPERS='\n'.join(function(core, name) for name in
            ('obor_profile_default_defense', 'isNumeric', 'getValidInt', 'getValidFloat')),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_DecimalValue', 'ScriptVariant_IntegerValue')),
        CASES=',\n'.join(cases),
        CONTEXTS=',\n'.join('{%du,%d}' % (row['revision'], row['fractional_storage'])
                             for row in data['sources']))
    text = Path(__file__).with_name('classic_block_resources_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native block-resource input')
    return text
