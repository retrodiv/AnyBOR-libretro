"""Compare each original boomerang movement route and its caller outputs.

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
from test_historical_model_defaults import model_command_functions
from test_historical_player import function, switch_cases

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-boomerang-motion-contracts.json'
TERRAIN = FIXTURE.with_name('profile-4432-projectile-terrain.json')
RICOCHET = FIXTURE.with_name('profile-6391-projectile-ricochet.json')
CLASSIC = FIXTURE.with_name('profile-6391-classic-boomerang.json')
ENTITY_LOSS = FIXTURE.with_name('profile-entity-loss.json')
PROJECTILE_ORIGINS = FIXTURE.with_name('profile-projectile-origins.json')
INPUTS = (
    'aimove', 'parent', 'direction', 'parent_direction', 'parent_type',
    'x', 'y', 'z', 'vx', 'vz', 'dest', 'accel', 'distance', 'speed',
    'count', 'sortid', 'nomove', 'wall_toggle', 'wall_index', 'wall_animation',
    'catch_ground', 'catch_air', 'min', 'max', 'parent_y', 'parent_pain', 'parent_falling', 'parent_dead',
)


def movement_dispatch(text):
    start = text.index('    else if(aimove & AIMOVE1_NOMOVE)')
    end = re.search(r'(?m)^    else\s*\n', text[start:])
    if end is None:
        raise ValueError('Native special-movement dispatcher did not terminate before other AI')
    return text[:start+end.start()] + '    return -19;\n}\n'


def candidate_movement(source):
    names = (
        'obor_boomerang_oscillate', 'obor_boomerang_turn_by_distance', 'obor_boomerang_catch', 'boomerang_move'
    )
    if 'obor_profile_animation_base' in source:
        names = ('obor_profile_animation_base',) + names
    if 'obor_projectile_hits_platform' in source:
        names = ('obor_projectile_hits_platform',) + names
    return '\n'.join(function(source, name) for name in names) + '\n' + movement_dispatch(
        function(source, 'common_move'))


def source_engine(data):
    return Path(os.environ.get('OBOR_PROJECTILE_TERRAIN_ENGINE', ROOT / 'src/engines' / data['engine']))


def entity_loss_defaults(source):
    declarations = (
        r'^static int DEFAULT_OFFSCREEN_KILL\s*=\s*\d+;',
        r'^const s_collision_attack emptyattack\s*=\s*\{.*?^\};',
        r'^s_axis\w* default_model_dropv\s*=\s*\{.*?^\};',
    )
    return '\n'.join(re.search(pattern, source, re.M | re.S)[0] for pattern in declarations)


def program(data, movement=None):
    engine = source_engine(data)
    if movement is None:
        movement = candidate_movement((engine/'openbor.c').read_text(encoding='latin1'))
    params = ['{' + ','.join(str(row[name]) for name in INPUTS) + '}' for row in data['cases']]
    values = {'MOVEMENT': movement, 'CASES': ',\n'.join(params),
              'REVISIONS': ','.join(str(row['revision']) for row in data['sources'])}
    template = Path(__file__).with_name('boomerang_motion_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda m: values[m[1]], template)


class BoomerangMotionTests(unittest.TestCase):
    def check_projectile_origins(self, engine_id):
        data = load_contract_fixture(PROJECTILE_ORIGINS) | {'engine': engine_id}
        rows = [row for row in data['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][engine_id])))
        engine = source_engine(data)
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        spawn = function(source, 'spawn')
        predicate, = re.findall(r'(?m)^\s*(if\(\(e->modeldata.type & TYPE_PLAYER\) && [^\n]+\))\s*$', spawn)
        methods = ('knife_spawn',)
        if 'obor_spawn_excludes_player_targets(' in source:
            methods = ('obor_spawn_excludes_player_targets',) + methods
        values = {
            'SPAWN_FILTER': braced_statement(spawn, predicate),
            'METHODS': '\n'.join(function(source, name) for name in methods),
            'ROWS': ','.join('{%du,%d,%d,%d,{%s}}' % (row['revision'], row['exclusion_value'],
                            row['active_state'], row['spawn_type'], ','.join(map(str, row['origin_masks'])))
                             for row in rows),
        }
        template = Path(__file__).with_name('projectile_origins_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        raw = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in raw.splitlines()], revisions)

    def test_4432_projectile_origins(self):
        self.check_projectile_origins('4432')

    def test_6391_projectile_origins(self):
        self.check_projectile_origins('6391')

    def check_entity_loss(self, engine_id):
        data = load_contract_fixture(ENTITY_LOSS) | {'engine': engine_id}
        rows = [row for row in data['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][engine_id])))
        engine = source_engine(data)
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        methods = (('kill',) if engine_id == '4432' else ('is_frozen', 'kill_entity')) + ('check_lost',)
        values = {
            'DEFAULTS': entity_loss_defaults(source),
            'METHODS': '\n'.join(function(source, name) for name in methods),
            'PROFILES': ','.join('{%du,%d,%d}' % (row['revision'], row['full_summon_type'], row['release_shot'])
                                 for row in rows),
        }
        template = Path(__file__).with_name('entity_loss_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        raw = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in raw.splitlines()], revisions)

    def test_4432_entity_loss(self):
        self.check_entity_loss('4432')

    def test_6391_entity_loss(self):
        self.check_entity_loss('6391')

    def check_projectile_launch(self, data, revisions):
        engine = source_engine(data)
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        loader, cases = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        directives = ('PSHOTFRAMENO', 'SHOOTFRAME', 'PBOMBFRAME')
        update = function(source, 'update_frame')
        frames = ('throwframe', 'shootframe', 'tossframe')
        defaults = re.findall(r'(?m)^\s*(newanim->projectile\.(?:shoot|throw|toss)frame\s*=\s*-1;)', loader)
        self.assertEqual(len(defaults), 3)
        values = {
            'METHODS': '\n'.join(function(source, name) for name in
                                 ('isNumeric', 'getValidInt', 'bomb_spawn', 'star_spawn')),
            'DEFAULT_FRAMES': '\n'.join(defaults),
            'DIRECTIVES': '\n'.join(f"case {name}:" + cases[f'CMD_MODEL_{name}']['body']
                                    for name in directives),
            'SELECTORS': '\n'.join(
                f'case {name}: return ' +
                re.search(rf'if\s*\((anim->projectile\.{frame}\s*==\s*f)\)', update)[1] + ';'
                for name, frame in zip(directives, frames, strict=True)),
            'BOMB_FRAME': braced_statement(update, 'if(anim->projectile.tossframe == f)'),
            'PROFILES': ','.join(str(revision) for revision in revisions),
        }
        template = Path(__file__).with_name('projectile_launch_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda token: values[token[1]], template)
        actual = native_output(code, data, engine_source=engine)
        self.assertEqual([int(line) for line in actual.splitlines()], revisions)

    def test_4432_projectile_launch_state(self):
        data = load_contract_fixture(TERRAIN)
        revisions = [row['revision'] for row in data['sources'] if row['revision'] in (4750, 4905)]
        self.assertEqual(revisions, [4750, 4905])
        self.check_projectile_launch(data, revisions)

    def test_6391_projectile_launch_state(self):
        data = load_contract_fixture(CLASSIC)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'])))
        self.check_projectile_launch(data, revisions)

    def test_6391_classic_boomerang(self):
        data = load_contract_fixture(CLASSIC)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = source_engine(data)
        core = (engine / 'openbor.c').read_text(encoding='latin-1')
        commands = (engine / 'source/openborscript/commands.c').read_text()
        utility = (engine / 'source/utils.c').read_text()
        loader = function(core, 'load_cached_model')
        initialize = function(core, 'ent_default_init')
        gravity = function(core, 'check_gravity')
        _, cases = switch_cases(core, 'load_cached_model', 'cmd', outermost=True)
        def selector(method, word):
            return braced_statement(function(core, method),
                f'else if(obor_profile_has_classic_boomerang() && stricmp(value, "{word}") == 0)')
        methods = ('obor_profile_has_classic_boomerang', 'isNumeric', 'getValidFloat',
                   'diff', 'inair', 'sort_invert_by_parent', 'do_catch', 'boomerang_catch',
                   'boomerang_initialize', 'boomerang_move', 'ent_spawn_ent', 'ent_summon_ent')
        model_cases = {'CMD_MODEL_BOOMERANGVALUES', 'CMD_MODEL_BOOMERANG',
                       'CMD_MODEL_BOMB', 'CMD_MODEL_PLAYBOMB'}
        values = {
            'COMMANDS': model_command_functions(commands, utility),
            'METHODS': '\n'.join(function(core, name) for name in methods),
            'LOSS_DEFAULTS': entity_loss_defaults(core),
            'LOST': '\n'.join(function(core, name) for name in ('is_frozen', 'check_lost')),
            'MODEL': ''.join('case ' + name + ':' + case['body'] for name, case in cases.items()
                             if name in model_cases),
            'SUBTYPE': selector('lcmHandleCommandSubtype', 'boomerang'),
            'AIMOVE': selector('lcmHandleCommandAimove', 'boomerang'),
            'ANIMATION': '\n'.join(selector('translate_ani_id', name) for name in
                                   ('getboomerang', 'getboomeranginair')),
            'DISPATCH': braced_statement(function(core, 'common_move'),
                              'else if(obor_profile_has_classic_boomerang() && (aimove & AIMOVE1_BOOMERANG))'),
            'DAMAGE': braced_statement(loader, 'if(newchar->subtype == SUBTYPE_ARROW || (obor_profile_has_classic_boomerang()'),
            'INITIALIZE': braced_statement(initialize,
                'else if(e->modeldata.subtype == SUBTYPE_ARROW || (obor_profile_has_classic_boomerang()'),
            'DROP': re.search(r'(?m)^\s*dodrop = \(e->modeldata.subtype[^\n]+;', initialize)[0],
            'LAND': braced_statement(gravity, 'else if((!self->animation->move[self->animpos]->base'),
            'DRAW': braced_statement(function(core, 'display_ents'), 'if(e->owner)\n                    {'),
            'PROFILES': ','.join('{%du,%d,%d,%d}' % (row['revision'], row['syntax'],
                                                    row['boomerang_id'], row['touch_id']) for row in rows),
        }
        template = Path(__file__).with_name('classic_boomerang_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        raw = native_output(code, data, engine_source=engine, extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in raw.splitlines()], revisions)

    def test_6391_projectile_ricochet(self):
        data = load_contract_fixture(RICOCHET)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = source_engine(data)
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        methods = ('diff', 'toss', 'checkwall_index', 'obor_profile_uses_legacy_ricochet',
                   'check_block_wall', 'check_block_obstacle', 'projectile_wall_deflect',
                   'arrow_move', 'star_move', 'boomerang_move')
        values = {
            'METHODS': '\n'.join(function(source, name) for name in methods),
            'DEFAULT_ATTACK': re.search(r'(?ms)^const s_collision_attack emptyattack\s*=\s*\{.*?^\};', source)[0],
            'PROFILES': ','.join('{%du,%d}' % (row['revision'], row['legacy']) for row in data['sources']),
            'CASES': ',\n'.join('{' + ','.join(str(int(value)) for value in row) + '}'
                               for row in data['cases']),
        }
        template = Path(__file__).with_name('projectile_ricochet_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        raw = native_output(code, data, engine_source=engine)
        self.assertEqual([int(line) for line in raw.splitlines()], revisions)

    def test_projectile_terrain(self):
        data = load_contract_fixture(TERRAIN)
        rows = data['sources']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = source_engine(data)
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        names = ('obor_profile_animation_base', 'obor_projectile_hits_platform', 'arrow_move',
                 'obor_boomerang_oscillate', 'obor_boomerang_turn_by_distance', 'obor_boomerang_catch',
                 'boomerang_move', 'bomb_move', 'star_move', 'star_spawn')
        spawn = function(source, 'bomb_spawn')
        entry = spawn.index('    e->modeldata.no_adjust_base = 0;')
        commands = function((engine / 'source/gamelib/commands.c').read_text(), 'createModelCommandList')
        registration = re.search(r'(?m)^    if\([^\n]+\)\n    \{\n'
                                 r'        LIST_ADD\(CMD_MODEL_STAR_VELOCITY, "starvelocity"\);\n    \}', commands)[0]
        _, cases = switch_cases(source, 'load_cached_model', 'cmd', outermost=True)
        draw_sort = braced_statement(function(source, 'display_ents'), 'if(e->owner &&\n')
        checks = dict(MOVEMENT='\n'.join(function(source, name) for name in names),
                      SPAWN=spawn[entry:spawn.rindex('    return e;')],
                      STAR_REGISTRATION=registration,
                      STAR_COMMAND=cases['CMD_MODEL_STAR_VELOCITY']['body'],
                      STAR_DRAW_SORT=draw_sort,
                      PROFILES=',\n'.join('{%du,%d}' % (row['revision'], row['terrain'])
                                          for row in rows))
        template = Path(__file__).with_name('projectile_terrain_contract.c.in').read_text()
        probe = re.sub(r'@([A-Z_]+)@', lambda m: checks[m[1]], template)
        actual = native_output(probe, data, engine_source=engine)
        self.assertEqual([int(line) for line in actual.splitlines()], revisions)

    def test_original_motion_contracts(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual(revisions, contract_revisions(data, data['expected_revisions']))
        output = native_output(program(data), data, engine_source=source_engine(data))
        actual = [json.loads(line) for line in output.splitlines()]
        expected = [[row['revision'], *result] for row in data['sources']
                    for result in data['contracts'][row['contract']]]
        self.assertEqual(len(actual), len(expected))
        for result, reference in zip(actual, expected):
            with self.subTest(revision=reference[0], case=data['cases'][reference[1]]['name']):
                self.assertEqual(result, reference)

    def test_parentless_launch_keeps_vertical_position(self):
        data = load_contract_fixture(FIXTURE)
        launch = next(case for case in data['cases'] if case['name'] == 'launch_right')
        sample = data | {
            'sources': [{'revision': 4432}],
            'cases': [launch | {'parent': 0, 'x': 88, 'y': 9, 'z': 4}],
        }
        result = json.loads(native_output(program(sample), data, engine_source=source_engine(data)))
        self.assertEqual(result[:6], [4432, 0, 1, [88, 9, 4], [12, 0, 0], 1])


if __name__ == '__main__':
    unittest.main()
