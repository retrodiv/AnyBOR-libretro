"""Check native counter, repeated contact and follow-up decisions.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_early_jump_walkoff import braced_statement, continued_macro
from test_forward_attack_callbacks import source_calls
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-attack-rule-contracts.json'
TARGET_FIXTURE = FIXTURE.with_name('profile-attackone-boundaries.json')
STATE_FIXTURE = FIXTURE.with_name('profile-attack-state-transitions.json')
RECOVERY_FIXTURE = FIXTURE.with_name('profile-rise-pain-and-grab.json')
ID_RESET_FIXTURE = FIXTURE.with_name('profile-attack-id-resets.json')
GRAB_FINISH_FIXTURE = FIXTURE.with_name('profile-grab-finisher.json')
FOLLOW_ANIMATION_FIXTURE = FIXTURE.with_name('profile-follow-animation-storage.json')
WALK_DIRECTION_FIXTURE = FIXTURE.with_name('profile-walk-animation-direction.json')
GROUPS = ('counter', 'contact', 'follow')


def program(data, engine):
    source = (engine / 'openbor.c').read_text(encoding='latin1')
    commands = (engine / 'source/gamelib/commands.c').read_text(encoding='latin1')
    attack = function(source, 'do_attack')
    setter = function(source, 'ent_set_anim')
    counter_start = attack.index('            else if(self->animation->counterrange')
    flash = attack.index('                    if(!attack->no_flash)', counter_start)
    normal = re.search(r'(?m)^ {12}else if\([^{};]*self->takedamage\(e, attack\)\)', attack)
    follow = attack.index('            if((e->animation->followup.animation)')
    follow_end = attack.index('            self->hit_by_attack_id = current_attack_id;', follow)
    repeat = attack.index('            if(target->hit_by_attack_id == current_attack_id')
    registry = re.search(r'(?m)^(?:    if\([^\n]+\)\n    \{\n)?'
                         r'[ \t]*LIST_ADD\(CMD_MODEL_IGNOREATTACKID, "ignoreattackid"\);'
                         r'(?:\n    \})?', commands)
    command = source.index('case CMD_MODEL_IGNOREATTACKID:')
    helpers = ('counter_matches_hit', 'attack_follow_animation')
    parts = {
        'HELPERS': '\n'.join(function(source, name) for name in helpers if name in source),
        'ANIMATION_GATE': setter[setter.index('{') + 1:setter.index('    ani = ')],
        'COUNTER_BODY': attack[counter_start:flash],
        'NORMAL_ROUTE': normal[0],
        'FOLLOW_BODY': attack[follow:follow_end],
        'REPEAT_GATE': attack[repeat:attack.index('{', repeat)],
        'REGISTRY': registry[0],
        'COMMAND': source[command:source.index('case CMD_MODEL_', command + 5)],
        'PROFILES': ','.join(str(row['revision']) for row in data['sources']),
    }
    for name in GROUPS:
        parts[name.upper()] = ',\n'.join(
            '{' + ','.join(map(str, row['input'])) + '}' for row in data['cases'][name])
    template = Path(__file__).with_name('attack_rule_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda token: parts[token[1]], template)


def attackone_program(data, engine):
    source = (engine / 'openbor.c').read_text(encoding='latin-1')
    attack = function(source, 'do_attack')
    loader = function(source, 'load_cached_model')
    default = re.search(r'(?m)^\s*(newanim->attackone\s*=\s*-?\d+;)', loader)
    directive = re.search(r'(?m)^\s*case CMD_MODEL_COLLISIONONE:\s*(newanim->attackone[^;]+;)', loader)
    target = re.search(r'(?m)^\s*(if\(current_anim->attackone[^\n]+)', attack)[1]
    repeat = re.search(r'if\((?:target->hit_by_attack_id == current_attack_id|obor_attack_seen\()'
                       r'[^{}]+(?=\n\s*\{)', attack)[0].rstrip()
    follows = re.findall(r'(?m)^\s*(if\([^\n]*\[current_follow_id\]->attackone[^\n]*)', attack)
    if len(follows) != 2:
        raise ValueError('Native counter and follow attackone decisions required')
    busy_anchor = attack.index('(!self->idling &&')
    busy_comment = attack.index("// Can't block if busy", busy_anchor)
    busy = attack[busy_anchor:busy_comment].rstrip().removesuffix('&&').rstrip()
    if not busy.endswith('))'):
        raise ValueError('Expected final native passive-block disqualifier')
    remember = re.findall(r'(?m)^\s*((?:obor_remember_attack\(self, current_attack_id\)|'
                          r'self->hit_by_attack_id = current_attack_id);)', attack)
    if len(remember) != 2:
        raise ValueError('Native counter and ordinary hit tracking writes required')
    setup = re.search(r'(?m)^\s*current_attack_id = e->attack_id\w*;', attack).start()
    values = {
        'DEFAULT': default[1],
        'DIRECTIVE': directive[1],
        'TARGET': braced_statement(attack, target),
        'COUNTER': braced_statement(attack, follows[0]),
        'FOLLOW': braced_statement(attack, follows[1]),
        'REPEAT': braced_statement(attack, repeat),
        'BUSY': busy[:-1],
        'COUNTER_WRITE': remember[0],
        'HIT_WRITE': remember[1],
        'ID_SETUP': attack[setup:attack.index('    current_anim = e->animation;', setup)],
        'HELPERS': '\n'.join(function(source, name) for name in
                             ('obor_attack_seen', 'obor_remember_attack')
                             if name in source),
        'PROFILES': ','.join('{%du,%d,%d}' % (row['revision'], row['default'], row['boolean'])
                             for row in data['sources']),
    }
    template = Path(__file__).with_name('attackone_boundaries_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda token: values[token[1]], template)


def attack_state_program(data, engine):
    source = (engine / 'openbor.c').read_text(encoding='latin-1')
    methods = ('set_idle', 'set_death', 'set_fall', 'recheck_nextattack',
               'common_try_normalattack', 'common_try_block', 'common_attack_proc', 'diff')
    run = function(source, 'common_try_runattack')
    jump = function(source, 'common_try_jumpattack')
    blocked_target = r'if\((!target->animation->vulnerable[^\n]+)\)'
    run_test = re.search(blocked_target, run)[1]
    jump_tests = re.findall(blocked_target, jump)
    if len(jump_tests) != 2:
        raise ValueError('Both original jump target predicates required')
    lookup = function(source, 'block_find_target')
    busy = re.search(r'!attacker->dead\s*(?://[^\n]+)?\s*&&\s*attacker->attacking[^\n]*', lookup)[0]
    wander = function(source, 'common_try_wander')
    behind = re.search(r'if\(behind && target->attacking[^\n]*\)', wander)[0]
    distance = re.search(r'(?m)^\s*(mindx = \(!behind && target->attacking[^\n]+;)', wander)[1]
    model = function(source, 'ent_set_model')
    reset = re.search(r'(?m)^\s*(ent->attacking = (?:0|ATTACKING_INACTIVE);)', model)[1]
    parts = {
        'METHODS': '\n'.join(function(source, name) for name in methods),
        'RUN_TARGET': run_test,
        'JUMP_TARGET_FIRST': jump_tests[0],
        'JUMP_TARGET_SECOND': jump_tests[1],
        'BLOCK_ELIGIBLE': re.sub(r'//[^\n]*', '', busy),
        'WANDER_BEHIND': braced_statement(wander, behind),
        'WANDER_DISTANCE': distance,
        'MODEL_RESET': reset,
        'PROFILES': ','.join('{%du,%d,%d}' % (row['revision'], row['keep_recovery'], row['prepared_attack'])
                             for row in data['sources']),
    }
    template = Path(__file__).with_name('attack_state_transitions_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda token: parts[token[1]], template)


def recovery_program(data, engine):
    source = (engine / 'openbor.c').read_text(encoding='latin-1')
    jump = function(source, 'common_jump')
    grab = function(source, 'dograb')
    jump_start = jump.index('        self->jumping = 0;')
    grab_start = grab.index('        target->attacking = ')
    writes = []
    for name, count in (('common_grab_check', 1), ('common_grab', 1), ('dograb', 1),
                        ('common_grabattack', 2), ('player_grab_check', 2), ('drop_all_enemies', 1)):
        selected = re.findall(r'(?m)^\s*((?:self|attacker|ent_list\[i\])->attacking\s*=[^;\n]+;)',
                              function(source, name))
        if len(selected) != count:
            raise ValueError('Original grab attack-state assignments required in ' + name)
        writes.extend(selected)
    ai_grab = function(source, 'ai_check_grab')
    player_grab = function(source, 'player_grab_check')
    loader = function(source, 'load_cached_model')
    grab_directive = re.search(r'case CMD_MODEL_GRABIN:[\s\S]*?\bbreak;', loader)[0]
    grab_geometry = ['diff', 'adjust_grabposition']
    if 'static int obor_lns_adjust_grabposition(' in source:
        grab_geometry.insert(1, 'obor_lns_adjust_grabposition')
    recovery_fields = (
        'revision', 'front_only', 'has_rising', 'has_riseattacking', 'rise_clears_backpain',
        'riseattack_clears_pain', 'riseattack_clears_edge', 'riseattack_clears_ducking',
        'pain_clears_rising', 'grabbed_pain_clears_rising', 'pain_clears_riseattacking',
        'pain_clears_edge', 'pain_clears_ducking', 'landing_clears_edge', 'landing_clears_ducking',
        'grab_clears_backpain', 'grab_clears_edge', 'grab_clears_ducking',
    )
    parts = {
        'METHODS': '\n'.join(function(source, name) for name in ('set_rise', 'set_riseattack', 'set_pain')),
        'PAIN_FLAGS': continued_macro(source, 'painflags') if data['engine'] == '4432' else '',
        'LANDING': jump[jump_start:jump.index('        if(!self->modeldata.runhold)', jump_start)],
        'GRAB': grab[grab_start:grab.index('        /* Stop all movement. */', grab_start)],
        'GRAB_WRITES': '\n'.join(f'case {index}: {statement} break;' for index, statement in enumerate(writes)),
        'AI_GRAB_TEST': re.search(r'if\((self->grabbing && [^\n]+)\)', ai_grab)[1],
        'PLAYER_GRAB_TEST': re.search(r'(?m)^\s*if\((self->attacking[^\n]*)\)', player_grab)[1],
        'GRAB_DIRECTIVE': grab_directive,
        'GRAB_GEOMETRY': '\n'.join(function(source, name) for name in grab_geometry),
        'CHECK_GRAB': function(source, 'checkgrab'),
        'PROFILES': ',\n'.join('{' + ', '.join(f'.{field} = {row[field]}' for field in recovery_fields) + '}'
                               for row in data['sources']),
    }
    template = Path(__file__).with_name('rise_pain_and_grab_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda token: parts[token[1]], template)


def attack_id_reset_program(data, engine):
    source = (engine / 'openbor.c').read_text(encoding='latin-1')
    names = ('check_attack', 'biker_move')
    if data['engine'] == '4432':
        landing = 'obor_apply_pending_landing_damage'
    else:
        landing = 'checkdamageonlanding'
        names = ('is_frozen',) + names
    calls = source_calls(function(source, landing), ('execute_ondoattack_script',))
    if len(calls) != 2:
        raise ValueError('Both original landing exchange callbacks are required')
    values = {
        'METHODS': '\n'.join(function(source, name) for name in names),
        'LANDING_CALLS': '\n'.join(call['text'] + ';' for call in calls),
        'ROWS': ','.join('{%du,%d}' % (row['revision'], row['record']) for row in data['sources']),
    }
    template = Path(__file__).with_name('attack_id_reset_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda token: values[token[1]], template)


def grab_finish_program(rows, engine_id, engine):
    source = (engine / 'openbor.c').read_text(encoding='latin-1')
    methods = ('dograbattack', 'doprethrow', 'dothrow', 'common_throw_wait', 'common_prethrow')
    defaults = [re.search(r'(?ms)^int[ \t]+grab_attacks\[5\]\[2\]\s*=\s*\{.*?^\};', source)[0]]
    if engine_id == '6391':
        methods = ('do_grab_attack_finish',) + methods
        defaults.append(re.search(r'(?ms)^const s_collision_attack emptyattack\s*=\s*\{.*?^\};', source)[0])
    values = {
        'DEFAULTS': '\n'.join(defaults),
        'METHODS': '\n'.join(function(source, name) for name in methods),
        'PROFILES': ','.join('{%du,%d}' % (row['revision'], row['active_state']) for row in rows),
    }
    template = Path(__file__).with_name('grab_finisher_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda token: values[token[1]], template)


class HistoricalAttackRuleTests(unittest.TestCase):
    def check_walk_animation_direction(self, physical):
        data = load_contract_fixture(WALK_DIRECTION_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == physical]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][physical])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / physical))
        core = (engine / 'openbor.c').read_text(encoding='latin-1')
        script = (engine / 'openborscript.c').read_text(encoding='latin-1')
        walk = function(core, 'adjust_walk_animation')
        update = function(core, 'update_animation')
        legacy_get = function(script, 'openbor_getentityproperty')
        legacy_set = function(script, 'openbor_changeentityproperty')
        reads = re.findall(r'\(\*pretvar\)->lVal\s*=\s*\(LONG\)ent->animating;', legacy_get)
        self.assertEqual(len(reads), 2)
        values = {
            'WALK_DIRECTION': walk[walk.index('    if(((self->direction == DIRECTION_RIGHT'):walk.rindex('}')],
            'NEXT_FRAME': re.search(r'\bf\s*=\s*self->animpos\s*\+\s*self->animating;', update)[0],
            'LEGACY_READ': reads[0],
            'LEGACY_WRITE': re.search(r'\bent->animating\s*=[^;]+;', legacy_set)[0],
            'INTEGER_VALUE': '',
            'TYPED_READ_CASES': '',
            'TYPED_WRITE_CASES': '',
            'ROWS': ',\n'.join(f"{{{row['revision']}u, {int(row['boolean_direction'])}}}"
                              for row in rows),
        }
        if physical != '4432':
            typed = (engine / 'source/openborscript/entity.c').read_text(encoding='latin-1')
            variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
            _, getters = switch_cases(typed, 'openbor_get_entity_property', 'property')
            _, setters = switch_cases(typed, 'openbor_set_entity_property', 'property')
            properties = ('_ENTITY_ANIMATION_ANIMATING', '_ENTITY_ARROW_ON')
            values.update({
                'INTEGER_VALUE': function(variants, 'ScriptVariant_IntegerValue'),
                'TYPED_READ_CASES': '\n'.join(
                    f'case {prop}:\n' + re.search(r'\(\*pretvar\)->lVal\s*=[^;]+;', getters[prop]['body'])[0] +
                    '\n    break;' for prop in properties),
                'TYPED_WRITE_CASES': '\n'.join(f'case {prop}:' + setters[prop]['body']
                                              for prop in properties),
            })
        template = Path(__file__).with_name('walk_animation_direction_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda token: values[token[1]], template)
        output = native_output(code, {'engine': physical}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_walk_animation_direction(self):
        self.check_walk_animation_direction('4432')

    def test_6391_walk_animation_direction(self):
        self.check_walk_animation_direction('6391')

    def check_follow_animation_storage(self, physical):
        data = load_contract_fixture(FOLLOW_ANIMATION_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == physical]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][physical])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / physical))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        load = function(source, 'load_cached_model')
        start = load.index('case CMD_MODEL_FOLLOWANIM:')
        end = load.index('case CMD_MODEL_FOLLOWCOND:', start)
        callers = re.findall(r'current_follow_id\s*=\s*attack_follow_animation\((self|e)\);',
                             function(source, 'do_attack'))
        self.assertEqual(callers, ['self', 'e'])
        values = {
            'DIRECTIVE': load[start:end],
            'HELPERS': '\n'.join(function(source, name) for name in
                                 ('isNumeric', 'getValidInt', 'attack_follow_animation')),
            'ROWS': ','.join('{%du,%d}' % (row['revision'], row['negative_selection']) for row in rows),
        }
        template = Path(__file__).with_name('follow_animation_storage_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda token: values[token[1]], template)
        output = native_output(code, {'engine': physical}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_follow_animation_storage(self):
        self.check_follow_animation_storage('4432')

    def test_6391_follow_animation_storage(self):
        self.check_follow_animation_storage('6391')

    def check_grab_finish(self, engine_id):
        data = load_contract_fixture(GRAB_FINISH_FIXTURE) | {'engine': engine_id}
        rows = [row for row in data['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][engine_id])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / engine_id))
        output = native_output(grab_finish_program(rows, engine_id, engine), data, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_grab_finish_and_throw(self):
        self.check_grab_finish('4432')

    def test_6391_grab_finish_and_throw(self):
        self.check_grab_finish('6391')

    def check_attack_id_resets(self, engine_id):
        fixture = load_contract_fixture(ID_RESET_FIXTURE)
        rows = [row for row in fixture['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(fixture, fixture['expected_revisions'][engine_id])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / engine_id))
        data = fixture | {'engine': engine_id, 'sources': rows}
        output = native_output(attack_id_reset_program(data, engine), data, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_native_attack_id_resets(self):
        self.check_attack_id_resets('4432')

    def test_6391_native_attack_id_resets(self):
        self.check_attack_id_resets('6391')

    def check_recovery_program(self, engine_id):
        fixture = load_contract_fixture(RECOVERY_FIXTURE)
        required = contract_revisions(fixture, fixture['expected_revisions'][engine_id])
        rows = [row for row in fixture['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(required))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / engine_id))
        data = fixture | {'engine': engine_id, 'sources': rows}
        output = native_output(recovery_program(data, engine), data, engine_source=engine)
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_native_rise_pain_and_grab(self):
        self.check_recovery_program('4432')

    def test_6391_native_rise_pain_and_grab(self):
        self.check_recovery_program('6391')

    def check_attack_state_transitions(self, engine_id):
        fixture = load_contract_fixture(STATE_FIXTURE)
        required = contract_revisions(fixture, fixture['expected_revisions'][engine_id])
        rows = [row for row in fixture['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(required))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / engine_id))
        data = fixture | {'engine': engine_id, 'sources': rows}
        output = native_output(attack_state_program(data, engine), data, engine_source=engine)
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_native_attack_state_transitions(self):
        self.check_attack_state_transitions('4432')

    def test_6391_native_attack_state_transitions(self):
        self.check_attack_state_transitions('6391')

    def check_attackone_boundaries(self, engine_id):
        data = load_contract_fixture(TARGET_FIXTURE)
        required = contract_revisions(data, data['expected_revisions'][engine_id])
        rows = [row for row in data['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(required))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / engine_id))
        context = data | {'engine': engine_id, 'sources': rows}
        actual = native_output(attackone_program(context, engine), context, engine_source=engine)
        self.assertEqual([int(line) for line in actual.splitlines()], revisions)

    def test_4432_native_attackone_boundaries(self):
        self.check_attackone_boundaries('4432')

    def test_6391_native_attackone_boundaries(self):
        self.check_attackone_boundaries('6391')

    def test_native_counter_contact_and_follow(self):
        data = load_contract_fixture(FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        actual = [json.loads(line) for line in native_output(program(data, engine), data).splitlines()]
        self.assertEqual(len(actual), len(rows))
        for row, (revision, observed) in zip(rows, actual, strict=True):
            self.assertEqual(revision, row['revision'])
            expected = data['contracts'][row['contract']]
            for name, cases in zip(GROUPS, observed, strict=True):
                for scenario, got, want in zip(data['cases'][name], cases, expected[name], strict=True):
                    with self.subTest(revision=revision, scenario=scenario['name']):
                        self.assertEqual(got, want)


if __name__ == '__main__':
    unittest.main()
