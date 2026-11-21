"""Execute native attack callback locals, cleanup and caller arguments.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, contract_revisions, load_contract_fixture
from test_early_jump_walkoff import braced_statement
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-attack-callbacks-contracts.json'
RECORD_FIXTURE = FIXTURE.with_name('profile-6391-combat-callbacks.json')
OPERAND_FIXTURE = FIXTURE.with_name('profile-combat-operands.json')
DAMAGE_FALL_DEATH_FIXTURE = FIXTURE.with_name('profile-damage-fall-death-callbacks.json')
DEFENSE_SLOT = re.compile(r'(?m)^    const int defense_slot = [^;]+;')


def source_calls(source, names):
    """Extract complete direct calls, excluding comments and literal text."""
    if (not isinstance(source, str) or not source.strip() or len(source) > 262144 or
            not isinstance(names, (list, tuple)) or not names or
            any(not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_]\w*', name) for name in names) or
            len(set(names)) != len(names)):
        raise ValueError('Explicit native callees required')
    masked = re.sub(r'/\*.*?\*/|//(?:\\(?:\r?\n|[\s\S])|[^\n\\])*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                    lambda m: re.sub(r'[^\n]', ' ', m[0]), source, flags=re.S)
    rows = []
    for match in re.finditer(r'\b('+'|'.join(re.escape(n) for n in names)+r')\s*\(', masked):
        start = match.end(); depth = 1; cursor = start; boundaries = [start]
        while cursor < len(masked) and depth:
            value = masked[cursor]
            if value == ',' and depth == 1:
                boundaries.append(cursor + 1)
            depth += (value == '(') - (value == ')'); cursor += 1
        if depth:
            raise ValueError('Incomplete native callback call')
        if masked[cursor:].lstrip().startswith('{'):
            continue
        ends = [i - 1 for i in boundaries[1:]] + [cursor - 1]
        args = [source[a:b].strip() for a, b in zip(boundaries, ends)]
        rows.append(dict(callee=match[1], arguments=args, text=source[match.start():cursor]))
    return rows


def program(data, engine):
    core = (engine / 'openbor.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    contexts = ','.join('{%du,%d}' % (r['revision'], r['tag']) for r in data['sources'])
    keys = ['{'+','.join(json.dumps(n) for n in row['keys'])+'}' for row in data['callbacks']]
    sizes = ','.join(str(len(row['keys'])) for row in data['callbacks'])
    observed = []
    for owner in data['caller_functions']:
        for index, row in enumerate(source_calls(function(core, owner), data['callees'])):
            observed.append(row | dict(owner=owner, ordinal=index))
    if [(r['owner'], r['ordinal'], r['callee']) for r in observed] != [
            (r['owner'], r['ordinal'], r['callee']) for r in data['calls']]:
        raise ValueError('Complete independently inventoried callback caller sequence required')
    cases = '\n'.join('case %d:%s;break;' % (i, row['text']) for i, row in enumerate(observed))
    expected = ','.join('{%d,%d,%d,{%s},%d}' % (r['kind'], r['entity'], r['other'],
        ','.join(map(str, r['values'])), r['attack_tag']) for r in data['calls'])
    values = dict(CONTEXTS=contexts, KEYS=','.join(keys), KEY_COUNTS=sizes,
        CALLBACKS='\n'.join(function(core, name) for name in data['functions']),
        FALL=function(core, 'set_fall'), CALLS=cases, EXPECTED_CALLS=expected,
        TAG_VALUES=','.join(map(str, data['tag_values'])),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType')))
    text = Path(__file__).with_name('forward_attack_callbacks_contract.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native attack callback input')
    return text


def operand_program(data, engine):
    core = (engine / 'openbor.c').read_text(encoding='latin-1')
    script = (engine / 'openborscript.c').read_text(encoding='latin-1')
    variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    attack = function(core, 'do_attack')
    blocking = attack.index('//if #05,   blocking code section')
    item = braced_statement(attack[blocking:], 'if(attack->attack_type == ATK_ITEM)')
    callbacks = ('execute_ondoattack_script', 'execute_didhit_script', 'execute_didblock_script')
    calls = source_calls(attack.replace(item, '', 1), callbacks)
    expected = [callbacks[0], callbacks[0], callbacks[1], callbacks[2],
                callbacks[1], callbacks[2], callbacks[1]]
    if [call['callee'] for call in calls] != expected:
        raise ValueError('Complete original attack, block and hit callback sequence required')
    pickup_calls = []
    for caller, count in (('common_pickupitem', 1), ('player_think', 2)):
        pickup = source_calls(function(core, caller), ('execute_didhit_script', 'do_item_script'))
        if len(pickup) != count:
            raise ValueError('Complete native pickup callback calls required in ' + caller)
        pickup_calls.extend(pickup)
    _, gets = switch_cases(script, 'openbor_getentityproperty', 'propind', outermost=True)
    _, sets = switch_cases(script, 'openbor_changeentityproperty', 'propind', outermost=True)

    def cases(arms):
        return 'case 0:' + arms['_ep_attackid']['body'] + 'case 1:' + arms['_ep_hitbyid']['body']

    helpers = ''
    if data['engine'] == '6391':
        empty = re.search(r'(?ms)^const s_collision_attack emptyattack\s*=\s*\{.*?^\};', core)[0]
        helpers = '\n'.join((empty, function(core, 'do_item_script'), function(core, 'obor_remember_attack')))
    parts = {
        'HELPERS': helpers,
        'ITEM_BRANCH': item,
        'CALLS': '\n'.join(call['text'] + ';' for call in calls),
        'PICKUP_CALLS': '\n'.join(f'case {index}: {call["text"]}; break;'
                                 for index, call in enumerate(pickup_calls)),
        'GETTERS': cases(gets),
        'SETTERS': cases(sets),
        'VARIANTS': '\n'.join(function(variants, name) for name in
                              ('ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
        'PROFILES': ','.join('{%du,%d}' % (row['revision'], row['record_operands'])
                             for row in data['sources']),
    }
    template = Path(__file__).with_name('combat_operands_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)


def damage_fall_death_program(data, engine):
    core = (engine / 'openbor.c').read_text(encoding='latin-1')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin-1')
    methods = ('execute_takedamage_script', 'execute_onfall_script', 'execute_ondeath_script', 'checkdamage')
    force = ('obor_apply_damage_factor', 'obor_force_damage') if data['engine'] == '4432' else ('calculate_force_damage',)
    fall_call, = source_calls(function(core, 'set_fall'), ('execute_onfall_script',))
    values = {
        'CALLBACKS': '\n'.join(function(core, name) for name in force + methods),
        'FALL_CALL': fall_call['text'] + ';',
        'VARIANTS': '\n'.join(function(variant, name) for name in
                              ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType')),
        'ROWS': ','.join('{%du,%d,%d}' % (row['revision'], row['record'], row['timeover'])
                         for row in data['sources']),
    }
    template = Path(__file__).with_name('damage_fall_death_callbacks_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


class ForwardAttackCallbackTests(unittest.TestCase):
    def test_6391_original_unsummon_frame(self):
        data = load_contract_fixture(FIXTURE.with_name('profile-6391-unsummon-frame.json'))
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_ATTACK_CALLBACKS_ENGINE', ROOT / 'src/engines' / '6391'))
        core = (engine / 'openbor.c').read_text(encoding='latin-1')
        frame = braced_statement(function(core, 'update_frame'), 'if(anim->unsummonframe == f)')
        removal = braced_statement(function(core, 'kill_entity'), 'if(victim->modeldata.summonkill)')
        damage = function(core, 'common_takedamage')
        store = re.search(r'(?ms)^    if\(attack->attack_type >= 0 && attack->attack_type < max_attack_types\)'
                          r'\s*\{[^{}]+\}\s*else\s*\{[^{}]+\}', damage)[0]
        if slot := DEFENSE_SLOT.search(damage):
            store += '\n' + slot[0]
        pain = re.search(r'(?ms)^    else if\((!self->frozen && !self->modeldata.nopain && !attack->no_pain.*?)(?=\)\n    \{)',
                         damage)[1]
        defaults = re.search(r'(?ms)^const s_collision_attack emptyattack\s*=\s*\{.*?^\};', core)[0]
        checks = ',\n'.join('{%du,%d,%d}' % (row['revision'], row['native_maximum'], row['last_slot'])
                           for row in rows)
        removal_type = re.search(r'(?m)^\s*(attack\.attack_type\s*=[^;]+;)', removal)[1]
        values = dict(UNSUMMON=frame, REMOVAL_TYPE=removal_type, STORE=store, PAIN=pain,
                      DROP=function(core, 'checkdamagedrop'), DEFAULTS=defaults, CONTROLS=checks)
        template = Path(__file__).with_name('unsummon_frame_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda token: values[token[1]], template)
        self.assertEqual(native_output(code, data, engine_source=engine), f'PASS {len(rows)}\n')

    def test_6391_timeover_status_and_tick_order(self):
        data = load_contract_fixture(FIXTURE.with_name('profile-6391-timeover-boundaries.json'))
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_ATTACK_CALLBACKS_ENGINE', ROOT / 'src/engines' / '6391'))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        status = function(source, 'updatestatus')
        unload = function(source, 'unload_level')
        start = status.index('dt = timeleft / COUNTER_SPEED;')
        end = status.index('if(go_time > _time)', start)
        parts = {
            'METHODS': '\n'.join(function(source, name) for name in (
                'kill_all_players_by_timeover', 'no_player_alive_to_join', 'time_over')),
            'COUNTDOWN': status[start:end],
            'UNLOAD_TIMER_RESET': re.search(r'(?m)^    is_total_timeover\s*=\s*0;\s*$', unload)[0].strip(),
            'ROWS': ','.join('{%du,%d,%d,%d,%d,%d}' % (row['revision'], row['countdown'],
                             row['total_timeover'], row['selects_lose'], row['selects_fall_lose'], row['local_actor'])
                             for row in data['sources']),
        }
        template = Path(__file__).with_name('timeover_status_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda token: parts[token[1]], template)
        output = native_output(code, {'engine': '6391'}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_6391_player_status_reset_and_continue(self):
        data = load_contract_fixture(FIXTURE.with_name('profile-6391-player-status.json'))
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_ATTACK_CALLBACKS_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        assignments = []
        for name, count in (('updatestatus', 1), ('selectplayer', 5), ('playgame', 1)):
            resets = re.findall(r'if\(obor_profile_has_player_status\(\)\) player\[i\]\.status = PLAYER_NO_STATUS;',
                                function(source, name))
            self.assertEqual(len(resets), count, name)
            assignments.extend(resets)
        parts = {
            'METHOD': function(source, 'no_player_alive_to_join'),
            'RESETS': '\n'.join(f'case {index}: {statement} break;' for index, statement in enumerate(assignments)),
            'RESET_COUNT': str(len(assignments)),
            'ROWS': ',\n'.join('{%du,%d,%d}' % (row['revision'], row['resets'], row['losing_prevents_continue'])
                               for row in rows),
        }
        template = Path(__file__).with_name('player_status_runtime_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda token: parts[token[1]], template)
        output = native_output(code, data, engine_source=engine)
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def check_damage_recovery(self, engine_id):
        fixture = DAMAGE_FALL_DEATH_FIXTURE.with_name('profile-damage-recovery.json')
        data = load_contract_fixture(fixture)
        rows = [row for row in data['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][engine_id])))
        engine = Path(os.environ.get('OBOR_ATTACK_CALLBACKS_ENGINE', ROOT / 'src/engines' / engine_id))
        core = (engine / 'openbor.c').read_text(encoding='latin-1')
        native = function(core, 'common_takedamage')
        store = re.search(r'if\(attack->attack_type >= 0 && attack->attack_type < max_attack_types\)'
                          r'\s*\{[^{}]+\}\s*else\s*\{[^{}]+\}', native)[0]
        slot = DEFENSE_SLOT.search(native)
        start = slot.start() if slot else re.search(r'(?m)^    if\(self->drop \|\|', native).start()
        recovery = native[start:native.rindex('}')]
        parts = dict(STORE=store, RECOVERY=recovery,
                     FALL=function(core, 'set_fall'),
                     ROWS=',\n'.join('{%du,%d}' % (row['revision'], row['damage_record']) for row in rows))
        template = Path(__file__).with_name('damage_recovery_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda token: parts[token[1]], template)
        output = native_output(code, {'engine': engine_id}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_damage_recovery(self):
        self.check_damage_recovery('4432')

    def test_6391_damage_recovery(self):
        self.check_damage_recovery('6391')

    def test_6391_defeat_state_changes(self):
        data = load_contract_fixture(FIXTURE.with_name('profile-6391-defeat-transitions.json'))
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_ATTACK_CALLBACKS_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        parts = {
            'METHODS': '\n'.join(function(source, name) for name in ('set_death', 'set_fall')),
            'ROWS': ',\n'.join('{%du,%du,%du}' % (row['revision'], row['death_clears'], row['fall_clears'])
                               for row in rows),
        }
        template = Path(__file__).with_name('defeat_transitions_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda token: parts[token[1]], template)
        output = native_output(code, data, engine_source=engine)
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def check_damage_fall_death(self, engine_id):
        data = load_contract_fixture(DAMAGE_FALL_DEATH_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][engine_id])))
        data = data | {'engine': engine_id, 'sources': rows}
        engine = Path(os.environ.get('OBOR_ATTACK_CALLBACKS_ENGINE', ROOT / 'src/engines' / engine_id))
        code = damage_fall_death_program(data, engine)
        actual = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in actual.splitlines()], revisions)

    def test_4432_native_damage_fall_death(self):
        self.check_damage_fall_death('4432')

    def test_6391_native_damage_fall_death(self):
        self.check_damage_fall_death('6391')

    def check_combat_operands(self, engine_id):
        fixture = load_contract_fixture(OPERAND_FIXTURE)
        rows = [row for row in fixture['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(fixture, fixture['expected_revisions'][engine_id])))
        data = fixture | {'engine': engine_id, 'sources': rows}
        engine = Path(os.environ.get('OBOR_ATTACK_CALLBACKS_ENGINE', ROOT / 'src/engines' / engine_id))
        output = native_output(operand_program(data, engine), data, engine_source=engine)
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_native_combat_operands(self):
        self.check_combat_operands('4432')

    def test_6391_native_combat_operands(self):
        self.check_combat_operands('6391')

    def test_6391_record_callbacks_and_juggle_gate(self):
        data = load_contract_fixture(RECORD_FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_ATTACK_CALLBACKS_ENGINE', ROOT / 'src/engines' / data['engine']))
        core = (engine / 'openbor.c').read_text(encoding='latin-1')
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        names = ('execute_ondoattack_script', '_execute_didhit_script', 'execute_didhit_script',
                 'execute_takedamage_script', 'execute_didblock_script', 'diff', 'inair', 'kill_all_enemies')
        caller = function(core, 'do_attack')
        # Extract the enclosing decision, including the early continue.
        comparison = caller.index('if(attack->jugglecost > target->modeldata.jugglepoints.current)')
        condition = caller.rindex('        if(', 0, comparison)
        condition_end = caller.index('\n', condition)
        prior_line = caller[:condition].splitlines()[-1]
        declaration = prior_line + '\n' if 'juggle_on_fall' in prior_line else ''
        sweep_selectors = {'max_attack_types': 'SWEEP_CUSTOM_LIMIT', 'ATK_TIMEOVER': 'ATK_TIMEOVER',
                           'ATK_NORMAL': 'ATK_NORMAL'}
        values = {
            'METHODS': '\n'.join(function(core, name) for name in names),
            'VARIANTS': '\n'.join(function(variants, name) for name in
                                  ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType')),
            'JUGGLE': declaration + braced_statement(caller, caller[condition:condition_end]),
            'PROFILES': ','.join('{%du,%s,%d,%d,%s}' % (row['revision'], json.dumps(row['participant']),
                                                    row['timeover'], row['juggle_by_falling'],
                                                    sweep_selectors[row['enemy_clear_attack']])
                                 for row in rows),
        }
        template = Path(__file__).with_name('combat_record_callbacks_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, data, engine_source=engine)
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_native_callback_locals_cleanup_and_caller_arguments(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {r['revision'] for r in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_ATTACK_CALLBACKS_ENGINE', ROOT / 'src/engines' / data['engine']))
        actual = [json.loads(line) for line in native_output(program(data, engine), data, engine_source=engine).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], status='PASS') for r in data['sources']])


if __name__ == '__main__':
    unittest.main()
