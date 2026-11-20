"""Check landing damage eligibility through the native gravity caller.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_revisions, load_contract_fixture
from test_early_jump_walkoff import braced_statement
from test_historical_common_think import ROOT, native_output
from test_historical_entity_namespace import entity_namespace
from test_historical_model_defaults import model_command_functions
from test_historical_script_collision_coordinates import attack_property_mapping, coordinate_dispatch
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'modern-landing-damage-contracts.json'
SETTLED_FIXTURE = FIXTURE.with_name('profile-4432-settled-landing-damage.json')
FIELDS_FIXTURE = FIXTURE.with_name('profile-4432-throw-landing-fields.json')
DEFERRED_FIXTURE = FIXTURE.with_name('profile-4432-deferred-landing.json')
FORCE_QUERY_FIXTURE = FIXTURE.with_name('profile-4432-attack-landing-force.json')
BACKPAIN_FIXTURE = FIXTURE.with_name('profile-4432-backpain-velocity.json')
LANDING_STORAGE_FIXTURE = FIXTURE.with_name('profile-landing-attack-storage.json')
LANDING_FRAME_FIXTURE = FIXTURE.with_name('profile-landing-frame-callbacks.json')
JUMP_FRAME_FIXTURE = FIXTURE.with_name('profile-jump-frame-record.json')
JUMP_STEAM_FIXTURE = FIXTURE.with_name('profile-jump-steam.json')
GRAVITY_DROP_FIXTURE = FIXTURE.with_name('profile-gravity-drop-effects.json')
EDGE_FIXTURE = FIXTURE.with_name('profile-6391-edge-animations.json')


def program(data):
    engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
    parts = dict(FUNCTION=function((engine / 'openbor.c').read_text(), 'check_gravity'),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    rows = []
    for row in data['cases']:
        values = [str(v) for v in row]
        if any(re.fullmatch(r'-?[0-9]+|[A-Z][A-Z0-9_]*', v) is None for v in values):
            raise ValueError('Literal or source constant required')
        rows.append('{' + ','.join(values) + '}')
    parts['CASES'] = ','.join(rows)
    code = Path(__file__).with_name('modern_landing_damage_contract.c.in').read_text()
    for key, value in parts.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved landing damage input')
    return code


class ModernLandingDamageContracts(unittest.TestCase):
    def check_jump_frame_record(self, physical):
        data = load_contract_fixture(JUMP_FRAME_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == physical]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][physical])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / physical))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        loader, cases = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        update = function(source, 'update_frame')
        methods = ('isNumeric', 'getValidInt', 'getValidFloat')
        if physical == '4432':
            defaults = re.findall(r'(?m)^\s*(newanim->jumpframe\.(?:frame\s*=\s*-1|velocity\.y\s*=\s*0);)', loader)
            self.assertEqual(len(defaults), 2)
            jump = braced_statement(update, 'if(anim->jumpframe.frame == f)')
            release = ''
        else:
            defaults = re.findall(r'(?m)^\s*(newanim->jumpframe\s*=\s*NULL;)', loader)
            self.assertEqual(len(defaults), 1)
            methods += ('check_jumpframe',)
            if 'obor_reset_jumpframe(' in source:
                methods += ('obor_reset_jumpframe',)
            jump, = re.findall(r'(?m)^\s*(check_jumpframe\(self, f\);)', update)
            release = braced_statement(function(source, 'free_anim'), 'if(anim->jumpframe)')
        sound = braced_statement(update, 'if(anim->soundtoplay && anim->soundtoplay[f] >= 0)')
        self.assertLess(update.index(sound), update.index(jump))
        self.assertLess(update.index(jump), update.index('if(anim->projectile.throwframe == f)'))
        names = ('DIVE', 'DIVE1', 'DIVE2', 'JUMPFRAME')
        values = {
            'DEFAULTS': '\n'.join(defaults),
            'DIRECTIVES': '\n'.join(f"case {name}: {cases['CMD_MODEL_' + name]['body']}" for name in names),
            'METHODS': '\n'.join(function(source, name) for name in methods),
            'FRAME_SIGNATURE': update[:update.index('{')],
            'FRAME_GUARD': braced_statement(update, 'if(!anim || anim->numframes <= 0'),
            'FRAME_WRITE': re.search(r'(?m)^\s*(self->animpos = f;)', update)[1],
            'FRAME_SOUND': sound, 'FRAME_JUMP': jump, 'RELEASE': release,
            'ROWS': ','.join('{%du,%d}' % (row['revision'], row['reason']) for row in rows),
        }
        template = Path(__file__).with_name('jump_frame_record_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, {'engine': physical}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_jump_frame_record(self):
        self.check_jump_frame_record('4432')

    def test_6391_jump_frame_record(self):
        self.check_jump_frame_record('6391')

    def check_jump_steam(self, physical):
        data = load_contract_fixture(JUMP_STEAM_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == physical]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][physical])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / physical))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        values = {
            'JUMP': function(source, 'dojump'),
            'AI_ACCEPTED': braced_statement(function(source, 'common_try_jumpattack'), 'if(rnum >= 0)'),
            'STEAM': function(source, 'steam_spawn'),
            'ROWS': ','.join('{%du,%d,%d}' % (row['revision'], row['dust'], row['steam']) for row in rows),
        }
        template = Path(__file__).with_name('jump_steam_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, {'engine': physical}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_jump_steam(self):
        self.check_jump_steam('4432')

    def test_6391_jump_steam(self):
        self.check_jump_steam('6391')

    def check_gravity_drop_effects(self, physical):
        data = load_contract_fixture(GRAVITY_DROP_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == physical]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][physical])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / physical))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        gravity = function(source, 'check_gravity')
        _, loader_cases = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        drop = braced_statement(gravity, 'if(self->animation->dropframe)')
        movement = braced_statement(gravity, 'if (self->velocity.y)')
        dust = braced_statement(gravity, 'if(self->modeldata.dust.fall_land >= 0')
        end = gravity.index(dust)
        begin = gravity.rindex('self->position.y = self->base;', 0, end)
        self.assertLess(gravity.index(drop), gravity.index(movement))
        values = {'DROP': drop, 'MOVE': movement, 'LAND': gravity[begin:end] + dust,
                  'DROPFRAME_CASE': loader_cases['CMD_MODEL_DROPFRAME']['body'],
                  'NUMBERS': '\n'.join(function(source, name) for name in ('isNumeric', 'getValidInt')),
                  'ROWS': ','.join('{%du,%d}' % (row['revision'], row['reason']) for row in rows)}
        template = Path(__file__).with_name('gravity_drop_effects_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, {'engine': physical}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_gravity_drop_effects(self):
        self.check_gravity_drop_effects('4432')

    def test_6391_gravity_drop_effects(self):
        self.check_gravity_drop_effects('6391')

    def test_6391_edge_animations(self):
        data = load_contract_fixture(EDGE_FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        code = (engine / 'openbor.c').read_text(encoding='latin-1')
        commands = (engine / 'source/openborscript/commands.c').read_text()
        utility = (engine / 'source/utils.c').read_text()
        _, cases = switch_cases(code, 'load_cached_model', 'cmd', outermost=True)
        translate = function(code, 'translate_ani_id')
        gravity = function(code, 'check_gravity')
        edge_start = gravity.index('    adjust_base(self, &plat);') + len('    adjust_base(self, &plat);')
        values = {
            'GRAVITY': gravity[edge_start:gravity.index('    if(!is_frozen(self)', edge_start)],
            'ANIMATION_DEFAULT': re.search(r'\bint ani_id = -?\d+(?=[,;])', translate)[0] + ';',
            'ANIMATION_NAMES': translate[translate.index('    else if(stricmp(value, "walkoff")'):translate.rindex('}')],
            'DEFAULTS': '\n'.join(re.findall(r'(?m)^\s*(newchar->edgerange\.[xz]\s*=\s*[^;]+;)',
                                             function(code, 'init_model'))),
            'DIRECTIVE': cases['CMD_MODEL_EDGERANGE']['body'],
            'METHODS': '\n'.join(function(code, name) for name in
                                 ('isNumeric', 'getValidFloat', 'check_edge', 'is_walking',
                                  'common_anim_series', 'common_idle_anim')),
            'COMMANDS': model_command_functions(commands, utility),
            'ROWS': ','.join('{%du,%d}' % (row['revision'], row['has_edge']) for row in rows),
        }
        template = Path(__file__).with_name('edge_animation_contract.c.in').read_text()
        generated = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        actual = native_output(generated, data, engine_source=engine)
        self.assertEqual([int(line) for line in actual.splitlines()], revisions)

    def test_6391_back_animation_names(self):
        data = load_contract_fixture(EDGE_FIXTURE.with_name('profile-6391-back-animation-names.json'))
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        translator = function(source, 'translate_ani_id')
        slots = sorted(set(re.findall(r'\b(anim[a-z]+)\[', translator)))
        self.assertLessEqual(set(data['dynamic_id_bases']), set(slots))
        setups = [
            f'        {name}[i] = {base} + obor_attack_to_native(i);'
            for name, base in data['dynamic_id_bases'].items()
        ]
        cases = []
        for row in rows:
            for query, animation, bounce in row['cases']:
                self.assertRegex(str(animation), r'^(?:ANI_[A-Z0-9]+|-?\d+)$')
                cases.append('    {%du, %s, %s, %d}' %
                             (row['revision'], json.dumps(query), animation, bounce))
        values = {'TRANSLATOR': function(source, 'obor_profile_has_classic_boomerang') + translator,
                  'CASES': ',\n'.join(cases),
                  'TABLES': '\n'.join(f'static int {name}[SERIES_SLOTS];' for name in slots),
                  'DYNAMIC_IDS': '\n'.join(setups)}
        template = Path(__file__).with_name('back_animation_names_contract.c.in').read_text()
        generated = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        actual = native_output(generated, data, engine_source=engine)
        self.assertEqual(actual, 'PASS %d\n' % len(cases))

    def check_landing_frame_callbacks(self, physical):
        data = load_contract_fixture(LANDING_FRAME_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == physical]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][physical])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / physical))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        loader, cases = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        gravity = function(source, 'check_gravity')
        update = function(source, 'update_frame')
        legacy = physical == '4432'
        fields = ('jumpframe', 'landframe')
        defaults = [re.search(r'(?m)^\s*(newanim->' + name + r'(?:\.frame)?\s*=\s*(?:-1|NULL);)',
                              loader)[1] for name in fields]
        values = {
            'DEFAULTS': '\n    '.join(defaults),
            'DIRECTIVE': cases['CMD_MODEL_LANDFRAME']['body'],
            'GRAVITY': braced_statement(gravity, 'if(self->animation->landframe.frame >= 0') if legacy else
                       re.search(r'(?m)^\s*(check_landframe\(self\);)', gravity)[1],
            'FRAME_SIGNATURE': update[:update.index('{')],
            'FRAME_GUARD': braced_statement(update, 'if(!anim || anim->numframes <= 0'),
            'FRAME_WRITE': re.search(r'(?m)^\s*(self->animpos = f;)', update)[1],
            'FRAME_SOUND': braced_statement(update, 'if(anim->soundtoplay && anim->soundtoplay[f] >= 0)'),
            'METHODS': '\n'.join(function(source, name) for name in
                                 ('isNumeric', 'getValidInt', 'ent_set_anim', 'common_jump') +
                                 (() if legacy else ('check_bind_override', 'check_landframe'))),
            'RELEASE': '' if legacy else '\n'.join(braced_statement(function(source, 'free_anim'),
                                                                  f'if(anim->{name})') for name in fields),
            'ROWS': ','.join('{%du,%d}' % (row['revision'], row['tag_dust']) for row in rows),
        }
        template = Path(__file__).with_name('landing_frame_callbacks_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, {'engine': physical}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_landing_frame_callbacks(self):
        self.check_landing_frame_callbacks('4432')

    def test_6391_landing_frame_callbacks(self):
        self.check_landing_frame_callbacks('6391')

    def check_landing_attack_storage(self, physical):
        data = load_contract_fixture(LANDING_STORAGE_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == physical]
        self.assertEqual([row['revision'] for row in rows], data['expected_revisions'][physical])
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / physical))
        old_layout = physical == '4432'
        modules = engine / ('source/gamelib' if old_layout else 'source/openborscript')
        script = (engine / 'openborscript.c' if old_layout else modules / 'collision_attack.c').read_text()
        core = (engine / 'openbor.c').read_text(encoding='latin-1')
        commands = (modules / 'commands.c').read_text()
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        utility = (engine / 'source/utils.c').read_text()
        _, cases = switch_cases(core, 'load_cached_model', 'cmd', outermost=True)
        methods = ('openbor_get_attack_property', 'openbor_set_attack_property')
        props = (
            'ATTACK_PROP_DAMAGE_LAND_FORCE', 'ATTACK_PROP_DAMAGE_LAND_MODE',
            'ATTACK_PROP_DAMAGE_LETHAL_DISABLE', 'ATTACK_PROP_DAMAGE_STEAL',
            'ATTACK_PROP_EFFECT_HIT_FLASH_DISABLE', 'ATTACK_PROP_REACTION_PAIN_SKIP',
        )
        model_cases = ('CMD_MODEL_DAMAGEONLANDING',) + tuple(
            prop.replace('ATTACK_PROP_', 'CMD_MODEL_COLLISION_', 1) for prop in props)
        parser = 'obor_landing_damage_type' if old_layout else 'translate_attack_type'
        first = 'typedef struct' if old_layout else '#define STRCACHE_INC'
        values = {
            'CACHE': variants[variants.index(first):variants.index('BOOL ScriptVariant_IsTrue(')],
            'SCRIPT': attack_property_mapping(script) + '\n' + '\n'.join(
                coordinate_dispatch(script, method, props) for method in methods),
            'COMMANDS': model_command_functions(commands, utility),
            'NUMBERS': '\n'.join(function(core, name) for name in ('isNumeric', 'getValidInt', parser)),
            'DEFAULT': re.search(r'(?ms)^const s_collision_attack emptyattack\s*=\s*\{.*?^\};', core)[0],
            'MODEL_CASES': ''.join('case ' + name + ':' + cases[name]['body'] for name in model_cases),
            'COPY_PENDING': re.search(r'(?m)^            self->damage_on_landing(?:\.attack_force)? = attack->[^;]+;\n'
                                      r'            self->damage_on_landing(?:\.attack_type|_type) = attack->[^;]+;',
                                      function(core, 'common_takedamage'))[0],
            'RESET_PENDING': re.search(r'(?m)^    self->damage_on_landing(?:\.attack_force)? = [^;]+;\n'
                                       r'    self->damage_on_landing(?:\.attack_type|_type) = [^;]+;',
                                       function(core, 'doland'))[0],
            'ROWS': ','.join('{%du,%d,%d,%d}' % (row['revision'], row['force'], row['mode'], row['lose_type'])
                             for row in rows),
        }
        template = Path(__file__).with_name('landing_attack_storage_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        result = native_output(code, {'engine': physical}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in result.splitlines()], [row['revision'] for row in rows])

    def test_4432_landing_attack_storage(self):
        self.check_landing_attack_storage('4432')

    def test_6391_landing_attack_storage(self):
        self.check_landing_attack_storage('6391')

    def check_landing_didhit(self, physical):
        fixture = LANDING_STORAGE_FIXTURE.with_name('profile-impact-callbacks.json')
        data = load_contract_fixture(fixture)
        rows = [row for row in data['sources'] if row['engine'] == physical]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][physical])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / physical))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        methods = ('obor_landing_damage_source', 'obor_apply_pending_landing_damage',
                   'obor_check_deferred_landing') if physical == '4432' else ('checkdamageonlanding',)
        damage_state = [
            re.search(r'\bset_' + action + r'\(self, self->(?:damagetype|last_damage_type), 0\);',
                      function(source, caller))[0]
            for caller, action in (('common_try_riseattack', 'riseattack'),
                                   ('common_lie', 'death'), ('common_lie', 'rise'))
        ]
        values = dict(METHODS='\n'.join(function(source, name) for name in ('diff', *methods)),
                      DEFAULT=re.search(r'(?ms)^const s_collision_attack emptyattack\s*=\s*\{.*?^\};', source)[0],
                      DAMAGE_STATE='\n'.join(damage_state),
                      ROWS=',\n'.join('{%du,%d}' % (row['revision'], row['landing_record']) for row in rows))
        template = Path(__file__).with_name('landing_didhit_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, {'engine': physical}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_landing_didhit(self):
        self.check_landing_didhit('4432')

    def test_6391_landing_didhit(self):
        self.check_landing_didhit('6391')

    def test_4432_backpain_velocity_precision(self):
        data = load_contract_fixture(BACKPAIN_FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        parts = {
            'FUNCTION': function((engine / 'openbor.c').read_text(), 'reset_backpain'),
            'REVISIONS': ','.join(str(int(revision)) + 'u' for revision in revisions),
            'CASES': ','.join('{%d,%d,%sf}' % (current, flip, float(velocity).hex())
                              for current, flip, velocity in data['cases']),
        }
        template = Path(__file__).with_name('backpain_velocity_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)
        raw = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',), libraries=('m',))
        actual = []
        for line in raw.splitlines():
            revision, result, direction, velocity, negative = line.split()
            actual.append([int(revision), int(result), int(direction),
                           float.fromhex(velocity), int(negative)])
        expected = [[row['revision'], *observation] for row in rows
                    for observation in data['contracts'][row['operation']]]
        self.assertEqual(actual, expected)

    def test_4432_attack_landing_force_query(self):
        data = load_contract_fixture(FORCE_QUERY_FIXTURE)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        self.assertTrue(set(data['boundary_controls']) <= set(revisions))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openborscript.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        parts = {
            'CACHE': variant[variant.index('typedef struct'):variant.index('// find an existing constant')],
            'GETTER': function(source, 'obor_script_collision_coordinates') +
                      attack_property_mapping(source) + '\n' +
                      function(source, 'openbor_get_attack_property'),
            'ROWS': ','.join('{%du,%d}' % (row['revision'], row['force_selector']) for row in rows),
        }
        template = Path(__file__).with_name('attack_landing_force_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: parts[match[1]], template)
        output = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_health_cheat_type_and_native_landing_gates(self):
        data = load_contract_fixture(FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        expected = dict(status='PASS', profiles=[dict(revision=row['revision'],
            cases=data['contracts'][row['contract']]) for row in data['sources']])
        self.assertEqual(json.loads(native_output(program(data), data)), expected)

    def test_4432_landing_damage_source_and_settling(self):
        data = load_contract_fixture(SETTLED_FIXTURE)
        rows = data['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        gravity = function(source, 'check_gravity')
        damage = function(source, 'common_takedamage')
        profile_rules = re.search(r'(?m)^    const int opponent_landing[^\n]+\n'
                                  r'    const int live_opponent_landing[^\n]+\n'
                                  r'    const int settled_landing[^\n]+', gravity)[0]
        sections = {
            'GRAVITY': profile_rules + '\n' + braced_statement(
                gravity, 'if(self->damage_on_landing > 0 && !self->dead &&'),
            'CONTINUATION': braced_statement(damage, 'if(self->damage_on_landing)'),
            'FALL': braced_statement(damage, re.search(
                r'if\(obor_profile_build >= 4642[^\n]+&& attack->obor_landing_hit\)', damage)[0]),
            'REVISIONS': ','.join(str(row['revision']) for row in rows),
            'CASES': ',\n'.join('{' + ','.join(str(int(n)) for n in case) + '}' for case in data['cases']),
        }
        code = Path(__file__).with_name('settled_landing_damage_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: sections[match[1]], code)
        actual = [json.loads(line) for line in native_output(
            code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',)).splitlines()]
        expected = [[row['revision'], *case] for row in rows for case in data['contracts'][row['contract']]]
        self.assertEqual(len(actual), len(expected))
        for expect, result in zip(expected, actual):
            with self.subTest(revision=expect[0], case=expect[1]):
                self.assertEqual(result, expect)

    def test_4432_landing_damage_force_and_type_records(self):
        data = load_contract_fixture(FIELDS_FIXTURE)
        rows = data['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(rows), len(revisions))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        game = (engine / 'openbor.c').read_text(encoding='latin-1')
        script = (engine / 'openborscript.c').read_text(encoding='latin-1')
        variants = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin-1')
        get = switch_cases(script, 'openbor_getentityproperty', 'propind')[1]
        change = switch_cases(script, 'openbor_changeentityproperty', 'propind')[1]
        load = function(game, 'load_cached_model')
        common = function(game, 'common_takedamage')
        resets = []
        for i, name in enumerate(('doland', 'arrow_move', 'boomerang_move', 'star_move',
                                  'drop_all_enemies', 'check_gravity')):
            body = function(game, name)
            reset = re.search(r'(?m)^[ \t]*(self|ent_list\[i\])->damage_on_landing = 0;\n'
                              r'[ \t]*\1->damage_on_landing_type = -1;', body)[0]
            resets.append(f'case {i}: {reset}\n    break;')
        sections = dict(
            GET=get['_ep_damage_on_landing']['body'],
            SET=change['_ep_damage_on_landing']['body'],
            VARIANTS='\n'.join(function(variants, name) for name in
                               ('ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
            TYPE=function(game, 'obor_landing_damage_type'),
            DEFAULT=re.search(r'(?ms)^const s_collision_attack emptyattack\s*=\s*\{.*?^\};', game)[0],
            COMMAND=re.search(r'(?ms)^            case CMD_MODEL_DAMAGEONLANDING:.*?^                break;', load)[0],
            COPY=re.search(r'(?m)^            self->damage_on_landing = attack->damage_on_landing;\n'
                           r'            self->damage_on_landing_type = attack->damage_on_landing_type;', common)[0],
            RESET='\n'.join(resets),
            RESET_COUNT=str(len(resets)),
            REVISIONS=','.join(str(row['revision']) for row in rows),
        )
        template = Path(__file__).with_name('throw_landing_fields_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: sections[match[1]], template)
        actual = [json.loads(line) for line in native_output(
            code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',)).splitlines()]
        expected = [[row['revision'], *data['contracts'][row['contract']]] for row in rows]
        self.assertEqual(actual, expected)

    def test_4432_deferred_landing_damage_and_death(self):
        data = load_contract_fixture(DEFERRED_FIXTURE)
        rows = data['sources']
        revisions = {row['revision'] for row in rows}
        self.assertEqual(len(revisions), len(rows))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / data['engine']))
        game = (engine / 'openbor.c').read_text(encoding='latin-1')
        script = (engine / 'openborscript.c').read_text(encoding='latin-1')
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin-1')
        getter = switch_cases(script, 'openbor_getentityproperty', 'propind')[1]
        setter = switch_cases(script, 'openbor_changeentityproperty', 'propind')[1]
        self.assertNotIn('_ep_die_on_landing', setter)
        read_type, write_type = re.findall(r'(?ms)^    case _sv_lasthitt:\n(.*?)^        break;', game)
        code = Path(__file__).with_name('deferred_landing_contract.c.in').read_text()
        values = dict(
            GET_LAST_TYPE=read_type,
            SET_LAST_TYPE=write_type,
            NAMESPACE=entity_namespace(script),
            SEARCH=function((engine / 'source/utils.c').read_text(), 'searchList'),
            GET_DIE=getter['_ep_die_on_landing']['body'],
            VARIANTS='\n'.join(function(variant, name) for name in
                               ('ScriptVariant_ChangeType', 'ScriptVariant_IntegerValue')),
            DEFAULT=re.search(r'(?ms)^const s_collision_attack emptyattack\s*=\s*\{.*?^\};', game)[0],
            METHODS='\n'.join(function(game, name) for name in (
                'obor_apply_damage_factor', 'obor_force_damage', 'checkdamage', 'common_takedamage',
                'obor_landing_damage_source', 'obor_apply_pending_landing_damage',
                'obor_check_deferred_landing')),
            GRAVITY_CALL=braced_statement(
                function(game, 'check_gravity'),
                f'if(obor_profile_build >= 4665 && obor_profile_build <= {data["range"][1]})'),
            REVISIONS=',\n'.join('{%d,%d,%d}' % (row['revision'], row['die_ordinal'], row['direction_ordinal'])
                                 for row in rows),
            CASES=',\n'.join('{' + ','.join(str(int(n)) for n in case) + '}' for case in data['cases']),
        )
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], code)
        actual = [json.loads(line) for line in native_output(
            code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',)).splitlines()]
        expected = [[row['revision'], *case] for row in rows for case in data['contracts'][row['contract']]]
        self.assertEqual(len(actual), len(expected))
        for result, reference in zip(actual, expected):
            with self.subTest(revision=reference[0], case=reference[1]):
                self.assertEqual(result, reference)


if __name__ == '__main__':
    unittest.main()
