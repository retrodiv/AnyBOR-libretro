"""Render native blocking predicates and death/fall transitions.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
from pathlib import Path
import re

from test_historical_player import function, rename_identifiers


def condition(source, marker):
    """Keep the actual predicate, excluding its following branch body."""
    start = source.index('(', source.index(marker))
    # Comments do not contribute parentheses to a C expression.
    masked = re.sub(r'/\*.*?\*/|//[^\n]*', lambda m: ' ' * len(m[0]),
                    source, flags=re.S)
    depth = 0
    for end in range(start, len(source)):
        depth += (masked[end] == '(') - (masked[end] == ')')
        if not depth:
            return source[start + 1:end]
    raise ValueError('Unclosed combat predicate')


def program(root, data):
    source = (root / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    attack = function(source, 'do_attack')
    values = dict(PASSIVE=condition(attack, 'if( !self->modeldata.nopassiveblock'),
        MANUAL=condition(attack, 'else if((self->modeldata.nopassiveblock'),
        FUNCTIONS='\n'.join(function(source, name) for name in ('set_death', 'set_fall')),
        CONTEXTS=','.join('{%du,%d,%d}' % (r['revision'], r['player_block'],
                                         r['clear_nonfrozen_time']) for r in data['sources']))
    text = Path(__file__).with_name('classic_combat_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved combat contract input')
    return text


def defense_program(root, data):
    """Use native default writes, directive arms, getter and counter gate."""
    engine = root / 'src/engines' / data['engine']
    source = (engine / 'openbor.c').read_text()
    script = (engine / 'openborscript.c').read_text()
    initializer = re.search(r'const s_defense default_defense\s*=\s*\{[^}]*\};', source)
    if initializer is None:
        raise ValueError('Native default defense initializer required')
    init = function(source, 'init_model')
    init = init[init.index('//Default offense/defense values.'):init.index('//Default sight ranges.')]
    load = function(source, 'load_cached_model')
    defense = load[load.index('case CMD_MODEL_DEFENSE:'):load.index('case CMD_MODEL_OFFENSE:')]
    counter = load[load.index('case CMD_MODEL_COUNTERFRAME:'):load.index('case CMD_MODEL_WEAPONFRAME:')]
    attack = function(source, 'do_attack')
    marker = 'else if((self->animpos >= self->animation->counterrange.frame.min'
    start = attack.index(marker)
    damage = attack.index('if(obor_profile_build < 4065', start)
    stop = attack.index('current_follow_id =', damage)
    damage = attack[damage:stop]
    getter = script[script.index('case _ep_defense_blocktype:'):script.index('case _ep_defense_knockdown:')]
    values = dict(DEFAULT=initializer[0],
        HELPERS='\n'.join(function(source, name) for name in
                          ('obor_profile_default_defense', 'isNumeric', 'getValidInt', 'getValidFloat')),
        INIT=init, DEFENSE=defense, COUNTER=counter, GATE=condition(attack[start:], marker),
        DAMAGE=damage, GETTER=getter,
        CONTEXTS=','.join('{%du,%d,%d,{%s}}' % (row['revision'], row['default_blocktype'],
            row['counter_nonzero'], ','.join(map(str, row['attack_slots']))) for row in data['sources']))
    text = Path(__file__).with_name('classic_defense_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native defense contract input')
    return text


def projectile_cost_program(root, data):
    source = (root / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    attack = function(source, 'do_attack')
    mp = attack.index('topowner->mp > 0')
    first = attack.rfind('    if(didhit)', 0, mp)
    last = attack.index('        // New blocking checks', mp)
    if first < 0:
        raise ValueError('Native hit-cost caller gate required')
    cost = attack[first:last]
    if cost.count('{') != cost.count('}') + 1 or 'e->tocost = 1;' not in cost:
        raise ValueError('Complete native cost branches and enclosing hit gate required')
    fields = dict(COST=cost + '\n    }\n',
        CASE_COUNT=str(len(data['cases'])),
        CASES=','.join('{%s}' % ','.join(str(row[k]) for k in
            ('mode', 'hp', 'mp', 'cost', 'hit', 'owner', 'nocost', 'cheat', 'already_charged'))
            for row in data['cases']),
        CONTEXTS=','.join('{%du,{%s}}' % (row['revision'],
            ','.join('{%s}' % ','.join(str(n) for n in result)
                for result in data['contracts'][row['contract']])) for row in data['sources']))
    text = Path(__file__).with_name('classic_projectile_cost_contract.c.in').read_text()
    for key, value in fields.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native projectile-cost input')
    return text


def weapon_loss_program(root, data):
    source = (root / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    initialize = function(source, 'init_model')
    default = initialize[initialize.index('    newchar->weaploss[0]'):
                         initialize.index('    newchar->lifespan')]
    load = function(source, 'load_cached_model')
    directive = load[load.index('case CMD_MODEL_WEAPLOSS:'):load.index('case CMD_MODEL_WEAPNUM:')]
    grabs = {}
    for key, name, stop in (('AI', 'common_grab_check', '    self->attacking = 0;'),
                             ('PLAYER', 'player_grab_check', '    // grabturn code')):
        body = function(source, name)
        grabs[key] = body[body.index('    if(!nolost'):body.index(stop)]
    damage = function(source, 'common_takedamage')
    damage = damage[damage.index('    // pre-check drop'):
                    damage.index('        if(self->health <= 0 && self->modeldata.falldie')]
    if damage.count('{') != damage.count('}') + 1:
        raise ValueError('Complete ordered hit and fall weapon-loss prefix required')
    stage = function(source, 'player_die')
    mode = stage.index('self->modeldata.weaploss[0]')
    stage = stage[stage.rfind('        if(', 0, mode):stage.index('        if(nomaxrushreset[4] != 2)')]
    values = dict(DEFAULT=default, DIRECTIVE=directive, **grabs,
        DAMAGE=damage + '\n    }\n', STAGE=stage,
        FUNCTIONS=function(source, 'set_weapon') + '\n' +
            rename_identifiers(function(source, 'dropweapon'), {'time': 'fixture_time'}),
        NUMBERS='\n'.join(function(source, name) for name in ('isNumeric', 'getValidInt', 'getValidFloat')),
        CONTEXTS=','.join('{%du,%d,%d}' % (row['revision'], row['default'],
            0 if row['contract'] == 'legacy' else 1) for row in data['sources']),
        CASES=','.join('{%s}' % ','.join(str(row[k]) for k in
            ('op', 'mode', 'fallback', 'is_player', 'nolost', 'after_hp', 'knockdown', 'physical', 'policy', 'weapon'))
            for row in data['cases']),
        EXPECTED=','.join('{%s}' % ','.join('{%s,%d,{%s}}' %
            (','.join(str(row[k]) for k in ('saved', 'mode', 'fallback', 'physical', 'falling')),
             len(row['trace']), ','.join('{%s}' % ','.join(str(n) for n in event) for event in row['trace']) or '{0}')
            for row in data['contracts'][key]) for key in ('legacy', 'enumerated')),
        CASE_COUNT=str(len(data['cases'])))
    text = Path(__file__).with_name('classic_weapon_loss_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native weapon-loss input')
    return text
