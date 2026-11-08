"""Render native facing storage, arithmetic and source-defined caller routes.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import re

from test_historical_player import function
from test_early_jump_walkoff import continued_macro


def direction_program(root, data):
    engine = root / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    getter = function(script, 'openbor_getentityproperty')
    setter = function(script, 'openbor_changeentityproperty')
    arms = {}
    for key, source in [('GETTER', getter), ('SETTER', setter)]:
        start = source.index('case _ep_direction:')
        stop = source.index('case _ep_dot:', start)
        arms[key] = source[start:stop]
    grabs = re.findall(r'(?m)^\s*(other->position\.x\s*=\s*[^;]*obor_direction_grab_offset[^;]*;)',
                       function(core, 'player_grab_check'))
    if len(grabs) != 2:
        raise ValueError('Both native grab-completion positions required')
    rows = []
    def matrix(values, floating=False):
        return '{' + ','.join('{' + ','.join(
            repr(float(x)) + 'f' if floating else str(x) for x in row) + '}'
            for row in values) + '}'
    for row in data['sources']:
        rows.append('{%du,%d,%d,{%s},{%s},{%s},{%s},%s,%s,%s,%s,%s}' % (
            row['revision'], row['signed_field'], row['whole_routes'],
            ','.join(map(str, row['right'])),
            ','.join(str(x) + 'LL' for x in row['getter32']),
            ','.join(str(x) + 'LL' for x in row['getter64']),
            ','.join(repr(float(x)) + 'f' for x in row['grab_x']),
            matrix(row['binding_x']), matrix(row['binding_stored']),
            matrix(row['target_selected']), matrix(row['range_accepted']),
            matrix(row['arrow_velocity'], True)))
    parts = dict(**arms,
        FUNCTIONS='\n'.join(function(core, name) for name in
            ('diff', 'adjust_bind', 'normal_find_target', 'ent_spawn_ent', 'ent_summon_ent', 'arrow_move')),
        MACROS='\n'.join(continued_macro(core, name) for name in
            ('common_up_anim', 'common_down_anim', 'common_walk_anim')),
        PROJECTILE=function(script, 'openbor_projectile'),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_DecimalValue', 'ScriptVariant_IntegerValue', 'ScriptVariant_ChangeType')),
        GRAB_A=grabs[0], GRAB_B=grabs[1], CONTEXTS=',\n'.join(rows),
        DIRECTIONS=','.join(map(str, data['bounded_directions'])),
        INPUTS=','.join(repr(float(x)) for x in data['property_inputs']),
        STORED=','.join(map(str, data['property_stored'])),
        MODES=','.join(map(str, data['force_modes'])),
        DIR_COUNT=str(len(data['bounded_directions'])), INPUT_COUNT=str(len(data['property_inputs'])),
        MODE_COUNT=str(len(data['force_modes'])))
    text = Path(__file__).with_name('classic_direction_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native facing input')
    return text
