"""Observe native frame effects and clocks against source-reviewed contracts.

Services record calls and may change the active animation; their implementations
and complete gameplay remain separate contracts.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import sys
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_early_jump_walkoff import braced_statement
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-frame-sampling-contracts.json'
SPAWN_FIXTURE = Path(__file__).with_name('fixtures') / 'profile-frame-spawn-contracts.json'
FRAME_ENTITY_FIXTURE = SPAWN_FIXTURE.with_name('profile-frame-entity-contracts.json')
VECTORS = ('delay', 'move', 'movez', 'movea', 'seta', 'soundtoplay',
           'weaponframe', 'spawnframe', 'summonframe')
SCALARS = ('numframes', 'flipframe', 'subentity', 'unsummonframe', 'throwframe',
           'throwa', 'custknife', 'custpshotno', 'custstar', 'shootframe', 'tossframe')


def animation_input(value):
    fields = ['.' + name + '=' + str(value[name]) for name in SCALARS]
    for name in VECTORS:
        data = value[name]
        if data is not None:
            fields += ['.' + name + '_present=1', '.' + name + '={' + ','.join(map(str, data)) + '}']
    for name in ('quakeframe', 'jumpframe'):
        fields.append('.' + name + '={' + ','.join('.' + k + '=' + str(v)
                                                   for k, v in value[name].items()) + '}')
    return '{' + ','.join(fields) + '}'


def program(data):
    source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
    parts = dict(FUNCTIONS=function(source, 'obor_profile_frame_unsummon') +
                          function(source, 'update_frame'),
                 PROFILES=','.join(str(row['revision']) + 'u' for row in data['sources']))
    rows = []
    for case in data['cases']:
        initial = case['initial']
        # Only inputs enter C. Source-reviewed modes and expected results stay
        # in Python and cannot affect native execution.
        values = ['.a=' + animation_input(case['a']), '.b=' + animation_input(case['b'])]
        for name in ('target', 'position_only', 'initial_child', 'jumping', 'star_result', 'knife_result'):
            values.append('.' + name + '=' + str(int(case[name])))
        for name in ('frame', 'clock', 'animating', 'base', 'altbase', 'direction',
                     'old_nextanim', 'level', 'handler'):
            values.append('.' + name + '=' + str(int(initial[name])) + ('u' if name == 'clock' else ''))
        values += ['.position={' + ','.join(map(str, initial['position'])) + '}',
                   '.edelay={' + ','.join('.' + k + '=' + str(v) for k, v in initial['edelay'].items()) + '}']
        rows.append('{' + ','.join(values) + '}')
    parts['CASES'] = ',\n'.join(rows)
    clocks = []
    for row in data['clock_fields']:
        if (not re.fullmatch(r'[A-Za-z_]\w*', row['name']) or
                type(row['elements']) is not int or not 1 <= row['elements'] <= 64):
            raise ValueError('Bounded native clock members required')
        for i in range(row['elements']):
            member = row['name'] + ('[%d]' % i if row['elements'] > 1 else '')
            clocks.append('assert(sizeof(subject.%s)==4); subject.%s=value; '
                          'assert((uint64_t)subject.%s==value); ++checked;' % (member, member, member))
    parts['CLOCK_CHECKS'] = '\n'.join(clocks)
    parts['CLOCK_VALUES'] = ','.join(str(v) + 'u' for v in data['clock_values'])
    text = Path(__file__).with_name('frame_sampling_contract.c.in').read_text()
    for key, value in parts.items():
        text = text.replace('@' + key + '@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native frame sampling dependency')
    return text


def spawn_program(rows, engine, engine_id):
    source = (engine / 'openbor.c').read_text(encoding='latin-1')
    methods = ['ent_spawn_ent', 'ent_summon_ent']
    if engine_id == '6391':
        methods.insert(0, 'obor_profile_has_classic_boomerang')
    code = Path(__file__).with_name('frame_spawn_contract.c.in').read_text()
    code = code.replace('@FUNCTIONS@', '\n'.join(function(source, name) for name in methods))
    return code.replace('@PROFILES@', ','.join('{%du,%d,%d,{%d,%d}}' % (
        row['revision'], row['shift_with_level'], row['shift_without_level'],
        *row.get('spawn_reasons', (0, 0))) for row in rows))


class FrameSamplingContracts(unittest.TestCase):
    def test_native_spawn_summon_placement_and_callback_order(self):
        data = load_contract_fixture(SPAWN_FIXTURE)
        rows = data['sources']
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        engine = ROOT / 'src/engines' / data['engine']
        code = spawn_program(rows, engine, data['engine'])
        actual = [json.loads(line) for line in native_output(code, data).splitlines()]
        self.assertEqual(actual, [dict(revision=r['revision'], cases=146) for r in rows])
        print(json.dumps(dict(spawn_contexts=len(rows), spawn_cases=146*len(rows))), file=sys.stderr)

    def test_native_effects_callbacks_ranges_and_unsigned_clocks(self):
        data = load_contract_fixture(FIXTURE)
        rows = data['sources']
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        output = [json.loads(line) for line in native_output(program(data), data).splitlines()]
        self.assertEqual(len(output), len(rows) * (1 + len(data['cases'])))
        cursor = iter(output)
        checks = sum(r['elements'] for r in data['clock_fields']) * len(data['clock_values'])
        for row in rows:
            self.assertEqual(next(cursor), dict(revision=row['revision'], clocks=checks))
            expected = data['contracts'][row['contract']]
            self.assertEqual(len(expected), len(data['cases']))
            self.assertIn(row['dust_autokill'], (1, 2))
            dust_field = data['state_fields'].index('dust_autokill')
            for i, value in enumerate(expected):
                with self.subTest(profile=row['revision'], case=data['cases'][i]['name']):
                    self.assertIn(value['state'][dust_field], (0, row['dust_autokill']))
                    self.assertEqual(next(cursor), dict(revision=row['revision'], case=i, **value))
        print(json.dumps(dict(contexts=len(rows), cases=len(rows)*len(data['cases']),
                              clock_checks=checks*len(rows))), file=sys.stderr)


class FrameEntityContracts(unittest.TestCase):
    def frame_entity_inputs(self, engine_id):
        data = load_contract_fixture(FRAME_ENTITY_FIXTURE)
        rows = [row for row in data['sources'] if row['engine'] == engine_id]
        revisions = [row['revision'] for row in rows]
        self.assertEqual(revisions, sorted(contract_revisions(data, data['expected_revisions'][engine_id])))
        engine = Path(os.environ.get('OBOR_HISTORICAL_ENGINE', ROOT / 'src/engines' / engine_id))
        return rows, revisions, engine

    def check_frame_entity_spawn(self, engine_id):
        rows, revisions, engine = self.frame_entity_inputs(engine_id)
        code = spawn_program(rows, engine, engine_id)
        actual = [json.loads(line) for line in native_output(code, {'engine': engine_id},
            engine_source=engine, extra_cflags=('-fgnu89-inline',)).splitlines()]
        self.assertEqual(actual, [dict(revision=revision, cases=146) for revision in revisions])

    def test_4432_frame_entity_spawn(self):
        self.check_frame_entity_spawn('4432')

    def test_6391_frame_entity_spawn(self):
        self.check_frame_entity_spawn('6391')

    def check_frame_entity_initialization(self, engine_id):
        rows, revisions, engine = self.frame_entity_inputs(engine_id)
        source = (engine / 'openbor.c').read_text(encoding='latin-1')
        init = function(source, 'ent_default_init')
        enemy = init[init.index('case TYPE_ENEMY:'):init.index('case TYPE_TRAP:')]
        shot = init[init.index('case TYPE_SHOT:'):init.index('case TYPE_NONE:')]
        frame = function(source, 'update_frame')
        costs = frame[frame.index('if(anim->projectile.throwframe == f)'):frame.index('uf_interrupted:')]
        modern = engine_id == '6391'
        cost_flag = 'deduct_ammo' if modern else 'reactive'
        consume = braced_statement(function(source, 'common_attack_proc'), f'if(self->{cost_flag} == 1)')
        values = dict(ENEMY=enemy, SHOT=shot, COSTS=costs, CONSUME=consume,
                      PROFILE=function(source, 'obor_profile_has_classic_boomerang') if modern else '',
                      RELEASE=braced_statement(function(source, 'free_ent'), 'if(e->item_properties)') if modern else '',
                      ROWS=',\n'.join('{%du,%d,%d}' % (
                          row['revision'], row['active_attack_state'], row['throw_boomerang']) for row in rows))
        template = Path(__file__).with_name('frame_entity_contract.c.in').read_text()
        code = re.sub(r'@([A-Z_]+)@', lambda match: values[match[1]], template)
        output = native_output(code, {'engine': engine_id}, engine_source=engine,
                               extra_cflags=('-fgnu89-inline',))
        self.assertEqual([int(line) for line in output.splitlines()], revisions)

    def test_4432_frame_entity_initialization(self):
        self.check_frame_entity_initialization('4432')

    def test_6391_frame_entity_initialization(self):
        self.check_frame_entity_initialization('6391')


if __name__ == '__main__':
    unittest.main()
