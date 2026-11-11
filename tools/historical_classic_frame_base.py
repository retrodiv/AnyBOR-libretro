"""Render native frame-base storage and its changed consumer branches.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import re

from test_historical_player import function
from test_early_jump_walkoff import braced_statement
from native_header_fixtures import assertion_refusals


def frame_base_program(root, data):
    source = (root / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    update = function(source, 'update_frame')
    movement = braced_statement(update, 'if(level && obor_frame_has_move(')
    start = update.index('if(obor_frame_has_base(anim, 0,')
    update = update[start:update.index('if(anim->flipframe == f)', start)]
    gravity = function(source, 'check_gravity')
    arm = braced_statement(gravity, 'else if(!obor_frame_has_base(')
    tail = gravity[gravity.index(arm) + len(arm):].lstrip()
    gravity = arm.removeprefix('else ') + '\n' + braced_statement(tail[:tail.index('\n\n')], 'else')
    hole = braced_statement(function(source, 'common_trymove'),
                           'if( !(self->modeldata.type & TYPE_PLAYER)')
    loading = function(source, 'load_cached_model')
    first = loading.index('case CMD_MODEL_SETA:')
    directive = loading[first:loading.index('case CMD_MODEL_MOVE:', first)]
    # Expectations are source-reviewed fixture data, independent of the native
    # predicates and storage code being exercised.
    cases = []
    for case in data['cases']:
        def oracle(kind):
            return '{' + ','.join('{%d,%d,%d,{{%s}}, {%s},{%s},{%s}}' %
                (row['base'], row['dy'], row['active'],
                 '},{'.join(','.join(map(str, pair)) for pair in row['update']),
                 ','.join(map(str, row['gravity'])), ','.join(map(str, row['hole'])),
                 ','.join(map(str, row['adjust']))) for row in case['oracles'][kind]) + '}'
        commands = ','.join('{%d,%d}' % (value is not None, value or 0)
                            for value in case['commands'])
        cases.append('{%d,{%s},%s,%s}' % (len(case['commands']), commands,
                                        oracle('legacy'), oracle('modern')))
    values = dict(ASSERTIONS=assertion_refusals(), FUNCTIONS='\n'.join(function(source, name) for name in
        ('setDrawMethod', 'getDrawMethod', 'alloc_frames', 'addframe', 'free_frames',
         'diff', 'inair', 'obor_classic_vault_animation', 'adjust_base')),
        NUMBERS='\n'.join(function(source, name) for name in ('isNumeric', 'getValidInt')),
        DIRECTIVE=directive, UPDATE=update, MOVE_UPDATE=movement,
        MOVE_CASES=',\n'.join('{%d,{%s},%d,{%s}}' %
            (len(row['frames']), ','.join('{%d,%d}' % tuple(pair) for pair in row['frames']),
             row['legacy_active'], ','.join(map(str, row['modern_active'])))
            for row in data['movement_cases']),
        MOVE_MAX_FRAMES=str(max(len(row['frames']) for row in data['movement_cases'])),
        GRAVITY=gravity, HOLE=hole,
        CONTEXTS=','.join('{%du,%d}' % (row['revision'], row['legacy_seta'])
                          for row in data['sources']), CASES=',\n'.join(cases),
        MAX_FRAMES=str(max(len(case['commands']) for case in data['cases'])),
        ALTBASES=','.join(map(str, data['altbases'])),
        INITIAL_BASES=','.join(map(str, data['initial_bases'])))
    text = Path(__file__).with_name('classic_frame_base_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native frame-base control input')
    return text
