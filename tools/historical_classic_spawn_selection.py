"""Render native spawn callbacks and selection setup side effects.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re

from test_historical_player import function


def spawn_callback_program(root, data):
    engine = root / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    parts = dict(CALLER=function(core, 'execute_spawn_script'),
        INITIALIZED=function(script, 'Script_IsInitialized'),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType', 'ScriptVariant_Copy')),
        CONTEXTS=','.join('{%du,%d}' % (row['revision'], row['spawn_locals']) for row in data['sources']),
        POSITIONS=','.join('{{%s},%d,{%s},%d}' % (
            ','.join(repr(float(value)) for value in row['input'][:3]), row['input'][3],
            ','.join(repr(float(value)) for value in row['expected'][:3]), row['expected'][3])
            for row in data['spawn_positions']))
    text = Path(__file__).with_name('classic_spawn_callback_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native spawn callback input')
    return text


def selection_program(root, data):
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openbor.c').read_text()
    method = function(source, 'selectplayer')
    start = method.index('        if(obor_profile_build >= 3990)')
    stop = method.index('\n    for(i = 0; i < set->maxplayers; i++)', start)
    prefix = method[:stop] + '\nobserve_continuation(string,defaultselect);return -73;\n}\n'

    def snapshot(row):
        return '{%d,%d,{%s},{%s},{%s},{%s}}' % (
            row['select_screen'], row['credits'], ','.join(map(str, row['player_credits'])),
            ','.join(map(str, row['player_lives'])), ','.join(map(str, row['hasplayed'])),
            ','.join(json.dumps(value) for value in row['names']))

    cases = []
    for row in data['selection_cases']:
        modes = []
        for mode in ('old', 'later'):
            expected = row['expected'][mode]
            events = ','.join('{%d,%s,%s}' % (event['kind'], json.dumps(event['path']), snapshot(event))
                              for event in expected['events'])
            modes.append('{%d,%d,{%s},%s}' % (expected['result'], len(expected['events']),
                                            events, snapshot(expected['final'])))
        cases.append('{%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,{%s},%d,%d,{%s},{%s}}' % (
            row['file_style'], row['skip_first'], row['noselect'], row['noshare'],
            row['creditscheat'], row['menu_ok'], row['remix_ok'], row['unlockbg'], row['bonus'],
            row['custom_path'], row['maxplayers'], ','.join(map(str, row['players'])),
            row['continues'], row['lives'], ','.join(json.dumps(v) for v in row['skip_names']),
            ','.join(modes)))
    parts = dict(PREFIX=prefix, BACKGROUND=function(source, 'obor_select_default_background'),
        NUMBERS='\n'.join(function(source, name) for name in ('isNumeric', 'getValidInt')),
        CONTEXTS=','.join('{%du,%d}' % (row['revision'], row['early_skipselect']) for row in data['sources']),
        CASES=','.join(cases))
    text = Path(__file__).with_name('classic_selection_setup_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native selection setup input')
    return text
