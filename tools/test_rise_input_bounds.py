"""Check bounded rise inputs against native action and timer contracts.

Timing controls preserve native unsigned expression widths. They alone do not
prove caller/RNG order, complete action behavior or game acceptance.
SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import os
from pathlib import Path
import re
import unittest

from test_model_constructor_ownership import run_native
from test_historical_player import function
from test_early_jump_walkoff import continued_macro

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OBOR_TEST_SOURCE', HERE.parent))


def action_program(engine, profiles, *, wrong_refusal=False):
    core = (engine / 'openbor.c').read_text(encoding='latin1')
    header = (engine / 'openbor.h').read_text(encoding='latin1')
    action = function(core, 'set_riseattack')
    guard = re.compile(r'/\* AnyBOR: validate rise selectors before native table reads\. \*/.*?'
                       r'/\* AnyBOR: native rise action follows\. \*/', re.S)
    if len(guard.findall(action)) != 1:
        raise ValueError('One bounded native rise action required')
    baseline = guard.sub('', action).replace('set_riseattack(', 'baseline_riseattack(', 1)
    if wrong_refusal:
        line = 'if(!iRiseattack || !animriseattacks || max_attack_types <= 0) return 0;'
        if action.count(line) != 1:
            raise ValueError('One native input refusal required')
        action = action.replace(line, line.replace('return 0;', 'return 1;'), 1)
    has_back = 'animbackriseattacks' in action
    if re.search(r'\bint ai_check_lie\(', core):
        gate = function(core, 'ai_check_lie').replace('ai_check_lie(', 'probe_lie(', 1)
    else:
        # Exact native condition/body; the integer signal represents the
        # void caller's early return. Later thinker branches are not executed.
        caller = function(core, 'common_think')
        matches = re.findall(r'if\(self->drop\b[^{}]*\{\s*common_try_riseattack\(\);\s*return;\s*\}', caller)
        if len(matches) != 1 or 'obor_rise_random' not in matches[0]:
            raise ValueError('One original inline rise gate required')
        gate = 'static int probe_lie(void) {\n'+matches[0].replace('return;', 'return 1;')+'\nreturn 0;\n}\n'
    pattern = re.compile(r'obor_rise_random\(rand32\(\),\s*(\(self->stalltime\s*-\s*_?time\s*\+\s*1\))\)')
    if len(pattern.findall(gate)) != 1:
        raise ValueError('One native timing gate required')
    old_gate = pattern.sub(r'((rand32() % \1) < 3)', gate).replace('probe_lie(', 'baseline_lie(', 1)
    writes = set(re.findall(r'(?:iRiseattack|self)->([\w.]+)\s*(?:=(?!=)|[|&^+*-]=)', action))
    writes.update(re.findall(r'e->([\w.]+)\s*=', continued_macro(header, 'set_attacking')))
    writes.update(('animnum', 'modeldata.riseattacktype'))
    if not 7 <= len(writes) <= 24:
        raise ValueError('Bounded native action field inventory required')
    time_type = re.findall(r'(?m)^(u32|uint64_t)\s+_?time\s*=', core)
    animation_type = re.findall(r'(?m)^\s*(int|e_animations|animation_id_t)\s*\*\s*animriseattacks\s*=', core)
    if len(time_type) != 1 or len(animation_type) != 1:
        raise ValueError('Native timer and table element types required')
    points_max = 'maximum' if 'modeldata.jugglepoints.maximum' in action else 'max'
    point_init = ('actor.modeldata.jugglepoints.current=3;actor.modeldata.jugglepoints.'+points_max+'=9;'
                  if 'modeldata.jugglepoints.current' in action else 'actor.modeldata.jugglepoints=9;')
    optional = []
    if has_back:
        optional.append('actor.inbackpain=back;')
    if 'nograb_default' in action:
        optional.append('actor.nograb_default=1;')
    if 'iRiseattack->jugglepoints' in action:
        optional.append('actor.jugglepoints=5;')
    if 'modeldata.profile_jugglepoints' in action:
        optional.append('actor.modeldata.profile_jugglepoints=11;')
    health = ('actor.energy_state.health_current' if 'energy_state.health_current' in gate else
              'actor.energy_status.health_current' if 'energy_status.health_current' in gate else 'actor.health')
    values = dict(CONFIG='#include "config.h"' if (engine / 'config.h').is_file() else '',
                  ANIM_TYPE=animation_type[0],
                  ANIM_ID_TYPE='animation_id_t' if re.search(r'void\s+ent_set_anim\([^;]+animation_id_t', header) else 'int',
                  TIME_TYPE=time_type[0],
                  SPAN_TYPE='unsigned long' if re.search(r'unsigned long\s+stalltime\s*;', header) else time_type[0],
                  HAS_BACK=str(int(has_back)), ACTION=action, BASELINE_ACTION=baseline,
                  GATE=gate, BASELINE_GATE=old_gate, POINT_INIT=point_init,
                  OPTIONAL_INIT='\n'.join(optional), HEALTH=health,
                  EQUAL_FIELDS='\n'.join('CHECK(a->%s==b->%s);' % (field, field) for field in sorted(writes)),
                  PROFILES=','.join(str(int(p.get('revision', p['build'].split('-')[0])))+'u' for p in profiles))
    text = (HERE / 'rise_action_bounds.c.in').read_text()
    for key, value in values.items():
        text = text.replace('@'+key+'@', value)
    if re.search(r'@[A-Z_]+@', text):
        raise ValueError('Unresolved native action dependency')
    return text


def timing_program(*, wrong_empty_span=False):
    header = (ROOT / 'src/port/libretro/obor_rise_inputs.h').read_text()
    if wrong_empty_span:
        line = 'return span && (uint64_t)sample % span < UINT64_C(3);'
        if header.count(line) != 1:
            raise ValueError('One native unsigned rise predicate required')
        header = header.replace(line, 'return !span || (uint64_t)sample % span < UINT64_C(3);', 1)
    return (HERE / 'rise_input_bounds.c.in').read_text().replace('@HEADER@', header)


class RiseInputBoundsTests(unittest.TestCase):
    def _check_native_profiles(self, scalar_points):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        selected = 0
        for row in pin['engines']:
            engine = ROOT / 'src/engines' / row['build']
            action = function((engine / 'openbor.c').read_text(encoding='latin1'), 'set_riseattack')
            if ('iRiseattack->jugglepoints' in action) != scalar_points:
                continue
            selected += 1
            profiles = [p for p in pin['profiles'] if p['engine'] == row['build']]
            with self.subTest(engine=row['build']):
                result = run_native(engine, action_program(engine, profiles))
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                value = json.loads(result.stdout)
                self.assertEqual(value['status'], 'PASS')
                self.assertEqual(value['profiles'], len(profiles))
                self.assertGreaterEqual(value['checks'], 1000*len(profiles))
        self.assertGreater(selected, 0)

    def test_native_rise_state_calls_arguments_and_rng_by_profile(self):
        self._check_native_profiles(False)

    def test_scalar_point_rise_state_calls_arguments_and_rng_by_profile(self):
        self._check_native_profiles(True)

    def test_wrong_action_refusal_fails_a_defined_result(self):
        pin = json.loads((ROOT / 'src/pin.json').read_text())
        engine = ROOT / 'src/engines/3400'
        profile = next(p for p in pin['profiles'] if p['build'] == '3400')
        text = '#define REFUSAL_ONLY 1\n'+action_program(engine, [profile], wrong_refusal=True)
        result = run_native(engine, text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('set_riseattack(NULL', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)

    def test_unsigned_timing_span_preserves_native_modulus(self):
        result = run_native(ROOT / 'src/engines/3400', timing_program())
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['status'], 'PASS')
        self.assertEqual(value['checks'], 1702)
        self.assertIn(value['long_bits'], (32, 64))

    def test_wrong_empty_span_fails_a_logical_result_without_memory_fault(self):
        result = run_native(ROOT / 'src/engines/3400', timing_program(wrong_empty_span=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('expected', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertNotIn('ERROR: AddressSanitizer', result.stderr)


if __name__ == '__main__':
    unittest.main()
