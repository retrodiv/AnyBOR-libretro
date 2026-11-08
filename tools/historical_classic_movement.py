"""Render native time-expansion and gravity-property component controls.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import re

from test_historical_player import function, switch_cases


def program(root, data):
    engine = root / 'src/engines' / data['engine']
    lines = (engine / 'openbor.h').read_text().splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.startswith('#define expand_time(e)')]
    if len(starts) != 1:
        raise ValueError('One native expand_time macro required')
    end = starts[0]
    while lines[end].rstrip().endswith('\\'):
        end += 1
    macro = ''.join(lines[starts[0]:end+1])
    script = (engine / 'openborscript.c').read_text()
    bodies = {}
    for key, method in [('GETTER', 'openbor_getentityproperty'),
                        ('SETTER', 'openbor_changeentityproperty')]:
        _, cases = switch_cases(script, method, 'propind', outermost=True)
        bodies[key] = cases['_ep_antigravity']['body']
    fields = dict(MACRO=macro, **bodies,
                  CONTEXTS=','.join('{%du,%d,%d}' % (r['revision'],
                      r['advance_nextmove'], r['model_antigravity_getter'])
                      for r in data['sources']))
    text = Path(__file__).with_name('classic_movement_contract.c.in').read_text()
    for key, value in fields.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native movement control input')
    return text


def backwalk_program(root, data):
    source = (root / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    method, cases = switch_cases(source, 'player_think', 'action', outermost=True)
    dispatch = method.index('switch(action)')
    prefix = method[method.rfind('    if(action)', 0, dispatch):dispatch]
    if 'self->takeaction = NULL;' not in prefix or 'self->idling = 1;' not in prefix:
        raise ValueError('Native movement dispatch state prefix required')
    macros = []
    lines = source.splitlines(keepends=True)
    for name in ('common_walk_anim', 'common_backwalk_anim'):
        starts = [i for i, line in enumerate(lines) if line.startswith('#define ' + name + '(')]
        if len(starts) != 1:
            raise ValueError('One native animation dispatch macro required')
        end = starts[0]
        while lines[end].rstrip().endswith('\\'):
            end += 1
        macros.append(''.join(lines[starts[0]:end + 1]))
    values = dict(PREFIX=prefix, WALK=cases['1']['body'], MACROS='\n'.join(macros),
        SERIES=function(source, 'common_anim_series'),
        CONTEXTS=','.join('{%du,{%s}}' % (row['revision'],
            ','.join(str(n) for n in data['contracts'][row['contract']])) for row in data['sources']),
        CASES=','.join('{%s}' % ','.join(str(row[k]) for k in
            ('model_facing', 'level_facing', 'direction', 'left_scroll', 'level', 'animation', 'turn', 'delay'))
            for row in data['cases']), CASE_COUNT=str(len(data['cases'])))
    text = Path(__file__).with_name('classic_backwalk_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native walking contract input')
    return text
