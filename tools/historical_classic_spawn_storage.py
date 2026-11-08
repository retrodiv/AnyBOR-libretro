"""Render level-coordinate loading and complete player-spawn controls.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re

from test_historical_player import function, rename_identifiers, switch_cases


def program(root, data):
    source = (root / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    labels = ['CMD_LEVEL_SPAWN' + str(i) for i in range(1, 5)]
    _, arms = switch_cases(source, 'load_level', 'cmd', outermost=True)
    loader = '\n'.join('case ' + label + ':' + arms[label]['body'] for label in labels)
    init = function(source, 'ent_default_init')
    start = init.index('        if(validanim(e, ANI_SPAWN) || validanim(e, ANI_RESPAWN))')
    stop = init.index('        if(time && e->modeldata.makeinv)', start)
    altitude = rename_identifiers(init[start:stop], {'time': 'game_time'})
    defaults = re.findall(r'^\s*obor_level_spawn_defaults\(level, obor_profile_build\);[^\n]*',
                          function(source, 'load_level'), re.M)
    if len(defaults) != 1:
        raise AssertionError('One native spawn default call required')
    directions = dict(left='SCROLL_LEFT', right='SCROLL_RIGHT',
                      inward='SCROLL_INWARD', outward='SCROLL_OUTWARD')
    cases = []
    for row in data['cases']:
        expected = ','.join('{%s}' % ','.join(repr(float(v)) for v in row['expected'][mode])
                            for mode in ('integer', 'float'))
        cases.append('{{%s},%d,%d,%d,%s,%d,{%s},%s}' % (
            ','.join(map(str, row['coordinates'])), row['minimum'], row['maximum'],
            row['width'], directions[row['scroll']], row['player'], expected,
            repr(float(row['altitude']))))
    parts = dict(LOADER=loader, DEFAULTS=defaults[0], ALTITUDE=altitude,
                 SPAWN=function(source, 'spawnplayer'),
                 NUMBERS='\n'.join(function(source, n) for n in ('isNumeric', 'getValidInt')),
                 CONTEXTS=','.join('{%du,%d}' % (r['revision'], r['integer_storage'])
                                   for r in data['sources']), CASES=','.join(cases))
    text = Path(__file__).with_name('classic_spawn_storage_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native spawn storage input')
    return text
