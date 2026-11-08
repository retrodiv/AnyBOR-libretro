"""Render native duration parsing, script values and effect application.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re

from test_historical_player import function, rename_identifiers, switch_cases


def time_program(root, data):
    engine = root / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    utils = (engine / 'source/utils.c').read_text()
    first = script.index('enum _axis_enum')
    declarations = script[first:script.index('HRESULT openbor_getanimationproperty(', first)]
    body, cases = switch_cases(script, 'openbor_getentityproperty', 'propind', outermost=True)
    getter = (body[:body.index('switch(propind)')] + 'switch(propind){case _ep_attack:' +
              cases['_ep_attack']['body'] + 'default:' + cases['default']['body'] +
              '}\nreturn S_OK;\n}\n')
    body, cases = switch_cases(script, 'openbor_changeattackproperty', 'prop', outermost=True)
    names = ['dottime', 'freezetime', 'maptime', 'sealtime']
    setter = (body[:body.index('switch(prop)')] + 'switch(prop){' + ''.join(
        'case _ep_attack_' + name + ':' + cases['_ep_attack_' + name]['body'] for name in names) +
        'default:goto cap_error;}\nreturn S_OK;\ncap_error:return E_FAIL;\n}\n')
    lines = script.splitlines(keepends=True)
    first = next(i for i, line in enumerate(lines) if line.startswith('#define MAPSTRINGS('))
    last = first
    while lines[last].rstrip().endswith('\\'):
        last += 1
    macros = ''.join(line for line in lines if line.startswith('#define _is_not_')) + ''.join(lines[first:last + 1])
    first = script.index('enum gtop_enum')
    text_declarations = script[first:script.index('HRESULT openbor_gettextobjproperty(', first)]
    load = function(core, 'load_cached_model')
    _, cases = switch_cases(core, 'load_cached_model', 'cmd', outermost=True)
    directives = ''.join('case ' + name + ':' + cases[name]['body'] for name in
                         ('CMD_MODEL_STUN', 'CMD_MODEL_FORCEMAP', 'CMD_MODEL_SEAL', 'CMD_MODEL_DOT'))
    first = load.rindex('case CMD_MODEL_FREEZE:')
    directives += load[first:load.index('case CMD_MODEL_ITEMBOX:', first)]
    effects = rename_identifiers(function(core, 'checkdamageeffects'), {'time': 'probe_clock'})
    effects = effects.replace('.probe_clock', '.time')
    attack = function(core, 'do_attack')
    pain = re.search(r'self->pain_time\s*=\s*time\s*\+\s*\([^;]*;', attack)[0]
    pain = rename_identifiers(pain, {'time': 'probe_clock'})
    values = dict(GAME_SPEED=str(data['game_speed']), DECLARATIONS=declarations, GETTER=getter, SETTER=setter,
        ATTACK_MAPPER=function(script, 'mapstrings_attackproperty'), MACROS=macros,
        TEXT_DECLARATIONS=text_declarations,
        TEXT_GETTER=function(script, 'openbor_gettextobjproperty'),
        DIRECTIVES=directives, EFFECTS=effects, PAIN=pain,
        HELPERS='\n'.join(function(core, name) for name in ('isNumeric', 'getValidInt', 'getValidFloat')),
        INAIR=function(core, 'diff') + '\n' + function(core, 'inair'),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue', 'ScriptVariant_DecimalValue')),
        SEARCH=function(utils, 'searchList'),
        CONTEXTS=','.join('{%du,%d,%d,{%s},%d,%d,%s}' % (
            row['revision'], row['signed_duration'], row['attack_property'],
            ','.join(map(str, row['attack_time_properties'])), row['idle_animation'],
            row['text_time_property'], json.dumps(row['text_time_name'])) for row in data['sources']),
        FLOATS=','.join('{%s,UINT32_C(%d),UINT32_C(%d),%d,%d}' % (
            json.dumps(row['text']), row['old_bits'], row['later_bits'],
            row['old_defined'], row['later_defined']) for row in data['float_loads']),
        RAW=','.join('{UINT32_C(%d),%sLL,UINT32_C(%d),UINT32_C(%d),%d}' % (
            row['bits'], row['signed'], row['old_ticks'], row['later_ticks'],
            row['old_product_defined']) for row in data['raw_times']),
        SCRIPT_VALUES=','.join(repr(float(value)) for value in data['script_values']),
        CLOCKS=','.join('UINT32_C(%d)' % value for value in data['clocks']))
    text = Path(__file__).with_name('classic_time_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native duration input')
    return text
