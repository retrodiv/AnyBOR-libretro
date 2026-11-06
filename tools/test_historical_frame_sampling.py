"""Observe native frame effects and clocks against source-reviewed contracts.

Services record calls and may change the active animation; their implementations
and complete gameplay remain separate contracts.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
from pathlib import Path
import re
import sys
import unittest

from contract_fixtures import load_contract_fixture, contract_revisions
from test_historical_common_think import ROOT, native_output
from test_historical_player import function

FIXTURE = Path(__file__).with_name('fixtures') / 'profile-frame-sampling-contracts.json'
SPAWN_FIXTURE = Path(__file__).with_name('fixtures') / 'profile-frame-spawn-contracts.json'
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


class FrameSamplingContracts(unittest.TestCase):
    def test_native_spawn_summon_placement_and_callback_order(self):
        data = load_contract_fixture(SPAWN_FIXTURE)
        rows = data['sources']
        self.assertEqual({r['revision'] for r in rows}, contract_revisions(data, data['expected_revisions']))
        self.assertEqual(len(rows), len({r['revision'] for r in rows}))
        source = (ROOT / 'src/engines' / data['engine'] / 'openbor.c').read_text()
        code = Path(__file__).with_name('frame_spawn_contract.c.in').read_text()
        code = code.replace('@FUNCTIONS@', function(source, 'ent_spawn_ent') + function(source, 'ent_summon_ent'))
        code = code.replace('@PROFILES@', ','.join('{%du,%d,%d}' % (
            r['revision'], r['shift_with_level'], r['shift_without_level']) for r in rows))
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


if __name__ == '__main__':
    unittest.main()
