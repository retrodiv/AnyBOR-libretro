"""Render native combo counters, script values, persistence and HUD dispatch.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import json
import re

from historical_classic_attack_cancellation import cancellation_program
from test_historical_player import function, rename_identifiers


def clock_namespace(text):
    text = rename_identifiers(text, {'time': 'fixture_clock'})
    return re.sub(r'((?:\.|->)\s*)fixture_clock\b', r'\1time', text)


def rush_program(root, data, contacts):
    names = [row['name'] for row in contacts['cases']]
    selected = names.index(data['contact_case_name'])
    if contacts['cases'][selected]['decisions'] != [[1, -1]]:
        raise ValueError('One confirmed native contact required')
    prefix = cancellation_program(root, contacts)
    prefix = prefix[:prefix.index('int main(void)')]
    engine = root / 'src/engines' / data['engine']
    core = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    hud = function(core, 'predrawstatus')
    start = hud.index('if(rush[0] &&')
    hud = hud[start:hud.index('if(player[i].ent->opponent', start)]
    think = function(core, 'player_think')
    start = think.index('if(time > self->rush.time)')
    expire = think[start:think.index('if(player_preinput())', start)]
    death = function(core, 'player_die')
    start = death.index('if(nomaxrushreset[4] >= 1)')
    capture = death[start:death.index('player[playerindex].ent = NULL;', start)]
    spawn = function(core, 'spawnplayer')
    start = spawn.index('if(nomaxrushreset[4] >= 1)')
    restore = spawn[start:spawn.index('memset(player[index].combokey', start)]
    parts = {}
    for key, name in [('GETTER', 'openbor_getentityproperty'),
                      ('SETTER', 'openbor_changeentityproperty')]:
        text = function(script, name)
        start = text.index('case _ep_rush_count:')
        parts[key] = text[start:text.index('case _ep_score:', start)]
    cases = []
    for row in data['counter_cases']:
        values = [str(row['current']), str(row['maximum']),
                  str(int(row['later_original_increment_defined']))]
        for group in ('unsigned', 'signed'):
            result = row[group]
            screens = ','.join('{%d,{%s}}' % (len(slots), ','.join(map(str, slots)) or '0')
                               for slots in result['hud_slots'])
            values.append('{%d,%d,%dLL,%dLL,%s,%s,{%s}}' % (
                result['current'], result['maximum'], result['current_getter64'],
                result['maximum_getter64'], json.dumps(result['current_text']),
                json.dumps(result['maximum_text']), screens))
        cases.append('{%s}' % ','.join(values))
    parts.update(PREFIX=prefix, CONTACT_CASE=str(selected),
        HUD=clock_namespace(hud), EXPIRE=clock_namespace(expire),
        CAPTURE=capture, RESTORE=restore,
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_DecimalValue', 'ScriptVariant_IntegerValue', 'ScriptVariant_ChangeType')),
        CONTEXTS=',\n'.join('{%du,%d}' % (row['revision'], row['unsigned_counter'])
                             for row in data['sources']),
        INPUTS=',\n'.join('{%d,%dLL,%dLL,%dLL}' % (row['value'], row['getter32'],
            row['unsigned_getter64'], row['signed_getter64']) for row in data['inputs']),
        CASES=',\n'.join(cases), CLOCK=str(data['clock']), DURATION=str(data['duration']),
        TIMER=str(data['clock'] + data['duration'] * data['game_speed']),
        GAME_SPEED=str(data['game_speed']),
        HUD_CASES=','.join('{%d,%du}' % (row['mode'], row['clock']) for row in data['hud_cases']),
        HUD_POSITIONS=','.join('{%s}' % ','.join(map(str, row)) for row in data['hud_positions']))
    text = Path(__file__).with_name('classic_rush_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native rush input')
    return text
