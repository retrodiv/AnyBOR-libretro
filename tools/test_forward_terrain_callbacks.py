"""Execute complete native terrain callbacks and movement callers.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from contract_fixtures import contract_profiles, contract_revisions, load_contract_fixture
from test_forward_attack_callbacks import source_calls
from test_historical_common_think import ROOT, native_output
from test_historical_player import function, switch_cases
from test_early_jump_walkoff import braced_statement

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-forward-terrain-callbacks-contracts.json'
BASEMAP_FIXTURE = FIXTURE.with_name('profile-basemap-hole-contracts.json')
ARGUMENT_FIXTURE = FIXTURE.with_name('profile-terrain-callback-arguments.json')
TRANSITION_FIXTURE = FIXTURE.with_name('profile-terrain-callback-transitions.json')


def program(data, engine):
    core = (engine / 'openbor.c').read_text()
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
    loader, cases = switch_cases(core, 'load_level', 'cmd', outermost=True)
    values = dict(FUNCTIONS='\n'.join(function(core, name) for name in data['functions']),
        CONTEXTS=','.join('{%du,%d,%d,%d,%d}' % (row['revision'], row['platform'],
                          row['wall_index'], row['hole'], row['base_event']) for row in data['sources']),
        LOAD_CASE=cases['CMD_LEVEL_HOLE']['body'],
        EXIT_HOLE=braced_statement(loader, 'if(exit_hole)'),
        PARSER='#pragma GCC diagnostic push\n#pragma GCC diagnostic ignored "-Wimplicit-fallthrough"\n' +
            function(core, 'ParseArgs') + '#pragma GCC diagnostic pop\n' +
            '\n'.join(function(core, name) for name in ('isNumeric','getValidFloat')),
        HOLE_VALUES=','.join('{%s,%sf,%d}' % (json.dumps(row['text']),
            float(row['value']).hex(), row['warning']) for row in data['hole_values']),
        VARIANTS='\n'.join(function(variant, name) for name in
            ('ScriptVariant_Init','ScriptVariant_Clear','ScriptVariant_ChangeType','ScriptVariant_Copy')))
    code = Path(__file__).with_name('forward_terrain_callbacks_contract.c.in').read_text()
    for key, value in values.items():
        code = code.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', code):
        raise ValueError('Unresolved native terrain callback input')
    return code


def basemap_program(data, engine):
    source = (engine / 'openbor.c').read_text()
    names = ('obor_terrain_between', 'testhole', 'checkhole_in', 'checkholeindex_in',
             'check_basemap', 'check_basemap_index', 'adjust_base')
    _, level_commands = switch_cases(source, 'load_level', 'cmd', outermost=True)
    draw = function(source, 'draw_scrolled_bg')
    start = draw.index('    s_drawmethod screenmethod =')
    end = draw.index('    for(index = 0; index < level->numlayersref;', start)
    cases = ['{' + ','.join(str(int(value)) for value in case['inputs']) + '}'
             for case in data['cases']]
    values = dict(FUNCTIONS='\n'.join(function(source, name) for name in names),
                  LOAD_HOLE=level_commands['CMD_LEVEL_HOLE']['body'],
                  DRAW_HOLES=draw[start:end],
                  PROFILES=','.join('{%du,%d}' % (row['revision'], row['draw_hole_sprite'])
                                    for row in data['sources']),
                  CASES=',\n'.join(cases))
    template = Path(__file__).with_name('basemap_hole_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


def callback_arguments_program(data, core, variant):
    names = ('execute_onblockw_script', 'execute_inhole_script')
    callbacks = [function(core, name) for name in names]
    extended = 'float depth' in callbacks[0].split('{', 1)[0]
    if extended != ('float depth' in callbacks[1].split('{', 1)[0]):
        raise ValueError('Terrain callbacks use inconsistent argument declarations')
    rows = ['{%d,%d,%sf,%d,%d}' % (
        case['plane'], case['initialized'], float(case['depth']).hex(),
        case['depth_value'], case['type']) for case in data['cases']]
    values = dict(
        DECLARATION_ALIASES='' if extended else '\n'.join(
            '#define ' + name + ' unused_' + name for name in names),
        VARIANTS='\n'.join(function(variant, name) for name in (
            'ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType',
            'ScriptVariant_Copy')),
        CALLBACKS='\n'.join(callbacks),
        PROFILES=','.join('{%du,%d}' % (row['revision'], row['fields']) for row in data['sources']),
        CASES=',\n'.join(rows),
        EXTRA_ARGS=', cases[c].depth, cases[c].type' if extended else '',
    )
    template = Path(__file__).with_name('terrain_callback_arguments_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


def terrain_transition_program(data, engine):
    core = (engine / 'openbor.c').read_text(encoding='latin-1')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin-1')
    movement = function(core, 'common_trymove')
    walls = []
    for axis in ('x', 'z'):
        condition = re.search(r'(?m)^[ \t]*(if\(' + axis + r'dir && \(wall = checkwall_below[^\n]+'
                              r'level->walls\[wall\]\.height > self->position\.y\))', movement)[1]
        walls.append(braced_statement(movement, condition))
    wall_code = '\n'.join(walls)
    callbacks = ['execute_onblockw_script', 'execute_inhole_script']
    if 'movement_wall_altitude()' in wall_code:
        callbacks.append('movement_wall_altitude')
    base = function(core, 'adjust_base')
    condition = re.search(r'(if\s*\(\s*hole\s*\))\s*\{\s*int holeind = checkholeindex_in', base)[1]
    values = {
        'VARIANTS': '\n'.join(function(variant, name) for name in
                              ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType')),
        'CALLBACKS': '\n'.join(function(core, name) for name in callbacks),
        'WALLS': wall_code,
        'HOLE': braced_statement(base, condition),
        'ROWS': ','.join('{%du,%d,%d,%d}' % (row['revision'], row['record'], row['x_axis'], row['z_axis'])
                         for row in data['sources']),
    }
    template = Path(__file__).with_name('terrain_callback_transition_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


def obstacle_callback_program(rows, engine):
    core = (engine / 'openbor.c').read_text(encoding='latin-1')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin-1')
    movement = function(core, 'common_trymove')
    condition = re.search(r'(?m)^\s*(if\(self->modeldata\.subject_to_obstacle > 0[^\n]*)', movement)[1]
    values = {
        'VARIANTS': '\n'.join(function(variant, name) for name in
                              ('ScriptVariant_Init', 'ScriptVariant_Clear', 'ScriptVariant_ChangeType')),
        'CALLBACK': function(core, 'execute_onblocko_script'),
        'COLLISION': braced_statement(movement, condition),
        'ROWS': ','.join('{%du,%d,%d,%d,%d}' % (row['revision'], row['obstacle_plane'],
                         row['obstacle_contact_inclusive'], row['x_axis'], row['z_axis']) for row in rows),
    }
    template = Path(__file__).with_name('obstacle_callback_plane_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


def terrain_contact_limits_program(rows, engine):
    core = (engine / 'openbor.c').read_text(encoding='latin-1')
    script = (engine / 'openborscript.c').read_text(encoding='latin-1')
    variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text(encoding='latin-1')
    movement = function(core, 'common_trymove')
    platform_condition = re.search(r'(?m)^\s*(if\(self->modeldata\.subject_to_platform > 0[^\n]*)', movement)[1]
    wall_calls = []
    for caller, count in (('testmove', 1), ('common_trymove', 2), ('common_try_jump', 2)):
        calls = source_calls(function(core, caller), ['checkwall_below'])
        if len(calls) != count:
            raise ValueError('Unexpected wall lookups in ' + caller)
        wall_calls.extend(call['text'] for call in calls)
    functions = ['testwall', 'checkwall_below', 'execute_onblockp_script']
    if 'movement_wall_altitude()' in '\n'.join(wall_calls):
        functions.append('movement_wall_altitude')
    values = {
        'VARIANTS': '\n'.join(function(variant, name) for name in ('ScriptVariant_Init', 'ScriptVariant_Clear',
                              'ScriptVariant_ChangeType', 'ScriptVariant_DecimalValue')),
        'FUNCTIONS': '\n'.join(function(core, name) for name in functions),
        'SCRIPT': function(script, 'openbor_checkwall'),
        'PLATFORM_COLLISION': braced_statement(movement, platform_condition),
        'WALL_CALLS': ',\n'.join(wall_calls),
        'ROWS': ','.join('{%du,%d,%d,%d,%d}' % (row['revision'], row['platform_x'], row['platform_z'],
                         row['movement_wall_altitude'], row['script_wall_altitude']) for row in rows),
    }
    template = Path(__file__).with_name('terrain_contact_limits_contract.c.in').read_text()
    return re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)


class ForwardTerrainCallbackTests(unittest.TestCase):
    def check_terrain_callback_transition(self, engine_id):
        data = load_contract_fixture(TRANSITION_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][engine_id])))
        data = data | {'engine': engine_id, 'sources': rows}
        engine = Path(os.environ.get('OBOR_TERRAIN_CALLBACKS_ENGINE', ROOT / 'src/engines' / engine_id))
        result = native_output(terrain_transition_program(data, engine), data, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in result.splitlines()], revisions)

    def test_4432_terrain_callback_transition(self):
        self.check_terrain_callback_transition('4432')

    def test_6391_terrain_callback_transition(self):
        self.check_terrain_callback_transition('6391')

    def test_6391_obstacle_callback_plane(self):
        data = load_contract_fixture(TRANSITION_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == '6391']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions']['6391'])))
        engine = Path(os.environ.get('OBOR_TERRAIN_CALLBACKS_ENGINE', ROOT / 'src/engines/6391'))
        result = native_output(obstacle_callback_program(rows, engine), {'engine': '6391'}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in result.splitlines()], revisions)

    def test_6391_platform_tags_and_wall_limits(self):
        data = load_contract_fixture(TRANSITION_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == '6391']
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions']['6391'])))
        engine = Path(os.environ.get('OBOR_TERRAIN_CALLBACKS_ENGINE', ROOT / 'src/engines/6391'))
        result = native_output(terrain_contact_limits_program(rows, engine), {'engine': '6391'}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in result.splitlines()], revisions)

    def test_native_locals_cleanup_axis_events_and_height_movement(self):
        data = load_contract_fixture(FIXTURE)
        revisions = {row['revision'] for row in data['sources']}
        self.assertEqual(len(revisions), len(data['sources']))
        self.assertEqual((min(revisions), max(revisions)), tuple(data['range']))
        self.assertTrue(set(data['boundary_controls']) <= revisions)
        for profile in contract_profiles(data, json.loads((ROOT / 'src/pin.json').read_text())['profiles']):
            revision = int(profile.get('revision', profile['build']))
            if profile['engine'] == data['engine'] and data['range'][0] <= revision <= data['range'][1]:
                self.assertIn(revision, revisions)
        engine = Path(os.environ.get('OBOR_TERRAIN_CALLBACKS_ENGINE', ROOT / 'src/engines' / data['engine']))
        actual = [json.loads(line) for line in native_output(program(data, engine), data, engine_source=engine).splitlines()]
        self.assertEqual(actual, [dict(revision=row['revision'], status='PASS') for row in data['sources']])

    def test_native_holes_when_basemaps_are_disabled(self):
        data = load_contract_fixture(BASEMAP_FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_BASEMAP_HOLES_ENGINE', ROOT / 'src/engines' / data['engine']))
        expected = [dict(revision=row['revision'],
                         cases=[case[row['contract']] for case in data['cases']])
                    for row in data['sources']]
        native = native_output(basemap_program(data, engine), data, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([json.loads(line) for line in native.splitlines()], expected)

    def test_native_wall_and_hole_callback_arguments(self):
        data = load_contract_fixture(ARGUMENT_FIXTURE)
        revisions = [row['revision'] for row in data['sources']]
        self.assertEqual(len(revisions), len(set(revisions)))
        self.assertEqual(set(revisions), contract_revisions(data, data['expected_revisions']))
        engine = Path(os.environ.get('OBOR_TERRAIN_CALLBACKS_ENGINE', ROOT / 'src/engines' / data['engine']))
        core = (engine / 'openbor.c').read_text()
        variant = (engine / 'source/scriptlib/ScriptVariant.c').read_text()
        output = native_output(callback_arguments_program(data, core, variant), data, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([json.loads(line) for line in output.splitlines()],
                         [dict(revision=revision, calls=len(data['cases'])) for revision in revisions])


if __name__ == '__main__':
    unittest.main()
